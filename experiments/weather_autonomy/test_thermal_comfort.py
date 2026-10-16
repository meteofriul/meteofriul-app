"""Isolated standard-library tests; no app imports, downloads or provider calls.

Run from repository root:
python -B -m unittest discover -s experiments/weather_autonomy -p test_thermal_comfort.py -v
"""

from dataclasses import asdict
import json
import math
import unittest

try:
    from .thermal_comfort import (
        apparent_temperature_c, calculate_thermal_comfort, heat_index_c,
        kelvin_to_celsius, vapour_pressure_hpa, wind_chill_c, wind_speed_to_m_s,
    )
except ImportError:
    from thermal_comfort import (
        apparent_temperature_c, calculate_thermal_comfort, heat_index_c,
        kelvin_to_celsius, vapour_pressure_hpa, wind_chill_c, wind_speed_to_m_s,
    )


def from_fahrenheit(value):
    return (value - 32) * 5 / 9


class ApparentTemperatureTests(unittest.TestCase):
    def test_bom_reference_arithmetic_warm_humid(self):
        self.assertAlmostEqual(apparent_temperature_c(30, 70, 2), 34.368334291495394, places=10)

    def test_bom_reference_arithmetic_mild(self):
        self.assertAlmostEqual(apparent_temperature_c(20, 50, 1), 19.148242312858148, places=10)

    def test_zero_celsius_saturated_vapour_pressure(self):
        self.assertEqual(vapour_pressure_hpa(0, 100), 6.105)
        self.assertAlmostEqual(apparent_temperature_c(0, 100, 5), -5.48535, places=10)

    def test_zero_humidity_is_not_missing(self):
        self.assertEqual(vapour_pressure_hpa(20, 0), 0)
        self.assertEqual(apparent_temperature_c(20, 0, 0), 16)

    def test_no_silent_clipping_of_negative_apparent_temperature(self):
        self.assertLess(apparent_temperature_c(-20, 70, 10), -20)

    def test_wind_changes_apparent_temperature_without_unit_confusion(self):
        calm = apparent_temperature_c(30, 70, 0)
        breezy = apparent_temperature_c(30, 70, wind_speed_to_m_s(36, "km/h"))
        self.assertAlmostEqual(calm - breezy, 7)

    def test_mathematical_vapour_pressure_singularity_rejected(self):
        for value in (-237.7, -240):
            with self.subTest(value=value), self.assertRaises(ValueError):
                vapour_pressure_hpa(value, 50)


class UnitConversionTests(unittest.TestCase):
    def test_kelvin(self):
        self.assertEqual(kelvin_to_celsius(273.15), 0)
        self.assertAlmostEqual(kelvin_to_celsius(303.15), 30)
        with self.assertRaises(ValueError):
            kelvin_to_celsius(-1)

    def test_wind_units(self):
        self.assertEqual(wind_speed_to_m_s(3.6, "km/h"), 1)
        self.assertEqual(wind_speed_to_m_s(1, "mph"), 0.44704)
        self.assertAlmostEqual(wind_speed_to_m_s(1, "knots"), 0.5144444444444445)
        self.assertEqual(wind_speed_to_m_s(0, "m/s"), 0)

    def test_unknown_units_rejected(self):
        for unit in ("kmh", "miles", None, []):
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                wind_speed_to_m_s(2, unit)


class HeatIndexTests(unittest.TestCase):
    def test_rothfusz_reference_vector(self):
        estimate = heat_index_c(from_fahrenheit(90), 70)
        self.assertEqual(estimate.status, "estimated")
        self.assertAlmostEqual(estimate.value_c, from_fahrenheit(105.9220206), places=8)

    def test_dry_air_correction(self):
        estimate = heat_index_c(from_fahrenheit(100), 10)
        self.assertAlmostEqual(estimate.value_c, from_fahrenheit(94.12248266218747), places=8)

    def test_humid_air_correction(self):
        estimate = heat_index_c(from_fahrenheit(86), 90)
        self.assertAlmostEqual(estimate.value_c, from_fahrenheit(105.3943646), places=8)

    def test_screening_uses_averaged_simple_formula(self):
        # At 80 F / 40%, the initial expression is 79.58 F and averaging is
        # still below 80 F. A temperature-only >=80 F switch is incorrect.
        estimate = heat_index_c(from_fahrenheit(80), 40)
        self.assertIsNone(estimate.value_c)
        self.assertEqual(estimate.status, "not_applicable")
        self.assertIsNotNone(heat_index_c(from_fahrenheit(80), 50).value_c)
        # At 81.1 F / 0%, the initial expression is only 78.91 F, but its
        # average with T is 80.005 F: screening must include that averaging.
        self.assertIsNotNone(heat_index_c(from_fahrenheit(81.1), 0).value_c)

    def test_no_heat_index_for_cold_air(self):
        for temperature in (-20, 0, 15, 25):
            with self.subTest(temperature=temperature):
                self.assertIsNone(heat_index_c(temperature, 50).value_c)

    def test_extreme_inputs_are_withheld_not_extrapolated(self):
        for temperature_f, humidity in ((120, 50), (110, 100), (100, 100)):
            with self.subTest(temperature_f=temperature_f, humidity=humidity):
                estimate = heat_index_c(from_fahrenheit(temperature_f), humidity)
                self.assertIsNone(estimate.value_c)
                self.assertEqual(estimate.status, "outside_experiment_domain")

    def test_chart_edge_uses_conservative_wetter_row(self):
        self.assertIsNotNone(heat_index_c(from_fahrenheit(98), 70).value_c)
        self.assertIsNone(heat_index_c(from_fahrenheit(98), 70.001).value_c)
        self.assertIsNotNone(heat_index_c(from_fahrenheit(96), 70.001).value_c)

    def test_high_humidity_chart_edge(self):
        self.assertIsNotNone(heat_index_c(from_fahrenheit(90), 100).value_c)
        self.assertIsNone(heat_index_c(from_fahrenheit(90.01), 100).value_c)


