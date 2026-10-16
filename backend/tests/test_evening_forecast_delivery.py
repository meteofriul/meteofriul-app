from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.push.fcm import FcmBatchOutcome
from app.services.evening_forecast_delivery import (
    EveningForecastConfigurationError,
    EveningForecastDeliveryService,
    build_evening_forecast_contents,
)
from app.services.local_notice_delivery import LocalNoticeDeliveryConfig
from app.services.location import LocationCatalog
from app.services.notice_municipalities import NoticeMunicipalityCatalog


LOCAL_ZONE = ZoneInfo("Europe/Rome")
NOW = datetime(2026, 9, 29, 18, 45, tzinfo=timezone.utc)
TOMORROW = NOW.astimezone(LOCAL_ZONE).date() + timedelta(days=1)
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


def device(
    *,
    device_id: str = "a" * 64,
    token: str = "token-a",
    language: str = "it",
) -> dict:
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
        "language": language,
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
    first = datetime(2026, 9, 29, 21, 0, tzinfo=LOCAL_ZONE)
    count = 36
    return {
        "source_run_id": "20260929T120000Z",
        "hourly": {
            "time": [
                (first + timedelta(hours=index)).isoformat(timespec="minutes")
                for index in range(count)
            ],
            "temperature_2m": [18.0] * count,
            "precipitation": [0.0] * count,
            "rain": [0.0] * count,
            "showers": [0.0] * count,
            "snowfall": [0.0] * count,
            "weather_code": [0] * count,
            "wind_gusts_10m": [12.0] * count,
        }
    }


def tomorrow_index(value: dict, hour: int) -> int:
    for index, raw in enumerate(value["hourly"]["time"]):
        parsed = datetime.fromisoformat(raw).astimezone(LOCAL_ZONE)
        if parsed.date() == TOMORROW and parsed.hour == hour:
            return index
    raise AssertionError(f"missing tomorrow hour {hour}")


class FakeDeviceRepository:
    def __init__(self, devices, *, claim_state: str = "sending") -> None:
        self.devices = deepcopy(devices)
        self.claim_state = claim_state
        self.claims = []
        self.finishes = []

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


class EveningForecastCopyTests(unittest.TestCase):
    def contents(self, value):
        municipality = LocationCatalog().match_istat("093033")
        return build_evening_forecast_contents(
            value,
            municipality,
            now=NOW,
        )

    def assert_bodies(self, value, italian, friulian):
        contents = self.contents(value)
        self.assertEqual(contents["it"].title, "Domani a Pordenone")
        self.assertEqual(contents["fur"].title, "Doman a Pordenone")
        self.assertEqual(contents["it"].body, italian)
        self.assertEqual(contents["fur"].body, friulian)

    def test_sunny_day(self):
        self.assert_bodies(
            snapshot(),
            "Giornata soleggiata. Apri e guarda.",
            "Zornade di soreli. Vierç e cjale.",
        )

    def test_rain_from_afternoon(self):
        value = snapshot()
        index = tomorrow_index(value, 13)
        value["hourly"]["weather_code"][index] = 61
        value["hourly"]["precipitation"][index] = 1.5
        value["hourly"]["rain"][index] = 1.5
        self.assert_bodies(
            value,
            "Pioggia dal pomeriggio. Apri e guarda.",
            "Ploie dal dopomisdì. Vierç e cjale.",
        )

    def test_cloudy_with_possible_clearings(self):
        value = snapshot()
        for hour in range(7, 17):
            value["hourly"]["weather_code"][tomorrow_index(value, hour)] = 3
        self.assert_bodies(
            value,
            "Nuvoloso, possibili schiarite. Apri e guarda.",
            "Nulât, pussibilis sclaridis. Vierç e cjale.",
        )

    def test_strong_wind_in_evening(self):
        value = snapshot()
        value["hourly"]["wind_gusts_10m"][tomorrow_index(value, 20)] = 75.0
        self.assert_bodies(
            value,
            "Vento forte in serata. Apri e guarda.",
            "Aiar fuart in serade. Vierç e cjale.",
        )

    def test_hazard_priority_and_friulian_variants(self):
        cases = (
            (
                95,
                "precipitation",
                "Temporali in mattinata. Apri e guarda.",
                "Temporâi di matine. Vierç e cjale.",
            ),
            (
                66,
                "precipitation",
                "Pioggia gelata in mattinata. Apri e guarda.",
                "Ploie glaçade di matine. Vierç e cjale.",
            ),
            (
                73,
                "snowfall",
                "Neve in mattinata. Apri e guarda.",
                "Nêf di matine. Vierç e cjale.",
            ),
        )
        for code, amount_field, italian, friulian in cases:
            with self.subTest(code=code):
                value = snapshot()
                index = tomorrow_index(value, 9)
                value["hourly"]["weather_code"][index] = code
                value["hourly"][amount_field][index] = 1.0
                self.assert_bodies(value, italian, friulian)

    def test_rejects_partial_tomorrow_coverage(self):
        value = snapshot()
        for key, series in value["hourly"].items():
            value["hourly"][key] = series[:15]

        self.assertEqual(self.contents(value), {})

    def test_rejects_the_previous_morning_model_run(self):
        value = snapshot()
        value["source_run_id"] = "20260929T000000Z"

        self.assertEqual(self.contents(value), {})


