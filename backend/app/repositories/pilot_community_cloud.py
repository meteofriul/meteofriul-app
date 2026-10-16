"""Pilot-only snapshots committed by a conditional Firestore pointer update.

Cloud writes never retry a stale transaction. An uncertain acknowledgement is
reported as unavailable; the next transaction reloads the pointer and existing
operation receipts reconcile a write which actually committed. GCS snapshots
are private, immutable and uniquely named. Runtime never initializes state.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any
from uuid import uuid4

from app.repositories.community import CommunityRepositoryUnavailable
from app.repositories.pilot_community import PILOT_STATE_FIELDS, PilotMemoryCommunityRepository
from app.repositories.pilot_community_sqlite import (
    APPLICATION_ID, SCHEMA_VERSION, _decode, _encode, _reject_duplicate_keys,
)

PILOT_PROJECT = os.environ.get("COMMUNITY_CLOUD_PROJECT", "meteofriul-pilot-20260906")
PILOT_BUCKET = os.environ.get("COMMUNITY_DATA_BUCKET", "meteofriul-pilot-20260906-community")
POINTER_COLLECTION = os.environ.get("COMMUNITY_POINTER_COLLECTION", "pilot_community_state")
POINTER_DOCUMENT = os.environ.get("COMMUNITY_POINTER_DOCUMENT", "current")
SNAPSHOT_PREFIX = os.environ.get("COMMUNITY_SNAPSHOT_PREFIX", "pilot/community/v1/snapshots/")
POINTER_KIND = "meteofriul.community.cloud-pointer.v1"
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
CLOUD_TIMEOUT_SECONDS = 20
_POINTER_FIELDS = frozenset({
    "kind", "project_id", "bucket", "schema_version", "snapshot_key",
    "snapshot_generation", "payload_sha256", "payload_bytes",
})


def serialize_state(state: dict[str, Any]) -> bytes:
    if set(state) != set(PILOT_STATE_FIELDS) or any(not isinstance(value, dict) for value in state.values()):
        raise ValueError("invalid_pilot_store_fields")
    payload = json.dumps(
        {field: _encode(state[field]) for field in PILOT_STATE_FIELDS},
        ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError("pilot_snapshot_capacity_reached")
    return payload


def deserialize_state(payload: bytes) -> dict[str, Any]:
    if not isinstance(payload, bytes) or len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError("invalid_pilot_store_payload")
    encoded = json.loads(payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(encoded, dict) or set(encoded) != set(PILOT_STATE_FIELDS):
        raise ValueError("unsupported_pilot_store_fields")
    state = {field: _decode(encoded[field]) for field in PILOT_STATE_FIELDS}
    if any(not isinstance(value, dict) for value in state.values()):
        raise ValueError("invalid_pilot_store_field")
    return state


def read_sqlite_seed(database_path: str | Path) -> dict[str, Any]:
    """Read one consistent existing SQLite snapshot without opening a writer."""
    path = Path(database_path).resolve(strict=True)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        if (
            connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
            or connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION
        ):
            raise ValueError("unsupported_pilot_store_schema")
        rows = connection.execute(
            "SELECT id, schema_version, payload, checksum FROM pilot_community_state"
        ).fetchall()
        if len(rows) != 1 or rows[0][:2] != (1, SCHEMA_VERSION):
            raise ValueError("invalid_pilot_store_row")
        payload, checksum = rows[0][2:]
        if not isinstance(payload, str) or not isinstance(checksum, str):
            raise ValueError("invalid_pilot_store_payload")
        data = payload.encode("utf-8")
        if hashlib.sha256(data).hexdigest() != checksum:
            raise ValueError("corrupt_pilot_store_checksum")
        return deserialize_state(data)
    finally:
        connection.close()


class PilotCloudCommunityRepository(PilotMemoryCommunityRepository):
    """Keep the entire pilot transaction model; Firestore is the commit point."""

    storage_kind = "pilot-cloud"

    def __init__(self, *, firestore_client: Any, storage_client: Any):
        super().__init__()
        self._configure(firestore_client, storage_client)
        self._closed = False
        self._read_state()

    def _configure(self, firestore_client, storage_client):
        if (
            getattr(firestore_client, "project", None) != PILOT_PROJECT
            or getattr(storage_client, "project", None) != PILOT_PROJECT
        ):
            raise ValueError("isolated_pilot_project_required")
        self._firestore = firestore_client
        self._bucket = storage_client.bucket(PILOT_BUCKET)
        if self._bucket.name != PILOT_BUCKET:
            raise ValueError("private_pilot_bucket_required")
        self._pointer = firestore_client.collection(POINTER_COLLECTION).document(POINTER_DOCUMENT)

    @staticmethod
    def _validate_pointer(pointer):
        if not isinstance(pointer, dict) or set(pointer) != _POINTER_FIELDS:
            raise ValueError("invalid_pilot_pointer")
        if (
            pointer["kind"] != POINTER_KIND
            or pointer["project_id"] != PILOT_PROJECT
            or pointer["bucket"] != PILOT_BUCKET
            or type(pointer["schema_version"]) is not int
            or pointer["schema_version"] != SCHEMA_VERSION
            or not isinstance(pointer["snapshot_key"], str)
            or not re.fullmatch(re.escape(SNAPSHOT_PREFIX) + r"[a-f0-9]{32}\.json", pointer["snapshot_key"])
            or not isinstance(pointer["snapshot_generation"], str)
            or not re.fullmatch(r"[1-9][0-9]*", pointer["snapshot_generation"])
            or not isinstance(pointer["payload_sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", pointer["payload_sha256"])
            or type(pointer["payload_bytes"]) is not int
            or not 0 < pointer["payload_bytes"] <= MAX_SNAPSHOT_BYTES
        ):
            raise ValueError("invalid_pilot_pointer")

    def _read_state(self):
        try:
            snapshot = self._pointer.get(timeout=CLOUD_TIMEOUT_SECONDS, retry=None)
            if not snapshot.exists:
                raise ValueError("pilot_cloud_not_initialized")
            pointer = snapshot.to_dict()
            self._validate_pointer(pointer)
            update_time = snapshot.update_time
            if not isinstance(update_time, datetime) or update_time.tzinfo is None:
                raise ValueError("invalid_pilot_pointer_version")
            blob = self._bucket.blob(pointer["snapshot_key"])
            payload = blob.download_as_bytes(
                if_generation_match=int(pointer["snapshot_generation"]),
                start=0, end=pointer["payload_bytes"], raw_download=True,
                timeout=CLOUD_TIMEOUT_SECONDS, retry=None,
            )
            if (
                len(payload) != pointer["payload_bytes"]
                or hashlib.sha256(payload).hexdigest() != pointer["payload_sha256"]
            ):
                raise ValueError("corrupt_pilot_snapshot")
            state = deserialize_state(payload)
            self._restore_state(state)
            return payload, update_time
        except Exception as error:
            raise CommunityRepositoryUnavailable("pilot_cloud_read_failed") from error

    def _upload_snapshot(self, payload):
        blob = self._bucket.blob(SNAPSHOT_PREFIX + uuid4().hex + ".json")
        blob.cache_control = "private, no-store"
        blob.upload_from_string(
            payload, content_type="application/json", if_generation_match=0,
            timeout=CLOUD_TIMEOUT_SECONDS, retry=None,
        )
        pointer = {
            "kind": POINTER_KIND, "project_id": PILOT_PROJECT, "bucket": PILOT_BUCKET,
            "schema_version": SCHEMA_VERSION, "snapshot_key": blob.name,
            "snapshot_generation": str(blob.generation),
            "payload_sha256": hashlib.sha256(payload).hexdigest(), "payload_bytes": len(payload),
        }
        self._validate_pointer(pointer)
        return pointer

    def _commit(self, previous, update_time):
        try:
            payload = serialize_state(self._snapshot_state())
            if payload == previous:
                return
            pointer = self._upload_snapshot(payload)
            self._pointer.update(
                pointer, option=self._firestore.write_option(last_update_time=update_time),
                timeout=CLOUD_TIMEOUT_SECONDS, retry=None,
            )
        except Exception as error:
            # The upload may leave an unreferenced immutable object. It is not
            # authoritative. No deletes or stale commit retries are attempted.
            raise CommunityRepositoryUnavailable("pilot_cloud_commit_failed") from error

    @contextmanager
    def transaction(self):
        with self.lock:
            if self._closed:
                raise CommunityRepositoryUnavailable("pilot_cloud_store_closed")
            if getattr(self, "_pilot_transaction_depth", 0):
                with super().transaction():
                    yield self
                return
            before = self._snapshot_state()
            try:
                previous, update_time = self._read_state()
                before = self._snapshot_state()
                with super().transaction():
                    yield self
                self._commit(previous, update_time)
            except BaseException:
                self._restore_state(before)
                raise

    def close(self):
        with self.lock:
            if getattr(self, "_pilot_transaction_depth", 0):
                raise CommunityRepositoryUnavailable("pilot_cloud_transaction_in_progress")
            self._closed = True

    @classmethod
    def seed(cls, *, firestore_client, storage_client, state):
        """Explicit create-only import; never called by the runtime constructor."""
        repository = cls.__new__(cls)
        repository._configure(firestore_client, storage_client)
        try:
            payload = serialize_state(state)
            if repository._pointer.get(timeout=CLOUD_TIMEOUT_SECONDS, retry=None).exists:
                raise ValueError("pilot_cloud_already_initialized")
            pointer = repository._upload_snapshot(payload)
            repository._pointer.create(pointer, timeout=CLOUD_TIMEOUT_SECONDS, retry=None)
            return {"project": PILOT_PROJECT, "payload_bytes": len(payload),
                    "payload_sha256": pointer["payload_sha256"]}
        except Exception as error:
            raise CommunityRepositoryUnavailable("pilot_cloud_seed_failed") from error

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
