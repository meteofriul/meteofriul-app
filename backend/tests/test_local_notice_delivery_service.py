import os
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.push.fcm import FcmBatchOutcome, FcmSenderUnavailable, FcmTokenInvalid
from app.repositories.push import (
    PUSH_TARGET_FCM_TOKEN,
    PUSH_TARGET_FIREBASE_INSTALLATION_ID,
    PushRepositoryUnavailable,
)
from app.services.local_notice_delivery import (
    LocalNoticeDeliveryAuditUnavailable,
    LocalNoticeDeliveryConfig,
    LocalNoticeDeliveryConfigurationError,
    LocalNoticeDeliveryDeviceStateUnavailable,
    LocalNoticeDeliveryService,
    _body,
)
from app.services.location import LocationCatalog
from app.services.notice_municipalities import NoticeMunicipalityCatalog
from app.services.fvg_geography import FvgGeographyCatalog
from app.weather import local_notice_shadow as shadow
from app.weather.local_notice_source import (
    DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
    MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
    LocalNoticeSourceUnavailable,
)


NOW = datetime(2026, 8, 14, 10, 15, tzinfo=timezone.utc)
DEVICE_ID = "a" * 64
TOKEN = "private-owner-token"
PLAY_BETA_GENERATION = "play-beta-v1"
PLAY_BETA_APP_ID = "1:49007668366:android:725bf6f8b339177a852ddf"
PLAY_BETA_WEB_APP_ID = "1:49007668366:web:a848e70da40a12eb852ddf"
PLAY_BETA_APP_VERSION = "0.1.0+300017"
PLAY_BETA_NEXT_APP_VERSION = "0.1.3+300020"


def device(
    *,
    device_id=DEVICE_ID,
    weather_notices=True,
    municipality=None,
    locality=None,
    location_evidence=None,
    municipality_only=False,
    token=TOKEN,
    platform="android",
    active=True,
    enrollment_generation="",
    app_check_app_id="",
    app_version=PLAY_BETA_APP_VERSION,
):
    if locality is None and not municipality_only:
        locality = {
            "id": "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.4636",
            "name": "Pordenone",
        }
    if location_evidence is None:
        location_evidence = {
            "captured_at": NOW,
            "received_at": NOW,
            "accuracy_m": 25.0,
        }
    target_kind = (
        PUSH_TARGET_FIREBASE_INSTALLATION_ID
        if platform == "web"
        else PUSH_TARGET_FCM_TOKEN
    )
    return {
        "schema_version": "2.1",
        "device_id": device_id,
        "target_kind": target_kind,
        "target_value": token,
        "target_hash": "",
        "active": active,
        "platform": platform,
        "enrollment_generation": enrollment_generation,
        "app_check_app_id": app_check_app_id,
        "app_version": app_version,
        "municipality": municipality or {"istat": "093033", "name": "Pordenone"},
        "locality": locality,
        "location_mode": "automatic_gps",
        "location_evidence": location_evidence,
        "preferences": {
            "official_alerts": True,
            "weather_notices": weather_notices,
        },
    }


def snapshot(
    *,
    wind_gust=20.0,
    weather_codes=None,
    municipality_istat="093033",
    locality=None,
    municipality_only=False,
    catalog=None,
):
    resolved_catalog = catalog or LocationCatalog()
    municipality = resolved_catalog.match_istat(municipality_istat)
    if locality is None and municipality_istat == "093033" and not municipality_only:
        locality = FvgGeographyCatalog().match_locality_id(
            "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.4636"
        )
    local_now = NOW.astimezone(shadow.FVG_ZONE)
    first = local_now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    count = 8
    codes = weather_codes or [1] * count
    return {
        "source": shadow.SOURCE_ID,
        "fetched_at": NOW.isoformat(timespec="seconds"),
        "timezone": shadow.FVG_TIMEZONE,
        "utc_offset_seconds": int(local_now.utcoffset().total_seconds()),
        "requested_location": shadow.canonical_weather_request(
            municipality.istat_code,
            catalog=resolved_catalog,
            locality=locality,
        ),
        "hourly_units": dict(shadow.EXPECTED_HOURLY_UNITS),
        "hourly": {
            "time": [
                (first + timedelta(hours=index)).replace(tzinfo=None).isoformat(
                    timespec="minutes"
                )
                for index in range(count)
            ],
            "temperature_2m": [24.0] * count,
            "apparent_temperature": [24.0] * count,
            "precipitation_probability": [0.0] * count,
            "precipitation": [0.0] * count,
            "rain": [0.0] * count,
            "showers": [0.0] * count,
            "snowfall": [0.0] * count,
            "weather_code": codes,
            "wind_gusts_10m": [wind_gust] * count,
        },
    }


def promotable_candidate(*, event_at, event_end):
    return {
        "schema_version": shadow.SCHEMA_VERSION,
        "policy_version": shadow.POLICY_VERSION,
        "mode": "shadow",
        "shadow_only": True,
        "can_notify": False,
        "kind": "wind",
        "priority": 60,
        "event_at": event_at.isoformat(),
        "event_end": event_end.isoformat(),
        "municipality": {"istat_code": "093033", "city": "Pordenone"},
        "locality": {
            "id": "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.4636",
            "name": "Pordenone",
        },
        "dedupe": {"signature": "f" * 64},
        "evidence": [{"metric": "wind_gusts_10m", "value": 75.0}],
    }


