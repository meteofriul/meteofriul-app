"""Independent API acceptance checks for the pilot-only rule boundaries."""

import itertools
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

from fastapi.testclient import TestClient

from tests import test_pilot_community as fixtures
from app.pilot_community import create_app
from app.services.community import COMMUNITY_GUIDELINES_POLICY_VERSION
from app.services.pilot_community import PilotCommunityService


class PilotRuleBoundaries(unittest.TestCase):
    def setUp(self):
        self.clock = fixtures.Clock()
        self.start = self.clock.value
        self.ids = itertools.count()
        self.operations = itertools.count()
        self.service = PilotCommunityService(
            geography=fixtures.FixtureGeography(), now=self.clock,
            report_id_factory=lambda: f"boundary-report-{next(self.ids)}",
        )
        self.client = TestClient(create_app(service=self.service), base_url="http://127.0.0.1:8783")
        self.headers = {"X-Meteo-Pilot-Community": "local-only", "Origin": "http://127.0.0.1:5174"}

    def operation(self):
        return f"boundary-operation-{next(self.operations):06d}"

    def command(self, type_id="rain", **changes):
        return {
            "type_id": type_id, "lat": 45.95793, "lon": 12.66284,
            "istat_code": "093033", "selected_place": "Pordenone", "client_id": "boundary-owner",
            "accepted_terms": True, "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
            "accuracy_m": 25, "age_ms": 1000, "operation_id": self.operation(), **changes,
        }

    def create(self, type_id="rain", **changes):
        return self.client.post("/api/community/reports", json=self.command(type_id, **changes), headers=self.headers)

    def withdraw(self, report, action="withdraw", **changes):
        return self.client.request("DELETE", f"/api/community/reports/{report['id']}", json={
            "client_id": "boundary-owner", "operation_id": self.operation(),
            "expected_revision": report["revision"], "action": action, **changes,
        }, headers=self.headers)

    def correct(self, report, type_id="snow", **changes):
        return self.client.post(f"/api/community/reports/{report['id']}/correction", json=self.command(
            type_id, expected_revision=report["revision"], **changes,
        ), headers=self.headers)

    def renew(self, report):
        command = self.command()
        for field in ("istat_code", "selected_place", "type_id"):
            command.pop(field)
        command["expected_revision"] = report["revision"]
        return self.client.patch(f"/api/community/reports/{report['id']}", json=command, headers=self.headers)

    def accepted(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_interval_exact_boundary_and_independent_phenomena(self):
        first = self.accepted(self.create())["report"]
        self.clock.value = self.start + 119.999
        self.assertEqual(self.create("wind").status_code, 429)
        self.clock.value = self.start + 120
        self.accepted(self.create("wind"))
        self.clock.value += 120
        self.assertEqual(self.create("rain").status_code, 409)
        self.assertIn(first["id"], self.service.repository._reports)
        self.assertEqual(len(self.service.repository._reports), 2)

    def test_rolling_hour_exact_boundary_withdrawals_do_not_refund(self):
        for index in range(4):
            self.clock.value = self.start + index * 120
            report = self.accepted(self.create())["report"]
            self.accepted(self.withdraw(report))
        self.clock.value = self.start + 3599.999
        self.assertEqual(self.create().status_code, 429)
        self.clock.value = self.start + 3600
        self.accepted(self.create())

    def test_rolling_day_does_not_reset_at_a_clock_hour_or_midnight(self):
        for index in range(12):
            self.clock.value = self.start + index * 3600
            report = self.accepted(self.create())["report"]
            self.accepted(self.withdraw(report))
        self.clock.value = self.start + 86399.999
        self.assertEqual(self.create().status_code, 429)
        self.clock.value = self.start + 86400
        self.accepted(self.create())

    def test_concurrent_fourth_and_fifth_creation_cannot_both_commit(self):
        for index in range(3):
            self.clock.value = self.start + index * 120
            report = self.accepted(self.create())["report"]
            self.accepted(self.withdraw(report))
        self.clock.value = self.start + 360
        barrier = Barrier(2)
        commands = [self.command("rain"), self.command("wind")]

        def send(command):
            barrier.wait(timeout=5)
            return self.client.post("/api/community/reports", json=command, headers=self.headers).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(send, commands))
        self.assertEqual(sorted(statuses), [200, 429])
        self.assertEqual(len(next(iter(self.service.repository._pilot_creations.values()))), 4)

    def test_correction_keeps_original_expiry_and_cannot_reopen_its_window(self):
        original = self.accepted(self.create())["report"]
        self.clock.value = self.start + 299.999
        corrected = self.accepted(self.correct(original))["report"]
        self.assertEqual(corrected["id"], original["id"])
        self.assertEqual(corrected["createdAt"], original["createdAt"])
        self.assertEqual(corrected["expiresAt"], original["expiresAt"])
        self.assertEqual(corrected["revision"], 2)
        feed = self.client.get("/api/community/reports", params={"istat_code": "093033"}).json()
        self.assertIn(corrected["id"], [report["id"] for report in feed["reports"]])
        self.clock.value = self.start + 300
        self.assertEqual(self.correct(corrected, "hail").status_code, 409)
        renewed = self.accepted(self.renew(corrected))["report"]
        self.assertEqual(self.correct(renewed, "hail").status_code, 409)
        self.assertEqual(len(next(iter(self.service.repository._pilot_creations.values()))), 1)

    def test_correction_collision_does_not_partially_change_report(self):
        original = self.accepted(self.create())["report"]
        self.clock.value += 120
        self.accepted(self.create("wind"))
        before = deepcopy(self.service.repository._reports[original["id"]])
        self.assertEqual(self.correct(original, "wind").status_code, 409)
        self.assertEqual(self.service.repository._reports[original["id"]], before)

    def test_replacement_bypasses_only_interval_once_and_cannot_chain(self):
        original = self.accepted(self.create())["report"]
        self.clock.value += 10
        retired = self.accepted(self.withdraw(original, "replace"))
        self.assertEqual(retired["replacement_expires_at"], original["expiresAt"])
        self.assertNotIn(original["id"], self.service.repository._reports)
        self.assertEqual(len(self.service.repository._reports), 0)  # no automatic new report
        command = self.command("snow", replacement_token=retired["replacement_token"])
        response = self.client.post("/api/community/reports", json=command, headers=self.headers)
        replacement = self.accepted(response)["report"]
        self.assertNotEqual(replacement["id"], original["id"])
        replay = self.accepted(self.client.post("/api/community/reports", json=command, headers=self.headers))
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["report"]["id"], replacement["id"])
        self.assertEqual(len(next(iter(self.service.repository._pilot_creations.values()))), 2)
        self.assertEqual(self.withdraw(replacement, "replace").status_code, 409)
        self.clock.value += 120
        self.assertEqual(self.create("hail", replacement_token=retired["replacement_token"]).status_code, 409)

    def test_replacement_does_not_bypass_full_hour_quota(self):
        for index in range(4):
            self.clock.value = self.start + index * 120
            report = self.accepted(self.create())["report"]
            if index < 3:
                self.accepted(self.withdraw(report))
        retired = self.accepted(self.withdraw(report, "replace"))
        blocked = self.create("snow", replacement_token=retired["replacement_token"])
        self.assertEqual(blocked.status_code, 429, blocked.text)
        self.assertFalse(self.service.repository._pilot_replacements[retired["replacement_token"]]["used"])
        self.assertEqual(len(next(iter(self.service.repository._pilot_creations.values()))), 4)

    def test_renew_requires_original_municipality_not_merely_fresh_gps(self):
        original = self.accepted(self.create())["report"]
        command = self.command(lat=43.72773, lon=12.63884)
        for field in ("istat_code", "selected_place", "type_id"):
            command.pop(field)
        command["expected_revision"] = original["revision"]
        before = deepcopy(self.service.repository._reports[original["id"]])
        response = self.client.patch(f"/api/community/reports/{original['id']}", json=command, headers=self.headers)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.service.repository._reports[original["id"]], before)

    def test_create_operation_id_cannot_be_reused_for_different_intent(self):
        command = self.command()
        original = self.accepted(self.client.post("/api/community/reports", json=command, headers=self.headers))["report"]
        command["type_id"] = "snow"
        response = self.client.post("/api/community/reports", json=command, headers=self.headers)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(list(self.service.repository._reports), [original["id"]])
