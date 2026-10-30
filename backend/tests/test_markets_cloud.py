import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.markets import get_markets_service
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
            ("PUT", "/api/admin/markets/state", {}),
            ("POST", "/api/admin/markets/publish", {}),
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