class FakeDeviceRepository:
    def __init__(
        self,
        devices=None,
        *,
        claim_state="sending",
        claim_states=None,
        claim_errors=None,
        error=None,
        finish_result=True,
    ):
        self.devices = list(devices or [])
        self.claim_state = claim_state
        self.claim_states = dict(claim_states or {})
        self.claim_errors = dict(claim_errors or {})
        self.error = error
        self.finish_result = finish_result
        self.list_calls = []
        self.claims = []
        self.finishes = []
        self.disabled = []

    def list_active_devices(self, *, max_devices, enrollment_generation=None):
        if self.error:
            raise self.error
        self.list_calls.append(
            {
                "max_devices": max_devices,
                "enrollment_generation": enrollment_generation,
            }
        )
        values = [
            value
            for value in self.devices
            if enrollment_generation is None
            or value.get("enrollment_generation") == enrollment_generation
        ]
        if enrollment_generation is None and len(values) > max_devices:
            raise PushRepositoryUnavailable("push_device_capacity_state_invalid")
        return deepcopy(values)

    def claim_local_notice_delivery(self, **kwargs):
        self.claims.append(kwargs)
        device_id = kwargs["device_id"]
        error = self.claim_errors.get(device_id)
        if error:
            raise error
        state = self.claim_states.get(device_id, self.claim_state)
        claimed = state == "sending"
        return SimpleNamespace(
            claimed=claimed,
            state=state,
            delivery_id=f"delivery-{device_id[:12]}",
            claim_id="claim-id" if claimed else "",
        )

    def finish_local_notice_delivery(self, **kwargs):
        self.finishes.append(kwargs)
        return self.finish_result

    def disable_device(self, **kwargs):
        self.disabled.append(kwargs)
        return True


class FakeAuditRepository:
    def __init__(self, *, errors_by_locality=None):
        self.saved = []
        self.errors_by_locality = dict(errors_by_locality or {})

    def save_run(self, **kwargs):
        self.saved.append(kwargs)
        error = self.errors_by_locality.get(kwargs.get("locality_id", ""))
        if error:
            raise error
        return "audit-id"


class FakeSource:
    def __init__(self, value=None, *, error=None, values=None, errors=None):
        self.value = value
        self.error = error
        self.values = dict(values or {})
        self.errors = dict(errors or {})
        self.calls = []

    def fetch(self, municipality, locality=None):
        self.calls.append((municipality, locality))
        key = (municipality.istat_code, locality.id if locality is not None else "")
        if key in self.errors:
            raise self.errors[key]
        if self.error:
            raise self.error
        return deepcopy(self.values.get(key, self.value))


class FakeSender:
    def __init__(self, *, error=None, errors_by_target=None):
        self.error = error
        self.errors_by_target = dict(errors_by_target or {})
        self.payloads = []

    def send(self, payload):
        self.payloads.append(payload)
        target_error = self.errors_by_target.get(payload.target_value)
        if target_error:
            raise target_error
        if self.error:
            raise self.error
        return "message-id"


class FakeBatchSender(FakeSender):
    def __init__(self):
        super().__init__()
        self.batch_sizes = []

    def send_batch(self, payloads):
        self.batch_sizes.append(len(payloads))
        self.payloads.extend(payloads)
        return [
            FcmBatchOutcome(message_id=f"message-{index}")
            for index, _ in enumerate(payloads, start=1)
        ]


def config(mode="dry_run"):
    return LocalNoticeDeliveryConfig(
        mode=mode,
        allowed_installation_hash=DEVICE_ID,
        retention_days=14,
        source_timeout_seconds=7,
        max_devices=2,
    )


def play_beta_config(mode="dry_run", *, max_devices=100, min_version_code=None):
    return LocalNoticeDeliveryConfig(
        mode=mode,
        allowed_installation_hash="",
        retention_days=14,
        source_timeout_seconds=7,
        max_devices=max_devices,
        enrollment_mode="play_beta",
        enrollment_generation=PLAY_BETA_GENERATION,
        allowed_app_ids=frozenset({PLAY_BETA_APP_ID}),
        web_app_ids=frozenset({PLAY_BETA_WEB_APP_ID}),
        allowed_app_versions=(
            frozenset() if min_version_code is not None
            else frozenset({PLAY_BETA_APP_VERSION})
        ),
        min_app_version_code=min_version_code,
    )


class SequenceClock:
    def __init__(self, *values):
        self.values = list(values)
        self.last = self.values[-1]

    def __call__(self):
        if self.values:
            self.last = self.values.pop(0)
        return self.last


