import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.live import get_community_service, get_webcam_manifest_service
from app.contracts.live import (
    CommunityConfirmationResponse,
    CommunityReportCreatedResponse,
    CommunityReportDeletedResponse,
    CommunityReportFlaggedResponse,
    CommunityReputationResponse,
    WebcamManifestResponse,
)
from app.main import create_app
from app.services.community import (
    COMMUNITY_GUIDELINES_POLICY_VERSION,
    CommunityService,
    CommunityServiceError,
)


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = WORKSPACE_ROOT / "contracts" / "runtime-api" / "v1" / "live"


def fixture(name):
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class FixtureWebcamService:
    def get_manifest(self):
        return WebcamManifestResponse.model_validate(fixture("webcams-success.json"))


class FixtureCommunityService:
    def get_reports(self):
        return CommunityService(now=lambda: 1786269600.0).get_reports()

    def create_report(self, command, client_host):
        return CommunityReportCreatedResponse.model_validate(
            fixture("community-created.json")
        )

    def delete_report(self, report_id, command, client_host):
        return CommunityReportDeletedResponse.model_validate(
            fixture("community-deleted.json")
        )

    def confirm_report(self, group_id, command, client_host):
        return CommunityConfirmationResponse.model_validate(
            fixture("community-confirmed.json")
        )

    def flag_report_group(self, group_id, command, client_host):
        return CommunityReportFlaggedResponse.model_validate(
            fixture("community-flagged.json")
        )

    def get_reputation(self, command, client_host):
        return CommunityReputationResponse.model_validate(
            fixture("community-reputation.json")
        )


class ErrorCommunityService(FixtureCommunityService):
    def create_report(self, command, client_host):
        raise CommunityServiceError(429, {
            "message": "Puoi inviare una nuova segnalazione piu tardi.",
            "retry_after_seconds": 120,
        })


class StorageErrorCommunityService(FixtureCommunityService):
    def get_reports(self):
        raise CommunityServiceError(503, {
            "message": "Il servizio segnalazioni è temporaneamente non disponibile.",
            "code": "community_storage_unavailable",
        })