class EveningForecastDeliveryTests(unittest.TestCase):
    def service(
        self,
        repository,
        source,
        sender,
        *,
        require_single=True,
        test_run_id="",
        test_installation_hash="",
    ):
        return EveningForecastDeliveryService(
            device_repository=repository,
            source=source,
            sender=sender,
            config=config(),
            require_single_target=require_single,
            test_run_id=test_run_id,
            test_installation_hash=test_installation_hash,
            location_catalog=NoticeMunicipalityCatalog(),
            now=lambda: NOW,
        )

    def test_sends_localized_next_day_message_on_existing_channel(self):
        value = snapshot()
        index = tomorrow_index(value, 13)
        value["hourly"]["weather_code"][index] = 61
        value["hourly"]["precipitation"][index] = 1.0
        value["hourly"]["rain"][index] = 1.0
        repository = FakeDeviceRepository([device(language="fur")])
        sender = FakeSender()

        result = self.service(repository, FakeSource(value), sender).run()

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 1)
        message = sender.messages[0]
        self.assertEqual(message.title, "Doman a Pordenone")
        self.assertEqual(
            message.body,
            "Ploie dal dopomisdì. Vierç e cjale.",
        )
        self.assertEqual(message.channel_id, "mf_weather_notices_v1")
        self.assertEqual(message.collapse_key, "mf-evening-forecast")
        self.assertEqual(message.notification_tag, "mf-evening-forecast")
        self.assertEqual(message.data["kind"], "evening_forecast")
        self.assertEqual(message.data["tab"], "bulletin")
        self.assertEqual(message.data["forecast_date"], TOMORROW.isoformat())
        self.assertEqual(repository.claims[0]["notice_kind"], "evening_forecast")
        self.assertEqual(repository.finishes[0]["state"], "sent")

    def test_localizes_each_device_without_refetching_the_shared_place(self):
        repository = FakeDeviceRepository(
            [
                device(language="it"),
                device(device_id="b" * 64, token="token-b", language="fur"),
            ]
        )
        source = FakeSource(snapshot())
        sender = FakeSender()

        result = self.service(
            repository,
            source,
            sender,
            require_single=False,
        ).run()

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 2)
        self.assertEqual(len(source.calls), 1)
        self.assertCountEqual(
            [(message.title, message.body) for message in sender.messages],
            [
                (
                    "Domani a Pordenone",
                    "Giornata soleggiata. Apri e guarda.",
                ),
                (
                    "Doman a Pordenone",
                    "Zornade di soreli. Vierç e cjale.",
                ),
            ],
        )

    def test_existing_daily_claim_is_not_sent_twice(self):
        repository = FakeDeviceRepository([device()], claim_state="sent")
        sender = FakeSender()

        result = self.service(repository, FakeSource(snapshot()), sender).run()

        self.assertEqual(result.status, "deduplicated")
        self.assertEqual(sender.messages, [])

    def test_test_run_id_is_rejected_without_single_target_guard(self):
        with self.assertRaises(EveningForecastConfigurationError):
            EveningForecastDeliveryService(
                device_repository=FakeDeviceRepository([device()]),
                source=FakeSource(snapshot()),
                sender=FakeSender(),
                config=config(),
                require_single_target=False,
                test_run_id="unsafe",
                location_catalog=NoticeMunicipalityCatalog(),
                now=lambda: NOW,
            )

    def test_installation_hash_selects_exact_owner_before_single_target_guard(self):
        selected_id = "b" * 64
        repository = FakeDeviceRepository(
            [
                device(),
                device(device_id=selected_id, token="token-b", language="fur"),
            ]
        )
        source = FakeSource(snapshot())
        sender = FakeSender()

        result = self.service(
            repository,
            source,
            sender,
            test_run_id="owner-dry-run",
            test_installation_hash=selected_id,
        ).run()

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.eligible_devices, 1)
        self.assertEqual(len(source.calls), 1)
        self.assertEqual(len(sender.messages), 1)
        self.assertEqual(sender.messages[0].target_value, "token-b")
        self.assertEqual(repository.claims[0]["device_id"], selected_id)

    def test_unknown_installation_hash_fails_closed_before_source_or_sender(self):
        repository = FakeDeviceRepository([device()])
        source = FakeSource(snapshot())
        sender = FakeSender()

        result = self.service(
            repository,
            source,
            sender,
            test_installation_hash="b" * 64,
        ).run()

        self.assertEqual(result.status, "no_eligible_device")
        self.assertEqual(result.eligible_devices, 0)
        self.assertEqual(source.calls, [])
        self.assertEqual(sender.messages, [])

    def test_installation_hash_is_rejected_without_single_target_guard(self):
        with self.assertRaisesRegex(
            EveningForecastConfigurationError,
            "test_installation_hash_requires_single_target",
        ):
            self.service(
                FakeDeviceRepository([device()]),
                FakeSource(snapshot()),
                FakeSender(),
                require_single=False,
                test_installation_hash="a" * 64,
            )

    def test_installation_hash_must_be_sha256(self):
        with self.assertRaisesRegex(
            EveningForecastConfigurationError,
            "test_installation_hash_invalid",
        ):
            self.service(
                FakeDeviceRepository([device()]),
                FakeSource(snapshot()),
                FakeSender(),
                test_installation_hash="not-a-sha256",
            )


if __name__ == "__main__":
    unittest.main()
