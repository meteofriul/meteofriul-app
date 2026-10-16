from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "scripts" / "data" / "ostermann-proverbs-1876"
LANGUAGE_FILES = "language-review-batch-*.json"
SELECTION_FILE = DATA_DIR / "editorial-selection-it.json"

ALLOWED_DECISIONS = {
    "approve_almanac",
    "approve_discover",
    "exclude_editorial",
    "hold_runtime_condition",
    "merge_existing",
}
EXPECTED_TARGETS = {
    "approve_almanac": "almanac",
    "approve_discover": "discover",
    "exclude_editorial": "none",
    "hold_runtime_condition": "almanac",
    "merge_existing": "existing",
}
SUMMARY_KEYS = {
    "approve_almanac": "approveAlmanac",
    "approve_discover": "approveDiscover",
    "exclude_editorial": "excludeEditorial",
    "hold_runtime_condition": "holdRuntimeCondition",
    "merge_existing": "mergeExisting",
}


def fail(message: str) -> None:
    raise SystemExit(f"Italian editorial selection invalid: {message}")


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
    source_records = load_language_records()
    payload = json.loads(SELECTION_FILE.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    selected_ids: set[str] = set()
    counts: Counter[str] = Counter()

    for record in records:
        record_id = record.get("id")
        if not record_id or record_id in selected_ids:
            fail(f"missing or duplicate selection id {record_id!r}")
        selected_ids.add(record_id)

        if record_id not in source_records:
            fail(f"unknown language record {record_id}")
        if not source_records[record_id].get("itFinal"):
            fail(f"{record_id} has no reviewed Italian copy")

        decision = record.get("decision")
        if decision not in ALLOWED_DECISIONS:
            fail(f"{record_id} has unknown decision {decision!r}")
        if record.get("target") != EXPECTED_TARGETS[decision]:
            fail(f"{record_id} target does not match {decision}")
        if not record.get("reason"):
            fail(f"{record_id} has no editorial reason")
        if record.get("publish") is not False:
            fail(f"{record_id} must remain publish=false")
        if decision == "merge_existing" and source_records[record_id].get("reviewStatus") != "merge_existing":
            fail(f"{record_id} is not marked merge_existing by the language review")
        if decision == "hold_runtime_condition":
            rule_type = (source_records[record_id].get("calendarRule") or {}).get("type")
            if rule_type != "weather_condition":
                fail(f"{record_id} has no weather_condition rule")

        counts[decision] += 1

    missing = sorted(set(source_records) - selected_ids)
    extra = sorted(selected_ids - set(source_records))
    if missing or extra:
        fail(f"selection coverage mismatch; missing={missing}, extra={extra}")

    summary = payload.get("summary", {})
    expected_summary = {
        "records": len(records),
        **{summary_key: counts[decision] for decision, summary_key in SUMMARY_KEYS.items()},
        "publishedRecords": 0,
    }
    if summary != expected_summary:
        fail(f"summary mismatch; expected {expected_summary}, found {summary}")

    print(
        json.dumps(
            {
                "sourceRecords": len(source_records),
                "selectedRecords": len(selected_ids),
                "decisions": dict(sorted(counts.items())),
                "publishedRecords": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
