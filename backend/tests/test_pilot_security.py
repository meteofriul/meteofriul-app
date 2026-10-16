import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.live import get_community_service
from app.infrastructure.app_check import (
    APP_CHECK_HEADER,
    AppCheckTokenInvalid,
    AppCheckVerifierUnavailable,
    get_app_check_verifier,
)
from app.main import (
    ADS_PANEL_ORIGIN,
    CAPACITOR_ORIGIN,
    CORS_ADDITIONAL_ORIGINS_ENV,
    WEB_APP_ORIGIN,
    create_app,
)
from app.services.community import COMMUNITY_GUIDELINES_POLICY_VERSION
from tests.test_live_api import FixtureCommunityService


CREATE_PAYLOAD = {
    "accepted_terms": True,
    "type_id": "rain",
    "lat": 45.95689,
    "lon": 12.66051,
    "selected_place": "Pordenone",
    "client_id": "client-1",
    "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
}
DELETE_PAYLOAD = {"client_id": "client-1"}
CONFIRM_PAYLOAD = {
    "accepted_terms": True,
    "client_id": "client-1",
    "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
    "vote": "yes",
}
FLAG_PAYLOAD = {"client_id": "client-flagger", "reason": "inaccurate"}
REPUTATION_PAYLOAD = {"client_id": "client-1"}
PILOT_FIREBASE_APP_ID = "1:1234567890:android:abcdef0123456789"
LOCAL_OFF_ENV = {
    "COMMUNITY_APP_CHECK_MODE": "off",
    "COMMUNITY_APP_CHECK_ALLOWED_APP_IDS": "",
    "COMMUNITY_STORAGE": "memory",
    "K_SERVICE": "",
}
ENFORCE_ENV = {
    "COMMUNITY_APP_CHECK_MODE": "enforce",
    "COMMUNITY_APP_CHECK_ALLOWED_APP_IDS": PILOT_FIREBASE_APP_ID,
    "COMMUNITY_STORAGE": "memory",
    "K_SERVICE": "",
}


