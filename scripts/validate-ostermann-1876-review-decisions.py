from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "scripts" / "data" / "ostermann-proverbs-1876"
SOURCE_BLOCKS = DATA_DIR / "source-blocks.csv"
DECISION_FILES = "review-decisions-batch-*.json"

ALLOWED_RECOMMENDATIONS = {
    "promote_after_language_review",
    "needs_context",
    "needs_language_context",
    "secondary_variant",
}


def fail(message: str) -> None:
    raise SystemExit(f"Review decisions invalid: {message}")


def load_source_blocks() -> dict[str, dict[str, str]]:
    with SOURCE_BLOCKS.open(encoding="utf-8-sig", newline="") as handle:
        return {row["block_id"]: row for row in csv.DictReader(handle)}


def main() -> None:
    source_blocks = load_source_blocks()
    decision_files = sorted(DATA_DIR.glob(DECISION_FILES))
    if not decision_files:
        fail("no decision batch found")

    seen_record_ids: set[str] = set()
    totals: Counter[str] = Counter()
    reviewed_source_blocks: set[str] = set()

    for path in decision_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("records", [])
        summary = payload.get("summary", {})

        expected_summary = {
            "records": len(records),
            "promoteAfterLanguageReview": sum(
                record.get("recommendation") == "promote_after_language_review"
                for record in records
            ),
            "needsContextOrLanguageReview": sum(
                record.get("recommendation")
                in {"needs_context", "needs_language_context"}
                for record in records
            ),
            "secondaryVariant": sum(
                record.get("recommendation") == "secondary_variant"
                for record in records
            ),
        }
        if summary != expected_summary:
            fail(f"{path.name} summary does not match its records")

        for record in records:
            record_id = record.get("id")
            if not record_id or record_id in seen_record_ids:
                fail(f"missing or duplicate record id: {record_id!r}")
            seen_record_ids.add(record_id)

            if record.get("publish") is not False:
                fail(f"{record_id} must remain publish=false")
            if record.get("recommendation") not in ALLOWED_RECOMMENDATIONS:
                fail(f"{record_id} has an unknown recommendation")
            if not record.get("furOriginal") or not record.get("proposedIt"):
                fail(f"{record_id} is missing source text or Italian draft")

            block_ids = record.get("sourceBlockIds") or []
            if not block_ids:
                fail(f"{record_id} has no source block")
            for block_id in block_ids:
                source_block = source_blocks.get(block_id)
                if source_block is None:
                    fail(f"{record_id} references unknown block {block_id}")
                if int(source_block["pdf_page"]) != record.get("pdfPage"):
                    fail(f"{record_id} has a PDF page mismatch")
                if int(source_block["printed_page"]) != record.get("printedPage"):
                    fail(f"{record_id} has a printed page mismatch")
                reviewed_source_blocks.add(block_id)

            totals[record["recommendation"]] += 1

    print(
        json.dumps(
            {
                "batches": len(decision_files),
                "decisionRecords": len(seen_record_ids),
                "reviewedSourceBlocks": len(reviewed_source_blocks),
                "recommendations": dict(sorted(totals.items())),
                "publishedRecords": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
