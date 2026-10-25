"""Offline, calendar-aware assessment of the two ordinary forecast summaries.

No cloud clients, delivery imports or mutation capability. Execution identity must
come from a verified Scheduler-to-RunJob binding, never a timestamp guess.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Mapping
import re
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Rome")
PROJECT = "meteo-friul"
REGION = "europe-west1"
HOURS = {"morning": time(7, 30), "evening": time(20, 45)}
GRACE = timedelta(minutes=15)
COUNTERS = ("eligible_devices", "attempted", "sent", "deduplicated", "failed",
            "sent_unconfirmed", "in_progress", "retry_scheduled")


def instant(value: str | datetime) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone-aware instant required")
    return parsed.astimezone(timezone.utc)


def stamp(value: datetime) -> str:
    return instant(value).isoformat().replace("+00:00", "Z")


def expected_slot(kind: str, local_date: date) -> dict[str, str]:
    # Build each civil date separately. A UTC +24h calculation is wrong at DST.
    scheduled = datetime.combine(local_date, HOURS[kind], ZONE).astimezone(timezone.utc)
    job = f"meteofriul-{kind}-forecast"
    resource = f"projects/{PROJECT}/locations/{REGION}/jobs/{job}"
    return {"kind": kind, "local_date": local_date.isoformat(),
            "timezone": ZONE.key, "slot_id": f"{kind}:{local_date.isoformat()}",
            "scheduled_at": stamp(scheduled), "deadline": stamp(scheduled + GRACE),
            "job": resource, "scheduler": resource}


def latest_slots(now: str | datetime) -> list[dict[str, str]]:
    current = instant(now)
    day = current.astimezone(ZONE).date()
    result = []
    for kind in HOURS:
        slot = expected_slot(kind, day)
        if instant(slot["scheduled_at"]) > current:
            slot = expected_slot(kind, day - timedelta(days=1))
        result.append(slot)
    return result


def _delivery(summary: Mapping[str, Any]) -> tuple[str, str]:
    if not isinstance(summary, Mapping):
        raise ValueError("missing application result")
    values = {key: summary.get(key) for key in COUNTERS}
    if any(type(n) is not int or n < 0 for n in values.values()):
        raise ValueError("invalid application counters")
    for key in ("opted_out", "retired_targets"):
        values[key] = summary.get(key, 0)  # Older morning jobs omit retired_targets.
        if type(values[key]) is not int or values[key] < 0:
            raise ValueError("invalid terminal counters")
    accounted = sum(values[key] for key in ("sent", "deduplicated", "sent_unconfirmed",
                                             "in_progress", "retry_scheduled", "opted_out", "retired_targets"))
    if accounted > values["attempted"]:
        raise ValueError("terminal counts exceed attempts")
    status = summary.get("status")
    if values["sent"] + values["deduplicated"] + values["sent_unconfirmed"] > values["attempted"]:
        raise ValueError("inconsistent application counters")
    if values["attempted"] > values["eligible_devices"]:
        raise ValueError("inconsistent eligibility counters")
    failed = values["failed"] or values["sent_unconfirmed"]
    if failed:
        return ("partial" if values["sent"] or values["deduplicated"] else "failed", "delivery_incomplete")
    if status in {"partial", "failed", "configuration_invalid", "device_state_unavailable",
                  "delivery_storage_unavailable", "target_count_invalid"}:
        return "failed", "application_failure"
    if status in {"disabled", "dry_run"}:
        return "inactive", str(status)
    if values["in_progress"] or values["retry_scheduled"] or status in {"in_progress", "retry_scheduled"}:
        return "delivery_pending", "delivery_not_terminal"
    if status == "no_forecast":
        return "no_forecast", "forecast_unavailable"
    if status == "no_eligible_device":
        if values["eligible_devices"] or values["attempted"]:
            raise ValueError("inconsistent empty audience")
        return "completed", "no_eligible_device"
    if status in {"sent", "deduplicated", "opted_out", "retired_targets"}:
        if accounted != values["attempted"]:
            raise ValueError("unaccounted delivery attempts")
        if values["attempted"] != values["eligible_devices"]:
            raise ValueError("unaccounted eligible devices")
    if status == "sent" and values["sent"]:
        return "completed", "fcm_accepted"
    if status == "deduplicated" and values["deduplicated"]:
        return "completed", "deduplicated"
    if status in {"opted_out", "retired_targets"} and values[status] > 0:
        return "completed", str(status)
    raise ValueError("unknown or inconsistent application result")


def evaluate_slot(slot: Mapping[str, str], evidence: Mapping[str, Any], *, now: str | datetime) -> dict:
    """Assess one exact slot from a complete, sanitized evidence bundle.

    schema_version=1; window_start/end delimit complete execution AND binding
    inventories; observed_at is acquisition end; bindings identify exact RunJob
    executions from trusted audit data. A caller must not synthesize bindings
    from nearby timestamps or creatorMatchesScheduler alone.
    """
    current = instant(now)
    canonical = expected_slot(slot["kind"], date.fromisoformat(slot["local_date"]))
    if dict(slot) != canonical:
        raise ValueError("slot differs from unchanged production schedule")
    scheduled, deadline = instant(slot["scheduled_at"]), instant(slot["deadline"])
    result = {**slot, "observed_at": stamp(current), "state": "check_unavailable",
              "reason": "evidence_incomplete", "attention": True,
              "execution": None, "delivery": None, "source_trace": None}

    def finish(state, reason, *, attention=None):
        result.update(state=state, reason=reason,
                      attention=(state not in {"not_due", "waiting", "running", "completed", "completed_late"}
                                 if attention is None else attention))
        return result

    if current < scheduled:
        return finish("not_due", "before_schedule")
    try:
        if type(evidence.get("schema_version")) is not int or evidence["schema_version"] != 1 or evidence.get("complete") is not True:
            return result
        observed = instant(evidence["observed_at"])
        if observed > current or current - observed > timedelta(minutes=5):
            return finish("check_unavailable", "evidence_stale_or_future")
        if instant(evidence["window_start"]) > scheduled or instant(evidence["window_end"]) < observed:
            return finish("check_unavailable", "inventory_window_incomplete")
        executions, bindings = evidence["executions"], evidence["bindings"]
        if not isinstance(executions, list) or not isinstance(bindings, list):
            raise ValueError("invalid inventories")
        matching = []
        for binding in bindings:
            if binding["job"] != slot["job"] or binding["scheduler"] != slot["scheduler"]:
                continue
            if instant(binding["scheduled_at"]) != scheduled:
                continue
            if binding["basis"] != "scheduler_run_job_audit":
                continue
            name = binding["execution"]
            prefix = slot["job"] + "/executions/" + slot["job"].rsplit("/", 1)[-1]
            if not isinstance(name, str) or not re.fullmatch(re.escape(prefix) + r"-[a-z0-9]{1,32}", name):
                raise ValueError("execution outside target")
            if name not in matching:
                matching.append(name)
        if len(matching) > 1:
            return finish("ambiguous", "multiple_ordinary_executions")
        relevant = [e for e in executions if e["job"] == slot["job"]
                    and scheduled <= instant(e["created_at"]) <= observed]
        if not matching:
            # Manual success is explicitly ignored. Unknown origin is not absence.
            unknown = [e for e in relevant if e.get("origin") != "manual"]
            if min(current, observed) < deadline:
                return finish("waiting", "awaiting_ordinary_evidence")
            if unknown:
                return finish("origin_unverified", "execution_not_bound_to_scheduler")
            return finish("missing", "ordinary_execution_absent")
        found = [e for e in executions if e.get("name") == matching[0]]
        if len(found) != 1:
            return finish("check_unavailable", "execution_inventory_ambiguous")
        execution = found[0]
        if execution["job"] != slot["job"] or execution.get("origin") == "manual":
            raise ValueError("conflicting execution identity")
        created = instant(execution["created_at"])
        if created < scheduled or created > observed:
            raise ValueError("execution outside observed slot")
        result["execution"] = matching[0].rsplit("/", 1)[-1]
        completed = execution.get("completed_at")
        if not completed:
            return finish("running_late" if current >= deadline else "running", "execution_not_terminal")
        completed_at = instant(completed)
        if not created <= completed_at <= observed:
            raise ValueError("invalid completion time")
        result["completion_late"] = completed_at > deadline
        runtime = execution["runtime_status"]
        if runtime not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("unknown runtime state")
        summary = execution.get("summary")
        if summary is None:
            return finish("failed" if runtime != "succeeded" else "check_unavailable",
                          "runtime_failure" if runtime != "succeeded" else "application_result_missing")
        state, reason = _delivery(summary)
        result["delivery"] = {key: summary[key] for key in COUNTERS}
        result["delivery"].update({key: summary.get(key, 0) for key in ("opted_out", "retired_targets")})
        trace = summary.get("source_trace")
        # Trace is optional for legacy jobs; never copy arbitrary payloads to output.
        if "source_trace" in summary:
            if not isinstance(trace, Mapping):
                raise ValueError("invalid explicit source trace")
            from app.services.summary_telemetry import sanitize_source_trace
            result["source_trace"] = sanitize_source_trace(trace)
        if state == "completed" and runtime != "succeeded":
            return finish("failed", "runtime_application_conflict")
        if state == "completed" and completed_at > deadline:
            return finish("completed_late", reason)
        return finish(state, reason)
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        return finish("check_unavailable", "evidence_invalid")
