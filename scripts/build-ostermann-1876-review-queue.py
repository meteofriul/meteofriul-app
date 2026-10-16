#!/usr/bin/env python3
"""Build a deterministic editorial queue from the raw Ostermann archive."""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Ostermann review queue.")
    parser.add_argument(
        "--blocks",
        type=Path,
        default=Path("scripts/data/ostermann-proverbs-1876/source-blocks.csv"),
    )
    parser.add_argument(
        "--existing",
        type=Path,
        default=Path("frontend/src/data/almanac/proverbs.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/data/ostermann-proverbs-1876/review-queue.csv"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("scripts/data/ostermann-proverbs-1876/review-queue-summary.json"),
    )
    return parser.parse_args()


def repair_mojibake(value: str) -> str:
    text = value or ""
    for _ in range(2):
        if not any(marker in text for marker in ("Ã", "Å", "Ä", "â")):
            break
        for encoding in ("cp1252", "latin1"):
            try:
                repaired = text.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if repaired.count("Ã") + repaired.count("Å") < text.count("Ã") + text.count("Å"):
                text = repaired
                break
        else:
            break
    return text


def normalize_for_match(value: str) -> str:
    text = repair_mojibake(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if char.isalpha() or char.isspace())
    return " ".join(text.split())


def source_printed_page(source: str) -> int | None:
    match = re.search(r"Ostermann 1876, p\.\s*(\d+)", source or "", re.I)
    return int(match.group(1)) if match else None


def existing_match(candidate: str, existing: list[dict]) -> tuple[float, str, str]:
    normalized = normalize_for_match(candidate)
    best_score = 0.0
    best_id = ""
    best_field = ""
    if not normalized:
        return best_score, best_id, best_field

    for record in existing:
        for field in ("fur_original", "fur", "it"):
            other = record.get(f"_{field}", "")
            if not other:
                continue
            score = difflib.SequenceMatcher(None, normalized, other).ratio()
            if score > best_score:
                best_score = score
                best_id = record.get("id", "")
                best_field = field
    return best_score, best_id, best_field


def queue_status(block: dict, similarity: float, same_page: bool) -> str:
    if similarity >= 0.78 or (same_page and similarity >= 0.62):
        return "probable_existing"
    if similarity >= 0.58 or (same_page and similarity >= 0.45):
        return "possible_existing"
    if block["review_risk"] == "yes":
        return "sensitive_review"
    if len(block["text"]) > 220 or block["text"].count(" / ") >= 4:
        return "split_or_context_review"
    return "new_candidate_review"


def main() -> int:
    args = parse_args()
    with args.blocks.open(encoding="utf-8-sig", newline="") as handle:
        blocks = list(csv.DictReader(handle))
    existing = json.loads(args.existing.read_text(encoding="utf-8"))
    for record in existing:
        for field in ("fur_original", "fur", "it"):
            record[f"_{field}"] = normalize_for_match(record.get(field, ""))
        record["_printed_page"] = source_printed_page(record.get("source", ""))

    queue: list[dict] = []
    for block in blocks:
        if block["kind"] != "candidate_block" or block["priority"] not in {"P1", "P2"}:
            continue
        similarity, match_id, match_field = existing_match(block["text"], existing)
        matched = next((record for record in existing if record.get("id") == match_id), None)
        same_page = bool(
            matched
            and matched.get("_printed_page")
            and matched["_printed_page"] == int(block["printed_page"])
        )
        status = queue_status(block, similarity, same_page)
        queue.append(
            {
                "queue_order": 0,
                "block_id": block["block_id"],
                "pdf_page": block["pdf_page"],
                "printed_page": block["printed_page"],
                "section": block["section"],
                "source_priority": block["priority"],
                "source_score": block["score"],
                "queue_status": status,
                "existing_match_id": match_id,
                "existing_match_field": match_field,
                "existing_similarity": f"{similarity:.3f}",
                "same_source_page": "yes" if same_page else "no",
                "weather_hint": block["weather_hint"],
                "date_hint": block["date_hint"],
                "review_risk": block["review_risk"],
                "editorial_decision": "pending",
                "text": block["text"],
            }
        )

    status_order = {
        "new_candidate_review": 0,
        "split_or_context_review": 1,
        "possible_existing": 2,
        "sensitive_review": 3,
        "probable_existing": 4,
    }
    queue.sort(
        key=lambda item: (
            0 if item["source_priority"] == "P1" else 1,
            status_order[item["queue_status"]],
            -int(item["source_score"]),
            int(item["pdf_page"]),
            item["block_id"],
        )
    )
    for index, item in enumerate(queue, start=1):
        item["queue_order"] = index

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(queue[0].keys()))
        writer.writeheader()
        writer.writerows(queue)

    status_counts = Counter(item["queue_status"] for item in queue)
    summary = {
        "schemaVersion": 1,
        "records": len(queue),
        "priorities": {
            priority: sum(item["source_priority"] == priority for item in queue)
            for priority in ("P1", "P2")
        },
        "statuses": dict(sorted(status_counts.items())),
        "rule": (
            "Similarity only orders review. It never excludes, translates or publishes a record."
        ),
    }
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
