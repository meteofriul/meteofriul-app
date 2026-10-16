"""Pure UTC evaluation and state transitions; no cloud dependencies."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
import re

PRODUCTS = ("fvg", "national")
METRICS = ("check_state", "critical_active", "check_completed")
METRIC_PREFIX = "custom.googleapis.com/meteofriul/icon2i/"
STEP = timedelta(minutes=30)


def instant(value):
    if isinstance(value, str):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z", value):
            raise ValueError("UTC RFC3339 timestamp required")
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("aware timestamp required")
    return value.astimezone(timezone.utc)


def stamp(value):
    return instant(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def slot(value):
    value = instant(value)
    if value.minute not in (10, 40) or value.second or value.microsecond:
        raise ValueError("planned slot must be :10 or :40 UTC")
    return value


def future_samples(run_at, last_at, now):
    run, last, now = map(instant, (run_at, last_at, now))
    if last < run or (last - run).total_seconds() % 3600:
        raise ValueError("non-hourly coverage")
    first = max(0, math.ceil((now - run).total_seconds() / 3600))
    return max(0, int((last - run).total_seconds() / 3600) - first + 1)


def empty_comparison(product):
    return {"ordinary": {"result": "not_attempted"},
            "diagnostic": {"result": "not_attempted"},
            "resolve": {"ordinary": {"result": "not_attempted"},
                        "diagnostic": {"result": "not_attempted"},
                        "target_istat": "058091" if product == "national" else None}}


def evaluate(product, planned_slot, observed_at, observation, previous=None):
    """Pure transition. Duplicate/superseded slots return None; recover their outbox."""
    if product not in PRODUCTS:
        raise ValueError("unknown product")
    planned, now = slot(planned_slot), instant(observed_at)
    if now < planned:
        raise ValueError("observation precedes planned slot")
    old = previous or {}
    if old and planned <= slot(old["scheduled_slot_utc"]):
        return None
    if old and now <= instant(old["observed_at"]):
        raise ValueError("observation clock regressed")
    obs = deepcopy(observation)
    critical = set(obs.get("critical_causes", []))
    attention = set(obs.get("attention_causes", []))
    indeterminate = bool(obs.get("indeterminate"))
    complete = bool(obs.get("complete")) and not indeterminate
    run = obs.get("run")
    age = None
    if run:
        age = (now - instant(run["run_at"])).total_seconds() / 3600
        if age < 0:
            critical.add("run_in_future")
        elif age >= 20:
            critical.add("run_age_critical")
        elif age >= 19:
            attention.add("run_age_attention")
    samples = None
    if run and obs.get("last_at"):
        samples = future_samples(run["run_at"], obs["last_at"], now)
        if samples < 12:
            critical.add("coverage_critical")
        elif samples < 24:
            attention.add("coverage_attention")

    last_verified = deepcopy(old.get("last_verified"))
    publication = deepcopy(old.get("publication"))
    if complete and run:
        if last_verified and run["source_run_id"] < last_verified["source_run_id"]:
            critical.add("run_regression")
            complete = False
        else:
            if last_verified and run["source_run_id"] > last_verified["source_run_id"]:
                publication = {"source_run_id": run["source_run_id"],
                               "at": run["time_created"], "generation": run["generation"],
                               "basis": "observed_run_change"}
            # Unknown at bootstrap. Same-run rewrites never advance publication.
            last_verified = {**run, "verified_at": stamp(now), "last_at": obs.get("last_at")}
    publication_age = None
    if publication:
        publication_age = (now - instant(publication["at"])).total_seconds() / 3600
        if publication_age > 14:
            critical.add("publication_age_critical")
        elif publication_age > 13:
            attention.add("publication_age_attention")

    history = {item["slot"]: item["indeterminate"] for item in old.get("history", [])}
    history[stamp(planned)] = indeterminate
    six = [{"slot": stamp(planned - STEP * i),
            "indeterminate": history.get(stamp(planned - STEP * i))}
           for i in range(5, -1, -1)]
    count = sum(item["indeterminate"] is True for item in six)
    if indeterminate:
        attention.add("comparison_indeterminate")
        if six[-2]["indeterminate"] is True:
            critical.add("comparison_indeterminate_consecutive")
    if count >= 3:
        attention.add("indeterminate_recurrent")
    if not complete and old.get("critical_active"):
        critical.update(old.get("critical_causes", ["unresolved_previous_critical"]))
    if not complete and not critical and not indeterminate:
        critical.add("incomplete_check")
    active = int(bool(critical))
    check_state = 3 if indeterminate else 2 if active else 1 if attention else 0
    values = {"check_state": check_state, "critical_active": active, "check_completed": 1}
    return {"schema_version": 1, "product": product,
            "scheduled_slot_utc": stamp(planned), "observed_at": stamp(now),
            **values, "complete": complete, "causes": sorted(critical | attention),
            "critical_causes": sorted(critical), "history": six,
            "indeterminate_count_last6": count, "last_verified": last_verified,
            "publication": publication, "publication_time_verified": publication is not None,
            "run_age_hours": age, "publication_age_hours": publication_age,
            "future_samples": samples, "observation": obs,
            "last_pointer_readable_at": obs.get("pointer_readable_at", old.get("last_pointer_readable_at")),
            "outbox": {name: {"value": value, "status": "ready"} for name, value in values.items()}}


def log_record(state):
    return {"event": "icon2i_freshness_check", **{key: deepcopy(value)
            for key, value in state.items() if key not in ("outbox", "history", "observation")},
            "http_comparison": deepcopy(state["observation"].get(
                "http_comparison", empty_comparison(state["product"]))),
            "observation": deepcopy(state["observation"]),
            "telemetry": {name: point["status"] for name, point in state["outbox"].items()}}
