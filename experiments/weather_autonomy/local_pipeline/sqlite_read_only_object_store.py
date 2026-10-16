"""Strict read-only adapter for an existing local weather object database."""

from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from .sqlite_object_store import (
    ObjectHead,
    ObjectNotFound,
    ObjectStoreError,
    StoredObject,
)


_REQUIRED_COLUMNS = frozenset(
    {
        "object_key",
        "body",
        "byte_length",
        "sha256",
        "etag",
        "content_type",
        "metadata_json",
        "generation",
    }
)


class SQLiteReadOnlyObjectStore:
    """Read existing objects using SQLite ``mode=ro`` and ``query_only``.

    The adapter deliberately exposes no create, CAS, delete or schema setup
    method.  Every operation opens a short-lived read-only connection so a
    separately running publisher can advance ``latest`` without restarting the
    data plane.
    """

    def __init__(self, database_path: str | Path, *, timeout_seconds: float = 10.0):
        raw_path = str(database_path)
        if raw_path == ":memory:" or raw_path.startswith("file:"):
            raise ValueError("read-only object store requires a filesystem database")
        selected = Path(database_path).expanduser()
        if selected.is_symlink():
            raise ObjectStoreError("read-only object database cannot be a symbolic link")
        try:
            self.database_path = selected.resolve(strict=True)
        except OSError as error:
            raise ObjectStoreError("read-only object database is missing") from error
        if not self.database_path.is_file():
            raise ObjectStoreError("read-only object database is not a regular file")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)
        self._uri = self.database_path.as_uri() + "?mode=ro"
        self._verify_schema()

    @staticmethod
    def _key(value: object) -> str:
        key = str(value or "")
        if (
            not key
            or key != key.strip()
            or "\x00" in key
            or any(ord(character) < 32 for character in key)
        ):
            raise ValueError("object key is empty or invalid")
        return key

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                self._uri,
                uri=True,
                timeout=self.timeout_seconds,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            if int(connection.execute("PRAGMA query_only").fetchone()[0]) != 1:
                connection.close()
                raise ObjectStoreError("SQLite query-only mode was not enabled")
            return connection
        except sqlite3.Error as error:
            raise ObjectStoreError("read-only object database cannot be opened") from error

    def _verify_schema(self) -> None:
        try:
            with closing(self._connect()) as connection:
                table = connection.execute(
                    "SELECT type FROM sqlite_master WHERE name = 'objects'"
                ).fetchone()
                columns = {
                    str(row["name"])
                    for row in connection.execute("PRAGMA table_info(objects)").fetchall()
                }
        except sqlite3.Error as error:
            raise ObjectStoreError("read-only object database schema is unavailable") from error
        if table is None or table["type"] != "table" or not _REQUIRED_COLUMNS <= columns:
            raise ObjectStoreError("read-only object database schema is invalid")

    @staticmethod
    def _head_from_row(row: sqlite3.Row) -> ObjectHead:
        try:
            metadata = json.loads(row["metadata_json"])
        except (TypeError, UnicodeError, json.JSONDecodeError) as error:
            raise ObjectStoreError("stored object metadata is invalid") from error
        if not isinstance(metadata, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in metadata.items()
        ):
            raise ObjectStoreError("stored object metadata is invalid")
        return ObjectHead(
            key=row["object_key"],
            byte_length=int(row["byte_length"]),
            sha256=row["sha256"],
            etag=row["etag"],
            content_type=row["content_type"],
            metadata=dict(metadata),
        )

    def head(self, key: str) -> ObjectHead:
        object_key = self._key(key)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT object_key, byte_length, sha256, etag,
                       content_type, metadata_json
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
                SELECT object_key, body, byte_length, sha256, etag,
                       content_type, metadata_json
                FROM objects WHERE object_key = ?
                """,
                (object_key,),
            ).fetchone()
        if row is None:
            raise ObjectNotFound(object_key)
        body = bytes(row["body"])
        head = self._head_from_row(row)
        if len(body) != head.byte_length or hashlib.sha256(body).hexdigest() != head.sha256:
            raise ObjectStoreError("stored object integrity check failed")
        return StoredObject(body=body, head=head)

    def close(self) -> None:
        """Compatibility no-op: operations use short-lived connections."""

    def __enter__(self) -> "SQLiteReadOnlyObjectStore":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()


__all__ = ["SQLiteReadOnlyObjectStore"]
