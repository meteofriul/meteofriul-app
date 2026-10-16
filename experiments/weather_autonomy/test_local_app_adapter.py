"""Offline API adapter checks over explicitly synthetic full-coverage fixtures."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from decode_cams import EXPECTED_VARIABLES
from local_app_adapter import LocalSnapshotAdapter, LocalSnapshotUnavailable, canonical_condition, iso, rome_time

RUN = datetime(2026, 9, 3, tzinfo=timezone.utc)


def fixture():
    hourly = []
    for hour in range(73):
        hourly.append(dict(valid_at_utc=iso(RUN + timedelta(hours=hour)), temperature_c=20 + hour/10,
                           relative_humidity_pct=70, apparent_temperature_c=23.125, pressure_msl_hpa=1017.125,
                           wind_m_s=1.5, wind_from_degrees=180, wind_gust_m_s=3.25, cloud_cover_pct=25,
                           precipitation_previous_hour_mm=None, rain_previous_hour_mm=0.0,
                           convective_rain_previous_hour_mm=0.0, snow_water_equivalent_previous_hour_mm=0.25,
                           graupel_water_equivalent_previous_hour_mm=0.125, precipitation_probability_pct=None,
                           visibility_m=None, condition=dict(code=96, label="Temporale con grandine o temporale forte", status="valid"),
                           quality_flags=["TOT_PREC_below_encoding_resolution"], precipitation_encoding={}))
    towns = [dict(id="pordenone" if n == 0 else f"fixture-{n}", name="Pordenone" if n == 0 else f"Fixture {n}",
                  latitude=45.95689, longitude=12.66051, grid_point=dict(lat=45.95, lon=12.65, distance=1.1, index=4),
                  hourly=hourly) for n in range(215)]
    icon = dict(schema_version=1, status="partial_pilot_not_production", validation=dict(usable=True),
                run_utc=iso(RUN), generated_at_utc=iso(RUN+timedelta(hours=14)), municipalities=towns,
                sources=dict(icon=dict(status="acquired_and_decoded", run_utc=iso(RUN), attribution="Synthetic fixture", license="CC BY 4.0", url="https://example.invalid")))
    variables = [dict(id=vid, units="grains/m3" if vid.endswith("_pollen") else "ug/m3",
                      source_units="grains/m3" if vid.endswith("_pollen") else "kg/m3", quality_flags=["unit_provenance"])
                 for vid in EXPECTED_VARIABLES]
    cams = dict(schema_version=2, kind="cams_region_point_extraction", run_utc=iso(RUN),
                generated_at_utc=iso(RUN+timedelta(hours=14)), sources={}, attribution="CAMS synthetic fixture",
                variables=variables, times_utc=[iso(RUN+timedelta(hours=h)) for h in range(97)],
                municipalities=[{**{k: t[k] for k in ("id", "name", "latitude", "longitude")}, "cell_id": "4"} for t in towns],
                cells=[dict(id="4", lat=45.95, lon=12.65, grid_index=4,
                            values={vid: [0.0]*97 for vid in EXPECTED_VARIABLES},
                            raw_values={vid: [0.0]*97 for vid in EXPECTED_VARIABLES}, quality_flags={})])
    return icon, cams


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.icon_path, cls.cams_path = Path(cls.temp.name)/"icon.json", Path(cls.temp.name)/"cams.json"
        cls.icon, cls.cams = fixture()
        cls.icon_path.write_text(json.dumps(cls.icon), encoding="utf-8")
        cls.cams_path.write_text(json.dumps(cls.cams), encoding="utf-8")
        cls.now = RUN + timedelta(hours=14, minutes=30)
        cls.adapter = LocalSnapshotAdapter(cls.icon_path, cls.cams_path, now_provider=lambda: cls.now)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_current_contract_native_code_units_and_nulls(self):
        result = self.adapter.current("PORDENONE", 45.96, 12.66)
        self.assertEqual("icon2i_local_pilot", result["primary_source"])
        self.assertEqual("Temporale", result["condition"])
        self.assertIsNone(result["weathercode"])
        self.assertEqual(96, result["data_quality"]["native_weather_code"])
        self.assertEqual(5.4, result["wind_speed"])
        self.assertEqual(11.700000000000001, result["wind_gusts"])
        self.assertEqual(1017.125, result["pressure"])
        self.assertIsNone(result["precipitation"])
        self.assertEqual(0, result["rain"])
        for key in ("showers", "snowfall", "pop", "visibility", "is_day", "sunrise", "sunset", "station", "official", "fallback_used"):
            self.assertIsNone(result[key])
        self.assertFalse(result["model_support"]["open_meteo"])
        self.assertEqual(0.25, result["data_quality"]["snowfall_water_equivalent_mm"])

    def test_hourly_horizon_and_original_timestamps(self):
        result = self.adapter.current("pordenone")
        self.assertEqual("2026-09-03T14:00:00Z", result["data_quality"]["valid_at_utc"])
        self.assertEqual("2026-09-03T14:00:00Z", result["cache"]["generated_at"])
        self.assertEqual("2026-09-03T14:00:00Z", result["hourly_forecast"][0]["time"])
        self.assertEqual("2026-09-05T15:00:00Z", result["hourly_forecast"][-1]["time"])
        self.assertEqual(12, len(result["hourly_next_12h"]))
        self.assertTrue(all(r["weathercode"] is None and r["precipitation"] is None for r in result["hourly_forecast"]))

    def test_cams_has_all_28_and_six_pollen_without_health_classes(self):
        pollen = self.adapter.current("Pordenone")["pollen_data"]
        self.assertEqual(28, len(pollen["all_variables"]))
        self.assertEqual(6, len(pollen["values"]))
        self.assertEqual(0, pollen["values"]["ambrosia"])
        self.assertIsNone(pollen["level"])
        self.assertIsNone(pollen["main"])
        self.assertIsNone(pollen["health_classification"])
        self.assertEqual("2026-09-03T14:00:00Z", pollen["valid_at_utc"])

    def test_daily_partial_minmax_not_presented_as_full_day(self):
        result = self.adapter.forecast("Pordenone")
        self.assertTrue(result["forecast"][0]["partial_day"])
        self.assertIsNone(result["forecast"][0]["min_temp"])
        self.assertIsNotNone(result["forecast"][0]["sampled_min_temp"])
        self.assertFalse(result["forecast"][1]["partial_day"])
        self.assertIsNotNone(result["forecast"][1]["min_temp"])
        self.assertTrue(all(d["official_text"] == "" and d["weathercode"] is None for d in result["forecast"]))
        self.assertIsNone(result["official"])
        self.assertIsNone(result["osmer_structured"])

    def test_all_215_resolve_without_any_external_lookup(self):
        for town in self.icon["municipalities"]:
            result = self.adapter.current(town["id"])
            self.assertEqual(town["id"], result["data_quality"]["municipality_id"])
        self.assertEqual(215, self.adapter.metadata()["municipalities"])

    def test_unknown_mismatched_and_incomplete_coordinates_fail(self):
        for args in (("unknown",), ("Pordenone", 46.5, 13.5), ("Pordenone", 45.9, None),
                     ("Pordenone", True, 12.6), ("Pordenone", 0, 0)):
            with self.subTest(args=args), self.assertRaises(LocalSnapshotUnavailable):
                self.adapter.current(*args)

    def test_stale_visible_expired_fails_no_fallback(self):
        adapter = LocalSnapshotAdapter(self.icon_path, self.cams_path, now_provider=lambda: RUN+timedelta(hours=20))
        self.assertEqual("stale", adapter.current("Pordenone")["cache"]["status"])
        adapter._now_provider = lambda: RUN+timedelta(hours=25)
        self.assertFalse(adapter.metadata()["usable"])
        with self.assertRaisesRegex(LocalSnapshotUnavailable, "insufficient_future_coverage"):
            adapter.current("Pordenone")
        adapter._now_provider = lambda: RUN-timedelta(hours=1)
        with self.assertRaisesRegex(LocalSnapshotUnavailable, "future_run"):
            adapter.forecast("Pordenone")

    def test_unknown_native_code_never_becomes_clear(self):
        self.assertEqual("Condizione meteo non disponibile", canonical_condition(dict(status="unknown", code=99)))
        self.assertEqual("Temporale", canonical_condition(dict(status="valid", code=96)))

    def test_snapshots_loaded_once_and_returned_current_does_not_relabel_source_time(self):
        result = self.adapter.current("Pordenone")
        self.assertEqual(self.icon["generated_at_utc"], result["data_quality"]["generated_at_utc"])
        self.assertEqual(self.icon["run_utc"], result["source"]["icon"]["run_utc"])
        self.assertEqual(64, len(result["source"]["icon_snapshot"]["sha256"]))

    def test_rome_utc_conversion_handles_summer_and_winter(self):
        self.assertEqual(timedelta(hours=2), rome_time(RUN).utcoffset())
        self.assertEqual(timedelta(hours=1), rome_time(datetime(2026, 12, 1, tzinfo=timezone.utc)).utcoffset())
        self.assertEqual(timedelta(hours=2), rome_time(datetime(2026, 10, 25, 0, tzinfo=timezone.utc)).utcoffset())
        self.assertEqual(timedelta(hours=1), rome_time(datetime(2026, 10, 25, 1, tzinfo=timezone.utc)).utcoffset())


if __name__ == "__main__":
    unittest.main()
