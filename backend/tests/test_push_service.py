import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.contracts.push import (
    PushDeviceLocationUpdateRequest,
    PushDeviceRegisterRequest,
    PushPreferences,
)
from app.infrastructure.app_check import PushAppCheckContext
from app.push.fcm import (
    DEFAULT_ANDROID_NOTIFICATION_CHANNEL,
    FcmBatchOutcome,
    FcmConfigurationError,
    FcmSenderUnavailable,
    FcmTokenInvalid,
)
from app.repositories.push import (
    PUSH_TARGET_FCM_TOKEN,
    PUSH_TARGET_FIREBASE_INSTALLATION_ID,
    PushDeliveryClaim,
    PushDeviceUpsertResult,
    PushRepositoryUnavailable,
    hash_installation_id,
    hash_push_target,
)
from app.services.push import (
    PUSH_TITLE,
    PushAppVersionNotAllowed,
    PushConfigurationError,
    PushInstallationNotAllowed,
    PushLocationEvidenceInvalid,
    PushLocalityInvalid,
    PushMunicipalityInvalid,
    PushPlatformNotAllowed,
    PushPilotConfig,
    PushPilotService,
)


NOW = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
INSTALLATION_ID = "0123456789abcdef0123456789abcdef"
DEVICE_ID = hash_installation_id(INSTALLATION_ID)
WEB_INSTALLATION_ID = "fedcba9876543210fedcba9876543210"
WEB_DEVICE_ID = hash_installation_id(WEB_INSTALLATION_ID)
WEB_FID = "c123456789012345678901"
PLAY_ANDROID_APP_ID = "1:123:android:abcdef012345"
PLAY_WEB_APP_ID = "1:123:web:abcdef012345"
PLAY_BETA_GENERATION = "play-beta-v1"
PLAY_BETA_APP_VERSION = "0.1.0+300017"
PLAY_BETA_NEXT_APP_VERSION = "0.1.3+300020"
DEFAULT_FVG_MUNICIPALITY = {"istat": "093033", "name": "Pordenone"}


def official_payload(
    *,
    cache_status="fresh",
    source_id="protezione_civile_fvg_alerts",
    source_mode="official_telegram_pdf_verified",
):
    return {
        "active": True,
        "count": 2,
        "source": {"id": source_id},
        "source_mode": source_mode,
        "fetched_at": NOW.isoformat(),
        "cache": {"status": cache_status},
        "alerts": [
            {
                "id": "yellow-zone-b",
                "alert_number": 22,
                "alert_year": 2026,
                "published_at": (NOW - timedelta(minutes=20)).isoformat(),
                "revision_hash": "a" * 64,
                "pdf_url": "https://cfd.protezionecivile.fvg.it/docs/alerts/alert-22.pdf",
                "pdf_sha256": "b" * 64,
                "pdf_size_bytes": 4096,
                "pdf_verified_at": (NOW - timedelta(minutes=19)).isoformat(),
                "level": "gialla",
                "risks": ["temporali"],
                "area": "Zona B",
                "zones": ["FVG-B"],
                "valid_from": NOW.isoformat(),
                "valid_to": (NOW + timedelta(hours=4)).isoformat(),
                "push_body_i18n": {
                    "it": "Allerta gialla per temporali in Zona B.",
                    "fur": "Alerte zale par burlaçs inte zone B.",
                },
            },
            {
                "id": "orange-zone-a",
                "alert_number": 23,
                "alert_year": 2026,
                "published_at": (NOW - timedelta(minutes=10)).isoformat(),
                "revision_hash": "b" * 64,
                "pdf_url": "https://cfd.protezionecivile.fvg.it/docs/alerts/alert-23.pdf",
                "pdf_sha256": "c" * 64,
                "pdf_size_bytes": 4096,
                "pdf_verified_at": (NOW - timedelta(minutes=9)).isoformat(),
                "level": "arancione",
                "risks": ["pioggia", "vento"],
                "area": "Zona A",
                "zones": ["FVG-A"],
                "valid_from": NOW.isoformat(),
                "valid_to": (NOW + timedelta(hours=2)).isoformat(),
                "push_body_i18n": {
                    "it": "Allerta arancione per pioggia e vento in Zona A.",
                    "fur": "Alerte narançade par ploie e aiar inte zone A.",
                },
            },
        ],
    }


def corroborated_official_payload(
    source_mode="official_fvg_widget_arpa_corroborated",
):
    payload = official_payload(source_mode=source_mode)
    method = (
        "official_telegram_arpa"
        if source_mode == "official_telegram_arpa_corroborated"
        else (
            "official_fvg_page_arpa"
            if source_mode == "official_page_arpa_corroborated"
            else "official_fvg_widget_arpa"
        )
    )
    for alert in payload["alerts"]:
        number = alert["alert_number"]
        alert.update(
            pdf_url=(
                "https://pianiemergenza.protezionecivile.fvg.it/"
                f"alerts/{number}_2026.pdf"
            ),
            corroborated_at=NOW.isoformat(),
            corroboration={
                "method": method,
                "identity": f"2026:{number}",
                "pcr_revision": "d" * 64,
            },
        )
        alert.pop("pdf_sha256", None)
        alert.pop("pdf_size_bytes", None)
        alert.pop("pdf_verified_at", None)
    return payload


def device(
    *,
    device_id=DEVICE_ID,
    token="fcm-token-that-is-long-enough-for-tests",
    language="it",
    official_alerts=True,
    weather_notices=True,
    schema_version="1.0",
    enrollment_generation="",
    app_check_app_id="",
    app_version="",
    municipality=DEFAULT_FVG_MUNICIPALITY,
):
    return {
        "schema_version": schema_version,
        "device_id": device_id,
        "token": token,
        "token_hash": hash_push_target(token),
        "platform": "android",
        "app_check_app_id": app_check_app_id,
        "enrollment_generation": enrollment_generation,
        "app_version": app_version,
        "language": language,
        "active": True,
        "municipality": dict(municipality) if municipality is not None else None,
        "preferences": {
            "official_alerts": official_alerts,
            "weather_notices": weather_notices,
        },
    }


def web_device(
    *,
    device_id=WEB_DEVICE_ID,
    fid=WEB_FID,
    language="it",
    official_alerts=True,
    weather_notices=True,
    municipality=DEFAULT_FVG_MUNICIPALITY,
    schema_version="2.0",
    enrollment_generation="",
    app_check_app_id="",
    app_version="",
):
    return {
        "schema_version": schema_version,
        "device_id": device_id,
        "target_kind": PUSH_TARGET_FIREBASE_INSTALLATION_ID,
        "target_value": fid,
        "target_hash": hash_push_target(fid),
        "token": "",
        "token_hash": "",
        "platform": "web",
        "app_check_app_id": app_check_app_id,
        "enrollment_generation": enrollment_generation,
        "app_version": app_version,
        "language": language,
        "active": True,
        "municipality": dict(municipality) if municipality is not None else None,
        "preferences": {
            "official_alerts": official_alerts,
            "weather_notices": weather_notices,
        },
    }


