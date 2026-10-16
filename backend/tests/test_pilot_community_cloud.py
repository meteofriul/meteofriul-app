"""No-network cloud transaction proofs with independent repository instances."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, RLock
import unittest
from unittest.mock import patch

from app.repositories.community import CommunityRepositoryUnavailable
from app.repositories.pilot_community import PILOT_STATE_FIELDS, PilotMemoryCommunityRepository
from app.repositories.pilot_community_cloud import (
    PILOT_BUCKET, PILOT_PROJECT, POINTER_COLLECTION, POINTER_DOCUMENT,
    SNAPSHOT_PREFIX, PilotCloudCommunityRepository, deserialize_state,
    read_sqlite_seed, serialize_state,
)
from app.repositories.pilot_community_sqlite import PilotSQLiteCommunityRepository
from tests import test_pilot_community_sqlite as sqlite_tests
from tests import test_community_cloud_compatibility as compatibility_tests


class FakeSnapshot:
    def __init__(self, data, version):
        self.exists = data is not None
        self.data = deepcopy(data)
        self.update_time = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=version)

    def to_dict(self):
        return deepcopy(self.data)


class FakeCloud:
    def __init__(self):
        self.project = PILOT_PROJECT
        self.name = PILOT_BUCKET
        self.pointer = None
        self.version = 0
        self.objects = {}
        self.uploads = 0
        self.updates = 0
        self.gets = 0
        self.fail_after_commit_on_update = None
        self.fail_before_commit = False
        self.fail_upload = False
        self.fail_read = False
        self.lock = RLock()

    def bucket(self, name):
        assert name == PILOT_BUCKET
        return self

    def collection(self, name):
        assert name == POINTER_COLLECTION
        return self

    def document(self, name):
        assert name == POINTER_DOCUMENT
        return self

    def blob(self, name):
        assert name.startswith(SNAPSHOT_PREFIX)
        return FakeBlob(self, name)

    def get(self, *, timeout, retry):
        assert timeout > 0 and retry is None
        with self.lock:
            self.gets += 1
            if self.fail_read:
                raise TimeoutError("simulated read failure")
            return FakeSnapshot(self.pointer, self.version)

    def create(self, data, *, timeout, retry):
        assert timeout > 0 and retry is None
        with self.lock:
            if self.pointer is not None:
                raise RuntimeError("AlreadyExists")
            self.pointer = deepcopy(data)
            self.version += 1

    @staticmethod
    def write_option(*, last_update_time):
        return last_update_time

    def update(self, data, *, option, timeout, retry):
        assert timeout > 0 and retry is None
        with self.lock:
            self.updates += 1
            if self.fail_before_commit:
                raise TimeoutError("simulated pre-commit failure")
            if self.pointer is None or option != FakeSnapshot(self.pointer, self.version).update_time:
                raise RuntimeError("FailedPrecondition")
            self.pointer = deepcopy(data)
            self.version += 1
            if self.updates == self.fail_after_commit_on_update:
                raise TimeoutError("simulated lost committed response")


class FakeBlob:
    def __init__(self, cloud, name):
        self.cloud, self.name = cloud, name
        self.generation = None

    def upload_from_string(self, data, *, content_type, if_generation_match, timeout, retry):
        assert content_type == "application/json" and if_generation_match == 0
        assert timeout > 0 and retry is None and self.cache_control == "private, no-store"
        with self.cloud.lock:
            if self.cloud.fail_upload:
                raise TimeoutError("simulated upload failure")
            if self.name in self.cloud.objects:
                raise RuntimeError("PreconditionFailed")
            self.cloud.uploads += 1
            self.generation = self.cloud.uploads
            self.cloud.objects[self.name] = (bytes(data), self.generation)

    def download_as_bytes(self, *, if_generation_match, start, end, raw_download, timeout, retry):
        assert start == 0 and raw_download is True and timeout > 0 and retry is None
        with self.cloud.lock:
            if self.cloud.fail_read:
                raise TimeoutError("simulated download failure")
            data, generation = self.cloud.objects[self.name]
            if generation != if_generation_match:
                raise RuntimeError("PreconditionFailed")
            return data[:end + 1]


class CloudFixtures:
    def setUp(self):
        self.cloud = FakeCloud()
        self.clock = sqlite_tests.NOW
        self.repositories = []
        self.addCleanup(lambda: [repo.close() for repo in self.repositories])
        self.seed(PilotMemoryCommunityRepository()._snapshot_state())

    def seed(self, state):
        return PilotCloudCommunityRepository.seed(
            firestore_client=self.cloud, storage_client=self.cloud, state=state,
        )

    def repository(self):
        repo = PilotCloudCommunityRepository(firestore_client=self.cloud, storage_client=self.cloud)
        self.repositories.append(repo)
        return repo

    service = sqlite_tests.PilotCommunitySQLiteTests.service
    create_command = sqlite_tests.PilotCommunitySQLiteTests.create_command
    update_command = sqlite_tests.PilotCommunitySQLiteTests.update_command


class CommunityCompatibilityCloudTests(unittest.TestCase):
    """Run real protocol services through immutable snapshots and pointer CAS."""

    def setUp(self):
        self.flow = compatibility_tests.CommunityCloudCompatibilityTests()
        self.flow.setUp()
        self.cloud = FakeCloud()
        PilotCloudCommunityRepository.seed(firestore_client=self.cloud, storage_client=self.cloud,
                                          state=PilotMemoryCommunityRepository()._snapshot_state())
        self.repositories = []
        self.addCleanup(lambda: [repo.close() for repo in self.repositories])
        self.reconnect()

    def reconnect(self):
        repo = PilotCloudCommunityRepository(firestore_client=self.cloud, storage_client=self.cloud)
        self.repositories.append(repo)
        self.flow.connect(repo)

    def test_restart_preserves_mixed_protocol_awards_history_and_downgrade_protection(self):
        old = self.flow.create()
        self.flow.vote(old)
        self.flow.now += 180
        upgraded = self.flow.create(kind="wind", new=True)
        self.flow.vote(upgraded, new=True)
        self.reconnect()
        self.assertEqual(2, self.flow.reputation()["points"])
        self.assertEqual(2, self.flow.reputation()["total_reports"])
        self.flow.vote(upgraded, expected=426)
        self.flow.post("reports", self.flow.create_command("author", "hail"), expected=426)
        rows = self.flow.post("history", {"client_id": "author", "istat_code": "093033"}, new=True)["reports"]
        self.assertEqual({old["report"]["id"], upgraded["report"]["id"]}, {row["id"] for row in rows})

    def test_uncertain_upgrade_commit_reconciles_without_a_second_submission_or_point(self):
        old = self.flow.create()
        self.flow.vote(old)
        self.flow.now += 180
        command = self.flow.create_command("author", "wind")
        # _charge_request commits once before the actual report transaction.
        self.cloud.fail_after_commit_on_update = self.cloud.updates + 2
        self.flow.post("reports", command, new=True, expected=503)
        self.cloud.fail_after_commit_on_update = None
        self.reconnect()
        replay = self.flow.post("reports", command, new=True)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(2, self.flow.reputation()["total_reports"])
        self.assertEqual(1, self.flow.reputation()["points"])
        self.flow.vote(replay, new=True)
        self.assertEqual(2, self.flow.reputation()["points"])


class PilotCommunityCloudRepositoryTests(CloudFixtures, unittest.TestCase):
    def test_all_21_fields_roundtrip_with_tagged_types(self):
        repo = self.repository()
        with repo.transaction():
            for field in PILOT_STATE_FIELDS:
                setattr(repo, field, {"key": {"type": "literal", "tuple": (3, 4), "set": {"a", "b"},
                                           "time": datetime.now(timezone.utc)}})
            expected = repo._snapshot_state()
        self.assertEqual(self.repository()._snapshot_state(), expected)
        self.assertEqual(len(expected), 21)

    test_two_running_instances_refresh_before_each_transaction = sqlite_tests.PilotCommunitySQLiteTests.test_two_running_instances_refresh_before_each_transaction
    test_rejected_transaction_restores_memory_and_disk = sqlite_tests.PilotCommunitySQLiteTests.test_rejected_transaction_restores_memory_and_disk
    test_nested_success_does_not_commit_before_outer_success = sqlite_tests.PilotCommunitySQLiteTests.test_nested_success_does_not_commit_before_outer_success
    test_caught_nested_failure_poisoning_matches_memory_repository = sqlite_tests.PilotCommunitySQLiteTests.test_caught_nested_failure_poisoning_matches_memory_repository
    test_non_finite_or_unsupported_state_rolls_back = sqlite_tests.PilotCommunitySQLiteTests.test_non_finite_or_unsupported_state_rolls_back
    test_closed_store_cannot_fall_back_to_memory = sqlite_tests.PilotCommunitySQLiteTests.test_closed_store_cannot_fall_back_to_memory

    def test_concurrent_last_quota_slot_commits_only_one_snapshot(self):
        first, second = self.repository(), self.repository()
        with first.transaction():
            first._pilot_creations["owner"] = [self.clock - 500, self.clock - 300, self.clock - 120]
        gate = Barrier(2)

        def attempt(repo, name):
            try:
                with repo.transaction():
                    self.assertEqual(len(repo._pilot_creations["owner"]), 3)
                    gate.wait(timeout=5)
                    repo._pilot_creations["owner"].append(self.clock)
                    repo._pilot_operations[name] = {"accepted": True}
                return "committed"
            except CommunityRepositoryUnavailable:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(attempt, first, "a"), pool.submit(attempt, second, "b")]
            self.assertEqual(sorted(job.result(timeout=10) for job in jobs), ["committed", "conflict"])
        restored = self.repository()
        self.assertEqual(len(restored._pilot_creations["owner"]), 4)
        self.assertEqual(len(restored._pilot_operations), 1)
        self.assertEqual(self.cloud.updates, 3)  # setup plus two single commit attempts

    def test_read_only_transaction_does_not_upload_or_touch_pointer(self):
        repo = self.repository()
        before = self.cloud.uploads, self.cloud.updates
        with repo.transaction():
            self.assertEqual(repo._reports, {})
        self.assertEqual((self.cloud.uploads, self.cloud.updates), before)

    def test_upload_or_pointer_failure_restores_memory_and_authoritative_state(self):
        for fault in ("fail_upload", "fail_before_commit"):
            with self.subTest(fault=fault):
                repo = self.repository()
                before = repo._snapshot_state()
                pointer_before = deepcopy(self.cloud.pointer)
                setattr(self.cloud, fault, True)
                with self.assertRaises(CommunityRepositoryUnavailable):
                    with repo.transaction():
                        repo.save_report(sqlite_tests.report())
                        repo._pilot_operations["op"] = {"accepted": True}
                setattr(self.cloud, fault, False)
                self.assertEqual(repo._snapshot_state(), before)
                self.assertEqual(self.cloud.pointer, pointer_before)
                self.assertEqual(self.repository()._snapshot_state(), before)

    def test_missing_or_corrupt_cloud_never_initializes_or_repairs_itself(self):
        initial_pointer = deepcopy(self.cloud.pointer)
        for corruption in ("missing", "schema", "project", "key", "size", "hash", "generation", "blob"):
            with self.subTest(corruption=corruption):
                self.cloud.pointer = deepcopy(initial_pointer)
                if corruption == "missing":
                    self.cloud.pointer = None
                elif corruption == "schema":
                    self.cloud.pointer["schema_version"] = 99
                elif corruption == "project":
                    self.cloud.pointer["project_id"] = "meteo-friul"
                elif corruption == "key":
                    self.cloud.pointer["snapshot_key"] = "pilot/weather/v1/secret.json"
                elif corruption == "size":
                    self.cloud.pointer["payload_bytes"] += 2
                elif corruption == "hash":
                    self.cloud.pointer["payload_sha256"] = "0" * 64
                elif corruption == "generation":
                    self.cloud.pointer["snapshot_generation"] = "9999"
                elif corruption == "blob":
                    self.cloud.pointer["snapshot_key"] = SNAPSHOT_PREFIX + "0" * 32 + ".json"
                before = self.cloud.uploads, self.cloud.updates
                with self.assertRaises(CommunityRepositoryUnavailable):
                    self.repository()
                self.assertEqual((self.cloud.uploads, self.cloud.updates), before)
        self.cloud.pointer = initial_pointer

    def test_incomplete_snapshot_even_with_valid_hash_fails_closed(self):
        pointer = self.cloud.pointer
        payload, generation = self.cloud.objects[pointer["snapshot_key"]]
        encoded = json.loads(payload)
        del encoded["_pilot_operations"]
        payload = json.dumps(encoded).encode()
        pointer["payload_bytes"] = len(payload)
        pointer["payload_sha256"] = hashlib.sha256(payload).hexdigest()
        self.cloud.objects[pointer["snapshot_key"]] = payload, generation
        with self.assertRaises(CommunityRepositoryUnavailable):
            self.repository()

    def test_seed_is_create_only_and_wrong_project_is_rejected_before_io(self):
        before = self.cloud.uploads
        with self.assertRaises(CommunityRepositoryUnavailable):
            self.seed(PilotMemoryCommunityRepository()._snapshot_state())
        self.assertEqual(self.cloud.uploads, before)
        wrong = FakeCloud()
        wrong.project = "meteo-friul"
        for firestore, storage in ((wrong, self.cloud), (self.cloud, wrong)):
            with self.assertRaises(ValueError):
                PilotCloudCommunityRepository(firestore_client=firestore, storage_client=storage)
            with self.assertRaises(ValueError):
                PilotCloudCommunityRepository.seed(firestore_client=firestore, storage_client=storage, state={})
        self.assertEqual(wrong.gets, 0)

    def test_read_failure_inside_transaction_restores_previous_memory(self):
        repo = self.repository()
        before = repo._snapshot_state()
        self.cloud.fail_read = True
        with self.assertRaises(CommunityRepositoryUnavailable):
            with repo.transaction():
                self.fail("unavailable cloud must not execute transaction body")
        self.assertEqual(repo._snapshot_state(), before)

    def test_size_limit_fails_closed_without_uploading_partial_snapshot(self):
        repo = self.repository()
        before = self.cloud.uploads
        with patch("app.repositories.pilot_community_cloud.MAX_SNAPSHOT_BYTES", len(serialize_state(repo._snapshot_state())) + 100):
            with self.assertRaises(CommunityRepositoryUnavailable):
                with repo.transaction():
                    repo._pilot_operations["large"] = {"data": "x" * 1000}
        self.assertEqual(repo._pilot_operations, {})
        self.assertEqual(self.cloud.uploads, before)


class PilotCommunityCloudServiceTests(CloudFixtures, unittest.TestCase):
    test_accepted_operation_stays_non_executable_after_49_hours_and_restart = sqlite_tests.PilotCommunitySQLiteTests.test_accepted_operation_stays_non_executable_after_49_hours_and_restart
    test_real_update_lost_response_reconciles_after_restart_only_for_owner = sqlite_tests.PilotCommunitySQLiteTests.test_real_update_lost_response_reconciles_after_restart_only_for_owner
    test_real_correction_receipt_history_and_expiry_survive_restart = sqlite_tests.PilotCommunitySQLiteTests.test_real_correction_receipt_history_and_expiry_survive_restart
    test_real_replacement_grant_and_one_time_lineage_survive_two_restarts = sqlite_tests.PilotCommunitySQLiteTests.test_real_replacement_grant_and_one_time_lineage_survive_two_restarts
    test_real_denials_survive_restart_and_prevent_renewal = sqlite_tests.PilotCommunitySQLiteTests.test_real_denials_survive_restart_and_prevent_renewal

    def test_actual_committed_lost_reply_reconciles_without_duplicate_or_quota_refund(self):
        service = self.service()
        command = self.create_command()
        self.cloud.fail_after_commit_on_update = self.cloud.updates + 2
        with self.assertRaises(CommunityRepositoryUnavailable):
            service.create_report(command, client_host="pilot")
        self.assertEqual(service.repository._reports, {})
        self.assertEqual(service.repository._pilot_creations, {})
        authoritative = self.repository()
        self.assertEqual(len(authoritative._reports), 1)
        first = next(iter(authoritative._reports.values()))
        replay = self.service().create_report(command, client_host="pilot")
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["report"]["id"], first["id"])
        self.assertEqual(replay["source"]["storage"], "pilot-cloud")
        persisted = self.repository()
        self.assertEqual(len(persisted._reports), 1)
        self.assertEqual(next(iter(persisted._pilot_creations.values())), [self.clock])
        self.assertEqual(len(persisted._pilot_history[first["id"]]), 1)

    def test_rejected_requests_charge_durably_without_creation_or_receipt(self):
        from app.services.community import CommunityServiceError

        for index in range(20):
            with self.assertRaises(CommunityServiceError) as denied:
                self.service().create_report(self.create_command(accuracy_m=501, operation_id=f"invalid-operation-{index:04d}"), client_host="pilot")
            self.assertEqual(denied.exception.status_code, 400)
        with self.assertRaises(CommunityServiceError) as limited:
            self.service().create_report(self.create_command(), client_host="pilot")
        self.assertEqual(limited.exception.status_code, 429)
        stored = self.repository()
        self.assertEqual(stored._pilot_requests["create"], (self.clock, 20))
        self.assertEqual(stored._reports, {})
        self.assertEqual(stored._pilot_creations, {})
        self.assertEqual(stored._pilot_operations, {})

    def test_serialized_snapshots_never_include_raw_gps_or_client_id(self):
        service = self.service()
        command = self.create_command()
        created = service.create_report(command, client_host="pilot")
        service.update_observation(created["report"]["id"], self.update_command(), client_host="pilot")
        for payload, _generation in self.cloud.objects.values():
            for private in (str(command.lat), str(command.lon), str(command.accuracy_m),
                            str(command.age_ms), command.client_id, "accuracy_m", "age_ms"):
                self.assertNotIn(private.encode(), payload)


class PilotCloudSeedTests(unittest.TestCase):
    def test_sqlite_import_reads_consistent_exact_state_without_modifying_file(self):
        with TemporaryDirectory(prefix="pilot-cloud-seed-test-") as directory:
            path = Path(directory) / "source.sqlite3"
            local = PilotSQLiteCommunityRepository(path)
            with local.transaction():
                local.save_report(sqlite_tests.report())
                local._pilot_creations["owner"] = [sqlite_tests.NOW]
                local._pilot_operations["permanent"] = {"accepted": True}
            expected = local._snapshot_state()
            before = path.read_bytes()
            state = read_sqlite_seed(path)
            self.assertEqual(state, expected)
            cloud = FakeCloud()
            PilotCloudCommunityRepository.seed(firestore_client=cloud, storage_client=cloud, state=state)
            imported = PilotCloudCommunityRepository(firestore_client=cloud, storage_client=cloud)
            self.assertEqual(imported._snapshot_state(), expected)
            self.assertEqual(path.read_bytes(), before)
            local.close()

    def test_bad_codec_does_not_reinterpret_missing_or_duplicate_protection_fields(self):
        payload = serialize_state(PilotMemoryCommunityRepository()._snapshot_state())
        with self.assertRaises(ValueError):
            deserialize_state(payload[:-1] + b', "_reports": null}')


if __name__ == "__main__":
    unittest.main()
