"""Per-phenomenon availability and bounded evidence for actual notice evaluations."""
from collections import Counter
from collections.abc import Mapping
from datetime import timezone
import math
import re

SCHEMA = "local-notice-quality.v2"
KINDS = ("storm", "ice", "snow", "wind", "rain", "heat")
NUMERIC_RANGES = {
    "temperature_2m": (-100.0, 70.0), "apparent_temperature": (-100.0, 80.0),
    "precipitation_probability": (0.0, 100.0), "precipitation": (0.0, 500.0),
    "rain": (0.0, 500.0), "showers": (0.0, 500.0), "snowfall": (0.0, 100.0),
    "wind_gusts_10m": (0.0, 500.0), "weather_code": (0.0, 99.0),
    "native_weather_code": (0.0, 99.0),
}
# Include the measured total behind the deterministic precipitation indicator.
# Storm corroboration is conditional: amounts cannot disprove a native storm code.
DEPENDENCIES = {
    "wind": ("wind_gusts_10m",),
    "heat": ("temperature_2m", "apparent_temperature"),
    "rain": ("rain", "showers", "precipitation", "precipitation_probability"),
    "snow": ("snowfall", "weather_code", "precipitation", "precipitation_probability"),
    "storm": ("native_weather_code",), "ice": ("native_weather_code",),
}
STORM_SUPPORT = ("rain", "showers", "precipitation", "precipitation_probability")
RESOLUTION_REASONS = frozenset({"positive_within_encoding_resolution", "negative_within_encoding_resolution"})
EVIDENCE_STATES = ('disabled', 'verified', 'unavailable', 'invalid')
STATES = frozenset({"evaluated_no_candidate", "evaluated_with_candidate", "not_evaluable"})
VARIABLES = frozenset(NUMERIC_RANGES) | {
    "temperature_c", "apparent_temperature_c", "wind_gust_max_m_s", "precipitation_mm",
    "liquid_rain_mm", "snow_water_equivalent_mm", "time", "source", "contract",
}
REASONS = frozenset({
    "missing", "invalid_type", "nonfinite", "negative", "out_of_range",
    "positive_within_encoding_resolution", "negative_within_encoding_resolution",
    "no_previous_interval", "invalid", "invalid_T_Td_for_RH_no_clipping",
    "gust_previous_hour_unavailable", "derived_input_unavailable",
    "source_unavailable", "source_error", "detector_error", "detector_contract_invalid",
    "invalid_snapshot_contract", "invalid_hourly_time", "hourly_times_not_increasing",
    "insufficient_future_slots", "first_future_slot_too_far", "future_slots_not_hourly",
    "resolution_metadata_missing", "resolution_budget_exceeded", "missing_or_invalid_accumulation",
    "invalid_tolerance_contract", "operational_tolerance_verified",
})
RUN = re.compile(r"\d{8}T\d{6}Z\Z")
UTC_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
MAX_REASONS = 128  # At most seven evaluated hourly slots, not the entire 73h run.


def run_identity(value):
    return value if isinstance(value, str) and RUN.fullmatch(value) else "unresolved"


def utc_stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def missing_reason(value):
    if value is None:
        return "missing"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "invalid_type"
    try:
        return "nonfinite" if not math.isfinite(float(value)) else "negative" if value < 0 else "out_of_range"
    except OverflowError:
        return "nonfinite"


def _clean_reasons(raw_reasons):
    reasons = []
    raw_reasons = raw_reasons if isinstance(raw_reasons, list) else []
    for item in raw_reasons[:MAX_REASONS]:
        if not isinstance(item, Mapping):
            continue
        variable, reason, at = item.get("variable"), item.get("reason"), item.get("at")
        if isinstance(variable, str) and isinstance(reason, str) and variable in VARIABLES and reason in REASONS:
            reasons.append({"at": at if isinstance(at, str) and UTC_TIME.fullmatch(at) else "",
                            "variable": variable, "reason": reason})
    return reasons


