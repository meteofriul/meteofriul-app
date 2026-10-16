from __future__ import annotations

import os
import time
from copy import deepcopy
from threading import RLock

from app.infrastructure.firebase import get_firestore_client
from app.repositories.event_sources import (
    EVENT_SOURCE_STATE_SCHEMA,
    EventSourceStateRepository,
    EventSourceStateRepositoryUnavailable,
)


EVENT_SOURCE_FEED_MODE_ENV = "EVENT_SOURCE_FEED_MODE"
EVENT_SOURCE_LOCAL_STATE_PATH_ENV = "EVENT_SOURCE_LOCAL_STATE_PATH"
EVENT_SOURCE_FEED_CACHE_SECONDS = 30

_cache_lock = RLock()
_cache_value: tuple[float, list[dict]] | None = None


def event_source_feed_mode() -> str:
    mode = os.getenv(EVENT_SOURCE_FEED_MODE_ENV, "off").strip().lower() or "off"
    if mode not in {"off", "preview", "active"}:
        return "off"
    if mode == "preview" and os.getenv("K_SERVICE", "").strip():
        return "off"
    return mode


def _repository() -> EventSourceStateRepository:
    local_path = os.getenv(EVENT_SOURCE_LOCAL_STATE_PATH_ENV, "").strip() or None
    if os.getenv("K_SERVICE", "").strip():
        local_path = None
    return EventSourceStateRepository(
        get_firestore_client,
        local_state_path=local_path,
    )


def load_guarded_official_events(*, use_cache: bool = True) -> list[dict]:
    global _cache_value
    mode = event_source_feed_mode()
    if mode == "off":
        return []

    now = time.monotonic()
    with _cache_lock:
        if (
            use_cache
            and _cache_value is not None
            and now - _cache_value[0] <= EVENT_SOURCE_FEED_CACHE_SECONDS
        ):
            return deepcopy(_cache_value[1])

    try:
        state, _ = _repository().load()
    except EventSourceStateRepositoryUnavailable:
        return []
    if (
        not isinstance(state, dict)
        or state.get("schema_version") != EVENT_SOURCE_STATE_SCHEMA
        or (mode == "active" and state.get("publication_enabled") is not True)
    ):
        return []

    events = [
        deepcopy(item.get("event"))
        for item in state.get("approved") or []
        if isinstance(item, dict) and isinstance(item.get("event"), dict)
    ]
    with _cache_lock:
        _cache_value = (now, deepcopy(events))
    return events


def reset_guarded_event_feed_cache() -> None:
    global _cache_value
    with _cache_lock:
        _cache_value = None


__all__ = [
    "event_source_feed_mode",
    "load_guarded_official_events",
    "reset_guarded_event_feed_cache",
]
