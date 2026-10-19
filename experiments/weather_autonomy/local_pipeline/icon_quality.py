"""Quality counts and bounded raw evidence from the acquisition already in memory.

No fetching, clipping, scheduling or public-contract changes. Absolute counts
are identified by source run: repeated worker logs must not be summed as new runs.
"""
from collections import Counter
from datetime import datetime
import hashlib
import math
import re

from .contract_v1 import canonical_json_bytes

SCHEMA = "icon2i-source-quality.v1"
MAX_ANOMALY_SAMPLES = 512
MAX_CONTROLS_PER_LEAD = 2
MAX_DIAGNOSTIC_BYTES = 2 * 1024**2
PACKING_KEYS = ("packingType", "referenceValue", "bitsPerValue", "binaryScaleFactor",
                "decimalScaleFactor", "packingError", "encoding_quantum_mm")
FIELDS = ("T_2M", "TD_2M", "TOT_PREC", "RAIN_CON", "RAIN_GSP", "SNOW_CON", "SNOW_GSP", "GRAU_GSP")
ACCUMULATIONS = {
    "precipitation_previous_hour_mm": ("TOT_PREC",),
    "rain_previous_hour_mm": ("RAIN_CON", "RAIN_GSP"),
    "snow_water_equivalent_previous_hour_mm": ("SNOW_CON", "SNOW_GSP"),
}
RESOLUTION = {"positive_within_encoding_resolution", "negative_within_encoding_resolution"}
RH_FLAG = "invalid_T_Td_for_RH_no_clipping"


def _thermal_evidence(t_k, td_k):
    t, td = t_k - 273.15, td_k - 273.15
    reasons = []
    rh = None
    if not all(math.isfinite(x) and -100 <= x <= 70 for x in (t, td)):
        reasons.append("temperature_or_dewpoint_outside_domain")
    else:
        # Same unrounded Magnus expression used by the producer; diagnostic only.
        rh = 100 * math.exp(17.27 * td / (237.7 + td) - 17.27 * t / (237.7 + t))
        if td > t:
            reasons.append("dewpoint_above_temperature")
        if not 0 <= rh <= 100:
            reasons.append("relative_humidity_outside_range")
    return dict(temperature_kelvin=t_k, dewpoint_kelvin=td_k,
                dewpoint_minus_temperature_k=td_k-t_k, rh_unclipped_pct=rh, reasons=reasons)


def build_source_quality(snapshot, payload, *, source_sha256):
    """Called after snapshot validation and derivation; count all rows, bound samples."""
    run_id = datetime.fromisoformat(snapshot["run_utc"].replace("Z", "+00:00")).strftime("%Y%m%dT%H%M%SZ")
    flags = Counter(); nulls = Counter(); resolution_nulls = Counter()
    anomalies = []; controls = []; controls_per_lead = Counter(); seen = set(); bad_grids = set()
    reason_counts = Counter(); raw = snapshot["raw"]
    rows = rh_bad = 0
    tolerance_states = Counter()
    tolerance_reasons = Counter()
    for index, town in enumerate(payload["municipalities"]):
        grid = snapshot["grid_points"][index]["index"]
        for lead, row in enumerate(town["hourly"]):
            rows += 1
            row_flags = row["quality_flags"]
            for variable, quality in row.get("accumulation_quality", {}).get("fields", {}).items():
                tolerance_states[(variable, quality["state"])] += 1
                if quality["reason"]:
                    tolerance_reasons[(variable, quality["reason"])] += 1
            flags.update(row_flags)
            bad = RH_FLAG in row_flags
            rh_bad += bad
            for variable, native in ACCUMULATIONS.items():
                if row.get(variable) is None:
                    nulls[variable] += 1
                    if any(f"{field}:{reason}" in row_flags for field in native for reason in RESOLUTION):
                        resolution_nulls[variable] += 1
            key = (grid, lead)
            if key in seen:
                continue
            seen.add(key)
            if bad:
                bad_grids.add(key)
            published_rh = row.get("relative_humidity_pct")
            near_saturation = isinstance(published_rh, (int, float)) and published_rh >= 97.99
            if not bad and not near_saturation:
                continue
            evidence = _thermal_evidence(raw["T_2M"]["values"][lead][index], raw["TD_2M"]["values"][lead][index])
            sample = dict(grid_index=grid, valid_at=snapshot["times_utc"][lead], lead_hours=lead, **evidence)
            if bad:
                reason_counts.update(evidence["reasons"] or ["unclassified_humidity_derivation_failure"])
                if len(anomalies) < MAX_ANOMALY_SAMPLES:
                    anomalies.append(sample)
            elif evidence["rh_unclipped_pct"] is not None and 98 <= evidence["rh_unclipped_pct"] <= 100 and controls_per_lead[lead] < MAX_CONTROLS_PER_LEAD:
                controls.append(sample); controls_per_lead[lead] += 1
    packing = {field: [{key: meta.get(key) for key in PACKING_KEYS} for meta in raw[field]["metadata"]] for field in FIELDS}
    resolution_ranges = {}
    for field in FIELDS[2:]:
        quanta = [meta["encoding_quantum_mm"] for meta in raw[field]["metadata"]]
        bounds = [left + right for left, right in zip(quanta, quanta[1:])]
        resolution_ranges[field] = dict(minimum_mm=min(bounds), maximum_mm=max(bounds),
            meaning="sum_of_adjacent_lattice_steps_not_certified_error_bound")
    result = {
        "schema_version": SCHEMA, "source_run_id": run_id, "source_snapshot_sha256": source_sha256,
        "catalog_sha256": snapshot["catalog_sha256"], "grid_hash": snapshot["grid_hash"],
        "field_sha256": {field: raw[field]["sha256"] for field in FIELDS},
        "grid_municipalities": {str(grid): [point.get("istatCode", point["slug"]) for point, location in zip(snapshot["points"], snapshot["grid_points"]) if location["index"] == grid]
                               for grid in sorted({location["index"] for location in snapshot["grid_points"]})},
        "counts": dict(municipality_hours=rows, municipalities=len(payload["municipalities"]),
                       grid_hours=len(seen), humidity_anomaly_rows=rh_bad, humidity_anomaly_grid_hours=len(bad_grids),
                       null_rows=dict(nulls), resolution_null_rows=dict(resolution_nulls), quality_flags=dict(flags),
                       humidity_reasons_by_grid_hour=dict(reason_counts),
                       accumulation_tolerance=[dict(variable=v, state=s, count=n)
                                               for (v, s), n in sorted(tolerance_states.items())],
                       accumulation_guard_rejections=[dict(variable=v, reason=r, count=n)
                                                      for (v, r), n in sorted(tolerance_reasons.items())]),
        "packing_by_field_and_lead": packing, "accumulation_resolution_ranges": resolution_ranges,
        "anomaly_samples": anomalies, "near_saturation_controls": controls,
        "sampling": {"anomaly_limit": MAX_ANOMALY_SAMPLES, "anomaly_samples_truncated": len(bad_grids)>len(anomalies),
                     "control_limit_per_lead": MAX_CONTROLS_PER_LEAD, "controls_are_a_sample": True},
    }
    validate_source_quality(result, source_run_id=run_id)
    return result


