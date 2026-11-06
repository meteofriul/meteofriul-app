from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from app.push.fcm import FcmBatchOutcome
from app.jobs import send_morning_forecast
from app.services.local_notice_delivery import LocalNoticeDeliveryConfig
from app.services.location import LocationCatalog
from app.services.morning_forecast_delivery import (
    MorningForecastConfigurationError,
    MorningForecastDeliveryService,
    build_morning_forecast_body,
)
from app.services.notice_municipalities import NoticeMunicipalityCatalog


NOW = datetime(2026, 9, 29, 5, 30, tzinfo=timezone.utc)
APP_ID = "1:49007668366:android:725bf6f8b339177a852ddf"
APP_VERSION = "0.1.8+300025"


def config(*, mode: str = "send") -> LocalNoticeDeliveryConfig:
    return LocalNoticeDeliveryConfig(
        mode=mode,
        allowed_installation_hash="",
        retention_days=14,
        source_timeout_seconds=15.0,
        max_devices=200,
        enrollment_mode="play_beta",
        enrollment_generation="play-beta-v1",
        allowed_app_ids=frozenset({APP_ID}),
        web_app_ids=frozenset(),
        allowed_app_versions=frozenset({APP_VERSION}),
    )


def device(*, device_id: str = "a" * 64, token: str = "token-a") -> dict:
    return {
        "schema_version": "2.1",
        "device_id": device_id,
        "target_kind": "fcm_token",
        "target_value": token,
        "target_hash": "",
        "active": True,
        "platform": "android",
        "enrollment_generation": "play-beta-v1",
        "app_check_app_id": APP_ID,
        "app_version": APP_VERSION,
        "municipality": {"istat": "093033", "name": "Pordenone"},
        "locality": None,
        "location_mode": "manual_selection",
        "location_evidence": None,
        "preferences": {
            "official_alerts": True,
            "weather_notices": True,
        },
    }


def snapshot() -> dict:
    local_zone = ZoneInfo("Europe/Rome")
    first = datetime(2026, 9, 29, 8, 0, tzinfo=local_zone)
    temperatures = [12, 13, 15, 18, 21, 23, 24, 25, 24, 22, 20, 18]
    count = len(temperatures)
    precipitation = [0.0] * count
    rain = [0.0] * count
    codes = [0] * count
    precipitation[6] = 1.5
    rain[6] = 1.5
    codes[6] = 61
    return {
        "hourly": {
            "time": [
                (first + timedelta(hours=index)).isoformat(timespec="minutes")
                for index in range(count)
            ],
            "temperature_2m": temperatures,
            "precipitation": precipitation,
            "rain": rain,
            "showers": [0.0] * count,
            "weather_code": codes,
        }
    }


class FakeDeviceRepository:
    def __init__(self, devices, *, claim_state: str = "sending") -> None:
        self.devices = deepcopy(devices)
        self.claim_state = claim_state
        self.claims = []
        self.finishes = []
        self.disabled = []

    def read_active_devices(self, *, max_devices, enrollment_generation=None):
        values = [
            value
            for value in self.devices
            if enrollment_generation is None
            or value.get("enrollment_generation") == enrollment_generation
        ]
        return SimpleNamespace(devices=deepcopy(values), pages_processed=1)

    def claim_local_notice_delivery(self, **kwargs):
        self.claims.append(kwargs)
        claimed = self.claim_state == "sending"
        return SimpleNamespace(
            claimed=claimed,
            state=self.claim_state,
            delivery_id="delivery-id",
            claim_id="claim-id" if claimed else "",
        )

    def finish_local_notice_delivery(self, **kwargs):
        self.finishes.append(kwargs)
        return True

    def disable_device(self, **kwargs):
        self.disabled.append(kwargs)
        return True


class FakeSource:
    def __init__(self, value) -> None:
        self.value = deepcopy(value)
        self.calls = []

    def fetch(self, municipality, locality=None):
        self.calls.append((municipality, locality))
        return deepcopy(self.value)


class FakeSender:
    def __init__(self) -> None:
        self.messages = []

    def send_batch(self, messages):
        self.messages.extend(messages)
        return [
            FcmBatchOutcome(message_id=f"message-{index}")
            for index, _ in enumerate(messages, start=1)
        ]


class MorningForecastCopyTests(unittest.TestCase):
    def test_builds_requested_compact_pordenone_copy(self):
        municipality = LocationCatalog().match_istat("093033")

        body = build_morning_forecast_body(
            snapshot(),
            municipality,
            now=NOW,
        )

        self.assertEqual(
            body,
            "Pordenone: cielo sereno, 12 °C. Massima 25 °C; "
            "possibili piogge dal pomeriggio.",
        )


