from datetime import datetime, timedelta, timezone
import hashlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.pilot_community_cloud import (
    EnrolledInstallations, IngressBudget, PILOT_PROJECT, create_app,
)
from app.repositories.community import CommunityRepositoryUnavailable


class PublicCommunityApiCorsTests(unittest.TestCase):
    def setUp(self):
        self.service = Mock()
        self.service.repository = SimpleNamespace(storage_kind="community-cloud")
        self.service.get_scoped_reports.return_value = {
            "map_groups": [],
            "reports": [],
        }
        self.client = TestClient(create_app(
            service=self.service,
            public_mode=True,
            app_check_verifier=Mock(),
            allowed_app_ids=frozenset({"approved-app"}),
        ), base_url="https://pilot-community-335641913741.europe-west1.run.app")

    def test_public_site_origins_can_read_recent_reports_without_app_check(self):
        for origin in ("https://meteofriul.it", "https://www.meteofriul.it"):
            with self.subTest(origin=origin):
                response = self.client.get(
                    "/api/community/reports?istat_code=093033",
                    headers={"Origin": origin},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["Access-Control-Allow-Origin"], origin)
        self.assertEqual(self.service.get_scoped_reports.call_count, 2)
        self.service.get_scoped_reports.assert_called_with(istat_code="093033")

    def test_unrelated_site_origin_is_rejected(self):
        response = self.client.get(
            "/api/community/reports?istat_code=093033",
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        self.service.get_scoped_reports.assert_not_called()


class PrivatePilotApiTests(unittest.TestCase):
    def setUp(self):
        self.token = "T" * 43
        self.client_id = "existing-phone-identity"
        self.digest = hashlib.sha256(self.client_id.encode()).hexdigest()
        self.headers = {"Authorization": f"Bearer {self.token}",
                        "X-Meteo-Pilot-Installation": self.digest,
                        "Origin": "https://localhost"}
        self.registry = Mock()
        self.registry.permits.return_value = True
        self.service = Mock()
        self.service.repository = SimpleNamespace(storage_kind="pilot-cloud")
        self.service.get_scoped_reports.return_value = {"groups": []}
        self.service.get_reputation.return_value = {"points": 0}
        self.client = TestClient(create_app(service=self.service, installations=self.registry),
            base_url="https://pilot-community-335641913741.europe-west1.run.app")

    def test_health_is_public_but_reports_require_enrollment(self):
        self.assertEqual(self.client.get("/api/community/health").json()["project"], PILOT_PROJECT)
        self.assertEqual(self.client.get("/api/community/reports?istat_code=093033").status_code, 401)
        self.registry.permits.assert_not_called()
        result = self.client.get("/api/community/reports?istat_code=093033", headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers["Cache-Control"], "no-store")
        self.registry.permits.assert_called_once_with(hashlib.sha256(self.token.encode()).hexdigest(), self.digest)

    def test_local_header_is_not_cloud_auth(self):
        self.assertEqual(self.client.post("/api/community/resolve", json={},
            headers={"X-Meteo-Pilot-Community": "local-only"}).status_code, 401)

    def test_early_security_errors_are_readable_only_from_exact_webview_origin(self):
        response = self.client.get("/api/community/reports?istat_code=093033", headers={"Origin": "https://localhost"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://localhost")
        self.assertEqual(response.headers["Vary"], "Origin")
        self.registry.permits.assert_not_called()
        response = self.client.post("/api/community/reputation", json={"client_id": "wrong-owner"}, headers=self.headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://localhost")
        self.registry.permits.side_effect = TimeoutError("private-auth-failure")
        response = self.client.get("/api/community/reports?istat_code=093033", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://localhost")
        self.assertNotIn("private-auth-failure", response.text)
        for origin in (None, "https://localhost.evil.example", "http://localhost", "https://evil.example"):
            with self.subTest(origin=origin):
                headers = {"Origin": origin} if origin else {}
                response = self.client.get("/api/community/reports?istat_code=093033", headers=headers)
                self.assertEqual(response.status_code, 403 if origin else 401)
                self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_unauthenticated_ingress_budget_rejects_before_auth_with_readable_cors(self):
        budget = Mock()
        budget.accept.return_value = False
        client = TestClient(create_app(service=self.service, installations=self.registry, budget=budget),
                           base_url="https://pilot-community-335641913741.europe-west1.run.app")
        response = client.get("/api/community/reports?istat_code=093033", headers={"Origin": "https://localhost"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://localhost")
        budget.accept.assert_called_once_with("ingress", 240)
        self.registry.permits.assert_not_called()

    def test_wrong_host_origin_and_revoked_enrollment_fail_closed(self):
        for extra in ({"Host": "meteo-friul.run.app"}, {"Origin": "https://evil.example"}):
            self.assertEqual(self.client.get("/api/community/reports?istat_code=093033",
                headers={**self.headers, **extra}).status_code, 403)
        self.registry.permits.return_value = False
        self.assertEqual(self.client.get("/api/community/reports?istat_code=093033",
            headers=self.headers).status_code, 401)
        self.registry.permits.side_effect = OSError("private storage failure")
        response = self.client.get("/api/community/reports?istat_code=093033", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private storage failure", response.text)

    def test_identity_cannot_be_impersonated(self):
        response = self.client.post("/api/community/reputation", json={"client_id": "another-owner"}, headers=self.headers)
        self.assertEqual(response.status_code, 403)
        self.service.get_reputation.assert_not_called()
        response = self.client.post("/api/community/reputation", json={"client_id": self.client_id}, headers=self.headers)
        self.assertEqual(response.status_code, 200)

    def test_malformed_unicode_identity_is_rejected_without_service_work(self):
        response = self.client.post("/api/community/reputation", content='{"client_id":"\\ud800"}', headers=self.headers)
        self.assertEqual(response.status_code, 403)
        self.service.get_reputation.assert_not_called()

    def test_state_store_failure_during_mutation_is_not_acknowledged(self):
        self.service.get_reputation.side_effect = CommunityRepositoryUnavailable("private-state-object")
        response = self.client.post("/api/community/reputation", json={"client_id": self.client_id}, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-state-object", response.text)

    def test_precise_coordinates_use_body_not_url(self):
        self.assertEqual(self.client.get("/api/community/reports?lat=45&lon=12", headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post("/api/community/reports/query", json={"lat": 45, "lon": 12}, headers=self.headers).status_code, 200)
        self.service.get_scoped_reports.assert_called_once_with(lat=45, lon=12, radius_km=30)

    def test_invalid_json_and_validation_never_echo_coordinates(self):
        for body in ("not-json", "[]", '{"lat":91,"lon":12}'):
            response = self.client.post("/api/community/reports/query", content=body, headers=self.headers)
            self.assertEqual(response.status_code, 422)
            self.assertNotIn('"lat"', response.text)
        response = self.client.post("/api/community/reports/query", content="X" * 8193, headers=self.headers)
        self.assertEqual(response.status_code, 413)

    def test_storage_failure_does_not_report_success(self):
        self.service.get_scoped_reports.side_effect = CommunityRepositoryUnavailable("private")
        with self.assertLogs("app.pilot_community_cloud", level="ERROR") as logs:
            response = self.client.get("/api/community/reports?istat_code=093033", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "community_storage_unavailable")
        self.assertNotIn("private", " ".join(logs.output))
        self.assertIn("CommunityRepositoryUnavailable", " ".join(logs.output))

    def test_preflight_is_narrow_and_requires_no_token(self):
        response = self.client.options("/api/community/reports", headers={
            "Origin": "https://localhost", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,x-meteo-pilot-installation,content-type",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://localhost")

    def test_ingress_limits_reset_on_rolling_boundary(self):
        clock = [0]
        budget = IngressBudget(clock=lambda: clock[0])
        self.assertTrue(budget.accept("token", 1))
        self.assertFalse(budget.accept("token", 1))
        clock[0] = 60
        self.assertTrue(budget.accept("token", 1))

    def test_registry_project_expiry_and_revocation(self):
        client = Mock(project=PILOT_PROJECT)
        snapshot = client.collection.return_value.document.return_value.get.return_value
        snapshot.exists = True
        record = {"project": PILOT_PROJECT, "active": True, "client_id_sha256": self.digest,
                  "expires_at": datetime.now(timezone.utc) + timedelta(days=30)}
        snapshot.to_dict.return_value = record
        registry = EnrolledInstallations(client)
        self.assertTrue(registry.permits("a" * 64, self.digest))
        client.collection.return_value.document.return_value.get.assert_called_once_with(timeout=10, retry=None)
        for key, value in (("active", False), ("project", "meteo-friul"),
                           ("expires_at", datetime.now(timezone.utc) - timedelta(seconds=1)),
                           ("client_id_sha256", "b" * 64)):
            snapshot.to_dict.return_value = {**record, key: value}
            self.assertFalse(registry.permits("a" * 64, self.digest))
        with self.assertRaises(ValueError):
            EnrolledInstallations(Mock(project="meteo-friul"))
