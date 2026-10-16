"""Synthetic fixtures only; no GRIB/network/credential dependency."""

from pathlib import Path
import unittest

from decode_cams_region import RegionDecoder, analyze_payload, compare_pordenone, daily_province_extremes, transport_projection
from decode_cams import EXPECTED_VARIABLES
from test_decode_cams import FakeEcCodes, metadata
from cams_test_fixtures import TEST_DATE

POINTS = [dict(slug="pordenone", name="Pordenone", province="PN", latitude=45.95689, longitude=12.66051),
          dict(slug="shared-test", name="Shared test", province="PN", latitude=45.952, longitude=12.651)]


class RegionalEcCodes(FakeEcCodes):
    def __init__(self):
        super().__init__()
        self.extractions = []

    def codes_grib_find_nearest_multiple(self, handle, land, lats, lons):
        self.mapping_calls += 1
        return [dict(lat=45.95, lon=12.65, distance=1.1, index=4, value=handle["value"]) for _ in lats]

    def codes_get_elements(self, handle, key, indexes):
        self.extractions.append(list(indexes))
        return [handle["value"] for _ in indexes]


def complete(values=(0, 2e-8), variables=("ozone",)):
    ec = RegionalEcCodes()
    decoder = RegionDecoder(POINTS, date=TEST_DATE, ec=ec, variables=variables, leads=(0, 1))
    for variable in variables:
        for lead, value in enumerate(values):
            decoder.decode(dict(meta=metadata(variable, lead), value=value))
    return decoder, ec, decoder.finish()


