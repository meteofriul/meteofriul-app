"""Per-run durable state snapshots with object-store compare-and-swap.

Reuses the tested SQLite state machine in an ephemeral scratch directory.
Every mutation publishes one complete snapshot conditionally; local WAL files
never serve as durable cloud state. No SQLite file is mounted over a network.
This adapter requires real provider concurrency tests before deployment.
"""
import hashlib
from datetime import datetime, timedelta, timezone
from time import monotonic
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from .contracts import RunKey, RunRecord, ClaimResult, TransitionResult, LeaseLost, StateConflict, StateStoreError
from .sqlite_object_store import ObjectNotFound, PreconditionFailed
from .sqlite_state import SqliteStateStore

MAX_STATE_BYTES = 1024 * 1024


class ObjectStateStore:
    def __init__(self, objects):
        self.objects = objects

    @staticmethod
    def _key(key):
        if not isinstance(key, RunKey):
            raise TypeError("RunKey required")
        identity = "\n".join((key.provider.value, key.source_run_id, key.request_hash))
        return "state/runs/" + hashlib.sha256(identity.encode()).hexdigest() + ".sqlite"

    def _execute(self, method, key, *, mutate, **kwargs):
        object_key = self._key(key)
        started = monotonic()
        base_now = kwargs.get("now") or datetime.now(timezone.utc)
        def effective_now():
            return base_now + timedelta(seconds=max(0, monotonic() - started))
        for _ in range(3):
            try:
                previous = self.objects.get(object_key)
            except ObjectNotFound:
                previous = None
            with TemporaryDirectory(prefix="meteofriul-state-") as scratch:
                path = Path(scratch) / "state.sqlite"
                if previous is not None:
                    if not 1 <= len(previous.body) <= MAX_STATE_BYTES:
                        raise StateStoreError("remote state size invalid")
                    if not previous.body.startswith(b"SQLite format 3\x00"):
                        raise StateStoreError("remote state format invalid")
                    path.write_bytes(previous.body)
                with SqliteStateStore(path) as local:
                    if mutate:
                        kwargs["now"] = effective_now()
                    result = getattr(local, method)(key, **kwargs)
                    if not mutate:
                        return result
                    with closing(sqlite3.connect(path)) as connection:
                        snapshot = connection.serialize()
                if len(snapshot) > MAX_STATE_BYTES:
                    raise StateStoreError("remote state exceeds size limit")
                try:
                    self.objects.compare_and_swap(object_key, snapshot,
                        expected_etag=previous.etag if previous else None,
                        content_type="application/vnd.sqlite3")
                    record = result.record if isinstance(result, ClaimResult) and result.acquired else result
                    if isinstance(result, TransitionResult):
                        record = result.record
                    if isinstance(record, RunRecord) and record.lease_expires_at <= effective_now():
                        raise LeaseLost("lease expired during remote state commit")
                    return result
                except PreconditionFailed:
                    # Re-run the state transition against the winning snapshot.
                    # No result/lease from the losing transaction is returned.
                    continue
        raise StateConflict("remote state changed repeatedly")

    def claim(self, key, **kwargs):
        return self._execute("claim", key, mutate=True, **kwargs)

    def renew_lease(self, key, **kwargs):
        return self._execute("renew_lease", key, mutate=True, **kwargs)

    def release_lease(self, key, **kwargs):
        return self._execute("release_lease", key, mutate=True, **kwargs)

    def transition_cams(self, key, **kwargs):
        return self._execute("transition_cams", key, mutate=True, **kwargs)

    def get(self, key):
        return self._execute("get", key, mutate=False)

    def history(self, key):
        return self._execute("history", key, mutate=False)