class FakePushRepository:
    def __init__(self):
        self.devices = [device()]
        self.claims = {}
        self.claim_calls = []
        self.finished = []
        self.disabled = []
        self.upserts = []
        self.unregistered = []
        self.location_updates = []
        self.finish_result = True

    def upsert_device(self, **kwargs):
        self.upserts.append(kwargs)
        target_kind = kwargs["target_kind"]
        target_value = kwargs["target_value"]
        target_hash = hash_push_target(target_value)
        stored = {
            "schema_version": "2.1",
            "device_id": kwargs["device_id"],
            "target_kind": target_kind,
            "target_value": target_value,
            "target_hash": target_hash,
            "token": (
                target_value if target_kind == PUSH_TARGET_FCM_TOKEN else ""
            ),
            "token_hash": (
                target_hash if target_kind == PUSH_TARGET_FCM_TOKEN else ""
            ),
            "platform": kwargs["platform"],
            "app_check_app_id": kwargs.get("app_check_app_id", ""),
            "enrollment_mode": kwargs.get("enrollment_mode", ""),
            "enrollment_generation": kwargs.get("enrollment_generation", ""),
            "app_version": kwargs["app_version"],
            "language": kwargs["language"],
            "municipality": kwargs["municipality"],
            "locality": kwargs.get("locality"),
            "location_mode": kwargs.get("location_mode"),
            "location_evidence": kwargs.get("location_evidence"),
            "preferences": dict(kwargs["preferences"]),
            "active": True,
        }
        self.devices = [stored]
        return PushDeviceUpsertResult(device=stored, created=True)

    def unregister_device(self, **kwargs):
        self.unregistered.append(kwargs)
        matching = [
            item
            for item in self.devices
            if item.get("device_id") == kwargs["device_id"]
        ]
        expected_platform = kwargs.get("expected_platform") or ""
        if (
            not matching
            or expected_platform
            and matching[0].get("platform") != expected_platform
        ):
            return False
        self.devices = [
            item
            for item in self.devices
            if item.get("device_id") != kwargs["device_id"]
        ]
        return True

    def update_android_location_target(self, **kwargs):
        self.location_updates.append(kwargs)
        matching = [
            item for item in self.devices
            if item.get("device_id") == kwargs["device_id"]
            and item.get("platform") == "android"
            and item.get("active") is True
        ]
        if not matching:
            return None
        stored = matching[0]
        stored.update({
            "municipality": kwargs["municipality"],
            "locality": kwargs["locality"],
            "location_mode": "automatic_gps" if kwargs["location_evidence"] else "",
            "location_evidence": kwargs["location_evidence"],
        })
        return dict(stored)

    def list_active_devices(self, *, max_devices, enrollment_generation=None):
        devices = [
            item
            for item in self.devices
            if enrollment_generation is None
            or item.get("enrollment_generation") == enrollment_generation
        ]
        if enrollment_generation is None and len(devices) > max_devices:
            raise AssertionError("test capacity exceeded")
        return [dict(item) for item in devices]

    def claim_official_alert_delivery(self, **kwargs):
        self.claim_calls.append(kwargs)
        key = (kwargs["device_id"], kwargs["alert_signature"])
        if key in self.claims:
            return PushDeliveryClaim(
                delivery_id=self.claims[key],
                claimed=False,
                state="sent",
            )
        delivery_id = f"delivery-{len(self.claims) + 1}"
        self.claims[key] = delivery_id
        return PushDeliveryClaim(
            delivery_id=delivery_id,
            claimed=True,
            state="sending",
            claim_id=f"claim-{len(self.claims)}",
            target_kind=kwargs.get("target_kind", ""),
            target_hash=kwargs.get("target_hash", ""),
        )

    def finish_official_alert_delivery(self, **kwargs):
        self.finished.append(kwargs)
        return self.finish_result

    def disable_device(self, **kwargs):
        self.disabled.append(kwargs)
        return True


class FakeSender:
    def __init__(self, error=None):
        self.messages = []
        self.error = error

    def send(self, message):
        self.messages.append(message)
        if self.error is not None:
            raise self.error
        return f"message-{len(self.messages)}"


class FakeBatchSender(FakeSender):
    def __init__(self):
        super().__init__()
        self.batch_sizes = []

    def send_batch(self, messages):
        self.batch_sizes.append(len(messages))
        self.messages.extend(messages)
        return [
            FcmBatchOutcome(message_id=f"batch-message-{index}")
            for index, _ in enumerate(messages, start=1)
        ]


