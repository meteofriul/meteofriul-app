from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "scripts" / "data" / "ostermann-proverbs-1876"
DECISION_FILES = "review-decisions-batch-*.json"
LANGUAGE_FILES = "language-review-batch-*.json"
PROVERBS = ROOT / "frontend" / "src" / "data" / "almanac" / "proverbs.json"

ALLOWED_STATUSES = {
    "language_reviewed",
    "merge_existing",
    "needs_native_review",
}
ALLOWED_DESTINATIONS = {"almanac", "discover"}
ALLOWED_CALENDAR_RULES = {
    "date",
    "date_range",
    "general",
    "months",
    "moon_shape",
    "movable_feast",
    "seasons",
    "weather_condition",
}


def fail(message: str) -> None:
    raise SystemExit(f"Language reviews invalid: {message}")


def load_decisions() -> tuple[dict[str, dict], dict[str, str]]:
    decisions: dict[str, dict] = {}
    decision_files: dict[str, str] = {}
    for path in sorted(DATA_DIR.glob(DECISION_FILES)):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for record in payload.get("records", []):
            record_id = record.get("id")
            if record_id in decisions:
                fail(f"duplicate preliminary decision {record_id}")
            decisions[record_id] = record
            decision_files[record_id] = path.name
    return decisions, decision_files


def validate_calendar_rule(record_id: str, rule: dict) -> None:
    rule_type = rule.get("type")
    if rule_type not in ALLOWED_CALENDAR_RULES:
        fail(f"{record_id} has unknown calendar rule {rule_type!r}")
    if not isinstance(rule.get("fallbackAllowed"), bool):
        fail(f"{record_id} must declare fallbackAllowed")

    if rule_type == "date":
        day = rule.get("day")
        month = rule.get("month")
        if not isinstance(day, int) or not 1 <= day <= 31:
            fail(f"{record_id} has invalid day")
        if not isinstance(month, int) or not 1 <= month <= 12:
            fail(f"{record_id} has invalid month")
    elif rule_type == "date_range":
        for boundary_name in ("from", "to"):
            boundary = rule.get(boundary_name) or {}
            day = boundary.get("day")
            month = boundary.get("month")
            if not isinstance(day, int) or not 1 <= day <= 31:
                fail(f"{record_id} has invalid {boundary_name} day")
            if not isinstance(month, int) or not 1 <= month <= 12:
                fail(f"{record_id} has invalid {boundary_name} month")
    elif rule_type == "months":
        months = rule.get("months")
        if not months or any(not isinstance(month, int) or not 1 <= month <= 12 for month in months):
            fail(f"{record_id} has invalid months")
    elif rule_type == "seasons":
        seasons = rule.get("seasons")
        allowed_seasons = {"spring", "summer", "autumn", "winter"}
        if not seasons or any(season not in allowed_seasons for season in seasons):
            fail(f"{record_id} has invalid seasons")
    elif rule_type == "weather_condition" and not rule.get("phenomena"):
        fail(f"{record_id} has no weather phenomena")
    elif rule_type == "movable_feast" and not rule.get("feast"):
        fail(f"{record_id} has no movable feast")


def main() -> None:
    decisions, decision_files = load_decisions()
    eligible_ids = {
        record_id
        for record_id, record in decisions.items()
        if record.get("recommendation") == "promote_after_language_review"
    }
    existing_proverb_ids = {
        record.get("id")
        for record in json.loads(PROVERBS.read_text(encoding="utf-8"))
    }
    language_files = sorted(DATA_DIR.glob(LANGUAGE_FILES))
    if not language_files:
        fail("no language review batch found")

    seen_ids: set[str] = set()
    statuses: Counter[str] = Counter()

    for path in language_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("records", [])
        source_files = set(payload.get("sourceDecisionFiles") or [])
        summary = payload.get("summary", {})
        expected_summary = {
            "records": len(records),
            "languageReviewed": sum(record.get("reviewStatus") == "language_reviewed" for record in records),
            "mergeExisting": sum(record.get("reviewStatus") == "merge_existing" for record in records),
            "needsNativeReview": sum(record.get("reviewStatus") == "needs_native_review" for record in records),
        }
        if summary != expected_summary:
            fail(f"{path.name} summary does not match its records")

        for record in records:
            record_id = record.get("id")
            if not record_id or record_id in seen_ids:
                fail(f"missing or duplicate language review id: {record_id!r}")
            seen_ids.add(record_id)

            if record_id not in eligible_ids:
                fail(f"{record_id} is not eligible for language review")
            if decision_files[record_id] not in source_files:
                fail(f"{record_id} does not belong to a declared source decision file")
            if record.get("publish") is not False:
                fail(f"{record_id} must remain publish=false")
            if record.get("reviewStatus") not in ALLOWED_STATUSES:
                fail(f"{record_id} has an unknown review status")
            if record.get("destination") not in ALLOWED_DESTINATIONS:
                fail(f"{record_id} has an unknown destination")
            if not record.get("itFinal"):
                fail(f"{record_id} has no final Italian copy")
            if not record.get("evidence"):
                fail(f"{record_id} has no review evidence")

            status = record["reviewStatus"]
            if status == "needs_native_review":
                if not record.get("furDraft") or record.get("furNormalized"):
                    fail(f"{record_id} must expose only a FUR draft")
            elif not record.get("furNormalized"):
                fail(f"{record_id} has no normalized FUR copy")

            if status == "merge_existing":
                merge_id = record.get("mergeExistingId")
                if merge_id not in existing_proverb_ids:
                    fail(f"{record_id} references unknown existing proverb {merge_id!r}")
                duplicate_audit = record.get("duplicateAudit") or {}
                if duplicate_audit.get("existingId") != merge_id:
                    fail(f"{record_id} merge target and duplicate audit disagree")

            validate_calendar_rule(record_id, record.get("calendarRule") or {})
            statuses[status] += 1

    print(
        json.dumps(
            {
                "eligibleDecisionRecords": len(eligible_ids),
                "languageReviewRecords": len(seen_ids),
                "remainingDecisionRecords": len(eligible_ids - seen_ids),
                "reviewStatuses": dict(sorted(statuses.items())),
                "publishedRecords": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
