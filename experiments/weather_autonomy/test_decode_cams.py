"""Synthetic offline fixtures: never confused with CAMS live retrieval."""

from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

from decode_cams import (
    AREA, EXPECTED_VARIABLES, MAX_MESSAGE_BYTES, META_KEYS, VARIABLE_IDENTITIES,
    CamsPointDecoder, convert_value, decoder_plan_options, grib_messages, identify_variable, run_time,
    verify_metadata,
)
from cams_test_fixtures import TEST_DATE, valid_plan


def metadata(variable="ozone", step=0, date=TEST_DATE):
    valid = run_time(date) + timedelta(hours=step)
    number, constituent = VARIABLE_IDENTITIES[variable]
    return dict(edition=2, centre=85, subCentre=2, discipline=0, parameterCategory=20,
                parameterNumber=number, constituentType=constituent, shortName="unknown", paramId=0,
                name="unknown", units="unknown", typeOfLevel="heightAboveGround", level=0,
                typeOfFirstFixedSurface=103, typeOfSecondFixedSurface=255,
                dataDate=int(date.replace("-", "")), dataTime=0, validityDate=int(valid.strftime("%Y%m%d")),
                validityTime=int(valid.strftime("%H%M")), stepType="instant", startStep=step,
                endStep=step, stepUnits=1, gridType="regular_ll", Ni=3, Nj=3, numberOfPoints=9,
                md5GridSection="verified-grid", latitudeOfFirstGridPointInDegrees=46.05,
                longitudeOfFirstGridPointInDegrees=12.55, latitudeOfLastGridPointInDegrees=45.85,
                longitudeOfLastGridPointInDegrees=12.75, iDirectionIncrementInDegrees=0.1,
                jDirectionIncrementInDegrees=0.1, iScansNegatively=0, jScansPositively=0,
                jPointsAreConsecutive=0, alternativeRowScanning=0,
                productDefinitionTemplateNumber=40, typeOfProcessedData=1, typeOfGeneratingProcess=2,
                productionStatusOfProcessedData=2, tablesVersion=21, localTablesVersion=0)


class FakeEcCodes:
    def __init__(self):
        self.released = 0
        self.mapping_calls = 0

    def codes_new_from_message(self, message):
        return message

    def codes_set(self, handle, key, value):
        pass

    def codes_get(self, handle, key):
        return 9999 if key == "missingValue" else handle["meta"][key]

    codes_get_long = codes_get

    def codes_release(self, handle):
        self.released += 1

    def codes_grib_find_nearest(self, handle, lat, lon, npoints):
        self.mapping_calls += 1
        return [dict(lat=45.95, lon=12.65, distance=1.1, index=4, value=handle["value"])]

    def codes_get_elements(self, handle, key, indices):
        return [handle["value"]]


