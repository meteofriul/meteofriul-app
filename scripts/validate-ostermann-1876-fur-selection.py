from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "scripts" / "data" / "ostermann-proverbs-1876"
LANGUAGE_FILES = "language-review-batch-*.json"
IT_SELECTION = DATA_DIR / "editorial-selection-it.json"
FUR_SELECTION = DATA_DIR / "editorial-selection-fur.json"
PROMOTED_IT_DECISIONS = {
    "approve_almanac",
    "approve_discover",
    "hold_runtime_condition",
}


def fail(message: str) -> None:
    raise SystemExit(f"Friulian editorial selection invalid: {message}")


def load_language_records() -> dict[str, dict]:
    records: dict[str, dict] = {}
    for path in sorted(DATA_DIR.glob(LANGUAGE_FILES)):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for record in payload.get("records", []):
            record_id = record.get("id")
            if not record_id or record_id in records:
                fail(f"missing or duplicate language record {record_id!r}")
            records[record_id] = record
    return records


def main() -> None:
    language_records = load_language_records()
    it_payload = json.loads(IT_SELECTION.read_text(encoding="utf-8"))
    fur_payload = json.loads(FUR_SELECTION.read_text(encoding="utf-8"))

    expected_ids = {
        record["id"]
        for record in it_payload.get("records", [])
        if record.get("decision") in PROMOTED_IT_DECISIONS
    }
    approved_ids = fur_payload.get("approvedIds", [])
    approved_set = set(approved_ids)

    if len(approved_ids) != len(approved_set):
        fail("approvedIds contains duplicates")
    if approved_set != expected_ids:
        fail(
            "FUR coverage does not match the promoted IT records; "
            f"missing={sorted(expected_ids - approved_set)}, "
            f"extra={sorted(approved_set - expected_ids)}"
        )

    for record_id in approved_ids:
        record = language_records.get(record_id)
        if not record:
            fail(f"unknown language record {record_id}")
        if record.get("reviewStatus") != "language_reviewed":
            fail(f"{record_id} is not language_reviewed")
        fur_text = record.get("furNormalized")
        if not fur_text:
            fail(f"{record_id} has no normalized FUR copy")
        if fur_text == record.get("itFinal"):
            fail(f"{record_id} repeats the Italian copy in FUR")
        if record.get("publish") is not False:
            fail(f"{record_id} must remain publish=false")

    summary = fur_payload.get("summary", {})
    expected_summary = {
        "records": len(approved_ids),
        "approvedNormalized": len(approved_ids),
        "requiresNativeReview": 0,
        "publishedRecords": 0,
    }
    if summary != expected_summary:
        fail(f"summary mismatch; expected {expected_summary}, found {summary}")

    print(
        json.dumps(
            {
                "promotedItalianRecords": len(expected_ids),
                "approvedFriulianRecords": len(approved_ids),
                "requiresNativeReview": 0,
                "publishedRecords": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
