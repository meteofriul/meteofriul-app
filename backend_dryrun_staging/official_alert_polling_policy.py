"""Pure polling policy for the primary FVG official-alert source.

This module is intentionally local and side-effect free. It does not schedule
jobs, fetch sources, write state, call Firestore, send notifications or touch
the UI.

It only answers one question:

When should the primary FVG source be checked again?
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from typing import Any


ACTIVE_STATES = {"active"}
NO_ALERT_STATES = {"inactive_confirmed", "no_alert", "no_alerts", "inactive"}
UNDECIDED_STATES = {"diagnostic", "expired", "stale", "stale_held_active", "unavailable"}
UNREACHABLE_STATES = {"unavailable", "timeout", "http_error", "network_error"}

NO_ALERT_INTERVAL_MINUTES = 30
ACTIVE_INTERVAL_MINUTES = 15
EXPIRING_INTERVAL_MINUTES = 5
UNDECIDED_INTERVAL_MINUTES = 10


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


def state_id(alert_state: dict[str, Any] | str | None) -> str:
    if isinstance(alert_state, str):
        return alert_state.strip().lower()
    if isinstance(alert_state, dict):
        return str(alert_state.get("state") or alert_state.get("status") or "").strip().lower()
    return "unavailable"


def alert_expires_at(alert_state: dict[str, Any] | str | None, expires_at: Any = None) -> Any:
    if expires_at:
        return expires_at
    if not isinstance(alert_state, dict):
        return None
    alert = alert_state.get("alert")
    if isinstance(alert, dict) and alert.get("expires_at"):
        return alert["expires_at"]
    alerts = alert_state.get("alerts")
    if isinstance(alerts, list) and alerts and isinstance(alerts[0], dict):
        return alerts[0].get("expires_at")
    return alert_state.get("expires_at")


def minutes_until(value: Any, now: Any) -> int | None:
    expires = parse_datetime(value)
    if expires is None:
        return None
    expires, reference = compare_ready_datetime(expires, normalize_now(now))
    return int((expires - reference).total_seconds() // 60)


def retry_minutes(consecutive_failures: Any) -> int:
    failures = normalize_failures(consecutive_failures, minimum=1)
    if failures == 1:
        return 5
    if failures == 2:
        return 10
    if failures == 3:
        return 20
    return 30


def normalize_failures(value: Any, minimum: int = 0) -> int:
    try:
        failures = int(value)
    except (TypeError, ValueError):
        failures = minimum
    return max(minimum, failures)


def diagnostics_effect(source_unreachable: bool, consecutive_failures: int) -> dict[str, Any]:
    allowed = bool(source_unreachable and consecutive_failures >= 2)
    return {
        "telegram_fvg_allowed": allowed,
        "dpc_national_allowed": allowed,
        "decision_role": "diagnostic_only",
        "can_decide": False,
        "can_clear_previous_alert": False,
        "can_notify": False,
        "reason": (
            "repeated_fvg_failures_diagnostic_only"
            if allowed
            else "diagnostics_not_needed_for_decision"
        ),
    }


def build_result(
    *,
    state: str,
    next_check_minutes: int,
    reason: str,
    now: Any,
    source_unreachable: bool = False,
    consecutive_failures: int = 0,
    expires_in_minutes: int | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "state": state,
        "next_check_minutes": next_check_minutes,
        "next_check_seconds": next_check_minutes * 60,
        "reason": reason,
        "source_unreachable": source_unreachable,
        "consecutive_failures": consecutive_failures,
        "expires_in_minutes": expires_in_minutes,
        "diagnostics": diagnostics_effect(source_unreachable, consecutive_failures),
        "scheduler_connected": False,
        "live_connected": False,
        "computed_at": normalize_now(now).isoformat(),
    }


def plan_official_alert_polling(
    alert_state: dict[str, Any] | str | None,
    *,
    primary_reachable: bool | None = None,
    consecutive_failures: int = 0,
    expires_at: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Return the next check interval for the primary FVG source."""

    state = state_id(alert_state)
    failures = normalize_failures(consecutive_failures)
    source_unreachable = primary_reachable is False or state in UNREACHABLE_STATES

    if source_unreachable:
        effective_failures = max(1, failures)
        return build_result(
            state=state,
            next_check_minutes=retry_minutes(effective_failures),
            reason=f"fvg_unreachable_retry_{effective_failures}",
            source_unreachable=True,
            consecutive_failures=effective_failures,
            now=now,
        )

    expires_in = minutes_until(alert_expires_at(alert_state, expires_at), now)

    if state in ACTIVE_STATES:
        if expires_in is not None and expires_in <= 60:
            return build_result(
                state=state,
                next_check_minutes=EXPIRING_INTERVAL_MINUTES,
                reason="active_alert_expiring_within_one_hour",
                consecutive_failures=failures,
                expires_in_minutes=expires_in,
                now=now,
            )
        return build_result(
            state=state,
            next_check_minutes=ACTIVE_INTERVAL_MINUTES,
            reason="active_alert_standard_interval",
            consecutive_failures=failures,
            expires_in_minutes=expires_in,
            now=now,
        )

    if state in NO_ALERT_STATES:
        return build_result(
            state="inactive_confirmed",
            next_check_minutes=NO_ALERT_INTERVAL_MINUTES,
            reason="no_alert_confirmed_standard_interval",
            consecutive_failures=failures,
            now=now,
        )

    if state in UNDECIDED_STATES:
        return build_result(
            state=state,
            next_check_minutes=UNDECIDED_INTERVAL_MINUTES,
            reason="undecided_state_needs_near_retry",
            consecutive_failures=failures,
            expires_in_minutes=expires_in,
            now=now,
        )

    return build_result(
        state=state or "unknown",
        next_check_minutes=UNDECIDED_INTERVAL_MINUTES,
        reason="unknown_state_needs_near_retry",
        consecutive_failures=failures,
        now=now,
    )


