"""Normalize raw local weather notices into clean notification candidates.

This module is pure: it does not import the backend, call network, write
storage, use Firestore or send FCM.

It is the bridge between a raw generator and the pure notification policy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


ALLOWED_KIND_CATEGORY = {
    "rain": "rain",
    "storm": "storms",
    "hail": "storms",
    "snow": "snow",
    "ice": "snow",
    "wind": "wind",
    "bora": "wind",
    "heat": "heat",
}

MACRO_LOCATION_LABELS = {
    "fvg",
    "friuli venezia giulia",
    "regione",
    "regione fvg",
    "pianura",
    "montagna",
    "monti",
    "costa",
    "laguna",
    "prealpi",
    "alpi",
}

FORBIDDEN_BODY_TERMS = (
    "allerta",
    "gialla",
    "arancione",
    "rossa",
    "criticita",
    "emergenza",
    "pericolo",
)

SOURCE_INPUTS_BY_SOURCE = {
    "osmer_station": ["osmer_station"],
    "osmer_station_and_open_meteo_support": ["osmer_station", "open_meteo_hourly_support"],
    "open_meteo_model_support": ["open_meteo_hourly_support"],
}

CONFIDENCE_BY_SOURCE = {
    "osmer_station": "high",
    "osmer_station_and_open_meteo_support": "medium",
    "open_meteo_model_support": "medium",
}


def normalized_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalized_city_key(value: Any) -> str:
    return normalized_text(value).casefold()


def looks_like_macro_location(city: str) -> bool:
    key = normalized_city_key(city)
    return not key or key in MACRO_LOCATION_LABELS


def has_forbidden_body_terms(body: str) -> bool:
    text = body.casefold()
    return any(term in text for term in FORBIDDEN_BODY_TERMS)


def body_has_city(body: str, city: str) -> bool:
    return normalized_city_key(city) in normalized_city_key(body)


def parse_event_at(value: Any) -> tuple[str, str]:
    raw = normalized_text(value)
    if not raw:
        return "", ""
    if len(raw) >= 16:
        candidate = raw[:16]
        try:
            datetime.fromisoformat(candidate)
            return candidate, "hour"
        except ValueError:
            return raw, ""
    if len(raw) == 10:
        try:
            datetime.fromisoformat(raw)
            return raw, "day"
        except ValueError:
            return raw, ""
    return raw, ""


def insert_city_in_known_body(body: str, city: str) -> tuple[str, str]:
    clean = normalized_text(body)
    if not clean or body_has_city(clean, city):
        return clean, ""

    replacements = (
        ("Pioggia prevista verso le ", f"Pioggia prevista a {city} verso le "),
        ("Temporali previsti verso le ", f"Temporali previsti a {city} verso le "),
        (
            "Temporali con possibile grandine previsti verso le ",
            f"Temporali con possibile grandine previsti a {city} verso le ",
        ),
        ("Neve prevista verso le ", f"Neve prevista a {city} verso le "),
        ("Bora prevista verso le ", f"Bora prevista a {city} verso le "),
        ("Vento forte previsto verso le ", f"Vento forte previsto a {city} verso le "),
        ("Possibile ghiaccio nelle ore piu fredde.", f"Possibile ghiaccio a {city} nelle ore piu fredde."),
        ("Possibile ghiaccio nelle ore piu' fredde.", f"Possibile ghiaccio a {city} nelle ore piu' fredde."),
        ("Possibile ghiaccio nelle ore più fredde.", f"Possibile ghiaccio a {city} nelle ore più fredde."),
    )
    for prefix, replacement in replacements:
        if clean.startswith(prefix):
            return replacement + clean[len(prefix):], "inserted_city"

    return clean, ""


def source_inputs_for(source: str) -> list[str]:
    return list(SOURCE_INPUTS_BY_SOURCE.get(source, []))


def confidence_for(source: str) -> str:
    return CONFIDENCE_BY_SOURCE.get(source, "low")


def normalize_notice_candidate(
    raw_notice: dict[str, Any],
    *,
    expected_city: str = "",
    event_at: str = "",
    threshold: str = "",
    evidence: str = "",
    official_alert_overlap: bool = False,
) -> dict[str, Any]:
    raw = dict(raw_notice or {})
    validation_errors: list[str] = []
    copy_normalizations: list[str] = []

    city = normalized_text(expected_city or raw.get("city"))
    kind = normalized_text(raw.get("kind")).lower()
    raw_category = normalized_text(raw.get("category")).lower()
    category = ALLOWED_KIND_CATEGORY.get(kind, raw_category)

    if not city or looks_like_macro_location(city):
        validation_errors.append("invalid_city")

    if kind not in ALLOWED_KIND_CATEGORY:
        validation_errors.append("invalid_kind")

    if category != ALLOWED_KIND_CATEGORY.get(kind, category):
        validation_errors.append("category_mismatch")

    starts_at = normalized_text(raw.get("starts_at"))
    normalized_event_at, event_precision = parse_event_at(event_at or starts_at)
    if not normalized_event_at or not event_precision:
        validation_errors.append("invalid_event_at")

    body, copy_action = insert_city_in_known_body(normalized_text(raw.get("body")), city)
    if copy_action:
        copy_normalizations.append(copy_action)

    if not body:
        validation_errors.append("missing_body")
    elif has_forbidden_body_terms(body):
        validation_errors.append("forbidden_body_terms")
    elif city and not body_has_city(body, city):
        validation_errors.append("body_missing_city")

    source = normalized_text(raw.get("source"))
    source_inputs = source_inputs_for(source)
    confidence = normalized_text(raw.get("confidence")) or confidence_for(source)
    if not source_inputs:
        validation_errors.append("unknown_source")
    if confidence not in ("high", "medium", "low"):
        validation_errors.append("invalid_confidence")
        confidence = "low"

    if official_alert_overlap:
        state = "suppressed_by_official_alert"
    elif validation_errors:
        state = "low_confidence" if "unknown_source" in validation_errors else "invalid_candidate"
    else:
        state = "ready"

    reason = (
        "soppresso: allerta ufficiale copre la stessa categoria"
        if official_alert_overlap
        else "fenomeno localizzato, candidato normalizzato"
        if state == "ready"
        else "; ".join(validation_errors)
    )

    candidate_can_notify = state == "ready" and confidence in ("high", "medium")

    return {
        "schema_version": "1.0",
        "type": "local_weather_notice",
        "state": state,
        "status": state,
        "kind": kind,
        "category": category,
        "city": city,
        "starts_at": starts_at,
        "event_at": normalized_event_at,
        "event_precision": event_precision,
        "reminder_window": normalized_text(raw.get("reminder_window")),
        "severity": raw.get("severity"),
        "title": normalized_text(raw.get("title")) or "Meteo Friul",
        "body": body,
        "source": source,
        "source_kind": "local_weather_model",
        "source_authority": "meteo_friul",
        "source_inputs": source_inputs,
        "confidence": confidence,
        "official_alert_overlap": bool(official_alert_overlap),
        "candidate_can_notify": candidate_can_notify,
        "can_notify": False,
        "notification_policy": "",
        "notification_reason": "",
        "threshold": normalized_text(threshold),
        "evidence": normalized_text(evidence),
        "trigger_source": normalized_text(raw.get("trigger_source")),
        "trigger_value": raw.get("trigger_value"),
        "trigger_unit": normalized_text(raw.get("trigger_unit")),
        "reason": reason,
        "validation_errors": validation_errors,
        "copy_normalizations": copy_normalizations,
    }
