"""Pure detector for local weather notice candidates.

This module only turns a city weather snapshot into raw local notice candidates.
It does not import the backend, fetch network data, write storage, call
Firestore or send FCM.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


RAIN_PRECIPITATION_THRESHOLD_MM = 0.3
RAIN_PROBABILITY_THRESHOLD = 60
STORM_WEATHER_CODES = (95, 96, 99)
HAIL_WEATHER_CODES = (96, 99)
SNOW_WEATHER_CODES = (71, 73, 75, 77, 85, 86)
SNOWFALL_THRESHOLD_MM = 0.2
WIND_GUST_THRESHOLD_KMH = 55
HEAT_NOTICE_TEMPERATURE_THRESHOLD = 33.0
HEAT_NOTICE_FEELS_LIKE_THRESHOLD = 34.0
ICE_NOTICE_TEMPERATURE_THRESHOLD = 0.0
FREEZING_PRECIPITATION_CODES = (56, 57, 66, 67)
DETECTOR_WINDOW_HOURS = 8


NOTICE_THRESHOLDS = {
    "rain": "rain/precipitation >= 0.3 mm or precipitation_probability >= 60%",
    "storm": "weathercode in 95, 96, 99",
    "hail": "weathercode in 96, 99",
    "snow": "weathercode snow or snowfall >= 0.2 mm",
    "ice": "freezing precipitation or temp <= 0 with wet slot/probability",
    "wind": "wind_gusts >= 55 km/h",
    "bora": "wind_gusts >= 55 km/h and Bora exposure/direction",
    "heat": "temperature >= 33 C or feels_like >= 34 C",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_for_search(value: Any) -> str:
    text = clean_text(value).casefold()
    replacements = (
        ("à", "a"),
        ("è", "e"),
        ("é", "e"),
        ("ì", "i"),
        ("ò", "o"),
        ("ù", "u"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def read_hourly_number(slot: dict[str, Any], key: str, fallback: float = 0) -> float:
    try:
        value = slot.get(key)
        return float(value) if value is not None else fallback
    except (TypeError, ValueError):
        return fallback


def parse_hourly_slot_datetime(value: Any) -> datetime | None:
    raw = clean_text(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw[:19])
    except ValueError:
        try:
            return datetime.fromisoformat(raw[:16])
        except ValueError:
            return None


def format_push_time_label(value: Any) -> str:
    parsed = parse_hourly_slot_datetime(value)
    if not parsed:
        return ""
    return parsed.strftime("%H:%M")


def precipitation_amount(slot: dict[str, Any]) -> float:
    return max(
        read_hourly_number(slot, "precipitation"),
        read_hourly_number(slot, "rain"),
        read_hourly_number(slot, "showers"),
    )


def slot_weather_code(slot: dict[str, Any], fallback: int = -1) -> int:
    return int(read_hourly_number(slot, "weathercode", fallback))


def is_local_ice_slot(slot: dict[str, Any]) -> bool:
    code = slot_weather_code(slot)
    if code in SNOW_WEATHER_CODES or read_hourly_number(slot, "snowfall") >= SNOWFALL_THRESHOLD_MM:
        return False
    if code in FREEZING_PRECIPITATION_CODES:
        return True

    temperature = read_hourly_number(slot, "temperature", 999)
    probability = read_hourly_number(slot, "precipitation_probability", -1)
    return (
        temperature <= ICE_NOTICE_TEMPERATURE_THRESHOLD
        and (precipitation_amount(slot) >= 0.1 or probability >= 50)
    )


def is_bora_wind_direction(direction: Any) -> bool:
    if direction is None:
        return True
    try:
        deg = float(direction) % 360
    except (TypeError, ValueError):
        return False
    return 20 <= deg <= 110


def is_bora_exposed_area(city: str) -> bool:
    name = normalize_for_search(city)
    exposed_names = (
        "trieste",
        "muggia",
        "duino",
        "aurisina",
        "sistiana",
        "monfalcone",
        "ronchi",
        "staranzano",
        "grado",
        "gorizia",
        "savogna",
        "doberdo",
        "san dorligo",
        "carso",
        "lignano",
        "lignano sabbiadoro",
    )
    return any(place in name for place in exposed_names)


def is_bora_notice_slot(city: str, slot: dict[str, Any], weather: dict[str, Any]) -> bool:
    if weather.get("is_bora") is True:
        return True
    direction = read_hourly_number(slot, "wind_direction", -1)
    return is_bora_exposed_area(city) and is_bora_wind_direction(direction)


def slot_evidence(slot: dict[str, Any], kind: str) -> str:
    time_label = format_push_time_label(slot.get("time"))
    prefix = f"{time_label}: " if time_label else ""
    if kind in ("storm", "hail"):
        return f"{prefix}weathercode {slot_weather_code(slot)}"
    if kind == "rain":
        return (
            f"{prefix}rain {precipitation_amount(slot):g} mm, "
            f"probability {read_hourly_number(slot, 'precipitation_probability'):g}%"
        )
    if kind == "snow":
        return (
            f"{prefix}weathercode {slot_weather_code(slot)}, "
            f"snowfall {read_hourly_number(slot, 'snowfall'):g} mm"
        )
    if kind == "ice":
        return (
            f"{prefix}temp {read_hourly_number(slot, 'temperature'):g} C, "
            f"weathercode {slot_weather_code(slot)}, "
            f"precip/probability {precipitation_amount(slot):g} mm/"
            f"{read_hourly_number(slot, 'precipitation_probability'):g}%"
        )
    if kind in ("wind", "bora"):
        return (
            f"{prefix}gusts {read_hourly_number(slot, 'wind_gusts'):g} km/h, "
            f"direction {read_hourly_number(slot, 'wind_direction', -1):g}"
        )
    return ""


def build_local_notice(
    *,
    kind: str,
    category: str,
    severity: int,
    city: str,
    starts_at: str = "",
    body: str,
    body_fur: str = "",
    source: str,
    reminder_window: str,
    evidence: str = "",
    trigger_source: str = "",
    trigger_value: float | None = None,
    trigger_unit: str = "",
) -> dict[str, Any]:
    notice = {
        "kind": kind,
        "category": category,
        "severity": severity,
        "city": city,
        "starts_at": starts_at or "",
        "event_at": (starts_at or "")[:16],
        "reminder_window": reminder_window,
        "title": "Meteo Friul",
        "body": body,
        "title_i18n": {"it": "Meteo Friul", "fur": "Meteo Friul"},
        "body_i18n": {"it": body, "fur": body_fur or body},
        "source": source,
        "threshold": NOTICE_THRESHOLDS.get(kind, ""),
        "evidence": evidence,
    }
    if trigger_source:
        notice["trigger_source"] = trigger_source
    if trigger_value is not None:
        notice["trigger_value"] = trigger_value
    if trigger_unit:
        notice["trigger_unit"] = trigger_unit
    return notice


def notice_body(base: str, time_value: Any) -> str:
    time_label = format_push_time_label(time_value)
    if time_label:
        return f"{base} verso le {time_label}."
    return f"{base}."


def find_storm_slot(candidate_slots: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (slot for slot in candidate_slots if slot_weather_code(slot) in STORM_WEATHER_CODES),
        None,
    )


def find_rain_slot(candidate_slots: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            slot
            for slot in candidate_slots
            if precipitation_amount(slot) >= RAIN_PRECIPITATION_THRESHOLD_MM
            or read_hourly_number(slot, "precipitation_probability") >= RAIN_PROBABILITY_THRESHOLD
        ),
        None,
    )


def find_snow_slot(candidate_slots: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            slot
            for slot in candidate_slots
            if slot_weather_code(slot) in SNOW_WEATHER_CODES
            or read_hourly_number(slot, "snowfall") >= SNOWFALL_THRESHOLD_MM
        ),
        None,
    )


def find_wind_slot(candidate_slots: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            slot
            for slot in candidate_slots
            if read_hourly_number(slot, "wind_gusts") >= WIND_GUST_THRESHOLD_KMH
        ),
        None,
    )


def build_local_heat_notice(
    city: str,
    weather: dict[str, Any],
    candidate_slots: list[dict[str, Any]],
    reminder_window: str,
) -> dict[str, Any] | None:
    current_temperature = read_hourly_number(weather, "temperature", -999)
    current_feels_like = read_hourly_number(weather, "feels_like", current_temperature)
    hottest_slot = None
    hottest_temperature = -999.0

    for slot in candidate_slots:
        slot_temperature = read_hourly_number(slot, "temperature", -999)
        if slot_temperature > hottest_temperature:
            hottest_temperature = slot_temperature
            hottest_slot = slot

    trigger_source = ""
    trigger_value = None
    starts_at = ""

    if current_feels_like >= HEAT_NOTICE_FEELS_LIKE_THRESHOLD:
        trigger_source = "current_feels_like"
        trigger_value = current_feels_like
        starts_at = str(weather.get("observed_at") or "")[:16]
    elif current_temperature >= HEAT_NOTICE_TEMPERATURE_THRESHOLD:
        trigger_source = "current_temperature"
        trigger_value = current_temperature
        starts_at = str(weather.get("observed_at") or "")[:16]
    elif hottest_temperature >= HEAT_NOTICE_TEMPERATURE_THRESHOLD:
        trigger_source = "hourly_temperature"
        trigger_value = hottest_temperature
        if hottest_slot and hottest_slot.get("time"):
            starts_at = str(hottest_slot.get("time"))[:16]

    if not trigger_source:
        return None

    if not starts_at:
        first_slot_time = str(candidate_slots[0].get("time") or "") if candidate_slots else ""
        starts_at = first_slot_time[:10] or datetime.now().date().isoformat()

    evidence = (
        f"current {current_temperature:g} C, feels_like {current_feels_like:g} C, "
        f"peak {hottest_temperature:g} C; trigger {trigger_source} {trigger_value:g} C"
    )
    return build_local_notice(
        kind="heat",
        category="heat",
        severity=1,
        city=city,
        starts_at=starts_at,
        reminder_window=reminder_window,
        body=f"Caldo previsto oggi a {city}.",
        body_fur=f"Cjalt previodut vue a {city}.",
        source="osmer_station_and_open_meteo_support",
        evidence=evidence,
        trigger_source=trigger_source,
        trigger_value=trigger_value,
        trigger_unit="C",
    )


def detect_local_weather_notices(
    city: str,
    weather: dict[str, Any] | None,
    *,
    reminder_window: str = "afternoon",
) -> list[dict[str, Any]]:
    city = clean_text(city)
    if not city or not weather:
        return []

    hourly = weather.get("hourly_next_12h") or []
    if not isinstance(hourly, list):
        return []

    notices: list[dict[str, Any]] = []
    candidate_slots = hourly[:DETECTOR_WINDOW_HOURS]

    storm_slot = find_storm_slot(candidate_slots)
    if storm_slot:
        code = slot_weather_code(storm_slot, 95)
        is_hail = code in HAIL_WEATHER_CODES
        kind = "hail" if is_hail else "storm"
        body = notice_body(
            "Temporali con possibile grandine previsti" if is_hail else "Temporali previsti",
            storm_slot.get("time"),
        )
        notices.append(
            build_local_notice(
                kind=kind,
                category="storms",
                severity=3 if is_hail else 2,
                city=city,
                starts_at=str(storm_slot.get("time") or "")[:16],
                reminder_window=reminder_window,
                body=body,
                source="open_meteo_model_support",
                evidence=slot_evidence(storm_slot, kind),
            )
        )

    ice_slot = next((slot for slot in candidate_slots if is_local_ice_slot(slot)), None)
    rain_slot = find_rain_slot(candidate_slots)
    if rain_slot and not storm_slot and not ice_slot:
        amount = precipitation_amount(rain_slot)
        notices.append(
            build_local_notice(
                kind="rain",
                category="rain",
                severity=1 if amount < 1 else 2,
                city=city,
                starts_at=str(rain_slot.get("time") or "")[:16],
                reminder_window=reminder_window,
                body=notice_body("Pioggia prevista", rain_slot.get("time")),
                source="open_meteo_model_support",
                evidence=slot_evidence(rain_slot, "rain"),
            )
        )

    if ice_slot:
        notices.append(
            build_local_notice(
                kind="ice",
                category="snow",
                severity=2,
                city=city,
                starts_at=str(ice_slot.get("time") or "")[:16],
                reminder_window=reminder_window,
                body="Possibile ghiaccio nelle ore piu fredde.",
                body_fur="Pussibil glac tes oris plui freddis.",
                source="open_meteo_model_support",
                evidence=slot_evidence(ice_slot, "ice"),
            )
        )

    snow_slot = find_snow_slot(candidate_slots)
    if snow_slot:
        notices.append(
            build_local_notice(
                kind="snow",
                category="snow",
                severity=2,
                city=city,
                starts_at=str(snow_slot.get("time") or "")[:16],
                reminder_window=reminder_window,
                body=notice_body("Neve prevista", snow_slot.get("time")),
                source="open_meteo_model_support",
                evidence=slot_evidence(snow_slot, "snow"),
            )
        )

    wind_slot = find_wind_slot(candidate_slots)
    if wind_slot:
        is_bora_notice = is_bora_notice_slot(city, wind_slot, weather)
        kind = "bora" if is_bora_notice else "wind"
        notices.append(
            build_local_notice(
                kind=kind,
                category="wind",
                severity=2,
                city=city,
                starts_at=str(wind_slot.get("time") or "")[:16],
                reminder_window=reminder_window,
                body=notice_body("Bora prevista" if is_bora_notice else "Vento forte previsto", wind_slot.get("time")),
                source="open_meteo_model_support",
                evidence=slot_evidence(wind_slot, kind),
            )
        )

    heat_notice = build_local_heat_notice(city, weather, candidate_slots, reminder_window)
    if heat_notice:
        notices.append(heat_notice)

    return sorted(notices, key=lambda item: item.get("severity", 0), reverse=True)


def local_notice_suppressed_by_official_alert(
    notice: dict[str, Any],
    official_alerts: list[dict[str, Any]],
) -> bool:
    if not official_alerts:
        return False

    category = str(notice.get("category") or "")
    risk_text = normalize_for_search(
        " ".join(
            " ".join(alert.get("risks") or []) + " " + str(alert.get("official_text") or "")
            for alert in official_alerts
            if isinstance(alert, dict)
        )
    )

    if category in ("rain", "storms"):
        return any(
            needle in risk_text
            for needle in ("temporali", "temporale", "idrogeologico", "idraulico", "piogg", "rovesc")
        )
    if category == "wind":
        return any(needle in risk_text for needle in ("vento", "bora", "raffich"))
    if category == "snow":
        return any(needle in risk_text for needle in ("neve", "nevicat", "ghiaccio", "gelat", "valang"))
    if category == "heat":
        return any(
            needle in risk_text
            for needle in ("caldo", "afa", "calore", "temperature elevate", "temperature estreme")
        )
    return False