def sanitize_quality(value):
    """Whitelist persisted evidence; recompute counts from the six explicit states."""
    if not isinstance(value, Mapping) or value.get("schema_version") != SCHEMA:
        return None
    raw = value.get("phenomena")
    raw = raw if isinstance(raw, Mapping) else {}
    phenomena = {}
    for kind in KINDS:
        item = raw.get(kind)
        item = item if isinstance(item, Mapping) else {}
        state = item.get("state")
        state = state if isinstance(state, str) and state in STATES else "not_evaluable"
        reasons = _clean_reasons(item.get("reasons"))
        tolerance = [r for r in _clean_reasons(item.get("tolerance_used")) if r["reason"] == "operational_tolerance_verified"]
        raw_reasons = item.get("reasons")
        truncated = item.get("reasons_truncated") is True or (isinstance(raw_reasons, list) and len(raw_reasons) > MAX_REASONS)
        phenomena[kind] = dict(state=state, reasons=reasons, reasons_truncated=truncated,
            uses_operational_tolerance=bool(tolerance), tolerance_used=tolerance,
            cause_class=("only_resolution" if reasons and not truncated and all(r["reason"] in RESOLUTION_REASONS for r in reasons)
                         else "other_or_mixed") if state == "not_evaluable" else None)
    blocked = sum(p["state"] == "not_evaluable" for p in phenomena.values())
    raw_reasons = value.get("reasons")
    return {
        "schema_version": SCHEMA, "source_run_id": run_identity(value.get("source_run_id")),
        "accumulation_evidence_status": (value.get('accumulation_evidence_status')
            if value.get('accumulation_evidence_status') in EVIDENCE_STATES else 'disabled'),
        "state": "not_evaluable" if blocked == len(KINDS) else "partial" if blocked else "evaluable",
        "gate": "per_phenomenon", "evaluations_expected": 1,
        "evaluations_not_possible": int(blocked == len(KINDS)),
        "evaluations_partial": int(0 < blocked < len(KINDS)), "evaluations_degraded": int(blocked > 0),
        "evaluations_with_tolerance": int(any(p["uses_operational_tolerance"] for p in phenomena.values())),
        "phenomena_expected": len(KINDS), "phenomena_not_possible": blocked,
        "phenomena": phenomena,
        "reasons": _clean_reasons(raw_reasons),
        "reasons_truncated": value.get("reasons_truncated") is True or (isinstance(raw_reasons, list) and len(raw_reasons) > MAX_REASONS),
    }


def valid_value(field, raw):
    lo, hi = NUMERIC_RANGES[field]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return False
    try:
        return math.isfinite(raw) and lo <= raw <= hi and (not field.endswith("weather_code") or float(raw).is_integer())
    except OverflowError:
        return False


def evaluation_quality(snapshot, slots, errors, *, failure=None):
    """The shared production/replay availability gate, before candidate detection."""
    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    from app.weather.local_notice_tolerance import prepare_notice_slots, indicator_exemptions, SPECS
    slots = prepare_notice_slots(slots)
    source_issues = snapshot.get("source_quality_issues", [])
    source_issues = source_issues if isinstance(source_issues, list) else []
    issues = {}
    for item in source_issues:
        if (isinstance(item, Mapping) and isinstance(item.get("at"), str)
                and isinstance(item.get("field"), str) and isinstance(item.get("variable"), str)
                and isinstance(item.get("reason"), str) and item["variable"] in VARIABLES and item["reason"] in REASONS):
            issues.setdefault((item["at"], item["field"]), set()).add((item["at"], item["variable"], item["reason"]))
    invalid = {}
    for slot in slots:
        at = utc_stamp(slot["event_at"])
        for field in NUMERIC_RANGES:
            raw = slot.get(field)
            if valid_value(field, raw):
                continue
            rejected = slot.get("tolerance_rejected", {}).get(field)
            variable = next((v for v, spec in SPECS.items() if spec[0] == field), field)
            invalid.setdefault(field, set()).update({(at, variable, rejected)} if rejected else
                                                     issues.get((at, field), {(at, field, missing_reason(raw))}))
    global_details = set()
    for error in errors:
        if error in REASONS:
            global_details.add(("", "time", error))
        else:
            global_details.add(("", "contract", "invalid_snapshot_contract"))
    if failure:
        global_details.add(("", "source", failure if failure in REASONS else "source_unavailable"))
    phenomena, details = {}, set()
    for kind in KINDS:
        fields = DEPENDENCIES[kind]
        if kind == "storm" and any(s.get("native_weather_code") in (95, 96, 99) for s in slots):
            fields += STORM_SUPPORT
        exemptions = {utc_stamp(t) for t in indicator_exemptions(kind, slots)}
        reasons = set(global_details)
        for field in fields:
            reasons.update(r for r in invalid.get(field, set()) if field != "precipitation_probability" or r[0] not in exemptions)
        relevant = set(fields)
        if kind == "snow":
            relevant.add("rain")  # Combined code also reads liquid rain.
        tolerated = [dict(at=utc_stamp(s["event_at"]), variable=v, reason="operational_tolerance_verified")
                     for s in slots for f, v in s.get("tolerance_verified", {}).items() if f in relevant]
        details.update(reasons)
        phenomena[kind] = dict(state="not_evaluable" if reasons else "evaluated_no_candidate",
            tolerance_used=tolerated,
            reasons=[dict(at=t, variable=v, reason=r) for t, v, r in sorted(reasons)[:MAX_REASONS]],
            reasons_truncated=len(reasons) > MAX_REASONS)
    return sanitize_quality({
        "schema_version": SCHEMA, "source_run_id": snapshot.get("source_run_id"),
        "accumulation_evidence_status": snapshot.get('accumulation_evidence_status'),
        "phenomena": phenomena,
        "reasons": [dict(at=t, variable=v, reason=r) for t, v, r in sorted(details)[:MAX_REASONS]],
        "reasons_truncated": len(details) > MAX_REASONS,
    })


