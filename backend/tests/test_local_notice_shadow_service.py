import inspect
import os
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.repositories.push import PushRepositoryUnavailable
from app.services import local_notice_shadow as service_module
from app.services.local_notice_shadow import (
    LocalNoticeShadowConfig,
    LocalNoticeShadowConfigurationError,
    LocalNoticeShadowDeviceStateUnavailable,
    LocalNoticeShadowService,
)
from app.weather import local_notice_shadow as shadow
from app.weather.local_notice_source import (
    DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
    MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
    LocalNoticeSourceUnavailable,
)


NOW = datetime(2026, 8, 14, 10, 15, tzinfo=timezone.utc)


def device(
    *,
    istat="093033",
    name="Pordenone",
    weather_notices=True,
    token="private-fcm-token",
    locality=None,
):
    return {
        "device_id": "private-device-id",
        "token": token,
        "active": True,
        "platform": "android",
        "municipality": {"istat": istat, "name": name},
        "locality": locality,
        "preferences": {
            "official_alerts": True,
            "weather_notices": weather_notices,
        },
    }


def snapshot_for(municipality, *, wind_gust=20.0, locality=None):
    local_now = NOW.astimezone(shadow.FVG_ZONE)
    first_slot = local_now.replace(minute=0, second=0, microsecond=0) + timedelta(
        hours=1
    )
    slot_count = 8
    hourly = {
        "time": [
            (first_slot + timedelta(hours=index))
            .replace(tzinfo=None)
            .isoformat(timespec="minutes")
            for index in range(slot_count)
        ],
        "temperature_2m": [24.0] * slot_count,
        "apparent_temperature": [24.0] * slot_count,
        "precipitation_probability": [0.0] * slot_count,
        "precipitation": [0.0] * slot_count,
        "rain": [0.0] * slot_count,
        "showers": [0.0] * slot_count,
        "snowfall": [0.0] * slot_count,
        "weather_code": [1] * slot_count,
        "wind_gusts_10m": [wind_gust] * slot_count,
    }
    return {
        "source": shadow.SOURCE_ID,
        "fetched_at": NOW.isoformat(timespec="seconds"),
        "timezone": shadow.FVG_TIMEZONE,
        "utc_offset_seconds": int(local_now.utcoffset().total_seconds()),
        "requested_location": shadow.canonical_weather_request(
            municipality.istat_code,
            locality=locality,
        ),
        "hourly_units": dict(shadow.EXPECTED_HOURLY_UNITS),
        "hourly": hourly,
    }


class FakeDeviceRepository:
    def __init__(self, devices=None, *, error=None):
        self.devices = list(devices or [])
        self.error = error
        self.calls = []

    def list_active_devices(self, *, max_devices):
        self.calls.append(max_devices)
        if self.error is not None:
            raise self.error
        return deepcopy(self.devices)


class FakeShadowRepository:
    def __init__(self):
        self.saved = []

    def save_run(self, **kwargs):
        self.saved.append(kwargs)
        return "shadow-run-id"


class FakeSource:
    def __init__(self, *, snapshot=None, error=None):
        self.snapshot = snapshot
        self.error = error
        self.calls = []

    def fetch(self, municipality, locality=None):
        self.calls.append((municipality, locality))
        if self.error is not None:
            raise self.error
        return deepcopy(self.snapshot)


def config(*, mode="shadow", max_devices=1, max_municipalities=1):
    return LocalNoticeShadowConfig(
        mode=mode,
        retention_days=14,
        source_timeout_seconds=7,
        max_municipalities=max_municipalities,
        max_devices=max_devices,
    )