def validate_source_quality(value, *, source_run_id):
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA or value.get("source_run_id") != source_run_id:
        raise ValueError("ICON quality identity mismatch")
    if not re.fullmatch(r"[0-9a-f]{64}", str(value.get("source_snapshot_sha256", ""))):
        raise ValueError("ICON quality lacks snapshot fingerprint")
    counts = value.get("counts", {})
    if counts.get("municipality_hours") != 215*73 or counts.get("municipalities") != 215:
        raise ValueError("ICON quality denominator mismatch")
    if not isinstance(value.get("anomaly_samples"), list) or len(value["anomaly_samples"]) > MAX_ANOMALY_SAMPLES:
        raise ValueError("ICON quality sample limit")
    if not isinstance(value.get("near_saturation_controls"), list) or len(value["near_saturation_controls"]) > 73*MAX_CONTROLS_PER_LEAD:
        raise ValueError("ICON quality control limit")
    if len(canonical_json_bytes(value)) > MAX_DIAGNOSTIC_BYTES:
        raise ValueError("ICON quality diagnostic size limit")


def quality_log_summary(value):
    if value is None:
        return {"quality_available": False, "quality_reason": "legacy_checkpoint_without_quality"}
    validate_source_quality(value, source_run_id=value.get("source_run_id"))
    counts = value["counts"]
    summary = {"quality_available": True,
            "quality_sha256": hashlib.sha256(canonical_json_bytes(value)).hexdigest(),
            "raw_diagnostic_samples": len(value["anomaly_samples"]),
            "diagnostic_samples_truncated": value["sampling"]["anomaly_samples_truncated"]}
    for key in ("municipality_hours", "municipalities", "grid_hours", "humidity_anomaly_rows", "humidity_anomaly_grid_hours"):
        summary["quality_" + key] = counts.get(key)
    for variable, label in (("precipitation_previous_hour_mm", "precipitation"),
                            ("rain_previous_hour_mm", "rain"),
                            ("snow_water_equivalent_previous_hour_mm", "snow")):
        summary["quality_null_" + label] = counts.get("null_rows", {}).get(variable, 0)
        summary["quality_resolution_null_" + label] = counts.get("resolution_null_rows", {}).get(variable, 0)
    for variable, label in (("precipitation_mm", "precipitation"), ("liquid_rain_mm", "rain"),
                            ("snow_water_equivalent_mm", "snow")):
        states = [item for item in counts.get("accumulation_tolerance", []) if item["variable"] == variable]
        summary["quality_tolerance_expected_" + label] = sum(item["count"] for item in states)
        summary["quality_tolerance_verified_" + label] = sum(item["count"] for item in states if item["state"] == "resolution_tolerance_verified")
        for reason in ("resolution_metadata_missing", "resolution_budget_exceeded", "missing_or_invalid_accumulation"):
            summary["quality_guard_" + label + "_" + reason] = sum(item["count"] for item in counts.get("accumulation_guard_rejections", [])
                                                                 if item["variable"] == variable and item["reason"] == reason)
    return summary
