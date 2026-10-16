import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.push import get_push_service
from app.contracts.push import (
    ActiveAlertDeliveryResponse,
    PushDeviceLocationUpdateResponse,
    PushDeviceRegisterResponse,
    PushDeviceUnregisterResponse,
)
from app.infrastructure.app_check import APP_CHECK_HEADER, get_app_check_verifier
from app.main import create_app
from app.repositories.push import PushPilotCapacityReached, PushTargetAlreadyRegistered
from app.services.push import (
    PushAppVersionNotAllowed,
    PushConfigurationError,
    PushLocalityInvalid,
    PushMunicipalityInvalid,
    PushPilotConfig,
    PushPlatformNotAllowed,
)


ANDROID_APP_ID = "1:1234567890:android:abcdef0123456789"
WEB_APP_ID = "1:49007668366:web:a848e70da40a12eb852ddf"
INSTALLATION_ID = "0123456789abcdef0123456789abcdef"
WEB_INSTALLATION_ID = "fedcba9876543210fedcba9876543210"
WEB_FID = "c123456789012345678901"
ANDROID_REGISTER_PAYLOAD = {
    "installation_id": INSTALLATION_ID,
    "token": "fcm-token-that-is-long-enough-for-tests",
    "platform": "android",
    "app_version": "0.1.0-pilot",
    "language": "it",
    "municipality": {"istat": "093033", "name": "Pordenone"},
    "preferences": {"official_alerts": True, "weather_notices": True},
}
WEB_REGISTER_PAYLOAD = {
    "installation_id": WEB_INSTALLATION_ID,
    "registration": {
        "kind": "firebase_installation_id",
        "value": WEB_FID,
    },
    "platform": "web",
    "app_version": "web-2026.08.15",
    "language": "it",
    "municipality": {"istat": "093033", "name": "Pordenone"},
    "preferences": {"official_alerts": True, "weather_notices": True},
}
ENFORCE_ENV = {
    "PUSH_APP_CHECK_MODE": "enforce",
    "PUSH_APP_CHECK_ANDROID_APP_IDS": ANDROID_APP_ID,
    "PUSH_APP_CHECK_WEB_APP_IDS": WEB_APP_ID,
    "PUSH_APP_CHECK_ALLOWED_APP_IDS": "",
    "COMMUNITY_APP_CHECK_ALLOWED_APP_IDS": "",
    "COMMUNITY_STORAGE": "memory",
    "K_SERVICE": "",
}


class FixturePushService:
    def __init__(self, error=None):
        self.error = error
        self.registered = []
        self.register_contexts = []
        self.unregistered = []
        self.unregister_contexts = []
        self.location_updates = []

    def register(self, request, app_check_context=None):
        if self.error is not None:
            raise self.error
        if (
            app_check_context is not None
            and app_check_context.platform is not None
            and app_check_context.platform != request.platform
        ):
            raise PushPlatformNotAllowed("push_platform_not_allowed")
        self.registered.append(request)
        self.register_contexts.append(app_check_context)
        return PushDeviceRegisterResponse(
            device_id="a" * 64,
            created=True,
            active_alert_delivery=ActiveAlertDeliveryResponse(status="disabled"),
        )

    def unregister(self, installation_id, app_check_context=None):
        if self.error is not None:
            raise self.error
        self.unregistered.append(installation_id)
        self.unregister_contexts.append(app_check_context)
        return PushDeviceUnregisterResponse(unregistered=True)

    def update_location(self, request, app_check_context=None):
        if self.error is not None:
            raise self.error
        if app_check_context is not None and app_check_context.platform != "android":
            raise PushPlatformNotAllowed("push_platform_not_allowed")
        self.location_updates.append((request, app_check_context))
        return PushDeviceLocationUpdateResponse(
            updated=True,
            status="resolved",
            local_target_eligible=True,
            display_name="Vigonovo",
            municipality={"istat": "093022", "name": "Fontanafredda"},
            locality={"id": "irdat:vigonovo", "name": "Vigonovo"},
            data_point={
                "lat": 46.0031,
                "lon": 12.5482,
                "source": "rafvg_irdat_5000",
            },
        )


