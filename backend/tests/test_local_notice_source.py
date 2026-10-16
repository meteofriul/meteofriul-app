import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone

import requests

from app.services.location import LocationCatalog
from app.services.fvg_geography import FvgGeographyCatalog
from app.services.national_municipalities import (
    NATIONAL_MUNICIPALITY_CATALOG_SHA256,
    NATIONAL_MUNICIPALITY_CATALOG_VERSION,
    NATIONAL_MUNICIPALITY_CODES_SHA256,
    NATIONAL_MUNICIPALITY_COUNT,
    get_default_national_municipality_catalog,
)
from app.weather import local_notice_shadow as shadow
from app.weather.local_notice_source import (
    DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
    ICON_LOCAL_NOTICE_BASE_URL,
    LOCAL_NOTICE_FORECAST_HOURS,
    MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
    NATIONAL_ICON_BLOCK_KIND,
    NATIONAL_ICON_CONTRACT,
    NATIONAL_ICON_LOCAL_NOTICE_BASE_URL,
    NATIONAL_ICON_RESOLUTION_KIND,
    IconLocalNoticeSource,
    LocalNoticeSourceUnavailable,
    NationalIconLocalNoticeSource,
    RoutedIconLocalNoticeSource,
)


NOW = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
RUN_ID = "20260814T000000Z"


def latest_payload():
    return {
        "provider": "icon2i",
        "latest": {
            "source_run_id": RUN_ID,
            "manifest_path": f"runs/{RUN_ID}/manifest.json",
        },
    }


def manifest_payload(istat="093033"):
    return {
        "provider": "icon2i",
        "source_run_id": RUN_ID,
        "objects": {
            istat: {
                "path": f"runs/{RUN_ID}/municipalities/{istat}.json",
            }
        }
    }


def municipality_payload(istat="093033", *, forecast_hours=LOCAL_NOTICE_FORECAST_HOURS):
    rows = []
    for hour in range(forecast_hours):
        rows.append(
            {
                "valid_at": (NOW + timedelta(hours=hour)).isoformat().replace(
                    "+00:00", "Z"
                ),
                "temperature_c": 20.0 + hour,
                "apparent_temperature_c": 21.0 + hour,
                "liquid_rain_mm": 1.0 if hour == 2 else 0.0,
                "precipitation_mm": 1.0 if hour == 2 else 0.0,
                "snow_water_equivalent_mm": 0.0,
                "wind_gust_max_m_s": 10.0,
                "condition": {"native_code": 2},
            }
        )
    return {
        "provider": "icon2i",
        "source_run_id": RUN_ID,
        "timezone": shadow.FVG_TIMEZONE,
        "municipality": {
            "istat_code": istat,
            "model_point": {"lat": 45.96, "lon": 12.65},
        },
        "hourly": rows,
    }


class FakeResponse:
    def __init__(
        self,
        payload=None,
        *,
        raw=None,
        json_error=None,
        http_error=None,
    ):
        self.payload = payload
        self.json_error = json_error
        self.http_error = http_error
        self.content = raw if raw is not None else json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.text = self.content.decode("utf-8")

    def raise_for_status(self):
        if self.http_error is not None:
            raise self.http_error

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.payload


