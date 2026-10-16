"""Pure notification policy for official FVG alerts.

This module is intentionally local and side-effect free. It does not send FCM,
write state, call Firestore, fetch sources or touch the UI.

It only answers one question:

Can this final official-alert state produce a notification?
"""

from __future__ import annotations

import argparse
import json
from typing import Any


LEVEL_ALIASES = {
    "yellow": "yellow",
    "gialla": "yellow",
    "allerta gialla": "yellow",
    "orange": "orange",
    "arancione": "orange",
    "allerta arancione": "orange",
    "red": "red",
    "rossa": "red",
    "allerta rossa": "red",
}

LEVEL_LABELS = {
    "yellow": "Allerta gialla",
    "orange": "Allerta arancione",
    "red": "Allerta rossa",
}

PRIMARY_FVG_AUTHORITIES = {
    "regional_fvg",
    "regional_fvg_primary",
    "protezione_civile_fvg",
}


def normalize_level(value: Any) -> str:
    return LEVEL_ALIASES.get(str(value or "").strip().lower(), "")


def first_alert(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        if isinstance(value.get("alert"), dict):
            return dict(value["alert"])
        alerts = value.get("alerts")
        if isinstance(alerts, list) and alerts and isinstance(alerts[0], dict):
            return dict(alerts[0])
        if "level" in value or "severity" in value or "label" in value:
            return dict(value)
    return {}


def state_id(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("state") or value.get("status") or "").strip().lower()
    return str(value or "").strip().lower()


def source_authority(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("source_authority") or value.get("sourceAuthority") or "").strip()


def alert_level(alert: dict[str, Any]) -> str:
    return normalize_level(alert.get("level") or alert.get("severity") or alert.get("label"))


def notification_signature(alert: dict[str, Any]) -> str:
    explicit = str(alert.get("signature") or alert.get("dedupe_key") or alert.get("id") or "").strip()
    if explicit:
        return explicit
    pieces = [
        alert_level(alert),
        str(alert.get("title") or alert.get("label") or "").strip(),
        str(alert.get("starts_at") or alert.get("valid_from") or "").strip(),
        str(alert.get("expires_at") or alert.get("valid_until") or "").strip(),
        str(alert.get("areas") or "").strip(),
    ]
    return "|".join(piece for piece in pieces if piece)


def has_important_text_change(final_state: dict[str, Any], alert: dict[str, Any]) -> bool:
    flags = [
        final_state.get("important_change"),
        final_state.get("important_signature_change"),
        alert.get("important_change"),
        alert.get("important_signature_change"),
    ]
    if any(bool(flag) for flag in flags):
        return True

    change_kind = str(
        alert.get("change_kind")
        or alert.get("change_type")
        or final_state.get("change_kind")
        or final_state.get("change_type")
        or ""
    ).strip().lower()
    return change_kind in {"important", "substantial", "major", "severity_text"}


def blocked(reason: str, final_state: dict[str, Any], alert: dict[str, Any] | None = None) -> dict[str, Any]:
    alert = alert or {}
    return {
        "can_notify": False,
        "reason": reason,
        "severity": alert_level(alert),
        "label": LEVEL_LABELS.get(alert_level(alert), ""),
        "dedupe_key": notification_signature(alert),
        "source_authority": source_authority(final_state),
        "live_connected": False,
    }


def allowed(reason: str, final_state: dict[str, Any], alert: dict[str, Any]) -> dict[str, Any]:
    level = alert_level(alert)
    return {
        "can_notify": True,
        "reason": reason,
        "severity": level,
        "label": LEVEL_LABELS.get(level, "Allerta"),
        "dedupe_key": notification_signature(alert),
        "source_authority": source_authority(final_state),
        "live_connected": False,
    }


def decide_official_alert_notification(
    previous_alert_state: dict[str, Any] | None,
    final_alert_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return whether a final alert state can produce a notification."""

    final_state = final_alert_state if isinstance(final_alert_state, dict) else {}
    previous_state = previous_alert_state if isinstance(previous_alert_state, dict) else {}

    final_state_id = state_id(final_state)
    final_alert = first_alert(final_state)
    previous_alert = first_alert(previous_state)
    authority = source_authority(final_state)

    if final_state_id != "active":
        return blocked(f"{final_state_id or 'missing'}_does_not_notify", final_state, final_alert)

    if authority not in PRIMARY_FVG_AUTHORITIES:
        return blocked("non_primary_fvg_source_does_not_notify", final_state, final_alert)

    final_level = alert_level(final_alert)
    if final_level not in LEVEL_LABELS:
        return blocked("unsupported_alert_level", final_state, final_alert)

    final_signature = notification_signature(final_alert)
    previous_signature = notification_signature(previous_alert)
    previous_level = alert_level(previous_alert)

    if previous_signature and final_signature and previous_signature == final_signature:
        return blocked("same_alert_already_known", final_state, final_alert)

    if not previous_alert:
        return allowed("new_fvg_alert", final_state, final_alert)

    if previous_level and previous_level != final_level:
        return allowed("severity_changed", final_state, final_alert)

    if previous_level == final_level:
        if has_important_text_change(final_state, final_alert):
            return allowed("important_signature_changed", final_state, final_alert)
        return blocked("same_level_text_change_suppressed", final_state, final_alert)

    return allowed("new_fvg_alert", final_state, final_alert)


def demo_previous_yellow() -> dict[str, Any]:
    return {
        "state": "active",
        "alert": {
            "level": "yellow",
            "label": "Allerta gialla",
            "signature": "yellow-1",
        },
    }


def demo_scenarios() -> list[dict[str, Any]]:
    previous = demo_previous_yellow()
    return [
        {
            "id": "new_yellow",
            "result": decide_official_alert_notification(
                {},
                {
                    "state": "active",
                    "source_authority": "regional_fvg_primary",
                    "alert": {"level": "yellow", "signature": "yellow-1"},
                },
            ),
        },
        {
            "id": "duplicate_yellow",
            "result": decide_official_alert_notification(
                previous,
                {
                    "state": "active",
                    "source_authority": "regional_fvg_primary",
                    "alert": {"level": "yellow", "signature": "yellow-1"},
                },
            ),
        },
        {
            "id": "yellow_to_orange",
            "result": decide_official_alert_notification(
                previous,
                {
                    "state": "active",
                    "source_authority": "regional_fvg_primary",
                    "alert": {"level": "orange", "signature": "orange-1"},
                },
            ),
        },
        {
            "id": "same_level_text_change",
            "result": decide_official_alert_notification(
                previous,
                {
                    "state": "active",
                    "source_authority": "regional_fvg_primary",
                    "alert": {"level": "yellow", "signature": "yellow-text-2"},
                },
            ),
        },
        {
            "id": "important_same_level_change",
            "result": decide_official_alert_notification(
                previous,
                {
                    "state": "active",
                    "source_authority": "regional_fvg_primary",
                    "alert": {
                        "level": "yellow",
                        "signature": "yellow-important-2",
                        "important_signature_change": True,
                    },
                },
            ),
        },
        {
            "id": "held_previous_unreachable",
            "result": decide_official_alert_notification(
                previous,
                {
                    "state": "stale_held_active",
                    "source_authority": "regional_fvg_primary_unreachable",
                    "alert": previous["alert"],
                },
            ),
        },
        {
            "id": "telegram_diagnostic",
            "result": decide_official_alert_notification(
                previous,
                {
                    "state": "active",
                    "source_authority": "telegram_public_channel",
                    "alert": {"level": "orange", "signature": "telegram-orange"},
                },
            ),
        },
    ]


def render_demo_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Scenario | Notifica | Severita | Motivo | Dedupe |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        result = row["result"]
        notify_text = "si" if result["can_notify"] else "no"
        lines.append(
            "| "
            + " | ".join(
                [
                    row["id"],
                    notify_text,
                    result["severity"] or "-",
                    result["reason"],
                    result["dedupe_key"] or "-",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Demo pure official-alert notification policy.")
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
