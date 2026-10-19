"""Producer guard for operational tolerance; never an error bound or imputation."""
import math

SCHEMA = "icon-accumulation-tolerance.v1"
FIELDS = {
    "precipitation_mm": (("TOT_PREC",), 0.1, "mm"),
    "liquid_rain_mm": (("RAIN_CON", "RAIN_GSP"), 0.1, "mm"),
    "snow_water_equivalent_mm": (("SNOW_CON", "SNOW_GSP"), 0.02, "mm_swe"),
}
RESOLUTION = {"positive_within_encoding_resolution", "negative_within_encoding_resolution"}
KNOWN = {"valid", "valid_reference_floor_normalized"}
KEYS = {"state", "unit", "known_component_sum_mm", "unquantified_components",
        "resolution_budget_mm", "tolerance_mm", "reason"}


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def build_accumulation_quality(intervals, packing_errors):
    fields = {}
    for name, (components, tolerance, unit) in FIELDS.items():
        known, budget, unresolved, reasons = 0.0, 0.0, 0, set()
        for field in components:
            item = intervals.get(field, {})
            value, status = item.get("value_mm"), item.get("status")
            if status in KNOWN and number(value):
                known += value
            elif status in RESOLUTION and value is None:
                unresolved += 1
                q = item.get("uncertainty_mm")
                errors = packing_errors.get(field)
                if (not number(q) or not isinstance(errors, (list, tuple)) or
                        len(errors) != 2 or not all(number(v) for v in errors)):
                    reasons.add("resolution_metadata_missing")
                else:
                    budget += q
            else:
                reasons.add("missing_or_invalid_accumulation")
        if not number(known) or not number(budget):
            reasons.add("missing_or_invalid_accumulation")
            known, budget = 0.0, 0.0
        if budget > tolerance:
            reasons.add("resolution_budget_exceeded")
        reason = next((r for r in ("missing_or_invalid_accumulation", "resolution_metadata_missing",
                                  "resolution_budget_exceeded") if r in reasons), None)
        state = ("unavailable" if reason else "resolution_tolerance_verified" if unresolved
                 else "known_zero" if known == 0 else "quantified")
        fields[name] = dict(state=state, unit=unit, known_component_sum_mm=known,
                            unquantified_components=unresolved, resolution_budget_mm=budget,
                            tolerance_mm=tolerance, reason=reason)
    return {"schema_version": SCHEMA, "fields": fields}


def validate_accumulation_quality(value, row):
    """Both old rows (no extension) and complete versioned extensions are valid."""
    if (not isinstance(value, dict) or set(value) != {"schema_version", "fields"}
            or value["schema_version"] != SCHEMA or not isinstance(value["fields"], dict)
            or set(value["fields"]) != set(FIELDS)):
        raise ValueError("invalid accumulation quality envelope")
    for name, (components, tolerance, unit) in FIELDS.items():
        item = value["fields"][name]
        if (not isinstance(item, dict) or set(item) != KEYS or item["unit"] != unit
                or type(item["tolerance_mm"]) not in (int, float) or item["tolerance_mm"] != tolerance
                or not number(item["known_component_sum_mm"]) or not number(item["resolution_budget_mm"])
                or type(item["unquantified_components"]) is not int
                or not 0 <= item["unquantified_components"] <= len(components)):
            raise ValueError("invalid accumulation quality field")
        state, known, count = item["state"], item["known_component_sum_mm"], item["unquantified_components"]
        if state in {"known_zero", "quantified"}:
            valid = (number(row.get(name)) and row[name] == known and not count
                     and item["resolution_budget_mm"] == 0 and item["reason"] is None
                     and (state == "known_zero") == (known == 0))
        elif state == "resolution_tolerance_verified":
            valid = (row.get(name) is None and count > 0 and item["reason"] is None
                     and item["resolution_budget_mm"] <= tolerance)
        elif state == "unavailable":
            valid = (row.get(name) is None and item["reason"] in {
                "missing_or_invalid_accumulation", "resolution_metadata_missing", "resolution_budget_exceeded"})
        else:
            valid = False
        if not valid:
            raise ValueError("accumulation quality disagrees with value or policy")
    return value