class PushApiTests(unittest.TestCase):
    def create_client(self, *, service=None, verifier=None):
        app = create_app()
        app.dependency_overrides[get_push_service] = lambda: service or FixturePushService()
        if verifier is not None:
            app.dependency_overrides[get_app_check_verifier] = lambda: verifier
        return TestClient(app)

    def test_register_requires_app_check_before_service_mutation(self):
        service = FixturePushService()
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service).post(
                "/api/push/devices/register",
                json=ANDROID_REGISTER_PAYLOAD,
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "app_check_required")
        self.assertEqual(service.registered, [])

    def test_background_location_update_requires_android_app_check_and_hides_coordinates(self):
        service = FixturePushService()
        payload = {
            "installation_id": INSTALLATION_ID,
            "lat": 45.99,
            "lon": 12.55,
            "accuracy_m": 18,
            "captured_at": "2026-08-16T12:00:00+00:00",
            "trigger": "geofence_exit",
        }
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            missing = self.create_client(service=service).post(
                "/api/push/devices/location",
                json=payload,
            )
            accepted = self.create_client(
                service=service,
                verifier=lambda token: {"app_id": ANDROID_APP_ID},
            ).post(
                "/api/push/devices/location",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(accepted.status_code, 200)
        self.assertNotIn("45.99", accepted.text)
        self.assertNotIn("12.55", accepted.text)
        self.assertEqual(accepted.json()["display_name"], "Vigonovo")
        self.assertEqual(
            accepted.json()["data_point"],
            {
                "lat": 46.0031,
                "lon": 12.5482,
                "source": "rafvg_irdat_5000",
            },
        )
        self.assertEqual(len(service.location_updates), 1)

    def test_web_app_check_cannot_update_an_android_background_location(self):
        service = FixturePushService()
        payload = {
            "installation_id": INSTALLATION_ID,
            "lat": 45.99,
            "lon": 12.55,
            "accuracy_m": 18,
            "captured_at": "2026-08-16T12:00:00+00:00",
            "trigger": "periodic",
        }
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(
                service=service,
                verifier=lambda token: {"app_id": WEB_APP_ID},
            ).post(
                "/api/push/devices/location",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "push_platform_not_allowed")
        self.assertEqual(service.location_updates, [])

    def test_auto_firestore_mode_also_defaults_push_app_check_to_enforce(self):
        environment = {
            **ENFORCE_ENV,
            "COMMUNITY_STORAGE": "auto",
        }
        with patch.dict(os.environ, environment, clear=False):
            os.environ.pop("PUSH_APP_CHECK_MODE", None)
            os.environ.pop("COMMUNITY_APP_CHECK_MODE", None)
            response = self.create_client().post(
                "/api/push/devices/register",
                json=ANDROID_REGISTER_PAYLOAD,
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "app_check_required")

    def test_legacy_android_contract_still_registers_and_receives_app_check_context(self):
        service = FixturePushService()
        verifier = lambda token: {"app_id": ANDROID_APP_ID, "sub": "android-attestation"}
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/register",
                json=ANDROID_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("token", response.text)
        self.assertEqual(
            response.json()["active_alert_delivery"]["sent_unconfirmed"],
            0,
        )
        self.assertEqual(len(service.registered), 1)
        registered = service.registered[0]
        self.assertEqual(registered.platform, "android")
        self.assertEqual(registered.token, ANDROID_REGISTER_PAYLOAD["token"])
        self.assertEqual(
            registered.preferences.weather_notices,
            True,
        )
        context = service.register_contexts[0]
        self.assertEqual(context.app_id, ANDROID_APP_ID)
        self.assertEqual(context.platform, "android")
        self.assertEqual(context.claims["sub"], "android-attestation")

    def test_android_contract_accepts_automatic_municipality_without_locality(self):
        service = FixturePushService()
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        payload = {
            **ANDROID_REGISTER_PAYLOAD,
            "location_mode": "automatic_gps",
            "location_evidence": {
                "captured_at": "2026-08-16T12:00:00+00:00",
                "accuracy_m": 25,
            },
        }

        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/register",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 200)
        registered = service.registered[0]
        self.assertIsNone(registered.locality)
        self.assertEqual(registered.location_mode, "automatic_gps")

    def test_location_mode_without_canonical_municipality_is_rejected(self):
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        payload = {
            **ANDROID_REGISTER_PAYLOAD,
            "municipality": None,
            "location_mode": "automatic_gps",
            "location_evidence": {
                "captured_at": "2026-08-16T12:00:00+00:00",
                "accuracy_m": 25,
            },
        }

        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_web_contract_accepts_only_a_firebase_installation_registration(self):
        service = FixturePushService()
        verifier = lambda token: {"app_id": WEB_APP_ID, "sub": "web-attestation"}
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/register",
                json=WEB_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(WEB_FID, response.text)
        self.assertEqual(len(service.registered), 1)
        registered = service.registered[0].model_dump(exclude_none=True)
        self.assertEqual(registered["platform"], "web")
        self.assertEqual(
            registered["registration"],
            WEB_REGISTER_PAYLOAD["registration"],
        )
        self.assertNotIn("token", registered)
        context = service.register_contexts[0]
        self.assertEqual(context.app_id, WEB_APP_ID)
        self.assertEqual(context.platform, "web")
        self.assertEqual(context.claims["sub"], "web-attestation")

    def test_unregister_uses_same_app_check_gate_and_contract(self):
        service = FixturePushService()
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/unregister",
                json={"installation_id": INSTALLATION_ID},
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"unregistered": True})
        self.assertEqual(service.unregistered, [INSTALLATION_ID])
        context = service.unregister_contexts[0]
        self.assertEqual(context.app_id, ANDROID_APP_ID)
        self.assertEqual(context.platform, "android")

    def test_web_unregister_passes_web_app_check_context_to_service(self):
        service = FixturePushService()
        verifier = lambda token: {"app_id": WEB_APP_ID}
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/unregister",
                json={"installation_id": WEB_INSTALLATION_ID},
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.unregistered, [WEB_INSTALLATION_ID])
        context = service.unregister_contexts[0]
        self.assertEqual(context.app_id, WEB_APP_ID)
        self.assertEqual(context.platform, "web")

    def test_only_32_character_random_hex_installation_id_is_accepted(self):
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        invalid_payload = {
            **ANDROID_REGISTER_PAYLOAD,
            "installation_id": "not-a-uuid",
        }
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=invalid_payload,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_unknown_platform_is_rejected(self):
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json={**ANDROID_REGISTER_PAYLOAD, "platform": "ios"},
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_web_rejects_legacy_root_token_without_registration(self):
        verifier = lambda token: {"app_id": WEB_APP_ID}
        payload = {
            **ANDROID_REGISTER_PAYLOAD,
            "installation_id": WEB_INSTALLATION_ID,
            "platform": "web",
        }
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_web_rejects_fcm_token_registration_kind(self):
        verifier = lambda token: {"app_id": WEB_APP_ID}
        payload = {
            **WEB_REGISTER_PAYLOAD,
            "registration": {
                "kind": "fcm_token",
                "value": ANDROID_REGISTER_PAYLOAD["token"],
            },
        }
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_android_rejects_firebase_installation_registration(self):
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        payload = {
            **WEB_REGISTER_PAYLOAD,
            "installation_id": INSTALLATION_ID,
            "platform": "android",
        }
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_web_rejects_malformed_firebase_installation_id(self):
        verifier = lambda token: {"app_id": WEB_APP_ID}
        payload = {
            **WEB_REGISTER_PAYLOAD,
            "registration": {
                "kind": "firebase_installation_id",
                "value": "not a valid fid",
            },
        }
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_web_rejects_firebase_installation_id_with_wrong_length(self):
        verifier = lambda token: {"app_id": WEB_APP_ID}
        payload = {
            **WEB_REGISTER_PAYLOAD,
            "registration": {
                "kind": "firebase_installation_id",
                "value": "c12345678901234567890",
            },
        }
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_web_rejects_firebase_installation_id_with_invalid_prefix(self):
        verifier = lambda token: {"app_id": WEB_APP_ID}
        payload = {
            **WEB_REGISTER_PAYLOAD,
            "registration": {
                "kind": "firebase_installation_id",
                "value": "a123456789012345678901",
            },
        }
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_web_rejects_ambiguous_legacy_token_and_registration(self):
        verifier = lambda token: {"app_id": WEB_APP_ID}
        payload = {
            **WEB_REGISTER_PAYLOAD,
            "token": ANDROID_REGISTER_PAYLOAD["token"],
        }
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_android_app_check_id_cannot_register_a_web_target(self):
        service = FixturePushService()
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/register",
                json=WEB_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-android-token"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "push_platform_not_allowed")
        self.assertEqual(service.registered, [])

    def test_web_app_check_id_cannot_register_an_android_target(self):
        service = FixturePushService()
        verifier = lambda token: {"app_id": WEB_APP_ID}
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/register",
                json=ANDROID_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "push_platform_not_allowed")
        self.assertEqual(service.registered, [])

    def test_unknown_app_id_is_rejected(self):
        verifier = lambda token: {"app_id": "different-app"}
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=ANDROID_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["code"],
            "app_check_app_not_allowed",
        )

    def test_web_app_id_must_be_explicitly_allowlisted(self):
        verifier = lambda token: {"app_id": WEB_APP_ID}
        environment = {**ENFORCE_ENV, "PUSH_APP_CHECK_WEB_APP_IDS": ""}
        with patch.dict(os.environ, environment, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=WEB_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["code"],
            "app_check_app_not_allowed",
        )

    def test_android_and_web_app_check_allowlists_cannot_overlap(self):
        verifier = lambda token: {"app_id": WEB_APP_ID}
        environment = {
            **ENFORCE_ENV,
            "PUSH_APP_CHECK_ANDROID_APP_IDS": WEB_APP_ID,
            "PUSH_APP_CHECK_WEB_APP_IDS": WEB_APP_ID,
        }
        with patch.dict(os.environ, environment, clear=False):
            response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=WEB_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-web-token"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "app_check_configuration_invalid",
        )

    def test_legacy_app_check_fallback_remains_android_only(self):
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        environment = {
            **ENFORCE_ENV,
            "PUSH_APP_CHECK_ANDROID_APP_IDS": "",
            "PUSH_APP_CHECK_WEB_APP_IDS": "",
            "PUSH_APP_CHECK_ALLOWED_APP_IDS": ANDROID_APP_ID,
        }
        with patch.dict(os.environ, environment, clear=False):
            android_response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=ANDROID_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-android-token"},
            )
            web_response = self.create_client(verifier=verifier).post(
                "/api/push/devices/register",
                json=WEB_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-android-token"},
            )

        self.assertEqual(android_response.status_code, 200)
        self.assertEqual(web_response.status_code, 403)
        self.assertEqual(
            web_response.json()["detail"]["code"],
            "push_platform_not_allowed",
        )

    def test_pilot_capacity_maps_to_sanitized_conflict(self):
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        service = FixturePushService(
            error=PushPilotCapacityReached("capacity")
        )
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/register",
                json=ANDROID_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"]["code"],
            "push_pilot_capacity_reached",
        )

    def test_duplicate_fcm_target_maps_to_sanitized_conflict(self):
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        service = FixturePushService(
            error=PushTargetAlreadyRegistered("sensitive-target-data")
        )
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/register",
                json=ANDROID_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"]["code"],
            "push_target_already_registered",
        )
        self.assertNotIn("sensitive-target-data", response.text)
        self.assertNotIn(ANDROID_REGISTER_PAYLOAD["token"], response.text)

    def test_disallowed_play_build_maps_to_sanitized_forbidden(self):
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        service = FixturePushService(
            error=PushAppVersionNotAllowed("old_build")
        )
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/register",
                json=ANDROID_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["code"],
            "push_app_version_not_allowed",
        )

    def test_municipality_catalog_mismatch_maps_to_422(self):
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        service = FixturePushService(
            error=PushMunicipalityInvalid("mismatch")
        )
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/register",
                json=ANDROID_REGISTER_PAYLOAD,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"]["code"],
            "push_municipality_invalid",
        )

    def test_locality_catalog_mismatch_maps_to_422(self):
        verifier = lambda token: {"app_id": ANDROID_APP_ID}
        service = FixturePushService(error=PushLocalityInvalid("mismatch"))
        payload = {
            **ANDROID_REGISTER_PAYLOAD,
            "locality": {"id": "official:unknown", "name": "Vigonovo"},
        }
        with patch.dict(os.environ, ENFORCE_ENV, clear=False):
            response = self.create_client(service=service, verifier=verifier).post(
                "/api/push/devices/register",
                json=payload,
                headers={APP_CHECK_HEADER: "valid-token"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "push_locality_invalid")


class PushWebConfigurationTests(unittest.TestCase):
    def test_web_app_url_defaults_to_the_canonical_https_origin(self):
        environment = {
            "PUSH_OFFICIAL_ALERTS_MODE": "off",
            "PUSH_PILOT_MAX_DEVICES": "2",
            "PUSH_PILOT_ALLOWED_INSTALLATION_HASHES": "",
            "PUSH_WEB_APP_URL": "removed-below",
        }
        with patch.dict(os.environ, environment, clear=False):
            os.environ.pop("PUSH_WEB_APP_URL", None)
            config = PushPilotConfig.from_environment()

        self.assertEqual(config.web_app_url, "https://meteofriul.app")

    def test_web_app_url_rejects_non_https_or_non_origin_values(self):
        invalid_urls = (
            "http://meteofriul.app",
            "https://meteofriul.app/path",
            "https://meteofriul.app?preview=true",
            "https://meteofriul.app#bulletin",
            "not-a-url",
        )
        for invalid_url in invalid_urls:
            with self.subTest(invalid_url=invalid_url):
                environment = {
                    "PUSH_OFFICIAL_ALERTS_MODE": "off",
                    "PUSH_PILOT_MAX_DEVICES": "2",
                    "PUSH_PILOT_ALLOWED_INSTALLATION_HASHES": "",
                    "PUSH_WEB_APP_URL": invalid_url,
                }
                with patch.dict(os.environ, environment, clear=False):
                    with self.assertRaises(PushConfigurationError):
                        PushPilotConfig.from_environment()


if __name__ == "__main__":
    unittest.main()
