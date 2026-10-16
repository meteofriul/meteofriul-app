"""Offline tests for local durable claims, leases and CAMS transitions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import threading
import unittest

from local_pipeline.contracts import (
    CamsState,
    ClaimDisposition,
    InvalidCheckpoint,
    InvalidTransition,
    LeaseLost,
    Provider,
    RunKey,
    RunState,
    StateConflict,
)
from local_pipeline.sqlite_state import SqliteStateStore


NOW = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)
LEASE = timedelta(minutes=5)
REQUEST_ID = "12345678-1234-1234-1234-123456789abc"


def submitted_checkpoint():
    return {
        "run_date": "2026-09-03",
        "request_plan_sha256": "1" * 64,
        "request_record_sha256": "2" * 64,
        "intent_sha256": "3" * 64,
        "job_sha256": "4" * 64,
        "catalog_sha256": "5" * 64,
        "request_id": REQUEST_ID,
    }


def validated_checkpoint():
    return {
        "payload_sha256": "8" * 64,
        "payload_bytes": 4567,
        "decode_report_sha256": "9" * 64,
        "municipality_count": 215,
        "variable_count": 28,
        "hourly_instants": 97,
        "validation_sha256": "a" * 64,
        "publication_intent_at": "2026-09-03T12:00:00Z",
    }


def key(provider=Provider.CAMS, request_hash="a" * 64, run="20260903T000000Z"):
    return RunKey(provider, run, request_hash)


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="meteofriul-local-state-")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "state.sqlite"
        self.store = SqliteStateStore(self.path)
        self.addCleanup(self.store.close)


class StorageAndClaimTests(StoreTestCase):
    def test_store_enables_wal_full_sync_foreign_keys_and_schema_version(self):
        self.assertEqual(
            self.store.storage_settings(),
            {"journal_mode": "wal", "synchronous": 2, "foreign_keys": 1, "user_version": 1},
        )

    def test_exact_idempotency_key_has_one_winner_across_concurrent_connections(self):
        shared_key = key()
        first = SqliteStateStore(self.path)
        second = SqliteStateStore(self.path)
        self.addCleanup(first.close)
        self.addCleanup(second.close)
        barrier = threading.Barrier(2)

        def compete(store, owner):
            barrier.wait(timeout=5)
            return store.claim(shared_key, owner_id=owner, lease_for=LEASE, now=NOW)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(compete, first, "worker-one"),
                executor.submit(compete, second, "worker-two"),
            ]
            results = [future.result(timeout=10) for future in futures]

        self.assertEqual(sum(result.acquired for result in results), 1)
        self.assertEqual(
            {result.disposition for result in results},
            {ClaimDisposition.CREATED, ClaimDisposition.HELD_BY_OTHER},
        )
        self.assertEqual(self.store.get(shared_key).fencing_token, 1)
        self.assertEqual(len(self.store.history(shared_key)), 1)

    def test_provider_run_and_request_hash_are_all_part_of_uniqueness_key(self):
        keys = (
            key(),
            key(request_hash="b" * 64),
            key(run="20260903T120000Z"),
            key(provider=Provider.ICON),
        )
        for index, run_key in enumerate(keys):
            result = self.store.claim(run_key, owner_id=f"worker-{index}", lease_for=LEASE, now=NOW)
            self.assertTrue(result.acquired)
            self.assertEqual(result.disposition, ClaimDisposition.CREATED)
        self.assertEqual(self.store.get(keys[-1]).state, RunState.CLAIMED)
        self.assertEqual(self.store.get(keys[0]).state, RunState.INTENT)

    def test_same_attempt_cannot_reenter_while_its_lease_is_live(self):
        run_key = key()
        original = self.store.claim(run_key, owner_id="worker-one", lease_for=LEASE, now=NOW)
        repeated = self.store.claim(
            run_key,
            owner_id="worker-one",
            lease_for=timedelta(hours=1),
            now=NOW + timedelta(minutes=1),
        )
        self.assertFalse(repeated.acquired)
        self.assertEqual(repeated.disposition, ClaimDisposition.HELD_BY_OTHER)
        self.assertEqual(repeated.record.fencing_token, original.record.fencing_token)
        self.assertEqual(repeated.record.lease_expires_at, original.record.lease_expires_at)

    def test_expired_lease_can_be_taken_over_only_with_higher_fence(self):
        run_key = key()
        first = self.store.claim(run_key, owner_id="worker-one", lease_for=LEASE, now=NOW)
        held = self.store.claim(
            run_key, owner_id="worker-two", lease_for=LEASE, now=NOW + timedelta(minutes=4, seconds=59)
        )
        takeover = self.store.claim(
            run_key, owner_id="worker-two", lease_for=LEASE, now=NOW + timedelta(minutes=5)
        )
        self.assertFalse(held.acquired)
        self.assertEqual(held.disposition, ClaimDisposition.HELD_BY_OTHER)
        self.assertTrue(takeover.acquired)
        self.assertEqual(takeover.disposition, ClaimDisposition.TAKEOVER_AFTER_EXPIRY)
        self.assertEqual(takeover.record.fencing_token, first.record.fencing_token + 1)
        self.assertEqual(takeover.record.state, RunState.INTENT)

    def test_lease_renewal_is_conditional_and_never_shortens_existing_lease(self):
        run_key = key()
        claim = self.store.claim(run_key, owner_id="worker-one", lease_for=LEASE, now=NOW)
        unchanged = self.store.renew_lease(
            run_key,
            owner_id="worker-one",
            fencing_token=claim.record.fencing_token,
            lease_for=timedelta(seconds=10),
            now=NOW + timedelta(minutes=1),
        )
        extended = self.store.renew_lease(
            run_key,
            owner_id="worker-one",
            fencing_token=claim.record.fencing_token,
            lease_for=LEASE,
            now=NOW + timedelta(minutes=2),
        )
        self.assertEqual(unchanged.lease_expires_at, claim.record.lease_expires_at)
        self.assertEqual(extended.lease_expires_at, NOW + timedelta(minutes=7))
        with self.assertRaises(LeaseLost):
            self.store.renew_lease(
                run_key,
                owner_id="worker-two",
                fencing_token=claim.record.fencing_token,
                lease_for=LEASE,
                now=NOW + timedelta(minutes=2),
            )
        with self.assertRaises(LeaseLost):
            self.store.renew_lease(
                run_key,
                owner_id="worker-one",
                fencing_token=claim.record.fencing_token,
                lease_for=LEASE,
                now=NOW + timedelta(minutes=7),
            )

    def test_release_is_fenced_and_allows_an_immediate_new_attempt(self):
        run_key = key()
        first = self.store.claim(
            run_key,
            owner_id="attempt-one",
            lease_for=timedelta(minutes=15),
            now=NOW,
        )

        self.assertFalse(
            self.store.release_lease(
                run_key,
                owner_id="different-attempt",
                fencing_token=first.record.fencing_token,
                now=NOW + timedelta(seconds=1),
            )
        )
        self.assertTrue(
            self.store.release_lease(
                run_key,
                owner_id="attempt-one",
                fencing_token=first.record.fencing_token,
                now=NOW + timedelta(seconds=1),
            )
        )
        second = self.store.claim(
            run_key,
            owner_id="attempt-two",
            lease_for=timedelta(minutes=15),
            now=NOW + timedelta(seconds=1),
        )

        self.assertTrue(second.acquired)
        self.assertEqual(
            ClaimDisposition.TAKEOVER_AFTER_EXPIRY,
            second.disposition,
        )
        self.assertEqual(
            first.record.fencing_token + 1,
            second.record.fencing_token,
        )
        self.assertFalse(
            self.store.release_lease(
                run_key,
                owner_id="attempt-one",
                fencing_token=first.record.fencing_token,
                now=NOW + timedelta(seconds=2),
            )
        )
        self.assertGreater(
            self.store.get(run_key).lease_expires_at,
            NOW + timedelta(seconds=2),
        )

    def test_unknown_future_schema_version_fails_closed(self):
        import sqlite3

        self.store.close()
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA user_version=999")
            connection.commit()
        with self.assertRaisesRegex(RuntimeError, "schema version"):
            SqliteStateStore(self.path)


class CamsTransitionTests(StoreTestCase):
    def claim(self, *, owner="worker-one", at=NOW):
        return self.store.claim(key(), owner_id=owner, lease_for=LEASE, now=at)

    def move(self, expected, target, checkpoint=None, *, owner="worker-one", fence=1, at=NOW):
        return self.store.transition_cams(
            key(),
            owner_id=owner,
            fencing_token=fence,
            expected_state=expected,
            target_state=target,
            checkpoint=checkpoint,
            now=at,
        )

    def test_full_cams_state_machine_is_durable_and_checkpoints_are_cumulative(self):
        self.claim()
        submitted = self.move(CamsState.INTENT, CamsState.SUBMITTED, submitted_checkpoint())
        repeated = self.move(CamsState.INTENT, CamsState.SUBMITTED, submitted_checkpoint())
        self.move(
            CamsState.SUBMITTED,
            CamsState.READY,
            {"ready_evidence_sha256": "6" * 64},
        )
        self.move(
            CamsState.READY,
            CamsState.DOWNLOADED,
            {
                "download_record_sha256": "7" * 64,
                "artifact_sha256": "b" * 64,
                "artifact_bytes": 1234,
            },
        )
        self.move(
            CamsState.DOWNLOADED,
            CamsState.VALIDATED,
            validated_checkpoint(),
        )
        published = self.move(
            CamsState.VALIDATED,
            CamsState.PUBLISHED,
            {
                "core_manifest_sha256": "c" * 64,
                "pollen_manifest_sha256": "d" * 64,
                "family_release_sha256": "f" * 64,
                "family_latest_etag": '"family-v1"',
                "family_revision": 1,
                "core_object_count": 215,
                "pollen_object_count": 215,
                "publication_sha256": "e" * 64,
            },
        )
        self.assertTrue(submitted.changed)
        self.assertFalse(repeated.changed)
        self.assertEqual(published.record.state, RunState.PUBLISHED)
        self.assertEqual(
            published.record.checkpoint,
            {
                **submitted_checkpoint(),
                "ready_evidence_sha256": "6" * 64,
                "download_record_sha256": "7" * 64,
                "artifact_sha256": "b" * 64,
                "artifact_bytes": 1234,
                **validated_checkpoint(),
                "core_manifest_sha256": "c" * 64,
                "pollen_manifest_sha256": "d" * 64,
                "family_release_sha256": "f" * 64,
                "family_latest_etag": '"family-v1"',
                "family_revision": 1,
                "core_object_count": 215,
                "pollen_object_count": 215,
                "publication_sha256": "e" * 64,
            },
        )
        self.store.close()
        reopened = SqliteStateStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get(key()).state, RunState.PUBLISHED)
        history = reopened.history(key())
        self.assertEqual(
            [event.to_state for event in history],
            [
                RunState.INTENT,
                RunState.SUBMITTED,
                RunState.READY,
                RunState.DOWNLOADED,
                RunState.VALIDATED,
                RunState.PUBLISHED,
            ],
        )
        self.assertEqual(history[-1].checkpoint, published.record.checkpoint)

    def test_skip_backwards_and_non_cams_transitions_are_rejected(self):
        self.claim()
        for expected, target in (
            (CamsState.INTENT, CamsState.READY),
            (CamsState.SUBMITTED, CamsState.INTENT),
            (CamsState.INTENT, CamsState.INTENT),
        ):
            with self.subTest(expected=expected, target=target), self.assertRaises(InvalidTransition):
                self.move(expected, target)
        icon_key = key(provider=Provider.ICON)
        icon = self.store.claim(icon_key, owner_id="icon-worker", lease_for=LEASE, now=NOW)
        with self.assertRaises(InvalidTransition):
            self.store.transition_cams(
                icon_key,
                owner_id="icon-worker",
                fencing_token=icon.record.fencing_token,
                expected_state=CamsState.INTENT,
                target_state=CamsState.SUBMITTED,
                checkpoint={"request_id": REQUEST_ID},
                now=NOW,
            )

    def test_expected_state_conflict_and_checkpoint_rewrite_fail_closed(self):
        self.claim()
        self.move(CamsState.INTENT, CamsState.SUBMITTED, submitted_checkpoint())
        with self.assertRaises(StateConflict):
            self.move(CamsState.SUBMITTED, CamsState.READY, {"request_id": "00000000-0000-0000-0000-000000000000"})
        with self.assertRaises(StateConflict):
            self.move(
                CamsState.INTENT,
                CamsState.SUBMITTED,
                {**submitted_checkpoint(), "request_id": "00000000-0000-0000-0000-000000000000"},
            )
        with self.assertRaises(StateConflict):
            self.move(CamsState.INTENT, CamsState.SUBMITTED, {**submitted_checkpoint(), "core_object_count": 1})

    def test_required_durable_fields_and_strict_json_are_enforced(self):
        self.claim()
        for checkpoint in (
            {},
            {**submitted_checkpoint(), "request_id": "not-a-uuid"},
            {"token": "must-not-be-stored"},
        ):
            with self.subTest(checkpoint=checkpoint), self.assertRaises(InvalidCheckpoint):
                self.move(CamsState.INTENT, CamsState.SUBMITTED, checkpoint)
        self.move(CamsState.INTENT, CamsState.SUBMITTED, submitted_checkpoint())
        self.move(
            CamsState.SUBMITTED,
            CamsState.READY,
            {"ready_evidence_sha256": "6" * 64},
        )
        for checkpoint in (
            {"download_record_sha256": "7" * 64, "artifact_sha256": "short", "artifact_bytes": 1},
            {"download_record_sha256": "7" * 64, "artifact_sha256": "b" * 64, "artifact_bytes": True},
            {"download_record_sha256": "7" * 64, "artifact_sha256": "b" * 64, "artifact_bytes": 0},
        ):
            with self.subTest(checkpoint=checkpoint), self.assertRaises(InvalidCheckpoint):
                self.move(CamsState.READY, CamsState.DOWNLOADED, checkpoint)

    def test_published_requires_both_exact_215_object_projections(self):
        self.claim()
        self.move(CamsState.INTENT, CamsState.SUBMITTED, submitted_checkpoint())
        self.move(
            CamsState.SUBMITTED,
            CamsState.READY,
            {"ready_evidence_sha256": "6" * 64},
        )
        self.move(
            CamsState.READY,
            CamsState.DOWNLOADED,
            {
                "download_record_sha256": "7" * 64,
                "artifact_sha256": "b" * 64,
                "artifact_bytes": 1234,
            },
        )
        self.move(
            CamsState.DOWNLOADED,
            CamsState.VALIDATED,
            validated_checkpoint(),
        )
        publication = {
            "core_manifest_sha256": "c" * 64,
            "pollen_manifest_sha256": "d" * 64,
            "family_release_sha256": "f" * 64,
            "family_latest_etag": '"family-v1"',
            "family_revision": 1,
            "core_object_count": 215,
            "pollen_object_count": 215,
            "publication_sha256": "e" * 64,
        }
        for invalid_revision in (0, True, "1"):
            with self.subTest(invalid_revision=invalid_revision), self.assertRaisesRegex(
                InvalidCheckpoint, "positive CAMS family revision"
            ):
                self.move(
                    CamsState.VALIDATED,
                    CamsState.PUBLISHED,
                    {**publication, "family_revision": invalid_revision},
                )

        with self.assertRaisesRegex(InvalidCheckpoint, "both complete 215"):
            self.move(
                CamsState.VALIDATED,
                CamsState.PUBLISHED,
                {**publication, "pollen_object_count": 214},
            )
        self.assertEqual(RunState.VALIDATED, self.store.get(key()).state)

    def test_expired_or_stale_fence_cannot_transition_after_takeover(self):
        first = self.claim()
        takeover_at = NOW + LEASE
        second = self.store.claim(key(), owner_id="worker-two", lease_for=LEASE, now=takeover_at)
        with self.assertRaises(LeaseLost):
            self.move(
                CamsState.INTENT,
                CamsState.SUBMITTED,
                submitted_checkpoint(),
                owner="worker-one",
                fence=first.record.fencing_token,
                at=takeover_at,
            )
        transitioned = self.move(
            CamsState.INTENT,
            CamsState.SUBMITTED,
            submitted_checkpoint(),
            owner="worker-two",
            fence=second.record.fencing_token,
            at=takeover_at,
        )
        self.assertTrue(transitioned.changed)
        self.assertEqual(transitioned.record.fencing_token, 2)


class ContractValidationTests(unittest.TestCase):
    def test_run_key_rejects_unsafe_ids_and_non_sha256_hashes(self):
        for provider, run, digest in (
            ("unknown", "2026090300", "a" * 64),
            (Provider.CAMS, "../run", "a" * 64),
            (Provider.CAMS, "20260903T000000Z", "A" * 64),
            (Provider.CAMS, "20260903T000000Z", "short"),
        ):
            with self.subTest(provider=provider, run=run), self.assertRaises(ValueError):
                RunKey(provider, run, digest)


if __name__ == "__main__":
    unittest.main()
