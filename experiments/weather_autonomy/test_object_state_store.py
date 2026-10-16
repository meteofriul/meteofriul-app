from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from local_pipeline.contracts import Provider, RunKey, LeaseLost, StateConflict
from local_pipeline.object_state_store import ObjectStateStore
from local_pipeline.sqlite_object_store import SQLiteObjectStore, PreconditionFailed, ObjectStoreError


class ObjectStateTests(TestCase):
    def test_expired_remote_commit_never_returns_ownership(self):
        with patch("local_pipeline.object_state_store.monotonic", side_effect=[0, 0, 61]):
            with self.assertRaises(LeaseLost):
                self.claim(self.state, "one")
        self.assertTrue(self.claim(self.state, "two", 62).acquired)

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.objects = SQLiteObjectStore(Path(self.tmp.name) / "objects.sqlite")
        self.state = ObjectStateStore(self.objects)
        self.key = RunKey(Provider.CAMS, "20260906T000000Z", "a" * 64)
        self.now = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)

    def claim(self, store, owner, seconds=0):
        return store.claim(self.key, owner_id=owner, lease_for=timedelta(seconds=60),
                           now=self.now + timedelta(seconds=seconds))

    def test_restart_retains_claim(self):
        first = self.claim(self.state, "one")
        restarted = ObjectStateStore(self.objects)
        self.assertEqual(restarted.get(self.key), first.record)
        self.assertFalse(self.claim(restarted, "two").acquired)

    def test_takeover_fences_previous_owner(self):
        first = self.claim(self.state, "one")
        second = self.claim(self.state, "two", 61)
        self.assertGreater(second.record.fencing_token, first.record.fencing_token)
        with self.assertRaises(LeaseLost):
            self.state.renew_lease(self.key, owner_id="one",
                fencing_token=first.record.fencing_token, lease_for=timedelta(seconds=60),
                now=self.now + timedelta(seconds=62))

    def test_cas_conflict_is_bounded(self):
        objects = Mock(wraps=self.objects)
        objects.compare_and_swap.side_effect = PreconditionFailed("state")
        with self.assertRaises(StateConflict):
            self.claim(ObjectStateStore(objects), "one")
        self.assertEqual(objects.compare_and_swap.call_count, 3)
        self.assertIsNone(self.state.get(self.key))

    def test_ambiguous_write_does_not_retry(self):
        objects = Mock(wraps=self.objects)
        objects.compare_and_swap.side_effect = ObjectStoreError("timeout")
        with self.assertRaises(ObjectStoreError):
            self.claim(ObjectStateStore(objects), "one")
        objects.compare_and_swap.assert_called_once()

    def test_two_simultaneous_workers_have_one_owner(self):
        barrier = Barrier(2)
        def attempt(owner):
            barrier.wait()
            return self.claim(ObjectStateStore(self.objects), owner)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ("one", "two")))
        self.assertEqual(sum(result.acquired for result in results), 1)
        winner = next(result.record.owner_id for result in results if result.acquired)
        self.assertEqual(self.state.get(self.key).owner_id, winner)


if __name__ == "__main__":
    main()
