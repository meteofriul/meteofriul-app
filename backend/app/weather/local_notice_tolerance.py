"""Consumer of the producer's versioned accumulation guard, only for notices.

No shared hourly measurement is filled. A private detector projection retains
the known component sum plus explicit tolerance evidence. Old/unverified nulls
remain unavailable. Rounding tolerance is not a certified uncertainty bound.
"""
import math
from app.weather.local_notice_thresholds import (
    RAIN_ACCUMULATION_THRESHOLD_MM, RAIN_MINIMUM_HOURLY_AMOUNT_MM,
    RAIN_WINDOW_HOURS, RAIN_PROBABILITY_THRESHOLD_PERCENT, STORM_WEATHER_CODES,
    SNOW_ACCUMULATION_THRESHOLD_CM, SNOW_WINDOW_HOURS, SNOW_PROBABILITY_THRESHOLD_PERCENT,
)

SCHEMA = "icon-accumulation-tolerance.v1"
SPECS = {
    "precipitation_mm": ("precipitation", 0.1, "mm", 1),
    "liquid_rain_mm": ("rain", 0.1, "mm", 2),
    "snow_water_equivalent_mm": ("snowfall", 0.02, "mm_swe", 2),
}
REASONS = {"missing_or_invalid_accumulation", "resolution_metadata_missing", "resolution_budget_exceeded"}
SNOW_WATER_RATIO = 10.0  # mm SWE * 10 / 10 mm per cm; explicitly fixed policy.


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def read_quality(value, measurements):
    """Validate the public extension independently of the producer implementation."""
    if not isinstance(value, dict) or set(value) != {"schema_version", "fields"} or value["schema_version"] != SCHEMA:
        return None
    fields = value["fields"]
    if not isinstance(fields, dict) or set(fields) != set(SPECS):
        return None
    for variable, (_, tolerance, unit, components) in SPECS.items():
        if variable not in measurements:
            return None
        q = fields[variable]
        if (not isinstance(q, dict) or set(q) != {"state", "unit", "known_component_sum_mm", "unquantified_components",
                                                 "resolution_budget_mm", "tolerance_mm", "reason"}
                or q["unit"] != unit or type(q["tolerance_mm"]) not in (int, float) or q["tolerance_mm"] != tolerance
                or not number(q["known_component_sum_mm"]) or not number(q["resolution_budget_mm"])
                or type(q["unquantified_components"]) is not int or not 0 <= q["unquantified_components"] <= components):
            return None
        state, known, count = q["state"], q["known_component_sum_mm"], q["unquantified_components"]
        if not isinstance(state, str):
            return None
        raw = measurements.get(variable)
        if state in {"known_zero", "quantified"}:
            valid = (number(raw) and raw == known and not count and q["resolution_budget_mm"] == 0
                     and q["reason"] is None and (state == "known_zero") == (known == 0))
        elif state == "resolution_tolerance_verified":
            valid = raw is None and count > 0 and q["reason"] is None and q["resolution_budget_mm"] <= tolerance
        elif state == "unavailable":
            valid = raw is None and isinstance(q["reason"], str) and q["reason"] in REASONS
        else:
            valid = False
        if not valid:
            return None
    return fields


def combined_weather_code(*, rain_mm, snow_cm, native_code):
    native_code = int(native_code) if number(native_code) and native_code <= 99 and float(native_code).is_integer() else None
    if native_code in {56, 57, 66, 67, 73, 75, 86, 95, 96, 99}:
        return int(native_code)
    if rain_mm is None or snow_cm is None:
        return None
    if snow_cm >= 1.0:
        return 73
    if snow_cm > 0.1:
        return 71
    if rain_mm >= 7.5:
        return 65
    if rain_mm >= 2.5:
        return 63
    if rain_mm > 0.1:
        return 61
    return int(native_code) if native_code in {0, 1, 2, 3} else 3


def prepare_notice_slots(slots):
    result = []
    for original in slots:
        slot = dict(original)
        slot["tolerance_verified"] = {}
        slot["tolerance_rejected"] = {}
        extension = slot.get("accumulation_quality")
        measurements = {v: slot.get(spec[0]) for v, spec in SPECS.items()}
        # SWE is converted to cm with the declared fixed ratio (currently 1:1 numerically).
        if number(measurements["snow_water_equivalent_mm"]):
            measurements["snow_water_equivalent_mm"] *= 10 / SNOW_WATER_RATIO
        fields = read_quality(extension, measurements) if extension is not None else None
        for variable, (field, _, _, _) in SPECS.items():
            if slot.get(field) is not None:
                continue
            q = fields.get(variable) if fields is not None else None
            if q is not None and q["state"] == "resolution_tolerance_verified":
                known = q["known_component_sum_mm"]
                slot[field] = known * SNOW_WATER_RATIO / 10 if field == "snowfall" else known
                slot["tolerance_verified"][field] = variable
                if field == "rain":
                    slot["showers"] = 0.0  # Rain already includes both preserved components.
            elif extension is not None:
                slot["tolerance_rejected"][field] = q["reason"] if q and q["reason"] else "invalid_tolerance_contract"
        if any(f in slot["tolerance_verified"] for f in ("rain", "snowfall")):
            if number(slot.get("rain")) and number(slot.get("snowfall")):
                slot["weather_code"] = combined_weather_code(rain_mm=slot["rain"], snow_cm=slot["snowfall"],
                                                            native_code=slot.get("native_weather_code"))
        # Never fill the deterministic indicator: a tolerated total is still not quantified.
        result.append(slot)
    return result


def indicator_exemptions(kind, slots):
    """Only verified-total unknowns may be ignored, when they cannot change a trigger.

    Generic missing indicators are never exempt. Unknown peak indicators remain
    blocking if a potential candidate cannot be decided from another known peak.
    """
    allowed = {s["event_at"] for s in slots if "precipitation" in s.get("tolerance_verified", {})
               and s.get("precipitation_probability") is None}
    if kind == "storm":
        return {s["event_at"] for s in slots if s["event_at"] in allowed and
                (s.get("native_weather_code") not in tuple(STORM_WEATHER_CODES) or s.get("rain") == s.get("showers") == 0)}
    if kind not in {"rain", "snow"}:
        return set()
    hours = RAIN_WINDOW_HOURS if kind == "rain" else SNOW_WINDOW_HOURS
    probability_threshold = RAIN_PROBABILITY_THRESHOLD_PERCENT if kind == "rain" else SNOW_PROBABILITY_THRESHOLD_PERCENT
    for i in range(len(slots) - hours + 1):
        window = slots[i:i+hours]
        if kind == "rain":
            if not all(number(s.get("rain")) and number(s.get("showers")) for s in window):
                return set()
            amounts = [s["rain"] + s["showers"] for s in window]
            relevant = [s for s, amount in zip(window, amounts) if amount >= RAIN_MINIMUM_HOURLY_AMOUNT_MM]
            possible = sum(amounts) >= RAIN_ACCUMULATION_THRESHOLD_MM and bool(relevant)
        else:
            if not all(number(s.get("snowfall")) for s in window):
                return set()
            amounts = [s["snowfall"] for s in window]
            relevant = [s for s, amount in zip(window, amounts) if amount > 0]
            possible = sum(amounts) >= SNOW_ACCUMULATION_THRESHOLD_CM
        known_positive = any(number(s.get("precipitation_probability")) and
                             probability_threshold <= s["precipitation_probability"] <= 100 for s in relevant)
        if possible and not known_positive:
            allowed.difference_update(s["event_at"] for s in relevant)
    return allowed