class FakeSession:
    def __init__(self, responses=None, *, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def national_payloads(municipality):
    count = 13
    times = [
        (NOW - timedelta(hours=2) + timedelta(hours=index))
        .isoformat()
        .replace("+00:00", "Z")
        for index in range(count)
    ]
    accumulated = [0.0, 0.0, 0.0, 0.0, 1.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0]
    values = {
        "t_2m_k": [293.15] * count,
        "u_10m_m_s": [1.0] * count,
        "v_10m_m_s": [1.0] * count,
        "total_precipitation_mm": accumulated,
        "weather_code": [2] * count,
        "wind_gust_max_m_s": [22.0] * count,
        "convective_rain_mm": accumulated,
        "grid_scale_rain_mm": [0.0] * count,
        "convective_snow_mm": [0.0] * count,
        "grid_scale_snow_mm": [0.0] * count,
        "grid_scale_graupel_mm": [0.0] * count,
    }
    block_id = "t0250000-y0527-x0770"
    cell_id = "g312390"
    block = {
        "schema_version": 2,
        "kind": NATIONAL_ICON_BLOCK_KIND,
        "contract": NATIONAL_ICON_CONTRACT,
        "source_run_id": RUN_ID,
        "block_id": block_id,
        "time_axis": times,
        "municipality_cells": {municipality.istat_code: cell_id},
        "cells": [
            {
                "cell_id": cell_id,
                "latitude": 41.9,
                "longitude": 12.5,
                "values": values,
            }
        ],
        "metadata": {
            "catalog": {
                "municipality_count": NATIONAL_MUNICIPALITY_COUNT,
                "version": NATIONAL_MUNICIPALITY_CATALOG_VERSION,
                "sha256": NATIONAL_MUNICIPALITY_CATALOG_SHA256,
                "municipality_codes_sha256": NATIONAL_MUNICIPALITY_CODES_SHA256,
            },
            "variables": [
                {"id": variable_id, "unit": unit}
                for variable_id, unit in {
                    "t_2m_k": "K",
                    "u_10m_m_s": "m/s",
                    "v_10m_m_s": "m/s",
                    "total_precipitation_mm": "mm",
                    "weather_code": "wmo_code",
                    "wind_gust_max_m_s": "m/s",
                    "convective_rain_mm": "mm",
                    "grid_scale_rain_mm": "mm",
                    "convective_snow_mm": "mm",
                    "grid_scale_snow_mm": "mm",
                    "grid_scale_graupel_mm": "mm",
                }.items()
            ],
        },
    }
    raw = json.dumps(
        block,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    resolution = {
        "schema_version": 1,
        "kind": NATIONAL_ICON_RESOLUTION_KIND,
        "contract": NATIONAL_ICON_CONTRACT,
        "status": "experimental_local_pilot_only",
        "source_run_id": RUN_ID,
        "municipality": {
            "istat_code": municipality.istat_code,
            "name": municipality.name,
            "province": municipality.province,
        },
        "block_id": block_id,
        "cell_id": cell_id,
        "block_path": f"runs/{RUN_ID}/blocks/{block_id}.json",
        "block_json_bytes": len(raw),
        "block_sha256": hashlib.sha256(raw).hexdigest(),
    }
    return resolution, block, raw


class LocalNoticeSourceTests(unittest.TestCase):
    def setUp(self):
        self.municipality = LocationCatalog().match_istat("093033")
        self.assertIsNotNone(self.municipality)
        self.vigonovo = FvgGeographyCatalog().match_locality_id(
            "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.3931"
        )
        self.assertIsNotNone(self.vigonovo)

    def make_source(self, session):
        return IconLocalNoticeSource(
            session=session,
            timeout_seconds=7,
            now=lambda: NOW,
        )

    def successful_session(self, istat="093033", *, manifest=None, municipalities=None):
        municipality_responses = municipalities or [municipality_payload(istat)]
        return FakeSession(
            [
                FakeResponse(latest_payload()),
                FakeResponse(manifest or manifest_payload(istat)),
                *[FakeResponse(payload) for payload in municipality_responses],
            ]
        )

    def test_fetch_reads_only_the_verified_icon_contract(self):
        session = self.successful_session()
        snapshot = self.make_source(session).fetch(self.municipality)

        self.assertEqual(len(session.calls), 3)
        self.assertEqual(session.calls[0][0], ICON_LOCAL_NOTICE_BASE_URL + "latest.json")
        self.assertTrue(session.calls[1][0].endswith(f"runs/{RUN_ID}/manifest.json"))
        self.assertTrue(session.calls[2][0].endswith(f"municipalities/093033.json"))
        self.assertTrue(all("api.open-meteo.com" not in call[0] for call in session.calls))
        self.assertTrue(all(call[1]["timeout"] == 7 for call in session.calls))
        self.assertEqual(snapshot["source"], shadow.SOURCE_ID)
        self.assertEqual(snapshot["source_run_id"], RUN_ID)
        self.assertEqual(snapshot["requested_location"]["istat_code"], "093033")
        self.assertEqual(snapshot["fetched_at"], "2026-08-14T10:00:00+00:00")
        self.assertEqual(len(snapshot["hourly"]["time"]), LOCAL_NOTICE_FORECAST_HOURS)
        self.assertEqual(snapshot["hourly"]["precipitation_probability"][2], 100.0)
        self.assertEqual(snapshot["hourly"]["wind_gusts_10m"][0], 36.0)

    def test_fetch_can_expand_the_verified_window_for_daily_summary(self):
        session = self.successful_session(
            municipalities=[municipality_payload(forecast_hours=24)]
        )
        source = IconLocalNoticeSource(
            session=session,
            timeout_seconds=7,
            now=lambda: NOW,
            forecast_hours=24,
        )

        snapshot = source.fetch(self.municipality)

        self.assertEqual(len(snapshot["hourly"]["time"]), 24)

    def test_fetch_preserves_locality_as_requested_location_and_icon_model_point(self):
        municipality = LocationCatalog().match_istat("093022")
        session = self.successful_session("093022")
        snapshot = self.make_source(session).fetch(municipality, self.vigonovo)

        self.assertEqual(snapshot["requested_location"]["latitude"], self.vigonovo.latitude)
        self.assertEqual(snapshot["requested_location"]["locality_id"], self.vigonovo.id)
        self.assertEqual(snapshot["model_location"], {"lat": 45.96, "lon": 12.65})

    def test_explicit_storm_code_is_not_downgraded_to_generic_rain(self):
        payload = municipality_payload()
        payload["hourly"][2]["condition"]["native_code"] = 95
        session = self.successful_session(municipalities=[payload])

        snapshot = self.make_source(session).fetch(self.municipality)

        self.assertEqual(snapshot["hourly"]["weather_code"][2], 95)

    def test_floating_point_precipitation_residue_does_not_create_snow(self):
        payload = municipality_payload()
        payload["hourly"][0]["condition"]["native_code"] = 1
        payload["hourly"][0]["snow_water_equivalent_mm"] = 6.3e-16
        payload["hourly"][0]["liquid_rain_mm"] = 5.4e-16
        payload["hourly"][0]["precipitation_mm"] = 6.3e-16
        session = self.successful_session(municipalities=[payload])

        snapshot = self.make_source(session).fetch(self.municipality)

        self.assertEqual(snapshot["hourly"]["weather_code"][0], 1)

    def test_multiple_municipalities_reuse_the_verified_run_index(self):
        second = "093022"
        manifest = manifest_payload()
        manifest["objects"][second] = {
            "path": f"runs/{RUN_ID}/municipalities/{second}.json"
        }
        session = self.successful_session(
            manifest=manifest,
            municipalities=[municipality_payload(), municipality_payload(second)],
        )
        source = self.make_source(session)

        source.fetch(self.municipality)
        source.fetch(LocationCatalog().match_istat(second), self.vigonovo)

        self.assertEqual(len(session.calls), 4)
        self.assertEqual(
            sum(call[0].endswith("latest.json") for call in session.calls),
            1,
        )
        self.assertEqual(
            sum(call[0].endswith("manifest.json") for call in session.calls),
            1,
        )

    def test_mismatched_or_invalid_contract_is_rejected(self):
        invalid = municipality_payload()
        invalid["timezone"] = "UTC"
        source = self.make_source(
            FakeSession(
                [
                    FakeResponse(latest_payload()),
                    FakeResponse(manifest_payload()),
                    FakeResponse(invalid),
                ]
            )
        )
        with self.assertRaises(LocalNoticeSourceUnavailable) as raised:
            source.fetch(self.municipality)
        self.assertEqual(raised.exception.code, "source_invalid_municipality")

        invalid_manifest = manifest_payload()
        invalid_manifest["provider"] = "open_meteo"
        source = self.make_source(
            FakeSession(
                [
                    FakeResponse(latest_payload()),
                    FakeResponse(invalid_manifest),
                ]
            )
        )
        with self.assertRaises(LocalNoticeSourceUnavailable) as raised:
            source.fetch(self.municipality)
        self.assertEqual(raised.exception.code, "source_invalid_manifest")

    def test_timeout_and_network_failures_have_sanitized_codes(self):
        for error, expected in (
            (requests.Timeout("secret-url"), "source_timeout"),
            (requests.ConnectionError("secret-url"), "source_request_failed"),
        ):
            with self.subTest(expected=expected):
                session = FakeSession(error=error)
                source = self.make_source(session)
                with self.assertRaises(LocalNoticeSourceUnavailable) as raised:
                    source.fetch(self.municipality)
                self.assertEqual(raised.exception.code, expected)
                self.assertNotIn("secret-url", str(raised.exception))
                self.assertEqual(
                    len(session.calls),
                    2 if expected == "source_timeout" else 1,
                )

    def test_timeout_is_retried_once_then_verified_contract_continues(self):
        session = FakeSession(
            [
                requests.Timeout("cold-start"),
                FakeResponse(latest_payload()),
                FakeResponse(manifest_payload()),
                FakeResponse(municipality_payload()),
            ]
        )
        source = IconLocalNoticeSource(
            session=session,
            timeout_seconds=30,
            now=lambda: NOW,
        )

        snapshot = source.fetch(self.municipality)

        self.assertEqual(snapshot["source_run_id"], RUN_ID)
        self.assertEqual(len(session.calls), 4)
        self.assertTrue(session.calls[0][0].endswith("latest.json"))
        self.assertEqual(session.calls[0][0], session.calls[1][0])
        self.assertTrue(all(call[1]["timeout"] == 30 for call in session.calls))

    def test_shared_fvg_index_failure_does_not_multiply_retry_budget(self):
        session = FakeSession(error=requests.Timeout("regional-outage"))
        source = IconLocalNoticeSource(
            session=session,
            timeout_seconds=30,
            now=lambda: NOW,
        )

        for _ in range(2):
            with self.assertRaises(LocalNoticeSourceUnavailable) as raised:
                source.fetch(self.municipality)
            self.assertEqual(raised.exception.code, "source_timeout")

        self.assertEqual(len(session.calls), 2)

    def test_timeout_default_and_upper_bound_cover_cloud_run_cold_starts(self):
        default_session = self.successful_session()
        IconLocalNoticeSource(
            session=default_session,
            now=lambda: NOW,
        ).fetch(self.municipality)
        self.assertTrue(
            all(
                call[1]["timeout"] == DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS
                for call in default_session.calls
            )
        )

        bounded_session = self.successful_session()
        IconLocalNoticeSource(
            session=bounded_session,
            timeout_seconds=90,
            now=lambda: NOW,
        ).fetch(self.municipality)
        self.assertTrue(
            all(
                call[1]["timeout"] == MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS
                for call in bounded_session.calls
            )
        )

    def test_invalid_json_and_non_object_payload_are_rejected(self):
        invalid_json = self.make_source(
            FakeSession([FakeResponse(json_error=ValueError("raw response"))])
        )
        with self.assertRaises(LocalNoticeSourceUnavailable) as raised:
            invalid_json.fetch(self.municipality)
        self.assertEqual(raised.exception.code, "source_invalid_json")

        invalid_payload = self.make_source(FakeSession([FakeResponse([])]))
        with self.assertRaises(LocalNoticeSourceUnavailable) as raised:
            invalid_payload.fetch(self.municipality)
        self.assertEqual(raised.exception.code, "source_invalid_payload")

    def test_national_source_verifies_resolution_block_and_adapts_roma(self):
        municipality = get_default_national_municipality_catalog().match_istat(
            "058091"
        )
        resolution, _, raw = national_payloads(municipality)
        session = FakeSession(
            [FakeResponse(resolution), FakeResponse(raw=raw)]
        )
        source = NationalIconLocalNoticeSource(
            session=session,
            timeout_seconds=7,
            now=lambda: NOW,
        )

        snapshot = source.fetch(municipality)

        self.assertEqual(len(session.calls), 2)
        self.assertEqual(
            session.calls[0][0],
            NATIONAL_ICON_LOCAL_NOTICE_BASE_URL + "resolve.json",
        )
        self.assertEqual(
            session.calls[0][1]["params"],
            {"city": "Roma", "province": "RM"},
        )
        self.assertEqual(snapshot["requested_location"]["istat_code"], "058091")
        self.assertEqual(snapshot["source_run_id"], RUN_ID)
        self.assertEqual(len(snapshot["hourly"]["time"]), 8)
        self.assertAlmostEqual(snapshot["hourly"]["temperature_2m"][0], 20.0)
        self.assertEqual(snapshot["hourly"]["wind_gusts_10m"][0], 79.2)

    def test_national_source_retries_one_timeout_before_validation(self):
        municipality = get_default_national_municipality_catalog().match_istat(
            "058091"
        )
        resolution, _, raw = national_payloads(municipality)
        session = FakeSession(
            [
                requests.Timeout("cold-start"),
                FakeResponse(resolution),
                FakeResponse(raw=raw),
            ]
        )
        source = NationalIconLocalNoticeSource(
            session=session,
            timeout_seconds=30,
            now=lambda: NOW,
        )

        snapshot = source.fetch(municipality)

        self.assertEqual(snapshot["source_run_id"], RUN_ID)
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(session.calls[0][0], session.calls[1][0])
        self.assertTrue(all(call[1]["timeout"] == 30 for call in session.calls))

    def test_national_resolver_outage_does_not_retry_for_every_group(self):
        municipality = get_default_national_municipality_catalog().match_istat(
            "058091"
        )
        session = FakeSession(error=requests.Timeout("national-outage"))
        source = NationalIconLocalNoticeSource(
            session=session,
            timeout_seconds=30,
            now=lambda: NOW,
        )

        for _ in range(2):
            with self.assertRaises(LocalNoticeSourceUnavailable) as raised:
                source.fetch(municipality)
            self.assertEqual(raised.exception.code, "source_timeout")

        self.assertEqual(len(session.calls), 2)

    def test_national_source_rejects_a_block_integrity_mismatch(self):
        municipality = get_default_national_municipality_catalog().match_istat(
            "058091"
        )
        resolution, _, raw = national_payloads(municipality)
        resolution["block_sha256"] = "0" * 64
        source = NationalIconLocalNoticeSource(
            session=FakeSession(
                [FakeResponse(resolution), FakeResponse(raw=raw)]
            ),
            now=lambda: NOW,
        )

        with self.assertRaises(LocalNoticeSourceUnavailable) as raised:
            source.fetch(municipality)

        self.assertEqual(
            raised.exception.code,
            "source_block_integrity_failed",
        )

    def test_router_keeps_fvg_v1_and_uses_v2_only_outside_region(self):
        class RecordingSource:
            def __init__(self, result):
                self.result = result
                self.calls = []

            def fetch(self, municipality, locality=None):
                self.calls.append((municipality, locality))
                return self.result

        fvg = RecordingSource({"route": "fvg"})
        national = RecordingSource({"route": "national"})
        router = RoutedIconLocalNoticeSource(
            fvg_source=fvg,
            national_source=national,
        )
        roma = get_default_national_municipality_catalog().match_istat("058091")

        self.assertEqual(router.fetch(self.municipality), {"route": "fvg"})
        self.assertEqual(router.fetch(roma), {"route": "national"})
        self.assertEqual(len(fvg.calls), 1)
        self.assertEqual(len(national.calls), 1)


if __name__ == "__main__":
    unittest.main()