class QualityCounter:
    """One record per canonical point per job; devices never multiply the denominator."""
    def __init__(self):
        self._records = {}

    def add(self, group_key, quality):
        clean = sanitize_quality(quality)
        if clean is None:
            clean = evaluation_quality({}, [], [], failure="detector_contract_invalid")
        self._records[group_key] = clean

    def summary(self):
        runs = []
        for run in sorted({q["source_run_id"] for q in self._records.values()}):
            items = [(key, q) for key, q in self._records.items() if q["source_run_id"] == run]
            blocked = [(key, q) for key, q in items if q["state"] == "not_evaluable"]
            degraded = [(key, q) for key, q in items if q["state"] != "evaluable"]
            causes = Counter()
            for _, q in degraded:
                causes.update({(r["variable"], r["reason"]) for r in q["reasons"]})
            runs.append({
                "source_run_id": run, "evaluations_expected": len(items),
                "accumulation_evidence": {state: sum(q['accumulation_evidence_status'] == state for _, q in items)
                                          for state in EVIDENCE_STATES},
                "evaluations_not_possible": len(blocked),
                "evaluations_partial": len(degraded) - len(blocked),
                "evaluations_degraded": len(degraded),
                "evaluations_with_tolerance": sum(q["evaluations_with_tolerance"] for _, q in items),
                "municipalities_expected": len({key[0] for key, _ in items}),
                "municipalities_not_evaluable": len({key[0] for key, _ in blocked}),
                "municipalities_degraded": len({key[0] for key, _ in degraded}),
                "phenomena": {kind: dict(expected=len(items),
                    with_operational_tolerance=sum(q["phenomena"][kind]["uses_operational_tolerance"] for _, q in items),
                    **{state: sum(q["phenomena"][kind]["state"] == state for _, q in items) for state in STATES},
                    **{cause: sum(q["phenomena"][kind]["cause_class"] == cause for _, q in items)
                       for cause in ("only_resolution", "other_or_mixed")}) for kind in KINDS},
                "causes": [dict(variable=v, reason=r, evaluations=count) for (v, r), count in sorted(causes.items())],
            })
        return {
            "schema_version": SCHEMA, "scope": "canonical_point_per_job_execution",
            "gate": "per_phenomenon", "evaluations_expected": len(self._records),
            "evaluations_not_possible": sum(q["state"] == "not_evaluable" for q in self._records.values()),
            "evaluations_partial": sum(q["state"] == "partial" for q in self._records.values()),
            "evaluations_degraded": sum(q["state"] != "evaluable" for q in self._records.values()),
            "evaluations_with_tolerance": sum(q["evaluations_with_tolerance"] for q in self._records.values()),
            "by_source_run": runs,
        }
