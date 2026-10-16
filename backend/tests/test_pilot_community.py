import itertools
import json
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.pilot_community import create_app
from app.api.live import router as published_live_router
from app.contracts.live import CommunityReportCreate, CommunityReportDelete
from app.services.community import COMMUNITY_GUIDELINES_POLICY_VERSION, CommunityService, CommunityServiceError
from app.services.location import haversine_km
from app.services.pilot_community import (
    PilotCommunityObservationUpdate, PilotCommunityReportDelete,
    PilotCommunityService,
)
from app.services.pilot_community_geography import PilotCommunityMunicipality


class Clock:
    value = 1_789_900_000.0

    def __call__(self):
        return self.value


class FixtureGeography:
    """Small deterministic map; real polygon correctness has its own tests."""

    def __init__(self):
        self.municipalities = tuple(
            PilotCommunityMunicipality(code, name, region, province, province, code, lat, lon, region)
            for code, name, province, region, lat, lon in [
                ("093033", "Pordenone", "PN", "IT-36", 45.9567, 12.6605),
                ("093017", "Cordenons", "PN", "IT-36", 45.9836, 12.7004),
                ("041067", "Urbino", "PU", "IT-57", 43.7265, 12.6365),
                ("016065", "Castro", "BG", "IT-25", 45.8, 10.07),
                ("075096", "Castro", "LE", "IT-75", 40.0, 18.4),
            ]
        )

    def match_istat(self, code):
        return next((item for item in self.municipalities if item.istat_code == code), None)

    def match_name(self, name, province=None):
        matches = [item for item in self.municipalities if item.name == name and (not province or item.province == province)]
        return matches[0] if len(matches) == 1 else None

    def resolve_municipality(self, lat, lon):
        return next((item for item in self.municipalities if abs(item.latitude-lat) < .15 and abs(item.longitude-lon) < .15), None)

    def nearby_municipalities(self, lat, lon, radius_km=30, limit=8):
        return sorted(
            (item for item in self.municipalities if haversine_km(lat, lon, item.latitude, item.longitude) <= radius_km),
            key=lambda item: haversine_km(lat, lon, item.latitude, item.longitude),
        )[:limit]


class PilotCommunityTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.operations = itertools.count()
        identifiers = itertools.count()
        self.service = PilotCommunityService(
            geography=FixtureGeography(), now=self.clock,
            report_id_factory=lambda: f"community-{next(identifiers)}",
        )
        self.client = TestClient(create_app(service=self.service), base_url="http://127.0.0.1:8783")
        self.headers = {"X-Meteo-Pilot-Community": "local-only", "Origin": "http://127.0.0.1:5174"}

    def command(self, code="093033", **kwargs):
        item = self.service.pilot_geography.match_istat(code)
        values = {
            "type_id": "rain", "lat": item.latitude+.00123, "lon": item.longitude+.00234,
            "istat_code": code, "selected_place": item.name, "client_id": "sender",
            "accepted_terms": True, "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
            "accuracy_m": 25, "age_ms": 1000,
            "operation_id": f"create-operation-{next(self.operations):06d}",
        }
        return {**values, **kwargs}

    def post_report(self, code="093033", **kwargs):
        return self.client.post("/api/community/reports", json=self.command(code, **kwargs), headers=self.headers)

    def update_command(self, code="093033", **kwargs):
        item = self.service.pilot_geography.match_istat(code)
        values = {
            "client_id": "sender",
            "operation_id": "update-operation-0001",
            "expected_revision": 1,
            "lat": item.latitude + .00123,
            "lon": item.longitude + .00234,
            "accuracy_m": 25,
            "age_ms": 1000,
            "accepted_terms": True,
            "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
        }
        return {**values, **kwargs}

    def patch_report(self, report_id, code="093033", **kwargs):
        return self.client.patch(
            f"/api/community/reports/{report_id}",
            json=self.update_command(code, **kwargs), headers=self.headers,
        )

    def feed(self, code="093033"):
        return self.client.get("/api/community/reports", params={"istat_code": code, "radius_km": 30})

    def withdraw(self, report_id, **changes):
        return self.client.request("DELETE", f"/api/community/reports/{report_id}", json={"client_id": "sender", "action": "withdraw", "operation_id": f"withdraw-operation-{next(self.operations):06d}", "expected_revision": 1, **changes}, headers=self.headers)

    def correct(self, report_id, **changes):
        return self.client.post(f"/api/community/reports/{report_id}/correction", json=self.command(expected_revision=1, **changes), headers=self.headers)

    def test_create_replay_and_operation_lookup_do_not_duplicate_or_leak_to_other_owner(self):
        first = self.post_report(operation_id="create-replay-0000001")
        self.clock.value += 5
        replay = self.post_report(operation_id="create-replay-0000001", age_ms=999999)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertTrue(replay.json()["idempotent_replay"])
        self.assertEqual(first.json()["report"], replay.json()["report"])
        self.assertEqual(sum(len(values) for values in self.service.repository._pilot_creations.values()), 1)
        accepted = self.client.post("/api/community/operations/create-replay-0000001", json={"client_id": "sender"}, headers=self.headers)
        other = self.client.post("/api/community/operations/create-replay-0000001", json={"client_id": "other"}, headers=self.headers)
        self.assertEqual(accepted.json()["status"], "accepted")
        self.assertEqual(other.json(), {"status": "not_found"})
        conflicting = self.post_report(operation_id="create-replay-0000001", type_id="wind")
        self.assertEqual(conflicting.json()["detail"]["code"], "community_idempotency_conflict")

    def test_accepted_create_id_is_never_executed_again_after_receipt_compaction(self):
        first = self.post_report(operation_id="create-retained-0001").json()
        self.clock.value += 49 * 3600
        replay = self.post_report(operation_id="create-retained-0001")
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertTrue(replay.json()["reconciled_only"])
        self.assertEqual(replay.json()["report_id"], first["report"]["id"])
        self.assertNotIn("report", replay.json())
        self.assertFalse(self.service.repository._reports)
        self.assertFalse(self.service.repository._pilot_creations)

    def test_correction_preserves_id_timestamps_quota_and_records_revision(self):
        created = self.post_report().json()["report"]
        quotas = deepcopy(self.service.repository._pilot_creations)
        self.clock.value += 100
        response = self.correct(created["id"], type_id="wind", operation_id="correct-replay-000001")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["report"]
        self.assertEqual(result["id"], created["id"])
        self.assertEqual(result["createdAt"], created["createdAt"])
        self.assertEqual(result["expiresAt"], created["expiresAt"])
        self.assertEqual(result["updatedAt"], created["updatedAt"])
        self.assertEqual(result["revision"], 2)
        self.assertEqual(result["typeId"], "wind")
        self.assertIn(created["groupId"], result["lineageGroupIds"])
        self.assertEqual(quotas, self.service.repository._pilot_creations)
        self.assertFalse(self.service.repository._reputation_awards)
        self.assertEqual(len(self.feed().json()["reports"]), 1)
        repeated = self.correct(created["id"], type_id="wind", operation_id="correct-replay-000001")
        self.assertTrue(repeated.json()["idempotent_replay"])
        self.assertEqual(len(self.service.repository._pilot_history[created["id"]]), 2)

    def test_correction_rejects_foreign_owner_stale_gps_duplicate_and_expired(self):
        first = self.post_report().json()["report"]
        self.clock.value += 120
        self.post_report(type_id="wind")
        for changes, code in [
            ({"type_id": "wind"}, "community_observation_already_recent"),
            ({"client_id": "other", "type_id": "snow"}, "community_observation_owner_mismatch"),
            ({"age_ms": 120001}, "community_fresh_gps_required"),
        ]:
            response = self.correct(first["id"], **changes)
            self.assertEqual(response.json()["detail"]["code"], code, response.text)
        self.clock.value = first["expiresAt"] / 1000
        expired = self.correct(first["id"], type_id="snow")
        self.assertEqual(expired.json()["detail"]["code"], "community_observation_expired")

    def test_replacement_consumes_quota_once_and_cannot_chain_or_cross_owner(self):
        first = self.post_report().json()["report"]
        withdrawal = self.withdraw(first["id"], action="replace", operation_id="replace-start-000001")
        self.assertEqual(withdrawal.status_code, 200, withdrawal.text)
        token = withdrawal.json()["replacement_token"]
        self.assertFalse(self.feed().json()["reports"])
        self.assertEqual(self.post_report(client_id="other", type_id="wind", replacement_token=token).json()["detail"]["code"], "community_replacement_unavailable")
        replay = self.withdraw(first["id"], action="replace", operation_id="replace-start-000001")
        self.assertEqual(replay.json()["replacement_token"], token)
        replacement = self.post_report(type_id="wind", replacement_token=token, operation_id="replacement-send-001")
        self.assertEqual(replacement.status_code, 200, replacement.text)
        second = replacement.json()["report"]
        self.assertFalse(second["replacementAvailable"])
        self.assertIn(first["groupId"], second["lineageGroupIds"])
        self.assertEqual(sum(len(values) for values in self.service.repository._pilot_creations.values()), 2)
        second_attempt = self.withdraw(second["id"], action="replace")
        self.assertEqual(second_attempt.json()["detail"]["code"], "community_replacement_unavailable")
        retry = self.post_report(type_id="wind", replacement_token=token, operation_id="replacement-send-001")
        self.assertTrue(retry.json()["idempotent_replay"])
        self.assertEqual(self.post_report(type_id="snow", replacement_token=token).json()["detail"]["code"], "community_replacement_unavailable")

    def test_denial_cannot_be_erased_by_correction_or_replacement(self):
        report = self.post_report().json()["report"]
        self.client.post(f"/api/community/reports/{report['groupId']}/confirmation", json={"vote": "no", "client_id": "reader"}, headers=self.headers)
        before = deepcopy(self.service.repository._confirmations)
        for response in [self.correct(report["id"], type_id="wind"), self.withdraw(report["id"], action="replace")]:
            self.assertEqual(response.json()["detail"]["code"], "community_observation_not_updateable")
        self.assertEqual(before, self.service.repository._confirmations)
        self.assertEqual(len(self.service.repository._reports), 1)
        self.assertFalse(self.service.repository._pilot_replacements)

    def test_corrected_lineage_cannot_earn_another_award_after_45_minutes(self):
        report = self.post_report().json()["report"]
        vote = {"vote": "yes", "client_id": "reader", "accepted_terms": True, "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION}
        first_vote = self.client.post(f"/api/community/reports/{report['groupId']}/confirmation", json=vote, headers=self.headers)
        self.assertEqual(first_vote.status_code, 200, first_vote.text)
        self.assertEqual(sum(item["points"] for item in self.service.repository._reputations.values()), 1)
        corrected = self.correct(report["id"], type_id="wind")
        self.assertEqual(corrected.status_code, 200, corrected.text)
        self.clock.value += 2701
        later_vote = self.client.post(f"/api/community/reports/{corrected.json()['report']['groupId']}/confirmation", json={**vote, "client_id": "second-reader"}, headers=self.headers)
        self.assertEqual(later_vote.status_code, 200, later_vote.text)
        self.assertEqual(sum(item["points"] for item in self.service.repository._reputations.values()), 1)

    def test_later_denial_of_historical_group_blocks_renewal_of_corrected_report(self):
        first = self.post_report().json()["report"]
        self.post_report(client_id="other")
        corrected = self.correct(first["id"], type_id="wind")
        self.assertEqual(corrected.status_code, 200, corrected.text)
        denied = self.client.post(f"/api/community/reports/{first['groupId']}/confirmation", json={"vote": "no", "client_id": "reader"}, headers=self.headers)
        self.assertEqual(denied.status_code, 200, denied.text)
        renewed = self.patch_report(first["id"], expected_revision=2)
        self.assertEqual(renewed.json()["detail"]["code"], "community_observation_not_updateable")
        target_group = next(group for group in self.feed().json()["map_groups"] if group["groupId"] == corrected.json()["report"]["groupId"])
        self.assertEqual(target_group["confirmations"]["no"], 1)

    def test_national_report_read_is_scoped_and_private(self):
        sent = self.post_report("041067")
        self.assertEqual(sent.status_code, 200, sent.text)
        created = sent.json()
        report = created["report"]
        self.assertEqual(created["revision"], 1)
        self.assertEqual(created["updated_at"], report["createdAt"])
        self.assertEqual(report["revision"], 1)
        self.assertEqual(report["updatedAt"], report["createdAt"])
        self.assertEqual(report["istatCode"], "041067")
        self.assertEqual(report["lat"], 43.7265)
        self.assertNotIn("client_id", report)
        self.assertNotIn("owner_key", report)
        self.assertNotIn("accuracy_m", report)
        self.assertEqual(self.feed().json()["reports"], [])
        local = self.feed("041067").json()
        self.assertEqual(local["reports"][0]["id"], report["id"])
        self.assertEqual(local["map_groups"][0]["istatCode"], "041067")
        self.assertEqual(len(local["locations"]), 1)
        self.assertEqual(local["source"]["storage"], "memory")
        self.assertEqual(
            local["contract"]["update_fields"],
            list(PilotCommunityObservationUpdate.model_fields),
        )
        self.assertEqual(
            local["contract"]["update_action"],
            "renew_same_observation",
        )
        serialized = json.dumps(self.service.repository._reports)
        self.assertNotIn(str(self.command("041067")["lat"]), serialized)
        self.assertNotIn('"age_ms"', serialized)

    def test_identical_names_have_distinct_istat_groups(self):
        first = self.post_report("016065", client_id="first").json()["report"]
        second = self.post_report("075096", client_id="second").json()["report"]
        self.assertEqual(first["place"], second["place"])
        self.assertNotEqual(first["groupId"], second["groupId"])
        self.assertEqual(self.feed("016065").json()["map_groups"][0]["count"], 1)

    def test_contained_gps_far_from_public_point_is_allowed(self):
        response = self.post_report(lat=46.0667)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["report"]["lat"], 45.9567)

    def test_invalid_outside_stale_and_mismatched_locations_fail(self):
        for changes, expected in [
            ({"lat": 48, "lon": 16}, 403),
            ({"age_ms": 120001}, 400), ({"accuracy_m": 501}, 400),
            ({"accuracy_m": None}, 400), ({"istat_code": "041067"}, 400),
            ({"lat": 100}, 422), ({"text": "arbitrary text"}, 422),
        ]:
            response = self.post_report(**changes)
            self.assertEqual(response.status_code, expected, response.text)
        self.assertFalse(self.service.repository._reports)

    def test_resolve_returns_canonical_points_and_identity(self):
        payload = {key: value for key, value in self.command().items() if key in {"lat", "lon", "accuracy_m", "age_ms"}}
        response = self.client.post("/api/community/resolve", json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["istatCode"], "093033")
        self.assertEqual(response.json()["nearbyPlaces"][0]["lat"], 45.9567)
        self.assertNotIn("lat", response.json())

    def test_withdraw_ownership_preserves_minimum_interval_and_expiry(self):
        report = self.post_report().json()["report"]
        url = f"/api/community/reports/{report['id']}"
        duplicate = self.post_report()
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(
            duplicate.json()["detail"]["code"],
            "community_observation_already_recent",
        )
        self.assertEqual(self.withdraw(report["id"], client_id="other").status_code, 403)
        self.assertEqual(self.withdraw(report["id"]).status_code, 200)
        self.assertFalse(self.feed().json()["reports"])
        self.assertEqual(self.post_report().status_code, 429)
        self.clock.value += 120
        replacement = self.post_report().json()["report"]
        self.clock.value += 61
        withdrawal = self.withdraw(replacement["id"])
        self.assertEqual(withdrawal.status_code, 200)
        self.assertEqual(withdrawal.json()["action"], "withdrawn")
        self.assertEqual(self.post_report().status_code, 429)
        self.clock.value += 3540
        self.assertFalse(self.feed().json()["reports"])
        self.assertEqual(self.post_report().status_code, 200)

    def test_update_before_expiry_renews_same_observation_atomically(self):
        created = self.post_report().json()
        report_id = created["report"]["id"]
        stored_before = deepcopy(self.service.repository._reports[report_id])
        cooldown_before = dict(self.service.repository._cooldowns)
        self.clock.value = stored_before["expires_at"] - .001

        response = self.patch_report(report_id)

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "updated")
        self.assertFalse(payload["idempotent_replay"])
        self.assertEqual(payload["revision"], 2)
        self.assertEqual(payload["report"]["id"], report_id)
        self.assertEqual(payload["report"]["revision"], 2)
        self.assertEqual(payload["updated_at"], int(self.clock.value * 1000))
        self.assertEqual(
            payload["previous_expires_at"],
            int(stored_before["expires_at"] * 1000),
        )
        stored = self.service.repository._reports[report_id]
        self.assertEqual(stored["created_at"], stored_before["created_at"])
        self.assertEqual(stored["group_id"], stored_before["group_id"])
        self.assertEqual(stored["type_id"], stored_before["type_id"])
        self.assertEqual(stored["istat_code"], stored_before["istat_code"])
        self.assertEqual(stored["updated_at"], self.clock.value)
        self.assertEqual(stored["expires_at"], self.clock.value + 3600)
        self.assertEqual(stored["revision"], 2)
        immutable_fields = {
            key: value for key, value in stored_before.items()
            if key not in {"updated_at", "expires_at", "revision"}
        }
        self.assertEqual(
            {
                key: value for key, value in stored.items()
                if key not in {"updated_at", "expires_at", "revision"}
            },
            immutable_fields,
        )
        self.assertEqual(set(self.service.repository._reports), {report_id})
        self.assertLessEqual(
            max(cooldown_before.values()), self.clock.value,
        )
        self.assertFalse(self.service.repository._cooldowns)
        self.assertFalse(self.service.repository._reputations)
        feed_report = self.feed().json()["reports"][0]
        self.assertEqual(feed_report["revision"], 2)
        self.assertEqual(feed_report["updatedAt"], int(self.clock.value * 1000))
        self.assertEqual(feed_report["createdAt"], created["report"]["createdAt"])

    def test_update_rejects_another_detected_municipality_even_if_nearby(self):
        created = self.post_report("093017")
        self.assertEqual(created.status_code, 200, created.text)
        report = created.json()["report"]
        self.assertEqual(report["istatCode"], "093017")

        updated = self.patch_report(report["id"], code="093017")

        self.assertEqual(updated.status_code, 409, updated.text)
        self.assertEqual(updated.json()["detail"]["code"], "community_observation_location_changed")
        self.assertEqual(self.service.repository._reports[report["id"]]["revision"], 1)

    def test_update_at_or_after_expiry_is_explicit_and_has_no_business_side_effects(self):
        for offset in (0, .001):
            with self.subTest(offset=offset):
                self.setUp()
                created = self.post_report().json()
                report_id = created["report"]["id"]
                stored = deepcopy(self.service.repository._reports[report_id])
                cooldown = deepcopy(self.service.repository._cooldowns)
                confirmations = deepcopy(self.service.repository._confirmations)
                reputations = deepcopy(self.service.repository._reputations)
                self.clock.value = stored["expires_at"] + offset

                response = self.patch_report(report_id)

                self.assertEqual(response.status_code, 409, response.text)
                detail = response.json()["detail"]
                self.assertEqual(detail["code"], "community_observation_expired")
                self.assertEqual(
                    detail["message"],
                    "Questa osservazione è scaduta. Per descrivere la situazione attuale, invia una nuova osservazione.",
                )
                self.assertEqual(detail["state"]["status"], "expired")
                self.assertEqual(detail["state"]["expires_at"], int(stored["expires_at"] * 1000))
                self.assertEqual(detail["state"]["server_time"], int(self.clock.value * 1000))
                self.assertEqual(detail["state"]["revision"], 1)
                self.assertNotIn(report_id, self.service.repository._reports)
                tombstone = self.service.repository._expired_observations[report_id]
                self.assertEqual(tombstone["owner_key"], stored["owner_key"])
                self.assertEqual(set(tombstone) - {"reconcile_until"}, {
                    "report_id", "owner_key", "status", "expires_at", "revision",
                })
                self.assertLessEqual(max(cooldown.values()), self.clock.value)
                self.assertFalse(self.service.repository._cooldowns)
                self.assertEqual(self.service.repository._confirmations, confirmations)
                self.assertEqual(self.service.repository._reputations, reputations)
                self.assertFalse(self.service.repository._update_receipts)

    def test_update_retry_is_idempotent_even_with_new_gps_sample(self):
        report_id = self.post_report().json()["report"]["id"]
        self.clock.value += 100
        first = self.patch_report(report_id).json()
        first_expiry = self.service.repository._reports[report_id]["expires_at"]
        first_updated = self.service.repository._reports[report_id]["updated_at"]
        # The original observation would now be expired, but the accepted
        # operation renewed it. A retry must replay, not extend it again.
        self.clock.value = first["previous_expires_at"] / 1000 + 1

        retry = self.patch_report(
            report_id, lat=45.957, lon=12.661,
            accuracy_m=35, age_ms=500,
        )

        self.assertEqual(retry.status_code, 200, retry.text)
        replay = retry.json()
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["revision"], first["revision"])
        self.assertEqual(replay["updated_at"], first["updated_at"])
        self.assertEqual(replay["previous_expires_at"], first["previous_expires_at"])
        self.assertEqual(self.service.repository._reports[report_id]["expires_at"], first_expiry)
        self.assertEqual(self.service.repository._reports[report_id]["updated_at"], first_updated)

    def test_update_idempotency_and_revision_conflicts_do_not_mutate(self):
        report_id = self.post_report().json()["report"]["id"]
        self.clock.value += 100
        self.assertEqual(self.patch_report(report_id).status_code, 200)
        snapshot = deepcopy(self.service.repository._reports[report_id])

        reused = self.patch_report(report_id, expected_revision=2)
        self.assertEqual(reused.status_code, 409)
        self.assertEqual(reused.json()["detail"]["code"], "community_idempotency_conflict")
        stale = self.patch_report(
            report_id, operation_id="update-operation-0002",
            expected_revision=1,
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["detail"]["code"], "community_observation_revision_conflict")
        self.assertEqual(self.service.repository._reports[report_id], snapshot)

    def test_expired_tombstone_survives_feed_reconciliation_then_expires(self):
        report_id = self.post_report().json()["report"]["id"]
        expiry = self.service.repository._reports[report_id]["expires_at"]
        self.clock.value = expiry + 10
        self.assertEqual(self.feed().json()["reports"], [])
        self.assertNotIn(report_id, self.service.repository._reports)

        expired = self.patch_report(report_id)
        self.assertEqual(expired.status_code, 409)
        self.assertEqual(expired.json()["detail"]["code"], "community_observation_expired")

        self.clock.value = expiry + 3600.001
        unavailable = self.patch_report(
            report_id, operation_id="update-operation-0003",
        )
        self.assertEqual(unavailable.status_code, 404)
        self.assertEqual(unavailable.json()["detail"]["code"], "community_observation_not_active")
        self.assertNotIn(report_id, self.service.repository._expired_observations)

    def test_update_preserves_and_extends_confirmation_state(self):
        report = self.post_report().json()["report"]
        confirmation_url = f"/api/community/reports/{report['groupId']}/confirmation"
        confirmed = self.client.post(
            confirmation_url,
            json={"vote": "yes", "client_id": "reader"},
            headers=self.headers,
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        confirmation_before = deepcopy(
            self.service.repository._confirmations[report["groupId"]]
        )
        self.clock.value += 120

        updated = self.patch_report(report["id"])

        self.assertEqual(updated.status_code, 200, updated.text)
        confirmation_after = self.service.repository._confirmations[report["groupId"]]
        self.assertEqual(confirmation_after["votes"], confirmation_before["votes"])
        self.assertEqual(confirmation_after["yes"], 1)
        self.assertEqual(confirmation_after["no"], 0)
        self.assertEqual(
            confirmation_after["expires_at_timestamp"].timestamp(),
            self.service.repository._reports[report["id"]]["expires_at"],
        )

    def test_denial_after_update_uses_renewed_expiry_and_blocks_later_update(self):
        report = self.post_report().json()["report"]
        self.clock.value += 120
        updated = self.patch_report(report["id"])
        self.assertEqual(updated.status_code, 200, updated.text)
        renewed = deepcopy(self.service.repository._reports[report["id"]])

        denied = self.client.post(
            f"/api/community/reports/{report['groupId']}/confirmation",
            json={"vote": "no", "client_id": "reader"},
            headers=self.headers,
        )

        self.assertEqual(denied.status_code, 200, denied.text)
        after_denial = self.service.repository._reports[report["id"]]
        self.assertEqual(after_denial["id"], renewed["id"])
        self.assertEqual(after_denial["revision"], renewed["revision"])
        self.assertEqual(after_denial["expires_at"], renewed["expires_at"])
        confirmation = self.service.repository._confirmations[report["groupId"]]
        self.assertEqual(confirmation["no"], 1)
        self.assertFalse(confirmation["map_withdrawn"])
        self.assertEqual(
            confirmation["expires_at_timestamp"].timestamp(),
            renewed["expires_at"],
        )
        report_before_retry = deepcopy(after_denial)
        confirmation_before_retry = deepcopy(confirmation)

        blocked = self.patch_report(
            report["id"], operation_id="update-operation-0002",
            expected_revision=2,
        )

        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertEqual(
            blocked.json()["detail"]["code"],
            "community_observation_not_updateable",
        )
        self.assertEqual(
            self.service.repository._reports[report["id"]],
            report_before_retry,
        )
        self.assertEqual(
            self.service.repository._confirmations[report["groupId"]],
            confirmation_before_retry,
        )

    def test_refreshed_older_contribution_extends_its_public_group(self):
        first = self.post_report(client_id="sender").json()["report"]
        self.clock.value += 10
        second = self.post_report(client_id="other").json()["report"]
        self.assertEqual(first["groupId"], second["groupId"])
        self.clock.value += 90

        updated = self.patch_report(first["id"])

        self.assertEqual(updated.status_code, 200, updated.text)
        payload = self.feed().json()
        group = payload["map_groups"][0]
        self.assertEqual(group["expiresAt"], updated.json()["report"]["expiresAt"])
        self.assertEqual(group["updatedAt"], updated.json()["updated_at"])
        self.assertEqual(group["count"], 2)

    def test_two_concurrent_updates_of_one_revision_commit_only_once(self):
        report_id = self.post_report().json()["report"]["id"]
        self.clock.value += 100
        gate = Barrier(2)

        def update(operation_id):
            command = PilotCommunityObservationUpdate(**self.update_command(
                operation_id=operation_id,
            ))
            gate.wait(timeout=5)
            try:
                result = self.service.update_observation(
                    report_id, command, client_host="test",
                )
                return ("ok", result["revision"])
            except CommunityServiceError as error:
                return ("error", error.detail.get("code"))

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                update,
                ("concurrent-update-0001", "concurrent-update-0002"),
            ))

        self.assertEqual(results.count(("ok", 2)), 1)
        self.assertEqual(
            results.count(("error", "community_observation_revision_conflict")),
            1,
        )
        self.assertEqual(self.service.repository._reports[report_id]["revision"], 2)
        self.assertEqual(len(self.service.repository._update_receipts), 1)

    def test_concurrent_update_and_withdraw_never_resurrect_report(self):
        report_id = self.post_report().json()["report"]["id"]
        self.clock.value += 61
        gate = Barrier(2)

        def update():
            gate.wait(timeout=5)
            try:
                self.service.update_observation(
                    report_id,
                    PilotCommunityObservationUpdate(**self.update_command()),
                    client_host="test",
                )
                return "updated"
            except CommunityServiceError as error:
                return str(error.detail.get("code") if isinstance(error.detail, dict) else error.status_code)

        def withdraw():
            gate.wait(timeout=5)
            try:
                self.service.delete_report(
                    report_id,
                    PilotCommunityReportDelete(
                        client_id="sender", action="withdraw",
                        operation_id="withdraw-operation-0001", expected_revision=1,
                    ),
                    client_host="test",
                )
                return "withdrawn"
            except CommunityServiceError as error:
                return str(error.status_code)

        with ThreadPoolExecutor(max_workers=2) as executor:
            update_future = executor.submit(update)
            withdraw_future = executor.submit(withdraw)
            outcomes = {update_future.result(), withdraw_future.result()}

        if "withdrawn" not in outcomes:
            # The update may win revision 1; withdrawal must then reconcile
            # and explicitly act on revision 2, never delete a stale version.
            self.assertIn("updated", outcomes)
            current = self.service.repository._reports[report_id]
            withdrawn = self.withdraw(report_id, expected_revision=current["revision"])
            self.assertEqual(withdrawn.status_code, 200, withdrawn.text)
        self.assertNotIn(report_id, self.service.repository._reports)
        self.assertFalse(self.feed().json()["reports"])
        self.assertNotIn(report_id, self.service.repository._update_receipts)

    def test_update_rejects_bad_gps_owner_source_block_and_hidden_group(self):
        cases = [
            ({"age_ms": 120001}, 400, "community_fresh_gps_required"),
            ({"accuracy_m": 501}, 400, "community_fresh_gps_required"),
            ({"lat": 48, "lon": 16}, 403, "community_location_outside_italy"),
            ({"client_id": "other"}, 403, "community_observation_owner_mismatch"),
        ]
        for changes, status, code in cases:
            with self.subTest(code=code):
                self.setUp()
                report_id = self.post_report().json()["report"]["id"]
                snapshot = deepcopy(self.service.repository._reports[report_id])
                response = self.patch_report(report_id, **changes)
                self.assertEqual(response.status_code, status, response.text)
                self.assertEqual(response.json()["detail"]["code"], code)
                self.assertEqual(self.service.repository._reports[report_id], snapshot)

        self.setUp()
        report_id = self.post_report().json()["report"]["id"]
        stored = self.service.repository._reports[report_id]
        self.service.repository.set_source_block(
            stored["owner_key"], blocked_until=self.clock.value + 600,
            reason="test",
        )
        blocked = self.patch_report(report_id)
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["detail"]["code"], "community_source_temporarily_blocked")
        self.assertEqual(self.service.repository._reports[report_id]["revision"], 1)

        self.setUp()
        report_id = self.post_report().json()["report"]["id"]
        self.service.repository._reports[report_id]["moderation_hidden"] = True
        hidden = self.patch_report(report_id)
        self.assertEqual(hidden.status_code, 409)
        self.assertEqual(hidden.json()["detail"]["code"], "community_group_hidden")
        self.assertEqual(self.service.repository._reports[report_id]["revision"], 1)

    def test_update_after_subthreshold_denials_is_rejected_without_mutation(self):
        for denial_count in (1, 2):
            with self.subTest(denial_count=denial_count):
                self.setUp()
                report = self.post_report().json()["report"]
                confirmation_url = (
                    f"/api/community/reports/{report['groupId']}/confirmation"
                )
                for index in range(denial_count):
                    denied = self.client.post(
                        confirmation_url,
                        json={"vote": "no", "client_id": f"reader-{index}"},
                        headers=self.headers,
                    )
                    self.assertEqual(denied.status_code, 200, denied.text)

                report_before = deepcopy(
                    self.service.repository._reports[report["id"]]
                )
                confirmation_before = deepcopy(
                    self.service.repository._confirmations[report["groupId"]]
                )
                self.assertEqual(confirmation_before["no"], denial_count)
                self.assertFalse(confirmation_before["map_withdrawn"])
                self.assertEqual(confirmation_before["temporal_status"], "ceased")

                updated = self.patch_report(report["id"])

                self.assertEqual(updated.status_code, 409, updated.text)
                self.assertEqual(
                    updated.json()["detail"]["code"],
                    "community_observation_not_updateable",
                )
                self.assertEqual(
                    self.service.repository._reports[report["id"]],
                    report_before,
                )
                self.assertEqual(
                    self.service.repository._confirmations[report["groupId"]],
                    confirmation_before,
                )

    def test_update_cannot_revive_an_observation_withdrawn_by_denials(self):
        report = self.post_report().json()["report"]
        confirmation_url = f"/api/community/reports/{report['groupId']}/confirmation"
        for index in range(3):
            response = self.client.post(
                confirmation_url,
                json={"vote": "no", "client_id": f"reader-{index}"},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 200, response.text)
        stored_before = deepcopy(self.service.repository._reports[report["id"]])
        confirmation_before = deepcopy(
            self.service.repository._confirmations[report["groupId"]]
        )
        self.assertTrue(stored_before["map_withdrawn"])
        self.assertTrue(confirmation_before["map_withdrawn"])

        updated = self.patch_report(report["id"])

        self.assertEqual(updated.status_code, 409, updated.text)
        self.assertEqual(
            updated.json()["detail"]["code"],
            "community_observation_not_updateable",
        )
        self.assertEqual(
            self.service.repository._reports[report["id"]],
            stored_before,
        )
        self.assertEqual(
            self.service.repository._confirmations[report["groupId"]],
            confirmation_before,
        )

    def test_quiet_observation_remains_updateable_when_normally_excluded(self):
        report = self.post_report(type_id="quiet").json()["report"]
        stored = self.service.repository._reports[report["id"]]
        self.assertEqual(stored["validity_status"], "excluded")
        self.assertEqual(stored["temporal_status"], "active")

        updated = self.patch_report(report["id"])

        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["revision"], 2)

    def test_successful_update_does_not_change_cooldown_or_reputation_ledgers(self):
        report_id = self.post_report().json()["report"]["id"]
        self.clock.value += 100
        cooldown = deepcopy(self.service.repository._cooldowns)
        reputations = deepcopy(self.service.repository._reputations)
        awards = deepcopy(self.service.repository._reputation_awards)

        response = self.patch_report(report_id)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.service.repository._cooldowns, cooldown)
        self.assertEqual(self.service.repository._reputations, reputations)
        self.assertEqual(self.service.repository._reputation_awards, awards)

    def test_owner_can_create_different_phenomenon_after_minimum_interval(self):
        first = self.post_report().json()["report"]
        cooldown_until = next(iter(self.service.repository._cooldowns.values()))
        self.clock.value = cooldown_until
        second = self.post_report(type_id="wind")
        self.assertEqual(second.status_code, 200, second.text)
        duplicate = self.post_report(type_id="rain")
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        self.assertEqual(duplicate.json()["detail"]["code"], "community_observation_already_recent")
        self.assertEqual(len(self.service.repository._reports), 2)
        self.assertIn(first["id"], self.service.repository._reports)

    def test_explicit_withdrawal_preserves_cooldown_even_inside_quick_undo_window(self):
        created = self.post_report().json()
        response = self.withdraw(created["report"]["id"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["action"], "withdrawn")
        self.assertEqual(response.json()["cooldown_until"], created["cooldown_until"])
        self.assertFalse(self.feed().json()["reports"])
        self.assertEqual(self.post_report().status_code, 429)
        self.clock.value += 120
        self.assertEqual(self.post_report().status_code, 200)

    def test_withdrawal_removes_only_own_contribution_and_preserves_group_votes(self):
        first = self.post_report(client_id="sender").json()["report"]
        second = self.post_report(client_id="other").json()["report"]
        self.assertEqual(first["groupId"], second["groupId"])
        self.client.post(
            f"/api/community/reports/{first['groupId']}/confirmation",
            json={"client_id": "reader", "vote": "yes"}, headers=self.headers,
        )
        self.assertEqual(self.feed().json()["map_groups"][0]["count"], 2)
        self.clock.value += 61
        url = f"/api/community/reports/{first['id']}"
        unauthorized = self.withdraw(first["id"], client_id="other")
        self.assertEqual(unauthorized.status_code, 403)
        response = self.withdraw(first["id"])
        self.assertEqual(response.status_code, 200)
        payload = self.feed().json()
        self.assertEqual([item["id"] for item in payload["reports"]], [second["id"]])
        self.assertEqual(payload["map_groups"][0]["count"], 1)
        self.assertEqual(payload["map_groups"][0]["reportIds"], [second["id"]])
        self.assertEqual(payload["map_groups"][0]["confirmations"]["yes"], 1)
        self.assertEqual(self.post_report(client_id="sender").status_code, 429)

    def test_withdrawal_expired_unknown_and_invalid_owner_fail_safely(self):
        report = self.post_report().json()["report"]
        url = f"/api/community/reports/{report['id']}"
        self.assertEqual(self.withdraw(report["id"], client_id="").status_code, 400)
        self.assertEqual(self.withdraw("missing").status_code, 404)
        self.clock.value += 3600
        self.assertEqual(self.withdraw(report["id"]).status_code, 409)
        self.assertFalse(self.feed().json()["map_groups"])

    def test_legacy_undo_is_rejected_without_mutation_and_withdraw_is_idempotent(self):
        report = self.post_report().json()["report"]
        url = f"/api/community/reports/{report['id']}"
        self.clock.value += 61
        self.assertEqual(self.withdraw(report["id"], action="undo").status_code, 422)
        self.assertEqual(len(self.feed().json()["reports"]), 1)
        first = self.withdraw(report["id"], operation_id="withdraw-idempotent-0001")
        second = self.withdraw(report["id"], operation_id="withdraw-idempotent-0001")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertTrue(second.json()["idempotent_replay"])

    def test_published_service_keeps_its_existing_undo_only_semantics(self):
        service = CommunityService(now=self.clock)
        command = CommunityReportCreate(**{
            key: value for key, value in self.command().items()
            if key in CommunityReportCreate.model_fields
        })
        report = service.create_report(command, client_host="test").report
        self.clock.value += 61
        with self.assertRaises(CommunityServiceError) as denied:
            service.delete_report(report.id, CommunityReportDelete(client_id="sender"), client_host="test")
        self.assertEqual(denied.exception.status_code, 409)
        self.assertEqual(len(service.get_reports().reports), 1)

    def test_confirm_flag_reputation_and_source_block_reuse(self):
        group = self.post_report().json()["report"]["groupId"]
        confirmation_url = f"/api/community/reports/{group}/confirmation"
        self.assertEqual(self.client.post(confirmation_url, json={"vote": "yes", "client_id": "sender"}, headers=self.headers).status_code, 403)
        for voter in ["reader1", "reader2", "reader3"]:
            response = self.client.post(confirmation_url, json={"vote": "yes", "client_id": voter}, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.feed().json()["map_groups"][0]["confirmations"]["yes"], 3)
        reputation = self.client.post("/api/community/reputation", json={"client_id": "sender"}, headers=self.headers)
        self.assertEqual(reputation.status_code, 200)
        self.assertGreaterEqual(reputation.json()["points"], 1)
        flagged = self.client.post(f"/api/community/reports/{group}/flags", json={"reason": "inaccurate", "client_id": "reader1"}, headers=self.headers)
        self.assertEqual(flagged.status_code, 200)
        self.assertFalse(flagged.json()["hidden_global"])
        self.assertTrue(self.feed().json()["reports"])

    def test_missing_global_scope_and_oversized_radius_rejected(self):
        self.assertEqual(self.client.get("/api/community/reports").status_code, 400)
        self.assertEqual(self.client.get("/api/community/reports?istat_code=093033&radius_km=999").status_code, 422)
        self.assertEqual(self.client.get("/api/community/reports?lat=48&lon=16").status_code, 403)
        self.assertEqual(self.client.get("/api/community/reports?lat=45.9567&lon=12.6605").status_code, 200)

    def test_mutations_require_local_header_origin_and_host(self):
        for headers in [
            {}, {**self.headers, "Origin": "https://meteo-friul.web.app"},
            {**self.headers, "Origin": "https://evil.example"},
            {**self.headers, "Host": "evil.example:8783"},
        ]:
            self.assertEqual(self.client.post("/api/community/reports", json=self.command(), headers=headers).status_code, 403)
        for origin in ["http://127.0.0.1:5174", "https://localhost"]:
            preflight = self.client.options("/api/community/reports", headers={
                "Origin": origin, "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-meteo-pilot-community",
            })
            self.assertEqual(preflight.status_code, 200)
            self.assertEqual(preflight.headers["access-control-allow-origin"], origin)

    def test_patch_is_pilot_only_cors_guarded_and_body_bounded(self):
        report_id = self.post_report().json()["report"]["id"]
        url = f"/api/community/reports/{report_id}"
        command = self.update_command()
        self.assertEqual(self.client.patch(url, json=command).status_code, 403)
        self.assertEqual(self.client.patch(
            url, json=command,
            headers={**self.headers, "Origin": "https://evil.example"},
        ).status_code, 403)
        self.assertEqual(self.client.patch(
            url, content="x" * 8193, headers=self.headers,
        ).status_code, 413)
        preflight = self.client.options(url, headers={
            "Origin": "http://127.0.0.1:5174",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type,x-meteo-pilot-community",
        })
        self.assertEqual(preflight.status_code, 200)
        self.assertIn("PATCH", preflight.headers["access-control-allow-methods"])

        published_methods = {
            method
            for route in published_live_router.routes
            if route.path == "/api/community/reports/{report_id}"
            for method in (route.methods or set())
        }
        self.assertEqual(published_methods, {"DELETE"})
        self.assertFalse(hasattr(CommunityService, "update_observation"))

    def test_request_size_and_validation_do_not_echo_gps(self):
        response = self.client.post("/api/community/reports", content="x"*8193, headers=self.headers)
        self.assertEqual(response.status_code, 413)
        response = self.post_report(lat=112.345678)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("112.345678", response.text)

    def test_memory_isolation_even_with_production_environment(self):
        with patch.dict(os.environ, {"COMMUNITY_STORAGE_MODE": "firestore", "GOOGLE_CLOUD_PROJECT": "production"}):
            service = PilotCommunityService(geography=FixtureGeography())
        self.assertFalse(service.repository.requires_firestore)
        self.assertIsNone(service.repository._db())
        self.post_report()
        fresh = PilotCommunityService(geography=FixtureGeography())
        self.assertEqual(fresh.repository.list_reports(self.clock.value)[0], [])
        self.assertEqual(self.client.get("/api/community/health").json()["published"], False)

    def test_global_rate_is_bounded_and_recovers(self):
        for index in range(20):
            self.assertEqual(self.post_report(client_id=f"client-{index}").status_code, 200)
        self.assertEqual(self.post_report(client_id="new").status_code, 429)
        self.clock.value += 61
        self.assertEqual(self.post_report(client_id="new").status_code, 200)

    def test_distant_national_activity_cannot_evict_a_local_report(self):
        local = self.post_report().json()["report"]
        for index in range(220):
            self.clock.value += 4
            response = self.post_report("041067", client_id=f"distant-{index}")
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.service.repository._reports), 221)
        local_feed = self.feed().json()
        self.assertEqual([item["id"] for item in local_feed["reports"]], [local["id"]])
        self.assertEqual(len(self.feed("041067").json()["reports"]), 200)
        self.clock.value += 3601
        self.assertFalse(self.feed().json()["reports"])
        self.assertFalse(self.service.repository._municipality_reports)
        self.assertFalse(self.service.repository._municipality_points)

    def test_hidden_local_reports_do_not_consume_visible_scoped_slots(self):
        municipality = self.service.pilot_geography.match_istat("093033")
        for index in range(205):
            report = self.service._build_report(
                type_id="rain", municipality=municipality, owner_key=f"owner-{index}",
                now=self.clock.value,
            )
            report["moderation_hidden"] = index > 0
            self.service.repository.save_report(report)
        self.assertEqual(len(self.feed().json()["reports"]), 1)

    def test_source_block_and_hidden_group_remain_enforced(self):
        owner = self.service._client_key("community-report", "blocked")
        self.service.repository.set_source_block(owner, blocked_until=self.clock.value+7200, reason="misuse")
        response = self.post_report(client_id="blocked")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "community_source_temporarily_blocked")
        report = self.post_report().json()["report"]
        # Simulate an existing moderation decision in the shared repository.
        self.service.repository._reports[report["id"]]["moderation_hidden"] = True
        self.assertFalse(self.feed().json()["reports"])

    def test_feed_cannot_resurrect_an_expired_report_or_change_coordinates(self):
        report = self.post_report().json()["report"]
        stored = self.service.repository._reports[report["id"]]
        stored["lat"], stored["lon"] = 12.34567, 78.98765
        public = self.feed().json()["reports"][0]
        self.assertEqual((public["lat"], public["lon"]), (45.9567, 12.6605))
        stored["expires_at"] = stored["created_at"] + 7200
        self.assertFalse(self.feed().json()["reports"])

    def test_entrypoint_imports_no_cloud_runtime_and_cannot_bind_lan(self):
        result = subprocess.run([
            sys.executable, "-c",
            "import sys; import app.pilot_community; assert 'app.infrastructure.firebase' not in sys.modules; assert 'firebase_admin' not in sys.modules",
        ], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([
            sys.executable, "-m", "app.pilot_community", "--host", "0.0.0.0",
        ], capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