class MorningForecastDeliveryTests(unittest.TestCase):
    def service(
        self,
        repository,
        source,
        sender,
        *,
        require_single=True,
        test_run_id="",
        test_platform="",
    ):
        return MorningForecastDeliveryService(
            device_repository=repository,
            source=source,
            sender=sender,
            config=config(),
            require_single_target=require_single,
            test_run_id=test_run_id,
            test_platform=test_platform,
            location_catalog=NoticeMunicipalityCatalog(),
            now=lambda: NOW,
        )

    def test_sends_one_deduplicated_morning_message_on_existing_channel(self):
        repository = FakeDeviceRepository([device()])
        source = FakeSource(snapshot())
        sender = FakeSender()

        result = self.service(repository, source, sender).run()

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 1)
        self.assertEqual(result.delivery_batches, 1)
        self.assertEqual(len(sender.messages), 1)
        message = sender.messages[0]
        self.assertEqual(message.title, "Meteo Friûl")
        self.assertEqual(message.channel_id, "mf_weather_notices_v1")
        self.assertEqual(message.collapse_key, "mf-morning-forecast")
        self.assertEqual(message.notification_tag, "mf-morning-forecast")
        self.assertEqual(message.data["kind"], "morning_forecast")
        self.assertEqual(message.data["tab"], "bulletin")
        self.assertEqual(message.data["forecast_date"], "2026-09-29")
        self.assertEqual(repository.claims[0]["notice_kind"], "morning_forecast")
        self.assertEqual(len(repository.claims[0]["notice_signature"]), 64)
        self.assertEqual(repository.finishes[0]["state"], "sent")

    def test_existing_daily_claim_is_not_sent_twice(self):
        repository = FakeDeviceRepository([device()], claim_state="sent")
        sender = FakeSender()

        result = self.service(
            repository,
            FakeSource(snapshot()),
            sender,
        ).run()

        self.assertEqual(result.status, "deduplicated")
        self.assertEqual(result.deduplicated, 1)
        self.assertEqual(sender.messages, [])

    def test_saved_canonical_municipality_remains_eligible_without_location_mode(self):
        saved = device()
        saved["location_mode"] = ""
        saved["location_evidence"] = None
        repository = FakeDeviceRepository([saved])
        sender = FakeSender()

        result = self.service(
            repository,
            FakeSource(snapshot()),
            sender,
            test_run_id="saved-municipality",
            test_platform="android",
        ).run()

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.eligible_devices, 1)
        self.assertEqual(len(sender.messages), 1)
        self.assertTrue(
            repository.claims[0]["allow_saved_municipality_without_mode"]
        )

    def test_single_target_guard_fails_closed_before_fetch_or_send(self):
        repository = FakeDeviceRepository(
            [
                device(),
                device(device_id="b" * 64, token="token-b"),
            ]
        )
        source = FakeSource(snapshot())
        sender = FakeSender()

        result = self.service(repository, source, sender).run()

        self.assertEqual(result.status, "target_count_invalid")
        self.assertEqual(result.failed, 1)
        self.assertEqual(source.calls, [])
        self.assertEqual(sender.messages, [])

    def test_single_target_test_run_ids_create_distinct_delivery_claims(self):
        repository_one = FakeDeviceRepository([device()])
        repository_two = FakeDeviceRepository([device()])

        first = self.service(
            repository_one,
            FakeSource(snapshot()),
            FakeSender(),
            test_run_id="foreground",
        ).run()
        second = self.service(
            repository_two,
            FakeSource(snapshot()),
            FakeSender(),
            test_run_id="background",
        ).run()

        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "sent")
        self.assertNotEqual(
            repository_one.claims[0]["notice_signature"],
            repository_two.claims[0]["notice_signature"],
        )

    def test_test_run_id_is_rejected_without_single_target_guard(self):
        with self.assertRaises(MorningForecastConfigurationError):
            self.service(
                FakeDeviceRepository([device()]),
                FakeSource(snapshot()),
                FakeSender(),
                require_single=False,
                test_run_id="unsafe",
            )

    def test_test_platform_filters_out_web_target_before_single_target_guard(self):
        web_device = device(device_id="b" * 64, token="web-installation")
        web_device.update(
            {
                "app_check_app_id": "1:49007668366:web:test",
                "app_version": "",
                "platform": "web",
                "target_kind": "firebase_installation_id",
            }
        )
        guarded_config = config()
        guarded_config = LocalNoticeDeliveryConfig(
            **{
                **guarded_config.__dict__,
                "web_app_ids": frozenset({"1:49007668366:web:test"}),
            }
        )
        repository = FakeDeviceRepository([device(), web_device])
        source = FakeSource(snapshot())
        sender = FakeSender()
        service = MorningForecastDeliveryService(
            device_repository=repository,
            source=source,
            sender=sender,
            config=guarded_config,
            require_single_target=True,
            test_run_id="android-only",
            test_platform="android",
            location_catalog=NoticeMunicipalityCatalog(),
            now=lambda: NOW,
        )

        result = service.run()

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.eligible_devices, 1)
        self.assertEqual(len(sender.messages), 1)
        self.assertEqual(sender.messages[0].platform, "android")


