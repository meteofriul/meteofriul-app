import itertools
import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.pilot_community import create_app
from app.repositories.community import CommunityRepositoryUnavailable
from app.repositories.pilot_community_sqlite import PilotSQLiteCommunityRepository
from app.services.community import COMMUNITY_GUIDELINES_POLICY_VERSION, CommunityServiceError
from app.services.community_reports import CommunityReportsService, CommunityReportVote, CommunityHistoryQuery
from app.services.pilot_community import PilotCommunityReportCreate
from app.contracts.live import CommunityReputationRequest
from tests.test_pilot_community import FixtureGeography, Clock


class CommunityReportsRulesTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.clock.value = 1_800_003_600.0  # On an hourly boundary.
        self.operations = itertools.count()
        self.ids = itertools.count()
        self.service = self.make_service()
        self.client = TestClient(create_app(service=self.service), base_url="http://127.0.0.1:8783")
        self.headers = {"X-Meteo-Pilot-Community": "local-only"}

    def make_service(self, repository=None):
        return CommunityReportsService(geography=FixtureGeography(), now=self.clock,
            report_id_factory=lambda: f"report-{next(self.ids)}", repository=repository)

    def command(self, type_id="rain", client_id="author", **extra):
        return PilotCommunityReportCreate(type_id=type_id, client_id=client_id,
            lat=45.957, lon=12.661, istat_code="093033", selected_place="Pordenone",
            accuracy_m=25, age_ms=10, accepted_terms=True,
            policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION,
            operation_id=f"create-operation-{next(self.operations):08d}", **extra)

    def create(self, type_id="rain", client_id="author", service=None):
        return (service or self.service).create_report(self.command(type_id, client_id), client_host="test")

    def vote_command(self, result, client_id="witness", vote="yes", **extra):
        values = dict(vote=vote, client_id=client_id, lat=45.957, lon=12.661,
            accuracy_m=25, age_ms=10, accepted_terms=True,
            policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION,
            report_ids=[result["report"]["id"]])
        return CommunityReportVote(**{**values, **extra})

    def vote(self, result, client_id="witness", vote="yes", service=None, **extra):
        return (service or self.service).confirm_report(result["report"]["groupId"],
            self.vote_command(result, client_id, vote, **extra), client_host="test")

    def reputation(self, client_id="author", service=None):
        return (service or self.service).get_reputation(CommunityReputationRequest(client_id=client_id), client_host="test")

    def history(self, client_id="author", **extra):
        return self.service.get_history(CommunityHistoryQuery(client_id=client_id, istat_code="093033", **extra))["reports"]

    def test_submission_idempotency_and_atomic_replacement(self):
        first = self.create()
        self.clock.value += 180
        command = self.command("wind")
        second = self.service.create_report(command, client_host="test")
        self.assertEqual([first["report"]["id"]], second["replaced_report_ids"])
        self.assertEqual(1, len(self.service.repository._reports))
        self.assertEqual(2, self.reputation().total_reports)
        self.assertTrue(self.service.create_report(command, client_host="test")["idempotent_replay"])
        self.assertEqual(2, self.reputation().total_reports)
        self.assertEqual(["active", "replaced"], [r["status"] for r in self.history()])

    def test_failed_save_rolls_back_old_report_quotas_counters_and_receipt(self):
        first = self.create()
        self.clock.value += 180
        command = self.command("wind")
        with patch.object(self.service.repository, "save_report", side_effect=CommunityRepositoryUnavailable("test")):
            with self.assertRaises(CommunityRepositoryUnavailable):
                self.service.create_report(command, client_host="test")
        self.assertIn(first["report"]["id"], self.service.repository._reports)
        self.assertEqual(1, self.reputation().total_reports)
        self.assertEqual(1, len(self.history()))
        self.service.create_report(command, client_host="test")
        self.assertEqual(2, self.reputation().total_reports)

    def test_repeated_observations_do_not_inherit_votes_and_old_targets_are_rejected(self):
        first = self.create()
        self.vote(first)
        self.clock.value += 180
        second = self.create()
        with self.assertRaises(CommunityServiceError) as failure:
            self.vote(first, "late-witness")
        self.assertEqual(409, failure.exception.status_code)
        self.assertEqual(1, self.reputation().validated_reports)
        self.vote(second)
        self.assertEqual(2, self.reputation().validated_reports)
        self.assertEqual(1, self.reputation().points)

    def test_change_of_phenomenon_cannot_use_previous_confirmation(self):
        first = self.create()
        self.vote(first)
        self.clock.value += 180
        second = self.create("wind")
        with self.assertRaises(CommunityServiceError):
            self.vote(first, "late")
        self.assertFalse(self.history()[0]["validated"])
        self.vote(second)
        self.assertEqual(2, self.reputation().points)

    def test_three_hours_start_at_award_not_submission_or_unpaid_validation(self):
        first = self.create()
        self.clock.value += 600
        self.vote(first)
        award_time = self.clock.value
        self.clock.value += 180
        second = self.create()
        self.vote(second)
        self.assertEqual(1, self.reputation().points)
        self.clock.value = award_time + 3 * 3600 - 1
        third = self.create()
        self.vote(third)
        self.assertEqual(3, self.reputation().validated_reports)
        self.assertEqual(1, self.reputation().points)
        self.clock.value += 1
        self.vote(third, "another-witness")
        self.assertEqual(2, self.reputation().points)
        self.assertEqual(3, self.reputation().validated_reports)
        self.vote(third, "third-witness")
        self.assertEqual(2, self.reputation().points)

    def test_independent_matching_observations_award_both_and_no_pair_or_daily_cap(self):
        for index, phenomenon in enumerate(["rain", "wind", "snow", "hail"]):
            if index:
                self.clock.value += 180
            self.create(phenomenon, "author")
            self.create(phenomenon, "neighbour")
        self.assertEqual(4, self.reputation().points)
        self.assertEqual(4, self.reputation("neighbour").points)
        self.assertIsNone(self.reputation().max_daily_awards)

    def test_hourly_group_boundary_is_preserved(self):
        self.clock.value = 1_800_003_600 - 1
        self.create(client_id="author")
        self.clock.value += 2
        self.create(client_id="neighbour")
        self.assertEqual(0, self.reputation().points)

    def test_quiet_is_counted_and_confirmed_but_never_awarded(self):
        result = self.create("quiet")
        self.vote(result)
        summary = self.reputation()
        self.assertEqual((1, 1, 0), (summary.total_reports, summary.validated_reports, summary.points))

    def test_minimum_interval_and_rolling_quotas_survive_replacement(self):
        self.create()
        self.clock.value += 179
        with self.assertRaises(CommunityServiceError) as failure:
            self.create("wind")
        self.assertEqual(1, failure.exception.detail["retry_after_seconds"])
        self.clock.value += 1
        self.create("wind")
        for _ in range(2):
            self.clock.value += 180
            self.create("snow")
        self.clock.value += 180
        with self.assertRaises(CommunityServiceError) as failure:
            self.create("rain")
        self.assertEqual("community_hourly_limit", failure.exception.detail["code"])
        self.clock.value += 3600 - 720
        self.create()

    def test_daily_limit_has_rolling_boundary(self):
        start = self.clock.value
        for i in range(12):
            self.clock.value = start + i * 3600
            self.create()
        self.clock.value = start + 86400 - 1
        with self.assertRaises(CommunityServiceError) as failure:
            self.create()
        self.assertEqual("community_daily_limit", failure.exception.detail["code"])
        self.clock.value += 1
        self.create()

    def test_gps_is_required_for_both_votes_and_must_match_municipality(self):
        report = self.create()
        for vote in ("yes", "no"):
            for invalid in ({"age_ms": 120001}, {"accuracy_m": 501}, {"lat": None},
                            {"lat": 43.7265, "lon": 12.6365}):
                with self.subTest(vote=vote, invalid=invalid), self.assertRaises(CommunityServiceError):
                    self.vote(report, vote=vote, **invalid)
        self.assertEqual(0, self.reputation().points)
        with self.assertRaises(CommunityServiceError):
            self.vote(report, "author")

    def test_third_cessation_archives_but_does_not_revoke_points(self):
        report = self.create()
        self.vote(report)
        for voter in ("one", "two", "three"):
            self.vote(report, voter, "no")
        self.assertEqual([], self.service.get_scoped_reports(istat_code="093033")["reports"])
        self.assertEqual("ceased", self.history()[0]["status"])
        self.assertTrue(self.history()[0]["point"])
        self.assertEqual(1, self.reputation().points)

    def test_expiry_and_history_privacy_and_retention(self):
        report = self.create()
        self.vote(report)
        self.clock.value += 3600
        with self.assertRaises(CommunityServiceError):
            self.vote(report, "late")
        history = self.history("other")[0]
        self.assertEqual("expired", history["status"])
        self.assertFalse(history["mine"])
        self.assertNotIn("point", history)
        self.assertNotIn("validated", history)
        self.assertEqual({"id", "typeId", "place", "istatCode", "createdAt", "expiresAt", "status", "mine", "count", "confirmations"}, set(history))
        self.assertEqual({"yes": 1, "no": 0}, history["confirmations"])
        self.clock.value += 47 * 3600
        self.assertEqual([], self.history())
        self.assertEqual(1, self.reputation().points)

    def test_concurrent_submissions_accept_only_one_without_double_counting(self):
        self.create()
        self.clock.value += 180
        barrier = Barrier(2)
        def send():
            barrier.wait()
            try:
                return self.create("wind")["ok"]
            except CommunityServiceError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual([False, True], sorted(pool.map(lambda _: send(), range(2))))
        self.assertEqual(1, len(self.service.repository._reports))
        self.assertEqual(2, self.reputation().total_reports)

    def test_grouped_history_keeps_frozen_votes_once_and_latest_submission_time(self):
        reports = [self.create(client_id=f"author-{i}") for i in range(2)]
        self.clock.value += 120
        reports.append(self.create(client_id="author-2"))
        ids = [result["report"]["id"] for result in reports]
        for i in range(4):
            self.vote(reports[0], f"witness-{i}", report_ids=ids)
        self.vote(reports[0], "ended", "no", report_ids=ids)
        # A changed vote reduces yes: don't take independent maxima or sum copies.
        self.vote(reports[0], "witness-0", "no", report_ids=ids)
        self.clock.value += 3600
        rows = self.history("reader", grouped=True)
        self.assertEqual(1, len(rows))
        self.assertEqual(3, rows[0]["count"])
        self.assertEqual({"yes": 3, "no": 2}, rows[0]["confirmations"])
        self.assertEqual(reports[-1]["report"]["createdAt"], rows[0]["createdAt"])
        self.assertFalse(rows[0]["mine"])
        self.assertNotIn("point", rows[0])
        self.assertNotIn("history_episode_id", rows[0])
        self.assertEqual(3, len(self.history("reader")))

    def test_reused_hourly_group_does_not_merge_replacements_or_later_votes(self):
        first = self.create()
        self.vote(first)
        self.clock.value += 180
        second = self.create()
        self.clock.value += 180
        third = self.create()
        self.vote(third, "latest")
        rows = self.history("reader", grouped=True)
        self.assertEqual(3, len(rows))
        by_id = {row["id"]: row for row in rows}
        self.assertEqual({"yes": 1, "no": 0}, by_id[first["report"]["id"]]["confirmations"])
        self.assertEqual({"yes": 0, "no": 0}, by_id[second["report"]["id"]]["confirmations"])

    def test_grouping_precedes_pagination_even_for_more_than_fifty_observations(self):
        for index in range(55):
            if index and index % 20 == 0:
                self.clock.value += 61
            self.create(client_id=f"group-author-{index}")
        self.clock.value += 3600
        page = self.service.get_history(CommunityHistoryQuery(client_id="reader", istat_code="093033", grouped=True))
        self.assertEqual(1, len(page["reports"]))
        self.assertEqual(55, page["reports"][0]["count"])
        self.assertIsNone(page["next_cursor"])

    def test_archived_group_and_votes_survive_sqlite_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.sqlite3"
            repository = PilotSQLiteCommunityRepository(path)
            self.service = self.make_service(repository)
            try:
                reports = [self.create(client_id=f"author-{i}") for i in range(3)]
                self.vote(reports[0], report_ids=[item["report"]["id"] for item in reports])
            finally:
                repository.close()
            self.clock.value += 3600
            repository = PilotSQLiteCommunityRepository(path)
            self.service = self.make_service(repository)
            try:
                rows = self.history("reader", grouped=True)
                self.assertEqual(1, len(rows))
                self.assertEqual((3, "expired", {"yes": 1, "no": 0}),
                    (rows[0]["count"], rows[0]["status"], rows[0]["confirmations"]))
            finally:
                repository.close()

    def test_history_cursor_survives_new_reports_and_equal_timestamps(self):
        for index in range(55):
            if index and index % 20 == 0:
                self.clock.value += 61
            self.create(client_id=f"history-author-{index}")
        query = dict(client_id="reader", istat_code="093033")
        page = self.service.get_history(CommunityHistoryQuery(**query))
        self.assertEqual(50, len(page["reports"]))
        cursor = page["next_cursor"]
        self.clock.value += 1
        self.create(client_id="newer-author")
        tail = self.service.get_history(CommunityHistoryQuery(**query,
            before_created_at=cursor["createdAt"], before_id=cursor["id"]))
        ids = [item["id"] for item in page["reports"] + tail["reports"]]
        self.assertEqual(55, len(ids))
        self.assertEqual(55, len(set(ids)))
        self.assertIsNone(tail["next_cursor"])
        # The legacy offset reader remains supported.
        self.assertEqual(50, page["next_offset"])
        invalid = self.client.post("/api/community/history", headers=self.headers,
            json={**query, "before_id": "incomplete"})
        self.assertEqual(422, invalid.status_code)

    def test_concurrent_confirmations_award_exactly_once(self):
        report = self.create()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda n: self.vote(report, f"voter-{n}"), range(4)))
        self.assertEqual(1, self.reputation().points)
        self.assertEqual(1, self.reputation().validated_reports)

    def test_sqlite_restart_preserves_history_and_reward_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "community.sqlite3"
            repository = PilotSQLiteCommunityRepository(path)
            self.service = self.make_service(repository)
            first = self.create()
            self.vote(first)
            repository.close()
            repository = PilotSQLiteCommunityRepository(path)
            try:
                self.service = self.make_service(repository)
                self.clock.value += 180
                second = self.create()
                self.vote(second)
                self.assertEqual((2, 2, 1), (self.reputation().total_reports, self.reputation().validated_reports, self.reputation().points))
                self.assertEqual(2, len(self.history()))
            finally:
                repository.close()

    def test_api_requires_target_ids_and_retired_actions_reject(self):
        result = self.client.post("/api/community/reports", json=self.command().model_dump(), headers=self.headers)
        self.assertEqual(200, result.status_code)
        report = result.json()
        vote = self.vote_command(report).model_dump()
        vote["report_ids"] = []
        rejected = self.client.post(f"/api/community/reports/{report['report']['groupId']}/confirmation", json=vote, headers=self.headers)
        self.assertEqual(409, rejected.status_code)
        for action in (self.service.update_observation, self.service.correct_observation, self.service.delete_report):
            with self.assertRaises(CommunityServiceError) as error:
                action(report["report"]["id"], None, client_host="test")
            self.assertEqual("community_new_observation_required", error.exception.detail["code"])
        history = self.client.post("/api/community/history", json={"client_id": "author", "istat_code": "093033"}, headers=self.headers)
        self.assertEqual(200, history.status_code)
        self.assertNotIn("owner_key", json.dumps(history.json()))
        operation = self.client.post("/api/community/operations/unknown-operation", json={"client_id": "author"}, headers=self.headers)
        self.assertEqual({"status": "not_found", "rules_version": "community-reports-v3"}, operation.json())

    def test_moderation_revokes_per_report_awards_idempotently(self):
        first = self.create()
        self.vote(first)
        self.clock.value += 180
        second = self.create()
        self.vote(second)
        with self.service.repository.transaction():
            self.service.repository.revoke_group_reputation_memory(first["report"]["groupId"], now=self.clock.value, reason="test")
        self.assertEqual(0, self.reputation().points)
        self.assertEqual(0, self.reputation().validated_reports)
        self.vote(second, "after-revocation")
        self.assertEqual(0, self.reputation().points)

    def test_ranks_change_at_five_and_fifteen(self):
        for points, rank in ((4, "novice"), (5, "lookout"), (14, "lookout"), (15, "sentinel")):
            self.assertEqual(rank, self.service._reputation_rank(points).id)
