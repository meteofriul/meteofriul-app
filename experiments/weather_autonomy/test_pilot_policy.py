"""Offline tests for experimental freshness, rain and two-hour policies."""

import copy
from datetime import datetime, timedelta, timezone
import unittest

from pilot_policy import assess_window, rain_interval, aggregate_two_hour


def iso_hour(hour):
    return (datetime(2026, 9, 3, tzinfo=timezone.utc) + timedelta(hours=hour)).isoformat().replace("+00:00", "Z")


class WindowTests(unittest.TestCase):
    def assess(self, now=12, start=0, stop=72, **kwargs):
        return assess_window(iso_hour(0), [iso_hour(h) for h in range(start, stop + 1)], iso_hour(now), **kwargs)

    def test_complete_fresh_run(self):
        actual = self.assess()
        self.assertEqual(actual, {"status": "fresh", "coverage_hours": 60.0, "run_age_hours": 12.0, "reason": "complete_window_from_fresh_run", "usable": True})

    def test_exact_default_fresh_boundary(self):
        self.assertEqual(self.assess(now=18)["status"], "fresh")

    def test_stale_is_explicit_but_usable_with_complete_coverage(self):
        actual = self.assess(now=19)
        self.assertEqual(actual["status"], "stale")
        self.assertTrue(actual["usable"])

    def test_30_hour_boundary_and_safety_cap(self):
        self.assertEqual(self.assess(now=30, stop=90)["status"], "stale")
        actual = self.assess(now=31, stop=90)
        self.assertEqual(actual["status"], "expired")
        self.assertEqual(actual["reason"], "run_exceeds_30_hour_safety_cap")
        self.assertFalse(actual["usable"])

    def test_incomplete_window_is_not_healthy_even_for_fresh_run(self):
        actual = self.assess(stop=59)
        self.assertEqual(actual["coverage_hours"], 47)
        self.assertEqual(actual["status"], "expired")
        self.assertEqual(actual["reason"], "insufficient_future_coverage")

    def test_exact_48_hour_endpoint_is_sufficient(self):
        self.assertTrue(self.assess(stop=60)["usable"])

    def test_fractional_now_requires_endpoint_after_48_hours(self):
        actual = assess_window(iso_hour(0), [iso_hour(h) for h in range(13, 61)], "2026-09-03T12:15:00Z")
        self.assertEqual(actual["status"], "expired")
        self.assertEqual(actual["coverage_hours"], 47.75)

    def test_first_future_hour_is_allowed_without_claiming_current_measurement(self):
        actual = assess_window(iso_hour(0), [iso_hour(h) for h in range(13, 62)], "2026-09-03T12:15:00Z")
        self.assertTrue(actual["usable"])

    def test_future_window_cannot_hide_gap_before_first_tick(self):
        actual = self.assess(start=14)
        self.assertEqual(actual["status"], "expired")
        self.assertEqual(actual["reason"], "missing_near_term_coverage")

    def test_past_only_window_has_no_remaining_coverage(self):
        actual = self.assess(now=12, stop=5)
        self.assertEqual(actual["coverage_hours"], 0)
        self.assertEqual(actual["status"], "expired")

    def test_future_run_is_invalid(self):
        actual = assess_window(iso_hour(12), [iso_hour(h) for h in range(12, 73)], iso_hour(11))
        self.assertEqual(actual["status"], "invalid")
        self.assertEqual(actual["reason"], "future_run")

    def test_rows_before_run_are_invalid(self):
        actual = assess_window(iso_hour(1), [iso_hour(h) for h in range(73)], iso_hour(12))
        self.assertEqual(actual["reason"], "forecast_before_run")

    def test_duplicates_gaps_and_reversed_order_are_invalid(self):
        for points in ([iso_hour(0), iso_hour(0)], [iso_hour(0), iso_hour(2)], [iso_hour(1), iso_hour(0)]):
            with self.subTest(points=points):
                self.assertEqual(assess_window(iso_hour(0), points, iso_hour(12))["status"], "invalid")

    def test_naive_non_utc_and_non_hourly_timestamps_are_invalid(self):
        invalid = ("2026-09-03T00:00:00", "2026-09-03T02:00:00+02:00", "2026-09-03T00:30:00Z", "2026-09-03T00:00:00.000001Z", None, "not a date")
        for value in invalid:
            with self.subTest(value=value):
                self.assertEqual(assess_window(iso_hour(0), [value], iso_hour(12))["status"], "invalid")

    def test_naive_now_and_fractional_run_are_invalid(self):
        for run, now in ((iso_hour(0), "2026-09-03T12:00:00"), ("2026-09-03T00:30:00Z", iso_hour(12))):
            self.assertEqual(assess_window(run, [iso_hour(h) for h in range(73)], now)["status"], "invalid")

    def test_zero_offset_and_z_are_same_timezone(self):
        points = [iso_hour(h).replace("Z", "+00:00") if h % 2 else iso_hour(h) for h in range(73)]
        self.assertTrue(assess_window(iso_hour(0), points, iso_hour(12))["usable"])

    def test_missing_empty_or_wrong_container_is_invalid(self):
        for points in (None, [], (), "2026-09-03T00:00:00Z", {"0": iso_hour(0)}):
            with self.subTest(points=points):
                self.assertEqual(assess_window(iso_hour(0), points, iso_hour(12))["status"], "invalid")

    def test_invalid_thresholds(self):
        for value in (0, -1, True, "48", float("nan"), float("inf")):
            with self.subTest(value=value):
                self.assertEqual(self.assess(required_hours=value)["reason"], "invalid_thresholds")
                self.assertEqual(self.assess(max_age_hours=value)["reason"], "invalid_thresholds")
        self.assertEqual(self.assess(max_age_hours=31)["status"], "invalid")

    def test_custom_freshness_and_horizon(self):
        self.assertEqual(self.assess(now=12, stop=36, required_hours=24, max_age_hours=6)["status"], "stale")

    def test_unrepresentable_horizon_is_invalid_instead_of_throwing(self):
        actual = self.assess(required_hours=1e308)
        self.assertEqual(actual["status"], "invalid")
        self.assertEqual(actual["reason"], "unrepresentable_horizon")