class WindChillTests(unittest.TestCase):
    def test_nws_reference_arithmetic(self):
        estimate = wind_chill_c(0, wind_speed_to_m_s(10, "mph"))
        self.assertEqual(estimate.status, "estimated")
        self.assertAlmostEqual(estimate.value_c, -4.596030966868121, places=10)

    def test_nws_temperature_boundary(self):
        self.assertIsNotNone(wind_chill_c(10, 5).value_c)
        self.assertIsNone(wind_chill_c(10.0001, 5).value_c)

    def test_nws_wind_boundary_is_strict(self):
        threshold = wind_speed_to_m_s(3, "mph")
        self.assertIsNone(wind_chill_c(0, threshold).value_c)
        self.assertIsNotNone(wind_chill_c(0, math.nextafter(threshold, math.inf)).value_c)

    def test_calm_air_has_no_wind_chill_fallback(self):
        estimate = wind_chill_c(-10, 0)
        self.assertEqual(estimate.status, "not_applicable")
        self.assertIsNone(estimate.value_c)


class InputAndResultTests(unittest.TestCase):
    def test_missing_non_finite_text_and_bool_rejected_for_each_input(self):
        valid = {"temperature_c": 20, "relative_humidity_pct": 50, "wind_10m_m_s": 2}
        invalid = (None, float("nan"), float("inf"), -float("inf"), "20", True, False)
        for name in valid:
            for value in invalid:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    calculate_thermal_comfort(**(valid | {name: value}))

    def test_humidity_outside_percent_range_rejected(self):
        for humidity in (-0.001, 100.001):
            with self.subTest(humidity=humidity), self.assertRaises(ValueError):
                calculate_thermal_comfort(temperature_c=20, relative_humidity_pct=humidity, wind_10m_m_s=2)

    def test_negative_wind_rejected_not_clipped(self):
        with self.assertRaises(ValueError):
            calculate_thermal_comfort(temperature_c=20, relative_humidity_pct=50, wind_10m_m_s=-0.1)

    def test_impossible_temperature_rejected(self):
        for temperature in (-273.15, -300):
            with self.subTest(temperature=temperature), self.assertRaises(ValueError):
                calculate_thermal_comfort(temperature_c=temperature, relative_humidity_pct=50, wind_10m_m_s=2)

    def test_indices_stay_separate_in_hot_conditions(self):
        result = calculate_thermal_comfort(temperature_c=30, relative_humidity_pct=70, wind_10m_m_s=2)
        self.assertIsNotNone(result.apparent_temperature.value_c)
        self.assertIsNotNone(result.heat_index.value_c)
        self.assertIsNone(result.wind_chill.value_c)
        self.assertNotEqual(result.apparent_temperature.value_c, result.heat_index.value_c)
        self.assertFalse(hasattr(result, "feels_like"))

    def test_indices_stay_separate_in_cold_conditions(self):
        result = calculate_thermal_comfort(temperature_c=-10, relative_humidity_pct=70, wind_10m_m_s=5)
        self.assertIsNotNone(result.apparent_temperature.value_c)
        self.assertIsNotNone(result.wind_chill.value_c)
        self.assertIsNone(result.heat_index.value_c)
        self.assertNotEqual(result.apparent_temperature.value_c, result.wind_chill.value_c)

    def test_heat_index_does_not_pretend_to_include_actual_wind(self):
        inputs = {"temperature_c": 30, "relative_humidity_pct": 70}
        calm = calculate_thermal_comfort(**inputs, wind_10m_m_s=0)
        windy = calculate_thermal_comfort(**inputs, wind_10m_m_s=10)
        self.assertEqual(calm.heat_index, windy.heat_index)
        self.assertNotEqual(calm.apparent_temperature, windy.apparent_temperature)

    def test_result_serializes_without_nan_or_infinity(self):
        result = calculate_thermal_comfort(temperature_c=20, relative_humidity_pct=50, wind_10m_m_s=2)
        payload = json.loads(json.dumps(asdict(result), allow_nan=False))
        self.assertEqual(set(payload), {"apparent_temperature", "heat_index", "wind_chill"})
        self.assertIsNone(payload["heat_index"]["value_c"])
        self.assertIsNone(payload["wind_chill"]["value_c"])


if __name__ == "__main__":
    unittest.main()
