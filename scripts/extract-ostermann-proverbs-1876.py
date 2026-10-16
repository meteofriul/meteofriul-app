#!/usr/bin/env python3
"""Build a reviewable source archive from Ostermann's 1876 proverb volume.

The generated records are source material only. They must never be read directly
by the app or promoted to ``proverbs.json`` without editorial review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps
from pypdf import PdfReader


SOURCE_PAGE_URL = (
    "https://www.techeudine.it/biblioteche-digital-furlane/"
    "proverbi-friulani-raccolti-dalla-viva-voce-del-popolo"
)
FACSIMILE_URL = (
    "https://manoscrittisbhu.comune.udine.it/uploads/BDF/LO11116556.pdf"
)
DEFAULT_FIRST_CONTENT_PAGE = 19
DEFAULT_LAST_CONTENT_PAGE = 307
PRINTED_PAGE_OFFSET = -4

SECTION_STARTS = (
    (19, "religion_superstition"),
    (26, "weather_calendar"),
    (40, "harvest_agriculture"),
    (51, "animals_pastoral_hunting_fishing"),
    (62, "human_body"),
    (76, "bodily_needs_and_traits"),
    (89, "food_and_drink"),
    (98, "love_and_family"),
    (112, "companionship_and_friends"),
    (120, "social_conditions_and_professions"),
    (133, "work_and_idleness"),
    (144, "activity_and_opportunity"),
    (151, "prudence_in_action"),
    (163, "manners_and_conduct"),
    (174, "experience"),
    (178, "habits"),
    (182, "business_and_affairs"),
    (193, "household_economy"),
    (208, "wealth_and_happiness"),
    (214, "pride_boasting_cowardice_envy"),
    (221, "adversity_and_comfort"),
    (236, "prudence_in_speech"),
    (244, "slander"),
    (250, "simulation_and_lies"),
    (255, "insults_anger_ingratitude"),
    (258, "jokes_and_mockery"),
    (264, "games"),
    (268, "ignorance_and_progress"),
    (275, "responsibility_and_consequences"),
    (282, "public_life_law_government"),
    (288, "places_and_historical_memories"),
    (302, "general_maxims"),
)

HIGH_VALUE_SECTIONS = {
    "weather_calendar": 55,
    "harvest_agriculture": 50,
    "animals_pastoral_hunting_fishing": 32,
    "work_and_idleness": 25,
    "activity_and_opportunity": 25,
    "prudence_in_action": 25,
    "experience": 25,
    "household_economy": 20,
    "responsibility_and_consequences": 20,
    "general_maxims": 28,
}

WEATHER_HINT_RE = re.compile(
    r"\b(?:timp|ploe|ploie|neve|niv|fred|fr[eé]d|soreli|sor[eé]li|lune|"
    r"arcobalen|burasc|tempor|vent|aiar|cald|canicol|rosade|brume|"
    r"nuvol|montane|gla[cz]|invier|primever|istat|autun)\w*\b",
    re.IGNORECASE,
)
DATE_HINT_RE = re.compile(
    r"\b(?:genar|genn|febr|mar[cz]|avril|aprile|mai|maggio|jugn|giugn|"
    r"lui|luglio|agost|setembr|ottobr|novembr|dicembr|nad[aâ]l|pasch|"
    r"epifani|san|sant|sante)\w*\b",
    re.IGNORECASE,
)
REVIEW_RISK_RE = re.compile(
    r"\b(?:femmini|femmine|mogli|ebre|zingar|bastard|storpi|mat|muss|"
    r"diaul|diavol)\w*\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OcrTools:
    pdftoppm: Path
    tesseract: Path
    dpi: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract the complete 1876 Ostermann proverb source archive."
    )
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/data/ostermann-proverbs-1876"),
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("tmp/ostermann-proverbs-1876-ocr-cache"),
    )
    parser.add_argument("--first-page", type=int, default=DEFAULT_FIRST_CONTENT_PAGE)
    parser.add_argument("--last-page", type=int, default=DEFAULT_LAST_CONTENT_PAGE)
    parser.add_argument(
        "--ocr",
        choices=("none", "missing", "all"),
        default="missing",
        help="OCR policy. 'missing' reuses cached page OCR when available.",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument("--pdftoppm", type=Path)
    parser.add_argument("--tesseract", type=Path)
    return parser.parse_args()


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFC", value or "")
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    compact: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if compact and not previous_blank:
                compact.append("")
            previous_blank = True
            continue
        compact.append(line)
        previous_blank = False
    return "\n".join(compact).strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def resolve_executable(explicit: Path | None, candidates: list[str]) -> Path:
    if explicit:
        resolved = explicit.expanduser().resolve()
        if resolved.is_file():
            return resolved
        raise FileNotFoundError(f"Executable not found: {resolved}")

    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return Path(found).resolve()
        path = Path(candidate)
        if path.is_file():
            return path.resolve()
    raise FileNotFoundError(f"Executable not found. Tried: {', '.join(candidates)}")


def section_for_page(page_number: int) -> str:
    section = "front_matter"
    for start_page, candidate in SECTION_STARTS:
        if page_number < start_page:
            break
        section = candidate
    return section


def crop_for_ocr(image_path: Path) -> None:
    with Image.open(image_path) as source:
        width, height = source.size
        crop = source.crop(
            (
                int(width * 0.07),
                int(height * 0.055),
                int(width * 0.93),
                int(height * 0.92),
            )
        )
        grayscale = ImageOps.grayscale(crop)
        enhanced = ImageOps.autocontrast(grayscale, cutoff=1)
        enhanced.save(image_path)


def ocr_page(
    pdf_path: Path,
    page_number: int,
    cache_dir: Path,
    tools: OcrTools,
    force: bool,
) -> tuple[int, str]:
    cache_file = cache_dir / f"page-{page_number:03d}.txt"
    if cache_file.is_file() and not force:
        return page_number, normalize_text(cache_file.read_text(encoding="utf-8"))

    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"ostermann-{page_number:03d}-") as temp:
        image_path = Path(temp) / "page.png"
        output_base = Path(temp) / "page"
        subprocess.run(
            [
                str(tools.pdftoppm),
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-singlefile",
                "-png",
                "-r",
                str(tools.dpi),
                str(pdf_path),
                str(output_base),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        crop_for_ocr(image_path)
        completed = subprocess.run(
            [
                str(tools.tesseract),
                str(image_path),
                "stdout",
                "-l",
                "ita+eng",
                "--psm",
                "4",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        text = normalize_text(completed.stdout.decode("utf-8", errors="replace"))

    cache_file.write_text(text + "\n", encoding="utf-8")
    return page_number, text


def line_kind(text: str) -> str:
    stripped = text.strip()
    letters = "".join(char for char in stripped if char.isalpha())
    if not stripped:
        return "blank"
    if re.fullmatch(r"[\dIVXLCDM.\- ]+", stripped, flags=re.IGNORECASE):
        return "page_number_or_marker"
    if letters and len(stripped) <= 90 and letters.upper() == letters:
        return "heading"
    if len(stripped) > 180:
        return "long_editorial_text"
    if re.match(r"^(cio[eè]|nota|letteralmente|vale a dire|ossia)\b", stripped, re.I):
        return "editorial_note"
    return "proverb_or_fragment"


def block_kind(text: str) -> str:
    flattened = " ".join(line.strip() for line in text.splitlines() if line.strip())
    letters = "".join(char for char in flattened if char.isalpha())
    if re.fullmatch(r"[\dIVXLCDM.\- ]+", flattened, flags=re.IGNORECASE):
        return "page_number_or_marker"
    if letters and len(flattened) <= 110 and letters.upper() == letters:
        return "heading"
    if len(flattened) > 320:
        return "long_editorial_text"
    return "candidate_block"


def candidate_score(section: str, text: str) -> tuple[int, list[str]]:
    flattened = " ".join(line.strip() for line in text.splitlines() if line.strip())
    score = HIGH_VALUE_SECTIONS.get(section, 8)
    reasons = [f"section:{section}"]

    if WEATHER_HINT_RE.search(flattened):
        score += 28
        reasons.append("weather_or_season")
    if DATE_HINT_RE.search(flattened):
        score += 20
        reasons.append("calendar_anchor")
    if 18 <= len(flattened) <= 180:
        score += 15
        reasons.append("editorial_length")
    elif len(flattened) > 320:
        score -= 45
        reasons.append("long_block")
    if 1 <= len(text.splitlines()) <= 4:
        score += 8
        reasons.append("compact_block")
    if REVIEW_RISK_RE.search(flattened):
        score -= 35
        reasons.append("sensitive_or_outdated_review")

    return score, reasons


def preferred_text(embedded: str, ocr: str) -> tuple[str, str]:
    if ocr and len(ocr) >= max(80, int(len(embedded) * 0.45)):
        return ocr, "tesseract_ita_eng"
    return embedded, "embedded_pdf_text"


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf.expanduser().resolve()
    output_dir = args.output.expanduser().resolve()
    cache_dir = args.cache.expanduser().resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)
    first_page = max(1, args.first_page)
    last_page = min(page_count, args.last_page)
    if first_page > last_page:
        raise ValueError(f"Invalid page range: {first_page}-{last_page}")

    embedded_by_page: dict[int, str] = {}
    for page_number in range(first_page, last_page + 1):
        embedded_by_page[page_number] = normalize_text(
            reader.pages[page_number - 1].extract_text() or ""
        )

    ocr_by_page: dict[int, str] = {}
    if args.ocr != "none":
        tools = OcrTools(
            pdftoppm=resolve_executable(
                args.pdftoppm,
                [
                    str(
                        Path.home()
                        / ".cache/codex-runtimes/codex-primary-runtime/dependencies/"
                        "native/poppler/Library/bin/pdftoppm.exe"
                    ),
                    "pdftoppm",
                ],
            ),
            tesseract=resolve_executable(
                args.tesseract,
                [r"C:\Program Files\Tesseract-OCR\tesseract.exe", "tesseract"],
            ),
            dpi=args.dpi,
        )
        force = args.ocr == "all"
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            jobs = {
                executor.submit(
                    ocr_page, pdf_path, page_number, cache_dir, tools, force
                ): page_number
                for page_number in range(first_page, last_page + 1)
            }
            done = 0
            for future in as_completed(jobs):
                page_number, text = future.result()
                ocr_by_page[page_number] = text
                done += 1
                if done == 1 or done % 25 == 0 or done == len(jobs):
                    print(f"OCR pages: {done}/{len(jobs)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    pages_path = output_dir / "master-pages.jsonl"
    lines_path = output_dir / "source-lines.csv"
    blocks_path = output_dir / "source-blocks.csv"
    source_path = output_dir / "source.json"
    report_path = output_dir / "quality-report.json"

    page_records: list[dict] = []
    source_lines: list[dict] = []
    source_blocks: list[dict] = []
    kind_counts: Counter[str] = Counter()
    for page_number in range(first_page, last_page + 1):
        embedded = embedded_by_page[page_number]
        ocr = ocr_by_page.get(page_number, "")
        selected, selected_source = preferred_text(embedded, ocr)
        page_record = {
            "schemaVersion": 1,
            "pdfPage": page_number,
            "printedPage": page_number + PRINTED_PAGE_OFFSET,
            "embeddedText": embedded,
            "ocrText": ocr,
            "preferredTextSource": selected_source,
            "preferredText": selected,
            "quality": {
                "embeddedReplacementChars": embedded.count("\ufffd"),
                "ocrReplacementChars": ocr.count("\ufffd"),
                "preferredChars": len(selected),
                "preferredNonEmptyLines": sum(
                    1 for line in selected.splitlines() if line.strip()
                ),
            },
            "reviewStatus": "raw_source_not_publishable",
        }
        page_records.append(page_record)

        section = section_for_page(page_number)
        block_number = 0
        for raw_block in re.split(r"\n\s*\n", selected):
            block_text = "\n".join(
                line.strip() for line in raw_block.splitlines() if line.strip()
            ).strip()
            if not block_text:
                continue
            block_number += 1
            kind = block_kind(block_text)
            score, score_reasons = candidate_score(section, block_text)
            source_blocks.append(
                {
                    "block_id": f"ost1876-p{page_number:03d}-b{block_number:03d}",
                    "pdf_page": page_number,
                    "printed_page": page_number + PRINTED_PAGE_OFFSET,
                    "block_number": block_number,
                    "section": section,
                    "kind": kind,
                    "score": score,
                    "priority": (
                        "P1" if score >= 70 else "P2" if score >= 45 else "P3"
                    ),
                    "weather_hint": "yes" if WEATHER_HINT_RE.search(block_text) else "no",
                    "date_hint": "yes" if DATE_HINT_RE.search(block_text) else "no",
                    "review_risk": "yes" if REVIEW_RISK_RE.search(block_text) else "no",
                    "score_reasons": ";".join(score_reasons),
                    "text": block_text.replace("\n", " / "),
                    "review_status": "raw_unreviewed",
                    "publish": "no",
                }
            )

        line_number = 0
        for raw_line in selected.splitlines():
            text = raw_line.strip()
            if not text:
                continue
            line_number += 1
            kind = line_kind(text)
            kind_counts[kind] += 1
            source_lines.append(
                {
                    "line_id": f"ost1876-p{page_number:03d}-l{line_number:03d}",
                    "pdf_page": page_number,
                    "printed_page": page_number + PRINTED_PAGE_OFFSET,
                    "line_number": line_number,
                    "section": section,
                    "kind": kind,
                    "text": text,
                    "review_status": "raw_unreviewed",
                    "publish": "no",
                }
            )

    with pages_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in page_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    with lines_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(source_lines[0].keys()))
        writer.writeheader()
        writer.writerows(source_lines)

    with blocks_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(source_blocks[0].keys()))
        writer.writeheader()
        writer.writerows(source_blocks)

    source_record = {
        "schemaVersion": 1,
        "id": "ostermann-proverbi-friulani-1876",
        "title": "Proverbi friulani raccolti dalla viva voce del popolo",
        "author": "Valentino Ostermann",
        "publicationYear": 1876,
        "publisher": "Tipografia di G. B. Doretti e soci, Udine",
        "cataloguePage": SOURCE_PAGE_URL,
        "facsimileUrl": FACSIMILE_URL,
        "pdfSha256": sha256_file(pdf_path),
        "pdfPages": page_count,
        "extractedPdfPages": {"first": first_page, "last": last_page},
        "printedPageOffset": PRINTED_PAGE_OFFSET,
        "workflowRule": (
            "Raw source archive only. Every proverb must be checked against the "
            "facsimile, normalized in FUR, translated and reviewed before promotion."
        ),
    }
    source_path.write_text(
        json.dumps(source_record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report = {
        "schemaVersion": 1,
        "pages": len(page_records),
        "sourceLines": len(source_lines),
        "sourceBlocks": len(source_blocks),
        "candidateBlocks": sum(
            1 for block in source_blocks if block["kind"] == "candidate_block"
        ),
        "priorityBlocks": {
            priority: sum(1 for block in source_blocks if block["priority"] == priority)
            for priority in ("P1", "P2", "P3")
        },
        "lineKinds": dict(sorted(kind_counts.items())),
        "pagesUsingOcr": sum(
            1
            for record in page_records
            if record["preferredTextSource"] == "tesseract_ita_eng"
        ),
        "pagesUsingEmbeddedText": sum(
            1
            for record in page_records
            if record["preferredTextSource"] == "embedded_pdf_text"
        ),
        "rawReplacementChars": sum(
            record["quality"]["embeddedReplacementChars"] for record in page_records
        ),
        "ocrReplacementChars": sum(
            record["quality"]["ocrReplacementChars"] for record in page_records
        ),
        "publicationRule": "No source line is publishable without editorial review.",
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Source archive: {output_dir}")
    print(f"Pages: {len(page_records)}")
    print(f"Source lines: {len(source_lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