class RegionTests(unittest.TestCase):
    def test_region_decoder_and_file_entrypoint_require_explicit_date_or_plan(self):
        with self.assertRaises(TypeError):
            RegionDecoder(POINTS, ec=RegionalEcCodes())
        from decode_cams_region import run_file
        with self.assertRaises(TypeError):
            run_file(Path("never-opened.grib"))

    def test_full_synthetic_215_by_28_by_97_matrix(self):
        points = [dict(POINTS[0], slug=f"synthetic-{number}", name=f"Synthetic {number}") for number in range(215)]
        ec = RegionalEcCodes()
        decoder = RegionDecoder(points, date=TEST_DATE, ec=ec)
        for variable in EXPECTED_VARIABLES:
            for lead in range(97):
                decoder.decode(dict(meta=metadata(variable, lead), value=0))
        payload = decoder.finish()
        analysis = analyze_payload(payload)
        self.assertEqual(583940, analysis["municipality_values"])
        self.assertEqual(2716, analysis["unique_fields"])
        self.assertEqual(2716, analysis["unique_cell_values"])
        self.assertEqual(2716, ec.released)
        self.assertEqual(1, ec.mapping_calls)
        self.assertEqual(0, sum(analysis["anomaly_counts_unique_cells"].values()))

    def test_215_cap_unique_ids_and_crop(self):
        for points in ([], POINTS * 2, [dict(POINTS[0], latitude=44)], [dict(POINTS[0], latitude=True)]):
            with self.subTest(points=points), self.assertRaises(ValueError):
                RegionDecoder(points, date=TEST_DATE, ec=RegionalEcCodes())

    def test_one_mapping_shared_cell_and_unique_extraction(self):
        decoder, ec, payload = complete()
        self.assertEqual(1, ec.mapping_calls)
        self.assertEqual([[4]], ec.extractions)
        self.assertEqual(2, ec.released)
        self.assertEqual(1, len(payload["cells"]))
        self.assertEqual(2, len(payload["municipalities"]))
        self.assertEqual([0, 20], payload["cells"][0]["values"]["ozone"])
        self.assertEqual({}, payload["cells"][0]["quality_flags"])
        self.assertTrue(payload["variables"][0]["quality_flags"])
        analysis = analyze_payload(payload)
        self.assertEqual(4, analysis["municipality_values"])
        self.assertEqual(2, analysis["unique_cell_values"])
        self.assertEqual(["pordenone", "shared-test"], analysis["variable_summary"][0]["maximum"]["municipality_ids"])

    def test_missing_negative_nonfinite_are_not_zeros(self):
        for bad, flag in ((9999, "missing_model_value"), (None, "missing_model_value"), (-1, "negative_concentration_not_clipped"),
                          (float("nan"), "nonfinite_or_nonnumeric_model_value"), (True, "nonfinite_or_nonnumeric_model_value")):
            with self.subTest(bad=bad):
                _, _, payload = complete(values=(0, bad))
                cell = payload["cells"][0]
                self.assertEqual([0, None], cell["values"]["ozone"])
                self.assertEqual([flag], cell["quality_flags"]["ozone"]["1"])
                analysis = analyze_payload(payload)
                self.assertEqual(1, analysis["anomaly_counts_unique_cells"][flag])
                self.assertEqual(2, analysis["anomaly_counts_municipalities"][flag])

    def test_daily_peaks_keep_timestamp_and_partial_day_explicit(self):
        _, _, payload = complete()
        result = daily_province_extremes(payload)
        self.assertEqual(1, len(result))
        day = result[0]
        self.assertEqual("PN", day["province"])
        self.assertFalse(day["complete_utc_day"])
        self.assertEqual(2, day["forecast_instants_in_day"])
        self.assertEqual(20, day["maximum"]["value"])
        self.assertEqual("2026-09-04T01:00:00Z", day["maximum"]["valid_at_utc"])

    def test_incomplete_duplicate_and_changed_grid_fail(self):
        decoder = RegionDecoder(POINTS, date=TEST_DATE, ec=RegionalEcCodes(), variables=("ozone",), leads=(0, 1))
        message = dict(meta=metadata(), value=0)
        decoder.decode(message)
        with self.assertRaises(ValueError):
            decoder.finish()
        with self.assertRaises(ValueError):
            decoder.decode(message)
        bad = metadata(step=1)
        bad["md5GridSection"] = "new-grid"
        with self.assertRaises(ValueError):
            decoder.decode(dict(meta=bad, value=0))

    def test_coordinate_index_and_shared_value_consistency(self):
        for change in (dict(index=0), dict(distance=11), dict(lat=46.0)):
            ec = RegionalEcCodes()
            ec.codes_grib_find_nearest_multiple = lambda *a, **k: [dict(lat=45.95, lon=12.65, distance=1.1, index=4, value=0, **{}) | change for _ in POINTS]
            decoder = RegionDecoder(POINTS, date=TEST_DATE, ec=ec, variables=("ozone",), leads=(0,))
            with self.subTest(change=change), self.assertRaises(ValueError):
                decoder.decode(dict(meta=metadata(), value=0))
        ec = RegionalEcCodes()
        ec.codes_grib_find_nearest_multiple = lambda *a, **k: [dict(lat=45.95, lon=12.65, distance=1.1, index=4, value=value) for value in (0, 1)]
        decoder = RegionDecoder(POINTS, date=TEST_DATE, ec=ec, variables=("ozone",), leads=(0,))
        with self.assertRaises(ValueError):
            decoder.decode(dict(meta=metadata(), value=0))

    def test_pm_mass_inconsistency_is_reported_not_corrected(self):
        decoder = RegionDecoder(POINTS, date=TEST_DATE, ec=RegionalEcCodes(), variables=("particulate_matter_2.5um", "particulate_matter_10um"), leads=(0,))
        for variable, value in (("particulate_matter_2.5um", 2e-8), ("particulate_matter_10um", 1e-8)):
            decoder.decode(dict(meta=metadata(variable), value=value))
        payload = decoder.finish()
        report = analyze_payload(payload)
        self.assertEqual(1, report["pm2_5_greater_than_pm10"]["unique_cell_hours"])
        self.assertEqual(2, report["pm2_5_greater_than_pm10"]["municipality_hours"])
        self.assertEqual([20], payload["cells"][0]["values"]["particulate_matter_2.5um"])

    def test_pordenone_comparison_uses_coordinates_not_crop_index(self):
        _, _, payload = complete()
        prior = dict(schema_version=1, dataset=payload["dataset"], run_utc=payload["run_utc"],
                     grid_point=dict(lat=45.95, lon=12.65, index=999), variables=[dict(id="ozone", hourly=[
                         dict(valid_at_utc=t, value=v, raw_value=r, units="ug/m3", source_units="kg/m3")
                         for t, v, r in zip(payload["times_utc"], (0, 20), (0, 2e-8))])])
        comparison = compare_pordenone(payload, prior)
        self.assertTrue(comparison["exact_equal_converted_values"])
        prior["variables"][0]["hourly"][1]["value"] = 21
        self.assertEqual(1, compare_pordenone(payload, prior)["changed_converted_values"])
        prior["grid_point"]["lat"] = 46.05
        self.assertEqual("not_comparable_different_native_cell", compare_pordenone(payload, prior)["status"])

    def test_display_projection_preserves_unrounded_values_flags_and_provenance(self):
        _, _, payload = complete(values=(1.234567890123e-8, -1))
        payload["sources"]["grib"] = dict(filename="source.grib", sha256="source-hash", bytes=100)
        audit = transport_projection(payload, municipality_id="pordenone")
        display = transport_projection(payload, municipality_id="pordenone", audit=False)
        self.assertEqual(1, len(audit["municipalities"]))
        self.assertEqual(1, len(display["municipalities"]))
        self.assertEqual(audit["cells"][0]["values"], display["cells"][0]["values"])
        self.assertEqual(audit["cells"][0]["quality_flags"], display["cells"][0]["quality_flags"])
        self.assertNotIn("raw_values", display["cells"][0])
        self.assertIn("raw_values", payload["cells"][0])
        self.assertEqual("source-hash", display["sources"]["grib"]["sha256"])
        self.assertEqual(payload["times_utc"], display["times_utc"])
        self.assertEqual(payload["variables"][0]["quality_flags"], display["variables"][0]["quality_flags"])
        self.assertEqual(0, display["variables"][0]["source_identity"]["constituentType"])
        with self.assertRaises(ValueError):
            transport_projection(payload, municipality_id="invented")


if __name__ == "__main__":
    unittest.main()
