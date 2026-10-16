"""Read-only status report for saved data-pipeline audits.

This laboratory command reads the local audit logs for:
- Protezione Civile FVG official alerts;
- OSMER structured bulletin.

It does not fetch network sources, call the backend, write Firestore, send FCM
or touch the UI. It only summarizes already saved audit evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import official_alert_notification_policy as notification_policy
import official_alert_polling_policy as polling_policy


UI3_ROOT = Path(__file__).resolve().parents[1]
AUDIT_ROOT = UI3_ROOT / "backend_dryrun_staging" / "audit_log"
OFFICIAL_ALERT_LOG = AUDIT_ROOT / "official-alerts.audit.jsonl"
OSMER_AUDIT_DIR = AUDIT_ROOT / "osmer"
OSMER_LOG = OSMER_AUDIT_DIR / "osmer-bulletin.audit.jsonl"
OSMER_INVALIDATED = OSMER_AUDIT_DIR / "invalidated_audits.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                rows.append(
                    {
                        "audit_id": f"{path.name}:{line_number}",
                        "ok": False,
                        "created_at": "",
                        "error": f"json_decode_error: {exc}",
                    }
                )
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def read_invalidated_osmer(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    invalidated: dict[str, dict[str, Any]] = {}
    for item in data.get("invalidated", []):
        if not isinstance(item, dict):
            continue
        audit_id = str(item.get("audit_id") or "")
        if audit_id:
            invalidated[audit_id] = item
    return invalidated


def read_json_file(path_value: Any) -> dict[str, Any]:
    path_text = str(path_value or "").strip()
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def is_live_official_alert(entry: dict[str, Any]) -> bool:
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    return bool(source.get("raw_snapshot_file"))


def is_sample_official_alert(entry: dict[str, Any]) -> bool:
    return not is_live_official_alert(entry)


def is_live_osmer(entry: dict[str, Any]) -> bool:
    discovery = entry.get("discovery") if isinstance(entry.get("discovery"), dict) else {}
    observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
    if discovery.get("mode") == "sample":
        return False
    if observation.get("source_status") == "local_fixture":
        return False
    for source in entry.get("sources") or []:
        if isinstance(source, dict) and source.get("status") == "sample":
            return False
    return True


def is_sample_osmer(entry: dict[str, Any]) -> bool:
    return not is_live_osmer(entry)


def filter_scope(
    rows: list[dict[str, Any]],
    scope: str,
    is_live,
    invalidated_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    invalidated_ids = invalidated_ids or set()
    filtered: list[dict[str, Any]] = []
    for row in rows:
        audit_id = str(row.get("audit_id") or "")
        if audit_id in invalidated_ids:
            continue
        if row.get("ok") is False:
            continue
        live = bool(is_live(row))
        if scope == "live" and not live:
            continue
        if scope == "sample" and live:
            continue
        filtered.append(row)
    return filtered


def latest_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return sorted(rows, key=lambda item: str(item.get("created_at") or ""))[-1]


def source_status_label(entry: dict[str, Any] | None, live_fn) -> str:
    if not entry:
        return "missing"
    return "live" if live_fn(entry) else "sample"


def summarize_official_alert(entry: dict[str, Any] | None) -> dict[str, Any]:
    if not entry:
        return {"available": False, "summary": "nessun audit allerta disponibile"}

    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    parser = entry.get("parser") if isinstance(entry.get("parser"), dict) else {}
    state = entry.get("state") if isinstance(entry.get("state"), dict) else {}
    transition = entry.get("transition") if isinstance(entry.get("transition"), dict) else {}
    user_effect = entry.get("user_effect") if isinstance(entry.get("user_effect"), dict) else {}
    reading = entry.get("reading") if isinstance(entry.get("reading"), dict) else {}

    home = user_effect.get("home") if isinstance(user_effect.get("home"), dict) else {}
    bulletin = (
        user_effect.get("bulletin") if isinstance(user_effect.get("bulletin"), dict) else {}
    )
    notification = (
        user_effect.get("notification")
        if isinstance(user_effect.get("notification"), dict)
        else {}
    )

    return {
        "available": True,
        "audit_id": entry.get("audit_id", ""),
        "created_at": entry.get("created_at", ""),
        "contract_now": entry.get("contract_now", "") or entry.get("created_at", ""),
        "previous_state_file": entry.get("previous_state_file", ""),
        "payload_file": (entry.get("payload") or {}).get("file", "")
        if isinstance(entry.get("payload"), dict)
        else "",
        "scope": source_status_label(entry, is_live_official_alert),
        "source_mode": source.get("mode", ""),
        "source_parser": source.get("parser", ""),
        "source_url": source.get("url", ""),
        "raw_sha256": source.get("raw_sha256", ""),
        "source_reachable": bool(source.get("raw_sha256")) and state.get("state") != "unavailable",
        "parser_status": parser.get("status", ""),
        "alerts_found": parser.get("alerts_found", 0),
        "alert_titles": parser.get("titles", []),
        "state": state.get("state", ""),
        "confidence": state.get("confidence", ""),
        "expires_at": state.get("expires_at", ""),
        "can_notify": bool(state.get("can_notify")),
        "can_clear_previous_alert": bool(state.get("can_clear_previous_alert")),
        "transition_actions": transition.get("actions", []),
        "home": {
            "show_alert": bool(home.get("show_alert")),
            "label": home.get("label", ""),
            "reading": reading.get("home", ""),
        },
        "bulletin": {
            "show_notice": bool(bulletin.get("show_notice")),
            "notice": bulletin.get("notice", ""),
            "reading": reading.get("bollettino", ""),
        },
        "notification": {
            "can_notify": bool(notification.get("can_notify")),
            "effect": notification.get("effect", "") or reading.get("notifiche", ""),
        },
        "previous_state_effect": reading.get("stato_precedente", ""),
    }


def first_payload_alert(payload: dict[str, Any]) -> dict[str, Any]:
    alerts = payload.get("alerts")
    if isinstance(alerts, list) and alerts and isinstance(alerts[0], dict):
        alert = dict(alerts[0])
        if payload.get("expires_at") and not alert.get("expires_at"):
            alert["expires_at"] = payload["expires_at"]
        if alert.get("valid_to") and not alert.get("expires_at"):
            alert["expires_at"] = alert["valid_to"]
        return alert
    return {}


def build_final_alert_state_from_audit(entry: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {}
    state = entry.get("state") if isinstance(entry.get("state"), dict) else {}
    payload_info = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    payload = read_json_file(payload_info.get("file"))
    alert = first_payload_alert(payload)
    if state.get("alert_signature") and not alert.get("signature"):
        alert["signature"] = state["alert_signature"]
    return {
        "state": state.get("state", ""),
        "source_authority": state.get("source_authority", ""),
        "alert": alert,
    }


def build_notification_summary(
    entry: dict[str, Any] | None,
    alert_summary: dict[str, Any],
) -> dict[str, Any]:
    if not alert_summary.get("available"):
        return notification_policy.decide_official_alert_notification(
            {},
            {"state": "unavailable", "source_authority": ""},
        )

    previous_state = read_json_file(alert_summary.get("previous_state_file"))
    final_state = build_final_alert_state_from_audit(entry)
    if not final_state.get("state"):
        final_state = {
            "state": alert_summary.get("state", ""),
            "source_authority": "regional_fvg_primary",
            "alert": {},
        }
    return notification_policy.decide_official_alert_notification(previous_state, final_state)


def is_fvg_source_failure(entry: dict[str, Any]) -> bool:
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    parser = entry.get("parser") if isinstance(entry.get("parser"), dict) else {}
    state = entry.get("state") if isinstance(entry.get("state"), dict) else {}
    state_id = str(state.get("state") or "").strip()
    parser_status = str(parser.get("status") or "").strip()
    failure_statuses = {
        "timeout",
        "http_error",
        "network_error",
        "source_unavailable",
        "unavailable",
    }
    if state_id == "unavailable":
        return True
    if parser_status in failure_statuses:
        return True
    return bool(source.get("fallback_error")) and not bool(source.get("raw_sha256"))


def count_consecutive_fvg_failures(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in sorted(rows, key=lambda item: str(item.get("created_at") or ""), reverse=True):
        if not is_fvg_source_failure(row):
            break
        count += 1
    return count


def build_polling_summary(
    alert: dict[str, Any],
    official_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    if not alert.get("available"):
        failures = max(1, count_consecutive_fvg_failures(official_candidates))
        return polling_policy.plan_official_alert_polling(
            "unavailable",
            primary_reachable=False,
            consecutive_failures=failures,
            now=None,
        )

    state = str(alert.get("state") or "").strip()
    primary_reachable = bool(alert.get("source_reachable"))
    failures = 0 if primary_reachable else max(1, count_consecutive_fvg_failures(official_candidates))
    return polling_policy.plan_official_alert_polling(
        {
            "state": state,
            "alert": {"expires_at": alert.get("expires_at", "")},
        },
        primary_reachable=primary_reachable,
        consecutive_failures=failures,
        now=alert.get("contract_now") or alert.get("created_at"),
    )


def summarize_osmer(entry: dict[str, Any] | None) -> dict[str, Any]:
    if not entry:
        return {"available": False, "summary": "nessun audit OSMER disponibile"}

    observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
    reading = entry.get("reading") if isinstance(entry.get("reading"), dict) else {}
    state = entry.get("state") if isinstance(entry.get("state"), dict) else {}
    transition = entry.get("transition") if isinstance(entry.get("transition"), dict) else {}
    discovery = entry.get("discovery") if isinstance(entry.get("discovery"), dict) else {}

    fetched_sources: list[dict[str, Any]] = []
    missing_sources: list[dict[str, Any]] = []
    sample_sources: list[dict[str, Any]] = []
    for source in entry.get("sources") or []:
        if not isinstance(source, dict):
            continue
        item = {
            "source_id": source.get("source_id", ""),
            "status": source.get("status", ""),
            "raw_sha256": source.get("raw_sha256", ""),
            "url": source.get("url", ""),
        }
        if source.get("status") == "fetched":
            fetched_sources.append(item)
        elif source.get("status") == "sample":
            sample_sources.append(item)
        else:
            missing_sources.append(item)

    return {
        "available": True,
        "audit_id": entry.get("audit_id", ""),
        "created_at": entry.get("created_at", ""),
        "scope": source_status_label(entry, is_live_osmer),
        "requested_date": entry.get("requested_date", ""),
        "language": entry.get("language", ""),
        "source_kind": observation.get("source_kind", ""),
        "source_status": observation.get("source_status", ""),
        "source_url": observation.get("source_url", ""),
        "valid_dates": observation.get("valid_dates", []),
        "days_count": observation.get("days_count", reading.get("days_count", 0)),
        "state": state.get("state", reading.get("state", "")),
        "can_use_as_current": bool(
            state.get("can_use_as_current", reading.get("can_use_as_current"))
        ),
        "can_render_native_map": bool(
            state.get("can_render_native_map", reading.get("can_render_native_map"))
        ),
        "warnings": state.get("warnings", reading.get("warnings", [])),
        "transition_actions": transition.get("actions", reading.get("actions", [])),
        "source_mix": bool(transition.get("source_mix")),
        "fetched_sources": fetched_sources,
        "missing_sources": missing_sources,
        "sample_sources": sample_sources,
        "discovery": discovery,
    }


def build_decision(
    alert: dict[str, Any],
    osmer: dict[str, Any],
    notification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    alert_state = alert.get("state", "") if alert.get("available") else ""
    osmer_state = osmer.get("state", "") if osmer.get("available") else ""

    can_show_bulletin = bool(osmer.get("can_use_as_current"))
    can_render_map = bool(osmer.get("can_render_native_map"))
    can_clear_previous_alert = bool(alert.get("can_clear_previous_alert"))
    notification_dry_run_allowed = bool(
        notification.get("can_notify") if isinstance(notification, dict) else alert.get("can_notify")
    )

    notes: list[str] = []
    if notification_dry_run_allowed:
        notes.append("notifica ammessa solo dal contratto dry-run; invio live non collegato")
    else:
        notes.append("nessuna notifica da inviare secondo il contratto")
    if alert_state == "inactive_confirmed":
        notes.append("eventuale vecchia allerta puo essere spenta")
    elif alert_state:
        notes.append("eventuale vecchia allerta non va spenta salvo stato confermato")
    if not can_show_bulletin:
        notes.append("bollettino non pronto per uso app")
    if not can_render_map:
        notes.append("mappa meteo non renderizzabile dal dato OSMER corrente")

    alert_ready_for_app = alert_state in {"active", "inactive_confirmed"}
    if alert_state in {"diagnostic", "expired", "stale", "stale_held_active", "unavailable"}:
        notes.append("stato allerta non confermato per decisione finale app")

    healthy = bool(alert.get("available")) and bool(osmer.get("available"))
    ready = healthy and can_show_bulletin and can_render_map and alert_ready_for_app

    return {
        "overall": "ready_for_review" if ready else "needs_review",
        "alert_state": alert_state,
        "osmer_state": osmer_state,
        "can_show_bulletin": can_show_bulletin,
        "can_render_map": can_render_map,
        "can_clear_previous_alert": can_clear_previous_alert,
        "notification_dry_run_allowed": notification_dry_run_allowed,
        "notification_live_connected": False,
        "notes": notes,
    }


def build_report(scope: str) -> dict[str, Any]:
    official_rows = read_jsonl(OFFICIAL_ALERT_LOG)
    osmer_rows = read_jsonl(OSMER_LOG)
    invalidated_osmer = read_invalidated_osmer(OSMER_INVALIDATED)
    invalidated_ids = set(invalidated_osmer)

    official_candidates = filter_scope(official_rows, scope, is_live_official_alert)
    osmer_candidates = filter_scope(osmer_rows, scope, is_live_osmer, invalidated_ids)

    latest_alert = latest_row(official_candidates)
    latest_osmer = latest_row(osmer_candidates)

    alert_summary = summarize_official_alert(latest_alert)
    osmer_summary = summarize_osmer(latest_osmer)
    polling_summary = build_polling_summary(alert_summary, official_candidates)
    notification_summary = build_notification_summary(latest_alert, alert_summary)
    return {
        "schema_version": "1.0",
        "scope": scope,
        "read_only": True,
        "logs": {
            "official_alerts": str(OFFICIAL_ALERT_LOG),
            "osmer": str(OSMER_LOG),
            "osmer_invalidated": str(OSMER_INVALIDATED),
        },
        "counts": {
            "official_alert_rows": len(official_rows),
            "official_alert_candidates": len(official_candidates),
            "osmer_rows": len(osmer_rows),
            "osmer_candidates": len(osmer_candidates),
            "osmer_invalidated_rows": len(invalidated_ids),
        },
        "ignored": {
            "osmer_invalidated": list(invalidated_osmer.values()),
        },
        "official_alerts": alert_summary,
        "polling": polling_summary,
        "notification_decision": notification_summary,
        "osmer_bulletin": osmer_summary,
        "decision": build_decision(alert_summary, osmer_summary, notification_summary),
    }


def yes_no(value: Any) -> str:
    return "si" if bool(value) else "no"


def fmt_list(items: Any) -> str:
    if not items:
        return "-"
    if isinstance(items, list):
        values = []
        for item in items:
            if isinstance(item, dict):
                source_id = item.get("source_id", "")
                status = item.get("status", "")
                values.append(f"{source_id} ({status})" if status else str(source_id))
            else:
                values.append(str(item))
        return ", ".join(value for value in values if value) or "-"
    return str(items)


def render_text(report: dict[str, Any]) -> str:
    alert = report["official_alerts"]
    osmer = report["osmer_bulletin"]
    notification = report.get("notification_decision", {})
    decision = report["decision"]
    counts = report["counts"]

    lines = [
        "DATA PIPELINE STATUS REPORT",
        f"Scope: {report['scope']} | read-only: {yes_no(report['read_only'])}",
        "",
        "Allerte ufficiali",
    ]

    if alert.get("available"):
        lines.extend(
            [
                f"- audit: {alert.get('audit_id')} ({alert.get('created_at')})",
                f"- fonte: {alert.get('source_mode')} / parser {alert.get('source_parser')}",
                f"- stato: {alert.get('state')} | alert trovate: {alert.get('alerts_found')}",
                f"- home: {alert.get('home', {}).get('reading') or alert.get('home', {}).get('label') or 'nessuna label'}",
                f"- bollettino: {alert.get('bulletin', {}).get('reading') or alert.get('bulletin', {}).get('notice') or 'nessun avviso'}",
                f"- notifiche: {alert.get('notification', {}).get('effect') or 'nessun invio'}",
                f"- spegne vecchia allerta: {yes_no(alert.get('can_clear_previous_alert'))}",
                f"- raw sha256: {alert.get('raw_sha256')}",
            ]
        )
    else:
        lines.append(f"- {alert.get('summary')}")

    polling = report.get("polling") if isinstance(report.get("polling"), dict) else {}
    lines.extend(
        [
            "",
            "Prossimo controllo FVG",
            f"- tra: {polling.get('next_check_minutes', '-')} minuti",
            f"- motivo: {polling.get('reason', '-')}",
            f"- fonte irraggiungibile: {yes_no(polling.get('source_unreachable'))}",
            f"- errori consecutivi: {polling.get('consecutive_failures', 0)}",
            f"- diagnostica Telegram/DPC: {yes_no((polling.get('diagnostics') or {}).get('telegram_fvg_allowed'))}",
            f"- scheduler collegato: {yes_no(polling.get('scheduler_connected'))}",
        ]
    )

    lines.extend(
        [
            "",
            "Decisione notifica",
            f"- ammessa: {yes_no(notification.get('can_notify'))}",
            f"- motivo: {notification.get('reason', '-')}",
            f"- severita: {notification.get('severity') or '-'}",
            f"- dedupe: {notification.get('dedupe_key') or '-'}",
            f"- live collegata: {yes_no(notification.get('live_connected'))}",
        ]
    )

    lines.extend(["", "OSMER bollettino"])
    if osmer.get("available"):
        lines.extend(
            [
                f"- audit: {osmer.get('audit_id')} ({osmer.get('created_at')})",
                f"- richiesto: {osmer.get('requested_date')} | lingua: {osmer.get('language')}",
                f"- stato: {osmer.get('state')} | source_status: {osmer.get('source_status')}",
                f"- giorni validi: {fmt_list(osmer.get('valid_dates'))}",
                f"- mappa nativa A1-A9: {yes_no(osmer.get('can_render_native_map'))}",
                f"- XML letti: {fmt_list(osmer.get('fetched_sources'))}",
                f"- XML mancanti/non bloccanti: {fmt_list(osmer.get('missing_sources'))}",
                f"- warning: {fmt_list(osmer.get('warnings'))}",
            ]
        )
    else:
        lines.append(f"- {osmer.get('summary')}")

    lines.extend(
        [
            "",
            "Decisione",
            f"- stato complessivo: {decision.get('overall')}",
            f"- Bollettino mostrabile: {yes_no(decision.get('can_show_bulletin'))}",
            f"- Mappa renderizzabile: {yes_no(decision.get('can_render_map'))}",
            f"- Vecchie allerte spegnibili: {yes_no(decision.get('can_clear_previous_alert'))}",
            f"- Notifica ammessa in dry-run: {yes_no(decision.get('notification_dry_run_allowed'))}",
            f"- Notifica live collegata: {yes_no(decision.get('notification_live_connected'))}",
            f"- Note: {fmt_list(decision.get('notes'))}",
            "",
            "Contatori",
            f"- audit allerta candidati: {counts.get('official_alert_candidates')} / {counts.get('official_alert_rows')}",
            f"- audit OSMER candidati: {counts.get('osmer_candidates')} / {counts.get('osmer_rows')}",
            f"- audit OSMER invalidati ignorati: {counts.get('osmer_invalidated_rows')}",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report read-only dagli audit locali Allerte + OSMER."
    )
    parser.add_argument(
        "--scope",
        choices=("live", "sample", "all"),
        default="live",
        help="Quali audit leggere. Default: live, cioe' solo fonti reali.",
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
    report = build_report(args.scope)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
