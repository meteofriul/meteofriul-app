import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.markets import get_markets_service
from app.main import create_app
from app.markets.repository import SQLiteMarketRepository
from app.markets.service import MarketsService
from tests.test_markets_archive import small_seed


class MarketsApiTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="mf-markets-api-")
        self.addCleanup(temporary.cleanup)
        self.service = MarketsService(SQLiteMarketRepository(Path(temporary.name) / "archive.sqlite3", seed=small_seed()))
        app = create_app()
        app.dependency_overrides[get_markets_service] = lambda: self.service
        self.client = TestClient(app)
        self.auth = {"Authorization": "Bearer markets-test-token"}
        self.environment = {"K_SERVICE": "", "MARKETS_ADMIN_AUTH_MODE": "local", "MARKETS_ADMIN_LOCAL_TOKEN": "markets-test-token"}
        environment = patch.dict(os.environ, self.environment)
        environment.start()
        self.addCleanup(environment.stop)

    def test_all_admin_routes_require_dedicated_authorization(self):
        for url in ("/api/admin/markets/state", "/api/admin/markets/history"):
            self.assertEqual(self.client.get(url).status_code, 401)
            self.assertEqual(self.client.get(url, headers={"Authorization": "Bearer wrong"}).status_code, 403)
            accepted = self.client.get(url, headers=self.auth)
            self.assertEqual(accepted.status_code, 200)
            self.assertEqual(accepted.headers["cache-control"], "no-store")

    def test_firebase_claim_is_independent_and_checks_revocation(self):
        app = object()
        with patch.dict(os.environ, {"MARKETS_ADMIN_AUTH_MODE": "firebase"}), patch(
            "app.infrastructure.markets_admin_auth.get_firebase_app", return_value=app,
        ), patch("firebase_admin.auth.verify_id_token", side_effect=[
            {"uid": "sponsor", "adsAdmin": True}, {"uid": "webcam", "webcamAdmin": True},
            {"uid": "owner", "marketsAdmin": "true"}, {"uid": "owner", "marketsAdmin": True},
            ValueError("revoked"),
        ]) as verify:
            statuses = [self.client.get("/api/admin/markets/state", headers=self.auth).status_code for _ in range(5)]
        self.assertEqual(statuses, [403, 403, 403, 200, 401])
        verify.assert_called_with("markets-test-token", app=app, check_revoked=True)

    def test_local_auth_cannot_run_in_cloud(self):
        with patch.dict(os.environ, {"K_SERVICE": "cloud-service"}):
            rejected = self.client.get("/api/admin/markets/state", headers=self.auth)
        self.assertEqual(rejected.status_code, 503)
        self.assertEqual(rejected.json()["detail"]["code"], "markets_admin_local_auth_forbidden")

    def test_save_publish_etag_and_revision_conflict(self):
        initial = self.client.get("/api/markets/catalogue")
        state = self.client.get("/api/admin/markets/state", headers=self.auth).json()
        state["dates"][0]["date"] = "2026-11-08"
        command = {"expectedRevision": 0, "operationId": "api-save-operation", "reason": "Data corretta dalla fonte", "state": state}
        saved = self.client.put("/api/admin/markets/state", headers=self.auth, json=command)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["publishedRevision"], 0)
        self.assertEqual(self.client.get("/api/markets/catalogue").json(), initial.json())
        replay = self.client.put("/api/admin/markets/state", headers=self.auth, json=command)
        self.assertTrue(replay.json()["idempotentReplay"])
        command["operationId"] = "another-operation"
        conflict = self.client.put("/api/admin/markets/state", headers=self.auth, json=command)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["detail"]["currentRevision"], 1)
        published = self.client.post("/api/admin/markets/publish", headers=self.auth,
                                     json={"expectedRevision": 1, "operationId": "api-publish-operation", "reason": "Revisione completata"})
        self.assertEqual(published.status_code, 200)
        public = self.client.get("/api/markets/catalogue")
        self.assertEqual(public.json()["revision"], 2)
        self.assertEqual(public.json()["dates"][0]["id"], "edition-one")
        self.assertNotEqual(initial.headers["etag"], public.headers["etag"])
        unchanged = self.client.get("/api/markets/catalogue", headers={"If-None-Match": public.headers["etag"]})
        self.assertEqual(unchanged.status_code, 304)
        self.assertEqual(unchanged.content, b"")

    def test_untyped_revision_and_unknown_top_level_keys_are_rejected(self):
        for extra in ({"expectedRevision": True}, {"expectedRevision": "0"}, {"unknown": True}):
            payload = {"expectedRevision": 0, "operationId": "strict-operation", "reason": "Test validazione", **extra}
            self.assertEqual(self.client.post("/api/admin/markets/publish", headers=self.auth, json=payload).status_code, 422)

    def test_public_projection_excludes_notes_and_admin_identity(self):
        self.assertNotIn("INTERNAL-NOTE", self.client.get("/api/markets/catalogue").text)
        self.assertNotIn("test-owner", self.client.get("/api/markets/catalogue").text)
        self.assertNotIn("drafts", self.client.get("/api/markets/catalogue").json())

    def test_panel_cors_accepts_authorized_mutation_headers(self):
        response = self.client.options("/api/admin/markets/state", headers={
            "Origin": "https://meteofriul-inserzioni.web.app", "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,content-type",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "https://meteofriul-inserzioni.web.app")


if __name__ == "__main__":
    unittest.main()
