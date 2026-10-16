import unittest
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app.push.fcm import (
    DEFAULT_ANDROID_NATIONAL_ALERT_CHANNEL,
    FcmBatchOutcome,
    FcmSenderUnavailable,
)
from app.repositories.national_alert_delivery import (
    PUSH_NATIONAL_ALERT_OUTBOX_COLLECTION,
    NationalAlertOutboxRepository,
)
from app.repositories.push import (
    PUSH_DEVICES_COLLECTION,
    PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION,
    PUSH_OUTBOX_COLLECTION,
    PushDeviceRepository,
    PushRepositoryUnavailable,
    hash_push_target,
)
from app.services.national_alert_delivery import (
    NationalAlertDeliveryConfig,
    NationalAlertDeliveryService,
    NationalAlertDeliveryUnavailable,
    prepare_national_alerts,
)
from app.services.national_alert_push_dry_run import (
    NationalAlertDryRunPolicy,
    NationalAlertCandidate,
    NationalAlertDryRunUnavailable,
)
from tests.test_national_official_alerts import NOW, reconciled_snapshot
from tests.test_push_repository import FakeFirestore, fake_transactional


APP_ID = "1:49007668366:android:725bf6f8b339177a852ddf"
DEVICE_ID = "national-test-device"
TOKEN = "national-test-token"
POLICY = NationalAlertDryRunPolicy(
    enrollment_generation="play-beta-v1",
    android_app_ids=frozenset({APP_ID}),
    min_app_version_code=300030,
)


def device(**overrides):
    return {
        "schema_version": "2.1",
        "device_id": DEVICE_ID,
        "active": True,
        "platform": "android",
        "enrollment_generation": "play-beta-v1",
        "app_check_app_id": APP_ID,
        "app_version": "0.1.13+300030",
        "location_mode": "manual_selection",
        "municipality": {"istat": "041067", "name": "Urbino"},
        "preferences": {"official_alerts": True, "weather_notices": False},
        "target_kind": "fcm_token",
        "target_value": TOKEN,
        "target_hash": hash_push_target(TOKEN),
        "language": "it",
    } | overrides


def claim_kwargs(**overrides):
    return {
        "device_id": DEVICE_ID,
        "alert_signature": "a" * 64,
        "forecast_day": "2026-09-24",
        "level": "yellow",
        "source_revision": "20260924_1400",
        "target_hash": hash_push_target(TOKEN),
        "municipality_istat": "041067",
        "municipality_name": "Urbino",
        "enrollment_generation": "play-beta-v1",
        "app_check_app_id": APP_ID,
        "app_version": "0.1.13+300030",
        "min_app_version_code": 300030,
        "now": NOW,
    } | overrides


class FakeSender:
    def __init__(self, error=""):
        self.calls = []
        self.error = error

    def send_batch(self, messages):
        self.calls.append(messages)
        if self.error == "unavailable":
            raise FcmSenderUnavailable("fcm_sender_unavailable")
        if self.error:
            return [FcmBatchOutcome(error_code=self.error) for _ in messages]
        return [FcmBatchOutcome(message_id=f"fcm-{index}") for index in range(len(messages))]


class NationalAlertOutboxTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeFirestore()
        self.db.collection(PUSH_DEVICES_COLLECTION).records[DEVICE_ID] = device()
        self.repository = NationalAlertOutboxRepository(
            lambda: self.db,
            transactional_decorator=fake_transactional,
        )

    def test_claim_and_finish_are_isolated_and_deduplicated(self):
        claimed = self.repository.claim(**claim_kwargs())
        duplicate = self.repository.claim(**claim_kwargs())

        self.assertTrue(claimed.claimed)
        self.assertEqual(duplicate.state, "delivery_in_progress")
        self.assertEqual(len(self.db.collection(PUSH_NATIONAL_ALERT_OUTBOX_COLLECTION).records), 1)
        self.assertEqual(self.db.collection(PUSH_OUTBOX_COLLECTION).records, {})
        self.assertEqual(self.db.collection(PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION).records, {})
        self.assertFalse(self.repository.finish(
            delivery_id=claimed.delivery_id,
            claim_id="wrong",
            target_hash=hash_push_target(TOKEN),
            state="sent",
            now=NOW,
        ))
        self.assertTrue(self.repository.finish(
            delivery_id=claimed.delivery_id,
            claim_id=claimed.claim_id,
            target_hash=hash_push_target(TOKEN),
            state="sent",
            now=NOW,
        ))
        self.assertEqual(self.repository.claim(**claim_kwargs()).state, "sent")

    def test_live_revocation_location_change_and_version_downgrade_block_claim(self):
        stored = self.db.collection(PUSH_DEVICES_COLLECTION).records[DEVICE_ID]
        for patch, expected in (
            ({"preferences": {"official_alerts": False}}, "preference_disabled"),
            ({"location_mode": "automatic_gps"}, "municipality_changed"),
            ({"municipality": {"istat": "058091", "name": "Roma"}}, "municipality_changed"),
            ({"app_version": "0.1.12+300029"}, "app_version_changed"),
            ({"app_check_app_id": "other"}, "play_policy_changed"),
            ({"target_hash": "b" * 64}, "device_target_changed"),
        ):
            with self.subTest(expected=expected):
                stored.clear()
                stored.update(device() | patch)
                self.assertEqual(self.repository.claim(**claim_kwargs()).state, expected)
                self.assertEqual(self.db.collection(PUSH_NATIONAL_ALERT_OUTBOX_COLLECTION).records, {})

    def test_expired_sending_lease_is_uncertain_and_never_automatically_retried(self):
        first = self.repository.claim(**claim_kwargs())
        second = self.repository.claim(**claim_kwargs(now=NOW + timedelta(minutes=16)))
        self.assertTrue(first.claimed)
        self.assertFalse(second.claimed)
        self.assertEqual(second.state, "delivery_uncertain")

    def test_known_transient_failure_retries_only_after_delay(self):
        first = self.repository.claim(**claim_kwargs())
        self.repository.finish(
            delivery_id=first.delivery_id,
            claim_id=first.claim_id,
            target_hash=hash_push_target(TOKEN),
            state="failed_transient",
            now=NOW,
            error_code="fcm_sender_unavailable",
        )
        self.assertEqual(self.repository.claim(**claim_kwargs()).state, "retry_scheduled")
        retry = self.repository.claim(**claim_kwargs(now=NOW + timedelta(minutes=16)))
        self.assertTrue(retry.claimed)
        self.assertNotEqual(retry.claim_id, first.claim_id)

    def test_firestore_failure_is_not_treated_as_no_candidate(self):
        self.db.fail_reads = True
        with self.assertRaisesRegex(PushRepositoryUnavailable, "claim_failed"):
            self.repository.claim(**claim_kwargs())


class NationalAlertDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeFirestore()
        self.db.collection(PUSH_DEVICES_COLLECTION).records[DEVICE_ID] = device()
        self.sender = FakeSender()
        self.snapshot = reconciled_snapshot()
        self.storage = "firestore"
        self.now = NOW

    def service(self, mode="send", cap=10):
        return NationalAlertDeliveryService(
            snapshot_repository=SimpleNamespace(load=lambda: (self.snapshot, self.storage)),
            device_repository=PushDeviceRepository(
                lambda: self.db, transactional_decorator=fake_transactional,
            ),
            outbox_repository=NationalAlertOutboxRepository(
                lambda: self.db, transactional_decorator=fake_transactional,
            ),
            sender=self.sender,
            config=NationalAlertDeliveryConfig(
                mode=mode,
                policy=POLICY if mode != "off" else None,
                page_size=10 if mode != "off" else 0,
                send_max_devices=cap if mode == "send" else 0,
            ),
            now=lambda: self.now,
            expected_zone_count=100,
        )

    def test_off_and_dry_run_never_claim_or_send(self):
        self.assertEqual(self.service("off").run(), {
            "status": "disabled", "sent": 0, "outbox_writes": 0,
        })
        summary = self.service("dry_run").run()
        self.assertEqual(summary["candidate_status"], "candidate")
        self.assertEqual(summary["candidate_devices"], 1)
        self.assertEqual(summary["sent"], 0)
        self.assertEqual(self.sender.calls, [])
        self.assertEqual(self.db.collection(PUSH_NATIONAL_ALERT_OUTBOX_COLLECTION).records, {})

    def test_sends_once_on_distinct_channel_and_same_alert_is_deduplicated(self):
        first = self.service().run()
        second = self.service().run()

        self.assertEqual(first["status"], "sent")
        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["status"], "deduplicated")
        self.assertEqual(second["sent"], 0)
        self.assertEqual(len(self.sender.calls), 1)
        message = self.sender.calls[0][0]
        self.assertEqual(message.channel_id, DEFAULT_ANDROID_NATIONAL_ALERT_CHANNEL)
        self.assertEqual(message.data["type"], "national_official_alert")
        self.assertEqual(message.data["municipality_istat"], "041067")
        self.assertIn("Urbino", message.body)
        self.assertNotIn(TOKEN, str(first))
        self.assertEqual(self.db.collection(PUSH_OUTBOX_COLLECTION).records, {})

    def test_fvg_old_play_and_web_devices_never_become_national_recipients(self):
        collection = self.db.collection(PUSH_DEVICES_COLLECTION).records
        collection[DEVICE_ID] = device(municipality={"istat": "093033", "name": "Pordenone"})
        collection["old"] = device(
            device_id="old", target_value="old-token", target_hash=hash_push_target("old-token"),
            app_version="0.1.12+300029",
        )
        collection["web"] = device(
            device_id="web", platform="web", target_kind="firebase_installation_id",
            target_value="web-fid", target_hash=hash_push_target("web-fid"),
        )
        result = self.service().run()

        self.assertEqual(result["status"], "no_candidate")
        self.assertEqual(result["candidate_devices"], 0)
        self.assertEqual(self.sender.calls, [])

    def test_revocation_between_listing_and_claim_prevents_delivery(self):
        service = self.service()
        actual_claim = service._outbox_repository.claim

        def revoke_then_claim(**kwargs):
            self.db.collection(PUSH_DEVICES_COLLECTION).records[DEVICE_ID]["preferences"] = {
                "official_alerts": False,
            }
            return actual_claim(**kwargs)

        service._outbox_repository.claim = revoke_then_claim
        result = service.run()

        self.assertEqual(result["opted_out"], 1)
        self.assertEqual(result["sent"], 0)
        self.assertEqual(self.sender.calls, [])

    def test_invalid_or_nonpersistent_snapshot_fails_before_any_write(self):
        self.storage = "memory_fallback"
        with self.assertRaises(NationalAlertDryRunUnavailable):
            self.service().run()
        self.assertEqual(self.db.collection(PUSH_NATIONAL_ALERT_OUTBOX_COLLECTION).records, {})
        self.assertEqual(self.sender.calls, [])

    def test_audience_cap_fails_before_claiming_any_delivery(self):
        with self.assertRaisesRegex(NationalAlertDeliveryUnavailable, "audience_cap_exceeded"):
            self.service(cap=0).run()
        self.assertEqual(self.db.collection(PUSH_NATIONAL_ALERT_OUTBOX_COLLECTION).records, {})

    def test_fcm_failure_is_visible_and_retry_is_delayed(self):
        self.sender.error = "unavailable"
        first = self.service().run()
        second = self.service().run()
        self.assertEqual(first["status"], "failed")
        self.assertEqual(first["failed"], 1)
        self.assertEqual(second["status"], "in_progress")
        self.assertEqual(len(self.sender.calls), 1)

    def test_unchanged_revision_does_not_affect_content_signature(self):
        candidate = NationalAlertCandidate(
            device=device(), municipality_istat="041067", municipality_name="Urbino",
            target_kind="fcm_token", target_value=TOKEN, target_hash=hash_push_target(TOKEN),
            projection={}, active_records=({
                "forecast_day": "2026-09-24", "zone_id": "DPC:Marc-2",
                "risk": "thunderstorm", "level": "yellow",
                "valid_to": "2026-09-24T23:59:59+02:00",
            },),
        )
        original = prepare_national_alerts(candidate)[0]
        revised = prepare_national_alerts(deepcopy(candidate))[0]
        self.assertEqual(original.signature, revised.signature)


class NationalAlertConfigTests(unittest.TestCase):
    def test_off_needs_no_fvg_or_firebase_settings(self):
        with patch.dict("os.environ", {"NATIONAL_OFFICIAL_ALERTS_PUSH_MODE": "off"}):
            self.assertEqual(NationalAlertDeliveryConfig.from_environment().mode, "off")

    def test_send_requires_separate_gate_cap_and_new_play_version_floor(self):
        base = SimpleNamespace(
            enrollment_mode="play_beta", enrollment_generation="play-beta-v1",
            android_app_ids=frozenset({APP_ID}), min_app_version_code=300029,
            max_devices=100,
        )
        env = {
            "NATIONAL_OFFICIAL_ALERTS_PUSH_MODE": "send",
            "NATIONAL_OFFICIAL_ALERTS_MIN_VERSION_CODE": "300030",
            "NATIONAL_OFFICIAL_ALERTS_SEND_MAX_DEVICES": "10",
        }
        with patch("app.services.national_alert_delivery.PushPilotConfig.from_environment", return_value=base):
            with patch.dict("os.environ", env, clear=True):
                with self.assertRaisesRegex(NationalAlertDeliveryUnavailable, "send_gate_closed"):
                    NationalAlertDeliveryConfig.from_environment()
                env["NATIONAL_OFFICIAL_ALERTS_SEND_GATE"] = "confirmed"
                with patch.dict("os.environ", env, clear=True):
                    config = NationalAlertDeliveryConfig.from_environment()
                    self.assertEqual(config.send_max_devices, 10)
                    self.assertEqual(config.policy.min_app_version_code, 300030)
                env["NATIONAL_OFFICIAL_ALERTS_MIN_VERSION_CODE"] = "300029"
                with patch.dict("os.environ", env, clear=True):
                    with self.assertRaisesRegex(NationalAlertDeliveryUnavailable, "min_version_invalid"):
                        NationalAlertDeliveryConfig.from_environment()


if __name__ == "__main__":
    unittest.main()