class RainTests(unittest.TestCase):
    def test_material_positive_increment(self):
        self.assertEqual(rain_interval(1, 2, .125, .125), {"value_mm": 1.0, "raw_increment_mm": 1.0, "status": "valid", "uncertainty_mm": .25})

    def test_positive_packed_change_within_combined_spacing_is_not_overstated(self):
        actual = rain_interval(1, 1.125, .125, .125)
        self.assertEqual(actual["status"], "positive_within_encoding_resolution")
        self.assertIsNone(actual["value_mm"])
        self.assertEqual(actual["raw_increment_mm"], .125)

    def test_small_negative_is_not_silently_clipped_to_dry(self):
        actual = rain_interval(1, .875, .125, .125)
        self.assertEqual(actual["status"], "negative_within_encoding_resolution")
        self.assertIsNone(actual["value_mm"])
        self.assertEqual(actual["raw_increment_mm"], -.125)

    def test_combined_spacing_keeps_a_boundary_increment_unquantified(self):
        actual = rain_interval(1, 1.25, .125, .125)
        self.assertEqual(actual["status"], "positive_within_encoding_resolution")
        self.assertIsNone(actual["value_mm"])
        self.assertEqual(actual["uncertainty_mm"], .25)

    def test_negative_boundary_is_uncertain_not_invalid(self):
        self.assertEqual(rain_interval(1, .75, .125, .125)["status"], "negative_within_encoding_resolution")

    def test_material_negative_increment_is_invalid(self):
        actual = rain_interval(1, .5, .125, .125)
        self.assertEqual(actual["status"], "invalid")
        self.assertIsNone(actual["value_mm"])
        self.assertEqual(actual["raw_increment_mm"], -.5)

    def test_equal_zero_accumulations_are_a_decoded_zero_increment(self):
        actual = rain_interval(0, 0, .125, .25)
        self.assertEqual(actual["value_mm"], 0)
        self.assertEqual(actual["status"], "valid")

    def test_identical_nonzero_accumulations_are_also_a_decoded_zero_increment(self):
        actual = rain_interval(4, 4, .125, .25)
        self.assertEqual(actual["status"], "valid")
        self.assertEqual(actual["value_mm"], 0)

    def test_sub_ulp_code_zero_reference_floor_is_normalized_explicitly(self):
        tiny = 3.5e-22
        actual = rain_interval(
            0,
            tiny,
            .0005,
            .001,
            previous_reference_mm=0,
            current_reference_mm=tiny,
        )
        self.assertEqual(actual["status"], "valid_reference_floor_normalized")
        self.assertEqual(actual["value_mm"], 0)
        self.assertEqual(actual["raw_increment_mm"], tiny)

    def test_material_code_zero_reference_floor_is_not_normalized_to_dry(self):
        actual = rain_interval(
            0,
            .01,
            .001,
            .001,
            previous_reference_mm=0,
            current_reference_mm=.01,
        )
        self.assertEqual(actual["status"], "valid")
        self.assertEqual(actual["value_mm"], .01)

    def test_one_quantum_signal_above_a_tiny_reference_floor_stays_unresolved(self):
        tiny = 3.5e-22
        actual = rain_interval(
            0,
            .001,
            .001,
            .001,
            previous_reference_mm=0,
            current_reference_mm=tiny,
        )
        self.assertEqual(actual["status"], "positive_within_encoding_resolution")
        self.assertIsNone(actual["value_mm"])
        self.assertEqual(actual["raw_increment_mm"], .001)

    def test_bad_accumulations_are_invalid(self):
        for value in (None, True, "1", -1, float("nan"), float("inf"), float("-inf"), 10 ** 999):
            for index in (0, 1):
                values = [0, 1, .125, .125]
                values[index] = value
                with self.subTest(value=value, index=index):
                    self.assertEqual(rain_interval(*values)["status"], "invalid")

    def test_bad_quantums_do_not_mask_raw_difference(self):
        for value in (None, True, "0.1", -1, float("nan"), float("inf")):
            for index in (2, 3):
                values = [0, 1, .125, .125]
                values[index] = value
                with self.subTest(value=value, index=index):
                    actual = rain_interval(*values)
                    self.assertEqual(actual["status"], "invalid")
                    self.assertEqual(actual["raw_increment_mm"], 1)
                    self.assertIsNone(actual["uncertainty_mm"])

    def test_uncertainty_overflow_is_invalid(self):
        self.assertEqual(rain_interval(0, 1, 1e308, 1e308)["status"], "invalid")

    def test_constant_zero_fields_have_effective_zero_quantum(self):
        actual = rain_interval(0, 0, 0, 0)
        self.assertEqual(actual, {"value_mm": 0.0, "raw_increment_mm": 0.0, "status": "valid", "uncertainty_mm": 0.0})

    def test_initial_constant_zero_does_not_add_spurious_uncertainty(self):
        actual = rain_interval(0, .5, 0, .125)
        self.assertEqual(actual["status"], "valid")
        self.assertEqual(actual["uncertainty_mm"], .125)
        self.assertEqual(actual["value_mm"], .5)

    def test_constant_nonzero_fields_are_valid_when_the_reference_proves_the_value(self):
        actual = rain_interval(
            1,
            1,
            0,
            0,
            previous_reference_mm=1,
            current_reference_mm=1,
        )
        self.assertEqual(actual["status"], "valid")
        self.assertEqual(actual["value_mm"], 0)

    def test_zero_quantum_with_value_different_from_reference_is_invalid(self):
        for inputs in ((1, 2, 0, .125), (1, 2, .125, 0), (1, 1, 0, 0)):
            with self.subTest(inputs=inputs):
                self.assertEqual(rain_interval(*inputs)["status"], "invalid")

    def test_constant_zero_current_value_can_preserve_uncertain_decrement(self):
        actual = rain_interval(.125, 0, .125, 0)
        self.assertEqual(actual["status"], "negative_within_encoding_resolution")
        self.assertEqual(actual["raw_increment_mm"], -.125)
        self.assertIsNone(actual["value_mm"])


