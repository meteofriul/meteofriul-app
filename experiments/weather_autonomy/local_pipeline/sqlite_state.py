"""SQLite implementation of the local durable pipeline state contract.

Only the standard library is used.  Every operation opens an independent
connection and every mutation uses ``BEGIN IMMEDIATE``.  WAL plus FULL
synchronous mode make the file suitable for restart and multi-process failure
tests; SQLite is a local test adapter, not a claim that a cloud object store has
cross-object transactions.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator, Mapping
from uuid import UUID

from .contracts import (
    CamsState,
    ClaimDisposition,
    ClaimResult,
    InvalidCheckpoint,
    InvalidTransition,
    LeaseLost,
    Provider,
    RunKey,
    RunNotFound,
    RunRecord,
    RunState,
    StateConflict,
    TransitionRecord,
    TransitionResult,
)


SCHEMA_VERSION = 1
MAX_LEASE_SECONDS = 24 * 60 * 60
MAX_CHECKPOINT_BYTES = 16 * 1024
_OWNER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CAMS_EDGES = {
    CamsState.INTENT: CamsState.SUBMITTED,
    CamsState.SUBMITTED: CamsState.READY,
    CamsState.READY: CamsState.DOWNLOADED,
    CamsState.DOWNLOADED: CamsState.VALIDATED,
    CamsState.VALIDATED: CamsState.PUBLISHED,
}
_CHECKPOINT_FIELDS = frozenset(
    {
        "run_date",
        "request_plan_sha256",
        "request_record_sha256",
        "intent_sha256",
        "job_sha256",
        "request_id",
        "ready_evidence_sha256",
        "download_record_sha256",
        "artifact_sha256",
        "artifact_bytes",
        "payload_sha256",
        "payload_bytes",
        "decode_report_sha256",
        "catalog_sha256",
        "municipality_count",
        "variable_count",
        "hourly_instants",
        "validation_sha256",
        "publication_intent_at",
        "core_manifest_sha256",
        "pollen_manifest_sha256",
        "family_release_sha256",
        "family_latest_etag",
        "family_revision",
        "core_object_count",
        "pollen_object_count",
        "publication_sha256",
    }
)


def _utc(value: datetime | None) -> datetime:
    result = datetime.now(timezone.utc) if value is None else value
    if not isinstance(result, datetime) or result.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware")
    result = result.astimezone(timezone.utc)
    if not math.isfinite(result.timestamp()):
        raise ValueError("Timestamp must be finite")
    return result


def _lease_seconds(value: timedelta) -> float:
    if not isinstance(value, timedelta):
        raise ValueError("Lease duration must be a timedelta")
    seconds = value.total_seconds()
    if not math.isfinite(seconds) or not 0 < seconds <= MAX_LEASE_SECONDS:
        raise ValueError("Lease duration must be positive and at most 24 hours")
    return seconds


def _owner(value: str) -> str:
    if not isinstance(value, str) or not _OWNER_ID.fullmatch(value):
        raise ValueError("Invalid execution owner identifier")
    return value


def _fence(value: int) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("Fencing token must be a positive integer")
    return value


def _enum(value: Any, kind: type[CamsState], message: str) -> CamsState:
    try:
        return value if isinstance(value, kind) else kind(value)
    except (TypeError, ValueError):
        raise InvalidTransition(message) from None


def _checkpoint(value: Mapping[str, Any] | None) -> tuple[dict[str, Any], str]:
    if value is None:
        value = {}
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise InvalidCheckpoint("Checkpoint must be a JSON object")
    if set(value) - _CHECKPOINT_FIELDS:
        raise InvalidCheckpoint("Checkpoint contains an unsupported field")
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        decoded = json.loads(encoded)
    except (TypeError, ValueError):
        raise InvalidCheckpoint("Checkpoint must contain strict JSON values") from None
    if len(encoded.encode("utf-8")) > MAX_CHECKPOINT_BYTES:
        raise InvalidCheckpoint("Checkpoint exceeds the local state size limit")
    return decoded, encoded


def _merge_checkpoint(current: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for key, value in patch.items():
        if key in merged and merged[key] != value:
            raise StateConflict("A durable checkpoint field cannot be changed")
        merged[key] = value
    return merged


def _checkpoint_sha256(checkpoint: Mapping[str, Any], field: str, state: str) -> None:
    digest = checkpoint.get(field)
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise InvalidCheckpoint(f"{state} requires {field} as a lowercase SHA-256")


def _checkpoint_etag(checkpoint: Mapping[str, Any], field: str) -> None:
    etag = checkpoint.get(field)
    if (
        not isinstance(etag, str)
        or not 1 <= len(etag) <= 256
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in etag)
    ):
        raise InvalidCheckpoint(f"PUBLISHED requires a bounded {field}")


def _validate_cams_checkpoint(
    state: CamsState,
    checkpoint: Mapping[str, Any],
    *,
    key: RunKey,
) -> None:
    if state is CamsState.INTENT:
        return
    run_date = checkpoint.get("run_date")
    if (
        not isinstance(run_date, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}", run_date) is None
        or run_date.replace("-", "") + "T000000Z" != key.source_run_id
    ):
        raise InvalidCheckpoint(
            "SUBMITTED and later states require a run date matching the run key"
        )
    for field in (
        "request_plan_sha256",
        "request_record_sha256",
        "intent_sha256",
        "job_sha256",
        "catalog_sha256",
    ):
        _checkpoint_sha256(checkpoint, field, "SUBMITTED")
    request_id = checkpoint.get("request_id")
    try:
        if not isinstance(request_id, str) or str(UUID(request_id)) != request_id:
            raise ValueError
    except (ValueError, AttributeError):
        raise InvalidCheckpoint("SUBMITTED and later states require a canonical request identifier") from None
    if state in {
        CamsState.READY,
        CamsState.DOWNLOADED,
        CamsState.VALIDATED,
        CamsState.PUBLISHED,
    }:
        _checkpoint_sha256(checkpoint, "ready_evidence_sha256", "READY")
    if state in {CamsState.DOWNLOADED, CamsState.VALIDATED, CamsState.PUBLISHED}:
        _checkpoint_sha256(checkpoint, "download_record_sha256", "DOWNLOADED")
        digest = checkpoint.get("artifact_sha256")
        size = checkpoint.get("artifact_bytes")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise InvalidCheckpoint("DOWNLOADED and later states require an artifact SHA-256")
        if type(size) is not int or size <= 0:
            raise InvalidCheckpoint("DOWNLOADED and later states require a positive artifact size")
    if state in {CamsState.VALIDATED, CamsState.PUBLISHED}:
        for field in (
            "payload_sha256",
            "decode_report_sha256",
            "validation_sha256",
        ):
            _checkpoint_sha256(checkpoint, field, "VALIDATED")
        if type(checkpoint.get("payload_bytes")) is not int or checkpoint["payload_bytes"] <= 0:
            raise InvalidCheckpoint("VALIDATED and later states require positive payload bytes")
        expected_counts = {
            "municipality_count": 215,
            "variable_count": 28,
            "hourly_instants": 97,
        }
        if any(checkpoint.get(field) != value for field, value in expected_counts.items()):
            raise InvalidCheckpoint(
                "VALIDATED and later states require the complete 215x28x97 CAMS matrix"
            )
        publication_intent = checkpoint.get("publication_intent_at")
        try:
            parsed_publication = datetime.strptime(
                publication_intent, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            raise InvalidCheckpoint(
                "VALIDATED and later states require a canonical publication intent"
            ) from None
        if parsed_publication.strftime("%Y-%m-%dT%H:%M:%SZ") != publication_intent:
            raise InvalidCheckpoint(
                "VALIDATED and later states require a canonical publication intent"
            )
    if state is CamsState.PUBLISHED:
        for field in (
            "core_manifest_sha256",
            "pollen_manifest_sha256",
            "family_release_sha256",
            "publication_sha256",
        ):
            _checkpoint_sha256(checkpoint, field, "PUBLISHED")
        _checkpoint_etag(checkpoint, "family_latest_etag")
        if type(checkpoint.get("family_revision")) is not int or checkpoint[
            "family_revision"
        ] < 1:
            raise InvalidCheckpoint(
                "PUBLISHED requires a positive CAMS family revision"
            )
        if (
            checkpoint.get("core_object_count") != 215
            or checkpoint.get("pollen_object_count") != 215
        ):
            raise InvalidCheckpoint(
                "PUBLISHED requires both complete 215-municipality provider projections"
            )


class SqliteStateStore:
    """Durable local state with conditional ownership and monotonic fencing."""

    def __init__(self, path: str | Path, *, busy_timeout_seconds: float = 10.0) -> None:
        self.path = Path(path)
        if self.path.exists() and not self.path.is_file():
            raise ValueError("SQLite state path must be a file")
        if not self.path.parent.is_dir():
            raise ValueError("SQLite state parent directory must already exist")
        if isinstance(busy_timeout_seconds, bool) or not isinstance(busy_timeout_seconds, (int, float)):
            raise ValueError("Busy timeout must be numeric")
        if not math.isfinite(float(busy_timeout_seconds)) or not 0 < float(busy_timeout_seconds) <= 60:
            raise ValueError("Busy timeout must be between zero and 60 seconds")
        self._busy_timeout_ms = round(float(busy_timeout_seconds) * 1000)
        self._closed = False
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("SQLite state store is closed")
        connection = sqlite3.connect(
            self.path,
            timeout=self._busy_timeout_ms / 1000,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                raise RuntimeError("SQLite WAL mode could not be enabled")
            existing_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if existing_version not in (0, SCHEMA_VERSION):
                raise RuntimeError("Unsupported SQLite state schema version")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    provider TEXT NOT NULL CHECK (provider IN ('icon', 'cams')),
                    source_run_id TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('CLAIMED', 'INTENT', 'SUBMITTED', 'READY',
                                  'DOWNLOADED', 'VALIDATED', 'PUBLISHED')
                    ),
                    checkpoint_json TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    fencing_token INTEGER NOT NULL CHECK (fencing_token >= 1),
                    lease_expires_at REAL NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (provider, source_run_id, request_hash)
                ) WITHOUT ROWID
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transitions (
                    sequence INTEGER PRIMARY KEY,
                    provider TEXT NOT NULL,
                    source_run_id TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    checkpoint_json TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    fencing_token INTEGER NOT NULL CHECK (fencing_token >= 1),
                    occurred_at REAL NOT NULL,
                    UNIQUE (provider, source_run_id, request_hash, to_state),
                    FOREIGN KEY (provider, source_run_id, request_hash)
                        REFERENCES runs (provider, source_run_id, request_hash)
                        ON DELETE RESTRICT
                )
                """
            )
            if existing_version == 0:
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _select(connection: sqlite3.Connection, key: RunKey) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT * FROM runs
            WHERE provider=? AND source_run_id=? AND request_hash=?
            """,
            (key.provider.value, key.source_run_id, key.request_hash),
        ).fetchone()

    @staticmethod
    def _record(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            key=RunKey(Provider(row["provider"]), row["source_run_id"], row["request_hash"]),
            state=RunState(row["state"]),
            checkpoint=json.loads(row["checkpoint_json"]),
            owner_id=row["owner_id"],
            fencing_token=row["fencing_token"],
            lease_expires_at=datetime.fromtimestamp(row["lease_expires_at"], timezone.utc),
            created_at=datetime.fromtimestamp(row["created_at"], timezone.utc),
            updated_at=datetime.fromtimestamp(row["updated_at"], timezone.utc),
        )

    @staticmethod
    def _require_owned(
        row: sqlite3.Row,
        *,
        owner_id: str,
        fencing_token: int,
        now_epoch: float,
    ) -> None:
        if (
            row["owner_id"] != owner_id
            or row["fencing_token"] != fencing_token
            or row["lease_expires_at"] <= now_epoch
        ):
            raise LeaseLost("Lease ownership or fencing token is no longer valid")

    def claim(
        self,
        key: RunKey,
        *,
        owner_id: str,
        lease_for: timedelta,
        now: datetime | None = None,
    ) -> ClaimResult:
        if not isinstance(key, RunKey):
            raise TypeError("key must be a RunKey")
        owner_id = _owner(owner_id)
        instant = _utc(now)
        now_epoch = instant.timestamp()
        lease_until = now_epoch + _lease_seconds(lease_for)
        with self._transaction() as connection:
            row = self._select(connection, key)
            if row is None:
                state = RunState.INTENT if key.provider is Provider.CAMS else RunState.CLAIMED
                empty = "{}"
                connection.execute(
                    """
                    INSERT INTO runs (
                        provider, source_run_id, request_hash, state, checkpoint_json,
                        owner_id, fencing_token, lease_expires_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        key.provider.value,
                        key.source_run_id,
                        key.request_hash,
                        state.value,
                        empty,
                        owner_id,
                        lease_until,
                        now_epoch,
                        now_epoch,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO transitions (
                        provider, source_run_id, request_hash, from_state, to_state,
                        checkpoint_json, owner_id, fencing_token, occurred_at
                    ) VALUES (?, ?, ?, NULL, ?, ?, ?, 1, ?)
                    """,
                    (
                        key.provider.value,
                        key.source_run_id,
                        key.request_hash,
                        state.value,
                        empty,
                        owner_id,
                        now_epoch,
                    ),
                )
                row = self._select(connection, key)
                return ClaimResult(True, ClaimDisposition.CREATED, self._record(row))

            if row["lease_expires_at"] > now_epoch:
                return ClaimResult(False, ClaimDisposition.HELD_BY_OTHER, self._record(row))

            next_fence = row["fencing_token"] + 1
            connection.execute(
                """
                UPDATE runs
                SET owner_id=?, fencing_token=?, lease_expires_at=?, updated_at=?
                WHERE provider=? AND source_run_id=? AND request_hash=?
                """,
                (
                    owner_id,
                    next_fence,
                    lease_until,
                    now_epoch,
                    key.provider.value,
                    key.source_run_id,
                    key.request_hash,
                ),
            )
            row = self._select(connection, key)
            return ClaimResult(True, ClaimDisposition.TAKEOVER_AFTER_EXPIRY, self._record(row))

    def renew_lease(
        self,
        key: RunKey,
        *,
        owner_id: str,
        fencing_token: int,
        lease_for: timedelta,
        now: datetime | None = None,
    ) -> RunRecord:
        if not isinstance(key, RunKey):
            raise TypeError("key must be a RunKey")
        owner_id = _owner(owner_id)
        fencing_token = _fence(fencing_token)
        instant = _utc(now)
        now_epoch = instant.timestamp()
        requested_until = now_epoch + _lease_seconds(lease_for)
        with self._transaction() as connection:
            row = self._select(connection, key)
            if row is None:
                raise RunNotFound("Weather run does not exist")
            self._require_owned(row, owner_id=owner_id, fencing_token=fencing_token, now_epoch=now_epoch)
            lease_until = max(row["lease_expires_at"], requested_until)
            connection.execute(
                """
                UPDATE runs
                SET lease_expires_at=?, updated_at=?
                WHERE provider=? AND source_run_id=? AND request_hash=?
                  AND owner_id=? AND fencing_token=? AND lease_expires_at>?
                """,
                (
                    lease_until,
                    now_epoch,
                    key.provider.value,
                    key.source_run_id,
                    key.request_hash,
                    owner_id,
                    fencing_token,
                    now_epoch,
                ),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise LeaseLost("Lease ownership or fencing token is no longer valid")
            return self._record(self._select(connection, key))

    def release_lease(
        self,
        key: RunKey,
        *,
        owner_id: str,
        fencing_token: int,
        now: datetime | None = None,
    ) -> bool:
        """Expire only the caller's still-live fenced lease.

        Returning ``False`` is intentional: a worker that has already lost its
        fence must not be able to shorten the successor's lease.  The durable
        lifecycle state and transition history are left untouched, so another
        attempt can resume from the last committed edge immediately.
        """

        if not isinstance(key, RunKey):
            raise TypeError("key must be a RunKey")
        owner_id = _owner(owner_id)
        fencing_token = _fence(fencing_token)
        instant = _utc(now)
        now_epoch = instant.timestamp()
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE runs
                SET lease_expires_at=?, updated_at=?
                WHERE provider=? AND source_run_id=? AND request_hash=?
                  AND owner_id=? AND fencing_token=? AND lease_expires_at>?
                """,
                (
                    now_epoch,
                    now_epoch,
                    key.provider.value,
                    key.source_run_id,
                    key.request_hash,
                    owner_id,
                    fencing_token,
                    now_epoch,
                ),
            )
            return cursor.rowcount == 1

    def transition_cams(
        self,
        key: RunKey,
        *,
        owner_id: str,
        fencing_token: int,
        expected_state: CamsState,
        target_state: CamsState,
        checkpoint: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> TransitionResult:
        if not isinstance(key, RunKey):
            raise TypeError("key must be a RunKey")
        if key.provider is not Provider.CAMS:
            raise InvalidTransition("CAMS transitions require a CAMS run key")
        owner_id = _owner(owner_id)
        fencing_token = _fence(fencing_token)
        expected = _enum(expected_state, CamsState, "Unsupported expected CAMS state")
        target = _enum(target_state, CamsState, "Unsupported target CAMS state")
        if _CAMS_EDGES.get(expected) is not target:
            raise InvalidTransition("CAMS state transition is not monotonic")
        patch, _ = _checkpoint(checkpoint)
        instant = _utc(now)
        now_epoch = instant.timestamp()

        with self._transaction() as connection:
            row = self._select(connection, key)
            if row is None:
                raise RunNotFound("Weather run does not exist")
            self._require_owned(row, owner_id=owner_id, fencing_token=fencing_token, now_epoch=now_epoch)
            current = RunState(row["state"])
            current_checkpoint = json.loads(row["checkpoint_json"])
            merged = _merge_checkpoint(current_checkpoint, patch)
            _validate_cams_checkpoint(target, merged, key=key)

            if current.value == target.value:
                if merged != current_checkpoint:
                    raise StateConflict("An already committed state cannot be changed")
                return TransitionResult(False, self._record(row))
            if current.value != expected.value:
                raise StateConflict("Durable CAMS state differs from the expected state")

            _, encoded = _checkpoint(merged)
            cursor = connection.execute(
                """
                UPDATE runs
                SET state=?, checkpoint_json=?, updated_at=?
                WHERE provider=? AND source_run_id=? AND request_hash=?
                  AND state=? AND owner_id=? AND fencing_token=? AND lease_expires_at>?
                """,
                (
                    target.value,
                    encoded,
                    now_epoch,
                    key.provider.value,
                    key.source_run_id,
                    key.request_hash,
                    expected.value,
                    owner_id,
                    fencing_token,
                    now_epoch,
                ),
            )
            if cursor.rowcount != 1:
                raise LeaseLost("Lease ownership or fencing token is no longer valid")
            connection.execute(
                """
                INSERT INTO transitions (
                    provider, source_run_id, request_hash, from_state, to_state,
                    checkpoint_json, owner_id, fencing_token, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key.provider.value,
                    key.source_run_id,
                    key.request_hash,
                    expected.value,
                    target.value,
                    encoded,
                    owner_id,
                    fencing_token,
                    now_epoch,
                ),
            )
            return TransitionResult(True, self._record(self._select(connection, key)))

    def get(self, key: RunKey) -> RunRecord | None:
        if not isinstance(key, RunKey):
            raise TypeError("key must be a RunKey")
        connection = self._connect()
        try:
            row = self._select(connection, key)
            return None if row is None else self._record(row)
        finally:
            connection.close()

    def history(self, key: RunKey) -> tuple[TransitionRecord, ...]:
        if not isinstance(key, RunKey):
            raise TypeError("key must be a RunKey")
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT * FROM transitions
                WHERE provider=? AND source_run_id=? AND request_hash=?
                ORDER BY sequence
                """,
                (key.provider.value, key.source_run_id, key.request_hash),
            ).fetchall()
            return tuple(
                TransitionRecord(
                    sequence=row["sequence"],
                    key=key,
                    from_state=None if row["from_state"] is None else RunState(row["from_state"]),
                    to_state=RunState(row["to_state"]),
                    checkpoint=json.loads(row["checkpoint_json"]),
                    owner_id=row["owner_id"],
                    fencing_token=row["fencing_token"],
                    occurred_at=datetime.fromtimestamp(row["occurred_at"], timezone.utc),
                )
                for row in rows
            )
        finally:
            connection.close()

    def storage_settings(self) -> dict[str, int | str]:
        """Expose only non-sensitive durability settings for local assertions."""
        connection = self._connect()
        try:
            return {
                "journal_mode": str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower(),
                "synchronous": int(connection.execute("PRAGMA synchronous").fetchone()[0]),
                "foreign_keys": int(connection.execute("PRAGMA foreign_keys").fetchone()[0]),
                "user_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
            }
        finally:
            connection.close()

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> "SqliteStateStore":
        if self._closed:
            raise RuntimeError("SQLite state store is closed")
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