class MorningForecastRetirementTests(unittest.TestCase):
    def service(self, repository, sender, *, source=None):
        return MorningForecastDeliveryService(
            device_repository=repository,
            source=source or FakeSource(snapshot()),
            sender=sender,
            config=config(),
            require_single_target=False,
            location_catalog=NoticeMunicipalityCatalog(),
            now=lambda: NOW,
        )

    def job_exit(self, result):
        output = io.StringIO()
        with patch.object(
            send_morning_forecast,
            "get_morning_forecast_delivery_service",
            return_value=SimpleNamespace(run=lambda: result),
        ), redirect_stdout(output):
            exit_code = send_morning_forecast.main()
        return exit_code, json.loads(output.getvalue()), output.getvalue()

    def test_only_confirmed_invalid_token_is_retired_without_job_failure(self):
        repository = FakeDeviceRepository([device()])
        sender = FakeSender()
        sender.send_batch = Mock(return_value=[FcmBatchOutcome(error_code="fcm_token_invalid")])

        result = self.service(repository, sender).run()
        exit_code, summary, raw = self.job_exit(result)

        self.assertEqual((result.status, result.sent, result.retired_targets, result.failed),
                         ("retired_targets", 0, 1, 0))
        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["retired_targets"], 1)
        self.assertEqual(len(repository.disabled), 1)
        self.assertNotIn("token-a", raw)

    def test_54_sends_and_one_confirmed_retirement_keep_job_successful(self):
        devices = [device(device_id=f"{index + 1:064x}", token=f"token-{index}")
                   for index in range(55)]
        repository = FakeDeviceRepository(devices)
        sender = FakeSender()
        sender.send_batch = Mock(return_value=[
            *[FcmBatchOutcome(message_id=f"message-{index}") for index in range(54)],
            FcmBatchOutcome(error_code="fcm_token_invalid"),
        ])

        result = self.service(repository, sender).run()
        exit_code, summary, _ = self.job_exit(result)

        self.assertEqual((result.status, result.sent, result.retired_targets, result.failed),
                         ("sent", 54, 1, 0))
        self.assertEqual((summary["eligible_devices"], summary["attempted"]), (55, 55))
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(repository.disabled), 1)

    def test_transient_fcm_and_source_errors_still_fail_the_job(self):
        repository = FakeDeviceRepository([device()])
        sender = FakeSender()
        sender.send_batch = Mock(return_value=[FcmBatchOutcome(error_code="fcm_sender_unavailable")])
        transient = self.service(repository, sender).run()
        self.assertEqual((transient.status, transient.device_failed, transient.retired_targets),
                         ("failed", 1, 0))
        self.assertEqual(self.job_exit(transient)[0], 1)
        self.assertEqual(repository.disabled, [])

        source_failure = self.service(
            FakeDeviceRepository([device()]), FakeSender(), source=FakeSource({})
        ).run()
        self.assertEqual((source_failure.status, source_failure.source_failed,
                          source_failure.retired_targets), ("failed", 1, 0))
        self.assertEqual(self.job_exit(source_failure)[0], 1)

    def test_unconfirmed_invalid_token_cleanup_still_fails_the_job(self):
        for unconfirmed_step in ("finish", "disable"):
            with self.subTest(unconfirmed_step=unconfirmed_step):
                repository = FakeDeviceRepository([device()])
                if unconfirmed_step == "finish":
                    repository.finish_local_notice_delivery = Mock(return_value=False)
                else:
                    repository.disable_device = Mock(return_value=False)
                sender = FakeSender()
                sender.send_batch = Mock(return_value=[
                    FcmBatchOutcome(error_code="fcm_token_invalid")
                ])

                result = self.service(repository, sender).run()
                self.assertEqual((result.status, result.retired_targets, result.failed),
                                 ("failed", 0, 1))
                self.assertEqual(self.job_exit(result)[0], 1)
                if unconfirmed_step == "finish":
                    self.assertEqual(repository.disabled, [])


if __name__ == "__main__":
    unittest.main()
