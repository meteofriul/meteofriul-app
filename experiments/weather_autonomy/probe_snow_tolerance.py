"""Offline prototype of the proposed operational tolerance, NOT a runtime adapter.

Input: already decoded and validated ICON component increments. No network,
job, publication or notification calls. Q budgets are policy guards, NOT
certified uncertainty bounds. Published non-quantifiable values stay null.
"""
from __future__ import annotations

import math

RESOLUTION_STATES = {
    "positive_within_encoding_resolution", "negative_within_encoding_resolution"
}
KNOWN_STATES = {"valid", "valid_reference_floor_normalized"}
SNOW_TOLERANCE_MM_SWE = 0.02


def finite_nonnegative(value):
    return (type(value) in (int, float) and math.isfinite(value) and value >= 0)


def aggregate_components(components, *, tolerance_mm, expected_components):
    """Budget only unresolved components, across the FINAL hourly field.

    Each component has the result of pilot_policy.rain_interval and verified
    packingError metadata for both messages. Metadata presence is required;
    packingError is retained diagnostically, not called forecast uncertainty.
    """
    if not finite_nonnegative(tolerance_mm):
        raise ValueError("invalid tolerance")
    reasons, known, budget, unresolved = [], 0.0, 0.0, 0
    if len(components) != expected_components:
        reasons.append("missing_component")
    for component in components:
        status, value = component.get("status"), component.get("value_mm")
        if status in KNOWN_STATES and finite_nonnegative(value):
            known += value
        elif status in RESOLUTION_STATES and value is None:
            unresolved += 1
            qsum = component.get("uncertainty_mm")
            errors = component.get("packing_errors_mm")
            if (not finite_nonnegative(qsum) or not isinstance(errors, (list, tuple))
                    or len(errors) != 2 or not all(finite_nonnegative(x) for x in errors)):
                reasons.append("resolution_metadata_missing_or_invalid")
            else:
                budget += qsum
        else:
            reasons.append("missing_or_invalid_value")
    if not math.isfinite(known) or not math.isfinite(budget):
        reasons.append("nonfinite_aggregate")
    if budget > tolerance_mm:
        reasons.append("final_field_resolution_budget_exceeds_tolerance")
    state = ("unavailable" if reasons else
             "resolution_tolerance_verified" if unresolved else
             "known_zero" if known == 0 else "quantified")
    return {
        "state": state,
        "value_mm": known if state in {"known_zero", "quantified"} else None,
        "known_component_sum_mm": known,
        "unquantified_components": unresolved,
        "resolution_budget_mm": budget,
        "tolerance_mm": tolerance_mm,
        "usable_under_operational_tolerance": not reasons,
        "reasons": sorted(set(reasons)),
    }


def snow_window(rows):
    """A three-hour experimental decision; input rows must be consecutive.

    Known SWE numerically maps to cm with the existing fixed 10:1 assumption.
    The combined-code override at >=1 is accounted for. Unknown indicators
    stay unknown. This is not the production B.4 gate or a send simulation.
    """
    if len(rows) != 3 or any(rows[i + 1]["lead"] != rows[i]["lead"] + 1 for i in (0, 1)):
        raise ValueError("expected three consecutive hourly leads")
    if any(not row["snow"]["usable_under_operational_tolerance"] for row in rows):
        return "not_evaluable"
    if any(type(row.get("native_weather_code")) is not int or
           not 0 <= row["native_weather_code"] <= 99 for row in rows):
        return "not_evaluable"
    amounts = [row["snow"]["known_component_sum_mm"] for row in rows]
    if any(row["native_weather_code"] in {73, 75, 86} or amount >= 1
           for row, amount in zip(rows, amounts)):
        return "evaluated_with_candidate"
    if sum(amounts) < 2:
        return "evaluated_without_candidate"
    probabilities = [row.get("precipitation_probability") for row, amount in zip(rows, amounts) if amount > 0]
    if any(finite_nonnegative(p) and 70 <= p <= 100 for p in probabilities):
        return "evaluated_with_candidate"
    if any(not finite_nonnegative(p) or p > 100 for p in probabilities):
        return "not_evaluable"
    return "evaluated_without_candidate"


def replay(fixture):
    """Reproduce only the two frozen Ciampac windows, without source access."""
    from pilot_policy import rain_interval
    from run_pilot import accumulation_quantum, accumulation_reference_mm, validate_contract

    indexed = {}
    for field, samples in fixture["fields"].items():
        indexed[field] = {}
        for sample in samples:
            lead, meta = sample["lead"], sample["metadata"]
            validate_contract(meta, field, fixture["run"], lead)
            if lead in indexed[field]:
                raise ValueError("duplicate lead")
            indexed[field][lead] = sample

    def increment(field, lead):
        previous, current = indexed[field][lead - 1], indexed[field][lead]
        p, c = previous["metadata"], current["metadata"]
        result = rain_interval(previous["point"]["value"], current["point"]["value"],
                               accumulation_quantum(p), accumulation_quantum(c),
                               previous_reference_mm=accumulation_reference_mm(p),
                               current_reference_mm=accumulation_reference_mm(c))
        result["packing_errors_mm"] = [p.get("packingError"), c.get("packingError")]
        return result

    windows = []
    for leads in ([1, 2, 3], [12, 13, 14]):
        rows = []
        for lead in leads:
            components = [increment(f, lead) for f in ("SNOW_CON", "SNOW_GSP")]
            snow = aggregate_components(components, tolerance_mm=0.02, expected_components=2)
            precipitation = increment("TOT_PREC", lead)
            total_guard = aggregate_components([precipitation], tolerance_mm=0.1, expected_components=1)
            pvalue = precipitation["value_mm"]
            probability = None if pvalue is None else 100 if pvalue > 0 else 0
            native = indexed["WW"][lead]["point"]["value"]
            if not finite_nonnegative(native) or native != int(native) or native > 99:
                raise ValueError("invalid native code")
            rows.append({"lead": lead, "snow_components": components, "snow": snow,
                         "total_precipitation_component": precipitation,
                         "total_precipitation_guard": total_guard,
                         "precipitation_probability": probability, "native_weather_code": int(native)})
        old_available = all(all(c["value_mm"] is not None for c in row["snow_components"])
                            and row["total_precipitation_component"]["value_mm"] is not None
                            for row in rows)
        windows.append({"leads": leads, "strict_contract_available": old_available,
                        "proposed_experimental_decision": snow_window(rows),
                        "contains_tolerated_resolution": any(row["snow"]["unquantified_components"] for row in rows),
                        "rows": rows})
    return {"kind": "isolated_operational_tolerance_probe_not_production",
            "run": fixture["run"], "point": fixture["point"],
            "snow_water_ratio": "fixed 10:1; 1 mm SWE numerically equals 1 cm snow",
            "guarantee": "operational tolerance only; not a certified error interval",
            "notification_calls": 0, "windows": windows}


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument('fixture', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = replay(json.loads(args.fixture.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    for window in result['windows']:
        print(window['leads'], 'strict_available=', window['strict_contract_available'],
              'trial=', window['proposed_experimental_decision'])
