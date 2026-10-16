"""Persistence/transaction regressions for the isolated local Community only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest

from app.repositories.community import CommunityRepositoryUnavailable
from app.repositories.pilot_community import (
    PILOT_STATE_FIELDS, PilotMemoryCommunityRepository,
)
from app.repositories.pilot_community_sqlite import PilotSQLiteCommunityRepository


NOW = 1_789_900_000.0


def report(identifier="report-1"):
    return {
        "id": identifier, "owner_key": "hashed-installation", "group_id": "group-1",
        "istat_code": "093033", "type_id": "rain", "place": "Pordenone",
        "lat": 45.9567, "lon": 12.6605,
        "created_at": NOW, "expires_at": NOW + 3600,
    }


class PilotCommunitySQLiteTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="mf-pilot-sqlite-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "private" / "state.sqlite3"
        self.repositories = []
        self.clock = NOW
        self.addCleanup(lambda: [repo.close() for repo in self.repositories])

    def repository(self):
        repo = PilotSQLiteCommunityRepository(self.path)
        self.repositories.append(repo)
        return repo

    def database_connection(self):
        connection = sqlite3.connect(self.path)
        self.addCleanup(connection.close)
        return connection

    def service(self):
        from app.services.pilot_community import PilotCommunityService
        from tests.test_pilot_community import FixtureGeography

        return PilotCommunityService(
            repository=self.repository(), geography=FixtureGeography(),
            now=lambda: self.clock,
        )

    def create_command(self, **changes):
        from app.services.community import COMMUNITY_GUIDELINES_POLICY_VERSION
        from app.services.pilot_community import PilotCommunityReportCreate

        return PilotCommunityReportCreate(**{
            "type_id": "rain", "client_id": "private-installation-raw-id",
            "operation_id": "create-operation-0001", "istat_code": "093033",
            "selected_place": "Pordenone", "lat": 45.95793217, "lon": 12.66289321,
            "accuracy_m": 17.31, "age_ms": 982.71,
            "accepted_terms": True, "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
            **changes,
        })

    def update_command(self, **changes):
        from app.services.pilot_community import PilotCommunityObservationUpdate

        values = self.create_command().model_dump()
        values = {key: value for key, value in values.items() if key in PilotCommunityObservationUpdate.model_fields}
        return PilotCommunityObservationUpdate(**{
            **values, "operation_id": "update-operation-0001", "expected_revision": 1,
            **changes,
        })

    def test_real_create_lost_response_replays_after_service_restart_without_duplicate(self):
        service = self.service()
        command = self.create_command()
        first = service.create_report(command, client_host="pilot")
        owner = service._client_key("community-report", command.client_id)
        service.repository.close()

        restarted = self.service()
        replay = restarted.create_report(command, client_host="pilot")
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["report"], first["report"])
        self.assertEqual(replay["source"]["storage"], "sqlite")
        with restarted.repository.transaction():
            self.assertEqual(list(restarted.repository._reports), [first["report"]["id"]])
            self.assertEqual(restarted.repository._pilot_creations[owner], [NOW])
            self.assertEqual(len(restarted.repository._pilot_history[first["report"]["id"]]), 1)

    def test_accepted_operation_stays_non_executable_after_49_hours_and_restart(self):
        from app.services.pilot_community import PilotOperation

        service = self.service()
        command = self.create_command()
        accepted = service.create_report(command, client_host="pilot")
        service.repository.close()
        self.clock += 49 * 3600

        restarted = self.service()
        status = restarted.operation_status(command.operation_id, PilotOperation(client_id=command.client_id))
        self.assertEqual(status["status"], "accepted")
        self.assertTrue(status["result"]["reconciled_only"])
        self.assertEqual(status["result"]["report_id"], accepted["report"]["id"])
        self.assertNotIn("report", status["result"])
        restarted.repository.close()

        restarted_again = self.service()
        replay = restarted_again.create_report(command, client_host="pilot")
        self.assertTrue(replay["reconciled_only"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertNotIn("report", replay)
        with restarted_again.repository.transaction():
            self.assertEqual(restarted_again.repository._reports, {})
            self.assertEqual(restarted_again.repository._pilot_creations, {})
            self.assertEqual(restarted_again.repository._pilot_history, {})
            self.assertEqual(len(restarted_again.repository._pilot_operations), 1)

    def test_real_update_lost_response_reconciles_after_restart_only_for_owner(self):
        from app.services.pilot_community import PilotOperation

        service = self.service()
        created = service.create_report(self.create_command(), client_host="pilot")
        self.clock += 90
        command = self.update_command()
        first = service.update_observation(created["report"]["id"], command, client_host="pilot")
        service.repository.close()

        restarted = self.service()
        self.clock += 45
        status = restarted.operation_status(command.operation_id, PilotOperation(client_id=command.client_id))
        self.assertEqual(status["status"], "accepted")
        self.assertEqual(status["result"]["report"], first["report"])
        unknown = restarted.operation_status(command.operation_id, PilotOperation(client_id="another-installation"))
        self.assertEqual(unknown["status"], "not_found")
        replay = restarted.update_observation(created["report"]["id"], command, client_host="pilot")
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["revision"], 2)
        self.assertEqual(replay["report"]["expiresAt"], first["report"]["expiresAt"])
        with restarted.repository.transaction():
            self.assertEqual(len(restarted.repository._pilot_history[created["report"]["id"]]), 2)
            self.assertEqual(next(iter(restarted.repository._pilot_creations.values())), [NOW])

    def test_real_correction_receipt_history_and_expiry_survive_restart(self):
        from app.services.pilot_community import PilotCommunityReportCorrection

        service = self.service()
        first = service.create_report(self.create_command(), client_host="pilot")
        self.clock += 30
        command = PilotCommunityReportCorrection(**{
            **self.create_command(type_id="snow", operation_id="correct-operation-0001").model_dump(),
            "expected_revision": 1,
        })
        corrected = service.correct_observation(first["report"]["id"], command, client_host="pilot")
        service.repository.close()
        restarted = self.service()
        replay = restarted.correct_observation(first["report"]["id"], command, client_host="pilot")
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["report"], corrected["report"])
        self.assertEqual(replay["report"]["expiresAt"], first["report"]["expiresAt"])
        with restarted.repository.transaction():
            self.assertEqual(len(restarted.repository._pilot_history[first["report"]["id"]]), 2)
            self.assertEqual(next(iter(restarted.repository._pilot_creations.values())), [NOW])

    def test_real_replacement_grant_and_one_time_lineage_survive_two_restarts(self):
        from app.services.community import CommunityServiceError
        from app.services.pilot_community import PilotCommunityReportDelete

        service = self.service()
        command = self.create_command()
        first = service.create_report(command, client_host="pilot")
        withdraw = PilotCommunityReportDelete(
            client_id=command.client_id, action="replace", expected_revision=1,
            operation_id="replace-operation-0001",
        )
        retired = service.delete_report(first["report"]["id"], withdraw, client_host="pilot")
        service.repository.close()

        restarted = self.service()
        replay = restarted.delete_report(first["report"]["id"], withdraw, client_host="pilot")
        self.assertEqual(replay["replacement_token"], retired["replacement_token"])
        replacement = restarted.create_report(self.create_command(
            type_id="snow", operation_id="replace-create-operation-0001",
            replacement_token=retired["replacement_token"],
        ), client_host="pilot")
        self.assertFalse(replacement["replacement_available"])
        restarted.repository.close()

        third = self.service()
        with self.assertRaises(CommunityServiceError) as denied:
            third.delete_report(replacement["report"]["id"], PilotCommunityReportDelete(
                client_id=command.client_id, action="replace", expected_revision=1,
                operation_id="replace-operation-0002",
            ), client_host="pilot")
        self.assertEqual(denied.exception.detail["code"], "community_replacement_unavailable")
        with third.repository.transaction():
            self.assertEqual(next(iter(third.repository._pilot_creations.values())), [NOW, NOW])
            self.assertTrue(third.repository._pilot_replacements[retired["replacement_token"]]["used"])

    def test_real_denials_survive_restart_and_prevent_renewal(self):
        from app.contracts.live import CommunityReportConfirmationCreate
        from app.services.community import CommunityServiceError

        service = self.service()
        first = service.create_report(self.create_command(), client_host="pilot")
        for index in range(3):
            service.confirm_report(first["report"]["groupId"], CommunityReportConfirmationCreate(
                client_id=f"reader-{index}", vote="no",
            ), client_host="pilot")
        service.repository.close()
        restarted = self.service()
        with self.assertRaises(CommunityServiceError) as denied:
            restarted.update_observation(first["report"]["id"], self.update_command(), client_host="pilot")
        self.assertEqual(denied.exception.detail["code"], "community_observation_not_updateable")
        with restarted.repository.transaction():
            confirmation = restarted.repository.get_confirmation(first["report"]["groupId"])
            self.assertEqual(confirmation["no"], 3)
            self.assertEqual(len(confirmation["votes"]), 3)
            self.assertTrue(confirmation["map_withdrawn"])

    def test_real_persisted_payload_and_receipts_never_store_raw_gps_or_client_id(self):
        service = self.service()
        command = self.create_command()
        first = service.create_report(command, client_host="pilot")
        service.update_observation(first["report"]["id"], self.update_command(), client_host="pilot")
        service.repository.close()
        with self.database_connection() as connection:
            payload = connection.execute("SELECT payload FROM pilot_community_state").fetchone()[0]
        for private_value in (
            str(command.lat), str(command.lon), str(command.accuracy_m), str(command.age_ms),
            command.client_id, "accuracy_m", "age_ms",
        ):
            self.assertNotIn(private_value, payload)
        self.assertIn("45.9567", payload)

    def test_restart_retains_observations_and_every_protection_ledger(self):
        repo = self.repository()
        with repo.transaction():
            repo.save_report(report())
            repo.save_confirmation("group-1", {
                "yes": 0, "no": 1, "votes": {"voter-hash": "no"},
            }, NOW + 3600)
            repo._cooldowns["hashed-installation"] = NOW + 2700
            repo._flags["flag-1"] = {"count": 1, "date": datetime.fromtimestamp(NOW, timezone.utc)}
            repo._moderation["group-1"] = {"hidden": False}
            repo._source_blocks["other-owner"] = {"blocked_until": NOW + 60}
            repo._rate_limits["request-key"] = {"count": 4, "start": NOW}
            repo._reputations["hashed-installation"] = {"points": 12}
            repo._reputation_awards["award-1"] = {"status": "awarded"}
            repo._expired_observations["old-report"] = {"revision": 2, "expires_at": NOW}
            repo._update_receipts["report-1"] = {"operation_id": "update-operation-1", "result": {"revision": 2}}
            repo._pilot_requests["create"] = (NOW, 2)
            repo._pilot_creations["hashed-installation"] = [NOW - 500, NOW]
            repo._pilot_operations["hashed-installation:op-1"] = {"result": {"id": "report-1"}, "expires_at": NOW + 3600}
            repo._pilot_replacements["token-1"] = {"used": True, "source_report": "report-1", "expires_at": NOW + 3600, "lineage_id": "lineage-1"}
            repo._pilot_lineages["lineage-1"] = {"replacement_used": True}
            repo._pilot_history["report-1"] = [{"revision": 1, "action": "create", "at": NOW}]
            repo._pilot_award_cooldowns["hashed-installation"] = NOW + 2700
            expected = repo._snapshot_state()
        repo.close()

        reopened = self.repository()
        with reopened.transaction():
            self.assertEqual(reopened._snapshot_state(), expected)
            self.assertEqual(set(expected), set(PILOT_STATE_FIELDS))
            self.assertEqual(reopened._municipality_reports["093033"], {"report-1"})
            self.assertIsInstance(reopened._flags["flag-1"]["date"], datetime)
            self.assertEqual(reopened._pilot_requests["create"], (NOW, 2))
            self.assertEqual(reopened.get_report("report-1", NOW)[1], "sqlite")

    def test_two_running_instances_refresh_before_each_transaction(self):
        first, second = self.repository(), self.repository()
        with first.transaction():
            first.save_report(report("first"))
            first._pilot_creations["hashed-installation"] = [NOW]
        with second.transaction():
            self.assertIn("first", second._reports)
            second.save_report(report("second"))
            second._pilot_creations["hashed-installation"].append(NOW + 120)
        with first.transaction():
            self.assertEqual(set(first._reports), {"first", "second"})
            self.assertEqual(first._pilot_creations["hashed-installation"], [NOW, NOW + 120])

    def test_concurrent_instances_cannot_overspend_last_quota_slot(self):
        first, second = self.repository(), self.repository()
        with first.transaction():
            first._pilot_creations["owner"] = [NOW - 500, NOW - 300, NOW - 120]
        gate = Barrier(2)

        def attempt(repo, suffix):
            gate.wait(timeout=5)
            with repo.transaction():
                accepted = repo._pilot_creations["owner"]
                if len(accepted) >= 4:
                    return False
                accepted.append(NOW)
                repo._pilot_operations[suffix] = {"accepted": True}
                return True

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt, first, "a"), pool.submit(attempt, second, "b")]
            self.assertEqual(sorted(future.result(timeout=10) for future in futures), [False, True])
        with first.transaction():
            self.assertEqual(len(first._pilot_creations["owner"]), 4)
            self.assertEqual(len(first._pilot_operations), 1)

    def test_rejected_transaction_restores_memory_and_disk(self):
        repo = self.repository()
        with repo.transaction():
            repo.save_report(report())
        expected = repo._snapshot_state()
        with self.assertRaisesRegex(RuntimeError, "business_rejected"):
            with repo.transaction():
                repo._reports["report-1"]["expires_at"] += 3600
                repo._pilot_creations["owner"] = [NOW]
                repo._pilot_operations["op"] = {"accepted": True}
                raise RuntimeError("business_rejected")
        self.assertEqual(repo._snapshot_state(), expected)
        self.assertEqual(self.repository()._snapshot_state(), expected)

    def test_nested_success_does_not_commit_before_outer_success(self):
        repo = self.repository()
        with self.assertRaises(RuntimeError):
            with repo.transaction():
                repo.save_report(report())
                with repo.transaction():
                    repo._pilot_operations["nested"] = {"accepted": True}
                raise RuntimeError("outer_failure")
        self.assertEqual(self.repository()._reports, {})
        self.assertEqual(repo._pilot_operations, {})

    def test_caught_nested_failure_poisoning_matches_memory_repository(self):
        for repo in (self.repository(), PilotMemoryCommunityRepository()):
            with self.subTest(storage=repo.storage_kind):
                with self.assertRaises(CommunityRepositoryUnavailable):
                    with repo.transaction():
                        repo.save_report(report())
                        try:
                            with repo.transaction():
                                repo._pilot_creations["owner"] = [NOW]
                                raise RuntimeError("nested_failure")
                        except RuntimeError:
                            pass
                self.assertEqual(repo._reports, {})
                self.assertEqual(repo._pilot_creations, {})

    def test_storage_write_failure_does_not_acknowledge_or_keep_mutations(self):
        repo = self.repository()
        with repo.transaction():
            repo.save_report(report())
        expected = repo._snapshot_state()
        connection = self.database_connection()
        connection.execute(
            "CREATE TRIGGER reject_changes BEFORE UPDATE ON pilot_community_state "
            "BEGIN SELECT RAISE(ABORT, 'simulated_disk_failure'); END"
        )
        connection.commit()
        with self.assertRaises(CommunityRepositoryUnavailable):
            with repo.transaction():
                repo._reports["report-1"]["revision"] = 9
                repo._pilot_lineages["lineage-1"] = {"replacement_used": True}
        self.assertEqual(repo._snapshot_state(), expected)
        self.assertEqual(self.repository()._snapshot_state(), expected)

    def test_checksum_corruption_fails_closed_without_resetting_database(self):
        repo = self.repository()
        repo.close()
        with self.database_connection() as connection:
            connection.execute("UPDATE pilot_community_state SET payload = '{broken'")
        with self.assertRaises(CommunityRepositoryUnavailable):
            self.repository()
        with self.database_connection() as connection:
            self.assertEqual(connection.execute("SELECT payload FROM pilot_community_state").fetchone()[0], "{broken")

    def test_schema_from_newer_or_unrelated_store_is_not_overwritten(self):
        repo = self.repository()
        repo.close()
        with self.database_connection() as connection:
            connection.execute("PRAGMA user_version = 99")
        with self.assertRaises(CommunityRepositoryUnavailable):
            self.repository()
        with self.database_connection() as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 99)

    def test_empty_or_non_sqlite_existing_file_is_not_treated_as_fresh_state(self):
        self.path.parent.mkdir()
        for content in (b"", b"this is not a database"):
            self.path.write_bytes(content)
            with self.assertRaises(CommunityRepositoryUnavailable):
                self.repository()
            self.assertEqual(self.path.read_bytes(), content)

    def test_missing_protection_field_with_valid_checksum_is_rejected(self):
        import hashlib

        repo = self.repository()
        repo.close()
        with self.database_connection() as connection:
            encoded = json.loads(connection.execute("SELECT payload FROM pilot_community_state").fetchone()[0])
            del encoded["_pilot_operations"]
            payload = json.dumps(encoded)
            connection.execute(
                "UPDATE pilot_community_state SET payload = ?, checksum = ?",
                (payload, hashlib.sha256(payload.encode()).hexdigest()),
            )
        with self.assertRaises(CommunityRepositoryUnavailable):
            self.repository()

    def test_non_finite_or_unsupported_state_rolls_back(self):
        repo = self.repository()
        for value in (float("nan"), object()):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(CommunityRepositoryUnavailable):
                    with repo.transaction():
                        repo._pilot_operations["op"] = {"value": value}
                self.assertEqual(repo._pilot_operations, {})

    def test_closed_store_cannot_fall_back_to_memory(self):
        repo = self.repository()
        repo.close()
        with self.assertRaises(CommunityRepositoryUnavailable):
            with repo.transaction():
                repo.save_report(report())
        self.assertEqual(repo._reports, {})

    def test_process_death_after_write_before_commit_keeps_previous_state(self):
        repo = self.repository()
        with repo.transaction():
            repo.save_report(report())
            repo._pilot_creations["owner"] = [NOW]
        expected = repo._snapshot_state()
        repo.close()
        program = """
import os, sys
from app.repositories.pilot_community_sqlite import PilotSQLiteCommunityRepository
repository = PilotSQLiteCommunityRepository(sys.argv[1])
with repository.transaction():
    repository._reports.clear()
    repository._pilot_creations.clear()
    repository._write_state()
    os._exit(9)
"""
        result = subprocess.run(
            [sys.executable, "-c", program, str(self.path)],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assertEqual(self.repository()._snapshot_state(), expected)


if __name__ == "__main__":
    unittest.main()
