"""Scheduler event identity, independent of receipt/execution/container times."""
from datetime import datetime, timezone
import re
from .core import instant, slot, stamp, STEP

PROJECT = "meteo-friul"
REGION = "europe-west1"
JOB = "meteofriul-icon2i-freshness"
DISPATCHER = JOB + "-dispatch"
SCHEDULER = f"projects/{PROJECT}/locations/{REGION}/jobs/{JOB}"
JOB_RESOURCE = f"projects/{PROJECT}/locations/{REGION}/jobs/{JOB}"
# Only applies to the immutable source timestamp, never to receipt/createTime.
SOURCE_OFFSET_SECONDS = 120


class ExpiredSlot(ValueError):
    pass


def scheduler_time(value):
    """Parse an explicit RFC3339 source instant; no naive/local timestamps."""
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})", value):
        raise ValueError("invalid scheduler timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def scheduler_slot(value):
    """Canonicalize only the stable source header within a bounded cron window."""
    source = scheduler_time(value)
    planned = source.replace(minute=10 if source.minute < 40 else 40, second=0, microsecond=0)
    if planned > source:
        planned -= STEP
    if not 0 <= (source - planned).total_seconds() <= SOURCE_OFFSET_SECONDS:
        raise ValueError("scheduler timestamp outside the configured cron window")
    return slot(planned)


def require_active_slot(planned, now):
    planned, now = slot(planned), instant(now)
    if now < planned:
        raise ValueError("future scheduled slot")
    if now - planned >= STEP:
        raise ExpiredSlot("scheduled slot expired; never relabel it as a later slot")
    return planned


def forwarded_slot(planned, source_time=None):
    planned = slot(planned)
    if source_time is not None and scheduler_slot(source_time) != planned:
        raise ValueError("scheduler source and explicit slot differ")
    return planned


def require_delivery(planned, source_time, now):
    planned = forwarded_slot(planned, source_time)
    if source_time is not None and scheduler_time(source_time) > instant(now):
        raise ValueError("future scheduler source time")
    return require_active_slot(planned, now)


def job_overrides(planned, source_time):
    planned = forwarded_slot(planned, source_time)
    return {"overrides": {"containerOverrides": [{"args": [
        "--cloud", "--scheduled-slot", stamp(planned),
        "--scheduler-schedule-time", source_time]}], "taskCount": 1, "timeout": "120s"}}
