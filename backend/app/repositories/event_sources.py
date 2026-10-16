from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable


EVENT_SOURCE_STATE_COLLECTION = "event_source_automation"
EVENT_SOURCE_STATE_DOCUMENT = "current"
EVENT_SOURCE_STATE_SCHEMA = "event-source-automation-state.v1"
EVENT_SOURCE_FIRESTORE_TIMEOUT_SECONDS = 5.0


class EventSourceStateRepositoryUnavailable(RuntimeError):
    """The guarded event-source state could not be read or stored durably."""


class EventSourceStateRepository:
    def __init__(
        self,
        firestore_provider: Callable[[], Any | None],
        *,
        local_state_path: str | Path | None = None,
        operation_timeout_seconds: float = EVENT_SOURCE_FIRESTORE_TIMEOUT_SECONDS,
    ) -> None:
        self._firestore_provider = firestore_provider
        self._local_state_path = (
            Path(local_state_path).resolve() if local_state_path else None
        )
        self._operation_timeout_seconds = max(0.1, operation_timeout_seconds)
        self._memory: dict[str, Any] | None = None
        self._lock = RLock()

    def _db(self) -> Any:
        try:
            db = self._firestore_provider()
        except Exception as error:
            raise EventSourceStateRepositoryUnavailable(
                "event_source_firestore_unavailable"
            ) from error
        if db is None:
            raise EventSourceStateRepositoryUnavailable(
                "event_source_firestore_unavailable"
            )
        return db

    def _load_local(self) -> dict[str, Any] | None:
        path = self._local_state_path
        if not path or not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise EventSourceStateRepositoryUnavailable(
                "event_source_local_state_invalid"
            ) from error
        if not isinstance(payload, dict):
            raise EventSourceStateRepositoryUnavailable(
                "event_source_local_state_invalid"
            )
        return payload

    def load(self) -> tuple[dict[str, Any] | None, str]:
        if self._local_state_path:
            state = self._load_local()
            if state is not None:
                with self._lock:
                    self._memory = deepcopy(state)
            return deepcopy(state), "local_file" if state else "local_empty"

        try:
            snapshot = (
                self._db()
                .collection(EVENT_SOURCE_STATE_COLLECTION)
                .document(EVENT_SOURCE_STATE_DOCUMENT)
                .get(retry=None, timeout=self._operation_timeout_seconds)
            )
        except EventSourceStateRepositoryUnavailable:
            raise
        except Exception as error:
            raise EventSourceStateRepositoryUnavailable(
                "event_source_state_read_failed"
            ) from error

        if not snapshot.exists:
            return None, "firestore_empty"
        stored = snapshot.to_dict() or {}
        state = stored.get("state")
        if not isinstance(state, dict):
            raise EventSourceStateRepositoryUnavailable(
                "event_source_state_invalid"
            )
        with self._lock:
            self._memory = deepcopy(state)
        return deepcopy(state), "firestore"

    def save(self, state: dict[str, Any]) -> str:
        normalized = deepcopy(state)
        if normalized.get("schema_version") != EVENT_SOURCE_STATE_SCHEMA:
            raise ValueError("event_source_state_schema_invalid")

        if self._local_state_path:
            path = self._local_state_path
            temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary.write_text(
                    json.dumps(normalized, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                temporary.replace(path)
            except OSError as error:
                raise EventSourceStateRepositoryUnavailable(
                    "event_source_local_state_write_failed"
                ) from error
            with self._lock:
                self._memory = normalized
            return "local_file"

        try:
            (
                self._db()
                .collection(EVENT_SOURCE_STATE_COLLECTION)
                .document(EVENT_SOURCE_STATE_DOCUMENT)
                .set(
                    {
                        "state": normalized,
                        "stored_at": datetime.now(timezone.utc),
                    },
                    retry=None,
                    timeout=self._operation_timeout_seconds,
                )
            )
        except EventSourceStateRepositoryUnavailable:
            raise
        except Exception as error:
            raise EventSourceStateRepositoryUnavailable(
                "event_source_state_write_failed"
            ) from error
        with self._lock:
            self._memory = normalized
        return "firestore"


__all__ = [
    "EVENT_SOURCE_STATE_COLLECTION",
    "EVENT_SOURCE_STATE_DOCUMENT",
    "EVENT_SOURCE_STATE_SCHEMA",
    "EventSourceStateRepository",
    "EventSourceStateRepositoryUnavailable",
]
