"""Published-client wire requests and mixed-version durable state, no network."""
import itertools
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.pilot_community_cloud import create_app
from app.repositories.pilot_community import PilotMemoryCommunityRepository
from app.repositories.pilot_community_sqlite import PilotSQLiteCommunityRepository
from app.services.community import COMMUNITY_GUIDELINES_POLICY_VERSION
from app.services.community import CommunityServiceError
from app.services.community_compatibility import (
    CloudCommunityReportsService, LegacyCommunityService, RULES_HEADER,
    RULES_VERSION, LEGACY_RULES_VERSION,
)
from app.services.pilot_community_geography import PilotCommunityMunicipality
from app.services.pilot_community import PilotCommunityReportCreate


class Geography:
    municipalities = (PilotCommunityMunicipality(
        "093033", "Pordenone", "IT-36", "PN", "PN", "093033", 45.9567, 12.6605, "IT-36"),)

    def match_istat(self, code):
        return self.municipalities[0] if code == "093033" else None

    def resolve_municipality(self, lat, lon):
        return self.municipalities[0] if abs(lat - 45.9567) < .1 and abs(lon - 12.6605) < .1 else None

    def nearby_municipalities(self, *args, **kwargs):
        return list(self.municipalities)


class CommunityCloudCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_800_003_600.0
        self.operations = itertools.count()
        self.identifiers = itertools.count()
        self.repository = PilotMemoryCommunityRepository()
        self.connect(self.repository)

    def connect(self, repository):
        self.repository = repository
        params = dict(repository=repository, geography=Geography(), now=lambda: self.now,
                      report_id_factory=lambda: f"observation-{next(self.identifiers)}")
        self.legacy = LegacyCommunityService(**params)
        self.current = CloudCommunityReportsService(legacy_service=self.legacy, **params)
        self.verifier = Mock(return_value={"app_id": "approved-app"})
        self.client = TestClient(create_app(service=self.current, legacy_service=self.legacy,
            public_mode=True, app_check_verifier=self.verifier, allowed_app_ids={"approved-app"}),
            base_url="https://pilot-community-335641913741.europe-west1.run.app")

    def operation(self):
        return f"compat-operation-{next(self.operations):08d}"

    def headers(self, new=False):
        return {"Origin": "https://localhost", "X-Firebase-AppCheck": "test-token",
                **({RULES_HEADER: RULES_VERSION} if new else {})}

    def create_command(self, owner, kind="rain"):
        return dict(client_id=owner, type_id=kind, lat=45.9567, lon=12.6605,
                    accuracy_m=25, age_ms=10, istat_code="093033", selected_place="Pordenone",
                    accepted_terms=True, policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION,
                    operation_id=self.operation())

    def post(self, path, body, new=False, expected=200):
        response = self.client.post("/api/community/" + path, json=body, headers=self.headers(new))
        self.assertEqual(expected, response.status_code, response.text)
        return response.json()

    def create(self, owner="author", kind="rain", new=False):
        return self.post("reports", self.create_command(owner, kind), new)

    def vote(self, result, owner="witness", new=False, vote="yes", expected=200, **extra):
        # The unversioned payload is exactly the shape read from 0.1.14's JS.
        body = dict(client_id=owner, vote=vote, accepted_terms=True,
                    policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION)
        if new:
            body.update(lat=45.9567, lon=12.6605, accuracy_m=25, age_ms=10,
                        report_ids=[result["report"]["id"]])
        body.update(extra)
        return self.post(f"reports/{result['report']['groupId']}/confirmation", body, new, expected)

    def reputation(self, owner="author", new=True):
        return self.post("reputation", {"client_id": owner}, new)

    def edit(self, result, action, new=False, expected=200, **extra):
        command = dict(client_id="author", operation_id=self.operation(),
                       expected_revision=result["revision"])
        suffix = ""
        method = "PATCH"
        if action == "update":
            command.update(lat=45.9567, lon=12.6605, accuracy_m=25, age_ms=10,
                           accepted_terms=True, policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION)
        elif action == "correction":
            command = {**self.create_command("author", "wind"), "expected_revision": result["revision"]}
            method, suffix = "POST", "/correction"
        else:
            method = "DELETE"
            command["action"] = action
        command.update(extra)
        response = self.client.request(method, "/api/community/reports/" + result["report"]["id"] + suffix,
                                       json=command, headers=self.headers(new))
        self.assertEqual(expected, response.status_code, response.text)
        return response.json()

    def test_default_and_opt_in_contracts_and_cors(self):
        for new, version in [(False, LEGACY_RULES_VERSION), (True, RULES_VERSION)]:
            response = self.client.get("/api/community/reports?istat_code=093033", headers=self.headers(new))
            self.assertEqual(200, response.status_code)
            self.assertEqual(version, response.json()["contract"]["schema_version"])
            self.assertEqual(version, response.headers[RULES_HEADER])
        response = self.client.options("/api/community/reports", headers={
            "Origin": "https://localhost", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": RULES_HEADER + ",x-firebase-appcheck,content-type"})
        self.assertEqual(200, response.status_code)
        response = self.client.get("/api/community/reports?istat_code=093033", headers={RULES_HEADER: "future"})
        self.assertEqual(426, response.status_code)
        self.post("history", {"client_id": "reader", "istat_code": "093033"}, expected=426)

    def test_published_create_confirm_without_gps_and_reputation_still_work(self):
        result = self.create()
        confirmed = self.vote(result)
        self.assertEqual(1, confirmed["confirmations"]["yes"])
        self.assertEqual(1, self.reputation(new=False)["points"])
        self.assertEqual(1, self.reputation()["points"])
        self.assertEqual(1, self.reputation()["validated_reports"])

    def test_published_refresh_correction_withdraw_and_replacement_still_work(self):
        original = self.create()
        self.now += 10
        refreshed = self.edit(original, "update")
        self.assertEqual(original["report"]["id"], refreshed["report"]["id"])
        corrected = self.edit(refreshed, "correction")
        self.assertEqual("wind", corrected["report"]["typeId"])
        replacement = self.edit(corrected, "replace")
        command = self.create_command("author", "snow")
        command["replacement_token"] = replacement["replacement_token"]
        created = self.post("reports", command)
        self.edit(created, "withdraw")
        self.assertEqual(0, len(self.repository._reports))

    def test_legacy_vote_cannot_validate_new_content_and_v3_keeps_gps_and_snapshot_checks(self):
        old = self.create()
        self.vote(old)
        new = self.create("new-author", new=True)
        self.assertNotEqual(old["report"]["groupId"], new["report"]["groupId"])
        self.assertEqual(0, self.reputation("new-author")["points"])
        self.vote(new, expected=426)
        self.vote(new, new=True, lat=None, lon=None, accuracy_m=None, age_ms=None, expected=400)
        self.vote(new, new=True, report_ids=[old["report"]["id"]], expected=409)
        self.vote(new, new=True)
        self.assertEqual(1, self.reputation("new-author")["points"])
        for new_header in (False, True):
            feed = self.client.get("/api/community/reports?istat_code=093033", headers=self.headers(new_header)).json()
            self.assertEqual(2, len(feed["map_groups"]))
            self.assertEqual({"093033"}, {row["istatCode"] for row in feed["map_groups"]})

    def test_new_and_old_voters_share_legacy_award_without_double_counting(self):
        old = self.create()
        self.vote(old, new=True)
        self.vote(old, owner="second-witness")
        self.assertEqual(1, self.reputation()["points"])
        self.assertEqual(1, self.reputation()["validated_reports"])
        self.vote(old, new=True, report_ids=[], expected=409)
        self.vote(old, new=True, age_ms=120001, expected=400)

    def test_new_records_reject_every_old_owner_edit(self):
        result = self.create(new=True)
        for action in ("update", "correction", "withdraw", "replace"):
            with self.subTest(action=action):
                self.edit(result, action, expected=426)
        self.assertEqual(1, self.reputation()["total_reports"])
        self.assertEqual(1, len(self.repository._reports))

    def test_upgrade_preserves_identity_points_and_replays_old_receipts(self):
        command = self.create_command("author")
        old = self.post("reports", command)
        self.vote(old)
        self.now += 180
        new = self.create(kind="wind", new=True)
        self.assertEqual([old["report"]["id"]], new["replaced_report_ids"])
        self.vote(new, new=True)
        self.assertEqual(2, self.reputation()["points"])
        self.assertEqual(2, self.reputation()["total_reports"])
        replay = self.post("reports", command)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(old["report"]["id"], replay["report"]["id"])
        self.post("reports", self.create_command("author", "hail"), expected=426)
        self.assertEqual(2, self.reputation()["total_reports"])

    def test_downgrade_guard_survives_redaction_and_restart(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "state.sqlite3"
            repo = PilotSQLiteCommunityRepository(database)
            self.connect(repo)
            self.create(new=True)
            self.now += 49 * 3600
            with repo.transaction():
                repo._prune_memory(self.now)
            repo.close()
            repo = PilotSQLiteCommunityRepository(database)
            try:
                self.connect(repo)
                self.post("reports", self.create_command("author"), expected=426)
                self.assertEqual(1, self.reputation()["total_reports"])
            finally:
                repo.close()

    def test_quotas_are_shared_during_upgrade(self):
        for kind in ["rain", "wind", "snow", "hail"]:
            self.create(kind=kind)
            self.now += 180
        failure = self.post("reports", self.create_command("author", "fog"), new=True, expected=429)
        self.assertEqual("community_hourly_limit", failure["detail"]["code"])
        self.assertEqual(4, len(self.repository._reports))

    def test_expired_legacy_history_retains_final_confirmation_counts(self):
        old = self.create()
        self.vote(old)
        self.vote(old, owner="gone-witness", vote="no")
        self.now += 3601
        rows = self.post("history", {"client_id": "reader", "istat_code": "093033", "grouped": True}, new=True)["reports"]
        self.assertEqual(1, len(rows))
        self.assertEqual({"yes": 1, "no": 1}, rows[0]["confirmations"])
        self.now += 48 * 3600
        self.assertEqual([], self.post("history", {"client_id": "reader", "istat_code": "093033"}, new=True)["reports"])

    def test_both_protocols_keep_app_check_required_and_validate_app_identity(self):
        for new in (False, True):
            body = self.create_command("author")
            response = self.client.post("/api/community/reports", json=body,
                headers={RULES_HEADER: RULES_VERSION} if new else {})
            self.assertEqual(401, response.status_code)
            self.verifier.return_value = {"app_id": "unapproved"}
            self.post("reports", body, new, expected=403)
        self.assertEqual({}, self.repository._reports)

    def test_pending_rollout_keeps_old_app_and_reads_working_without_new_writes(self):
        old = self.create()
        self.client = TestClient(create_app(service=self.current, legacy_service=self.legacy,
            public_mode=True, v3_writes_enabled=False, app_check_verifier=self.verifier,
            allowed_app_ids={"approved-app"}),
            base_url="https://pilot-community-335641913741.europe-west1.run.app")
        failure = self.post("reports", self.create_command("new-owner"), new=True, expected=503)
        self.assertEqual("community_v3_rollout_pending", failure["detail"]["code"])
        self.vote(old, new=True, expected=503)
        self.vote(old)
        self.assertEqual(1, self.reputation()["points"])
        self.post("history", {"client_id": "reader", "istat_code": "093033"}, new=True)
        self.assertEqual(1, len(self.repository._reports))

    def test_v3_preflight_and_read_contract_cover_android_and_public_web_origins(self):
        origins = ("https://localhost", "https://meteofriul.app", "https://www.meteofriul.app",
                   "https://meteofriul.it", "https://www.meteofriul.it")
        for origin in origins:
            with self.subTest(origin=origin):
                response = self.client.options("/api/community/reports", headers={
                    "Origin": origin, "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": RULES_HEADER + ",x-firebase-appcheck,content-type"})
                self.assertEqual(200, response.status_code)
                self.assertEqual(origin, response.headers["Access-Control-Allow-Origin"])
                self.assertIn(RULES_HEADER.lower(), response.headers["Access-Control-Allow-Headers"].lower())
                response = self.client.get("/api/community/reports?istat_code=093033",
                    headers={"Origin": origin, RULES_HEADER: RULES_VERSION})
                self.assertEqual(200, response.status_code)
                self.assertEqual(origin, response.headers["Access-Control-Allow-Origin"])
                self.assertEqual(RULES_VERSION, response.json()["contract"]["schema_version"])
        self.verifier.assert_not_called()  # Preflight and public reads need no bypass token.

    def test_compatible_freeze_after_v3_write_preserves_durable_data_and_legacy_operations(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "state.sqlite3"
            repo = PilotSQLiteCommunityRepository(database)
            self.connect(repo)
            command = self.create_command("author")
            accepted = self.post("reports", command, new=True)
            self.vote(accepted, new=True)
            before = self.reputation()
            repo.close()
            repo = PilotSQLiteCommunityRepository(database)
            try:
                self.connect(repo)
                self.client = TestClient(create_app(service=self.current, legacy_service=self.legacy,
                    public_mode=True, v3_writes_enabled=False, app_check_verifier=self.verifier,
                    allowed_app_ids={"approved-app"}),
                    base_url="https://pilot-community-335641913741.europe-west1.run.app")
                health = self.client.get("/api/community/health").json()
                self.assertFalse(health["v3_writes_enabled"])
                self.assertEqual(LEGACY_RULES_VERSION, health["default_rules"])
                self.assertEqual([LEGACY_RULES_VERSION, RULES_VERSION], health["supported_rules"])
                for new in (False, True):
                    feed = self.client.get("/api/community/reports?istat_code=093033", headers=self.headers(new))
                    self.assertEqual(200, feed.status_code)
                    self.assertEqual(1, len(feed.json()["map_groups"]))
                receipt = self.post("operations/" + command["operation_id"], {"client_id": "author"}, new=True)
                self.assertEqual("accepted", receipt["status"])
                self.assertEqual(accepted["report"]["id"], receipt["result"]["report"]["id"])
                self.post("reports", self.create_command("new-owner"), new=True, expected=503)
                self.vote(accepted, owner="next-witness", new=True, expected=503)
                for action in ("update", "correction", "withdraw", "replace"):
                    with self.subTest(action=action):
                        self.edit(accepted, action, new=True, expected=503)
                self.assertEqual(before, self.reputation())
                self.post("reports", self.create_command("author"), expected=426)
                old = self.create("legacy-owner", kind="wind")
                self.vote(old, owner="legacy-witness")
                self.assertEqual(1, self.reputation("legacy-owner", new=False)["points"])
                self.assertEqual(2, len(self.repository._reports))
            finally:
                repo.close()

    def test_new_three_hour_reward_window_respects_the_last_legacy_point(self):
        old = self.create()
        self.vote(old)
        self.now += 180
        upgraded = self.create(new=True)
        self.vote(upgraded, new=True)
        self.assertEqual(1, self.reputation()["points"])
        self.assertEqual(2, self.reputation()["validated_reports"])
        self.now += 3 * 3600
        next_observation = self.create(new=True)
        self.vote(next_observation, new=True)
        self.assertEqual(2, self.reputation()["points"])

    def test_failed_upgrade_does_not_pin_the_owner_or_replace_the_old_observation(self):
        old = self.create()
        self.now += 120  # Old interval, too early for v3.
        self.post("reports", self.create_command("author", "wind"), new=True, expected=429)
        self.assertIn(old["report"]["id"], self.repository._reports)
        self.create(kind="wind")
        self.assertEqual(2, self.reputation()["total_reports"])

    def test_independent_sqlite_instances_serialize_old_and_new_creations(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "state.sqlite3"
            repositories = [PilotSQLiteCommunityRepository(database) for _ in range(2)]
            services = []
            for index, repo in enumerate(repositories):
                params = dict(repository=repo, geography=Geography(), now=lambda: self.now,
                              report_id_factory=lambda i=index: f"parallel-{i}")
                old = LegacyCommunityService(**params)
                services.append(old if index == 0 else CloudCommunityReportsService(legacy_service=old, **params))
            barrier = Barrier(2)
            commands = [PilotCommunityReportCreate(**self.create_command("author", kind)) for kind in ("rain", "wind")]
            def send(index):
                barrier.wait()
                try:
                    services[index].create_report(commands[index], client_host="test")
                    return True
                except CommunityServiceError:
                    return False
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    self.assertEqual([False, True], sorted(pool.map(send, range(2))))
                with repositories[0].transaction():
                    self.assertEqual(1, len(repositories[0]._reports))
                    self.assertEqual(1, len(repositories[0]._pilot_operations))
            finally:
                for repo in repositories:
                    repo.close()
