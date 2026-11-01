"""Durable providers with the same CAS, revision and replay boundary."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing

from .model import MarketError, encode, initial_record
from .seed import load_seed


APPLICATION_ID = 0x4D464D4B
CHUNK_BYTES = 200_000


def _unavailable(error):
    if isinstance(error, MarketError):
        return error
    return MarketError("markets_storage_unavailable", 503)


def _check_request(current, expected_revision):
    if current["revision"] != expected_revision:
        raise MarketError("markets_revision_conflict", 409, currentRevision=current["revision"])


def _check_replay(receipt, request_hash):
    if receipt["requestHash"] != request_hash:
        raise MarketError("markets_operation_conflict", 409)


class SQLiteMarketRepository:
    storage = "sqlite"

    def __init__(self, path: str | Path, *, seed: dict | None = None):
        if str(path) == ":memory:" or str(path).startswith("file:"):
            raise MarketError("markets_persistent_file_required", 503)
        self.path = Path(path).expanduser().resolve()
        existed = self.path.exists()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connection()) as db:
                db.execute("BEGIN IMMEDIATE")
                tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if not existed and not tables:
                    db.execute("CREATE TABLE current_state (id INTEGER PRIMARY KEY CHECK(id=1), payload BLOB NOT NULL, checksum TEXT NOT NULL)")
                    db.execute("CREATE TABLE revisions (revision INTEGER PRIMARY KEY, payload BLOB NOT NULL, checksum TEXT NOT NULL)")
                    db.execute("CREATE TABLE operations (id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, revision INTEGER NOT NULL)")
                    db.execute(f"PRAGMA application_id={APPLICATION_ID}")
                    db.execute("PRAGMA user_version=1")
                    record = initial_record(seed if seed is not None else load_seed())
                    payload = encode(record)
                    checksum = hashlib.sha256(payload).hexdigest()
                    db.execute("INSERT INTO current_state VALUES (1,?,?)", (payload, checksum))
                    db.execute("INSERT INTO revisions VALUES (0,?,?)", (payload, checksum))
                self._read(db)
                db.commit()
        except Exception as error:
            raise _unavailable(error) from error

    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _decode(row):
        if not row or hashlib.sha256(row[0]).hexdigest() != row[1]:
            raise MarketError("markets_store_corrupt", 503)
        value = json.loads(row[0])
        if not isinstance(value, dict) or "revision" not in value or "catalogue" not in value:
            raise MarketError("markets_store_corrupt", 503)
        return value

    def _read(self, db, revision=None):
        if db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID or db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise MarketError("markets_store_schema_invalid", 503)
        if revision is None:
            row = db.execute("SELECT payload,checksum FROM current_state WHERE id=1").fetchone()
        else:
            row = db.execute("SELECT payload,checksum FROM revisions WHERE revision=?", (revision,)).fetchone()
        return self._decode(row)

    def read(self):
        try:
            with closing(self._connection()) as db:
                return self._read(db)
        except Exception as error:
            raise _unavailable(error) from error

    def mutate(self, *, expected_revision, operation_id, request_hash, change):
        db = None
        try:
            db = self._connection()
            db.execute("BEGIN IMMEDIATE")
            receipt = db.execute("SELECT request_hash,revision FROM operations WHERE id=?", (operation_id,)).fetchone()
            if receipt:
                _check_replay({"requestHash": receipt[0]}, request_hash)
                record = self._read(db, receipt[1])
                db.commit()
                return record, True
            current = self._read(db)
            _check_request(current, expected_revision)
            record = change(current)
            payload = encode(record)
            checksum = hashlib.sha256(payload).hexdigest()
            db.execute("UPDATE current_state SET payload=?,checksum=? WHERE id=1", (payload, checksum))
            db.execute("INSERT INTO revisions VALUES (?,?,?)", (record["revision"], payload, checksum))
            db.execute("INSERT INTO operations VALUES (?,?,?)", (operation_id, request_hash, record["revision"]))
            db.commit()
            return record, False
        except Exception as error:
            if db is not None:
                db.rollback()
            raise _unavailable(error) from error
        finally:
            if db is not None:
                db.close()


class FirestoreMarketRepository:
    """Immutable chunked revisions; the small pointer and receipts commit atomically.

    Runtime never creates a cloud archive. initialize() is an explicit provisioning
    operation, deliberately not called by the API factory.
    """

    storage = "firestore"

    def __init__(self, client, *, collection="markets_archive"):
        if not collection or "/" in collection:
            raise MarketError("markets_collection_invalid", 503)
        self.db = client
        self.root = client.collection(collection)
        self.pointer = self.root.document("current")

    def _snapshot(self, ref, transaction=None):
        return ref.get(transaction=transaction, timeout=15)

    def _read_revision(self, pointer, transaction=None):
        revision, count = pointer.get("revision"), pointer.get("chunkCount")
        if type(revision) is not int or revision < 0 or type(count) is not int or not 1 <= count <= 50:
            raise MarketError("markets_store_corrupt", 503)
        parts = []
        for index in range(count):
            snapshot = self._snapshot(self.root.document(f"revision-{revision}-{index}"), transaction)
            part = (snapshot.to_dict() or {}).get("payload") if snapshot.exists else None
            if not isinstance(part, bytes):
                raise MarketError("markets_store_corrupt", 503)
            parts.append(part)
        payload = b"".join(parts)
        if hashlib.sha256(payload).hexdigest() != pointer.get("sha256"):
            raise MarketError("markets_store_corrupt", 503)
        return json.loads(payload)

    def _write_revision(self, transaction, record):
        data = encode(record)
        parts = [data[offset:offset + CHUNK_BYTES] for offset in range(0, len(data), CHUNK_BYTES)]
        pointer = {"revision": record["revision"], "chunkCount": len(parts), "sha256": hashlib.sha256(data).hexdigest()}
        for index, part in enumerate(parts):
            transaction.create(self.root.document(f'revision-{record["revision"]}-{index}'), {"payload": part})
        transaction.set(self.pointer, pointer)
        return pointer

    def initialize(self, seed):
        from google.cloud import firestore

        @firestore.transactional
        def initialize_transaction(transaction):
            if self._snapshot(self.pointer, transaction).exists:
                raise MarketError("markets_archive_already_initialized", 409)
            self._write_revision(transaction, initial_record(seed))
        initialize_transaction(self.db.transaction())

    def read(self):
        try:
            pointer = self._snapshot(self.pointer)
            if not pointer.exists:
                raise MarketError("markets_archive_not_initialized", 503)
            # Immutable chunks remain consistent even when current advances.
            return self._read_revision(pointer.to_dict())
        except Exception as error:
            raise _unavailable(error) from error

    def mutate(self, *, expected_revision, operation_id, request_hash, change):
        from google.cloud import firestore

        operation = self.root.document("operation-" + hashlib.sha256(operation_id.encode()).hexdigest())

        @firestore.transactional
        def persist(transaction):
            receipt = self._snapshot(operation, transaction)
            if receipt.exists:
                saved = receipt.to_dict()
                _check_replay(saved, request_hash)
                return self._read_revision(saved["snapshot"], transaction), True
            current_pointer = self._snapshot(self.pointer, transaction)
            if not current_pointer.exists:
                raise MarketError("markets_archive_not_initialized", 503)
            current = self._read_revision(current_pointer.to_dict(), transaction)
            _check_request(current, expected_revision)
            record = change(current)
            pointer = self._write_revision(transaction, record)
            transaction.create(operation, {"requestHash": request_hash, "snapshot": pointer})
            return record, False
        try:
            return persist(self.db.transaction())
        except Exception as error:
            raise _unavailable(error) from error


def configured_repository():
    deployed = bool(os.getenv("K_SERVICE", "").strip() or os.getenv("CLOUD_RUN_JOB", "").strip())
    mode = os.getenv("MARKETS_STORAGE", "" if deployed else "sqlite").strip().lower()
    if mode == "sqlite" and not deployed:
        default = Path(__file__).resolve().parents[3] / ".dev-logs" / "markets" / "archive.sqlite3"
        return SQLiteMarketRepository(os.getenv("MARKETS_SQLITE_PATH") or default)
    if mode == "firestore":
        try:
            expected = os.getenv("MARKETS_FIREBASE_PROJECT_ID", "").strip()
            if not expected:
                raise MarketError("markets_firestore_project_required", 503)
            from firebase_admin import firestore
            from app.infrastructure.firebase import get_firebase_app
            client = firestore.client(get_firebase_app())
            if client.project != expected:
                raise MarketError("markets_firestore_project_mismatch", 503)
            return FirestoreMarketRepository(client, collection=os.getenv("MARKETS_FIRESTORE_COLLECTION", "markets_archive"))
        except Exception as error:
            raise _unavailable(error) from error
    raise MarketError("markets_storage_configuration_invalid", 503)
