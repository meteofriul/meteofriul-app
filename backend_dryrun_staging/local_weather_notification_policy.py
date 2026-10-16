"""Pure policy for local weather notification candidates.

This module is intentionally side-effect free. It does not import the backend,
fetch weather, write storage, call Firestore, call FCM or know about fixtures.

Input: normalized candidate notices.
Output: the same notices copied and annotated with final notification policy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


NOTICE_PRIORITY = {
    "hail": 90,
    "storm": 80,
    "ice": 75,
    "snow": 70,
    "bora": 65,
    "wind": 60,
    "rain": 40,
    "heat": 20,
}

MIN_SEPARATION_HOURS = 4
HEAT_BLOCK_HOURS = 8


def notice_priority(notice: dict[str, Any]) -> int:
    kind = str(notice.get("kind") or "")
    category = str(notice.get("category") or "")
    base = NOTICE_PRIORITY.get(kind, NOTICE_PRIORITY.get(category, 0))
    if kind == "rain" and int(notice.get("severity") or 0) >= 2:
        return base + 10
    return base


def parse_event_hour(value: str):
    value = str(value or "").strip()
    if len(value) < 13:
        return None
    try:
        return datetime.fromisoformat(value[:16])
    except ValueError:
        return None


def hours_between(left: dict[str, Any], right: dict[str, Any]) -> float | None:
    left_time = parse_event_hour(str(left.get("event_at") or ""))
    right_time = parse_event_hour(str(right.get("event_at") or ""))
    if not left_time or not right_time:
        return None
    return abs((left_time - right_time).total_seconds()) / 3600


def same_day(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_value = str(left.get("event_at") or left.get("starts_at") or "")
    right_value = str(right.get("event_at") or right.get("starts_at") or "")
    return bool(left_value[:10] and left_value[:10] == right_value[:10])


def blocks_heat(candidate: dict[str, Any], selected: list[dict[str, Any]]) -> dict[str, Any] | None:
    if candidate.get("kind") != "heat":
        return None
    for notice in selected:
        if int(notice.get("priority") or 0) <= int(candidate.get("priority") or 0):
            continue
        distance = hours_between(candidate, notice)
        if distance is not None and distance <= HEAT_BLOCK_HOURS:
            return notice
        if distance is None and same_day(candidate, notice):
            return notice
    return None


def near_selected_notice(candidate: dict[str, Any], selected: list[dict[str, Any]]) -> dict[str, Any] | None:
    for notice in selected:
        distance = hours_between(candidate, notice)
        if distance is not None:
            if distance < MIN_SEPARATION_HOURS:
                return notice
            continue
        if same_day(candidate, notice):
            return notice
    return None


def selection_sort_key(notice: dict[str, Any]) -> tuple[int, str]:
    return (
        -int(notice.get("priority") or 0),
        str(notice.get("event_at") or notice.get("starts_at") or "9999-12-31T23:59"),
    )


def apply_notification_policy(notices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evaluated = [dict(notice) for notice in notices]
    for notice in evaluated:
        if "priority" not in notice:
            notice["priority"] = notice_priority(notice)
    candidates = [
        notice
        for notice in evaluated
        if notice.get("candidate_can_notify") and notice.get("status") == "ready"
    ]
    if not candidates:
        for notice in evaluated:
            notice["can_notify"] = False
            notice["notification_policy"] = "no_candidate"
            notice["notification_reason"] = notice.get("reason") or "nessun candidato notificabile"
        return evaluated

    selected: list[dict[str, Any]] = []
    sorted_candidates = sorted(candidates, key=selection_sort_key)

    for candidate in sorted_candidates:
        heat_blocker = blocks_heat(candidate, selected)
        if heat_blocker:
            candidate["can_notify"] = False
            candidate["notification_policy"] = "held_by_more_important_nearby_event"
            candidate["notification_reason"] = (
                f"trattenuta: {heat_blocker['kind']} piu importante entro {HEAT_BLOCK_HOURS} ore"
            )
            continue

        near = near_selected_notice(candidate, selected)
        if near:
            candidate["can_notify"] = False
            candidate["notification_policy"] = "held_by_temporal_cluster"
            candidate["notification_reason"] = (
                f"trattenuta: {near['kind']} ha priorita uguale o superiore entro {MIN_SEPARATION_HOURS} ore"
            )
            continue

        candidate["can_notify"] = True
        candidate["notification_policy"] = "selected_by_priority_and_time"
        candidate["notification_reason"] = "scelta: priorita adeguata e finestra temporale distinta"
        selected.append(candidate)

    for notice in evaluated:
        if not notice.get("candidate_can_notify"):
            notice["can_notify"] = False
            notice["notification_policy"] = "suppressed"
            notice["notification_reason"] = notice.get("reason") or "non notificabile"
        elif not notice.get("notification_policy"):
            notice["can_notify"] = False
            notice["notification_policy"] = "held_by_policy"
            notice["notification_reason"] = "trattenuta dalla politica anti-rumore"
    return evaluated
