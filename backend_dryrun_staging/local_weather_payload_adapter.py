"""Adapt saved/read-only weather payloads into local notice snapshots.

This module is pure. It reads in-memory payload dictionaries and returns the
minimal shape needed by the local notice detector. It does not fetch network,
write storage, call Firestore or send FCM.
"""

from __future__ import annotations

from typing import Any


TEXT_SIGNAL_PATTERNS = {
    "heat": ("cald", "calore", "afa", "afoso", "temperature elevate", "record"),
    "storm": ("temporale", "temporali"),
    "hail": ("grandine",),
    "rain": ("piogg", "rovesc", "precipit"),
    "snow": ("neve", "nevicat"),
    "ice": ("ghiaccio", "gelat"),
    "wind": ("vento forte", "venti forti", "vento sostenuto", "vento moderato", "raffich"),
    "bora": ("bora", "buere"),
}

TEXT_KEYS = {
    "official_text",
    "text",
    "situation",
    "regional",
    "summary",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def lower_text(value: Any) -> str:
    return clean_text(value).casefold()


def is_object(value: Any) -> bool:
    return isinstance(value, dict)


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def read_number(value: Any, fallback: float | None = None) -> float | None:
    try:
        return float(value) if value is not None else fallback
    except (TypeError, ValueError):
        return fallback


def slot_time(slot: dict[str, Any]) -> str:
    return clean_text(slot.get("time"))[:16]


def summarize_weather(weather: dict[str, Any]) -> dict[str, Any]:
    hourly = as_list(weather.get("hourly_next_12h"))
    peak_temperature = None
    peak_temperature_time = ""
    max_precipitation = None
    max_precipitation_time = ""
    max_probability = None
    max_probability_time = ""
    max_wind_gusts = None
    max_wind_gusts_time = ""

    for slot in hourly:
        if not is_object(slot):
            continue
        temperature = read_number(slot.get("temperature"))
        if temperature is not None and (peak_temperature is None or temperature > peak_temperature):
            peak_temperature = temperature
            peak_temperature_time = slot_time(slot)

        precipitation_values = [
            read_number(slot.get("precipitation"), 0) or 0,
            read_number(slot.get("rain"), 0) or 0,
            read_number(slot.get("showers"), 0) or 0,
        ]
        precipitation = max(precipitation_values)
        if max_precipitation is None or precipitation > max_precipitation:
            max_precipitation = precipitation
            max_precipitation_time = slot_time(slot)

        probability = read_number(slot.get("precipitation_probability"))
        if probability is not None and (max_probability is None or probability > max_probability):
            max_probability = probability
            max_probability_time = slot_time(slot)

        wind_gusts = read_number(slot.get("wind_gusts"))
        if wind_gusts is not None and (max_wind_gusts is None or wind_gusts > max_wind_gusts):
            max_wind_gusts = wind_gusts
            max_wind_gusts_time = slot_time(slot)

    return {
        "temperature": read_number(weather.get("temperature")),
        "feels_like": read_number(weather.get("feels_like")),
        "observed_at": clean_text(weather.get("observed_at")),
        "hourly_count": len(hourly),
        "peak_temperature": peak_temperature,
        "peak_temperature_time": peak_temperature_time,
        "max_precipitation": max_precipitation,
        "max_precipitation_time": max_precipitation_time,
        "max_probability": max_probability,
        "max_probability_time": max_probability_time,
        "max_wind_gusts": max_wind_gusts,
        "max_wind_gusts_time": max_wind_gusts_time,
    }


def build_observed_at(current: dict[str, Any], cache: dict[str, Any]) -> str:
    explicit = clean_text(current.get("observed_at"))
    if len(explicit) >= 16:
        return explicit[:16]

    station = current.get("station") if is_object(current.get("station")) else {}
    station_time = clean_text(station.get("time"))
    generated_at = clean_text(cache.get("generated_at"))
    if len(generated_at) >= 10 and len(station_time) >= 5:
        return f"{generated_at[:10]}T{station_time[:5]}"

    current_time = clean_text(current.get("time"))
    if len(current_time) >= 16:
        return current_time[:16]
    if len(generated_at) >= 16:
        return generated_at[:16]
    return ""


def compact_source_status(payload: dict[str, Any]) -> dict[str, Any]:
    current = payload.get("current") if is_object(payload.get("current")) else {}
    source = current.get("source") if is_object(current.get("source")) else payload.get("source")
    data_quality = current.get("data_quality") if is_object(current.get("data_quality")) else payload.get("data_quality")
    cache = current.get("cache") if is_object(current.get("cache")) else payload.get("cache")

    return {
        "source_active": source.get("active") if is_object(source) else "",
        "primary_source": source.get("primary_source") if is_object(source) else "",
        "model_support": source.get("model_support") if is_object(source) else {},
        "data_quality": data_quality if is_object(data_quality) else {},
        "cache": cache if is_object(cache) else {},
    }


def extract_current_weather(payload: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    if is_object(payload.get("weather")):
        city = clean_text(payload.get("city") or payload["weather"].get("city"))
        return city, dict(payload["weather"]), "direct_weather_snapshot"

    current = payload.get("current") if is_object(payload.get("current")) else {}
    cache = current.get("cache") if is_object(current.get("cache")) else payload.get("cache")
    city = clean_text(payload.get("city") or current.get("city"))
    weather = {
        "temperature": current.get("temperature"),
        "feels_like": current.get("feels_like"),
        "weathercode": current.get("weathercode"),
        "wind_speed": current.get("wind_speed"),
        "wind_direction": current.get("wind_direction"),
        "wind_gusts": current.get("wind_gusts"),
        "cloud_cover": current.get("cloud_cover"),
        "precipitation": current.get("precipitation"),
        "rain": current.get("rain"),
        "showers": current.get("showers"),
        "snowfall": current.get("snowfall"),
        "is_bora": current.get("is_bora"),
        "humidity": current.get("humidity"),
        "pressure": current.get("pressure"),
        "hourly_next_12h": as_list(current.get("hourly_next_12h")),
        "observed_at": build_observed_at(current, cache if is_object(cache) else {}),
    }
    return city, weather, "weather_bootstrap"


def extract_official_alerts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    official_alerts = payload.get("official_alerts")
    if not is_object(official_alerts):
        return []
    alerts = official_alerts.get("alerts")
    return [alert for alert in as_list(alerts) if is_object(alert)]


def collect_text_fields(value: Any, fields: list[str] | None = None) -> list[str]:
    fields = fields if fields is not None else []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in TEXT_KEYS:
                if isinstance(child, str):
                    fields.append(clean_text(child))
                elif isinstance(child, dict):
                    text = clean_text(child.get("text"))
                    if text:
                        fields.append(text)
                elif isinstance(child, list):
                    collect_text_fields(child, fields)
            elif isinstance(child, (dict, list)):
                collect_text_fields(child, fields)
    elif isinstance(value, list):
        for child in value:
            collect_text_fields(child, fields)
    return fields


def detect_text_signals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    texts_by_key = {
        lower_text(text): text
        for text in collect_text_fields(payload)
        if text
    }
    texts = list(texts_by_key.values())
    signals: list[dict[str, Any]] = []
    for kind, patterns in TEXT_SIGNAL_PATTERNS.items():
        matches = [
            text
            for text in texts
            if any(pattern in lower_text(text) for pattern in patterns)
        ]
        if not matches:
            continue
        signals.append(
            {
                "kind": kind,
                "count": len(matches),
                "samples": matches[:2],
                "used_for_local_push": False,
                "reason": "segnale testuale regionale: non basta per una push locale",
            }
        )
    return signals


def detect_payload_gaps(weather: dict[str, Any], source_status: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not weather.get("hourly_next_12h"):
        gaps.append("missing_hourly_next_12h")
    if weather.get("feels_like") is None:
        gaps.append("missing_feels_like")
    if weather.get("weathercode") is None and not weather.get("hourly_next_12h"):
        gaps.append("missing_weathercode_and_hourly_codes")

    model_support = source_status.get("model_support")
    if is_object(model_support) and model_support.get("hourly") is False:
        gaps.append("hourly_model_support_false")

    data_quality = source_status.get("data_quality")
    if is_object(data_quality):
        status = clean_text(data_quality.get("status"))
        if status and status not in ("fresh", "ready"):
            gaps.append(f"data_quality_{status}")

    return gaps


def adapt_weather_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not is_object(payload):
        raise TypeError("Il payload meteo deve essere un oggetto JSON.")

    city, weather, source_shape = extract_current_weather(payload)
    source_status = compact_source_status(payload)
    return {
        "schema_version": "1.0",
        "source_shape": source_shape,
        "city": city,
        "weather": weather,
        "numeric_snapshot": summarize_weather(weather),
        "official_alerts": extract_official_alerts(payload),
        "source_status": source_status,
        "data_gaps": detect_payload_gaps(weather, source_status),
        "text_signals": detect_text_signals(payload),
    }


def iter_payload_objects(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if is_object(item)]
    if not is_object(raw):
        raise TypeError("Il JSON deve contenere un oggetto payload o una lista di payload.")
    for key in ("payloads", "items", "cities"):
        if isinstance(raw.get(key), list):
            return [item for item in raw[key] if is_object(item)]
    return [raw]
