import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.markets import get_markets_service, get_weekly_audit_store
from app.markets.repository import SQLiteMarketRepository
from app.markets.service import MarketsService
from app.markets_cloud import create_app
from app.infrastructure.markets_admin_auth import MarketsAdminContext, require_markets_admin
from tests.test_markets_archive import small_seed


class MarketsCloudTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {
            "K_SERVICE": "markets-test", "MARKETS_STORAGE": "firestore",
            "FIREBASE_PROJECT_ID": "market-test-project", "MARKETS_FIREBASE_PROJECT_ID": "market-test-project",
            "MARKETS_ADMIN_AUTH_MODE": "firebase", "MARKETS_ADMIN_LOCAL_TOKEN": "",
            "MARKETS_PUBLIC_CATALOGUE_ENABLED": "false",
        })
        env.start()
        self.addCleanup(env.stop)

    def test_startup_rejects_local_auth_ephemeral_storage_and_wrong_project(self):
        for overrides in (
            {"MARKETS_STORAGE": "sqlite"}, {"MARKETS_STORAGE": ""},
            {"MARKETS_ADMIN_AUTH_MODE": "local"}, {"MARKETS_ADMIN_LOCAL_TOKEN": "test-only"},
            {"MARKETS_FIREBASE_PROJECT_ID": ""}, {"FIREBASE_PROJECT_ID": "another-project"},
            {"MARKETS_PUBLIC_CATALOGUE_ENABLED": "yes"},
        ):
            with self.subTest(overrides=overrides), patch.dict(os.environ, overrides):
                with self.assertRaisesRegex(ValueError, "markets_cloud_configuration_invalid"):
                    create_app()

    def test_only_market_routes_and_liveness_are_mounted(self):
        with patch("app.markets.repository.configured_repository", side_effect=AssertionError("No provisioning")):
            app = create_app()
            client = TestClient(app)
            self.assertEqual(client.get("/healthz").json()["service"], "markets")
        self.assertEqual({route.path for route in app.routes}, {
            "/healthz", "/api/admin/markets/state",
            "/api/admin/markets/history", "/api/admin/markets/publish",
            "/api/admin/markets/weekly-audit", "/api/admin/markets/weekly-audit/{market_id}",
            "/api/admin/markets/weekly-audit/reviews",
            "/api/admin/markets/weekly-audit/{market_id}/review",
            "/api/admin/markets/review-complete",
            "/api/admin/markets/email-settings",
        })
        for path in ("/api/push/status", "/api/admin/promotions/state", "/api/community/reports", "/api/docs"):
            self.assertEqual(client.get(path).status_code, 404)

    def test_admin_auth_precedes_repository_reads(self):
        app = create_app()
        def forbidden_read():
            raise AssertionError("Unauthenticated request must not read private state")
        app.dependency_overrides[get_markets_service] = forbidden_read
        client = TestClient(app)
        for method,path,body in (
            ("GET", "/api/admin/markets/state", None),
            ("GET", "/api/admin/markets/history", None),
            ("GET", "/api/admin/markets/weekly-audit", None),
            ("GET", "/api/admin/markets/weekly-audit/reviews", None),
            ("GET", "/api/admin/markets/weekly-audit/M001", None),
            ("PUT", "/api/admin/markets/weekly-audit/M001/review", {}),
            ("PUT", "/api/admin/markets/state", {}),
            ("POST", "/api/admin/markets/publish", {}),
            ("POST", "/api/admin/markets/review-complete", {}),
            ("PUT", "/api/admin/markets/email-settings", {}),
        ):
            self.assertEqual(client.request(method,path,json=body).status_code, 401)

    def test_panel_cors_and_public_snapshot_do_not_expose_drafts(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"MARKETS_PUBLIC_CATALOGUE_ENABLED": "true"}):
            service = MarketsService(SQLiteMarketRepository(Path(directory)/"archive.sqlite3",seed=small_seed()))
            app = create_app()
            app.dependency_overrides[get_markets_service] = lambda: service
            client = TestClient(app)
            for origin in ("https://meteofriul-inserzioni.web.app", "https://meteofriul.app", "https://localhost"):
                response = client.options("/api/admin/markets/state",headers={
                    "Origin":origin, "Access-Control-Request-Method":"PUT",
                    "Access-Control-Request-Headers":"authorization,content-type",
                })
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers["access-control-allow-origin"],origin)
            denied = client.options("/api/admin/markets/state",headers={
                "Origin":"https://untrusted.invalid", "Access-Control-Request-Method":"PUT",
            })
            self.assertEqual(denied.status_code,400)
            self.assertNotIn("access-control-allow-origin",denied.headers)
            public = client.get("/api/markets/catalogue")
            self.assertEqual(public.status_code,200)
            self.assertNotIn("drafts",public.json())
            self.assertNotIn("audit",public.json())
            self.assertEqual(client.get("/api/markets/catalogue",headers={"If-None-Match":public.headers["etag"]}).status_code,304)

    def test_weekly_report_requires_admin_and_is_never_public(self):
        app = create_app()
        class ReportStore:
            def latest(self):
                return {"status": "completed", "markets": [{"marketId": "M001", "changes": 1}]}
            def market(self, market_id):
                return {"marketId": market_id, "changesDetail": [{"before": "Piazza", "after": "Piazza nuova"}]} if market_id == "M001" else None
            def reviews(self):
                return [{"marketId": "M001", "outcome": "verified"}]
            def save_review(self, **values):
                return values
        app.dependency_overrides[get_weekly_audit_store] = ReportStore
        client = TestClient(app)
        self.assertEqual(client.get("/api/admin/markets/weekly-audit").status_code, 401)
        app.dependency_overrides[require_markets_admin] = lambda: MarketsAdminContext("test-operator", {"marketsAdmin": True})
        response = client.get("/api/admin/markets/weekly-audit")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["markets"][0]["changes"], 1)
        self.assertEqual(client.get("/api/admin/markets/weekly-audit/M001").json()["changesDetail"][0]["after"], "Piazza nuova")
        self.assertEqual(client.get("/api/admin/markets/weekly-audit/reviews").json()[0]["outcome"], "verified")
        review = client.put("/api/admin/markets/weekly-audit/M001/review", json={
            "sourceUrl": "https://example.test/mercato", "outcome": "verified",
            "note": "Fonte letta e verificata.", "reportRunId": "a" * 32,
            "operationId": "test-op-001",
        })
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.headers["cache-control"], "no-store")
        self.assertEqual(review.json()["market_id"], "M001")
        self.assertEqual(client.get("/api/admin/markets/weekly-audit/M002").status_code, 404)
        self.assertEqual(client.get("/api/markets/weekly-audit").status_code, 404)

    def test_panel_only_mode_blocks_catalogue_and_publication_before_repository_access(self):
        os.environ.pop("MARKETS_PUBLIC_CATALOGUE_ENABLED", None)
        app = create_app()
        def forbidden_read():
            raise AssertionError("Disabled public access must not read or change the archive")
        app.dependency_overrides[get_markets_service] = forbidden_read
        client = TestClient(app)
        self.assertFalse(client.get("/healthz").json()["publicCatalogueEnabled"])
        self.assertEqual(client.get("/api/markets/catalogue").status_code, 404)
        self.assertEqual(client.post("/api/admin/markets/publish", json={}).status_code, 401)
        app.dependency_overrides[require_markets_admin] = lambda: MarketsAdminContext("test-operator", {"marketsAdmin": True})
        blocked = client.post("/api/admin/markets/publish", json={})
        self.assertEqual(blocked.status_code, 423)
        self.assertEqual(blocked.json()["detail"]["code"], "markets_publication_disabled")
        for origin, expected in (("https://meteofriul-inserzioni.web.app", 200), ("https://meteofriul.app", 400), ("https://localhost", 400)):
            response = client.options("/api/admin/markets/state", headers={"Origin": origin, "Access-Control-Request-Method": "PUT"})
            self.assertEqual(response.status_code, expected)
        with TemporaryDirectory() as directory:
            service = MarketsService(SQLiteMarketRepository(Path(directory)/"archive.sqlite3", seed=small_seed()))
            app.dependency_overrides[get_markets_service] = lambda: service
            response = client.get("/api/admin/markets/state")
            self.assertEqual(response.status_code, 200)
            self.assertIn("drafts", response.json())


if __name__ == "__main__":
    unittest.main()
