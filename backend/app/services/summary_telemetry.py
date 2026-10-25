"""Bounded, non-personal execution/source diagnostics for summary jobs."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import os
import re
from zoneinfo import ZoneInfo

MAX_RUNS = 64
RUN = re.compile(r"[0-9]{8}T[0-9]{6}Z")


def _run_id(value):
    if not isinstance(value, str) or not RUN.fullmatch(value):
        return None
    try:
        datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return None
    return value


def _time(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("aware time required")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class SourceTrace:
    def __init__(self):
        self.runs = {}
        self.fetched = self.failed = self.unknown = self.omitted = 0

    def fetch_failed(self):
        self.failed += 1

    def observe(self, snapshot, *, read_at):
        self.fetched += 1
        run = _run_id(snapshot.get("source_run_id")) if isinstance(snapshot, Mapping) else None
        if run is None:
            self.unknown += 1
            return
        if run not in self.runs and len(self.runs) >= MAX_RUNS:
            self.omitted += 1
            return
        at = _time(read_at)
        row = self.runs.setdefault(run, {"source_run_id": run, "groups": 0, "first_read_at": at, "last_read_at": at})
        row["groups"] += 1
        row["last_read_at"] = at

    def summary(self):
        return {"fetched_groups": self.fetched, "fetch_failed_groups": self.failed,
                "unknown_run_groups": self.unknown, "omitted_run_groups": self.omitted,
                "runs": [dict(self.runs[key]) for key in sorted(self.runs)]}


def sanitize_source_trace(trace):
    counts = {k: trace.get(k) for k in ("fetched_groups", "fetch_failed_groups", "unknown_run_groups", "omitted_run_groups")}
    if any(type(v) is not int or v < 0 for v in counts.values()):
        raise ValueError("invalid source trace counts")
    source = trace.get("runs")
    if not isinstance(source, list) or len(source) > MAX_RUNS:
        raise ValueError("invalid source trace runs")
    rows, seen = [], set()
    for row in source:
        run = _run_id(row.get("source_run_id"))
        groups = row.get("groups")
        first, last = _time(row.get("first_read_at")), _time(row.get("last_read_at"))
        if not run or run in seen or type(groups) is not int or groups < 1 or first > last:
            raise ValueError("invalid source trace row")
        seen.add(run)
        rows.append({"source_run_id": run, "groups": groups, "first_read_at": first, "last_read_at": last})
    if sum(row["groups"] for row in rows) + counts["unknown_run_groups"] + counts["omitted_run_groups"] != counts["fetched_groups"]:
        raise ValueError("inconsistent source trace counts")
    return {**counts, "runs": rows}


def execution_context(kind, started_at, completed_at, *, environment=None):
    if kind not in {"morning", "evening"}:
        raise ValueError("unknown summary kind")
    env = os.environ if environment is None else environment
    job = f"meteofriul-{kind}-forecast"
    execution = env.get("CLOUD_RUN_EXECUTION", "")
    if not re.fullmatch(re.escape(job) + r"-[a-z0-9]{1,32}", execution):
        execution = None
    started = _time(started_at)
    return {"schema_version": 1, "kind": kind, "execution": execution,
            "job": job, "started_at": started, "completed_at": _time(completed_at),
            "invocation_local_date": datetime.fromisoformat(started.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Rome")).date().isoformat(),
            # Container times identify invocation date, NEVER Scheduler origin.
            "origin": "not_attested_by_worker"}