def demo_scenarios() -> list[dict[str, Any]]:
    now = "2026-06-26T12:00:00+02:00"
    return [
        {
            "id": "no_alert_confirmed",
            "result": plan_official_alert_polling("inactive_confirmed", now=now),
        },
        {
            "id": "active_alert",
            "result": plan_official_alert_polling(
                {"state": "active", "alert": {"expires_at": "2026-06-26T18:00:00+02:00"}},
                now=now,
            ),
        },
        {
            "id": "active_alert_expiring",
            "result": plan_official_alert_polling(
                {"state": "active", "alert": {"expires_at": "2026-06-26T12:45:00+02:00"}},
                now=now,
            ),
        },
        {
            "id": "fvg_unreachable_first_retry",
            "result": plan_official_alert_polling(
                "unavailable",
                primary_reachable=False,
                consecutive_failures=1,
                now=now,
            ),
        },
        {
            "id": "fvg_unreachable_second_retry",
            "result": plan_official_alert_polling(
                "unavailable",
                primary_reachable=False,
                consecutive_failures=2,
                now=now,
            ),
        },
        {
            "id": "fvg_unreachable_third_retry",
            "result": plan_official_alert_polling(
                "unavailable",
                primary_reachable=False,
                consecutive_failures=3,
                now=now,
            ),
        },
        {
            "id": "fvg_unreachable_repeated_retry",
            "result": plan_official_alert_polling(
                "unavailable",
                primary_reachable=False,
                consecutive_failures=4,
                now=now,
            ),
        },
    ]


def render_demo_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Scenario | Stato | Prossimo controllo | Diagnostica | Motivo |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        result = row["result"]
        diagnostics = "si" if result["diagnostics"]["telegram_fvg_allowed"] else "no"
        lines.append(
            "| "
            + " | ".join(
                [
                    row["id"],
                    result["state"],
                    f"{result['next_check_minutes']} min",
                    diagnostics,
                    result["reason"],
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Demo pure official-alert polling policy.")
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
