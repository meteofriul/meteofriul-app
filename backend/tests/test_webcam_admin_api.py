import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.live import get_webcam_manifest_service
from app.main import create_app
from app.services.webcam_controls import (
    WebcamControlRepository,
    WebcamControlService,
    get_webcam_control_service,
)
from tests.test_webcam_controls import manifest


class StubManifestService:
    def __init__(self):
        self.value = manifest()

    def get_manifest(self):
        return self.value


class WebcamAdminApiTests(unittest.TestCase):
    def setUp(self):
        self.manifest_service = StubManifestService()
        self.control_service = WebcamControlService(
            WebcamControlRepository(lambda: None),
            cache_seconds=60,
        )
        app = create_app()
        app.dependency_overrides[get_webcam_manifest_service] = lambda: self.manifest_service
        app.dependency_overrides[get_webcam_control_service] = lambda: self.control_service
        self.client = TestClient(app)
        self.auth = {
            "Authorization": "Bearer webcam-test-token",
        }
        self.environment = {
            "WEBCAM_ADMIN_AUTH_MODE": "local",
            "WEBCAM_ADMIN_LOCAL_TOKEN": "webcam-test-token",
            "K_SERVICE": "",
        }

    def test_admin_state_requires_dedicated_webcam_token(self):
        missing = self.client.get("/api/admin/webcams/state")
        with patch.dict(os.environ, self.environment):
            forbidden = self.client.get(
                "/api/admin/webcams/state",
                headers={"Authorization": "Bearer wrong"},
            )
            accepted = self.client.get(
                "/api/admin/webcams/state",
                headers=self.auth,
            )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.headers["cache-control"], "no-store")
        self.assertEqual(accepted.json()["revision"], 0)
        self.assertTrue(accepted.json()["webcams"][0]["previewEnabled"])

    def test_firebase_auth_does_not_reuse_ads_admin_privilege(self):
        firebase_environment = {
            "WEBCAM_ADMIN_AUTH_MODE": "firebase",
            "K_SERVICE": "",
        }
        firebase_app = object()
        with patch.dict(os.environ, firebase_environment), patch(
            "app.infrastructure.webcam_admin_auth.get_firebase_app",
            return_value=firebase_app,
        ), patch(
            "firebase_admin.auth.verify_id_token",
            side_effect=[
                {"uid": "ads-only", "email": "ads@example.test", "adsAdmin": True},
                {
                    "uid": "webcam-owner",
                    "email": "owner@example.test",
                    "webcamAdmin": True,
                },
            ],
        ) as verify_token:
            ads_only = self.client.get(
                "/api/admin/webcams/state",
                headers={"Authorization": "Bearer ads-token"},
            )
            webcam_admin = self.client.get(
                "/api/admin/webcams/state",
                headers={"Authorization": "Bearer webcam-token"},
            )

        self.assertEqual(ads_only.status_code, 403)
        self.assertEqual(ads_only.json()["detail"]["code"], "webcam_admin_claim_required")
        self.assertEqual(webcam_admin.status_code, 200)
        self.assertEqual(verify_token.call_count, 2)
        verify_token.assert_any_call("ads-token", app=firebase_app, check_revoked=True)
        verify_token.assert_any_call("webcam-token", app=firebase_app, check_revoked=True)

    def test_admin_can_disable_preview_without_changing_public_schema(self):
        with patch.dict(os.environ, self.environment):
            updated = self.client.put(
                "/api/admin/webcams/state",
                headers=self.auth,
                json={
                    "expectedRevision": 0,
                    "changes": [{
                        "webcamId": "udine-panorama-castello",
                        "previewEnabled": False,
                        "reason": "Verifica in corso",
                    }],
                },
            )
            public = self.client.get("/api/live/webcams")

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.headers["cache-control"], "no-store")
        self.assertEqual(updated.json()["revision"], 1)
        self.assertFalse(updated.json()["webcams"][0]["previewEnabled"])
        self.assertEqual(public.status_code, 200)
        udine = next(
            record for record in public.json()["webcams"]
            if record["id"] == "udine-panorama-castello"
        )
        self.assertNotIn("imageUrl", udine)
        self.assertNotIn("mediaType", udine)
        self.assertNotIn("playerUrl", udine)
        self.assertEqual(
            udine["fallbackImageUrl"],
            "/municipalities/photos/030129-photo.webp",
        )
        self.assertEqual(udine["sourcePage"], "https://udine.example.test/")
        self.assertNotIn("previewEnabled", udine)
        self.assertNotIn("reason", udine)

    def test_revision_conflict_and_unknown_camera_are_explicit(self):
        with patch.dict(os.environ, self.environment):
            first = self.client.put(
                "/api/admin/webcams/state",
                headers=self.auth,
                json={
                    "expectedRevision": 0,
                    "changes": [{
                        "webcamId": "udine-panorama-castello",
                        "previewEnabled": False,
                    }],
                },
            )
            conflict = self.client.put(
                "/api/admin/webcams/state",
                headers=self.auth,
                json={
                    "expectedRevision": 0,
                    "changes": [{
                        "webcamId": "forni-varmost",
                        "previewEnabled": False,
                    }],
                },
            )
            unknown = self.client.put(
                "/api/admin/webcams/state",
                headers=self.auth,
                json={
                    "expectedRevision": 1,
                    "changes": [{
                        "webcamId": "missing-camera",
                        "previewEnabled": False,
                    }],
                },
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(
            conflict.json()["detail"]["code"],
            "webcam_control_revision_conflict",
        )
        self.assertEqual(unknown.status_code, 422)
        self.assertEqual(
            unknown.json()["detail"]["code"],
            "webcam_control_unknown_id",
        )

    def test_write_requires_revision_and_a_strict_boolean(self):
        with patch.dict(os.environ, self.environment):
            missing_revision = self.client.put(
                "/api/admin/webcams/state",
                headers=self.auth,
                json={
                    "changes": [{
                        "webcamId": "udine-panorama-castello",
                        "previewEnabled": False,
                    }],
                },
            )
            string_boolean = self.client.put(
                "/api/admin/webcams/state",
                headers=self.auth,
                json={
                    "expectedRevision": 0,
                    "changes": [{
                        "webcamId": "udine-panorama-castello",
                        "previewEnabled": "false",
                    }],
                },
            )

        self.assertEqual(missing_revision.status_code, 422)
        self.assertEqual(string_boolean.status_code, 422)


if __name__ == "__main__":
    unittest.main()
