"""CAMS-only operational bounds; public availability is never proof of data quality."""
from datetime import timedelta, timezone

SCHEDULE_HOURS_UTC = (9, 10, 11, 15, 20)
FULL_FORECAST_DEADLINE_UTC = 10
TASK_TIMEOUT_SECONDS = 1200
RECOVERY_BUDGET_SECONDS = 900
ADS_WAIT_SECONDS = 120
RECOVERY_DELAYS = (30, 60, 120)
REGIONAL_PASS_RESERVE_SECONDS = 480
UV_PASS_RESERVE_SECONDS = 180
# Only explicit absence/incompleteness is expected before the provider deadline.
# Ambiguous rows, disabled catalogues, changed schemas and transport errors
# must remain failures rather than successful availability probes.
_AVAILABILITY_REASONS = frozenset({
    "constraints_incomplete_leads", "constraints_no_date_rows",
    "catalogue_date_unavailable", "form_date_unavailable",
})

def next_schedule_at(now):
    if now.tzinfo is None:
        raise ValueError("CAMS operational times must be timezone-aware")
    now = now.astimezone(timezone.utc)
    for hour in SCHEDULE_HOURS_UTC:
        candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate > now:
            return candidate.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (now + timedelta(days=1)).replace(hour=SCHEDULE_HOURS_UTC[0],
        minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

def source_deferral(error, now):
    from cams_request_plan import PublicMetadataUnavailable
    from local_pipeline.operational_diagnostics import error_fields
    if now.tzinfo is None:
        raise ValueError("CAMS operational times must be timezone-aware")
    if (not isinstance(error, PublicMetadataUnavailable)
            or error_fields(error).get("reason_code") not in _AVAILABILITY_REASONS
            or now.astimezone(timezone.utc).hour >= FULL_FORECAST_DEADLINE_UTC):
        return None
    return {"status": "source_pending", "retryable": True,
            "next_schedule_at": next_schedule_at(now),
            "availability_deadline_utc": now.astimezone(timezone.utc).replace(
                hour=FULL_FORECAST_DEADLINE_UTC, minute=0, second=0,
                microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")}

def retry_reserve(outcomes):
    terminal = {"verified", "disabled", "source_pending", "manual_review", "permanent_failure"}
    return (REGIONAL_PASS_RESERVE_SECONDS if outcomes["air"]["status"] not in terminal else 0) + (
        UV_PASS_RESERVE_SECONDS if outcomes["uv"]["status"] not in terminal else 0)