class LiveApiTests(unittest.TestCase):
    def create_client(self, community_service=None):
        app = create_app()
        app.dependency_overrides[get_webcam_manifest_service] = FixtureWebcamService
        app.dependency_overrides[get_community_service] = lambda: (
            community_service or FixtureCommunityService()
        )
        return TestClient(app)

    def test_webcam_contract(self):
        response = self.create_client().get("/api/live/webcams")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fixture("webcams-success.json"))

    def test_empty_community_contract(self):
        response = self.create_client().get("/api/community/reports")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["reports"], [])
        self.assertEqual(payload["map_groups"], [])
        self.assertEqual(len(payload["locations"]), 215)
        self.assertEqual(
            payload["contract"]["schema_version"],
            "community-ephemeral-safety-v1",
        )
        self.assertEqual(
            payload["contract"]["location_catalog_sha256"],
            "a387ff7f1f704695361597b054556ff82a6a8739373eb0af465b81b1f3b89dae",
        )
        self.assertEqual(
            payload["contract"]["user_flag_visibility"],
            "local_only",
        )
        self.assertFalse(payload["contract"]["automatic_global_hide"])

    def test_private_community_reputation_contract(self):
        response = self.create_client().post(
            "/api/community/reputation",
            json={"client_id": "private-installation-id"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fixture("community-reputation.json"))
        self.assertNotIn("private-installation-id", response.text)
        self.assertNotIn("owner", response.text)

    def test_create_report_contract(self):
        response = self.create_client().post("/api/community/reports", json={
            "accepted_terms": True,
            "type_id": "rain",
            "lat": 45.95689,
            "lon": 12.66051,
            "selected_place": "Pordenone",
            "client_id": "client-1",
            "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fixture("community-created.json"))

    def test_create_report_accepts_only_the_versioned_public_identity_shape(self):
        payload = {
            "accepted_terms": True,
            "type_id": "rain",
            "lat": 45.95689,
            "lon": 12.66051,
            "selected_place": "Pordenone",
            "client_id": "client-1",
            "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
            "identity": {
                "version": 1,
                "alias": "Clâf di Pordenon",
                "subject_id": "claf",
                "avatar": {
                    "palette_id": "sky",
                    "pattern_id": "diagonal",
                    "variant": 2,
                    "angle": 135,
                },
            },
        }

        accepted = self.create_client().post("/api/community/reports", json=payload)
        self.assertEqual(accepted.status_code, 200)

        current_alias = self.create_client().post(
            "/api/community/reports",
            json={
                **payload,
                "client_id": "client-current-alias",
                "identity": {**payload["identity"], "alias": "Clâf dal Fogolâr"},
            },
        )
        self.assertEqual(current_alias.status_code, 200)

        invalid_identities = (
            {**payload["identity"], "version": 2},
            {**payload["identity"], "version": "1"},
            {**payload["identity"], "alias": "🦅 Clâf di Pordenon"},
            {**payload["identity"], "alias": "Ключ di Pordenon"},
            {**payload["identity"], "alias": "Ors di Udin"},
            {**payload["identity"], "alias": "Clâf dal Colosseu"},
            {**payload["identity"], "subject_id": "free-text-subject"},
            {**payload["identity"], "owner_key": "private-owner"},
            {
                **payload["identity"],
                "avatar": {
                    **payload["identity"]["avatar"],
                    "palette_id": "neon-custom",
                },
            },
            {
                **payload["identity"],
                "avatar": {
                    **payload["identity"]["avatar"],
                    "variant": 4,
                },
            },
            {
                **payload["identity"],
                "avatar": {
                    **payload["identity"]["avatar"],
                    "angle": "135",
                },
            },
            {
                **payload["identity"],
                "avatar": {
                    **payload["identity"]["avatar"],
                    "client_id": "private-client",
                },
            },
        )
        for identity in invalid_identities:
            with self.subTest(identity=identity):
                rejected = self.create_client().post(
                    "/api/community/reports",
                    json={**payload, "identity": identity},
                )
                self.assertEqual(rejected.status_code, 422)

    def test_create_and_list_publish_identity_without_private_ownership_fields(self):
        service = CommunityService(
            now=lambda: 1786269600.0,
            report_id_factory=lambda: "community-identity-test",
        )
        client = self.create_client(service)
        identity = {
            "version": 1,
            "alias": "Clâf di Pordenon",
            "subject_id": "claf",
            "avatar": {
                "palette_id": "sky",
                "pattern_id": "diagonal",
                "variant": 2,
                "angle": 135,
            },
        }
        response = client.post("/api/community/reports", json={
            "accepted_terms": True,
            "type_id": "rain",
            "lat": 45.95689,
            "lon": 12.66051,
            "selected_place": "Pordenone",
            "client_id": "private-installation-id",
            "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
            "identity": identity,
        })
        feed = client.get("/api/community/reports")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(feed.status_code, 200)
        created = response.json()["report"]
        listed = feed.json()
        self.assertEqual(created["identity"], identity)
        self.assertEqual(listed["reports"][0]["identity"], identity)
        self.assertEqual(
            listed["map_groups"][0]["identities"],
            [{"sourceKey": created["sourceKey"], "identity": identity}],
        )
        serialized = json.dumps({"created": response.json(), "feed": listed})
        self.assertNotIn("private-installation-id", serialized)
        self.assertNotIn("owner_key", serialized)
        self.assertNotIn("client_id", created)
        self.assertNotIn("client_id", listed["reports"][0])
        self.assertNotIn("client_id", listed["map_groups"][0])

    def test_delete_report_contract(self):
        response = self.create_client().request(
            "DELETE",
            "/api/community/reports/community-test-1",
            json={"client_id": "client-1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fixture("community-deleted.json"))

    def test_confirmation_contract(self):
        group_id = "group-rain:pordenone:496186"
        response = self.create_client().post(
            f"/api/community/reports/{group_id}/confirmation",
            json={
                "accepted_terms": True,
                "client_id": "client-1",
                "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
                "vote": "yes",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fixture("community-confirmed.json"))

    def test_confirmation_accepts_the_exact_play_300011_legacy_payload(self):
        group_id = "group-rain:pordenone:496186"
        response = self.create_client().post(
            f"/api/community/reports/{group_id}/confirmation",
            json={"client_id": "legacy-play-client", "vote": "yes"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fixture("community-confirmed.json"))

    def test_confirmation_rejects_unknown_extra_fields(self):
        group_id = "group-rain:pordenone:496186"
        response = self.create_client().post(
            f"/api/community/reports/{group_id}/confirmation",
            json={
                "client_id": "legacy-play-client",
                "comment": "free text is intentionally forbidden",
                "vote": "yes",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_flag_contract(self):
        group_id = "group-rain:pordenone:496186"
        response = self.create_client().post(
            f"/api/community/reports/{group_id}/flags",
            json={"client_id": "client-flagger", "reason": "inaccurate"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), fixture("community-flagged.json"))
        self.assertNotIn("client_id", response.json())
        self.assertNotIn("owner", json.dumps(response.json()))
        self.assertNotIn("flaggers", json.dumps(response.json()))

    def test_flag_contract_rejects_unknown_reason_and_extra_fields(self):
        group_id = "group-rain:pordenone:496186"
        client = self.create_client()

        unknown = client.post(
            f"/api/community/reports/{group_id}/flags",
            json={"client_id": "client-flagger", "reason": "spam"},
        )
        extra = client.post(
            f"/api/community/reports/{group_id}/flags",
            json={
                "client_id": "client-flagger",
                "reason": "misuse",
                "comment": "free text is intentionally forbidden",
            },
        )

        self.assertEqual(unknown.status_code, 422)
        self.assertEqual(extra.status_code, 422)

    def test_service_errors_keep_status_and_structured_detail(self):
        response = self.create_client(ErrorCommunityService()).post(
            "/api/community/reports",
            json={
                "accepted_terms": True,
                "type_id": "rain",
                "lat": 45.95689,
                "lon": 12.66051,
                "selected_place": "Pordenone",
                "client_id": "client-1",
                "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
            },
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"]["retry_after_seconds"], 120)
        self.assertEqual(response.headers["retry-after"], "120")

    def test_report_create_bypass_without_consent_is_400(self):
        response = self.create_client(CommunityService()).post(
            "/api/community/reports",
            json={
                "type_id": "rain",
                "lat": 45.95689,
                "lon": 12.66051,
                "selected_place": "Pordenone",
                "client_id": "client-1",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "community_terms_required")

    def test_confirmation_partial_or_invalid_new_consent_is_400(self):
        group_id = "group-rain:pordenone:496186"
        client = self.create_client(CommunityService())
        payloads = (
            {
                "accepted_terms": True,
                "client_id": "client-1",
                "vote": "yes",
            },
            {
                "client_id": "client-1",
                "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
                "vote": "yes",
            },
            {
                "accepted_terms": True,
                "client_id": "client-1",
                "policy_version": "community-guidelines-old",
                "vote": "yes",
            },
        )

        for payload in payloads:
            with self.subTest(payload=payload):
                response = client.post(
                    f"/api/community/reports/{group_id}/confirmation",
                    json=payload,
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json()["detail"]["code"],
                    "community_terms_required",
                )

    def test_get_reports_propagates_storage_503(self):
        response = self.create_client(StorageErrorCommunityService()).get(
            "/api/community/reports"
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "community_storage_unavailable",
        )

    def test_runtime_v1_contract_is_explicitly_pre_release(self):
        manifest = json.loads(
            (FIXTURE_ROOT.parent / "manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["contractStatus"]["stability"], "pre-release")
        self.assertFalse(manifest["contractStatus"]["publiclyFrozen"])
        live_endpoints = manifest["families"]["live"]["endpoints"]
        self.assertIn(
            "POST /api/community/reports/{groupId}/confirmation",
            live_endpoints,
        )
        self.assertIn(
            "POST /api/community/reports/{groupId}/flags",
            live_endpoints,
        )
        self.assertNotIn("POST /api/community/reports/{id}/flags", live_endpoints)


if __name__ == "__main__":
    unittest.main()
