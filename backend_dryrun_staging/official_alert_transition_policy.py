"""Pure official-alert transition policy for Meteo Friul UI 3.0.0.

This module is intentionally local and side-effect free. It does not fetch
sources, write state, call Firestore, send notifications or touch the UI.

Inputs are already-normalized observations:
- previous official alert state;
- primary FVG portal/widget read;
- optional Telegram FVG diagnostic;
- optional national DPC diagnostic.

Only the primary FVG source can decide active/no-alert. Telegram FVG and DPC
national data are diagnostic support only.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from typing import Any

import official_alert_notification_policy as notification_policy


ACTIVE_STATES = {"active", "stale_held_active"}
PRIMARY_FINAL_STATES = {"active", "inactive_confirmed"}
PRIMARY_DUBIOUS_STATES = {"diagnostic", "expired", "stale", "stale_held_active", "unavailable"}
UNREACHABLE_STATUSES = {"unreachable", "unavailable", "timeout", "http_error", "network_error"}

SEVERITY_LABELS = {
    "yellow": "Allerta gialla",
    "gialla": "Allerta gialla",
    "orange": "Allerta arancione",
    "arancione": "Allerta arancione",
    "red": "Allerta rossa",
    "rossa": "Allerta rossa",
}


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def normalize_now(now: Any) -> datetime:
    parsed = parse_datetime(now)
    if parsed is None:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def compare_ready_datetime(value: datetime, reference: datetime) -> tuple[datetime, datetime]:
    left = value
    right = reference
    if left.tzinfo is None and right.tzinfo is not None:
        left = left.replace(tzinfo=right.tzinfo)
    if right.tzinfo is None and left.tzinfo is not None:
        right = right.replace(tzinfo=left.tzinfo)
    if left.tzinfo is None and right.tzinfo is None:
        left = left.replace(tzinfo=timezone.utc)
        right = right.replace(tzinfo=timezone.utc)
    return left, right


def severity_key(value: Any) -> str:
    return str(value or "").strip().lower()


def alert_label(alert: dict[str, Any] | None) -> str:
    if not alert:
        return ""
    label = str(alert.get("label") or "").strip()
    if label:
        return label
    level = severity_key(alert.get("level") or alert.get("severity"))
    return SEVERITY_LABELS.get(level, "Allerta")


def normalize_alert(alert: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(alert, dict):
        return {}
    normalized = dict(alert)
    normalized["label"] = alert_label(normalized)
    normalized["level"] = severity_key(normalized.get("level") or normalized.get("severity"))
    return normalized


def first_alert(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        if isinstance(value.get("alert"), dict):
            return normalize_alert(value["alert"])
        alerts = value.get("alerts")
        if isinstance(alerts, list) and alerts and isinstance(alerts[0], dict):
            return normalize_alert(alerts[0])
        if "level" in value or "severity" in value or "label" in value:
            return normalize_alert(value)
    return {}


def previous_alert_valid(previous_state: dict[str, Any] | None, now: Any) -> bool:
    if not isinstance(previous_state, dict):
        return False
    state_id = str(previous_state.get("state") or "").strip()
    if state_id not in ACTIVE_STATES:
        return False
    alert = first_alert(previous_state)
    expires_at = alert.get("expires_at") or previous_state.get("expires_at")
    expires = parse_datetime(expires_at)
    if expires is None:
        return False
    expires, reference = compare_ready_datetime(expires, normalize_now(now))
    return expires > reference


def normalize_primary_state(primary_fvg_read: dict[str, Any] | None) -> str:
    if not isinstance(primary_fvg_read, dict):
        return "unavailable"
    explicit_reachable = primary_fvg_read.get("reachable")
    raw_state = str(primary_fvg_read.get("state") or primary_fvg_read.get("status") or "").strip()
    state = raw_state.lower()
    if explicit_reachable is False or state in UNREACHABLE_STATUSES:
        return "unavailable"
    if state in {"no_alert", "no_alerts", "inactive", "inactive_confirmed"}:
        return "inactive_confirmed"
    if state in {"active", "diagnostic", "expired", "stale"}:
        return state
    if first_alert(primary_fvg_read):
        return "active"
    return "unavailable"


def normalize_diagnostic(source: str, diagnostic: dict[str, Any] | None) -> dict[str, Any]:
    data = diagnostic if isinstance(diagnostic, dict) else {}
    return {
        "source": source,
        "available": bool(data),
        "status": str(data.get("status") or ("not_checked" if not data else "available")),
        "raw_ref": data.get("raw_ref", ""),
        "alert_signature": data.get("alert_signature", ""),
        "decision_role": "diagnostic_only",
        "can_decide": False,
        "can_clear_previous_alert": False,
        "can_notify": False,
    }


def normalize_diagnostics(
    telegram_diagnostic: dict[str, Any] | None = None,
    dpc_diagnostic: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [
        normalize_diagnostic("telegram_public_channel", telegram_diagnostic),
        normalize_diagnostic("national_dpc", dpc_diagnostic),
    ]


def notification_for_active(previous_state: dict[str, Any] | None, alert: dict[str, Any]) -> dict[str, Any]:
    return notification_policy.decide_official_alert_notification(
        previous_state,
        {
            "state": "active",
            "source_authority": "regional_fvg_primary",
            "alert": alert,
        },
    )


def build_visible_alert_effect(alert: dict[str, Any], copy_mode: str) -> dict[str, Any]:
    return {
        "show_alert": True,
        "label": alert_label(alert),
        "level": alert.get("level", ""),
        "expires_at": alert.get("expires_at", ""),
        "copy_mode": copy_mode,
        "show_uncertainty_copy": False,
    }


def build_visible_bulletin_effect(alert: dict[str, Any], copy_mode: str) -> dict[str, Any]:
    return {
        "show_notice": True,
        "label": alert_label(alert),
        "level": alert.get("level", ""),
        "expires_at": alert.get("expires_at", ""),
        "copy_mode": copy_mode,
        "show_unreachable_copy": False,
    }


def build_empty_effects() -> tuple[dict[str, Any], dict[str, Any]]:
    home = {
        "show_alert": False,
        "label": "",
        "level": "",
        "expires_at": "",
        "copy_mode": "none",
        "show_uncertainty_copy": False,
    }
    bulletin = {
        "show_notice": False,
        "label": "",
        "level": "",
        "expires_at": "",
        "copy_mode": "none",
        "show_unreachable_copy": False,
    }
    return home, bulletin


def transition_official_alert(
    previous_alert_state: dict[str, Any] | None,
    primary_fvg_read: dict[str, Any] | None,
    telegram_diagnostic: dict[str, Any] | None = None,
    dpc_diagnostic: dict[str, Any] | None = None,
    now: Any = None,
) -> dict[str, Any]:
    """Return final state and user effects for one alert transition."""

    primary_state = normalize_primary_state(primary_fvg_read)
    diagnostics = normalize_diagnostics(telegram_diagnostic, dpc_diagnostic)
    now_value = normalize_now(now)

    if primary_state == "active":
        alert = first_alert(primary_fvg_read)
        notification = notification_for_active(previous_alert_state, alert)
        return {
            "schema_version": "1.0",
            "final_alert_state": {
                "state": "active",
                "alert": alert,
                "source_authority": "regional_fvg_primary",
                "primary_state": primary_state,
                "can_clear_previous_alert": False,
                "can_notify": notification["can_notify"],
                "diagnostics": diagnostics,
            },
            "home_effect": build_visible_alert_effect(alert, "primary_alert"),
            "bulletin_effect": build_visible_bulletin_effect(alert, "primary_alert"),
            "notification_effect": notification,
            "audit_reason": "primary_fvg_active",
            "computed_at": now_value.isoformat(),
        }

    if primary_state == "inactive_confirmed":
        home, bulletin = build_empty_effects()
        return {
            "schema_version": "1.0",
            "final_alert_state": {
                "state": "inactive_confirmed",
                "alert": {},
                "source_authority": "regional_fvg_primary",
                "primary_state": primary_state,
                "can_clear_previous_alert": True,
                "can_notify": False,
                "diagnostics": diagnostics,
            },
            "home_effect": home,
            "bulletin_effect": bulletin,
            "notification_effect": {
                "can_notify": False,
                "reason": "primary_fvg_confirmed_no_alert",
                "live_connected": False,
            },
            "audit_reason": "primary_fvg_inactive_confirmed",
            "computed_at": now_value.isoformat(),
        }

    if previous_alert_valid(previous_alert_state, now_value):
        previous_alert = first_alert(previous_alert_state)
        return {
            "schema_version": "1.0",
            "final_alert_state": {
                "state": "stale_held_active",
                "alert": previous_alert,
                "source_authority": "regional_fvg_primary_unreachable",
                "primary_state": primary_state,
                "can_clear_previous_alert": False,
                "can_notify": False,
                "diagnostics": diagnostics,
            },
            "home_effect": build_visible_alert_effect(previous_alert, "retain_previous_alert"),
            "bulletin_effect": build_visible_bulletin_effect(previous_alert, "retain_previous_alert"),
            "notification_effect": {
                "can_notify": False,
                "reason": "previous_alert_retained_no_new_notification",
                "live_connected": False,
            },
            "audit_reason": f"{primary_state}_previous_valid_retained",
            "computed_at": now_value.isoformat(),
        }

    fallback_state = primary_state if primary_state in PRIMARY_DUBIOUS_STATES else "unavailable"
    home, bulletin = build_empty_effects()
    return {
        "schema_version": "1.0",
        "final_alert_state": {
            "state": fallback_state,
            "alert": {},
            "source_authority": "regional_fvg_primary_unreachable",
            "primary_state": primary_state,
            "can_clear_previous_alert": False,
            "can_notify": False,
            "diagnostics": diagnostics,
        },
        "home_effect": home,
        "bulletin_effect": bulletin,
        "notification_effect": {
            "can_notify": False,
            "reason": "no_decidable_primary_fvg_state",
            "live_connected": False,
        },
        "audit_reason": f"{fallback_state}_no_valid_previous_alert",
        "computed_at": now_value.isoformat(),
    }


def demo_previous_alert() -> dict[str, Any]:
    return {
        "state": "active",
        "alert": {
            "level": "yellow",
            "label": "Allerta gialla",
            "expires_at": "2026-06-26T18:00:00+02:00",
            "signature": "allerta-regionale-demo-yellow",
        },
    }


def demo_scenarios() -> list[dict[str, Any]]:
    now = "2026-06-26T12:00:00+02:00"
    previous = demo_previous_alert()
    diagnostics = {
        "telegram_diagnostic": {"status": "checked", "alert_signature": "telegram-demo"},
        "dpc_diagnostic": {"status": "checked"},
    }
    return [
        {
            "id": "primary_active_yellow_new",
            "result": transition_official_alert(
                {},
                {
                    "state": "active",
                    "alert": {
                        "level": "yellow",
                        "label": "Allerta gialla",
                        "expires_at": "2026-06-26T18:00:00+02:00",
                        "signature": "allerta-regionale-demo-yellow-new",
                    },
                },
                now=now,
            ),
        },
        {
            "id": "primary_active_yellow_duplicate",
            "result": transition_official_alert(
                previous,
                {
                    "state": "active",
                    "alert": {
                        "level": "yellow",
                        "label": "Allerta gialla",
                        "expires_at": "2026-06-26T18:00:00+02:00",
                        "signature": "allerta-regionale-demo-yellow",
                    },
                },
                now=now,
            ),
        },
        {
            "id": "primary_inactive_confirmed",
            "result": transition_official_alert(
                previous,
                {"state": "inactive_confirmed"},
                now=now,
            ),
        },
        {
            "id": "primary_unreachable_keep_previous_alert",
            "result": transition_official_alert(
                previous,
                {"state": "unavailable", "reachable": False},
                now=now,
                **diagnostics,
            ),
        },
        {
            "id": "primary_parse_error_keep_previous_alert",
            "result": transition_official_alert(
                previous,
                {"state": "diagnostic", "reachable": True},
                now=now,
                **diagnostics,
            ),
        },
        {
            "id": "primary_unreachable_without_previous",
            "result": transition_official_alert(
                {},
                {"state": "unavailable", "reachable": False},
                now=now,
                **diagnostics,
            ),
        },
    ]


def render_demo_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Scenario | Stato | Home | Bollettino | Notifica | Audit |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        result = row["result"]
        state = result["final_alert_state"]["state"]
        home = result["home_effect"]
        bulletin = result["bulletin_effect"]
        notification = result["notification_effect"]
        home_text = home["label"] if home["show_alert"] else "nessuna allerta"
        bulletin_text = bulletin["label"] if bulletin["show_notice"] else "nessun avviso"
        notify_text = "si" if notification["can_notify"] else "no"
        lines.append(
            "| "
            + " | ".join(
                [
                    row["id"],
                    state,
                    home_text,
                    bulletin_text,
                    notify_text,
                    result["audit_reason"],
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Demo pure official-alert transition policy.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = demo_scenarios()
    if args.format == "json":
        print(json.dumps({"scenarios": rows}, ensure_ascii=False, indent=2))
    else:
        print(render_demo_markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
