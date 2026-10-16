"""Dry-run local weather notices from saved or read-only real payloads.

This is a lab tool. It can read JSON files or GET read-only URLs, then runs:

payload -> adapter -> detector -> normalizer -> notification policy

It does not write storage, call Firestore, send FCM or trigger workflows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import local_weather_notice_detector as notice_detector
import local_weather_notice_normalizer as notice_normalizer
import local_weather_notification_policy as notification_policy
import local_weather_payload_adapter as payload_adapter


DEFAULT_BOOTSTRAP_BASE_URL = "http://127.0.0.1:5173/api/weather/bootstrap"


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


def sort_notices_for_display(notices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        notices,
        key=lambda notice: (
            str(notice.get("event_at") or "9999-12-31T23:59"),
            -int(notice.get("priority") or 0),
        ),
    )


def evaluate_notice(
    notice: dict[str, Any],
    official_alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    suppressed = notice_detector.local_notice_suppressed_by_official_alert(notice, official_alerts)
    normalized = notice_normalizer.normalize_notice_candidate(
        notice,
        expected_city=notice.get("city") or "",
        event_at=notice.get("event_at") or notice.get("starts_at") or "",
        threshold=notice.get("threshold") or "",
        evidence=notice.get("evidence") or "",
        official_alert_overlap=suppressed,
    )
    normalized["priority"] = notification_policy.notice_priority(normalized)
    return normalized


def evaluate_adapted_payload(adapted: dict[str, Any]) -> dict[str, Any]:
    city = str(adapted.get("city") or "").strip()
    weather = adapted.get("weather") or {}
    official_alerts = adapted.get("official_alerts") or []

    raw_notices = notice_detector.detect_local_weather_notices(
        city,
        weather,
        reminder_window="read_only_payload",
    )
    evaluated = [
        evaluate_notice(notice, official_alerts)
        for notice in raw_notices
    ]
    final_notices = sort_notices_for_display(notification_policy.apply_notification_policy(evaluated))

    status = "ready" if final_notices else "no_notice"
    reason = "" if final_notices else "nessuna soglia locale numerica superata"
    if not city:
        status = "invalid_payload"
        reason = "payload senza city"

    return {
        "city": city,
        "status": status,
        "reason": reason,
        "source_shape": adapted.get("source_shape"),
        "source_status": adapted.get("source_status"),
        "numeric_snapshot": adapted.get("numeric_snapshot") or {},
        "data_gaps": adapted.get("data_gaps") or [],
        "text_signals": adapted.get("text_signals") or [],
        "notices": final_notices,
    }


def build_report_from_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    adapted_payloads = [payload_adapter.adapt_weather_payload(payload) for payload in payloads]
    evaluated_payloads = [evaluate_adapted_payload(adapted) for adapted in adapted_payloads]
    notices = [
        notice
        for payload in evaluated_payloads
        for notice in payload.get("notices", [])
    ]
    return {
        "dry_run": True,
        "source": "saved/read-only payload -> adapter -> detector -> normalizer -> policy",
        "side_effects": {
            "firestore": False,
            "fcm": False,
            "workflow": False,
            "writes": False,
        },
        "policy_rules": {
            "priority_order": "hail > storm > ice > snow > bora > wind > rain > heat",
            "min_separation_hours": notification_policy.MIN_SEPARATION_HOURS,
            "heat_block_hours": notification_policy.HEAT_BLOCK_HOURS,
        },
        "summary": {
            "payloads": len(evaluated_payloads),
            "ready_payloads": sum(1 for item in evaluated_payloads if item.get("status") == "ready"),
            "no_notice_payloads": sum(1 for item in evaluated_payloads if item.get("status") == "no_notice"),
            "candidate_notices": len(notices),
            "dry_run_notifiable": sum(1 for notice in notices if notice.get("can_notify")),
            "payloads_with_text_signals": sum(1 for item in evaluated_payloads if item.get("text_signals")),
            "payloads_with_data_gaps": sum(1 for item in evaluated_payloads if item.get("data_gaps")),
        },
        "payloads": evaluated_payloads,
    }


def load_payloads_from_inputs(
    inputs: list[Path],
    urls: list[str],
    cities: list[str] | None = None,
    base_url: str = DEFAULT_BOOTSTRAP_BASE_URL,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in inputs:
        payloads.extend(payload_adapter.iter_payload_objects(load_json_file(path)))
    for url in urls:
        payloads.extend(payload_adapter.iter_payload_objects(load_json_url(url)))
    for city in cities or []:
        payloads.extend(payload_adapter.iter_payload_objects(load_json_url(build_city_url(base_url, city))))
    return payloads


def format_text_report(report: dict[str, Any]) -> str:
    lines = [
        "Dry-run payload reali notifiche meteo locali",
        f"Sorgente: {report['source']}",
        "Effetti collaterali: Firestore=no, FCM=no, workflow=no, writes=no",
        f"Ordine: {report['policy_rules']['priority_order']}",
        (
            "Sintesi: "
            f"payload={report['summary']['payloads']}, "
            f"con candidati={report['summary']['ready_payloads']}, "
            f"senza notice={report['summary']['no_notice_payloads']}, "
            f"notice={report['summary']['candidate_notices']}, "
            f"notificabili dry-run={report['summary']['dry_run_notifiable']}"
        ),
        "",
    ]
    for item in report["payloads"]:
        lines.append(f"{item['city'] or '(city mancante)'} | shape={item['source_shape']} | status={item['status']}")
        numeric = item.get("numeric_snapshot") or {}
        if numeric:
            lines.append(
                "  numeri locali: "
                f"temp={numeric.get('temperature')} C, "
                f"percepita={numeric.get('feels_like')} C, "
                f"picco={numeric.get('peak_temperature')} C"
                + (f" @ {numeric.get('peak_temperature_time')}" if numeric.get("peak_temperature_time") else "")
                + f", ore={numeric.get('hourly_count')}"
            )
        if item.get("reason"):
            lines.append(f"  motivo: {item['reason']}")
        if item.get("data_gaps"):
            lines.append(f"  gap dati: {', '.join(item['data_gaps'])}")
        if item.get("text_signals"):
            signal_parts = [
                f"{signal['kind']}({signal['count']})"
                for signal in item["text_signals"]
            ]
            lines.append(
                "  segnali testuali regionali non usati per push: "
                + ", ".join(signal_parts)
            )
        if not item.get("notices"):
            lines.append("  notifiche locali: nessuna")
            lines.append("")
            continue

        for notice in item["notices"]:
            notify = "si, consigliata in dry-run" if notice["can_notify"] else "no"
            lines.append(
                f"  {notice['kind']} ({notice['category']}) | status={notice['status']} | notifica={notify}"
            )
            lines.append(f"    frase: {notice['body']}")
            lines.append(f"    soglia: {notice['threshold']}")
            lines.append(f"    evidenza: {notice['evidence']}")
            if notice.get("trigger_source"):
                trigger = f"{notice['trigger_source']}={notice.get('trigger_value')}"
                if notice.get("trigger_unit"):
                    trigger += f" {notice['trigger_unit']}"
                lines.append(f"    trigger: {trigger}")
            lines.append(f"    evento: {notice['event_at']}")
            lines.append(f"    confidenza: {notice['confidence']}")
            lines.append(f"    motivo notifica: {notice['notification_reason']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run notifiche locali da payload reali/salvati.")
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        type=Path,
        help="File JSON payload o lista payload. Ripetibile.",
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="URL JSON da leggere in sola lettura. Ripetibile.",
    )
    parser.add_argument(
        "--city",
        action="append",
        default=[],
        help="Citta da leggere dal bootstrap locale/read-only. Ripetibile.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BOOTSTRAP_BASE_URL,
        help="Base URL per --city. Default: bootstrap locale 127.0.0.1:5173.",
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
    if not args.input and not args.url and not args.city:
        raise SystemExit("Serve almeno --input, --url o --city.")
    report = build_report_from_payloads(
        load_payloads_from_inputs(args.input, args.url, args.city, args.base_url)
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text_report(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
