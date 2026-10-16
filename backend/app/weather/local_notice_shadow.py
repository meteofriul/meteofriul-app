"""Pure, shadow-only detector for local weather notice candidates.

This module deliberately has no API route, scheduler, repository, Firebase or
FCM dependency.  It accepts an already-fetched ICON 2I snapshot, validates
its provenance contract and returns diagnostic candidates that can never be
sent directly.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

from app.services.location import LocationCatalog, Municipality
from app.services.fvg_geography import FvgLocality
from app.weather.timezone_support import FVG_TIMEZONE, get_fvg_timezone


SCHEMA_VERSION = "local-weather-shadow.v1"
POLICY_VERSION = "production-2026-09-24-icon2i-v1"
SOURCE_ID = "icon2i"
FVG_ZONE = get_fvg_timezone()

MAX_SNAPSHOT_AGE = timedelta(minutes=45)
MAX_FUTURE_CLOCK_SKEW = timedelta(minutes=5)
FORECAST_EVALUATION_HORIZON = timedelta(hours=6)
NOTICE_MAX_LEAD_TIME = timedelta(hours=1)
CANONICAL_COORDINATE_TOLERANCE = 0.0001

RAIN_ACCUMULATION_THRESHOLD_MM = 15.0
RAIN_MINIMUM_HOURLY_AMOUNT_MM = 5.0
RAIN_WINDOW_HOURS = 3
RAIN_PROBABILITY_THRESHOLD_PERCENT = 70.0
STORM_WEATHER_CODES = frozenset({95, 96, 99})
MODERATE_OR_HEAVY_SNOW_CODES = frozenset({73, 75, 86})
SNOW_ACCUMULATION_THRESHOLD_CM = 2.0
SNOW_WINDOW_HOURS = 3
SNOW_PROBABILITY_THRESHOLD_PERCENT = 70.0
FREEZING_PRECIPITATION_CODES = frozenset({56, 57, 66, 67})
WIND_GUST_THRESHOLD_KMH = 70.0
HEAT_TEMPERATURE_THRESHOLD_C = 35.0
HEAT_APPARENT_THRESHOLD_C = 38.0
HEAT_WATCH_APPARENT_THRESHOLD_C = 37.0
HEAT_CONSECUTIVE_SLOTS = 2
MIN_FUTURE_SLOTS = 3

EXPECTED_HOURLY_UNITS = {
    "time": "iso8601",
    "temperature_2m": "°C",
    "apparent_temperature": "°C",
    "precipitation_probability": "%",
    "precipitation": "mm",
    "rain": "mm",
    "showers": "mm",
    "snowfall": "cm",
    "weather_code": "wmo code",
    "wind_gusts_10m": "km/h",
}

REQUIRED_HOURLY_FIELDS = tuple(EXPECTED_HOURLY_UNITS)

NOTICE_PRIORITY = {
    "storm": 90,
    "ice": 80,
    "snow": 70,
    "wind": 60,
    "rain": 50,
    "heat": 40,
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_weather_code(value: Any) -> int | None:
    numeric = _as_float(value)
    if numeric is None or not numeric.is_integer():
        return None
    return int(numeric)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="minutes")


def _parse_aware_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(_clean(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _parse_hourly_datetime(value: Any) -> datetime | None:
    raw = _clean(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=FVG_ZONE)
    return parsed.astimezone(FVG_ZONE)


def resolve_canonical_municipality(
    reference: str,
    *,
    catalog: LocationCatalog | None = None,
) -> Municipality | None:
    """Resolve only a canonical FVG municipality name, slug or ISTAT code."""

    resolved_catalog = catalog or LocationCatalog()
    clean_reference = _clean(reference)
    if not clean_reference:
        return None

    match_istat = getattr(resolved_catalog, "match_istat", None)
    if callable(match_istat):
        municipality = match_istat(clean_reference)
        if municipality is not None:
            return municipality
    return resolved_catalog.match_names(clean_reference)


def canonical_weather_request(
    reference: str,
    *,
    catalog: LocationCatalog | None = None,
    locality: FvgLocality | None = None,
) -> dict[str, Any]:
    """Build the only location metadata accepted by the shadow evaluator."""

    municipality = resolve_canonical_municipality(reference, catalog=catalog)
    if municipality is None:
        raise ValueError("unknown_fvg_municipality")
    if locality is not None and locality.municipality_istat != municipality.istat_code:
        raise ValueError("locality_municipality_mismatch")
    return {
        "city": municipality.name,
        "istat_code": municipality.istat_code,
        "locality_id": locality.id if locality is not None else "",
        "locality_name": locality.name if locality is not None else "",
        "latitude": locality.latitude if locality is not None else municipality.latitude,
        "longitude": locality.longitude if locality is not None else municipality.longitude,
    }


def _municipality_payload(municipality: Municipality | None) -> dict[str, Any] | None:
    if municipality is None:
        return None
    return {
        "city": municipality.name,
        "istat_code": municipality.istat_code,
        "province": municipality.province,
        "latitude": municipality.latitude,
        "longitude": municipality.longitude,
    }


def _requested_location_errors(
    snapshot: Mapping[str, Any],
    municipality: Municipality,
    locality: FvgLocality | None = None,
) -> list[str]:
    requested = snapshot.get("requested_location")
    if not isinstance(requested, Mapping):
        return ["missing_requested_location"]

    errors: list[str] = []
    if _clean(requested.get("istat_code")) != municipality.istat_code:
        errors.append("requested_location_istat_mismatch")
    if _clean(requested.get("city")).casefold() != municipality.name.casefold():
        errors.append("requested_location_city_mismatch")
    expected_locality_id = locality.id if locality is not None else ""
    expected_locality_name = locality.name if locality is not None else ""
    if _clean(requested.get("locality_id")) != expected_locality_id:
        errors.append("requested_location_locality_id_mismatch")
    if _clean(requested.get("locality_name")).casefold() != expected_locality_name.casefold():
        errors.append("requested_location_locality_name_mismatch")

    latitude = _as_float(requested.get("latitude"))
    longitude = _as_float(requested.get("longitude"))
    expected_latitude = locality.latitude if locality is not None else municipality.latitude
    expected_longitude = locality.longitude if locality is not None else municipality.longitude
    if latitude is None or longitude is None:
        errors.append("requested_location_coordinates_missing")
    elif (
        abs(latitude - expected_latitude) > CANONICAL_COORDINATE_TOLERANCE
        or abs(longitude - expected_longitude) > CANONICAL_COORDINATE_TOLERANCE
    ):
        errors.append("requested_location_coordinates_not_canonical")
    return errors


def _snapshot_contract_errors(
    snapshot: Mapping[str, Any],
    municipality: Municipality,
    now: datetime,
    locality: FvgLocality | None = None,
) -> tuple[list[str], datetime | None]:
    errors = _requested_location_errors(snapshot, municipality, locality)

    if _clean(snapshot.get("source")) != SOURCE_ID:
        errors.append("unsupported_source")
    if _clean(snapshot.get("timezone")) != FVG_TIMEZONE:
        errors.append("invalid_timezone")

    fetched_at = _parse_aware_datetime(snapshot.get("fetched_at"))
    if fetched_at is None:
        errors.append("invalid_fetched_at")
    else:
        age = timedelta(seconds=now.timestamp() - fetched_at.timestamp())
        if age > MAX_SNAPSHOT_AGE:
            errors.append("snapshot_stale")
        elif age < -MAX_FUTURE_CLOCK_SKEW:
            errors.append("snapshot_from_future")

        expected_offset = int(
            fetched_at.astimezone(FVG_ZONE).utcoffset().total_seconds()
        )
        try:
            supplied_offset = int(snapshot.get("utc_offset_seconds"))
        except (TypeError, ValueError):
            supplied_offset = None
        if supplied_offset != expected_offset:
            errors.append("utc_offset_mismatch")

    units = snapshot.get("hourly_units")
    if not isinstance(units, Mapping):
        errors.append("missing_hourly_units")
    else:
        for field, expected_unit in EXPECTED_HOURLY_UNITS.items():
            if units.get(field) != expected_unit:
                errors.append(f"invalid_unit:{field}")

    hourly = snapshot.get("hourly")
    if not isinstance(hourly, Mapping):
        errors.append("missing_hourly_data")
    else:
        times = hourly.get("time")
        expected_length = len(times) if isinstance(times, list) else None
        if expected_length is None or expected_length == 0:
            errors.append("missing_hourly_times")
        for field in REQUIRED_HOURLY_FIELDS:
            values = hourly.get(field)
            if not isinstance(values, list):
                errors.append(f"missing_hourly_field:{field}")
            elif expected_length is not None and len(values) != expected_length:
                errors.append(f"hourly_length_mismatch:{field}")

    return list(dict.fromkeys(errors)), fetched_at


def _build_slots(
    hourly: Mapping[str, Any],
    *,
    now: datetime,
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    times = hourly.get("time") or []
    parsed_times = [_parse_hourly_datetime(value) for value in times]
    if any(value is None for value in parsed_times):
        return [], ["invalid_hourly_time"]

    for left, right in zip(parsed_times, parsed_times[1:]):
        if right <= left:
            errors.append("hourly_times_not_increasing")
            break

    slots: list[dict[str, Any]] = []
    local_now = now.astimezone(FVG_ZONE)
    horizon_end = local_now + FORECAST_EVALUATION_HORIZON
    for index, event_at in enumerate(parsed_times):
        if event_at < local_now or event_at > horizon_end:
            continue
        values = {
            field: (hourly.get(field) or [])[index]
            for field in REQUIRED_HOURLY_FIELDS
            if field != "time"
        }
        slots.append({"event_at": event_at, **values})
    return slots, errors


def _future_slot_contract_errors(
    slots: Sequence[dict[str, Any]],
    *,
    now: datetime,
) -> list[str]:
    """Reject incomplete or implausible hourly data instead of reporting no event."""

    if len(slots) < MIN_FUTURE_SLOTS:
        return ["insufficient_future_slots"]

    errors: list[str] = []
    local_now = now.astimezone(FVG_ZONE)
    if slots[0]["event_at"] - local_now > timedelta(minutes=90):
        errors.append("first_future_slot_too_far")
    if any(
        right["event_at"] - left["event_at"] != timedelta(hours=1)
        for left, right in zip(slots, slots[1:])
    ):
        errors.append("future_slots_not_hourly")

    numeric_ranges = {
        "temperature_2m": (-100.0, 70.0),
        "apparent_temperature": (-100.0, 80.0),
        "precipitation_probability": (0.0, 100.0),
        "precipitation": (0.0, 500.0),
        "rain": (0.0, 500.0),
        "showers": (0.0, 500.0),
        "snowfall": (0.0, 100.0),
        "wind_gusts_10m": (0.0, 500.0),
    }
    for slot in slots:
        for field, (minimum, maximum) in numeric_ranges.items():
            value = _as_float(slot.get(field))
            if value is None:
                errors.append(f"invalid_hourly_value:{field}")
            elif value < minimum or value > maximum:
                errors.append(f"hourly_value_out_of_range:{field}")

        weather_code = _as_weather_code(slot.get("weather_code"))
        if weather_code is None:
            errors.append("invalid_hourly_value:weather_code")
        elif weather_code < 0 or weather_code > 99:
            errors.append("hourly_value_out_of_range:weather_code")

    return list(dict.fromkeys(errors))


def _consecutive_windows(
    slots: Sequence[dict[str, Any]],
    size: int,
) -> list[list[dict[str, Any]]]:
    windows: list[list[dict[str, Any]]] = []
    for index in range(0, len(slots) - size + 1):
        window = list(slots[index : index + size])
        if all(
            right["event_at"] - left["event_at"] == timedelta(hours=1)
            for left, right in zip(window, window[1:])
        ):
            windows.append(window)
    return windows


def _event_bucket(kind: str, event_at: datetime) -> str:
    local_event = event_at.astimezone(FVG_ZONE)
    if kind == "heat":
        return local_event.date().isoformat()
    six_hour_start = (local_event.hour // 6) * 6
    return f"{local_event.date().isoformat()}T{six_hour_start:02d}"


def _candidate(
    *,
    municipality: Municipality,
    kind: str,
    category: str,
    severity: int,
    event_at: datetime,
    event_end: datetime,
    threshold: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    bucket = _event_bucket(kind, event_at)
    event_key = (
        f"{SCHEMA_VERSION}:{POLICY_VERSION}:{municipality.istat_code}:"
        f"{kind}:{bucket}"
    )
    signature = hashlib.sha256(event_key.encode("utf-8")).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "mode": "shadow",
        "shadow_only": True,
        "can_notify": False,
        "kind": kind,
        "category": category,
        "severity": severity,
        "priority": NOTICE_PRIORITY[kind],
        "municipality": _municipality_payload(municipality),
        "event_at": _iso(event_at),
        "event_end": _iso(event_end),
        "threshold": dict(threshold),
        "evidence": [dict(item) for item in evidence],
        "dedupe": {
            "event_bucket": bucket,
            "event_key": event_key,
            "signature": signature,
        },
    }


def _storm_candidate(
    municipality: Municipality,
    slots: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    for index, slot in enumerate(slots):
        code = _as_weather_code(slot.get("weather_code"))
        if code in STORM_WEATHER_CODES:
            adjacent_storm_slot = any(
                abs(other_index - index) == 1
                and abs(other_slot["event_at"] - slot["event_at"])
                == timedelta(hours=1)
                and _as_weather_code(other_slot.get("weather_code"))
                in STORM_WEATHER_CODES
                for other_index, other_slot in enumerate(slots)
            )
            probability = _as_float(slot.get("precipitation_probability")) or 0.0
            liquid_precipitation = (
                (_as_float(slot.get("rain")) or 0.0)
                + (_as_float(slot.get("showers")) or 0.0)
            )
            probability_and_liquid = (
                probability >= RAIN_PROBABILITY_THRESHOLD_PERCENT
                and liquid_precipitation > 0.0
            )
            corroborated = probability_and_liquid
            candidate = _candidate(
                municipality=municipality,
                kind="storm",
                category="storms",
                severity=3 if code in {96, 99} else 2,
                event_at=slot["event_at"],
                event_end=slot["event_at"] + timedelta(hours=1),
                threshold={"weather_codes": sorted(STORM_WEATHER_CODES)},
                evidence=[
                    {
                        "metric": "weather_code",
                        "value": code,
                        "unit": "wmo code",
                        "at": _iso(slot["event_at"]),
                    },
                    {
                        "metric": "storm_corroboration",
                        "two_consecutive_storm_slots": adjacent_storm_slot,
                        "precipitation_probability_percent": probability,
                        "liquid_precipitation_mm": round(liquid_precipitation, 2),
                        "probability_and_liquid": probability_and_liquid,
                    },
                ],
            )
            candidate["confidence"] = {
                "level": "corroborated" if corroborated else "single_slot_unconfirmed",
                "corroborated": corroborated,
                "reason": (
                    "wmo_storm_code_with_probability_and_liquid"
                    if corroborated
                    else "wmo_storm_code_without_probability_and_liquid"
                ),
                "send_eligible": False,
            }
            return candidate
    return None


def _rain_candidate(
    municipality: Municipality,
    slots: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    for window in _consecutive_windows(slots, RAIN_WINDOW_HOURS):
        amounts = [
            (_as_float(slot.get("rain")) or 0.0)
            + (_as_float(slot.get("showers")) or 0.0)
            for slot in window
        ]
        probabilities = [
            _as_float(slot.get("precipitation_probability")) or 0.0
            for slot in window
        ]
        total = sum(amounts)
        intense_slot_probabilities = [
            probability
            for amount, probability in zip(amounts, probabilities, strict=True)
            if amount >= RAIN_MINIMUM_HOURLY_AMOUNT_MM
        ]
        peak_probability = (
            max(intense_slot_probabilities) if intense_slot_probabilities else 0.0
        )
        if (
            total >= RAIN_ACCUMULATION_THRESHOLD_MM
            and max(amounts, default=0.0) >= RAIN_MINIMUM_HOURLY_AMOUNT_MM
            and peak_probability >= RAIN_PROBABILITY_THRESHOLD_PERCENT
        ):
            return _candidate(
                municipality=municipality,
                kind="rain",
                category="rain",
                severity=2,
                event_at=window[0]["event_at"],
                event_end=window[-1]["event_at"] + timedelta(hours=1),
                threshold={
                    "accumulation_mm": RAIN_ACCUMULATION_THRESHOLD_MM,
                    "window_hours": RAIN_WINDOW_HOURS,
                    "minimum_hourly_amount_mm": RAIN_MINIMUM_HOURLY_AMOUNT_MM,
                    "minimum_intense_slot_probability_percent": (
                        RAIN_PROBABILITY_THRESHOLD_PERCENT
                    ),
                },
                evidence=[
                    {
                        "metric": "rain_plus_showers_3h",
                        "value": round(total, 2),
                        "unit": "mm",
                        "from": _iso(window[0]["event_at"]),
                        "to": _iso(window[-1]["event_at"] + timedelta(hours=1)),
                    },
                    {
                        "metric": "precipitation_probability_intense_slot_peak",
                        "value": peak_probability,
                        "unit": "%",
                    },
                ],
            )
    return None


def _ice_candidate(
    municipality: Municipality,
    slots: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    for slot in slots:
        code = _as_weather_code(slot.get("weather_code"))
        if code in FREEZING_PRECIPITATION_CODES:
            return _candidate(
                municipality=municipality,
                kind="ice",
                category="snow",
                severity=2,
                event_at=slot["event_at"],
                event_end=slot["event_at"] + timedelta(hours=1),
                threshold={
                    "explicit_weather_codes": sorted(FREEZING_PRECIPITATION_CODES),
                },
                evidence=[
                    {
                        "metric": "weather_code",
                        "value": code,
                        "unit": "wmo code",
                        "at": _iso(slot["event_at"]),
                    }
                ],
            )
    return None


def _snow_candidate(
    municipality: Municipality,
    slots: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    code_trigger = next(
        (
            slot
            for slot in slots
            if _as_weather_code(slot.get("weather_code"))
            in MODERATE_OR_HEAVY_SNOW_CODES
        ),
        None,
    )
    accumulation_trigger = None
    for window in _consecutive_windows(slots, SNOW_WINDOW_HOURS):
        total = sum(_as_float(slot.get("snowfall")) or 0.0 for slot in window)
        probabilities = [
            _as_float(slot.get("precipitation_probability")) or 0.0
            for slot in window
            if (_as_float(slot.get("snowfall")) or 0.0) > 0.0
        ]
        peak_probability = max(probabilities) if probabilities else 0.0
        if (
            total >= SNOW_ACCUMULATION_THRESHOLD_CM
            and peak_probability >= SNOW_PROBABILITY_THRESHOLD_PERCENT
        ):
            accumulation_trigger = (window, total, peak_probability)
            break

    candidates: list[tuple[datetime, str, Any]] = []
    if code_trigger is not None:
        candidates.append((code_trigger["event_at"], "weather_code", code_trigger))
    if accumulation_trigger is not None:
        window, total, peak_probability = accumulation_trigger
        candidates.append(
            (
                window[0]["event_at"],
                "snowfall_3h",
                (window, total, peak_probability),
            )
        )
    if not candidates:
        return None

    event_at, trigger, payload = min(candidates, key=lambda item: item[0])
    if trigger == "weather_code":
        code = _as_weather_code(payload.get("weather_code"))
        event_end = event_at + timedelta(hours=1)
        evidence = [
            {
                "metric": "weather_code",
                "value": code,
                "unit": "wmo code",
                "at": _iso(event_at),
            }
        ]
    else:
        window, total, peak_probability = payload
        event_end = window[-1]["event_at"] + timedelta(hours=1)
        evidence = [
            {
                "metric": "snowfall_3h",
                "value": round(total, 2),
                "unit": "cm",
                "from": _iso(window[0]["event_at"]),
                "to": _iso(event_end),
            },
            {
                "metric": "precipitation_probability_snow_slot_peak",
                "value": peak_probability,
                "unit": "%",
            },
        ]

    return _candidate(
        municipality=municipality,
        kind="snow",
        category="snow",
        severity=2,
        event_at=event_at,
        event_end=event_end,
        threshold={
            "moderate_or_heavy_weather_codes": sorted(
                MODERATE_OR_HEAVY_SNOW_CODES
            ),
            "accumulation_cm": SNOW_ACCUMULATION_THRESHOLD_CM,
            "window_hours": SNOW_WINDOW_HOURS,
            "accumulation_probability_percent": (
                SNOW_PROBABILITY_THRESHOLD_PERCENT
            ),
        },
        evidence=evidence,
    )


def _wind_candidate(
    municipality: Municipality,
    slots: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    for slot in slots:
        gust = _as_float(slot.get("wind_gusts_10m"))
        if gust is not None and gust >= WIND_GUST_THRESHOLD_KMH:
            return _candidate(
                municipality=municipality,
                kind="wind",
                category="wind",
                severity=2,
                event_at=slot["event_at"],
                event_end=slot["event_at"] + timedelta(hours=1),
                threshold={"wind_gust_kmh": WIND_GUST_THRESHOLD_KMH},
                evidence=[
                    {
                        "metric": "wind_gusts_10m",
                        "value": gust,
                        "unit": "km/h",
                        "at": _iso(slot["event_at"]),
                    }
                ],
            )
    return None


def _heat_candidate_and_observations(
    municipality: Municipality,
    slots: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    observations: list[dict[str, Any]] = []
    windows = _consecutive_windows(slots, HEAT_CONSECUTIVE_SLOTS)
    triggers: list[tuple[datetime, str, list[dict[str, Any]], list[float]]] = []

    for metric, threshold in (
        ("temperature_2m", HEAT_TEMPERATURE_THRESHOLD_C),
        ("apparent_temperature", HEAT_APPARENT_THRESHOLD_C),
    ):
        for window in windows:
            values = [_as_float(slot.get(metric)) for slot in window]
            if all(value is not None and value >= threshold for value in values):
                triggers.append((window[0]["event_at"], metric, window, values))
                break

    if triggers:
        _, metric, window, values = min(triggers, key=lambda trigger: trigger[0])
        return (
            _candidate(
                municipality=municipality,
                kind="heat",
                category="heat",
                severity=2,
                event_at=window[0]["event_at"],
                event_end=window[-1]["event_at"] + timedelta(hours=1),
                threshold={
                    "temperature_c": HEAT_TEMPERATURE_THRESHOLD_C,
                    "apparent_temperature_c": HEAT_APPARENT_THRESHOLD_C,
                    "consecutive_slots": HEAT_CONSECUTIVE_SLOTS,
                },
                evidence=[
                    {
                        "metric": metric,
                        "values": values,
                        "unit": "°C",
                        "from": _iso(window[0]["event_at"]),
                        "to": _iso(window[-1]["event_at"] + timedelta(hours=1)),
                    }
                ],
            ),
            observations,
        )

    for window in windows:
        values = [_as_float(slot.get("apparent_temperature")) for slot in window]
        if all(
            value is not None and value >= HEAT_WATCH_APPARENT_THRESHOLD_C
            for value in values
        ):
            observations.append(
                {
                    "kind": "heat_watch",
                    "candidate": False,
                    "reason": "apparent_temperature_watch_below_candidate_threshold",
                    "values": values,
                    "unit": "°C",
                    "from": _iso(window[0]["event_at"]),
                    "to": _iso(window[-1]["event_at"] + timedelta(hours=1)),
                }
            )
            break
    return None, observations


def _partition_notice_window(
    candidates: Sequence[dict[str, Any]],
    *,
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep only phenomena whose onset is no more than one hour away.

    The detector still evaluates six forecast hours so multi-hour rain, snow and
    heat evidence remains available.  Only the notice onset is restricted.
    """

    local_now = now.astimezone(FVG_ZONE)
    eligible: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for candidate in candidates:
        event_at = _parse_aware_datetime(candidate.get("event_at"))
        if event_at is None:
            continue
        lead = event_at.astimezone(FVG_ZONE) - local_now
        if timedelta(0) <= lead <= NOTICE_MAX_LEAD_TIME:
            eligible.append(candidate)
            continue
        if lead > NOTICE_MAX_LEAD_TIME:
            deferred.append(
                {
                    "kind": candidate.get("kind"),
                    "candidate": False,
                    "reason": "onset_beyond_notice_window",
                    "event_at": candidate.get("event_at"),
                    "lead_minutes": int(lead.total_seconds() // 60),
                    "maximum_lead_minutes": int(
                        NOTICE_MAX_LEAD_TIME.total_seconds() // 60
                    ),
                }
            )
    return eligible, deferred


def evaluate_local_notice_shadow(
    municipality_reference: str,
    snapshot: Mapping[str, Any],
    *,
    now: datetime | None = None,
    catalog: LocationCatalog | None = None,
    locality: FvgLocality | None = None,
) -> dict[str, Any]:
    """Validate a snapshot and return non-sendable local notice candidates."""

    evaluation_now = now or datetime.now(FVG_ZONE)
    if evaluation_now.tzinfo is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "policy_version": POLICY_VERSION,
            "mode": "shadow",
            "shadow_only": True,
            "can_send": False,
            "status": "rejected",
            "municipality": None,
            "validation_errors": ["now_must_be_timezone_aware"],
            "candidates": [],
            "observations": [],
        }

    municipality = resolve_canonical_municipality(
        municipality_reference,
        catalog=catalog,
    )
    if municipality is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "policy_version": POLICY_VERSION,
            "mode": "shadow",
            "shadow_only": True,
            "can_send": False,
            "status": "rejected",
            "municipality": None,
            "validation_errors": ["unknown_fvg_municipality"],
            "candidates": [],
            "observations": [],
        }
    if locality is not None and locality.municipality_istat != municipality.istat_code:
        return {
            "schema_version": SCHEMA_VERSION,
            "policy_version": POLICY_VERSION,
            "mode": "shadow",
            "shadow_only": True,
            "can_send": False,
            "status": "rejected",
            "municipality": _municipality_payload(municipality),
            "locality": locality.to_public_dict(),
            "validation_errors": ["locality_municipality_mismatch"],
            "candidates": [],
            "observations": [],
        }

    if not isinstance(snapshot, Mapping):
        errors = ["invalid_snapshot"]
        fetched_at = None
    else:
        errors, fetched_at = _snapshot_contract_errors(
            snapshot,
            municipality,
            evaluation_now,
            locality,
        )

    slots: list[dict[str, Any]] = []
    if not errors:
        slots, slot_errors = _build_slots(
            snapshot["hourly"],
            now=evaluation_now,
        )
        errors.extend(slot_errors)
        if not slot_errors:
            errors.extend(
                _future_slot_contract_errors(slots, now=evaluation_now)
            )

    base = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "mode": "shadow",
        "shadow_only": True,
        "can_send": False,
        "municipality": _municipality_payload(municipality),
        "locality": locality.to_public_dict() if locality is not None else None,
        "evaluated_at": _iso(evaluation_now.astimezone(FVG_ZONE)),
        "snapshot": {
            "source": _clean(snapshot.get("source")) if isinstance(snapshot, Mapping) else "",
            "fetched_at": _iso(fetched_at.astimezone(FVG_ZONE)) if fetched_at else "",
            "timezone": _clean(snapshot.get("timezone")) if isinstance(snapshot, Mapping) else "",
            "eligible_slots": len(slots),
        },
        "validation_errors": list(dict.fromkeys(errors)),
    }
    if errors:
        return {**base, "status": "rejected", "candidates": [], "observations": []}

    heat_candidate, observations = _heat_candidate_and_observations(
        municipality,
        slots,
    )
    detected_candidates = [
        candidate
        for candidate in (
            _storm_candidate(municipality, slots),
            _ice_candidate(municipality, slots),
            _snow_candidate(municipality, slots),
            _wind_candidate(municipality, slots),
            _rain_candidate(municipality, slots),
            heat_candidate,
        )
        if candidate is not None
    ]
    candidates, deferred_observations = _partition_notice_window(
        detected_candidates,
        now=evaluation_now,
    )
    observations.extend(deferred_observations)
    candidates.sort(
        key=lambda candidate: (
            candidate["event_at"],
            -candidate["priority"],
            candidate["kind"],
        )
    )
    if locality is not None:
        for candidate in candidates:
            candidate["locality"] = locality.to_public_dict()
            dedupe = candidate.get("dedupe") or {}
            bucket = str(dedupe.get("event_bucket") or "")
            event_key = (
                f"{SCHEMA_VERSION}:{POLICY_VERSION}:{municipality.istat_code}:"
                f"{locality.id}:{candidate['kind']}:{bucket}"
            )
            candidate["dedupe"] = {
                **dedupe,
                "event_key": event_key,
                "signature": hashlib.sha256(event_key.encode("utf-8")).hexdigest(),
            }
    return {
        **base,
        "status": "candidates" if candidates else "no_candidate",
        "candidates": candidates,
        "observations": observations,
    }
