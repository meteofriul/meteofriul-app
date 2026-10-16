"""Audit what the Bulletin UI can safely display from weather payloads.

This is a read-only lab tool. It accepts saved JSON payloads or read-only
bootstrap URLs/cities and produces a field-by-field display audit:

UI field -> payload path -> source -> state -> safe_to_show

It does not write storage, call Firestore, send FCM or trigger workflows.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


DEFAULT_BOOTSTRAP_BASE_URL = "http://127.0.0.1:5173/api/weather/bootstrap"
DAY_IDS = ["today", "tomorrow", "afterTomorrow", "plus3", "plus4"]
AREA_IDS = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
FASCE_IDS = ["F1", "F2", "F3", "F4"]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def add_days_to_date_key(value: str, days_to_add: int = 1) -> str:
    if not value:
        return ""
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return ""
    return (parsed + timedelta(days=days_to_add)).isoformat()


def is_object(value: Any) -> bool:
    return isinstance(value, dict)


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_token(value: Any) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in str(value or "")).strip("_")


def load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_json_url(url: str) -> Any:
    with urlopen(url, timeout=15) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset))


def build_city_url(base_url: str, city: str) -> str:
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode({'city': city})}"


def iter_payload_objects(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if is_object(item)]
    if not is_object(raw):
        raise TypeError("Il JSON deve contenere un oggetto payload o una lista di payload.")
    for key in ("payloads", "items", "cities"):
        if isinstance(raw.get(key), list):
            return [item for item in raw[key] if is_object(item)]
    return [raw]


def forecast_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("forecast") if is_object(payload.get("forecast")) else {}


def get_official_forecasts(forecast: dict[str, Any], language: str = "it") -> list[dict[str, Any]]:
    official = forecast.get("official") if is_object(forecast.get("official")) else {}
    localized = official.get(language) if is_object(official.get(language)) else {}
    italian = official.get("it") if is_object(official.get("it")) else {}
    localized_forecasts = as_list(localized.get("forecasts"))
    if localized_forecasts:
        return [item for item in localized_forecasts if is_object(item)]
    return [item for item in as_list(italian.get("forecasts")) if is_object(item)]


def get_calendar_official_forecasts(forecast: dict[str, Any], fallback_forecasts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    official = forecast.get("official") if is_object(forecast.get("official")) else {}
    italian = official.get("it") if is_object(official.get("it")) else {}
    italian_forecasts = [item for item in as_list(italian.get("forecasts")) if is_object(item)]
    return italian_forecasts or fallback_forecasts


def forecasts_by_date(forecasts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        clean_text(day.get("date")): day
        for day in forecasts
        if clean_text(day.get("date"))
    }


def get_model_forecast_days(forecast: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("forecast", "daily", "days"):
        days = as_list(forecast.get(key))
        if days:
            return [item for item in days if is_object(item)]
    return []


def get_osmer_structured(forecast: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("osmer_structured", "osmerStructured"):
        if is_object(forecast.get(key)):
            return forecast[key]
    return None


def get_structured_days(structured: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [day for day in as_list(structured.get("days") if structured else []) if is_object(day)]


def build_forecast_date_slots(official_days: list[dict[str, Any]], structured_days: list[dict[str, Any]]) -> list[str]:
    last_date = ""
    slots: list[str] = []
    for index, _day_id in enumerate(DAY_IDS):
        explicit_date = clean_text(
            (official_days[index].get("date") if index < len(official_days) else "")
            or (structured_days[index].get("valid_date") if index < len(structured_days) else "")
        )
        if explicit_date:
            last_date = explicit_date
            slots.append(explicit_date)
            continue
        if last_date:
            last_date = add_days_to_date_key(last_date)
            slots.append(last_date)
            continue
        slots.append("")
    return slots


def get_structured_day(model_day: dict[str, Any], forecast_date: str, structured: dict[str, Any] | None) -> dict[str, Any] | None:
    for key in ("osmer_structured_day", "osmerStructuredDay", "structured_osmer_day"):
        if is_object(model_day.get(key)) and is_object(model_day[key].get("areas9")):
            return model_day[key]
    for day in as_list(structured.get("days") if structured else []):
        if is_object(day) and clean_text(day.get("valid_date")) == forecast_date:
            return day
    return None


def source_kind(value: Any) -> str:
    token = normalize_token(value)
    if token == "structured_xml":
        return "structured_xml"
    if token == "official_projected":
        return "official_projected"
    return token or "unknown"


def day_source_kind(day: dict[str, Any] | None, structured: dict[str, Any] | None) -> str:
    if not day:
        return "unavailable"
    explicit = source_kind(day.get("source_kind") or day.get("sourceKind"))
    if explicit != "unknown":
        return explicit
    return source_kind((structured or {}).get("source_kind") or (structured or {}).get("fonte"))


def missing_keys(source: dict[str, Any] | None, required: list[str]) -> list[str]:
    return [key for key in required if not source or not source.get(key)]


def structured_state(day: dict[str, Any] | None, structured: dict[str, Any] | None) -> dict[str, Any]:
    missing_areas = missing_keys(day.get("areas9") if day else None, AREA_IDS)
    missing_fasce = missing_keys(day.get("fasce4") if day else None, FASCE_IDS)
    stale = bool((structured or {}).get("is_stale") or (structured or {}).get("isStale"))
    status = normalize_token((structured or {}).get("source_status") or (structured or {}).get("sourceStatus"))
    unavailable = "unavailable" in status or "failed" in status or "404" in status
    kind = day_source_kind(day, structured)

    if not day:
        state = "unavailable"
    elif stale or unavailable:
        state = "stale"
    elif missing_areas or missing_fasce:
        state = "partial"
    else:
        state = "ready"

    can_render_native_map = bool(day and not missing_areas and state != "stale" and kind == "structured_xml")
    return {
        "state": state,
        "source_kind": kind,
        "area_count": len(AREA_IDS) - len(missing_areas),
        "fasce_count": len(FASCE_IDS) - len(missing_fasce),
        "missing_areas": missing_areas,
        "missing_fasce": missing_fasce,
        "can_render_native_map": can_render_native_map,
        "can_use_full_bulletin": state == "ready" and kind == "structured_xml",
    }


def official_text(day: dict[str, Any], model_day: dict[str, Any]) -> str:
    return clean_text(
        day.get("text")
        or day.get("official_text")
        or model_day.get("official_text")
        or model_day.get("text")
        or model_day.get("displayText")
        or ""
    )


def bulletin_updated_value(forecast: dict[str, Any], structured: dict[str, Any] | None) -> str:
    official = forecast.get("official") if is_object(forecast.get("official")) else {}
    italian = official.get("it") if is_object(official.get("it")) else {}
    return clean_text(
        italian.get("updated_at")
        or italian.get("updatedAt")
        or (structured or {}).get("data_emissione")
        or (structured or {}).get("source_date")
        or ""
    )


def add_row(rows: list[dict[str, Any]], **row: Any) -> None:
    defaults = {
        "ui_field": "",
        "payload_path": "",
        "source": "",
        "state": "",
        "safe_to_show": False,
        "reason": "",
        "value": "",
    }
    defaults.update(row)
    rows.append(defaults)


def classify_official_alerts(payload: dict[str, Any]) -> dict[str, Any]:
    alerts_payload = payload.get("officialAlerts") or payload.get("official_alerts") or {}
    if not is_object(alerts_payload):
        return {
            "state": "unavailable",
            "safe_to_show": False,
            "reason": "payload official_alerts assente",
            "value": "",
        }
    cache = alerts_payload.get("cache") if is_object(alerts_payload.get("cache")) else {}
    cache_status = normalize_token(cache.get("status"))
    source_mode = normalize_token(alerts_payload.get("source_mode"))
    error = normalize_token(alerts_payload.get("error"))
    active_alerts = [
        alert
        for alert in as_list(alerts_payload.get("alerts"))
        if is_object(alert) and normalize_token(alert.get("level")) not in ("", "verde", "green")
    ]

    if cache_status in ("stale", "unavailable") or error:
        return {
            "state": cache_status or "unavailable",
            "safe_to_show": False,
            "reason": "allerta non mostrabile: fonte stale/unavailable/error",
            "value": "",
        }
    if active_alerts:
        levels = ", ".join(clean_text(alert.get("level")) for alert in active_alerts)
        return {
            "state": "active",
            "safe_to_show": True,
            "reason": "allerta ufficiale attiva non verde",
            "value": levels,
        }
    if "dpc" in source_mode and "unverified" in source_mode:
        return {
            "state": "diagnostic",
            "safe_to_show": False,
            "reason": "DPC diagnostico: non verde regionale verificato",
            "value": "",
        }
    return {
        "state": "inactive_or_empty",
        "safe_to_show": False,
        "reason": "nessuna allerta attiva da mostrare",
        "value": "",
    }


def audit_bulletin_payload(payload: dict[str, Any], language: str = "it") -> dict[str, Any]:
    forecast = forecast_payload(payload)
    official_days = get_official_forecasts(forecast, language)
    calendar_official_days = get_calendar_official_forecasts(forecast, official_days)
    official_days_by_date = forecasts_by_date(official_days)
    model_days = get_model_forecast_days(forecast)
    structured = get_osmer_structured(forecast)
    rows: list[dict[str, Any]] = []

    city = clean_text(payload.get("city"))
    source_status = clean_text((structured or {}).get("source_status") or (structured or {}).get("sourceStatus"))
    structured_days = get_structured_days(structured)
    source_day_count = max(len(calendar_official_days), len(structured_days))
    forecast_date_slots = build_forecast_date_slots(calendar_official_days, structured_days)
    max_days = len(DAY_IDS) if source_day_count else 1

    add_row(
        rows,
        ui_field="source.title",
        payload_path="static copy",
        source="UI copy",
        state="ready",
        safe_to_show=True,
        reason="etichetta fonte statica consentita",
        value="OSMER ARPA FVG",
    )
    add_row(
        rows,
        ui_field="source.updatedLabel",
        payload_path="forecast.official.it.updated_at | forecast.official.it.updatedAt | osmer_structured.data_emissione | osmer_structured.source_date",
        source="OSMER official text / structured XML",
        state="ready" if official_days or structured else "unavailable",
        safe_to_show=bool(official_days or structured),
        reason="stessa priorita' della UI per evitare discrepanze tra audit e schermo",
        value=bulletin_updated_value(forecast, structured),
    )
    add_row(
        rows,
        ui_field="osmer_structured.snapshot",
        payload_path="forecast.osmer_structured",
        source="OSMER XML",
        state="ready" if structured_days else "unavailable",
        safe_to_show=bool(structured_days),
        reason=f"source_status={source_status or 'missing'}; days={len(structured_days)}",
        value=f"{len(structured_days)} giorni",
    )

    alert_state = classify_official_alerts(payload)
    add_row(
        rows,
        ui_field="alert.banner",
        payload_path="official_alerts",
        source="Protezione Civile FVG / override",
        state=alert_state["state"],
        safe_to_show=alert_state["safe_to_show"],
        reason=alert_state["reason"],
        value=alert_state["value"],
    )

    for index in range(max_days):
        day_id = DAY_IDS[index] if index < len(DAY_IDS) else f"extra{index + 1}"
        calendar_official_day = calendar_official_days[index] if index < len(calendar_official_days) else {}
        indexed_official_day = official_days[index] if index < len(official_days) else {}
        model_day = model_days[index] if index < len(model_days) else {}
        indexed_structured_day = structured_days[index] if index < len(structured_days) else {}
        forecast_date = clean_text(
            calendar_official_day.get("date")
            or indexed_structured_day.get("valid_date")
            or forecast_date_slots[index]
            or (model_day.get("date") if not source_day_count else "")
        )
        official_day_by_date = official_days_by_date.get(forecast_date, {})
        official_day = (
            indexed_official_day
            if indexed_official_day
            else official_day_by_date
            if clean_text(official_day_by_date.get("date")) == forecast_date
            else calendar_official_day
        )
        is_pending_bulletin = bool(source_day_count and index >= source_day_count and forecast_date)
        display_model_day = {} if is_pending_bulletin else model_day
        structured_day = None if is_pending_bulletin else get_structured_day(display_model_day, forecast_date, structured)
        contract = structured_state(structured_day, structured)
        text = "Bollettino non ancora emesso." if is_pending_bulletin else official_text(official_day, display_model_day)

        add_row(
            rows,
            ui_field=f"days[{day_id}].tabLabel",
            payload_path=f"forecast.official.{language}.forecasts[{index}].date_label | forecast.osmer_structured.days[{index}].valid_date",
            source="OSMER calendar",
            state="ready" if forecast_date or official_day.get("date_label") else "fallback_label",
            safe_to_show=bool(forecast_date or official_day.get("date_label")),
            reason="tab giorno mostrabile se collegato a data o date_label ufficiale",
            value=clean_text(official_day.get("date_label") or forecast_date),
        )
        add_row(
            rows,
            ui_field=f"days[{day_id}].officialText",
            payload_path="UI copy" if is_pending_bulletin else f"forecast.official.{language}.forecasts[{index}].text",
            source="UI copy" if is_pending_bulletin else "OSMER official text",
            state="pending" if is_pending_bulletin else "ready" if text else "unavailable",
            safe_to_show=bool(text),
            reason=(
                "quinto giorno riservato al calendario OSMER: bollettino non ancora emesso"
                if is_pending_bulletin
                else "testo mostrabile solo se ufficiale/normalizzato"
            ),
            value=text[:140],
        )
        add_row(
            rows,
            ui_field=f"days[{day_id}].nativeMap",
            payload_path=f"forecast.osmer_structured.days[valid_date={forecast_date}].areas9",
            source="OSMER structured XML",
            state="pending" if is_pending_bulletin else contract["state"],
            safe_to_show=contract["can_render_native_map"],
            reason=(
                "bollettino non ancora emesso"
                if is_pending_bulletin
                else
                "mappa nativa solo con structured_xml, A1-A9 complete, non stale"
                if contract["can_render_native_map"]
                else f"source_kind={contract['source_kind']}; aree={contract['area_count']}/9; fasce={contract['fasce_count']}/4"
            ),
            value=f"{contract['area_count']}/9 aree",
        )
        add_row(
            rows,
            ui_field=f"days[{day_id}].reliability",
            payload_path=f"forecast.osmer_structured.days[valid_date={forecast_date}].areas9.*.attendibilita",
            source="OSMER structured XML",
            state="pending" if is_pending_bulletin else "ready" if contract["can_render_native_map"] else contract["state"],
            safe_to_show=contract["can_render_native_map"],
            reason=(
                "bollettino non ancora emesso"
                if is_pending_bulletin
                else "attendibilita mostrabile solo se la mappa nativa del giorno e' usabile"
            ),
            value="",
        )

    safe_rows = sum(1 for row in rows if row["safe_to_show"])
    unsafe_rows = len(rows) - safe_rows
    return {
        "city": city,
        "language": language,
        "summary": {
            "rows": len(rows),
            "safe_to_show": safe_rows,
            "not_safe_to_show": unsafe_rows,
            "official_text_days": sum(1 for row in rows if row["ui_field"].endswith(".officialText") and row["source"] == "OSMER official text" and row["safe_to_show"]),
            "pending_days": sum(1 for row in rows if row["ui_field"].endswith(".officialText") and row["state"] == "pending"),
            "native_map_days": sum(1 for row in rows if row["ui_field"].endswith(".nativeMap") and row["safe_to_show"]),
        },
        "rows": rows,
    }


def build_report_from_payloads(payloads: list[dict[str, Any]], language: str = "it") -> dict[str, Any]:
    audits = [audit_bulletin_payload(payload, language=language) for payload in payloads]
    return {
        "dry_run": True,
        "source": "saved/read-only payload -> bulletin display field audit",
        "side_effects": {
            "firestore": False,
            "fcm": False,
            "workflow": False,
            "writes": False,
        },
        "language": language,
        "payloads": audits,
    }


def load_payloads_from_inputs(
    inputs: list[Path],
    urls: list[str],
    cities: list[str] | None = None,
    base_url: str = DEFAULT_BOOTSTRAP_BASE_URL,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in inputs:
        payloads.extend(iter_payload_objects(load_json_file(path)))
    for url in urls:
        payloads.extend(iter_payload_objects(load_json_url(url)))
    for city in cities or []:
        payloads.extend(iter_payload_objects(load_json_url(build_city_url(base_url, city))))
    return payloads


def format_text_report(report: dict[str, Any]) -> str:
    lines = [
        "Audit visualizzazione Bollettino",
        f"Sorgente: {report['source']}",
        "Effetti collaterali: Firestore=no, FCM=no, workflow=no, writes=no",
        f"Lingua: {report['language']}",
        "",
    ]
    for audit in report["payloads"]:
        summary = audit["summary"]
        lines.append(
            f"{audit['city'] or '(city mancante)'} | righe={summary['rows']} | "
            f"show={summary['safe_to_show']} | no-show={summary['not_safe_to_show']} | "
            f"testi={summary['official_text_days']} | mappe={summary['native_map_days']}"
        )
        lines.append("| Campo UI | Stato | Show | Fonte | Path | Motivo |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in audit["rows"]:
            show = "si" if row["safe_to_show"] else "no"
            lines.append(
                "| "
                + " | ".join(
                    clean_text(value).replace("|", "/")
                    for value in (
                        row["ui_field"],
                        row["state"],
                        show,
                        row["source"],
                        row["payload_path"],
                        row["reason"],
                    )
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit read-only dei campi UI del Bollettino.")
    parser.add_argument("--input", action="append", default=[], type=Path, help="File JSON payload. Ripetibile.")
    parser.add_argument("--url", action="append", default=[], help="URL JSON read-only. Ripetibile.")
    parser.add_argument("--city", action="append", default=[], help="Citta da leggere dal bootstrap locale. Ripetibile.")
    parser.add_argument("--base-url", default=DEFAULT_BOOTSTRAP_BASE_URL, help="Base URL per --city.")
    parser.add_argument("--language", choices=("it", "fur"), default="it", help="Lingua audit.")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Formato output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input and not args.url and not args.city:
        raise SystemExit("Serve almeno --input, --url o --city.")
    report = build_report_from_payloads(
        load_payloads_from_inputs(args.input, args.url, args.city, args.base_url),
        language=args.language,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text_report(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
