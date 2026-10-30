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
from tests.test_markets_archive import small_seed


class MarketsCloudTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {
            "K_SERVICE": "markets-test", "MARKETS_STORAGE": "firestore",
            "FIREBASE_PROJECT_ID": "market-test-project", "MARKETS_FIREBASE_PROJECT_ID": "market-test-project",
            "MARKETS_ADMIN_AUTH_MODE": "firebase", "MARKETS_ADMIN_LOCAL_TOKEN": "",
        })
        env.start()
        self.addCleanup(env.stop)

    def test_startup_rejects_local_auth_ephemeral_storage_and_wrong_project(self):
        for overrides in (
            {"MARKETS_STORAGE": "sqlite"}, {"MARKETS_STORAGE": ""},
            {"MARKETS_ADMIN_AUTH_MODE": "local"}, {"MARKETS_ADMIN_LOCAL_TOKEN": "test-only"},
            {"MARKETS_FIREBASE_PROJECT_ID": ""}, {"FIREBASE_PROJECT_ID": "another-project"},
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
            "/healthz", "/api/markets/catalogue", "/api/admin/markets/state",
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
        with TemporaryDirectory() as directory:
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


if __name__ == "__main__":
    unittest.main()