class CamsDecoderTests(unittest.TestCase):
    def test_date_is_explicit_and_verified_plan_drives_full_decoder_options(self):
        with self.assertRaises(TypeError):
            run_time()
        with self.assertRaises(TypeError):
            verify_metadata(metadata())
        with self.assertRaises(TypeError):
            CamsPointDecoder(ec=FakeEcCodes())
        plan = valid_plan(area=AREA)
        options = decoder_plan_options(plan, "a" * 64, AREA)
        self.assertEqual(options["date"], TEST_DATE)
        self.assertEqual(options["expected_variables"], tuple(plan["request_groups"][0]["request"]["variable"]))
        self.assertEqual(options["expected_leads"], tuple(range(97)))

    def test_plan_date_mismatch_in_grib_fails_and_releases_handle(self):
        ec = FakeEcCodes()
        decoder = CamsPointDecoder(
            date="2026-09-05", ec=ec, expected_variables=("ozone",), expected_leads=(0,)
        )
        with self.assertRaisesRegex(ValueError, "date/time mismatch"):
            decoder.decode(dict(meta=metadata(), value=0))
        self.assertEqual(ec.released, 1)

    def test_identifies_28_documented_constituents_not_generic_paramid(self):
        self.assertEqual(28, len(EXPECTED_VARIABLES))
        self.assertEqual(28, len(VARIABLE_IDENTITIES))
        for variable in VARIABLE_IDENTITIES:
            self.assertEqual(variable, identify_variable(metadata(variable)))

    def test_new_components_have_distinct_verified_chemical_identities(self):
        self.assertEqual((0, 62003), VARIABLE_IDENTITIES["pm2.5_ammonium"])
        self.assertEqual((0, 62004), VARIABLE_IDENTITIES["pm2.5_nitrate"])
        self.assertEqual((0, 62006), VARIABLE_IDENTITIES["pm2.5_sulphate"])

    def test_unknown_identity_not_guessed(self):
        meta = metadata()
        meta["constituentType"] = 65000
        with self.assertRaises(ValueError):
            identify_variable(meta)

    def test_mass_conversion_and_unit_provenance(self):
        result = convert_value(3.5e-8, metadata())
        self.assertAlmostEqual(35.0, result["value"])
        self.assertEqual("kg/m3", result["source_units"])
        self.assertEqual("ug/m3", result["units"])
        self.assertEqual("unknown", result["raw_units"])
        self.assertTrue(result["quality_flags"])

    def test_count_conversion_retains_fractional_pollen(self):
        result = convert_value(1.75, metadata("grass_pollen"))
        self.assertEqual(1.75, result["value"])
        self.assertEqual("grains/m3", result["units"])

    def test_zero_is_valid_not_missing(self):
        result = convert_value(0, metadata(), missing_value=9999)
        self.assertEqual(0, result["value"])
        self.assertEqual("valid", result["status"])

    def test_negative_missing_nonfinite_not_replaced_with_zero(self):
        for value, status in ((-1e-10, "invalid"), (9999, "missing"), (None, "missing"),
                              (float("nan"), "invalid"), (float("inf"), "invalid"), (True, "invalid")):
            with self.subTest(value=value):
                result = convert_value(value, metadata(), missing_value=9999)
                self.assertEqual(status, result["status"])
                self.assertIsNone(result["value"])
                json.dumps(result, allow_nan=False)
        self.assertEqual(-1.0, convert_value(-1.0, metadata())["raw_value"])

    def test_incompatible_explicit_units_fail(self):
        for unit in ("kg kg**-1", "ug/m3", "Pa", "K"):
            meta = metadata()
            meta["units"] = unit
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                convert_value(1, meta)

    def test_metadata_accepts_realistic_surface_and_height_zero(self):
        self.assertEqual(96, verify_metadata(metadata(step=96), TEST_DATE))
        meta = metadata()
        meta.update(typeOfLevel="surface", typeOfFirstFixedSurface=1)
        self.assertEqual(0, verify_metadata(meta, TEST_DATE))

    def test_wrong_model_vertical_time_grid_are_rejected(self):
        for change in (dict(centre=98), dict(subCentre=1), dict(level=50), dict(typeOfSecondFixedSurface=103),
                       dict(dataTime=1200), dict(validityTime=200), dict(startStep=0, endStep=1),
                       dict(stepType="accum"), dict(Ni=1000), dict(gridType="reduced_gg"),
                       dict(iDirectionIncrementInDegrees=0.25), dict(latitudeOfFirstGridPointInDegrees=60.0),
                       dict(productDefinitionTemplateNumber=0), dict(typeOfProcessedData=0),
                       dict(typeOfGeneratingProcess=0), dict(jPointsAreConsecutive=1),
                       dict(alternativeRowScanning=1), dict(longitudeOfLastGridPointInDegrees=12.65)):
            meta = metadata()
            meta.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_metadata(meta, TEST_DATE)

    def test_same_grid_index_reused_and_matrix_complete(self):
        ec = FakeEcCodes()
        decoder = CamsPointDecoder(date=TEST_DATE, ec=ec, expected_variables=("ozone", "grass_pollen"), expected_leads=(0, 1))
        for variable in ("ozone", "grass_pollen"):
            for step in (1, 0):
                decoder.decode(dict(meta=metadata(variable, step), value=0.0))
        result = decoder.finish()
        self.assertEqual(4, result["fields"])
        self.assertEqual(1, ec.mapping_calls)
        self.assertEqual(4, ec.released)
        self.assertEqual("2026-09-04T00:00:00Z", result["variables"][0]["hourly"][0]["valid_at_utc"])

    def test_duplicates_fail_and_handle_is_released(self):
        ec = FakeEcCodes()
        decoder = CamsPointDecoder(date=TEST_DATE, ec=ec, expected_variables=("ozone",), expected_leads=(0,))
        message = dict(meta=metadata(), value=0.0)
        decoder.decode(message)
        with self.assertRaises(ValueError):
            decoder.decode(message)
        self.assertEqual(2, ec.released)

    def test_grid_changes_fail_before_wrong_point_extraction(self):
        decoder = CamsPointDecoder(date=TEST_DATE, ec=FakeEcCodes(), expected_variables=("ozone",), expected_leads=(0, 1))
        decoder.decode(dict(meta=metadata(), value=0.0))
        meta = metadata(step=1)
        meta["md5GridSection"] = "different"
        with self.assertRaises(ValueError):
            decoder.decode(dict(meta=meta, value=1.0))

    def test_nearest_index_must_agree_with_coordinates(self):
        ec = FakeEcCodes()
        ec.codes_grib_find_nearest = lambda *args, **kwargs: [dict(lat=45.95, lon=12.65, distance=1.1, index=0, value=0.0)]
        decoder = CamsPointDecoder(date=TEST_DATE, ec=ec, expected_variables=("ozone",), expected_leads=(0,))
        with self.assertRaises(ValueError):
            decoder.decode(dict(meta=metadata(), value=0.0))
        self.assertEqual(1, ec.released)

    def test_missing_time_or_variable_not_reported_as_complete(self):
        decoder = CamsPointDecoder(date=TEST_DATE, ec=FakeEcCodes(), expected_variables=("ozone", "grass_pollen"), expected_leads=(0, 1))
        decoder.decode(dict(meta=metadata(), value=0.0))
        with self.assertRaises(ValueError):
            decoder.finish()

    def test_bad_point_or_expected_selection_rejected(self):
        for options in (dict(point=(0, 0)), dict(area=(46, 13, 46, 13)), dict(expected_leads=(0, 0)),
                        dict(expected_variables=("invented",)), dict(point=(True, 12.6))):
            with self.subTest(options=options), self.assertRaises(ValueError):
                CamsPointDecoder(date=TEST_DATE, ec=FakeEcCodes(), **options)

    def test_framing_rejects_bad_header_trailer_truncation_and_extra_bytes(self):
        valid = b"GRIB" + b"\x00\x00\x00\x02" + (20).to_bytes(8, "big") + b"7777"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.grib"
            path.write_bytes(valid + valid)
            self.assertEqual([valid, valid], list(grib_messages(path)))
            for broken in (b"<html>" * 5, valid[:-1], valid[:-4] + b"xxxx", valid+b"extra", valid[:8]+(MAX_MESSAGE_BYTES+1).to_bytes(8, "big")+b"7777"):
                path.write_bytes(broken)
                with self.subTest(broken=broken[:16]), self.assertRaises(ValueError):
                    list(grib_messages(path))


if __name__ == "__main__":
    unittest.main()