class LocalNoticeShadowServiceTests(unittest.TestCase):
    def make_service(
        self,
        *,
        devices=None,
        source=None,
        repository=None,
        resolved_config=None,
    ):
        return LocalNoticeShadowService(
            device_repository=repository or FakeDeviceRepository(devices),
            shadow_repository=FakeShadowRepository(),
            source=source or FakeSource(snapshot={}),
            config=resolved_config or config(),
            now=lambda: NOW,
        )

    def test_config_defaults_to_resilient_timeout_and_rejects_above_bound(self):
        with patch.dict(os.environ, {}, clear=True):
            value = LocalNoticeShadowConfig.from_environment()
        self.assertEqual(
            value.source_timeout_seconds,
            DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
        )

        with patch.dict(
            os.environ,
            {
                "LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS": str(
                    MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS + 1
                )
            },
            clear=True,
        ):
            with self.assertRaises(LocalNoticeShadowConfigurationError):
                LocalNoticeShadowConfig.from_environment()

    def test_off_mode_does_not_read_devices_contact_source_or_write(self):
        devices = FakeDeviceRepository([device()])
        source = FakeSource(error=AssertionError("source must remain idle"))
        persistence = FakeShadowRepository()
        service = LocalNoticeShadowService(
            device_repository=devices,
            shadow_repository=persistence,
            source=source,
            config=config(mode="off"),
            now=lambda: NOW,
        )

        result = service.run()

        self.assertEqual(result.status, "disabled")
        self.assertEqual(devices.calls, [])
        self.assertEqual(source.calls, [])
        self.assertEqual(persistence.saved, [])

    def test_only_android_owner_with_weather_notices_and_location_is_eligible(self):
        service = self.make_service(
            devices=[
                device(weather_notices=False),
                {**device(), "municipality": None},
            ]
        )

        result = service.run()

        self.assertEqual(result.status, "no_eligible_municipality")

    def test_valid_owner_snapshot_is_evaluated_and_persisted_without_device_data(self):
        catalog = service_module.LocationCatalog()
        municipality = catalog.match_istat("093033")
        source = FakeSource(snapshot=snapshot_for(municipality, wind_gust=70.0))
        persistence = FakeShadowRepository()
        service = LocalNoticeShadowService(
            device_repository=FakeDeviceRepository([device()]),
            shadow_repository=persistence,
            source=source,
            config=config(),
            location_catalog=catalog,
            now=lambda: NOW,
        )

        result = service.run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.evaluated, 1)
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.persisted, 1)
        self.assertEqual(source.calls[0][0].istat_code, "093033")
        saved_text = str(persistence.saved[0])
        self.assertNotIn("private-fcm-token", saved_text)
        self.assertNotIn("private-device-id", saved_text)
        evaluation = persistence.saved[0]["evaluation"]
        self.assertFalse(evaluation["can_send"])
        self.assertFalse(evaluation["candidates"][0]["can_notify"])

    def test_source_failure_is_persisted_as_sanitized_evidence_without_snapshot(self):
        source = FakeSource(
            error=LocalNoticeSourceUnavailable("source_timeout")
        )
        persistence = FakeShadowRepository()
        service = LocalNoticeShadowService(
            device_repository=FakeDeviceRepository([device()]),
            shadow_repository=persistence,
            source=source,
            config=config(),
            now=lambda: NOW,
        )

        result = service.run()

        self.assertEqual(result.status, "source_unavailable")
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.persisted, 1)
        saved = persistence.saved[0]
        self.assertEqual(saved["source_error_code"], "source_timeout")
        self.assertEqual(saved["evaluation"]["candidates"], [])
        self.assertNotIn("token", str(saved))

    def test_corrupt_registered_municipality_fails_closed_without_network(self):
        source = FakeSource(error=AssertionError("source must remain idle"))
        service = self.make_service(
            devices=[device(name="Wrong name")],
            source=source,
        )

        result = service.run()

        self.assertEqual(result.status, "invalid_target_state")
        self.assertEqual(result.failed, 1)
        self.assertEqual(source.calls, [])

    def test_more_than_one_distinct_municipality_hits_owner_limit(self):
        source = FakeSource(error=AssertionError("source must remain idle"))
        service = self.make_service(
            devices=[
                device(),
                device(istat="030129", name="Udine", token="second-token"),
            ],
            source=source,
            resolved_config=config(max_devices=2),
        )

        result = service.run()

        self.assertEqual(result.status, "target_limit_exceeded")
        self.assertEqual(result.eligible_municipalities, 2)
        self.assertEqual(source.calls, [])

    def test_device_storage_failure_is_exposed_without_network(self):
        devices = FakeDeviceRepository(
            error=PushRepositoryUnavailable("read_failed")
        )
        source = FakeSource(error=AssertionError("source must remain idle"))
        service = LocalNoticeShadowService(
            device_repository=devices,
            shadow_repository=FakeShadowRepository(),
            source=source,
            config=config(),
            now=lambda: NOW,
        )

        with self.assertRaises(LocalNoticeShadowDeviceStateUnavailable):
            service.run()
        self.assertEqual(source.calls, [])

    def test_configuration_defaults_off_and_rejects_send_or_more_than_owner(self):
        with patch.dict(os.environ, {}, clear=True):
            defaults = LocalNoticeShadowConfig.from_environment()
        self.assertEqual(defaults.mode, "off")
        self.assertEqual(defaults.retention_days, 14)
        self.assertEqual(defaults.max_municipalities, 1)

        with patch.dict(
            os.environ,
            {"LOCAL_NOTICE_SHADOW_MODE": ""},
            clear=True,
        ):
            self.assertEqual(
                LocalNoticeShadowConfig.from_environment().mode,
                "off",
            )

        for environment in (
            {"LOCAL_NOTICE_SHADOW_MODE": "send"},
            {"LOCAL_NOTICE_SHADOW_MAX_MUNICIPALITIES": "2"},
        ):
            with self.subTest(environment=environment):
                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaises(LocalNoticeShadowConfigurationError):
                        LocalNoticeShadowConfig.from_environment()

    def test_service_module_has_no_fcm_or_push_sender_dependency(self):
        source = inspect.getsource(service_module)
        self.assertNotIn("app.push", source)
        self.assertNotIn("FirebaseCloudMessagingSender", source)


if __name__ == "__main__":
    unittest.main()