class LocalNoticeDeliveryServiceTests(unittest.TestCase):
    def make_service(
        self,
        *,
        mode="dry_run",
        devices=None,
        source=None,
        sender=None,
        repository=None,
        audit=None,
        service_config=None,
        now=None,
        location_catalog=None,
    ):
        return LocalNoticeDeliveryService(
            device_repository=repository or FakeDeviceRepository(devices or [device()]),
            audit_repository=audit or FakeAuditRepository(),
            source=source or FakeSource(snapshot(wind_gust=70.0)),
            sender=sender or FakeSender(),
            config=service_config or config(mode),
            now=now or (lambda: NOW),
            location_catalog=location_catalog,
        )

    def test_config_defaults_off_and_requires_exact_owner_hash_when_enabled(self):
        with patch.dict(os.environ, {}, clear=True):
            default_config = LocalNoticeDeliveryConfig.from_environment()
        self.assertEqual(default_config.mode, "off")
        self.assertEqual(
            default_config.source_timeout_seconds,
            DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
        )
        for environment in (
            {"LOCAL_NOTICE_DELIVERY_MODE": "send"},
            {
                "LOCAL_NOTICE_DELIVERY_MODE": "dry_run",
                "LOCAL_NOTICE_ALLOWED_INSTALLATION_HASHES": "bad",
            },
            {
                "LOCAL_NOTICE_DELIVERY_MODE": "send",
                "LOCAL_NOTICE_ALLOWED_INSTALLATION_HASHES": f"{'a' * 64},{'b' * 64}",
            },
            {
                "LOCAL_NOTICE_DELIVERY_MODE": "dry_run",
                "LOCAL_NOTICE_ALLOWED_INSTALLATION_HASHES": "a" * 64,
                "PUSH_PILOT_MAX_DEVICES": "11",
            },
            {
                "LOCAL_NOTICE_DELIVERY_MODE": "dry_run",
                "LOCAL_NOTICE_ALLOWED_INSTALLATION_HASHES": "a" * 64,
                "PUSH_ENROLLMENT_GENERATION": PLAY_BETA_GENERATION,
            },
        ):
            with self.subTest(environment=environment):
                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaises(LocalNoticeDeliveryConfigurationError):
                        LocalNoticeDeliveryConfig.from_environment()

    def test_config_accepts_30_to_45_second_source_timeout(self):
        for timeout in (30, MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS):
            with self.subTest(timeout=timeout):
                with patch.dict(
                    os.environ,
                    {"LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS": str(timeout)},
                    clear=True,
                ):
                    value = LocalNoticeDeliveryConfig.from_environment()
                self.assertEqual(value.source_timeout_seconds, timeout)

        with patch.dict(
            os.environ,
            {
                "LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS": str(
                    MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS + 1
                )
            },
            clear=True,
        ):
            with self.assertRaises(LocalNoticeDeliveryConfigurationError):
                LocalNoticeDeliveryConfig.from_environment()

    def test_play_beta_config_accepts_release_coexistence_and_page_30(self):
        valid = {
            "LOCAL_NOTICE_DELIVERY_MODE": "dry_run",
            "LOCAL_NOTICE_ENROLLMENT_MODE": "play_beta",
            "PUSH_ENROLLMENT_GENERATION": PLAY_BETA_GENERATION,
            "PUSH_APP_CHECK_ANDROID_APP_IDS": PLAY_BETA_APP_ID,
            "PUSH_APP_CHECK_WEB_APP_IDS": PLAY_BETA_WEB_APP_ID,
            "PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS": (
                f"{PLAY_BETA_APP_VERSION},{PLAY_BETA_NEXT_APP_VERSION}"
            ),
            "PUSH_PILOT_MAX_DEVICES": "30",
        }
        with patch.dict(os.environ, valid, clear=True):
            value = LocalNoticeDeliveryConfig.from_environment()
        self.assertEqual(value.enrollment_mode, "play_beta")
        self.assertEqual(value.enrollment_generation, PLAY_BETA_GENERATION)
        self.assertEqual(value.allowed_app_ids, frozenset({PLAY_BETA_APP_ID}))
        self.assertEqual(value.web_app_ids, frozenset({PLAY_BETA_WEB_APP_ID}))
        self.assertEqual(
            value.allowed_app_versions,
            frozenset({PLAY_BETA_APP_VERSION, PLAY_BETA_NEXT_APP_VERSION}),
        )
        self.assertEqual(value.max_devices, 30)
        without_explicit_page_size = dict(valid)
        without_explicit_page_size.pop("PUSH_PILOT_MAX_DEVICES")
        with patch.dict(os.environ, without_explicit_page_size, clear=True):
            self.assertEqual(
                LocalNoticeDeliveryConfig.from_environment().max_devices,
                200,
            )

        invalid_overrides = (
            {"PUSH_ENROLLMENT_GENERATION": ""},
            {"PUSH_ENROLLMENT_GENERATION": "Play Beta"},
            {"PUSH_APP_CHECK_ANDROID_APP_IDS": ""},
            {"PUSH_APP_CHECK_ANDROID_APP_IDS": "web-app-id"},
            {"PUSH_APP_CHECK_WEB_APP_IDS": "android-app-id"},
            {"PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS": ""},
            {"PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS": "invalid version"},
            {"LOCAL_NOTICE_ALLOWED_INSTALLATION_HASHES": DEVICE_ID},
            {"PUSH_PILOT_MAX_DEVICES": "501"},
        )
        for override in invalid_overrides:
            environment = {**valid, **override}
            with self.subTest(override=override):
                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaises(LocalNoticeDeliveryConfigurationError):
                        LocalNoticeDeliveryConfig.from_environment()

    def test_play_beta_config_accepts_minimum_version_code_only(self):
        environment = {
            "LOCAL_NOTICE_DELIVERY_MODE": "dry_run",
            "LOCAL_NOTICE_ENROLLMENT_MODE": "play_beta",
            "PUSH_ENROLLMENT_GENERATION": PLAY_BETA_GENERATION,
            "PUSH_APP_CHECK_ANDROID_APP_IDS": PLAY_BETA_APP_ID,
            "PUSH_APP_CHECK_WEB_APP_IDS": PLAY_BETA_WEB_APP_ID,
            "PUSH_PLAY_BETA_MIN_VERSION_CODE": "300029",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = LocalNoticeDeliveryConfig.from_environment()
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
                    with self.assertRaises(LocalNoticeDeliveryConfigurationError):
                        LocalNoticeDeliveryConfig.from_environment()

    def test_play_beta_uses_generation_bound_capacity_and_attested_devices_only(self):
        eligible = device(
            device_id="b" * 64,
            token="eligible-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        wrong_app = device(
            device_id="c" * 64,
            token="wrong-app-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id="1:49007668366:android:wrong",
        )
        old_generation = device(
            device_id="d" * 64,
            token="old-generation-token",
            enrollment_generation="play-beta-v0",
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        old_version = device(
            device_id="1" * 64,
            token="old-version-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
            app_version="1.0.0+300010",
        )
        web = device(
            device_id="e" * 64,
            token="web-token",
            platform="web",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        old_schema = device(
            device_id="f" * 64,
            token="old-schema-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        old_schema["schema_version"] = "2.0"
        repository = FakeDeviceRepository(
            [eligible, wrong_app, old_generation, old_version, web, old_schema]
        )

        result = self.make_service(
            repository=repository,
            service_config=play_beta_config(),
        ).run()

        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.eligible_devices, 1)
        self.assertEqual(result.attempted, 1)
        self.assertEqual(
            repository.list_calls,
            [
                {
                    "max_devices": 100,
                    "enrollment_generation": PLAY_BETA_GENERATION,
                }
            ],
        )

    def test_off_does_not_read_source_or_devices(self):
        repository = FakeDeviceRepository(error=AssertionError("must stay idle"))
        source = FakeSource(error=AssertionError("must stay idle"))
        result = self.make_service(
            mode="off", repository=repository, source=source
        ).run()
        self.assertEqual(result.status, "disabled")
        self.assertEqual(source.calls, [])

    def test_only_allowlisted_android_owner_is_evaluated(self):
        source = FakeSource(snapshot(wind_gust=70.0))
        result = self.make_service(
            devices=[device(device_id="b" * 64)], source=source
        ).run()
        self.assertEqual(result.status, "no_eligible_device")
        self.assertEqual(source.calls, [])

    def test_stale_or_imprecise_location_is_never_eligible(self):
        stale = device(location_evidence={
            "captured_at": NOW - timedelta(minutes=61),
            "received_at": NOW - timedelta(minutes=61),
            "accuracy_m": 25.0,
        })
        imprecise = device(location_evidence={
            "captured_at": NOW,
            "received_at": NOW,
            "accuracy_m": 251.0,
        })
        for value in (stale, imprecise):
            with self.subTest(evidence=value["location_evidence"]):
                result = self.make_service(devices=[value]).run()
                self.assertEqual(result.status, "no_eligible_device")

    def test_manual_canonical_locality_is_eligible_without_gps_lease(self):
        value = device()
        value["location_mode"] = "manual_selection"
        value["location_evidence"] = None

        result = self.make_service(devices=[value]).run()

        self.assertEqual(result.status, "dry_run")

    def test_manual_canonical_municipality_is_eligible_without_gps_lease(self):
        value = device(municipality_only=True)
        value["location_mode"] = "manual_selection"
        value["location_evidence"] = None
        source = FakeSource(
            snapshot(wind_gust=70.0, municipality_only=True)
        )

        result = self.make_service(devices=[value], source=source).run()

        self.assertEqual(result.status, "dry_run")
        self.assertIsNone(source.calls[0][1])

    def test_automatic_municipality_only_target_uses_fresh_gps_evidence(self):
        stored_device = device(municipality_only=True)
        source = FakeSource(
            snapshot(wind_gust=70.0, municipality_only=True)
        )

        result = self.make_service(
            devices=[stored_device],
            source=source,
        ).run()

        self.assertEqual(result.status, "dry_run")
        self.assertIsNone(source.calls[0][1])

    def test_stale_municipality_only_gps_target_remains_ineligible(self):
        stored_device = device(
            municipality_only=True,
            location_evidence={
                "captured_at": NOW - timedelta(minutes=61),
                "received_at": NOW - timedelta(minutes=61),
                "accuracy_m": 25.0,
            },
        )

        result = self.make_service(devices=[stored_device]).run()

        self.assertEqual(result.status, "no_eligible_device")

    def test_saved_gps_target_remains_eligible_for_sixty_minutes(self):
        stored_device = device(
            municipality_only=True,
            location_evidence={
                "captured_at": NOW - timedelta(minutes=59),
                "received_at": NOW - timedelta(minutes=59),
                "accuracy_m": 250.0,
            },
        )
        source = FakeSource(
            snapshot(wind_gust=70.0, municipality_only=True)
        )

        result = self.make_service(devices=[stored_device], source=source).run()

        self.assertEqual(result.status, "dry_run")

    def test_manual_national_municipality_is_delivered_without_gps(self):
        catalog = NoticeMunicipalityCatalog()
        roma = device(
            municipality={"istat": "058091", "name": "Roma"},
            municipality_only=True,
        )
        roma["location_mode"] = "manual_selection"
        roma["location_evidence"] = None
        source = FakeSource(
            snapshot(
                wind_gust=70.0,
                municipality_istat="058091",
                municipality_only=True,
                catalog=catalog,
            )
        )

        result = self.make_service(
            devices=[roma],
            source=source,
            location_catalog=catalog,
        ).run()

        self.assertEqual(result.status, "dry_run")
        self.assertEqual(source.calls[0][0].istat_code, "058091")

    def test_automatic_national_target_fails_closed_without_boundaries(self):
        catalog = NoticeMunicipalityCatalog()
        roma = device(
            municipality={"istat": "058091", "name": "Roma"},
            municipality_only=True,
        )

        result = self.make_service(
            devices=[roma],
            location_catalog=catalog,
        ).run()

        self.assertEqual(result.status, "no_eligible_device")

    def test_dry_run_selects_one_candidate_logs_it_and_never_claims_or_sends(self):
        repository = FakeDeviceRepository([device()])
        audit = FakeAuditRepository()
        sender = FakeSender()
        result = self.make_service(
            repository=repository,
            audit=audit,
            sender=sender,
        ).run()
        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.selected_kind, "wind")
        self.assertEqual(result.attempted, 1)
        self.assertEqual(repository.claims, [])
        self.assertEqual(sender.payloads, [])
        self.assertEqual(audit.saved[-1]["delivery_status"], "dry_run")

    def test_play_beta_groups_devices_at_the_same_canonical_point(self):
        first = device(
            device_id="b" * 64,
            token="first-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        second = device(
            device_id="c" * 64,
            token="second-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        repository = FakeDeviceRepository([first, second])
        source = FakeSource(snapshot(wind_gust=70.0))
        sender = FakeSender()

        result = self.make_service(
            repository=repository,
            source=source,
            sender=sender,
            service_config=play_beta_config(),
        ).run()

        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.groups, 1)
        self.assertEqual(result.failed_groups, 0)
        self.assertEqual(result.eligible_devices, 2)
        self.assertEqual(result.evaluated, 2)
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.data_quality['evaluations_expected'], 1)
        self.assertEqual(result.data_quality['evaluations_not_possible'], 0)
        self.assertEqual(result.attempted, 2)
        self.assertEqual(len(source.calls), 1)
        self.assertEqual(repository.claims, [])
        self.assertEqual(sender.payloads, [])

    def test_play_beta_fetches_once_for_each_distinct_canonical_point(self):
        locality_device = device(
            device_id="b" * 64,
            token="locality-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        municipality_device = device(
            device_id="c" * 64,
            token="municipality-token",
            municipality_only=True,
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        locality_id = locality_device["locality"]["id"]
        source = FakeSource(
            values={
                ("093033", locality_id): snapshot(wind_gust=70.0),
                ("093033", ""): snapshot(
                    wind_gust=70.0,
                    municipality_only=True,
                ),
            }
        )

        result = self.make_service(
            devices=[locality_device, municipality_device],
            source=source,
            service_config=play_beta_config(),
        ).run()

        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.groups, 2)
        self.assertEqual(result.evaluated, 2)
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.attempted, 2)
        self.assertEqual(len(source.calls), 2)

    def test_group_source_failure_does_not_block_other_canonical_points(self):
        locality_device = device(
            device_id="b" * 64,
            token="locality-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        municipality_device = device(
            device_id="c" * 64,
            token="municipality-token",
            municipality_only=True,
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        locality_id = locality_device["locality"]["id"]
        source = FakeSource(
            values={
                ("093033", locality_id): snapshot(wind_gust=70.0),
            },
            errors={
                ("093033", ""): LocalNoticeSourceUnavailable("source_timeout"),
            },
        )

        result = self.make_service(
            devices=[municipality_device, locality_device],
            source=source,
            service_config=play_beta_config(),
        ).run()

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.groups, 2)
        self.assertEqual(result.failed_groups, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.attempted, 1)
        self.assertEqual(len(source.calls), 2)
        self.assertEqual(result.data_quality['evaluations_expected'], 2)
        self.assertEqual(result.data_quality['evaluations_not_possible'], 1)
        self.assertEqual(result.data_quality['by_source_run'][0]['causes'], [
            {'variable': 'source', 'reason': 'source_unavailable', 'evaluations': 1}])

    def test_group_audit_failure_does_not_block_other_canonical_points(self):
        locality_device = device(
            device_id="b" * 64,
            token="locality-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        municipality_device = device(
            device_id="c" * 64,
            token="municipality-token",
            municipality_only=True,
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        locality_id = locality_device["locality"]["id"]
        audit = FakeAuditRepository(
            errors_by_locality={
                locality_id: LocalNoticeDeliveryAuditUnavailable("write_failed"),
            }
        )
        source = FakeSource(
            values={
                ("093033", locality_id): snapshot(wind_gust=70.0),
                ("093033", ""): snapshot(
                    wind_gust=70.0,
                    municipality_only=True,
                ),
            }
        )

        result = self.make_service(
            devices=[locality_device, municipality_device],
            source=source,
            audit=audit,
            service_config=play_beta_config(),
        ).run()

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.failed_groups, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.attempted, 1)

    def test_dry_run_does_not_select_an_onset_more_than_one_hour_away(self):
        future = snapshot()
        future["hourly"]["wind_gusts_10m"] = [
            20.0,
            70.0,
            20.0,
            20.0,
            20.0,
            20.0,
            20.0,
            20.0,
        ]
        audit = FakeAuditRepository()
        result = self.make_service(
            source=FakeSource(future),
            audit=audit,
        ).run()

        self.assertEqual(result.status, "no_candidate")
        self.assertEqual(result.candidates, 0)
        self.assertTrue(
            any(
                item.get("reason") == "onset_beyond_notice_window"
                for item in audit.saved[-1]["evaluation"]["observations"]
            )
        )

    def test_notification_copy_is_direct_and_heat_uses_dalle(self):
        municipality = LocationCatalog().match_istat("093033")
        locality = FvgGeographyCatalog().match_locality_id(
            "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.4636"
        )
        self.assertIsNotNone(municipality)
        self.assertIsNotNone(locality)
        event_at = "2026-08-14T16:00+02:00"
        cases = (
            ("storm", [], "Temporali per le 16:00 a Pordenone."),
            (
                "storm",
                [{"metric": "weather_code", "value": 96}],
                "Temporali con grandine per le 16:00 a Pordenone.",
            ),
            ("rain", [], "Pioggia intensa per le 16:00 a Pordenone."),
            ("wind", [], "Raffiche forti per le 16:00 a Pordenone."),
            ("snow", [], "Nevicate per le 16:00 a Pordenone."),
            (
                "ice",
                [],
                "Precipitazioni gelate per le 16:00 a Pordenone.",
            ),
            ("heat", [], "Caldo intenso dalle 16:00 a Pordenone."),
        )
        for kind, evidence, expected in cases:
            with self.subTest(kind=kind, evidence=evidence):
                self.assertEqual(
                    _body(
                        {
                            "kind": kind,
                            "event_at": event_at,
                            "evidence": evidence,
                        },
                        municipality,
                        locality,
                    ),
                    expected,
                )

    def test_send_uses_local_channel_direct_copy_and_finishes_outbox(self):
        repository = FakeDeviceRepository([device()])
        audit = FakeAuditRepository()
        sender = FakeSender()
        result = self.make_service(
            mode="send",
            repository=repository,
            audit=audit,
            sender=sender,
        ).run()
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 1)
        self.assertEqual(len(sender.payloads), 1)
        payload = sender.payloads[0]
        self.assertEqual(payload.channel_id, "mf_weather_notices_v1")
        self.assertNotIn("possibil", payload.body.lower())
        self.assertIn("Pordenone", payload.body)
        self.assertEqual(payload.data["type"], "local_weather_notice")
        self.assertEqual(repository.finishes[-1]["state"], "sent")
        self.assertEqual(audit.saved[0]["delivery_status"], "planned")
        self.assertEqual(audit.saved[-1]["delivery_status"], "sent")

    def test_play_beta_sends_local_notice_to_attested_web_manual_target(self):
        web = device(
            device_id="e" * 64,
            token="c123456789012345678901",
            platform="web",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_WEB_APP_ID,
            app_version="0.1.4",
        )
        web["location_mode"] = "manual_selection"
        web["location_evidence"] = None
        repository = FakeDeviceRepository([web])
        sender = FakeSender()

        result = self.make_service(
            mode="send",
            repository=repository,
            sender=sender,
            service_config=play_beta_config(mode="send"),
        ).run()

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 1)
        self.assertEqual(len(sender.payloads), 1)
        payload = sender.payloads[0]
        self.assertEqual(payload.platform, "web")
        self.assertEqual(
            payload.target_kind,
            PUSH_TARGET_FIREBASE_INSTALLATION_ID,
        )
        self.assertEqual(payload.target_value, web["target_value"])
        self.assertEqual(payload.web_link, "https://meteofriul.app/?tab=weather")
        self.assertEqual(repository.claims[0]["expected_app_version"], "")
        self.assertEqual(
            repository.claims[0]["target_kind"],
            PUSH_TARGET_FIREBASE_INSTALLATION_ID,
        )

    def test_play_beta_send_aggregates_sent_and_deduplicated_devices(self):
        first = device(
            device_id="b" * 64,
            token="first-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        second = device(
            device_id="c" * 64,
            token="second-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        repository = FakeDeviceRepository(
            [first, second],
            claim_states={second["device_id"]: "sent"},
        )
        sender = FakeSender()

        result = self.make_service(
            repository=repository,
            sender=sender,
            service_config=play_beta_config(mode="send"),
        ).run()

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.groups, 1)
        self.assertEqual(result.attempted, 2)
        self.assertEqual(result.sent, 1)
        self.assertEqual(result.deduplicated, 1)
        self.assertEqual(result.failed, 0)
        self.assertEqual(len(repository.claims), 2)
        self.assertEqual(len(sender.payloads), 1)
        for claim in repository.claims:
            self.assertEqual(
                claim["expected_enrollment_generation"],
                PLAY_BETA_GENERATION,
            )
            self.assertEqual(claim["expected_app_check_app_id"], PLAY_BETA_APP_ID)
            self.assertEqual(
                claim["expected_app_version"],
                PLAY_BETA_APP_VERSION,
            )

    def test_play_beta_minimum_sends_to_current_and_future_not_old(self):
        devices = [
            device(
                device_id=f"{index + 1:064x}",
                token=f"minimum-token-{index}",
                enrollment_generation=PLAY_BETA_GENERATION,
                app_check_app_id=PLAY_BETA_APP_ID,
                app_version=app_version,
            )
            for index, app_version in enumerate(
                ("0.1.11+300028", "0.1.12+300029", "0.1.13+300030")
            )
        ]
        repository = FakeDeviceRepository(devices)
        sender = FakeSender()

        result = self.make_service(
            repository=repository,
            sender=sender,
            service_config=play_beta_config(
                mode="send", min_version_code=300029
            ),
        ).run()

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 2)
        self.assertEqual(len(sender.payloads), 2)
        self.assertEqual(
            {claim["expected_app_version"] for claim in repository.claims},
            {"0.1.12+300029", "0.1.13+300030"},
        )

    def test_play_beta_send_uses_bounded_fcm_batches(self):
        devices = [
            device(
                device_id=f"{index + 1:064x}",
                token=f"batch-token-{index}",
                enrollment_generation=PLAY_BETA_GENERATION,
                app_check_app_id=PLAY_BETA_APP_ID,
            )
            for index in range(3)
        ]
        sender = FakeBatchSender()

        result = self.make_service(
            repository=FakeDeviceRepository(devices),
            sender=sender,
            service_config=play_beta_config(mode="send", max_devices=2),
        ).run()

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.sent, 3)
        self.assertEqual(result.pages_processed, 1)
        self.assertEqual(result.delivery_batches, 2)
        self.assertEqual(sender.batch_sizes, [2, 1])

    def test_one_invalid_token_does_not_block_other_beta_devices(self):
        invalid = device(
            device_id="b" * 64,
            token="invalid-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        valid = device(
            device_id="c" * 64,
            token="valid-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        repository = FakeDeviceRepository([invalid, valid])
        sender = FakeSender(
            errors_by_target={"invalid-token": FcmTokenInvalid("invalid")}
        )

        result = self.make_service(
            repository=repository,
            sender=sender,
            service_config=play_beta_config(mode="send"),
        ).run()

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.sent, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.failed_groups, 1)
        self.assertEqual(len(repository.claims), 2)
        self.assertEqual(len(sender.payloads), 2)
        self.assertEqual(len(repository.disabled), 1)
        self.assertEqual(repository.disabled[0]["device_id"], invalid["device_id"])
        self.assertEqual(repository.disabled[0]["reason"], "fcm_token_invalid")
        self.assertEqual(repository.disabled[0]["now"], NOW)

    def test_claim_storage_failure_is_isolated_to_one_beta_device(self):
        unavailable = device(
            device_id="b" * 64,
            token="unavailable-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        valid = device(
            device_id="c" * 64,
            token="valid-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        repository = FakeDeviceRepository(
            [unavailable, valid],
            claim_errors={
                unavailable["device_id"]: PushRepositoryUnavailable("claim_failed")
            },
        )

        result = self.make_service(
            repository=repository,
            service_config=play_beta_config(mode="send"),
        ).run()

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.sent, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.failed_groups, 1)

    def test_transient_sender_error_isolated_and_aggregated(self):
        first = device(
            device_id="b" * 64,
            token="first-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        second = device(
            device_id="c" * 64,
            token="second-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        repository = FakeDeviceRepository([first, second])
        sender = FakeSender(
            errors_by_target={
                "first-token": FcmSenderUnavailable("temporary_failure")
            }
        )

        result = self.make_service(
            repository=repository,
            sender=sender,
            service_config=play_beta_config(mode="send"),
        ).run()

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.sent, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(
            {finish["state"] for finish in repository.finishes},
            {"failed_transient", "sent"},
        )

    def test_each_claim_uses_fresh_time_and_expired_candidate_is_not_claimed(self):
        repository = FakeDeviceRepository([device()])
        sender = FakeSender()
        clock = SequenceClock(NOW, NOW, NOW + timedelta(minutes=46))

        result = self.make_service(
            mode="send",
            repository=repository,
            sender=sender,
            now=clock,
        ).run()

        self.assertEqual(result.status, "expired")
        self.assertEqual(result.expired, 1)
        self.assertEqual(repository.claims, [])
        self.assertEqual(sender.payloads, [])

    def test_candidate_expiring_after_claim_is_closed_without_send(self):
        repository = FakeDeviceRepository([device()])
        sender = FakeSender()
        clock = SequenceClock(NOW, NOW, NOW, NOW + timedelta(minutes=46))

        result = self.make_service(
            mode="send",
            repository=repository,
            sender=sender,
            now=clock,
        ).run()

        self.assertEqual(result.status, "expired")
        self.assertEqual(result.expired, 1)
        self.assertEqual(sender.payloads, [])
        self.assertEqual(repository.finishes[0]["state"], "skipped_expired")

    def test_ttl_is_computed_from_fresh_send_time(self):
        repository = FakeDeviceRepository([device()])
        sender = FakeSender()
        service = self.make_service(
            mode="send",
            repository=repository,
            sender=sender,
            now=SequenceClock(
                NOW + timedelta(minutes=5),
                NOW + timedelta(minutes=10),
                NOW + timedelta(minutes=11),
            ),
        )
        target = service._eligible_targets([device()], now=NOW)[0]
        selected = promotable_candidate(
            event_at=NOW + timedelta(minutes=40),
            event_end=NOW + timedelta(minutes=50),
        )

        status = service._deliver_target(
            target=target,
            selected=selected,
            selected_kind="wind",
        )

        self.assertEqual(status, "sent")
        self.assertEqual(sender.payloads[0].ttl_seconds, 40 * 60)
        self.assertEqual(repository.claims[0]["now"], NOW + timedelta(minutes=5))

    def test_unconfirmed_finish_never_reports_sent(self):
        repository = FakeDeviceRepository([device()], finish_result=False)
        sender = FakeSender()
        audit = FakeAuditRepository()

        result = self.make_service(
            mode="send",
            repository=repository,
            sender=sender,
            audit=audit,
        ).run()

        self.assertEqual(result.status, "sent_unconfirmed")
        self.assertEqual(result.sent, 0)
        self.assertEqual(result.sent_unconfirmed, 1)
        self.assertEqual(result.summary()["sent_unconfirmed"], 1)
        self.assertEqual(result.storage_failed, 1)
        self.assertEqual(result.device_failed, 0)
        self.assertEqual(len(sender.payloads), 1)
        self.assertEqual(
            audit.saved[-1]["delivery_status"],
            "sent_unconfirmed",
        )

    def test_duplicate_target_same_point_sends_once_and_reports_anomaly(self):
        first = device(
            device_id="b" * 64,
            token="shared-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        second = device(
            device_id="c" * 64,
            token="shared-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        sender = FakeSender()

        result = self.make_service(
            mode="send",
            devices=[first, second],
            sender=sender,
            service_config=play_beta_config(mode="send"),
        ).run()

        self.assertEqual(len(sender.payloads), 1)
        self.assertEqual(result.sent, 1)
        self.assertEqual(result.duplicate_targets, 1)
        self.assertEqual(result.security_failed, 1)
        self.assertEqual(result.status, "partial")

    def test_duplicate_target_across_points_fails_closed_without_send(self):
        first = device(
            device_id="b" * 64,
            token="shared-token",
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        second = device(
            device_id="c" * 64,
            token="shared-token",
            municipality_only=True,
            enrollment_generation=PLAY_BETA_GENERATION,
            app_check_app_id=PLAY_BETA_APP_ID,
        )
        sender = FakeSender()

        result = self.make_service(
            mode="send",
            devices=[first, second],
            sender=sender,
            service_config=play_beta_config(mode="send"),
        ).run()

        self.assertEqual(sender.payloads, [])
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.duplicate_targets, 1)
        self.assertEqual(result.security_failed, 1)
        self.assertEqual(result.failed_groups, 2)

    def test_claim_states_have_explicit_non_deduplicated_counters(self):
        cases = (
            ("sent", "deduplicated", "deduplicated"),
            ("delivery_in_progress", "in_progress", "in_progress"),
            ("retry_scheduled", "retry_scheduled", "retry_scheduled"),
            ("weather_notices_disabled", "opted_out", "opted_out"),
            ("failed_invalid_token", "device_failed", "failed"),
            ("app_version_changed", "security_failed", "failed"),
        )
        for claim_state, counter, status in cases:
            with self.subTest(claim_state=claim_state):
                result = self.make_service(
                    mode="send",
                    repository=FakeDeviceRepository(
                        [device()],
                        claim_state=claim_state,
                    ),
                ).run()
                self.assertEqual(result.status, status)
                self.assertEqual(getattr(result, counter), 1)
                self.assertEqual(
                    result.deduplicated,
                    int(claim_state == "sent"),
                )

    def test_audit_storage_failure_is_not_counted_as_device_failure(self):
        locality_id = device()["locality"]["id"]
        result = self.make_service(
            audit=FakeAuditRepository(
                errors_by_locality={
                    locality_id: LocalNoticeDeliveryAuditUnavailable("write_failed")
                }
            )
        ).run()

        self.assertEqual(result.audit_failed, 1)
        self.assertEqual(result.storage_failed, 0)
        self.assertEqual(result.device_failed, 0)

    def test_send_uses_canonical_locality_for_forecast_copy_and_data(self):
        locality = FvgGeographyCatalog().match_locality_id(
            "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.3931"
        )
        self.assertIsNotNone(locality)
        stored_device = device(
            municipality={"istat": "093022", "name": "Fontanafredda"},
            locality={"id": locality.id, "name": locality.name},
        )
        source = FakeSource(
            snapshot(
                wind_gust=70.0,
                municipality_istat="093022",
                locality=locality,
            )
        )
        sender = FakeSender()

        result = self.make_service(
            mode="send",
            devices=[stored_device],
            source=source,
            sender=sender,
        ).run()

        self.assertEqual(result.status, "sent")
        self.assertEqual(source.calls[0][1].id, locality.id)
        self.assertIn("Vigonovo", sender.payloads[0].body)
        self.assertNotIn("Fontanafredda", sender.payloads[0].body)
        self.assertEqual(sender.payloads[0].data["locality_id"], locality.id)
        self.assertEqual(sender.payloads[0].data["target_scope"], "locality")
        self.assertEqual(
            sender.payloads[0].data["data_point_source"],
            "rafvg_irdat_5000",
        )

    def test_send_municipality_only_uses_canonical_center_and_explicit_copy(self):
        stored_device = device(municipality_only=True)
        source = FakeSource(
            snapshot(wind_gust=70.0, municipality_only=True)
        )
        repository = FakeDeviceRepository([stored_device])
        sender = FakeSender()

        result = self.make_service(
            mode="send",
            repository=repository,
            source=source,
            sender=sender,
        ).run()

        self.assertEqual(result.status, "sent")
        self.assertIsNone(source.calls[0][1])
        payload = sender.payloads[0]
        self.assertIn("nel Comune di Pordenone", payload.body)
        self.assertEqual(payload.data["locality_id"], "")
        self.assertEqual(payload.data["target_scope"], "municipality")
        self.assertEqual(payload.data["data_point_source"], "municipality_catalog")
        self.assertEqual(repository.claims[0]["expected_locality_id"], "")

    def test_single_unconfirmed_storm_is_logged_but_not_sent(self):
        sender = FakeSender()
        result = self.make_service(
            mode="send",
            source=FakeSource(snapshot(weather_codes=[95] + [1] * 7)),
            sender=sender,
        ).run()
        self.assertEqual(result.status, "not_eligible")
        self.assertEqual(result.candidates, 1)
        self.assertEqual(sender.payloads, [])

    def test_existing_outbox_delivery_is_deduplicated(self):
        repository = FakeDeviceRepository([device()], claim_state="sent")
        sender = FakeSender()
        result = self.make_service(
            mode="send", repository=repository, sender=sender
        ).run()
        self.assertEqual(result.status, "deduplicated")
        self.assertEqual(result.deduplicated, 1)
        self.assertEqual(sender.payloads, [])

    def test_source_and_device_storage_fail_closed(self):
        with self.assertRaises(LocalNoticeDeliveryDeviceStateUnavailable):
            self.make_service(
                repository=FakeDeviceRepository(
                    error=PushRepositoryUnavailable("read_failed")
                )
            ).run()
        result = self.make_service(
            source=FakeSource(error=LocalNoticeSourceUnavailable("source_timeout"))
        ).run()
        self.assertEqual(result.status, "source_unavailable")
        self.assertEqual(result.failed, 1)


if __name__ == "__main__":
    unittest.main()
