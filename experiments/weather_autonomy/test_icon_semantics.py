"""Offline tests of pilot WW meanings and honest capability declarations."""

import json
from fractions import Fraction
import unittest

from icon_semantics import icon_condition, pilot_capabilities


class IconConditionTests(unittest.TestCase):
    def test_clear_sky_requires_actual_zero_code(self):
        self.assertEqual(icon_condition(0), {"code": 0, "label": "Sereno", "status": "valid", "period": "previous_hour"})

    def test_cloud_cover_fallback_codes_are_distinct(self):
        self.assertEqual([icon_condition(code)["label"] for code in (1, 2, 3)], ["Poco nuvoloso", "Parzialmente nuvoloso", "Molto nuvoloso o coperto"])

    def test_supported_dwd_subset_is_exact(self):
        supported = {0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96}
        for code in range(100):
            with self.subTest(code=code):
                self.assertEqual(icon_condition(code)["status"], "valid" if code in supported else "unknown")

    def test_integer_valued_float_from_grib_is_valid(self):
        actual = icon_condition(61.0)
        self.assertEqual(actual["code"], 61)
        self.assertIs(type(actual["code"]), int)
        self.assertEqual(actual["label"], "Pioggia debole")

    def test_fractional_number_is_not_accepted_after_float_rounding(self):
        raw = Fraction(61_000_000_000_000_001, 1_000_000_000_000_000)
        self.assertEqual(float(raw), 61.0)
        self.assertEqual(icon_condition(raw)["status"], "invalid")

    def test_invalid_inputs_do_not_fall_back_to_clear(self):
        invalid = (None, True, False, "0", "61", [], {}, object(), float("nan"), float("inf"), float("-inf"), 1.5, 61.0000001, 10 ** 999)
        for value in invalid:
            with self.subTest(value=value):
                actual = icon_condition(value)
                self.assertEqual(actual["status"], "invalid")
                self.assertIsNone(actual["code"])
                self.assertNotEqual(actual["label"], "Sereno")

    def test_unknown_integer_code_is_preserved_for_diagnosis(self):
        for code in (-1, 4, 49, 99, 100, 255):
            with self.subTest(code=code):
                actual = icon_condition(code)
                self.assertEqual(actual["status"], "unknown")
                self.assertEqual(actual["code"], code)
                self.assertNotEqual(actual["label"], "Sereno")

    def test_icon_d2_code_99_is_not_assumed_for_icon_2i(self):
        self.assertEqual(icon_condition(99)["status"], "unknown")

    def test_code_96_does_not_claim_hail_is_necessarily_present(self):
        self.assertEqual(icon_condition(96)["label"], "Temporale con grandine o temporale forte")

    def test_fog_depositing_rime_is_not_ordinary_fog(self):
        self.assertEqual(icon_condition(45)["label"], "Nebbia")
        self.assertIn("brina", icon_condition(48)["label"])

    def test_freezing_precipitation_remains_explicit(self):
        for code in (56, 57, 66, 67):
            self.assertIn("gelata", icon_condition(code)["label"])

    def test_snow_grains_and_showers_are_distinct(self):
        self.assertEqual(icon_condition(77)["label"], "Granuli di neve")
        self.assertIn("Nevicata", icon_condition(71)["label"])
        self.assertIn("Rovesci di neve", icon_condition(85)["label"])

    def test_all_statuses_retain_previous_hour_period(self):
        for value in (0, 95, 99, None):
            self.assertEqual(icon_condition(value)["period"], "previous_hour")

    def test_all_results_are_strict_json_safe(self):
        for value in (0, 96, 99, None, float("nan"), float("inf")):
            json.dumps(icon_condition(value), allow_nan=False)

    def test_result_is_a_fresh_independent_dict(self):
        actual = icon_condition(61)
        actual["label"] = "not the real label"
        self.assertEqual(icon_condition(61)["label"], "Pioggia debole")


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.rows = pilot_capabilities()
        self.by_id = {row["id"]: row for row in self.rows}

    def test_schema_and_unique_ids(self):
        self.assertEqual(len(self.rows), len(self.by_id))
        for row in self.rows:
            self.assertEqual(set(row), {"id", "label", "status", "detail"})
            self.assertTrue(all(isinstance(value, str) and value for value in row.values()))

    def test_supported_meteo_is_explicitly_experimental(self):
        for item in ("temperature", "apparent_temperature", "pressure_msl", "relative_humidity", "wind", "wind_gust", "cloud_cover", "weather_condition", "precipitation_amount", "precipitation_phase"):
            with self.subTest(item=item):
                self.assertEqual(self.by_id[item]["status"], "experimental")

    def test_missing_products_are_not_fabricated(self):
        for item in ("precipitation_probability", "visibility", "five_day_forecast"):
            self.assertEqual(self.by_id[item]["status"], "missing")
        self.assertIn("deterministica", self.by_id["precipitation_probability"]["detail"])
        self.assertIn("72 ore", self.by_id["five_day_forecast"]["detail"])

    def test_cams_is_blocked_not_downloaded(self):
        actual = self.by_id["cams_pollen"]
        self.assertEqual(actual["status"], "blocked")
        self.assertIn("credenziali", actual["detail"])
        self.assertIn("non eseguito", actual["detail"])

    def test_official_bulletin_and_alerts_stay_separate(self):
        self.assertEqual(self.by_id["official_bulletin"]["status"], "unchanged")
        self.assertIn("OSMER", self.by_id["official_bulletin"]["detail"])
        self.assertEqual(self.by_id["official_alerts"]["status"], "unchanged")
        self.assertIn("Protezione Civile", self.by_id["official_alerts"]["detail"])

    def test_accuracy_comparison_is_still_pending(self):
        self.assertEqual(self.by_id["observations_comparison"]["status"], "pending")

    def test_local_geocoding_does_not_erase_open_meteo_provenance(self):
        actual = self.by_id["geocoding"]
        self.assertEqual(actual["status"], "local_catalog")
        self.assertIn("Open-Meteo", actual["detail"])
        self.assertIn("nessuna chiamata", actual["detail"])

    def test_derived_rh_and_water_equivalent_are_named(self):
        self.assertIn("derivata", self.by_id["relative_humidity"]["label"])
        self.assertIn("equivalente d'acqua", self.by_id["precipitation_phase"]["detail"])
        self.assertIn("centimetri", self.by_id["precipitation_phase"]["detail"])

    def test_calls_return_independent_lists_and_dicts(self):
        self.rows[0]["status"] = "wrong"
        self.rows.pop()
        actual = pilot_capabilities()
        self.assertEqual(len(actual), 18)
        self.assertEqual(actual[0]["status"], "experimental")

    def test_all_capabilities_are_json_safe(self):
        json.dumps(self.rows, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