class PilotSecurityTests(unittest.TestCase):
    def create_client(self, verifier=None):
        app = create_app()
        app.dependency_overrides[get_community_service] = FixtureCommunityService
        if verifier is not None:
            app.dependency_overrides[get_app_check_verifier] = lambda: verifier
        return TestClient(app)

    def test_simple_cors_response_uses_exact_capacitor_origin(self):
        response = self.create_client().get(
            "/api/healthz",
            headers={"Origin": CAPACITOR_ORIGIN},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            CAPACITOR_ORIGIN,
        )

    def test_simple_cors_response_rejects_insecure_capacitor_origin(self):
        response = self.create_client().get(
            "/api/healthz",
            headers={"Origin": "http://localhost"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_simple_cors_response_allows_the_public_web_app_origin(self):
        response = self.create_client().get(
            "/api/healthz",
            headers={"Origin": WEB_APP_ORIGIN},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            WEB_APP_ORIGIN,
        )

    def test_admin_panel_origin_can_send_authenticated_updates(self):
        response = self.create_client().options(
            "/api/admin/promotions/state",
            headers={
                "Origin": ADS_PANEL_ORIGIN,
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            ADS_PANEL_ORIGIN,
        )
        self.assertIn(
            "authorization",
            response.headers["access-control-allow-headers"].lower(),
        )

    def test_exact_preview_origin_can_be_added_without_wildcards(self):
        preview_origin = "https://meteofriul-app.pages.dev"
        with patch.dict(
            os.environ,
            {CORS_ADDITIONAL_ORIGINS_ENV: preview_origin},
        ):
            response = self.create_client().options(
                "/api/community/reports",
                headers={
                    "Origin": preview_origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": (
                        "content-type,x-firebase-appcheck"
                    ),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            preview_origin,
        )

    def test_invalid_additional_cors_origin_fails_closed(self):
        with patch.dict(
            os.environ,
            {CORS_ADDITIONAL_ORIGINS_ENV: "https://*.pages.dev"},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "cors_origin_must_be_absolute_https_origin",
            ):
                create_app()

    def test_capacitor_preflight_allows_only_required_origin_and_headers(self):
        response = self.create_client().options(
            "/api/community/reports",
            headers={
                "Origin": CAPACITOR_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": (
                    "content-type,x-firebase-appcheck"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            CAPACITOR_ORIGIN,
        )
        self.assertIn(
            "x-firebase-appcheck",
            response.headers["access-control-allow-headers"].lower(),
        )

    def test_preflight_rejects_unlisted_origin(self):
        response = self.create_client().options(
            "/api/community/reports",
            headers={
                "Origin": "https://example.invalid",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_local_mode_leaves_mutations_available_without_token(self):
        calls = []

        def verifier(token):
            calls.append(token)
            raise AssertionError("Verifier must stay idle while App Check is off")

        with patch.dict(os.environ, LOCAL_OFF_ENV):
            response = self.create_client(verifier).post(
                "/api/community/reports",
                json=CREATE_PAYLOAD,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [])

    def test_public_community_read_never_requires_app_check(self):
        def verifier(token):
            raise AssertionError("Public reads must not invoke App Check")

        with patch.dict(os.environ, ENFORCE_ENV):
            response = self.create_client(verifier).get("/api/community/reports")

        self.assertEqual(response.status_code, 200)

    def test_enforcement_rejects_all_mutations_without_token(self):
        requests = (
            ("POST", "/api/community/reputation", REPUTATION_PAYLOAD),
            ("POST", "/api/community/reports", CREATE_PAYLOAD),
            (
                "DELETE",
                "/api/community/reports/community-test-1",
                DELETE_PAYLOAD,
            ),
            (
                "POST",
                "/api/community/reports/group-rain:pordenone:496186/confirmation",
                CONFIRM_PAYLOAD,
            ),
            (
                "POST",
                "/api/community/reports/group-rain:pordenone:496186/flags",
                FLAG_PAYLOAD,
            ),
        )

        with patch.dict(os.environ, ENFORCE_ENV):
            client = self.create_client()
            for method, url, payload in requests:
                with self.subTest(method=method, url=url):
                    response = client.request(method, url, json=payload)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(
                        response.json()["detail"]["code"],
                        "app_check_required",
                    )

    def test_valid_token_unlocks_all_mutations(self):
        verified_tokens = []

        def verifier(token):
            verified_tokens.append(token)
            return {"app_id": PILOT_FIREBASE_APP_ID}

        requests = (
            ("POST", "/api/community/reputation", REPUTATION_PAYLOAD),
            ("POST", "/api/community/reports", CREATE_PAYLOAD),
            (
                "DELETE",
                "/api/community/reports/community-test-1",
                DELETE_PAYLOAD,
            ),
            (
                "POST",
                "/api/community/reports/group-rain:pordenone:496186/confirmation",
                CONFIRM_PAYLOAD,
            ),
            (
                "POST",
                "/api/community/reports/group-rain:pordenone:496186/flags",
                FLAG_PAYLOAD,
            ),
        )

        with patch.dict(os.environ, ENFORCE_ENV):
            client = self.create_client(verifier)
            for method, url, payload in requests:
                with self.subTest(method=method, url=url):
                    response = client.request(
                        method,
                        url,
                        json=payload,
                        headers={APP_CHECK_HEADER: "valid-pilot-token"},
                    )
                    self.assertEqual(response.status_code, 200)

        self.assertEqual(verified_tokens, ["valid-pilot-token"] * 5)

    def test_invalid_token_is_rejected(self):
        def verifier(token):
            raise AppCheckTokenInvalid

        with patch.dict(os.environ, ENFORCE_ENV):
            response = self.create_client(verifier).post(
                "/api/community/reports",
                json=CREATE_PAYLOAD,
                headers={APP_CHECK_HEADER: "invalid-pilot-token"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "app_check_invalid")

    def test_verifier_failure_is_fail_closed(self):
        def verifier(token):
            raise AppCheckVerifierUnavailable

        with patch.dict(os.environ, ENFORCE_ENV):
            response = self.create_client(verifier).post(
                "/api/community/reports",
                json=CREATE_PAYLOAD,
                headers={APP_CHECK_HEADER: "unverifiable-pilot-token"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "app_check_unavailable",
        )

    def test_unknown_mode_is_fail_closed(self):
        with patch.dict(
            os.environ,
            {
                **ENFORCE_ENV,
                "COMMUNITY_APP_CHECK_MODE": "typo",
            },
        ):
            response = self.create_client().post(
                "/api/community/reports",
                json=CREATE_PAYLOAD,
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "app_check_configuration_invalid",
        )

    def test_cloud_run_rejects_ephemeral_memory_storage(self):
        environment = {
            **ENFORCE_ENV,
            "K_SERVICE": "meteofriul-api",
        }
        with patch.dict(os.environ, environment):
            os.environ.pop("COMMUNITY_APP_CHECK_MODE", None)
            response = self.create_client().post(
                "/api/community/reports",
                json=CREATE_PAYLOAD,
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "app_check_configuration_invalid",
        )

    def test_cloud_run_rejects_unknown_community_storage_mode(self):
        environment = {
            **ENFORCE_ENV,
            "K_SERVICE": "meteofriul-api",
            "COMMUNITY_STORAGE": "firestor",
        }
        with patch.dict(os.environ, environment):
            response = self.create_client().post(
                "/api/community/reports",
                json=CREATE_PAYLOAD,
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "app_check_configuration_invalid",
        )

    def test_missing_mode_defaults_to_enforce_with_firestore(self):
        for storage_mode in ("firestore", "auto"):
            with self.subTest(storage_mode=storage_mode):
                environment = {
                    **ENFORCE_ENV,
                    "COMMUNITY_STORAGE": storage_mode,
                }
                with patch.dict(os.environ, environment):
                    os.environ.pop("COMMUNITY_APP_CHECK_MODE", None)
                    response = self.create_client().post(
                        "/api/community/reports",
                        json=CREATE_PAYLOAD,
                    )

                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.json()["detail"]["code"],
                    "app_check_required",
                )

    def test_explicit_off_is_rejected_outside_local_environment(self):
        environments = (
            {**LOCAL_OFF_ENV, "K_SERVICE": "meteofriul-api"},
            {**LOCAL_OFF_ENV, "COMMUNITY_STORAGE": "firestore"},
            {**LOCAL_OFF_ENV, "COMMUNITY_STORAGE": "auto"},
        )
        for environment in environments:
            with self.subTest(environment=environment):
                with patch.dict(os.environ, environment):
                    response = self.create_client().post(
                        "/api/community/reports",
                        json=CREATE_PAYLOAD,
                    )

                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.json()["detail"]["code"],
                    "app_check_configuration_invalid",
                )

    def test_missing_mode_defaults_to_off_only_locally(self):
        with patch.dict(os.environ, LOCAL_OFF_ENV):
            os.environ.pop("COMMUNITY_APP_CHECK_MODE", None)
            response = self.create_client().post(
                "/api/community/reports",
                json=CREATE_PAYLOAD,
            )

        self.assertEqual(response.status_code, 200)

    def test_enforcement_requires_an_app_id_allowlist(self):
        environment = {
            **ENFORCE_ENV,
            "COMMUNITY_APP_CHECK_ALLOWED_APP_IDS": "",
        }
        with patch.dict(os.environ, environment):
            response = self.create_client().post(
                "/api/community/reports",
                json=CREATE_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-pilot-token"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "app_check_configuration_invalid",
        )

    def test_token_from_an_unlisted_firebase_app_is_rejected(self):
        def verifier(token):
            return {"app_id": "com.meteofriul.app"}

        with patch.dict(os.environ, ENFORCE_ENV):
            response = self.create_client(verifier).post(
                "/api/community/reports",
                json=CREATE_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-other-app-token"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["code"],
            "app_check_app_not_allowed",
        )


if __name__ == "__main__":
    unittest.main()