class PushPilotServiceTests(unittest.TestCase):
    def make_service(
        self,
        *,
        mode="send",
        repository=None,
        sender=None,
        loader=None,
        allowed_hashes=frozenset(),
        max_devices=1,
        enrollment_mode="owner_allowlist",
        enrollment_generation="",
        android_app_ids=frozenset(),
        web_app_ids=frozenset(),
        allowed_app_versions=frozenset(),
        min_app_version_code=None,
        location_service=None,
    ):
        return PushPilotService(
            repository=repository or FakePushRepository(),
            sender=sender or FakeSender(),
            official_alert_loader=loader or official_payload,
            config=PushPilotConfig(
                mode=mode,
                max_devices=max_devices,
                allowed_installation_hashes=allowed_hashes,
                enrollment_mode=enrollment_mode,
                enrollment_generation=enrollment_generation,
                android_app_ids=android_app_ids,
                web_app_ids=web_app_ids,
                allowed_app_versions=allowed_app_versions,
                min_app_version_code=min_app_version_code,
            ),
            now=lambda: NOW,
            location_service=location_service,
        )

    def test_background_location_refresh_persists_only_canonical_target(self):
        repository = FakePushRepository()
        location_service = SimpleNamespace(reverse=lambda **kwargs: SimpleNamespace(
            displayName="Vigonovo",
            municipality=SimpleNamespace(istatCode="093022", name="Fontanafredda"),
            locality=SimpleNamespace(id="irdat:vigonovo", name="Vigonovo"),
            dataPoint=SimpleNamespace(
                lat=46.0031,
                lon=12.5482,
                source="rafvg_irdat_5000",
            ),
            resolution=SimpleNamespace(status="resolved", boundaryDistanceM=600.0),
        ))
        service = self.make_service(
            mode="off",
            repository=repository,
            location_service=location_service,
        )
        context = PushAppCheckContext(
            claims={"app_id": "1:123:android:private"},
            app_id="1:123:android:private",
            platform="android",
        )

        result = service.update_location(
            PushDeviceLocationUpdateRequest(
                installation_id=INSTALLATION_ID,
                lat=45.99,
                lon=12.55,
                accuracy_m=18,
                captured_at=NOW - timedelta(seconds=20),
                trigger="geofence_exit",
            ),
            app_check_context=context,
        )

        self.assertEqual(result.status, "resolved")
        self.assertTrue(result.local_target_eligible)
        self.assertEqual(result.display_name, "Vigonovo")
        self.assertEqual(result.data_point.lat, 46.0031)
        self.assertEqual(result.data_point.lon, 12.5482)
        self.assertEqual(result.data_point.source, "rafvg_irdat_5000")
        update = repository.location_updates[-1]
        self.assertEqual(update["municipality"]["name"], "Fontanafredda")
        self.assertEqual(update["locality"]["name"], "Vigonovo")
        self.assertEqual(update["location_evidence"]["trigger"], "geofence_exit")
        self.assertNotIn("lat", update["location_evidence"])
        self.assertNotIn("lon", update["location_evidence"])

    def test_background_location_refresh_fails_closed_at_boundary_and_when_stale(self):
        repository = FakePushRepository()
        location_service = SimpleNamespace(reverse=lambda **kwargs: SimpleNamespace(
            displayName="",
            municipality=SimpleNamespace(istatCode="030001", name="Aiello del Friuli"),
            locality=None,
            dataPoint=SimpleNamespace(
                lat=45.871,
                lon=13.365,
                source="municipality_catalog",
            ),
            resolution=SimpleNamespace(status="municipality_only", boundaryDistanceM=20.0),
        ))
        service = self.make_service(
            mode="off",
            repository=repository,
            location_service=location_service,
        )
        request = PushDeviceLocationUpdateRequest(
            installation_id=INSTALLATION_ID,
            lat=45.8855,
            lon=13.3720,
            accuracy_m=18,
            captured_at=NOW - timedelta(seconds=20),
            trigger="periodic",
        )

        result = service.update_location(request)
        self.assertEqual(result.status, "ambiguous_boundary")
        self.assertFalse(result.local_target_eligible)
        self.assertIsNone(result.data_point)
        self.assertIsNone(repository.location_updates[-1]["municipality"])

        with self.assertRaises(PushLocationEvidenceInvalid):
            service.update_location(request.model_copy(update={
                "captured_at": NOW - timedelta(minutes=11),
            }))

    def test_external_location_returns_only_its_canonical_weather_point(self):
        repository = FakePushRepository()
        location_service = SimpleNamespace(reverse=lambda **kwargs: SimpleNamespace(
            displayName="San Giovanni in Persiceto",
            municipality=None,
            locality=None,
            dataPoint=SimpleNamespace(
                lat=44.6386,
                lon=11.1842,
                source="nominatim_place",
            ),
            resolution=SimpleNamespace(
                status="external_place",
                boundaryDistanceM=None,
            ),
        ))
        service = self.make_service(
            mode="off",
            repository=repository,
            location_service=location_service,
        )

        result = service.update_location(
            PushDeviceLocationUpdateRequest(
                installation_id=INSTALLATION_ID,
                lat=44.6401,
                lon=11.1899,
                accuracy_m=22,
                captured_at=NOW - timedelta(seconds=20),
                trigger="periodic",
            ),
        )

        self.assertEqual(result.status, "external_place")
        self.assertFalse(result.local_target_eligible)
        self.assertEqual(result.display_name, "San Giovanni in Persiceto")
        self.assertEqual(result.data_point.lat, 44.6386)
        self.assertEqual(result.data_point.lon, 11.1842)
        self.assertEqual(result.data_point.source, "nominatim_place")
        update = repository.location_updates[-1]
        self.assertIsNone(update["municipality"])
        self.assertIsNone(update["locality"])
        self.assertIsNone(update["location_evidence"])

    def test_clean_install_defaults_enable_both_notification_preferences(self):
        self.assertEqual(
            PushPreferences().model_dump(),
            {"official_alerts": True, "weather_notices": True},
        )

    def test_dispatch_sends_one_highest_priority_notification_for_whole_state(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 1)
        self.assertEqual(len(sender.messages), 1)
        message = sender.messages[0]
        self.assertEqual(message.title, PUSH_TITLE)
        self.assertEqual(message.title, "Meteo Fri\u00fbl")
        self.assertEqual(ord(message.title[-2]), 0x00FB)
        self.assertEqual(
            message.body,
            "Allerta arancione per pioggia e vento in Zona A.",
        )
        self.assertEqual(message.channel_id, DEFAULT_ANDROID_NOTIFICATION_CHANNEL)
        self.assertEqual(message.collapse_key, "mf-official-alerts")
        self.assertEqual(message.notification_tag, "mf-official-alerts")
        self.assertEqual(message.platform, "android")
        self.assertEqual(message.target_kind, PUSH_TARGET_FCM_TOKEN)
        self.assertEqual(
            message.target_value,
            "fcm-token-that-is-long-enough-for-tests",
        )
        self.assertEqual(
            set(message.data),
            {"type", "alert_id", "issued_at", "area"},
        )
        self.assertEqual(message.data["type"], "official_alert")
        self.assertEqual(message.data["alert_id"], "orange-zone-a")
        self.assertEqual(message.data["area"], "Zona A")
        self.assertLessEqual(message.ttl_seconds, 2 * 60 * 60)

    def test_dispatch_requires_a_canonical_fvg_municipality(self):
        repository = FakePushRepository()
        valid = device()
        missing = device(device_id="e" * 64, municipality=None)
        mismatched = device(
            device_id="f" * 64,
            municipality={"istat": "093033", "name": "Roma"},
        )
        national = device(
            device_id="1" * 64,
            municipality={"istat": "058091", "name": "Roma"},
        )
        sender = FakeSender()
        service = self.make_service(
            repository=repository,
            sender=sender,
            max_devices=4,
        )

        result = service.dispatch_official_alerts(
            official_payload(),
            devices=[valid, missing, mismatched, national],
        )

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.attempted, 1)
        self.assertEqual(result.sent, 1)
        self.assertEqual(len(sender.messages), 1)
        self.assertEqual(repository.claim_calls[0]["device_id"], DEVICE_ID)

    def test_dispatch_does_not_count_fcm_send_when_outbox_confirmation_is_lost(self):
        repository = FakePushRepository()
        repository.finish_result = False
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "sent_unconfirmed")
        self.assertEqual(result.attempted, 1)
        self.assertEqual(result.sent, 0)
        self.assertEqual(result.sent_unconfirmed, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.summary()["sent_unconfirmed"], 1)
        self.assertEqual(result.response().sent_unconfirmed, 1)
        self.assertEqual(len(sender.messages), 1)

    def test_play_beta_dispatch_fails_closed_on_duplicate_fcm_targets(self):
        repository = FakePushRepository()
        repository.devices = [
            device(
                device_id=DEVICE_ID,
                schema_version="2.1",
                enrollment_generation=PLAY_BETA_GENERATION,
                app_check_app_id=PLAY_ANDROID_APP_ID,
                app_version=PLAY_BETA_APP_VERSION,
            ),
            device(
                device_id="f" * 64,
                schema_version="2.1",
                enrollment_generation=PLAY_BETA_GENERATION,
                app_check_app_id=PLAY_ANDROID_APP_ID,
                app_version=PLAY_BETA_APP_VERSION,
            ),
        ]
        service = self.make_service(
            repository=repository,
            max_devices=100,
            enrollment_mode="play_beta",
            enrollment_generation=PLAY_BETA_GENERATION,
            android_app_ids=frozenset({PLAY_ANDROID_APP_ID}),
            allowed_app_versions=frozenset({PLAY_BETA_APP_VERSION}),
        )

        with self.assertRaisesRegex(
            PushRepositoryUnavailable,
            "push_duplicate_fcm_target_detected",
        ):
            service.dispatch_official_alerts(
                official_payload(),
                devices=repository.devices,
            )

    def test_play_beta_dispatch_is_not_capped_by_firestore_page_size(self):
        devices = [
            device(
                device_id=f"{index + 1:064x}",
                token=f"play-token-{index}-long-enough",
                schema_version="2.1",
                enrollment_generation=PLAY_BETA_GENERATION,
                app_check_app_id=PLAY_ANDROID_APP_ID,
                app_version=PLAY_BETA_APP_VERSION,
            )
            for index in range(3)
        ]
        service = self.make_service(
            mode="dry_run",
            max_devices=2,
            enrollment_mode="play_beta",
            enrollment_generation=PLAY_BETA_GENERATION,
            android_app_ids=frozenset({PLAY_ANDROID_APP_ID}),
            allowed_app_versions=frozenset({PLAY_BETA_APP_VERSION}),
        )

        result = service.dispatch_official_alerts(
            official_payload(),
            devices=devices,
        )

        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.attempted, 3)

    def test_play_beta_dispatch_uses_bounded_fcm_batches(self):
        devices = [
            device(
                device_id=f"{index + 1:064x}",
                token=f"play-token-{index}-long-enough",
                schema_version="2.1",
                enrollment_generation=PLAY_BETA_GENERATION,
                app_check_app_id=PLAY_ANDROID_APP_ID,
                app_version=PLAY_BETA_APP_VERSION,
            )
            for index in range(3)
        ]
        sender = FakeBatchSender()
        service = self.make_service(
            mode="send",
            sender=sender,
            max_devices=2,
            enrollment_mode="play_beta",
            enrollment_generation=PLAY_BETA_GENERATION,
            android_app_ids=frozenset({PLAY_ANDROID_APP_ID}),
            allowed_app_versions=frozenset({PLAY_BETA_APP_VERSION}),
        )

        result = service.dispatch_official_alerts(
            official_payload(),
            devices=devices,
        )

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 3)
        self.assertEqual(result.pages_processed, 1)
        self.assertEqual(result.delivery_batches, 2)
        self.assertEqual(sender.batch_sizes, [2, 1])

    def test_dispatch_sends_android_v1_and_web_v2_with_owner_allowlist(self):
        outsider_id = "f" * 64
        repository = FakePushRepository()
        repository.devices = [
            device(),
            web_device(),
            web_device(
                device_id=outsider_id,
                fid="c99999999999999999999",
            ),
        ]
        sender = FakeSender()
        service = self.make_service(
            repository=repository,
            sender=sender,
            allowed_hashes=frozenset({DEVICE_ID, WEB_DEVICE_ID}),
            max_devices=3,
        )

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.attempted, 2)
        self.assertEqual(result.sent, 2)
        self.assertEqual(len(sender.messages), 2)
        android_message, web_message = sender.messages
        self.assertEqual(
            (
                android_message.platform,
                android_message.target_kind,
                android_message.target_value,
            ),
            (
                "android",
                PUSH_TARGET_FCM_TOKEN,
                "fcm-token-that-is-long-enough-for-tests",
            ),
        )
        self.assertEqual(
            (
                web_message.platform,
                web_message.target_kind,
                web_message.target_value,
            ),
            (
                "web",
                PUSH_TARGET_FIREBASE_INSTALLATION_ID,
                WEB_FID,
            ),
        )
        self.assertEqual(
            web_message.web_link,
            "https://meteofriul.app/?tab=bulletin",
        )
        self.assertEqual(
            {call["device_id"] for call in repository.claim_calls},
            {DEVICE_ID, WEB_DEVICE_ID},
        )

    def test_same_selected_alert_is_deduplicated_on_next_sync(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)

        first = service.dispatch_official_alerts(official_payload())
        second = service.dispatch_official_alerts(official_payload())

        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "deduplicated")
        self.assertEqual(second.deduplicated, 1)
        self.assertEqual(len(sender.messages), 1)

    def test_corroborated_alert_refresh_and_source_switch_do_not_resend(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)
        initial = corroborated_official_payload()
        refreshed = corroborated_official_payload()
        refreshed["fetched_at"] = (NOW + timedelta(seconds=1)).isoformat()
        for alert in refreshed["alerts"]:
            alert["corroborated_at"] = refreshed["fetched_at"]
            alert["revision_hash"] = "c" * 64
        alternate_source = corroborated_official_payload(
            source_mode="official_telegram_arpa_corroborated"
        )
        for alert in alternate_source["alerts"]:
            alert["revision_hash"] = "d" * 64

        first = service.dispatch_official_alerts(initial)
        second = service.dispatch_official_alerts(refreshed)
        third = service.dispatch_official_alerts(alternate_source)

        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "deduplicated")
        self.assertEqual(third.status, "deduplicated")
        self.assertEqual(len({call["alert_signature"] for call in repository.claim_calls}), 1)
        self.assertEqual(len(sender.messages), 1)

    def test_corroborated_alert_validity_change_sends_new_revision(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)
        initial = corroborated_official_payload()
        revised = corroborated_official_payload()
        revised["alerts"][1]["valid_to"] = (
            NOW + timedelta(hours=3)
        ).isoformat()

        first = service.dispatch_official_alerts(initial)
        second = service.dispatch_official_alerts(revised)

        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "sent")
        self.assertEqual(len({call["alert_signature"] for call in repository.claim_calls}), 2)
        self.assertEqual(len(sender.messages), 2)

    def test_real_yellow_23_to_orange_24_sends_each_alert_once(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)
        yellow_state = official_payload()
        yellow = yellow_state["alerts"][0]
        yellow.update(
            id="allerta-regionale-23-2026",
            alert_number=23,
            pdf_url=(
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_23-2026_19082026-14_57.pdf"
            ),
        )
        yellow_state.update(count=1, alerts=[yellow])
        orange_state = official_payload()
        orange = orange_state["alerts"][1]
        orange.update(
            id="allerta-regionale-24-2026",
            alert_number=24,
            pdf_url=(
                "https://cfd.protezionecivile.fvg.it/docs/alerts/2026/"
                "Allerta_regionale_24-2026_20082026-11_36.pdf"
            ),
        )
        orange_state.update(count=1, alerts=[orange])

        yellow_result = service.dispatch_official_alerts(yellow_state)
        orange_result = service.dispatch_official_alerts(orange_state)
        repeated_orange = service.dispatch_official_alerts(orange_state)

        self.assertEqual(yellow_result.status, "sent")
        self.assertEqual(orange_result.status, "sent")
        self.assertEqual(repeated_orange.status, "deduplicated")
        self.assertEqual(
            [message.data["alert_id"] for message in sender.messages],
            ["allerta-regionale-23-2026", "allerta-regionale-24-2026"],
        )

    def test_push_copy_and_telegram_text_revision_changes_with_same_pdf_dedupe(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)
        initial = official_payload()
        revised_copy = official_payload()
        revised_copy["alerts"][0]["push_body_i18n"] = {
            "it": "Testo italiano rivisto senza modificare l'allerta.",
            "fur": "Test furlan revisionât cence cambiâ la alerte.",
        }
        revised_copy["alerts"][1]["push_body_i18n"] = {
            "it": "Altro testo italiano rivisto.",
            "fur": "Altri test furlan revisionât.",
        }
        revised_copy["alerts"][1]["revision_hash"] = "d" * 64

        first = service.dispatch_official_alerts(initial)
        second = service.dispatch_official_alerts(revised_copy)

        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "deduplicated")
        self.assertEqual(len(sender.messages), 1)

    def test_selected_alert_identity_validity_level_and_area_change_signature(self):
        changes = {
            "event": lambda alert: alert.update(id="orange-zone-a-reissued"),
            "pdf": lambda alert: alert.update(
                pdf_url="https://cfd.protezionecivile.fvg.it/docs/alerts/alert-23-rev-2.pdf"
            ),
            "validity": lambda alert: alert.update(
                valid_to=(NOW + timedelta(hours=5)).isoformat()
            ),
            "level": lambda alert: alert.update(level="rossa"),
            "area": lambda alert: alert.update(area="Zona A e Zona C"),
            "zones": lambda alert: alert.update(zones=["FVG-A", "FVG-C"]),
        }

        for name, change in changes.items():
            with self.subTest(name=name):
                repository = FakePushRepository()
                sender = FakeSender()
                service = self.make_service(repository=repository, sender=sender)
                initial = official_payload()
                revised = official_payload()
                change(revised["alerts"][1])

                first = service.dispatch_official_alerts(initial)
                second = service.dispatch_official_alerts(revised)

                self.assertEqual(first.status, "sent")
                self.assertEqual(second.status, "sent")
                self.assertEqual(len(sender.messages), 2)

    def test_changed_verified_pdf_hash_creates_a_new_delivery(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)
        initial = official_payload()
        revised = official_payload()
        revised["alerts"][1]["pdf_sha256"] = "d" * 64

        first = service.dispatch_official_alerts(initial)
        second = service.dispatch_official_alerts(revised)

        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "sent")
        self.assertEqual(len(sender.messages), 2)

    def test_removing_or_changing_non_selected_alert_does_not_resend_primary(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)
        initial = official_payload()
        changed_secondary = official_payload()
        changed_secondary["alerts"][0]["area"] = "Zona B aggiornata"
        removed_secondary = official_payload()
        removed_secondary["alerts"] = [removed_secondary["alerts"][1]]
        removed_secondary["count"] = 1

        first = service.dispatch_official_alerts(initial)
        changed = service.dispatch_official_alerts(changed_secondary)
        removed = service.dispatch_official_alerts(removed_secondary)

        self.assertEqual(first.status, "sent")
        self.assertEqual(changed.status, "deduplicated")
        self.assertEqual(removed.status, "deduplicated")
        self.assertEqual(len(sender.messages), 1)

    def test_selected_order_is_highest_level_then_newest_publication_and_number(self):
        payload = official_payload()
        payload["alerts"][0].update(
            level="arancione",
            published_at=(NOW - timedelta(minutes=5)).isoformat(),
            pdf_verified_at=(NOW - timedelta(minutes=4)).isoformat(),
            alert_number=24,
        )
        sender = FakeSender()
        service = self.make_service(sender=sender)

        result = service.dispatch_official_alerts(payload)

        self.assertEqual(result.status, "sent")
        self.assertEqual(sender.messages[0].data["alert_id"], "yellow-zone-b")

    def test_only_active_capable_reconciled_source_modes_can_send(self):
        active_payloads = (
            official_payload(source_mode="official_telegram_pdf_verified"),
            corroborated_official_payload(),
            corroborated_official_payload(
                source_mode="official_telegram_arpa_corroborated"
            ),
            corroborated_official_payload(
                source_mode="official_page_arpa_corroborated"
            ),
        )
        for payload in active_payloads:
            with self.subTest(source_mode=payload["source_mode"]):
                sender = FakeSender()
                service = self.make_service(sender=sender)

                result = service.dispatch_official_alerts(payload)

                self.assertEqual(result.status, "sent")
                self.assertEqual(len(sender.messages), 1)

        for source_mode in ("official_widget", "official_page"):
            with self.subTest(legacy_active_mode=source_mode):
                sender = FakeSender()
                service = self.make_service(sender=sender)
                result = service.dispatch_official_alerts(
                    official_payload(source_mode=source_mode)
                )
                self.assertEqual(result.status, "source_unavailable")
                self.assertEqual(sender.messages, [])

        sender = FakeSender()
        service = self.make_service(sender=sender)
        result = service.dispatch_official_alerts(
            official_payload(source_mode="official_telegram_positive_only")
        )
        self.assertEqual(result.status, "source_unavailable")
        self.assertEqual(sender.messages, [])

        for source_mode in ("arpa_pcr_mirror", "official_validity_expired"):
            with self.subTest(active_only_invalid_mode=source_mode):
                sender = FakeSender()
                service = self.make_service(sender=sender)
                result = service.dispatch_official_alerts(
                    official_payload(source_mode=source_mode)
                )
                self.assertEqual(result.status, "source_unavailable")
                self.assertEqual(sender.messages, [])

    def test_structured_mode_requires_recent_exact_arpa_corroboration(self):
        cases = {
            "host": lambda alert: alert.update(
                pdf_url="https://example.invalid/alerts/23_2026.pdf"
            ),
            "identity": lambda alert: alert["corroboration"].update(
                identity="2026:22"
            ),
            "method": lambda alert: alert["corroboration"].update(
                method="text_similarity"
            ),
            "pcr_revision": lambda alert: alert["corroboration"].update(
                pcr_revision="not-a-hash"
            ),
            "revision_hash": lambda alert: alert.update(revision_hash="not-a-hash"),
            "stale": lambda alert: alert.update(
                corroborated_at=(NOW - timedelta(hours=1)).isoformat()
            ),
        }

        for name, mutate in cases.items():
            with self.subTest(name=name):
                payload = corroborated_official_payload()
                mutate(payload["alerts"][1])
                sender = FakeSender()
                service = self.make_service(sender=sender)

                result = service.dispatch_official_alerts(payload)

                self.assertEqual(result.status, "source_unavailable")
                self.assertEqual(sender.messages, [])

    def test_verified_telegram_mode_requires_downloaded_pdf_evidence(self):
        for missing_field in (
            "pdf_sha256",
            "pdf_size_bytes",
            "pdf_verified_at",
            "published_at",
        ):
            with self.subTest(missing_field=missing_field):
                payload = official_payload()
                payload["alerts"][1].pop(missing_field)
                sender = FakeSender()
                service = self.make_service(sender=sender)

                result = service.dispatch_official_alerts(payload)

                self.assertEqual(result.status, "source_unavailable")
                self.assertEqual(sender.messages, [])

    def test_official_validity_expired_is_trusted_inactive_state(self):
        sender = FakeSender()
        service = self.make_service(sender=sender)
        payload = official_payload(source_mode="official_validity_expired")
        payload.update(active=False, count=0, alerts=[])

        result = service.dispatch_official_alerts(payload)

        self.assertEqual(result.status, "no_active_alert")
        self.assertEqual(sender.messages, [])

    def test_friulian_device_uses_friulian_body(self):
        repository = FakePushRepository()
        repository.devices = [device(language="fur")]
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)

        service.dispatch_official_alerts(official_payload())

        self.assertEqual(
            sender.messages[0].body,
            "Alerte narançade par ploie e aiar inte zone A.",
        )

    def test_registration_is_idempotently_covered_by_shared_outbox(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)
        request = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
            language="it",
            municipality=DEFAULT_FVG_MUNICIPALITY,
        )

        first = service.register(request)
        second = service.register(request)

        self.assertTrue(first.created)
        self.assertEqual(first.active_alert_delivery.status, "sent")
        self.assertEqual(second.active_alert_delivery.status, "deduplicated")
        self.assertEqual(len(sender.messages), 1)
        self.assertNotIn("token", first.model_dump())
        self.assertEqual(repository.upserts[0]["preferences"]["weather_notices"], True)

    def test_registration_does_not_deliver_regional_alert_without_fvg_target(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(repository=repository, sender=sender)
        request = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
            preferences={
                "official_alerts": True,
                "weather_notices": False,
            },
        )

        response = service.register(request)

        self.assertEqual(
            response.active_alert_delivery.status,
            "no_eligible_devices",
        )
        self.assertEqual(sender.messages, [])
        self.assertIsNone(repository.upserts[-1]["municipality"])

    def test_off_mode_registers_without_loading_or_sending_current_alert(self):
        repository = FakePushRepository()
        sender = FakeSender()

        def forbidden_loader():
            raise AssertionError("loader must remain idle")

        service = self.make_service(
            mode="off",
            repository=repository,
            sender=sender,
            loader=forbidden_loader,
        )
        response = service.register(
            PushDeviceRegisterRequest(
                installation_id=INSTALLATION_ID,
                token="fcm-token-that-is-long-enough-for-tests",
                platform="android",
                app_version="0.1.0-pilot",
            )
        )

        self.assertEqual(response.active_alert_delivery.status, "disabled")
        self.assertEqual(len(repository.upserts), 1)
        self.assertEqual(sender.messages, [])

    def test_weather_notices_preference_never_triggers_a_local_web_push(self):
        repository = FakePushRepository()
        sender = FakeSender()

        def forbidden_loader():
            raise AssertionError("weather notices must not load official alerts")

        service = self.make_service(
            repository=repository,
            sender=sender,
            loader=forbidden_loader,
        )
        response = service.register(
            PushDeviceRegisterRequest(
                installation_id=WEB_INSTALLATION_ID,
                registration={
                    "kind": PUSH_TARGET_FIREBASE_INSTALLATION_ID,
                    "value": WEB_FID,
                },
                platform="web",
                app_version="web-2026.08.15",
                preferences={
                    "official_alerts": False,
                    "weather_notices": True,
                },
            )
        )

        self.assertEqual(response.active_alert_delivery.status, "preference_disabled")
        self.assertTrue(repository.upserts[0]["preferences"]["weather_notices"])
        self.assertFalse(repository.upserts[0]["preferences"]["official_alerts"])
        self.assertEqual(repository.claims, {})
        self.assertEqual(sender.messages, [])

    def test_register_binds_platform_and_persists_verified_app_id(self):
        repository = FakePushRepository()
        service = self.make_service(mode="off", repository=repository)
        request = PushDeviceRegisterRequest(
            installation_id=WEB_INSTALLATION_ID,
            registration={
                "kind": PUSH_TARGET_FIREBASE_INSTALLATION_ID,
                "value": WEB_FID,
            },
            platform="web",
            app_version="web-2026.08.15",
        )
        context = PushAppCheckContext(
            claims={"app_id": "1:123:web:owner"},
            app_id="1:123:web:owner",
            platform="web",
        )

        service.register(request, app_check_context=context)

        self.assertEqual(repository.upserts[-1]["platform"], "web")
        self.assertEqual(
            repository.upserts[-1]["app_check_app_id"],
            "1:123:web:owner",
        )

        with self.assertRaises(PushPlatformNotAllowed):
            service.register(
                request,
                app_check_context=PushAppCheckContext(
                    claims={"app_id": "1:123:android:owner"},
                    app_id="1:123:android:owner",
                    platform="android",
                ),
            )

    def test_dry_run_does_not_claim_outbox_or_contact_fcm(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(
            mode="dry_run", repository=repository, sender=sender
        )

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.attempted, 1)
        self.assertEqual(repository.claims, {})
        self.assertEqual(sender.messages, [])

    def test_unofficial_or_stale_payload_fails_closed(self):
        sender = FakeSender()
        service = self.make_service(sender=sender)

        stale = service.dispatch_official_alerts(
            official_payload(cache_status="stale")
        )
        unofficial = service.dispatch_official_alerts(
            official_payload(source_id="untrusted")
        )

        self.assertEqual(stale.status, "source_unavailable")
        self.assertEqual(unofficial.status, "source_unavailable")
        self.assertEqual(sender.messages, [])

    def test_old_missing_or_future_fetched_at_fails_closed(self):
        sender = FakeSender()
        service = self.make_service(sender=sender)

        old = official_payload()
        old["fetched_at"] = (NOW - timedelta(minutes=46)).isoformat()
        missing = official_payload()
        missing.pop("fetched_at")
        future = official_payload()
        future["fetched_at"] = (NOW + timedelta(minutes=6)).isoformat()

        results = [
            service.dispatch_official_alerts(payload).status
            for payload in (old, missing, future)
        ]

        self.assertEqual(
            results,
            ["source_unavailable", "source_unavailable", "source_unavailable"],
        )
        self.assertEqual(sender.messages, [])

    def test_invalid_token_is_terminal_and_disables_device(self):
        repository = FakePushRepository()
        sender = FakeSender(error=FcmTokenInvalid("invalid"))
        service = self.make_service(repository=repository, sender=sender)

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "failed")
        self.assertEqual(repository.finished[0]["state"], "failed_invalid_token")
        self.assertEqual(repository.disabled[0]["reason"], "fcm_token_invalid")
        self.assertEqual(repository.disabled[0]["now"], NOW)

    def test_invalid_web_fid_disable_uses_kind_and_hash_cas(self):
        repository = FakePushRepository()
        repository.devices = [web_device()]
        sender = FakeSender(error=FcmTokenInvalid("invalid fid"))
        service = self.make_service(repository=repository, sender=sender)

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "failed")
        self.assertEqual(len(repository.disabled), 1)
        disable = repository.disabled[0]
        self.assertEqual(
            disable["expected_target_kind"],
            PUSH_TARGET_FIREBASE_INSTALLATION_ID,
        )
        self.assertEqual(
            disable["expected_target_hash"],
            hash_push_target(WEB_FID),
        )
        finish = repository.finished[0]
        self.assertEqual(finish["expected_claim_id"], "claim-1")
        self.assertEqual(
            finish["expected_target_kind"],
            PUSH_TARGET_FIREBASE_INSTALLATION_ID,
        )

    def test_transient_sender_failure_is_marked_retryable(self):
        repository = FakePushRepository()
        sender = FakeSender(error=FcmSenderUnavailable("unavailable"))
        service = self.make_service(repository=repository, sender=sender)

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "failed")
        self.assertEqual(repository.finished[0]["state"], "failed_transient")
        self.assertEqual(repository.disabled, [])

    def test_configuration_failure_is_reported_without_disabling_device(self):
        repository = FakePushRepository()
        sender = FakeSender(error=FcmConfigurationError("missing IAM"))
        service = self.make_service(repository=repository, sender=sender)

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "failed")
        self.assertEqual(repository.finished[0]["state"], "failed_configuration")
        self.assertEqual(repository.disabled, [])

    def test_optional_installation_hash_allowlist_is_enforced(self):
        service = self.make_service(allowed_hashes=frozenset({"f" * 64}))
        request = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
        )

        with self.assertRaises(PushInstallationNotAllowed):
            service.register(request)

    def test_dispatch_excludes_preexisting_device_outside_owner_allowlist(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(
            repository=repository,
            sender=sender,
            allowed_hashes=frozenset({"f" * 64}),
        )

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "no_eligible_devices")
        self.assertEqual(sender.messages, [])
        self.assertEqual(repository.claims, {})

    def test_pilot_test_excludes_device_outside_owner_allowlist(self):
        repository = FakePushRepository()
        service = self.make_service(
            repository=repository,
            allowed_hashes=frozenset({"f" * 64}),
        )
        with patch.dict(os.environ, {"PUSH_PILOT_TEST_MODE": "send"}, clear=False):
            with self.assertRaisesRegex(
                PushConfigurationError,
                "push_test_requires_one_device",
            ):
                service.send_pilot_test()

    def test_send_mode_requires_an_owner_installation_allowlist(self):
        with patch.dict(
            os.environ,
            {
                "PUSH_OFFICIAL_ALERTS_MODE": "send",
                "PUSH_PILOT_ENROLLMENT_MODE": "owner_allowlist",
                "PUSH_PILOT_ALLOWED_INSTALLATION_HASHES": "",
            },
            clear=True,
        ):
            with self.assertRaises(PushConfigurationError):
                PushPilotConfig.from_environment()

    def test_private_test_send_accepts_attested_android_without_hash_allowlist(self):
        with patch.dict(
            os.environ,
            {
                "PUSH_OFFICIAL_ALERTS_MODE": "send",
                "PUSH_PILOT_ENROLLMENT_MODE": "private_test",
                "PUSH_PILOT_ALLOWED_INSTALLATION_HASHES": "",
                "PUSH_PILOT_MAX_DEVICES": "10",
            },
            clear=True,
        ):
            config = PushPilotConfig.from_environment()

        self.assertEqual(config.enrollment_mode, "private_test")
        self.assertEqual(config.max_devices, 10)
        self.assertEqual(config.allowed_installation_hashes, frozenset())

    def test_private_test_rejects_conflicting_owner_allowlist(self):
        with patch.dict(
            os.environ,
            {
                "PUSH_OFFICIAL_ALERTS_MODE": "send",
                "PUSH_PILOT_ENROLLMENT_MODE": "private_test",
                "PUSH_PILOT_ALLOWED_INSTALLATION_HASHES": "f" * 64,
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                PushConfigurationError,
                "push_private_test_allowlist_conflict",
            ):
                PushPilotConfig.from_environment()

    def test_private_test_accepts_android_and_rejects_web_registration(self):
        repository = FakePushRepository()
        service = self.make_service(
            mode="send",
            repository=repository,
            max_devices=10,
            enrollment_mode="private_test",
        )
        android_request = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="3.0.0-private-test",
        )
        android_context = PushAppCheckContext(
            claims={"app_id": "1:123:android:private"},
            app_id="1:123:android:private",
            platform="android",
        )
        service.register(android_request, app_check_context=android_context)

        web_request = PushDeviceRegisterRequest(
            installation_id=WEB_INSTALLATION_ID,
            platform="web",
            app_version="3.0.0-web",
            registration={
                "kind": "firebase_installation_id",
                "value": WEB_FID,
            },
        )
        web_context = PushAppCheckContext(
            claims={"app_id": "1:123:web:public"},
            app_id="1:123:web:public",
            platform="web",
        )
        with self.assertRaisesRegex(
            PushPlatformNotAllowed,
            "push_private_test_android_only",
        ):
            service.register(web_request, app_check_context=web_context)

    def test_private_test_dispatches_only_to_android_targets(self):
        repository = FakePushRepository()
        repository.devices = [device(), web_device()]
        sender = FakeSender()
        service = self.make_service(
            repository=repository,
            sender=sender,
            max_devices=10,
            enrollment_mode="private_test",
        )

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 1)
        self.assertEqual(len(sender.messages), 1)
        self.assertEqual(sender.messages[0].platform, "android")

    def test_play_beta_configuration_accepts_release_coexistence_and_page_30(self):
        environment = {
            "PUSH_OFFICIAL_ALERTS_MODE": "dry_run",
            "PUSH_PILOT_ENROLLMENT_MODE": "play_beta",
            "PUSH_PILOT_ALLOWED_INSTALLATION_HASHES": "",
            "PUSH_ENROLLMENT_GENERATION": PLAY_BETA_GENERATION,
            "PUSH_APP_CHECK_ANDROID_APP_IDS": PLAY_ANDROID_APP_ID,
            "PUSH_APP_CHECK_WEB_APP_IDS": PLAY_WEB_APP_ID,
            "PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS": (
                f"{PLAY_BETA_APP_VERSION},{PLAY_BETA_NEXT_APP_VERSION}"
            ),
            "PUSH_PILOT_MAX_DEVICES": "30",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = PushPilotConfig.from_environment()

        self.assertEqual(config.enrollment_mode, "play_beta")
        self.assertEqual(config.enrollment_generation, PLAY_BETA_GENERATION)
        self.assertEqual(config.max_devices, 30)
        self.assertEqual(config.android_app_ids, frozenset({PLAY_ANDROID_APP_ID}))
        self.assertEqual(config.web_app_ids, frozenset({PLAY_WEB_APP_ID}))
        self.assertEqual(
            config.allowed_app_versions,
            frozenset({PLAY_BETA_APP_VERSION, PLAY_BETA_NEXT_APP_VERSION}),
        )
        without_explicit_page_size = dict(environment)
        without_explicit_page_size.pop("PUSH_PILOT_MAX_DEVICES")
        with patch.dict(os.environ, without_explicit_page_size, clear=True):
            self.assertEqual(PushPilotConfig.from_environment().max_devices, 200)
        with patch.dict(
            os.environ,
            {**environment, "PUSH_PILOT_MAX_DEVICES": "100"},
            clear=True,
        ):
            self.assertEqual(PushPilotConfig.from_environment().max_devices, 100)

        invalid_environments = (
            {**environment, "PUSH_ENROLLMENT_GENERATION": ""},
            {**environment, "PUSH_APP_CHECK_ANDROID_APP_IDS": ""},
            {**environment, "PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS": ""},
            {
                **environment,
                "PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS": "invalid version",
            },
            {
                **environment,
                "PUSH_APP_CHECK_ANDROID_APP_IDS": "1:123:web:abcdef012345",
            },
            {
                **environment,
                "PUSH_APP_CHECK_WEB_APP_IDS": "1:123:android:abcdef012345",
            },
            {**environment, "PUSH_PILOT_MAX_DEVICES": "501"},
            {
                **environment,
                "PUSH_PILOT_ALLOWED_INSTALLATION_HASHES": "f" * 64,
            },
        )
        for invalid in invalid_environments:
            with self.subTest(invalid=invalid):
                with patch.dict(os.environ, invalid, clear=True):
                    with self.assertRaises(PushConfigurationError):
                        PushPilotConfig.from_environment()

    def test_play_beta_configuration_accepts_minimum_version_code_only(self):
        environment = {
            "PUSH_OFFICIAL_ALERTS_MODE": "dry_run",
            "PUSH_PILOT_ENROLLMENT_MODE": "play_beta",
            "PUSH_ENROLLMENT_GENERATION": PLAY_BETA_GENERATION,
            "PUSH_APP_CHECK_ANDROID_APP_IDS": PLAY_ANDROID_APP_ID,
            "PUSH_APP_CHECK_WEB_APP_IDS": PLAY_WEB_APP_ID,
            "PUSH_PLAY_BETA_MIN_VERSION_CODE": "300029",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = PushPilotConfig.from_environment()
        self.assertEqual(config.min_app_version_code, 300029)
        self.assertEqual(config.allowed_app_versions, frozenset())
        for invalid in (
            {**environment, "PUSH_PLAY_BETA_MIN_VERSION_CODE": "0"},
            {**environment, "PUSH_PLAY_BETA_MIN_VERSION_CODE": "300029.0"},
            {
                **environment,
                "PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS": "0.1.12+300029",
            },
        ):
            with self.subTest(invalid=invalid):
                with patch.dict(os.environ, invalid, clear=True):
                    with self.assertRaises(PushConfigurationError):
                        PushPilotConfig.from_environment()

    def test_play_beta_minimum_allows_current_and_future_registrations(self):
        repository = FakePushRepository()
        service = self.make_service(
            mode="off",
            repository=repository,
            max_devices=100,
            enrollment_mode="play_beta",
            enrollment_generation=PLAY_BETA_GENERATION,
            android_app_ids=frozenset({PLAY_ANDROID_APP_ID}),
            min_app_version_code=300029,
        )
        context = PushAppCheckContext(
            claims={"app_id": PLAY_ANDROID_APP_ID},
            app_id=PLAY_ANDROID_APP_ID,
            platform="android",
        )
        request = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.11+300028",
        )
        with self.assertRaises(PushAppVersionNotAllowed):
            service.register(request, app_check_context=context)
        for app_version in ("0.1.12+300029", "0.1.13+300030"):
            service.register(
                request.model_copy(update={"app_version": app_version}),
                app_check_context=context,
            )
        self.assertEqual(
            [record["app_version"] for record in repository.upserts],
            ["0.1.12+300029", "0.1.13+300030"],
        )

    def test_play_beta_registration_requires_attested_android_and_is_server_scoped(self):
        repository = FakePushRepository()
        service = self.make_service(
            mode="off",
            repository=repository,
            max_devices=100,
            enrollment_mode="play_beta",
            enrollment_generation=PLAY_BETA_GENERATION,
            android_app_ids=frozenset({PLAY_ANDROID_APP_ID}),
            allowed_app_versions=frozenset({PLAY_BETA_APP_VERSION}),
        )
        request = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version=PLAY_BETA_APP_VERSION,
        )

        with self.assertRaisesRegex(
            PushPlatformNotAllowed,
            "push_play_beta_app_check_required",
        ):
            service.register(request)
        with self.assertRaisesRegex(
            PushPlatformNotAllowed,
            "push_play_beta_app_check_required",
        ):
            service.register(
                request,
                app_check_context=PushAppCheckContext(
                    claims={"app_id": "1:123:android:other"},
                    app_id="1:123:android:other",
                    platform="android",
                ),
            )

        context = PushAppCheckContext(
            claims={"app_id": PLAY_ANDROID_APP_ID},
            app_id=PLAY_ANDROID_APP_ID,
            platform="android",
        )
        old_request = request.model_copy(
            update={"app_version": "1.0.0+300010"}
        )
        with self.assertRaisesRegex(
            PushAppVersionNotAllowed,
            "push_app_version_not_allowed",
        ):
            service.register(old_request, app_check_context=context)
        service.register(request, app_check_context=context)

        persisted = repository.upserts[-1]
        self.assertEqual(persisted["enrollment_mode"], "play_beta")
        self.assertEqual(
            persisted["enrollment_generation"], PLAY_BETA_GENERATION
        )
        self.assertEqual(persisted["app_check_app_id"], PLAY_ANDROID_APP_ID)
        self.assertEqual(persisted["app_version"], PLAY_BETA_APP_VERSION)

    def test_play_beta_registers_and_dispatches_attested_web_fid(self):
        repository = FakePushRepository()
        sender = FakeSender()
        service = self.make_service(
            mode="send",
            repository=repository,
            sender=sender,
            max_devices=100,
            enrollment_mode="play_beta",
            enrollment_generation=PLAY_BETA_GENERATION,
            android_app_ids=frozenset({PLAY_ANDROID_APP_ID}),
            web_app_ids=frozenset({PLAY_WEB_APP_ID}),
            allowed_app_versions=frozenset({PLAY_BETA_APP_VERSION}),
        )
        request = PushDeviceRegisterRequest(
            installation_id=WEB_INSTALLATION_ID,
            platform="web",
            registration={
                "kind": PUSH_TARGET_FIREBASE_INSTALLATION_ID,
                "value": WEB_FID,
            },
            app_version="0.1.4",
            municipality=DEFAULT_FVG_MUNICIPALITY,
            location_mode="manual_selection",
        )
        context = PushAppCheckContext(
            claims={"app_id": PLAY_WEB_APP_ID},
            app_id=PLAY_WEB_APP_ID,
            platform="web",
        )

        registered = service.register(request, app_check_context=context)

        self.assertTrue(registered.created)
        persisted = repository.upserts[-1]
        self.assertEqual(persisted["platform"], "web")
        self.assertEqual(persisted["app_check_app_id"], PLAY_WEB_APP_ID)
        self.assertEqual(persisted["app_version"], "0.1.4")
        self.assertEqual(persisted["location_mode"], "manual_selection")
        self.assertIsNone(persisted["location_evidence"])
        self.assertEqual(len(sender.messages), 1)
        self.assertEqual(sender.messages[0].platform, "web")
        self.assertEqual(
            sender.messages[0].target_kind,
            PUSH_TARGET_FIREBASE_INSTALLATION_ID,
        )
        self.assertEqual(sender.messages[0].target_value, WEB_FID)

        unregistered = service.unregister(
            WEB_INSTALLATION_ID,
            app_check_context=context,
        )
        self.assertTrue(unregistered.unregistered)
        self.assertEqual(repository.unregistered[-1]["expected_platform"], "web")

    def test_play_beta_dispatch_excludes_legacy_wrong_generation_and_wrong_app(self):
        repository = FakePushRepository()
        current = device(
            device_id="current-device",
            token="current-fcm-token-long-enough",
            schema_version="2.1",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_ANDROID_APP_ID,
            app_version=PLAY_BETA_APP_VERSION,
        )
        repository.devices = [
            device(device_id="legacy-device"),
            device(
                device_id="old-generation",
                schema_version="2.1",
                enrollment_generation="play-beta-v0",
                app_check_app_id=PLAY_ANDROID_APP_ID,
                app_version=PLAY_BETA_APP_VERSION,
            ),
            device(
                device_id="wrong-app",
                schema_version="2.1",
                enrollment_generation=PLAY_BETA_GENERATION,
                app_check_app_id="1:123:android:other",
                app_version=PLAY_BETA_APP_VERSION,
            ),
            device(
                device_id="old-version",
                schema_version="2.1",
                enrollment_generation=PLAY_BETA_GENERATION,
                app_check_app_id=PLAY_ANDROID_APP_ID,
                app_version="1.0.0+300010",
            ),
            current,
        ]
        sender = FakeSender()
        service = self.make_service(
            repository=repository,
            sender=sender,
            max_devices=100,
            enrollment_mode="play_beta",
            enrollment_generation=PLAY_BETA_GENERATION,
            android_app_ids=frozenset({PLAY_ANDROID_APP_ID}),
            allowed_app_versions=frozenset({PLAY_BETA_APP_VERSION}),
        )

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 1)
        self.assertEqual(len(sender.messages), 1)
        self.assertEqual(repository.claim_calls[0]["device_id"], "current-device")
        self.assertEqual(
            repository.claim_calls[0]["expected_enrollment_generation"],
            PLAY_BETA_GENERATION,
        )
        self.assertEqual(
            repository.claim_calls[0]["expected_app_check_app_id"],
            PLAY_ANDROID_APP_ID,
        )
        self.assertEqual(
            repository.claim_calls[0]["expected_app_version"],
            PLAY_BETA_APP_VERSION,
        )

    def test_play_beta_dispatch_minimum_excludes_old_but_sends_to_future(self):
        repository = FakePushRepository()
        repository.devices = [
            device(
                device_id=f"version-{index}",
                token=f"version-{index}-fcm-token-long-enough",
                schema_version="2.1",
                enrollment_generation=PLAY_BETA_GENERATION,
                app_check_app_id=PLAY_ANDROID_APP_ID,
                app_version=app_version,
            )
            for index, app_version in enumerate(
                ("0.1.11+300028", "0.1.12+300029", "0.1.13+300030")
            )
        ]
        sender = FakeSender()
        service = self.make_service(
            repository=repository,
            sender=sender,
            max_devices=100,
            enrollment_mode="play_beta",
            enrollment_generation=PLAY_BETA_GENERATION,
            android_app_ids=frozenset({PLAY_ANDROID_APP_ID}),
            min_app_version_code=300029,
        )

        result = service.dispatch_official_alerts(official_payload())

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 2)
        self.assertEqual(len(sender.messages), 2)
        self.assertEqual(
            {claim["device_id"] for claim in repository.claim_calls},
            {"version-1", "version-2"},
        )

    def test_municipality_istat_and_name_must_match_canonical_fvg_catalog(self):
        repository = FakePushRepository()
        service = self.make_service(mode="off", repository=repository)
        valid = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
            municipality={"istat": "093033", "name": "Pordenone"},
        )
        service.register(valid)
        self.assertEqual(
            repository.upserts[-1]["municipality"],
            {"istat": "093033", "name": "Pordenone"},
        )

        mismatched = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
            municipality={"istat": "093033", "name": "Udine"},
        )
        with self.assertRaises(PushMunicipalityInvalid):
            service.register(mismatched)

    def test_locality_must_match_canonical_id_name_and_municipality(self):
        repository = FakePushRepository()
        service = self.make_service(mode="off", repository=repository)
        valid = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
            municipality={"istat": "093022", "name": "Fontanafredda"},
            locality={
                "id": "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.3931",
                "name": "Vigonovo",
            },
        )
        service.register(valid)
        self.assertEqual(
            repository.upserts[-1]["locality"],
            {
                "id": "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.3931",
                "name": "Vigonovo",
            },
        )

        wrong_municipality = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
            municipality={"istat": "093033", "name": "Pordenone"},
            locality={
                "id": "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.3931",
                "name": "Vigonovo",
            },
        )
        with self.assertRaises(PushLocalityInvalid):
            service.register(wrong_municipality)

        wrong_name = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
            municipality={"istat": "093022", "name": "Fontanafredda"},
            locality={
                "id": "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.3931",
                "name": "Fontanafredda",
            },
        )
        with self.assertRaises(PushLocalityInvalid):
            service.register(wrong_name)

    def test_fresh_precise_location_evidence_is_persisted_for_local_notices(self):
        repository = FakePushRepository()
        service = self.make_service(mode="off", repository=repository)
        request = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
            municipality={"istat": "093022", "name": "Fontanafredda"},
            locality={
                "id": "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.3931",
                "name": "Vigonovo",
            },
            location_mode="automatic_gps",
            location_evidence={
                "captured_at": (NOW - timedelta(seconds=30)).isoformat(),
                "accuracy_m": 24.5,
            },
        )

        response = service.register(request)

        evidence = repository.upserts[-1]["location_evidence"]
        self.assertEqual(evidence["captured_at"], NOW - timedelta(seconds=30))
        self.assertEqual(evidence["accuracy_m"], 24.5)
        self.assertEqual(evidence["received_at"], NOW)
        self.assertTrue(response.local_target_eligible)

    def test_fresh_municipality_only_target_is_eligible_without_inventing_locality(self):
        repository = FakePushRepository()
        service = self.make_service(mode="off", repository=repository)
        request = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
            municipality={"istat": "093033", "name": "Pordenone"},
            location_mode="automatic_gps",
            location_evidence={
                "captured_at": (NOW - timedelta(seconds=30)).isoformat(),
                "accuracy_m": 24.5,
            },
        )

        response = service.register(request)

        saved = repository.upserts[-1]
        self.assertEqual(
            saved["municipality"],
            {"istat": "093033", "name": "Pordenone"},
        )
        self.assertIsNone(saved["locality"])
        self.assertEqual(saved["location_mode"], "automatic_gps")
        self.assertEqual(saved["location_evidence"]["accuracy_m"], 24.5)
        self.assertTrue(response.local_target_eligible)

    def test_manual_municipality_targets_are_explicitly_eligible_without_evidence(self):
        cases = (
            ("093033", "Pordenone"),
            ("030129", "Udine"),
            ("030189", "Sappada"),
        )
        repository = FakePushRepository()
        service = self.make_service(mode="off", repository=repository)

        for istat, name in cases:
            with self.subTest(municipality=name):
                request = PushDeviceRegisterRequest(
                    installation_id=INSTALLATION_ID,
                    token="fcm-token-that-is-long-enough-for-tests",
                    platform="android",
                    app_version="0.1.0-pilot",
                    municipality={"istat": istat, "name": name},
                    location_mode="manual_selection",
                )
                response = service.register(request)

                saved = repository.upserts[-1]
                self.assertEqual(saved["municipality"], {"istat": istat, "name": name})
                self.assertIsNone(saved["locality"])
                self.assertIsNone(saved["location_evidence"])
                self.assertTrue(response.local_target_eligible)

    def test_manual_national_municipality_is_eligible_without_gps(self):
        repository = FakePushRepository()
        service = self.make_service(mode="off", repository=repository)
        request = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
            municipality={"istat": "058091", "name": "Roma"},
            location_mode="manual_selection",
        )

        response = service.register(request)

        saved = repository.upserts[-1]
        self.assertEqual(saved["municipality"], {"istat": "058091", "name": "Roma"})
        self.assertEqual(saved["location_mode"], "manual_selection")
        self.assertIsNone(saved["location_evidence"])
        self.assertTrue(response.local_target_eligible)

    def test_automatic_national_municipality_waits_for_boundary_resolver(self):
        repository = FakePushRepository()
        service = self.make_service(mode="off", repository=repository)
        request = PushDeviceRegisterRequest(
            installation_id=INSTALLATION_ID,
            token="fcm-token-that-is-long-enough-for-tests",
            platform="android",
            app_version="0.1.0-pilot",
            municipality={"istat": "058091", "name": "Roma"},
            location_mode="automatic_gps",
            location_evidence={
                "captured_at": (NOW - timedelta(seconds=30)).isoformat(),
                "accuracy_m": 24.5,
            },
        )

        response = service.register(request)

        saved = repository.upserts[-1]
        self.assertEqual(saved["municipality"], {"istat": "058091", "name": "Roma"})
        self.assertIsNone(saved["location_mode"])
        self.assertIsNone(saved["location_evidence"])
        self.assertFalse(response.local_target_eligible)

    def test_stale_or_future_location_evidence_degrades_only_local_targeting(self):
        repository = FakePushRepository()
        service = self.make_service(mode="off", repository=repository)
        for captured_at in (
            NOW - timedelta(minutes=11),
            NOW + timedelta(minutes=3),
            NOW.replace(tzinfo=None),
        ):
            with self.subTest(captured_at=captured_at):
                request = PushDeviceRegisterRequest(
                    installation_id=INSTALLATION_ID,
                    token="fcm-token-that-is-long-enough-for-tests",
                    platform="android",
                    app_version="0.1.0-pilot",
                    municipality={"istat": "093022", "name": "Fontanafredda"},
                    locality={
                        "id": "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.3931",
                        "name": "Vigonovo",
                    },
                    location_mode="automatic_gps",
                    location_evidence={
                        "captured_at": captured_at.isoformat(),
                        "accuracy_m": 25,
                    },
                )
                response = service.register(request)

                saved = repository.upserts[-1]
                self.assertEqual(
                    saved["municipality"],
                    {"istat": "093022", "name": "Fontanafredda"},
                )
                self.assertEqual(saved["locality"]["name"], "Vigonovo")
                self.assertIsNone(saved["location_mode"])
                self.assertIsNone(saved["location_evidence"])
                self.assertFalse(response.local_target_eligible)

    def test_configuration_defaults_off_and_rejects_invalid_values(self):
        with patch.dict(os.environ, {}, clear=True):
            config = PushPilotConfig.from_environment()
            self.assertEqual(config.mode, "off")
            self.assertEqual(config.enrollment_mode, "owner_allowlist")
        with patch.dict(os.environ, {"PUSH_OFFICIAL_ALERTS_MODE": "typo"}, clear=True):
            with self.assertRaises(PushConfigurationError):
                PushPilotConfig.from_environment()
        with patch.dict(os.environ, {"PUSH_PILOT_ENROLLMENT_MODE": "public"}, clear=True):
            with self.assertRaises(PushConfigurationError):
                PushPilotConfig.from_environment()

    def test_pilot_test_requires_both_explicit_send_switches(self):
        service = self.make_service(mode="send")
        with patch.dict(os.environ, {"PUSH_PILOT_TEST_MODE": "off"}, clear=False):
            with self.assertRaises(PushConfigurationError):
                service.send_pilot_test()


if __name__ == "__main__":
    unittest.main()
