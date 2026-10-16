"""Dry-run report for local weather notices.

This is a lab tool. It does not fetch live weather, write storage, call FCM,
or run the production dispatcher.

It injects controlled city fixtures into a pure detector and returns a readable
table:

city -> phenomenon -> source -> threshold -> body -> notify yes/no -> reason
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import local_weather_notice_detector as notice_detector
import local_weather_notice_normalizer as notice_normalizer
import local_weather_notification_policy as notification_policy


NOTICE_THRESHOLDS = notice_detector.NOTICE_THRESHOLDS

CITY_FIXTURES: dict[str, dict[str, Any]] = {
    "Pordenone": {
        "label": "caldo + pioggia nello stesso pomeriggio",
        "weather": {
            "temperature": 34.1,
            "feels_like": 35.2,
            "observed_at": "2026-06-27T15:00",
            "hourly_next_12h": [
                {
                    "time": "2026-06-27T15:00",
                    "weathercode": 2,
                    "temperature": 34.5,
                    "precipitation": 0,
                    "rain": 0,
                    "showers": 0,
                    "precipitation_probability": 10,
                    "wind_gusts": 18,
                    "snowfall": 0,
                },
                {
                    "time": "2026-06-27T17:00",
                    "weathercode": 61,
                    "temperature": 32.0,
                    "precipitation": 1.2,
                    "rain": 1.2,
                    "showers": 0,
                    "precipitation_probability": 75,
                    "wind_gusts": 20,
                    "snowfall": 0,
                },
            ],
        },
        "evidence": {
            "rain": "17:00: rain 1.2 mm, probability 75%",
            "heat": "current 34.1 C, feels_like 35.2 C, peak 34.5 C",
        },
        "event_times": {
            "heat": "2026-06-27T15:00",
            "rain": "2026-06-27T17:00",
        },
    },
    "Udine": {
        "label": "giornata senza soglie locali",
        "weather": {
            "temperature": 25.0,
            "feels_like": 25.5,
            "hourly_next_12h": [
                {
                    "time": "2026-06-27T15:00",
                    "weathercode": 2,
                    "temperature": 26.0,
                    "precipitation": 0,
                    "rain": 0,
                    "showers": 0,
                    "precipitation_probability": 15,
                    "wind_gusts": 18,
                    "snowfall": 0,
                }
            ],
        },
        "evidence": {},
    },
    "Trieste": {
        "label": "vento/Bora localizzata",
        "weather": {
            "is_bora": True,
            "temperature": 24.0,
            "feels_like": 24.0,
            "hourly_next_12h": [
                {
                    "time": "2026-06-27T21:00",
                    "weathercode": 2,
                    "temperature": 23.0,
                    "precipitation": 0,
                    "rain": 0,
                    "showers": 0,
                    "precipitation_probability": 0,
                    "wind_gusts": 62,
                    "wind_direction": 55,
                    "snowfall": 0,
                }
            ],
        },
        "evidence": {
            "bora": "21:00: gusts 62 km/h, Bora flag true",
            "wind": "21:00: gusts 62 km/h",
        },
    },
    "Tarvisio": {
        "label": "temporale con grandine + neve",
        "weather": {
            "temperature": 6.0,
            "feels_like": 4.0,
            "hourly_next_12h": [
                {
                    "time": "2026-06-27T18:00",
                    "weathercode": 96,
                    "temperature": 8.0,
                    "precipitation": 0,
                    "rain": 0,
                    "showers": 0,
                    "precipitation_probability": 40,
                    "wind_gusts": 20,
                    "snowfall": 0,
                },
                {
                    "time": "2026-06-27T21:00",
                    "weathercode": 71,
                    "temperature": -1.0,
                    "precipitation": 0,
                    "rain": 0,
                    "showers": 0,
                    "precipitation_probability": 20,
                    "wind_gusts": 12,
                    "snowfall": 0.4,
                },
            ],
        },
        "evidence": {
            "hail": "18:00: weathercode 96",
            "storm": "18:00: weathercode 96",
            "snow": "21:00: weathercode 71, snowfall 0.4",
        },
        "event_times": {
            "hail": "2026-06-27T18:00",
            "snow": "2026-06-27T21:00",
        },
    },
    "Lignano Sabbiadoro": {
        "label": "pioggia sulla costa",
        "weather": {
            "temperature": 24.0,
            "feels_like": 24.5,
            "hourly_next_12h": [
                {
                    "time": "2026-06-27T20:00",
                    "weathercode": 61,
                    "temperature": 23.0,
                    "precipitation": 0.4,
                    "rain": 0.4,
                    "showers": 0,
                    "precipitation_probability": 68,
                    "wind_gusts": 42,
                    "snowfall": 0,
                }
            ],
        },
        "evidence": {
            "rain": "20:00: rain 0.4 mm, probability 68%",
        },
        "event_times": {
            "rain": "2026-06-27T20:00",
        },
    },
    "Cividale del Friuli": {
        "label": "caldo mattina + temporale sera separati",
        "weather": {
            "temperature": 34.0,
            "feels_like": 34.8,
            "observed_at": "2026-06-27T09:00",
            "hourly_next_12h": [
                {
                    "time": "2026-06-27T09:00",
                    "weathercode": 1,
                    "temperature": 34.0,
                    "precipitation": 0,
                    "rain": 0,
                    "showers": 0,
                    "precipitation_probability": 5,
                    "wind_gusts": 12,
                    "snowfall": 0,
                },
                {
                    "time": "2026-06-27T20:00",
                    "weathercode": 95,
                    "temperature": 25.0,
                    "precipitation": 0.2,
                    "rain": 0.2,
                    "showers": 0,
                    "precipitation_probability": 55,
                    "wind_gusts": 28,
                    "snowfall": 0,
                },
            ],
        },
        "evidence": {
            "heat": "09:00: current 34.0 C, feels_like 34.8 C",
            "storm": "20:00: weathercode 95",
        },
        "event_times": {
            "heat": "2026-06-27T09:00",
            "storm": "2026-06-27T20:00",
        },
    },
}


def selected_city_names(cities: list[str] | None = None) -> list[str]:
    if not cities:
        return list(CITY_FIXTURES.keys())
    names: list[str] = []
    for city in cities:
        if city not in CITY_FIXTURES:
            available = ", ".join(CITY_FIXTURES)
            raise ValueError(f"Citta fixture non disponibile: {city}. Disponibili: {available}")
        names.append(city)
    return names


def event_time_for(notice: dict[str, Any], fixture: dict[str, Any]) -> str:
    notice_event_at = str(notice.get("event_at") or "").strip()
    if notice_event_at:
        return notice_event_at[:16]

    kind = str(notice.get("kind") or "")
    category = str(notice.get("category") or "")
    times = fixture.get("event_times") or {}
    explicit = str(times.get(kind) or times.get(category) or "").strip()
    if explicit:
        return explicit

    starts_at = str(notice.get("starts_at") or "").strip()
    if len(starts_at) >= 16:
        return starts_at[:16]
    return starts_at


def evaluate_notice(notice: dict[str, Any], fixture: dict[str, Any], official_alerts: list[dict[str, Any]]) -> dict[str, Any]:
    suppressed = notice_detector.local_notice_suppressed_by_official_alert(notice, official_alerts)
    kind = str(notice.get("kind") or "")
    category = str(notice.get("category") or "")
    normalized = notice_normalizer.normalize_notice_candidate(
        notice,
        expected_city=notice.get("city") or "",
        event_at=event_time_for(notice, fixture),
        threshold=notice.get("threshold") or NOTICE_THRESHOLDS.get(kind) or NOTICE_THRESHOLDS.get(category) or "",
        evidence=notice.get("evidence")
        or fixture.get("evidence", {}).get(kind)
        or fixture.get("evidence", {}).get(category)
        or "",
        official_alert_overlap=suppressed,
    )
    normalized["priority"] = notification_policy.notice_priority(normalized)
    return normalized


def sort_notices_for_display(notices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        notices,
        key=lambda notice: (
            str(notice.get("event_at") or "9999-12-31T23:59"),
            -int(notice.get("priority") or 0),
        ),
    )


def build_report(
    cities: list[str] | None = None,
    official_alerts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    official_alerts = official_alerts or []
    city_names = selected_city_names(cities)
    results: list[dict[str, Any]] = []

    for city in city_names:
        fixture = CITY_FIXTURES[city]
        notices = notice_detector.detect_local_weather_notices(
            city,
            fixture["weather"],
            reminder_window="afternoon",
        )
        if not notices:
            results.append(
                {
                    "city": city,
                    "fixture": fixture["label"],
                    "status": "no_notice",
                    "notices": [],
                    "reason": "nessuna soglia locale superata",
                }
            )
            continue
        evaluated = [
            evaluate_notice(notice, fixture, official_alerts)
            for notice in notices
        ]
        results.append(
            {
                "city": city,
                "fixture": fixture["label"],
                "status": "ready",
                "notices": sort_notices_for_display(notification_policy.apply_notification_policy(evaluated)),
            }
        )

    return {
        "dry_run": True,
        "source": "fixture dichiarate -> local_weather_notice_detector.detect_local_weather_notices",
        "notification_policy": "priority_and_time_window_policy",
        "policy_rules": {
            "priority_order": "hail > storm > ice > snow > bora > wind > rain > heat",
            "min_separation_hours": notification_policy.MIN_SEPARATION_HOURS,
            "heat_block_hours": notification_policy.HEAT_BLOCK_HOURS,
        },
        "side_effects": {
            "network": False,
            "firestore": False,
            "fcm": False,
            "workflow": False,
        },
        "official_alerts_count": len(official_alerts),
        "cities": results,
    }


def format_text_report(report: dict[str, Any]) -> str:
    lines = [
        "Dry-run notifiche meteo locali",
        f"Sorgente: {report['source']}",
        "Politica audit: priorita + distanza temporale, non semplice massimo uno",
        f"Ordine: {report['policy_rules']['priority_order']}",
        (
            "Distanza minima: "
            f"{report['policy_rules']['min_separation_hours']}h; "
            f"caldo trattenuto se evento piu importante entro {report['policy_rules']['heat_block_hours']}h"
        ),
        "Effetti collaterali: rete=no, Firestore=no, FCM=no, workflow=no",
        f"Allerte ufficiali usate come soppressione: {report['official_alerts_count']}",
        "",
    ]
    for city in report["cities"]:
        lines.append(f"{city['city']} - {city['fixture']}")
        if city["status"] == "no_notice":
            lines.append(f"  status: no_notice | notifica: no | motivo: {city['reason']}")
            lines.append("")
            continue
        for notice in city["notices"]:
            notify = "si, consigliata in dry-run" if notice["can_notify"] else "no"
            lines.append(
                f"  {notice['kind']} ({notice['category']}) | status: {notice['status']} | notifica finale: {notify}"
            )
            lines.append(f"    frase: {notice['body']}")
            lines.append(f"    fonte: {notice['source']}")
            lines.append(f"    soglia: {notice['threshold']}")
            lines.append(f"    evidenza: {notice['evidence']}")
            if notice.get("trigger_source"):
                trigger = f"{notice['trigger_source']}={notice.get('trigger_value')}"
                if notice.get("trigger_unit"):
                    trigger += f" {notice['trigger_unit']}"
                lines.append(f"    trigger: {trigger}")
            lines.append(f"    evento: {notice['event_at']}")
            lines.append(f"    priorita: {notice['priority']}")
            lines.append(f"    confidenza: {notice['confidence']}")
            if notice.get("copy_normalizations"):
                lines.append(f"    normalizzazione copy: {', '.join(notice['copy_normalizations'])}")
            if notice.get("validation_errors"):
                lines.append(f"    errori validazione: {', '.join(notice['validation_errors'])}")
            lines.append(f"    motivo dati: {notice['reason']}")
            lines.append(f"    motivo notifica: {notice['notification_reason']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run notifiche meteo locali.")
    parser.add_argument(
        "--city",
        action="append",
        dest="cities",
        help="Limita il report a una citta fixture. Ripetibile.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Formato output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.cities)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text_report(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
