"""Small SQLite-backed object store used by the offline publication simulator.

The store deliberately models only the object-store operations needed by the
weather pipeline: immutable creates, reads and conditional pointer updates.
There is no unconditional overwrite or delete operation.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Mapping


class ObjectStoreError(RuntimeError):
    """Base error for the local object-store simulator."""


class ObjectNotFound(KeyError, ObjectStoreError):
    """Raised when an object key does not exist."""


class PreconditionFailed(ObjectStoreError):
    """A simulated HTTP 412 from a failed create-only or CAS operation."""

    status_code = 412
    http_status = 412
    code = "PreconditionFailed"

    def __init__(self, key: str, message: str = "object precondition failed") -> None:
        super().__init__(f"{message}: {key}")
        self.key = key


@dataclass(frozen=True)
class ObjectHead:
    key: str
    byte_length: int
    sha256: str
    etag: str
    content_type: str
    metadata: dict[str, str]

    @property
    def size(self) -> int:
        return self.byte_length


@dataclass(frozen=True)
class StoredObject:
    body: bytes
    head: ObjectHead

    @property
    def key(self) -> str:
        return self.head.key

    @property
    def byte_length(self) -> int:
        return self.head.byte_length

    @property
    def size(self) -> int:
        return self.head.byte_length

    @property
    def sha256(self) -> str:
        return self.head.sha256

    @property
    def etag(self) -> str:
        return self.head.etag

    @property
    def content_type(self) -> str:
        return self.head.content_type

    @property
    def metadata(self) -> dict[str, str]:
        return dict(self.head.metadata)


def _canonical_metadata(metadata: Mapping[str, object] | None) -> tuple[dict[str, str], str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in (metadata or {}).items():
        key = str(raw_key).strip()
        if not key or any(ord(char) < 32 for char in key):
            raise ValueError("object metadata key is empty or contains a control character")
        if raw_value is None:
            raise ValueError(f"object metadata value is null: {key}")
        value = str(raw_value)
        if any(ord(char) < 32 and char not in "\t" for char in value):
            raise ValueError(f"object metadata contains a control character: {key}")
        normalized[key] = value
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return normalized, encoded


def _body_bytes(body: bytes | bytearray | memoryview) -> bytes:
    if not isinstance(body, (bytes, bytearray, memoryview)):
        raise TypeError("object body must be bytes-like")
    return bytes(body)


def _object_hashes(body: bytes, content_type: str, metadata_json: str) -> tuple[str, str]:
    body_sha256 = hashlib.sha256(body).hexdigest()
    envelope = (
        len(body).to_bytes(8, "big")
        + body
        + b"\x00"
        + content_type.encode("utf-8")
        + b"\x00"
        + metadata_json.encode("utf-8")
    )
    etag = '"sha256-' + hashlib.sha256(envelope).hexdigest() + '"'
    return body_sha256, etag


class SQLiteObjectStore:
    """Durable local object store with create-only writes and atomic CAS.

    A separate file must be used for pipeline state. Passing its path is
    optional, but when supplied the constructor fails closed if both paths are
    the same.
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        state_database_path: str | Path | None = None,
        state_db_path: str | Path | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if state_database_path is not None and state_db_path is not None:
            raise ValueError("provide only one state database path")
        raw_path = str(database_path)
        if raw_path == ":memory:" or raw_path.startswith("file:"):
            raise ValueError("object store requires a durable filesystem database")
        self.database_path = Path(database_path).expanduser().resolve()
        state_path = state_database_path if state_database_path is not None else state_db_path
        if state_path is not None and self.database_path == Path(state_path).expanduser().resolve():
            raise ValueError("object store database must be separate from state database")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=self.timeout_seconds,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=" + str(int(self.timeout_seconds * 1000)))
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with closing(sqlite3.connect(self.database_path, timeout=self.timeout_seconds)) as connection:
            mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                raise ObjectStoreError("SQLite WAL mode could not be enabled")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS objects (
                    object_key TEXT PRIMARY KEY,
                    body BLOB NOT NULL,
                    byte_length INTEGER NOT NULL CHECK (byte_length >= 0),
                    sha256 TEXT NOT NULL,
                    etag TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    generation INTEGER NOT NULL CHECK (generation >= 1)
                ) WITHOUT ROWID
                """
            )
            connection.commit()

    @staticmethod
    def _key(value: object) -> str:
        key = str(value or "")
        if not key or key != key.strip() or "\x00" in key or any(ord(char) < 32 for char in key):
            raise ValueError("object key is empty or invalid")
        return key

    @staticmethod
    def _content_type(value: object) -> str:
        content_type = str(value or "").strip()
        if not content_type or any(ord(char) < 32 for char in content_type):
            raise ValueError("content type is empty or invalid")
        return content_type

    @staticmethod
    def _head_from_row(row: sqlite3.Row) -> ObjectHead:
        metadata = json.loads(row["metadata_json"])
        if not isinstance(metadata, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in metadata.items()
        ):
            raise ObjectStoreError(f"stored metadata is invalid: {row['object_key']}")
        return ObjectHead(
            key=row["object_key"],
            byte_length=int(row["byte_length"]),
            sha256=row["sha256"],
            etag=row["etag"],
            content_type=row["content_type"],
            metadata=dict(metadata),
        )

    def put(
        self,
        key: str,
        body: bytes | bytearray | memoryview,
        *,
        content_type: str = "application/octet-stream",
        metadata: Mapping[str, object] | None = None,
    ) -> ObjectHead:
        """Create an object; an existing key always produces simulated 412."""

        object_key = self._key(key)
        payload = _body_bytes(body)
        normalized_content_type = self._content_type(content_type)
        normalized_metadata, metadata_json = _canonical_metadata(metadata)
        body_sha256, etag = _object_hashes(payload, normalized_content_type, metadata_json)
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    """
                    INSERT INTO objects (
                        object_key, body, byte_length, sha256, etag,
                        content_type, metadata_json, generation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        object_key,
                        sqlite3.Binary(payload),
                        len(payload),
                        body_sha256,
                        etag,
                        normalized_content_type,
                        metadata_json,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise PreconditionFailed(object_key, "create-only object already exists") from error
        return ObjectHead(
            key=object_key,
            byte_length=len(payload),
            sha256=body_sha256,
            etag=etag,
            content_type=normalized_content_type,
            metadata=normalized_metadata,
        )

    put_create_only = put

    def compare_and_swap(
        self,
        key: str,
        body: bytes | bytearray | memoryview,
        *,
        expected_etag: str | None,
        content_type: str = "application/octet-stream",
        metadata: Mapping[str, object] | None = None,
    ) -> ObjectHead:
        """Atomically create-if-absent or replace only the expected generation."""

        object_key = self._key(key)
        payload = _body_bytes(body)
        normalized_content_type = self._content_type(content_type)
        normalized_metadata, metadata_json = _canonical_metadata(metadata)
        body_sha256, etag = _object_hashes(payload, normalized_content_type, metadata_json)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT etag, generation FROM objects WHERE object_key = ?",
                (object_key,),
            ).fetchone()
            if expected_etag is None:
                if current is not None:
                    raise PreconditionFailed(object_key, "CAS expected an absent object")
                connection.execute(
                    """
                    INSERT INTO objects (
                        object_key, body, byte_length, sha256, etag,
                        content_type, metadata_json, generation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        object_key,
                        sqlite3.Binary(payload),
                        len(payload),
                        body_sha256,
                        etag,
                        normalized_content_type,
                        metadata_json,
                    ),
                )
            else:
                if current is None or current["etag"] != expected_etag:
                    raise PreconditionFailed(object_key, "CAS ETag does not match")
                cursor = connection.execute(
                    """
                    UPDATE objects
                    SET body = ?, byte_length = ?, sha256 = ?, etag = ?,
                        content_type = ?, metadata_json = ?, generation = generation + 1
                    WHERE object_key = ? AND etag = ?
                    """,
                    (
                        sqlite3.Binary(payload),
                        len(payload),
                        body_sha256,
                        etag,
                        normalized_content_type,
                        metadata_json,
                        object_key,
                        expected_etag,
                    ),
                )
                if cursor.rowcount != 1:
                    raise PreconditionFailed(object_key, "CAS ETag changed concurrently")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        # Return the generation committed by this CAS. A following CAS may have
        # advanced the mutable key before the caller performs another read.
        return ObjectHead(
            key=object_key,
            byte_length=len(payload),
            sha256=body_sha256,
            etag=etag,
            content_type=normalized_content_type,
            metadata=normalized_metadata,
        )

    cas = compare_and_swap

    def head(self, key: str) -> ObjectHead:
        object_key = self._key(key)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT object_key, byte_length, sha256, etag, content_type, metadata_json
                FROM objects WHERE object_key = ?
                """,
                (object_key,),
            ).fetchone()
        if row is None:
            raise ObjectNotFound(object_key)
        return self._head_from_row(row)

    def get(self, key: str) -> StoredObject:
        object_key = self._key(key)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT object_key, body, byte_length, sha256, etag, content_type, metadata_json
                FROM objects WHERE object_key = ?
                """,
                (object_key,),
            ).fetchone()
        if row is None:
            raise ObjectNotFound(object_key)
        body = bytes(row["body"])
        head = self._head_from_row(row)
        if len(body) != head.byte_length or hashlib.sha256(body).hexdigest() != head.sha256:
            raise ObjectStoreError(f"stored object integrity check failed: {object_key}")
        return StoredObject(body=body, head=head)

    def exists(self, key: str) -> bool:
        try:
            self.head(key)
        except ObjectNotFound:
            return False
        return True

    def list_keys(self, prefix: str = "") -> list[str]:
        with closing(self._connect()) as connection:
            if prefix:
                rows = connection.execute(
                    """
                    SELECT object_key FROM objects
                    WHERE substr(object_key, 1, ?) = ?
                    ORDER BY object_key
                    """,
                    (len(prefix), prefix),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT object_key FROM objects ORDER BY object_key"
                ).fetchall()
        return [row["object_key"] for row in rows]

    def sqlite_durability(self) -> dict[str, str | int]:
        with closing(self._connect()) as connection:
            journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
        return {"journal_mode": journal_mode, "synchronous": synchronous}

    def close(self) -> None:
        """Compatibility no-op: operations use short-lived connections."""

    def __enter__(self) -> "SQLiteObjectStore":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()


SqliteObjectStore = SQLiteObjectStore


__all__ = [
    "ObjectHead",
    "ObjectNotFound",
    "ObjectStoreError",
    "PreconditionFailed",
    "SQLiteObjectStore",
    "SqliteObjectStore",
    "StoredObject",
]
