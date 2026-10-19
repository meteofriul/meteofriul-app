import unittest
import json
from pathlib import Path

from probe_snow_tolerance import aggregate_components, snow_window, replay


def known(value):
    return {"status": "valid", "value_mm": value}


def unresolved(budget):
    return {"status": "positive_within_encoding_resolution", "value_mm": None,
            "uncertainty_mm": budget, "packing_errors_mm": [budget / 4, budget / 4]}


def aggregate(*components):
    return aggregate_components(components, tolerance_mm=0.02, expected_components=2)


class SnowToleranceProbeTests(unittest.TestCase):
    def test_frozen_real_ciampac_sample(self):
        path = Path(__file__).parent / 'fixtures' / 'ciampac-snow-tolerance-20261019.json'
        result = replay(json.loads(path.read_text(encoding='utf-8')))
        early, current = result['windows']
        self.assertFalse(early['strict_contract_available'])
        self.assertEqual(early['proposed_experimental_decision'], 'evaluated_without_candidate')
        self.assertTrue(all(row['snow']['value_mm'] is None for row in early['rows']))
        self.assertIsNone(early['rows'][0]['precipitation_probability'])
        self.assertTrue(current['strict_contract_available'])
        self.assertTrue(all(row['snow']['state'] == 'known_zero' for row in current['rows']))

    def test_known_zero_stays_zero(self):
        self.assertEqual(aggregate(known(0), known(0))["state"], "known_zero")

    def test_real_resolution_null_stays_null(self):
        value = aggregate(known(0), unresolved(1.52587890625e-5))
        self.assertEqual(value["state"], "resolution_tolerance_verified")
        self.assertIsNone(value["value_mm"])

    def test_preserves_known_component(self):
        self.assertEqual(aggregate(known(0.7), unresolved(0.01))["known_component_sum_mm"], 0.7)

    def test_budget_is_for_final_field(self):
        self.assertEqual(aggregate(unresolved(0.012), unresolved(0.012))["state"], "unavailable")
        self.assertEqual(aggregate(unresolved(0.01), unresolved(0.01))["state"], "resolution_tolerance_verified")

    def test_missing_metadata_and_missing_values_do_not_become_zero(self):
        missing = unresolved(0.01)
        missing.pop("packing_errors_mm")
        for item in (missing, {}, known(None), known(True), known("0"), known(float("nan")), known(float("inf"))):
            with self.subTest(item=item):
                self.assertEqual(aggregate(known(0), item)["state"], "unavailable")

    def test_guard_above_tolerance(self):
        self.assertEqual(aggregate(known(0), unresolved(0.020001))["state"], "unavailable")

    def test_near_accumulation_threshold_and_indicator(self):
        def rows(values, probability):
            return [{"lead": i + 1, "snow": aggregate(known(v), unresolved(0.0001)),
                     "native_weather_code": 2, "precipitation_probability": probability}
                    for i, v in enumerate(values)]
        self.assertEqual(snow_window(rows([0.66, 0.66, 0.67], 100)), "evaluated_without_candidate")
        self.assertEqual(snow_window(rows([0.67, 0.67, 0.67], 100)), "evaluated_with_candidate")
        self.assertEqual(snow_window(rows([0.67, 0.67, 0.67], None)), "not_evaluable")

    def test_native_and_derived_codes_and_unavailable_input(self):
        rows = [{"lead": i + 1, "snow": aggregate(known(0), known(0)),
                 "native_weather_code": 2, "precipitation_probability": None} for i in range(3)]
        rows[0]["native_weather_code"] = 73
        self.assertEqual(snow_window(rows), "evaluated_with_candidate")
        rows[0]["native_weather_code"] = 2
        rows[0]["snow"] = aggregate(known(1), known(0))
        self.assertEqual(snow_window(rows), "evaluated_with_candidate")
        rows[0]["snow"] = aggregate(known(0), {})
        self.assertEqual(snow_window(rows), "not_evaluable")


if __name__ == '__main__':
    unittest.main()
