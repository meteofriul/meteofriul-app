from __future__ import annotations

import os
import time
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable


NATIONAL_OFFICIAL_ALERT_SNAPSHOTS_COLLECTION = (
    "national_official_alert_snapshots"
)
NATIONAL_OFFICIAL_ALERT_SNAPSHOT_DOCUMENT = "current"
NATIONAL_OFFICIAL_ALERT_FIRESTORE_TIMEOUT_SECONDS = float(
    os.getenv("NATIONAL_OFFICIAL_ALERTS_FIRESTORE_TIMEOUT_SECONDS", "5")
)
NATIONAL_OFFICIAL_ALERT_READ_TTL_SECONDS = float(
    os.getenv("NATIONAL_OFFICIAL_ALERTS_FIRESTORE_READ_TTL_SECONDS", "30")
)


class NationalOfficialAlertSnapshotRepository:
    """National state isolated from the existing regional FVG collection."""

    def __init__(
        self,
        firestore_provider: Callable[[], Any | None] | None = None,
        *,
        operation_timeout_seconds: float = (
            NATIONAL_OFFICIAL_ALERT_FIRESTORE_TIMEOUT_SECONDS
        ),
        read_ttl_seconds: float = NATIONAL_OFFICIAL_ALERT_READ_TTL_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._firestore_provider = firestore_provider or (lambda: None)
        self._operation_timeout_seconds = max(0.1, operation_timeout_seconds)
        self._read_ttl_seconds = max(0.0, read_ttl_seconds)
        self._monotonic = monotonic
        self._memory: dict[str, Any] | None = None
        self._lock = RLock()
        self._load_in_progress = False
        self._last_load_attempt_at: float | None = None
        self._last_load_result: tuple[dict[str, Any] | None, str] | None = None

    def _db(self) -> Any | None:
        try:
            return self._firestore_provider()
        except Exception:
            return None

    def load(self) -> tuple[dict[str, Any] | None, str]:
        now = self._monotonic()
        with self._lock:
            memory = deepcopy(self._memory)
            if (
                self._last_load_result is not None
                and self._last_load_attempt_at is not None
                and now - self._last_load_attempt_at < self._read_ttl_seconds
            ):
                payload, storage = self._last_load_result
                if payload is None and memory is not None:
                    return memory, "memory"
                return deepcopy(payload), storage
            if self._load_in_progress:
                return memory, "memory" if memory else "refreshing"
            self._load_in_progress = True

        result: tuple[dict[str, Any] | None, str]
        try:
            db = self._db()
            if db is None:
                result = (memory, "memory" if memory else "empty")
            else:
                try:
                    snapshot = db.collection(
                        NATIONAL_OFFICIAL_ALERT_SNAPSHOTS_COLLECTION
                    ).document(NATIONAL_OFFICIAL_ALERT_SNAPSHOT_DOCUMENT).get(
                        retry=None,
                        timeout=self._operation_timeout_seconds,
                    )
                    if snapshot.exists:
                        stored = snapshot.to_dict() or {}
                        payload = stored.get("payload")
                        result = (
                            (deepcopy(payload), "firestore")
                            if isinstance(payload, dict)
                            else (memory, "memory" if memory else "firestore_empty")
                        )
                    else:
                        result = (
                            memory,
                            "memory" if memory else "firestore_empty",
                        )
                except Exception:
                    result = (
                        memory,
                        "memory_fallback" if memory else "unavailable",
                    )
        finally:
            with self._lock:
                payload, storage = result
                if isinstance(payload, dict):
                    self._memory = deepcopy(payload)
                self._last_load_attempt_at = self._monotonic()
                self._last_load_result = (deepcopy(payload), storage)
                self._load_in_progress = False
        return deepcopy(result[0]), result[1]

    def save(self, payload: dict[str, Any]) -> str:
        normalized = deepcopy(payload)
        with self._lock:
            self._memory = normalized
        db = self._db()
        if db is None:
            storage = "memory"
        else:
            try:
                db.collection(
                    NATIONAL_OFFICIAL_ALERT_SNAPSHOTS_COLLECTION
                ).document(NATIONAL_OFFICIAL_ALERT_SNAPSHOT_DOCUMENT).set(
                    {
                        "payload": deepcopy(payload),
                        "stored_at": datetime.now(timezone.utc),
                    },
                    retry=None,
                    timeout=self._operation_timeout_seconds,
                )
                storage = "firestore"
            except Exception:
                storage = "memory_fallback"
        with self._lock:
            self._last_load_attempt_at = self._monotonic()
            self._last_load_result = (deepcopy(normalized), storage)
        return storage
