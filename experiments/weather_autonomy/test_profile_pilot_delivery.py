"""Offline packing checks; synthetic input is never presented as live data."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from profile_pilot_delivery import (
    COLUMNS, ENCODING_FIELDS, MAX_INPUT_BYTES, TWO_HOUR_COLUMNS, VALUE_COLUMNS,
    compact_json, iso, make_candidate, measure_candidate, run_profile,
)


def fixture(generated="2026-09-03T13:30:00Z", towns=2):
    start = datetime(2026, 9, 3, tzinfo=timezone.utc)
    rows = []
    for step in range(73):
        row = {key: 1.0 for key in VALUE_COLUMNS}
        row.update(valid_at_utc=iso(start + timedelta(hours=step)), temperature_c=20 + step / 10,
                   precipitation_probability_pct=None, visibility_m=None,
                   condition=dict(code=0, label="Sereno", status="valid"),
                   quality_flags=[], precipitation_encoding={
                       key: dict(value_mm=0.0, uncertainty_mm=0.01, status="valid", raw_increment_mm=0.0)
                       for key in ENCODING_FIELDS})
        rows.append(row)
    return dict(schema_version=1, status="partial_pilot_not_production",
                generated_at_utc=generated, run_utc="2026-09-03T00:00:00Z",
                validation=dict(status="fresh", usable=True),
                sources=dict(icon=dict(status="acquired_and_decoded", run_utc="2026-09-03T00:00:00Z",
                    attribution="Institution", license="CC BY 4.0", url="https://example.invalid/model/")),
                capabilities=[dict(id="pollen", status="blocked"), dict(id="probability", status="missing"),
                              dict(id="temperature", status="experimental"), dict(id="observations", status="pending")],
                municipalities=[dict(id=f"town-{index}", name=f"Comune {index}", latitude=46.0, longitude=13.0,
                    grid_point=dict(lat=46.0, lon=13.0, distance=0.0, index=1), current=None,
                    hourly=deepcopy(rows), two_hourly=[]) for index in range(towns)])


class DeliveryPackingTests(unittest.TestCase):
    def test_minute_offset_retains_49_future_points_and_current(self):
        payload = fixture()
        candidate = make_candidate(payload)
        self.assertEqual(49, len(candidate["times_utc"]))
        self.assertEqual("2026-09-03T14:00:00Z", candidate["times_utc"][0])
        self.assertEqual("2026-09-05T14:00:00Z", candidate["times_utc"][-1])
        self.assertEqual(48.5, candidate["validation"]["coverage_hours"])
        self.assertEqual("2026-09-03T13:00:00Z", candidate["municipalities"][0]["current"]["valid_at_utc"])
        self.assertIsNone(payload["municipalities"][0]["current"])

    def test_exact_hour_retains_48_future_points(self):
        candidate = make_candidate(fixture("2026-09-03T13:00:00Z"))
        self.assertEqual(48, len(candidate["times_utc"]))
        self.assertEqual("2026-09-05T13:00:00Z", candidate["times_utc"][-1])

    def test_nulls_are_not_zero_and_components_flags_survive(self):
        payload = fixture()
        row = payload["municipalities"][0]["hourly"][14]
        row.update(precipitation_previous_hour_mm=None, wind_gust_m_s=None,
                   quality_flags=["TOT_PREC:below_encoding_resolution"])
        row["precipitation_encoding"]["RAIN_GSP"]["value_mm"] = None
        candidate = make_candidate(payload)
        packed = dict(zip(COLUMNS, candidate["municipalities"][0]["hourly"][0]))
        self.assertIsNone(packed["precipitation_previous_hour_mm"])
        self.assertIsNone(packed["wind_gust_m_s"])
        self.assertIsNone(packed["grid_scale_rain_previous_hour_mm"])
        self.assertEqual(0, packed["weather_code"])
        self.assertEqual(row["quality_flags"], packed["quality_flags"])
        self.assertNotIn("raw_increment_mm", compact_json(candidate).decode())

    def test_two_hourly_is_true_aggregation_and_unpaired_is_explicit(self):
        payload = fixture()
        payload["municipalities"][0]["hourly"][14]["wind_gust_m_s"] = 99.0
        candidate = make_candidate(payload)
        aggregates = candidate["municipalities"][0]["two_hourly"]
        first = dict(zip(TWO_HOUR_COLUMNS, aggregates[0]))
        last = dict(zip(TWO_HOUR_COLUMNS, aggregates[-1]))
        self.assertEqual(99.0, first["wind_gust_max_m_s"])
        self.assertEqual(2.0, first["precipitation_mm"])
        self.assertEqual("incomplete", last["status"])
        self.assertIsNone(last["precipitation_mm"])

    def test_manifest_and_sources_survive_without_fabricated_probability(self):
        candidate = make_candidate(fixture())
        self.assertEqual({"pollen", "probability", "observations"}, {item["id"] for item in candidate["capability_gaps"]})
        self.assertEqual("CC BY 4.0", candidate["source"]["license"])
        self.assertTrue(all(row[COLUMNS.index("precipitation_probability_pct")] is None
                            for town in candidate["municipalities"] for row in town["hourly"]))

    def test_rejects_invalid_coverage_and_status(self):
        for mutation in (
            lambda p: p["validation"].update(usable=False),
            lambda p: p["municipalities"][0]["hourly"].pop(15),
            lambda p: p["municipalities"][0]["hourly"].pop(0),
            lambda p: p.update(generated_at_utc="2026-09-04T01:00:00Z"),
            lambda p: p.update(generated_at_utc="2026-09-03T13:30:00"),
        ):
            with self.subTest(mutation=mutation):
                payload = fixture()
                mutation(payload)
                with self.assertRaises(ValueError):
                    make_candidate(payload)

    def test_invalid_values_and_missing_columns_fail_closed(self):
        for value in (True, float("nan"), float("inf"), "20"):
            payload = fixture()
            payload["municipalities"][0]["hourly"][14]["temperature_c"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_candidate(payload)
        payload = fixture()
        payload["municipalities"][0]["hourly"][14]["precipitation_probability_pct"] = 30
        with self.assertRaises(ValueError):
            make_candidate(payload)

    def test_exact_sizes_hashes_and_no_self_referential_metrics(self):
        candidate = make_candidate(fixture())
        report = measure_candidate(candidate)
        encoded = compact_json(candidate)
        self.assertEqual(len(encoded), report["json_bytes"])
        self.assertEqual(len(gzip.compress(encoded, compresslevel=6, mtime=0)), report["gzip_bytes"])
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), report["sha256"])
        self.assertNotIn("metrics", candidate)
        self.assertNotIn("json_bytes", candidate)
        self.assertEqual(2, report["municipality_count"])
        self.assertEqual(min(item["gzip_bytes"] for item in report["single_municipality_sizes"]), report["single_municipality_min_gzip_bytes"])

    def test_outputs_are_new_and_source_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            source, candidate, report = [Path(directory) / name for name in ("source.json", "candidate.json", "report.json")]
            original = compact_json(fixture())
            source.write_bytes(original)
            result = run_profile(source, candidate, report)
            self.assertEqual(original, source.read_bytes())
            self.assertEqual(candidate.stat().st_size, result["json_bytes"])
            with self.assertRaises(ValueError):
                run_profile(source, candidate, report)
            with self.assertRaises(ValueError):
                run_profile(source, source, report)

    def test_input_cap_checked_before_parsing_and_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            source, candidate, report = [Path(directory) / name for name in ("source.json", "candidate.json", "report.json")]
            source.write_bytes(b"{}")
            with patch("profile_pilot_delivery.MAX_INPUT_BYTES", 1):
                with self.assertRaises(ValueError):
                    run_profile(source, candidate, report)
            self.assertFalse(candidate.exists())
            self.assertFalse(report.exists())
            self.assertEqual(64 * 1024**2, MAX_INPUT_BYTES)


if __name__ == "__main__":
    unittest.main()
