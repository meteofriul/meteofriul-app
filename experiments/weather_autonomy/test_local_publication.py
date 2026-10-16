"""Offline tests for the local object store and atomic publication protocol."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

try:
    from experiments.weather_autonomy.local_pipeline.publisher import (
        ImmutableObjectConflict,
        InvalidPublication,
        LocalPublisher,
        PublicationObject,
        PublicationSizeExceeded,
        StaleRun,
    )
    from experiments.weather_autonomy.local_pipeline.sqlite_object_store import (
        PreconditionFailed,
        SQLiteObjectStore,
    )
except ModuleNotFoundError:  # unittest discovery with weather_autonomy as sys.path root
    from local_pipeline.publisher import (
        ImmutableObjectConflict,
        InvalidPublication,
        LocalPublisher,
        PublicationObject,
        PublicationSizeExceeded,
        StaleRun,
    )
    from local_pipeline.sqlite_object_store import PreconditionFailed, SQLiteObjectStore


def run_objects(label: str = "a") -> list[PublicationObject]:
    return [
        PublicationObject(
            "municipalities/030129.json",
            ('{"city":"Pordenone","sample":"' + label + '"}').encode(),
            metadata={"municipality_id": "030129"},
        ),
        PublicationObject(
            "municipalities/030006.json",
            ('{"city":"Aviano","sample":"' + label + '"}').encode(),
            metadata={"municipality_id": "030006"},
        ),
    ]


class RecordingStore:
    def __init__(self, inner: SQLiteObjectStore) -> None:
        self.inner = inner
        self.put_keys: list[str] = []
        self.cas_keys: list[str] = []

    def put(self, key, body, **kwargs):
        self.put_keys.append(key)
        return self.inner.put(key, body, **kwargs)

    def compare_and_swap(self, key, body, **kwargs):
        self.cas_keys.append(key)
        return self.inner.compare_and_swap(key, body, **kwargs)

    def __getattr__(self, name):
        return getattr(self.inner, name)


class PartialFailureStore(RecordingStore):
    def __init__(self, inner: SQLiteObjectStore, failing_run: str, fail_on_object: int) -> None:
        super().__init__(inner)
        self.failing_run = f"/runs/{failing_run}/objects/"
        self.fail_on_object = fail_on_object
        self.object_attempts = 0

    def put(self, key, body, **kwargs):
        if self.failing_run in key:
            self.object_attempts += 1
            if self.object_attempts == self.fail_on_object:
                raise OSError("synthetic interrupted upload")
        return super().put(key, body, **kwargs)


class FirstCasBarrierStore(RecordingStore):
    """Makes both publishers observe the old pointer before their first CAS."""

    def __init__(self, inner: SQLiteObjectStore) -> None:
        super().__init__(inner)
        self.barrier = threading.Barrier(2, timeout=5)
        self.lock = threading.Lock()
        self.first_call_threads: set[int] = set()

    def compare_and_swap(self, key, body, **kwargs):
        thread_id = threading.get_ident()
        should_wait = False
        if key.endswith("/latest.json"):
            with self.lock:
                if thread_id not in self.first_call_threads:
                    self.first_call_threads.add(thread_id)
                    should_wait = True
        if should_wait:
            self.barrier.wait()
        return super().compare_and_swap(key, body, **kwargs)


class SQLiteObjectStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="meteofriul-objects-")
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_database_is_durable_separate_and_create_only(self):
        object_db = self.root / "objects.sqlite3"
        state_db = self.root / "state.sqlite3"
        store = SQLiteObjectStore(object_db, state_db_path=state_db)
        self.assertNotEqual(object_db.resolve(), state_db.resolve())
        self.assertEqual(
            store.sqlite_durability(),
            {"journal_mode": "wal", "synchronous": 2},
        )
        head = store.put(
            "runs/a/data.json",
            b'{"ok":true}',
            content_type="application/json",
            metadata={"source": "fixture"},
        )
        self.assertEqual(head.byte_length, 11)
        self.assertEqual(store.head(head.key), head)
        self.assertEqual(store.get(head.key).body, b'{"ok":true}')
        with self.assertRaises(PreconditionFailed) as raised:
            store.put(head.key, b"different")
        self.assertEqual(raised.exception.status_code, 412)
        with self.assertRaises(ValueError):
            SQLiteObjectStore(object_db, state_db_path=object_db)

    def test_compare_and_swap_models_412_and_changes_etag(self):
        store = SQLiteObjectStore(self.root / "objects.sqlite3")
        first = store.compare_and_swap(
            "icon/latest.json",
            b'{"run":"1"}',
            expected_etag=None,
            content_type="application/json",
        )
        with self.assertRaises(PreconditionFailed):
            store.compare_and_swap(
                "icon/latest.json", b'{"run":"2"}', expected_etag=None
            )
        with self.assertRaises(PreconditionFailed):
            store.compare_and_swap(
                "icon/latest.json", b'{"run":"2"}', expected_etag='"wrong"'
            )
        second = store.cas(
            "icon/latest.json",
            b'{"run":"2"}',
            expected_etag=first.etag,
            content_type="application/json",
        )
        self.assertNotEqual(first.etag, second.etag)
        self.assertEqual(store.get("icon/latest.json").body, b'{"run":"2"}')


class LocalPublisherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="meteofriul-publish-")
        self.root = Path(self.temporary.name)
        self.store = SQLiteObjectStore(self.root / "objects.sqlite3")
        self.publisher = LocalPublisher(self.store)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_objects_are_verified_before_manifest_and_latest(self):
        recording = RecordingStore(self.store)
        publisher = LocalPublisher(recording)
        result = publisher.publish_run(
            "icon2i",
            "2026090300",
            run_objects(),
            expected_count=2,
            run_metadata={"model": "ICON-2I"},
        )
        self.assertEqual(recording.put_keys[-1], result.manifest_key)
        self.assertTrue(all("/objects/" in key for key in recording.put_keys[:-1]))
        self.assertEqual(recording.cas_keys, [result.latest_key])

        manifest_object = self.store.get(result.manifest_key)
        manifest = json.loads(manifest_object.body)
        self.assertEqual(manifest["expected_object_count"], 2)
        self.assertEqual(manifest["object_count"], 2)
        self.assertEqual(len(manifest["objects"]), 2)
        for entry in manifest["objects"]:
            stored = self.store.get(entry["object_key"])
            self.assertEqual(entry["byte_length"], stored.byte_length)
            self.assertEqual(entry["sha256"], stored.sha256)
            self.assertEqual(entry["etag"], stored.etag)
        self.assertEqual(self.publisher.read_latest("icon2i")["run_id"], "2026090300")

    def test_same_run_is_idempotent_without_replacing_latest(self):
        first = self.publisher.publish(
            "icon2i", "2026090300", run_objects(), expected_count=2
        )
        first_latest = self.store.head(first.latest_key)
        second = self.publisher.publish(
            "icon2i", "2026090300", run_objects(), expected_count=2
        )
        self.assertTrue(second.idempotent)
        self.assertFalse(second.latest_updated)
        self.assertEqual(first_latest.etag, self.store.head(first.latest_key).etag)
        self.assertEqual(len(self.store.list_keys("weather/v1/icon2i/")), 4)

    def test_expected_count_failure_writes_nothing(self):
        with self.assertRaises(InvalidPublication):
            self.publisher.publish(
                "icon2i", "2026090300", run_objects(), expected_count=3
            )
        self.assertEqual(self.store.list_keys(), [])

    def test_oversize_object_or_total_run_writes_nothing(self):
        recording = RecordingStore(self.store)
        object_capped = LocalPublisher(
            recording, max_object_bytes=8, max_run_bytes=32
        )
        with self.assertRaises(PublicationSizeExceeded):
            object_capped.publish(
                "icon2i",
                "2026090300",
                [
                    PublicationObject("small.bin", b"small"),
                    PublicationObject("large.bin", b"123456789"),
                ],
                expected_count=2,
            )
        self.assertEqual(recording.put_keys, [])
        self.assertEqual(recording.cas_keys, [])
        self.assertEqual(self.store.list_keys(), [])

        total_capped = LocalPublisher(
            recording, max_object_bytes=8, max_run_bytes=10
        )
        with self.assertRaises(PublicationSizeExceeded):
            total_capped.publish(
                "cams",
                "2026090300",
                [
                    PublicationObject("one.bin", b"123456"),
                    PublicationObject("two.bin", b"123456"),
                ],
                expected_count=2,
            )
        self.assertEqual(recording.put_keys, [])
        self.assertEqual(recording.cas_keys, [])
        self.assertEqual(self.store.list_keys(), [])

    def test_partial_upload_never_moves_latest_and_can_resume(self):
        self.publisher.publish("icon2i", "2026090300", run_objects("old"), expected_count=2)
        old_latest = self.publisher.read_latest("icon2i")
        failing = PartialFailureStore(self.store, "2026090306", fail_on_object=2)
        with self.assertRaisesRegex(OSError, "interrupted"):
            LocalPublisher(failing).publish(
                "icon2i", "2026090306", run_objects("new"), expected_count=2
            )
        self.assertEqual(self.publisher.read_latest("icon2i"), old_latest)
        self.assertFalse(self.store.exists(self.publisher.manifest_key("icon2i", "2026090306")))
        partial_keys = self.store.list_keys("weather/v1/icon2i/runs/2026090306/objects/")
        self.assertEqual(len(partial_keys), 1)

        resumed = self.publisher.publish(
            "icon2i", "2026090306", run_objects("new"), expected_count=2
        )
        self.assertTrue(resumed.latest_updated)
        self.assertEqual(self.publisher.read_latest("icon2i")["run_id"], "2026090306")

    def test_changed_bytes_or_manifest_for_same_run_conflict(self):
        original = self.publisher.publish(
            "icon2i",
            "2026090300",
            run_objects("original"),
            expected_count=2,
            run_metadata={"cycle": "00"},
        )
        latest_before = self.store.get(original.latest_key)
        with self.assertRaises(ImmutableObjectConflict):
            self.publisher.publish(
                "icon2i",
                "2026090300",
                run_objects("changed"),
                expected_count=2,
                run_metadata={"cycle": "00"},
            )
        self.assertEqual(self.store.get(original.latest_key), latest_before)

        # Identical objects with conflicting run metadata conflict at manifest.
        with self.assertRaises(ImmutableObjectConflict):
            self.publisher.publish(
                "icon2i",
                "2026090300",
                run_objects("original"),
                expected_count=2,
                run_metadata={"cycle": "conflict"},
            )
        self.assertEqual(self.store.get(original.latest_key), latest_before)

    def test_latest_is_monotonic_and_isolated_per_provider(self):
        self.publisher.publish("icon2i", "2026090306", run_objects("icon"), expected_count=2)
        self.publisher.publish("cams", "2026090300", run_objects("cams"), expected_count=2)
        with self.assertRaises(StaleRun):
            self.publisher.publish("icon2i", "2026090300", run_objects("old"), expected_count=2)
        self.assertEqual(self.publisher.read_latest("icon2i")["run_id"], "2026090306")
        self.assertEqual(self.publisher.read_latest("cams")["run_id"], "2026090300")

    def test_two_simultaneous_runs_finish_with_newest_pointer(self):
        barrier_store = FirstCasBarrierStore(self.store)

        def publish(run_id: str):
            try:
                return LocalPublisher(barrier_store).publish(
                    "icon2i", run_id, run_objects(run_id), expected_count=2
                )
            except StaleRun:
                return "stale"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(publish, ("2026090300", "2026090306")))
        self.assertEqual(self.publisher.read_latest("icon2i")["run_id"], "2026090306")
        self.assertTrue(any(result != "stale" for result in results))

    def test_revoke_is_immutable_idempotent_and_does_not_delete_run(self):
        published = self.publisher.publish(
            "cams", "2026090300", run_objects("cams"), expected_count=2
        )
        first = self.publisher.revoke(
            "cams", "2026090300", reason="quality gate failed"
        )
        self.assertTrue(first.latest_updated)
        latest = self.publisher.read_latest("cams")
        self.assertEqual(latest["status"], "revoked")
        self.assertEqual(latest["revocation_key"], first.revocation_key)
        self.assertTrue(self.store.exists(published.manifest_key))
        self.assertTrue(all(self.store.exists(key) for key in published.object_keys))

        second = self.publisher.revoke(
            "cams", "2026090300", reason="quality gate failed"
        )
        self.assertTrue(second.idempotent)
        self.assertFalse(second.latest_updated)
        with self.assertRaises(ImmutableObjectConflict):
            self.publisher.revoke("cams", "2026090300", reason="different reason")

    def test_sqlite_contains_no_pipeline_state_tables(self):
        self.publisher.publish("icon2i", "2026090300", run_objects(), expected_count=2)
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertEqual(tables, {"objects"})


if __name__ == "__main__":
    unittest.main()
