import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.infrastructure.events_admin_auth import require_events_admin
from app.api.events_admin import _client
from app.main import create_app


class EventsAdminSourceTests(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.dependency_overrides[require_events_admin] = lambda: {"uid": "owner", "email": "owner@example.test"}
        self.client = TestClient(app)
        self.controls = {"schema": "event-source-controls-v1", "revision": 4,
                         "sources": {"Barcolana": {"enabled": False,
                                                    "reason": "Sito cambiato"}}}

    def test_state_does_not_call_paused_source_verified(self):
        catalog = {"schema": "pilot-events-v1", "attempted_at": "2026-11-15T10:00:00Z",
                   "sources": {"Barcolana": {"status": "fresh",
                                             "updated_at": datetime.now(timezone.utc).isoformat()}}}
        with patch("app.api.events_admin._blob"), \
             patch("app.api.events_admin.read_controls", return_value=(self.controls, 1)), \
             patch("app.api.events_admin._catalog", return_value=catalog), \
             patch("app.api.events_admin._allowed", return_value={"Barcolana": object()}):
            response = self.client.get("/api/admin/events/sources")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["sources"][0]["status"], "paused")

    def test_update_requires_revision_and_reason(self):
        with patch("app.api.events_admin._blob"), \
             patch("app.api.events_admin._allowed", return_value={"Barcolana": object()}), \
             patch("app.api.events_admin.save_control", return_value={"revision": 5}) as save:
            response = self.client.put("/api/admin/events/sources/Barcolana", json={
                "expectedRevision": 4, "enabled": False, "pausedUntil": None,
                "reason": "Pagina non leggibile"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(save.call_args.kwargs["expected_revision"], 4)
        self.assertEqual(save.call_args.kwargs["actor"], "owner")

    def test_verify_reserves_once_and_runs_only_named_source(self):
        with patch("app.api.events_admin._blob"), \
             patch("app.api.events_admin._allowed", return_value={"Barcolana": object()}), \
             patch("app.api.events_admin.reserve_verification") as reserve, \
             patch("app.api.events_admin._start_single_source", return_value="operation") as start:
            response = self.client.post("/api/admin/events/sources/Barcolana/verify")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(reserve.call_args.kwargs["name"], "Barcolana")
        start.assert_called_once_with("Barcolana")
        self.assertEqual(response.json()["operation"], "operation")

    def test_unknown_source_never_starts_job(self):
        with patch("app.api.events_admin._allowed", return_value={"Barcolana": object()}), \
             patch("app.api.events_admin._start_single_source") as start:
            response = self.client.post("/api/admin/events/sources/unknown/verify")
        self.assertEqual(response.status_code, 404)
        start.assert_not_called()


class EventsAdminAuthTests(unittest.TestCase):
    def test_storage_client_rejects_wrong_runtime_project(self):
        _client.cache_clear()
        with patch("google.auth.default", return_value=(object(), "another-project")):
            with self.assertRaises(HTTPException) as error:
                _client()
        self.assertEqual(error.exception.status_code, 503)

    def test_requires_verified_owner_account(self):
        with self.assertRaises(HTTPException) as missing:
            require_events_admin(None)
        self.assertEqual(missing.exception.status_code, 401)
        with patch("app.infrastructure.events_admin_auth.get_firebase_app"), \
             patch("firebase_admin.auth.verify_id_token", return_value={
                 "uid": "someone", "email": "other@example.test", "email_verified": True}):
            with self.assertRaises(HTTPException) as forbidden:
                require_events_admin("Bearer valid-token")
        self.assertEqual(forbidden.exception.status_code, 403)
        with patch("app.infrastructure.events_admin_auth.get_firebase_app"), \
             patch("firebase_admin.auth.verify_id_token", return_value={
                 "uid": "owner", "email": "meteofriul@gmail.com", "email_verified": True}):
            self.assertEqual(require_events_admin("Bearer valid-token")["uid"], "owner")
