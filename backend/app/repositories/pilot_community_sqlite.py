"""Durable *local* pilot Community, never a production/Firestore provider.

SQLite serializes complete service transactions with BEGIN IMMEDIATE. Each
transaction reloads the current state so two processes cannot overwrite another
process's quotas, votes or idempotency receipts with a stale memory snapshot.
Callers must use ``transaction()`` for every service read or mutation. The memory
repository remains the deterministic default for unit tests.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Any

from app.repositories.community import CommunityRepositoryUnavailable
from app.repositories.pilot_community import (
    PILOT_STATE_FIELDS,
    PilotMemoryCommunityRepository,
)


SCHEMA_VERSION = 1
APPLICATION_ID = 0x4D465043  # MFPC: Meteo Friul Pilot Community


def _encode(value: Any) -> Any:
    # Explicit tags avoid both pickle execution and collisions between a JSON
    # object's keys and the metadata used to encode dates/tuples/sets.
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non_finite_state")
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive_datetime_state")
        return {"type": "datetime", "value": value.isoformat()}
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("non_string_state_key")
        return {"type": "dict", "value": {
            key: _encode(item) for key, item in value.items()
        }}
    if isinstance(value, (list, tuple, set)):
        items = [_encode(item) for item in value]
        if isinstance(value, set):
            items.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return {"type": type(value).__name__, "value": items}
    raise ValueError("unsupported_state_value")


def _decode(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non_finite_state")
        return value
    if not isinstance(value, dict) or set(value) != {"type", "value"}:
        raise ValueError("invalid_state_encoding")
    kind, content = value["type"], value["value"]
    if kind == "datetime" and isinstance(content, str):
        result = datetime.fromisoformat(content)
        if result.tzinfo is None:
            raise ValueError("naive_datetime_state")
        return result
    if kind == "dict" and isinstance(content, dict):
        return {key: _decode(item) for key, item in content.items()}
    if kind in {"list", "tuple", "set"} and isinstance(content, list):
        items = [_decode(item) for item in content]
        if kind == "tuple":
            return tuple(items)
        if kind == "set":
            return set(items)
        return items
    raise ValueError("invalid_state_encoding")


def _reject_duplicate_keys(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate_state_key")
        result[key] = value
    return result


class PilotSQLiteCommunityRepository(PilotMemoryCommunityRepository):
    """Local file repository with fail-closed persistence and no cloud I/O."""

    storage_kind = "sqlite"

    def __init__(self, database_path: str | Path):
        super().__init__()
        if str(database_path) == ":memory:" or str(database_path).startswith("file:"):
            raise ValueError("pilot_storage_requires_local_file")
        self.database_path = Path(database_path).expanduser().resolve()
        self._connection: sqlite3.Connection | None = None
        self._pilot_transaction_depth = 0
        existed = self.database_path.exists()
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(
                self.database_path, isolation_level=None, check_same_thread=False,
                timeout=15,
            )
            self._connection.execute("PRAGMA synchronous = FULL")
            self._connection.execute("BEGIN IMMEDIATE")
            tables = self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
            if not tables and not existed:
                self._connection.execute(
                    "CREATE TABLE pilot_community_state ("
                    "id INTEGER PRIMARY KEY CHECK (id = 1), "
                    "schema_version INTEGER NOT NULL, payload TEXT NOT NULL, "
                    "checksum TEXT NOT NULL)"
                )
                self._connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
                self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                self._write_state(initial=True)
            self._read_state()
            self._connection.commit()
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError) as error:
            if self._connection is not None:
                self._connection.rollback()
                self._connection.close()
                self._connection = None
            raise CommunityRepositoryUnavailable("pilot_sqlite_store_unavailable") from error

    def _read_state(self) -> str:
        connection = self._require_connection()
        if (
            connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
            or connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION
        ):
            raise ValueError("unsupported_pilot_store_schema")
        rows = connection.execute(
            "SELECT id, schema_version, payload, checksum FROM pilot_community_state"
        ).fetchall()
        if len(rows) != 1 or rows[0][0:2] != (1, SCHEMA_VERSION):
            raise ValueError("invalid_pilot_store_row")
        payload, checksum = rows[0][2:]
        if not isinstance(payload, str) or not isinstance(checksum, str):
            raise ValueError("invalid_pilot_store_payload")
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != checksum:
            raise ValueError("corrupt_pilot_store_checksum")
        encoded = json.loads(payload, object_pairs_hook=_reject_duplicate_keys)
        if not isinstance(encoded, dict) or set(encoded) != set(PILOT_STATE_FIELDS):
            raise ValueError("unsupported_pilot_store_fields")
        state = {field: _decode(encoded[field]) for field in PILOT_STATE_FIELDS}
        if any(not isinstance(item, dict) for item in state.values()):
            raise ValueError("invalid_pilot_store_field")
        self._restore_state(state)
        return payload

    def _serialize_state(self) -> str:
        return json.dumps(
            {field: _encode(value) for field, value in self._snapshot_state().items()},
            ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"),
        )

    def _write_state(self, *, initial: bool = False, previous: str | None = None) -> None:
        payload = self._serialize_state()
        if payload == previous:
            return
        values = (SCHEMA_VERSION, payload, hashlib.sha256(payload.encode("utf-8")).hexdigest())
        if initial:
            self._require_connection().execute(
                "INSERT INTO pilot_community_state (id, schema_version, payload, checksum) "
                "VALUES (1, ?, ?, ?)", values,
            )
        else:
            result = self._require_connection().execute(
                "UPDATE pilot_community_state SET schema_version = ?, payload = ?, checksum = ? "
                "WHERE id = 1", values,
            )
            if result.rowcount != 1:
                raise ValueError("missing_pilot_store_row")

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise CommunityRepositoryUnavailable("pilot_sqlite_store_closed")
        return self._connection

    @contextmanager
    def transaction(self):
        with self.lock:
            # The superclass implements rollback-only nesting. Only the outer
            # SQLite boundary reloads, writes or commits a transaction.
            if self._pilot_transaction_depth:
                with super().transaction():
                    yield self
                return
            connection = self._require_connection()
            before = self._snapshot_state()
            try:
                connection.execute("BEGIN IMMEDIATE")
                previous = self._read_state()
                before = self._snapshot_state()
                with super().transaction():
                    yield self
                self._write_state(previous=previous)
                connection.commit()
            except BaseException as error:
                connection.rollback()
                self._restore_state(before)
                if isinstance(error, (sqlite3.Error, ValueError, TypeError, KeyError)):
                    raise CommunityRepositoryUnavailable("pilot_sqlite_transaction_failed") from error
                raise

    def close(self) -> None:
        with self.lock:
            if self._pilot_transaction_depth:
                raise CommunityRepositoryUnavailable("pilot_sqlite_transaction_in_progress")
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def save_report(self, report):
        super().save_report(report)
        return self.storage_kind

    def delete_report(self, report_id):
        super().delete_report(report_id)
        return self.storage_kind

    def list_scoped_reports(self, **kwargs):
        reports, _ = super().list_scoped_reports(**kwargs)
        return reports, self.storage_kind

    def get_report(self, report_id, now):
        report, _ = super().get_report(report_id, now)
        return report, self.storage_kind


# Accept the spelling used by the standalone pilot entrypoint as well.
PilotSqliteCommunityRepository = PilotSQLiteCommunityRepository