class TwoHourTests(unittest.TestCase):
    def row(self, hour, rain=1, gust=10, temperature=20, flags=None):
        return {"valid_at_utc": iso_hour(hour), "precipitation_previous_hour_mm": rain, "wind_gust_m_s": gust, "temperature_c": temperature, "quality_flags": flags or []}

    def test_sum_rain_max_gust_and_sample_temperature_extrema(self):
        actual = aggregate_two_hour([self.row(1, 5, 20, 25), self.row(2, 1, 5, 15)])[0]
        self.assertEqual(actual, {"start_at_utc": iso_hour(0), "end_at_utc": iso_hour(2), "source_hours": 2, "precipitation_mm": 6.0, "wind_gust_max_m_s": 20.0, "temperature_min_c": 15.0, "temperature_max_c": 25.0, "temperature_end_c": 15.0, "status": "valid", "quality_flags": []})

    def test_windows_are_nonoverlapping_and_retain_every_hour(self):
        actual = aggregate_two_hour([self.row(h, rain=h) for h in range(1, 5)])
        self.assertEqual([r["precipitation_mm"] for r in actual], [3, 7])
        self.assertEqual(actual[0]["end_at_utc"], actual[1]["start_at_utc"])

    def test_missing_rain_does_not_become_zero_or_partial_sum(self):
        actual = aggregate_two_hour([self.row(1, rain=None), self.row(2, rain=2)])[0]
        self.assertIsNone(actual["precipitation_mm"])
        self.assertEqual(actual["status"], "incomplete")
        self.assertIn("missing_precipitation_previous_hour_mm", actual["quality_flags"])
        self.assertEqual(actual["wind_gust_max_m_s"], 10)

    def test_missing_gust_does_not_underestimate_two_hour_max(self):
        actual = aggregate_two_hour([self.row(1, gust=None), self.row(2, gust=5)])[0]
        self.assertIsNone(actual["wind_gust_max_m_s"])
        self.assertEqual(actual["status"], "incomplete")

    def test_missing_temperature_retains_only_known_endpoint(self):
        actual = aggregate_two_hour([self.row(1, temperature=None), self.row(2, temperature=-5)])[0]
        self.assertIsNone(actual["temperature_min_c"])
        self.assertIsNone(actual["temperature_max_c"])
        self.assertEqual(actual["temperature_end_c"], -5)
        self.assertEqual(actual["status"], "incomplete")

    def test_final_unpaired_hour_is_explicitly_incomplete(self):
        actual = aggregate_two_hour([self.row(h) for h in range(1, 4)])[-1]
        self.assertEqual(actual["source_hours"], 1)
        self.assertEqual(actual["status"], "incomplete")
        for key in ("precipitation_mm", "wind_gust_max_m_s", "temperature_min_c", "temperature_max_c"):
            self.assertIsNone(actual[key])
        self.assertEqual(actual["temperature_end_c"], 20)

    def test_flags_are_unioned_without_mutating_inputs(self):
        rows = [self.row(1, flags=["stale", "derived"]), self.row(2, flags=["stale"])]
        original = copy.deepcopy(rows)
        actual = aggregate_two_hour(rows)[0]
        self.assertEqual(actual["quality_flags"], ["derived", "stale"])
        self.assertEqual(rows, original)

    def test_gap_duplicate_reverse_and_cross_window_gap_are_invalid(self):
        for hours in ([1, 3], [1, 1], [2, 1], [1, 2, 4, 5]):
            with self.subTest(hours=hours):
                actual = aggregate_two_hour([self.row(h) for h in hours])[-1]
                self.assertEqual(actual["status"], "invalid")
                self.assertIn("non_contiguous_hours", actual["quality_flags"])
                self.assertIsNone(actual["precipitation_mm"])
                self.assertIsNone(actual["temperature_end_c"])

    def test_invalid_time_is_visible_instead_of_interpolated(self):
        for invalid_time in (None, "bad", "2026-09-03T00:00:00", "2026-09-03T00:30:00Z", "2026-09-03T02:00:00+02:00"):
            first = self.row(1)
            first["valid_at_utc"] = invalid_time
            with self.subTest(invalid_time=invalid_time):
                actual = aggregate_two_hour([first, self.row(2)])[0]
                self.assertEqual(actual["status"], "invalid")
                self.assertIsNone(actual["start_at_utc"])
                self.assertIsNone(actual["wind_gust_max_m_s"])

    def test_invalid_previous_window_boundary_is_not_ignored(self):
        rows = [self.row(h) for h in range(1, 5)]
        rows[1]["valid_at_utc"] = None
        actual = aggregate_two_hour(rows)
        self.assertEqual([r["status"] for r in actual], ["invalid", "invalid"])

    def test_negative_precipitation_or_gust_is_invalid(self):
        for field in ("precipitation_previous_hour_mm", "wind_gust_m_s"):
            first = self.row(1)
            first[field] = -1
            self.assertEqual(aggregate_two_hour([first, self.row(2)])[0]["status"], "invalid")

    def test_nonfinite_text_and_boolean_values_are_invalid(self):
        for field in ("precipitation_previous_hour_mm", "wind_gust_m_s", "temperature_c"):
            for value in (True, "2", float("nan"), float("inf"), float("-inf"), 10 ** 999):
                first = self.row(1)
                first[field] = value
                with self.subTest(field=field, value=value):
                    self.assertEqual(aggregate_two_hour([first, self.row(2)])[0]["status"], "invalid")

    def test_bad_flags_are_invalid(self):
        for flags in ("stale", None, [1], {"stale": True}):
            first = self.row(1)
            first["quality_flags"] = flags
            self.assertEqual(aggregate_two_hour([first, self.row(2)])[0]["status"], "invalid")

    def test_all_zero_intervals_are_valid(self):
        actual = aggregate_two_hour([self.row(1, rain=0, gust=0), self.row(2, rain=0, gust=0)])[0]
        self.assertEqual(actual["status"], "valid")
        self.assertEqual(actual["precipitation_mm"], 0)
        self.assertEqual(actual["wind_gust_max_m_s"], 0)

    def test_overflow_is_not_emitted_as_json_infinity(self):
        actual = aggregate_two_hour([self.row(1, rain=1e308), self.row(2, rain=1e308)])[0]
        self.assertEqual(actual["status"], "invalid")
        self.assertIsNone(actual["precipitation_mm"])

    def test_non_dict_row_is_invalid(self):
        self.assertEqual(aggregate_two_hour([None, self.row(2)])[0]["status"], "invalid")

    def test_empty_input_and_invalid_container(self):
        self.assertEqual(aggregate_two_hour([]), [])
        for value in (None, {}, "rows"):
            with self.assertRaises(ValueError):
                aggregate_two_hour(value)


if __name__ == "__main__":
    unittest.main()
