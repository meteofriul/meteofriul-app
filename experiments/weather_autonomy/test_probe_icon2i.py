"""Offline tests: run with python -m unittest discover -s experiments/weather_autonomy."""

import unittest
from unittest.mock import Mock, patch

from probe_icon2i import Links, POINTS, decode_message, message_length, relative_humidity_from_dewpoint


class ProbeTests(unittest.TestCase):
    def test_link_parser_retains_only_actual_links(self):
        parser = Links()
        parser.feed('<a href="2026090212/">run</a><img src="other"><a>none</a>')
        self.assertEqual(parser.hrefs, ["2026090212/"])

    def test_grib_header_length(self):
        header = b"GRIB\x00\x00\x00\x02" + (1158428).to_bytes(8, "big")
        self.assertEqual(message_length(header), 1158428)

    def test_grib_header_rejects_bad_or_unbounded_messages(self):
        for data in (b"", b"<html>not GRIB!!!", b"GRIB\x00\x00\x00\x01" + (1024).to_bytes(8, "big"), b"GRIB\x00\x00\x00\x02" + (10**9).to_bytes(8, "big")):
            with self.subTest(data=data), self.assertRaises(ValueError):
                message_length(data)

    def test_dewpoint_at_temperature_means_saturation(self):
        self.assertEqual(relative_humidity_from_dewpoint(20, 20), 100)

    def test_reasonable_unsaturated_humidity(self):
        self.assertAlmostEqual(relative_humidity_from_dewpoint(20, 10), 52.56, delta=0.1)

    def test_humidity_rejects_invalid_inputs(self):
        for t, td in ((20, 21), (float("nan"), 10), (20, float("inf")), (-237.7, -240)):
            with self.subTest(t=t, td=td), self.assertRaises(ValueError):
                relative_humidity_from_dewpoint(t, td)

    def test_small_supersaturation_is_not_silently_clipped(self):
        with self.assertRaisesRegex(ValueError, "no silent saturation clipping"):
            relative_humidity_from_dewpoint(20, 20.05)


class EcCodesStub:
    """Metadata/nearest stub only: this does not claim to validate GRIB decoding."""

    def __init__(self, metadata):
        self.metadata = dict(metadata)
        self.handle = object()
        self.codes_new_from_message = Mock(return_value=self.handle)
        self.codes_set = Mock(side_effect=self._set)
        self.codes_get = Mock(side_effect=lambda handle, key: self.metadata[key])
        self.codes_grib_find_nearest = Mock(side_effect=self._nearest)
        self.codes_release = Mock()

    def _set(self, handle, key, value):
        self.metadata[key] = value

    def _nearest(self, handle, lat, lon, npoints):
        return [{"lat": lat, "lon": lon, "distance": 0.2, "value": 293.15}]


class DecodeMessageTests(unittest.TestCase):
    """Exercise fail-closed metadata checks without real ecCodes or networking."""

    def metadata(self, **changes):
        values = {
            "shortName": "2t", "paramId": 167, "name": "2 metre temperature",
            "units": "K", "typeOfLevel": "heightAboveGround", "level": 2,
            "dataDate": 20260902, "dataTime": 1200,
            "validityDate": 20260903, "validityTime": 1200,
            "startStep": 24, "endStep": 24, "stepUnits": "0m",
            "stepType": "instant", "gridType": "regular_ll",
            "numberOfPoints": 1440000, "Ni": 1200, "Nj": 1200,
            "uvRelativeToGrid": 0, "iDirectionIncrementInDegrees": 0.02,
            "jDirectionIncrementInDegrees": 0.02, "missingValue": 9999,
        }
        values.update(changes)
        return values

    def rain_metadata(self, **changes):
        values = self.metadata(
            shortName="tp", paramId=228228, name="Total precipitation",
            units="kg m**-2", typeOfLevel="surface", level=0,
            startStep=0, stepType="accum",
        )
        values.update(changes)
        return values

    def assert_decode_rejected(self, metadata, field, message):
        stub = EcCodesStub(metadata)
        with patch.dict("sys.modules", {"eccodes": stub}):
            with self.assertRaisesRegex(ValueError, message):
                decode_message(b"stub-message", field, "2026090212", 24)
        stub.codes_release.assert_called_once_with(stub.handle)
        stub.codes_grib_find_nearest.assert_not_called()

    def test_success_normalizes_time_units_extracts_points_and_releases(self):
        stub = EcCodesStub(self.metadata())
        with patch.dict("sys.modules", {"eccodes": stub}):
            result = decode_message(b"stub-message", "T_2M", "2026090212", 24)
        stub.codes_new_from_message.assert_called_once_with(b"stub-message")
        stub.codes_set.assert_called_once_with(stub.handle, "stepUnits", 1)
        stub.codes_release.assert_called_once_with(stub.handle)
        self.assertEqual(result["metadata"]["stepUnits"], 1)
        self.assertEqual(result["metadata"]["shortName"], "2t")
        self.assertEqual(set(result["points"]), set(POINTS))
        self.assertEqual(stub.codes_grib_find_nearest.call_count, len(POINTS))
        for point in result["points"].values():
            self.assertEqual(point["value"], 293.15)

    def test_temperature_and_dewpoint_cannot_be_swapped(self):
        for field, wrong_name in (("T_2M", "2d"), ("TD_2M", "2t")):
            with self.subTest(field=field):
                self.assert_decode_rejected(
                    self.metadata(shortName=wrong_name), field, "Unexpected parameter",
                )

    def test_wrong_vertical_type_or_height_is_rejected(self):
        for changes in ({"level": 10}, {"typeOfLevel": "isobaricInhPa"}):
            with self.subTest(changes=changes):
                self.assert_decode_rejected(self.metadata(**changes), "T_2M", "Wrong vertical level")

    def test_wrong_units_are_rejected(self):
        self.assert_decode_rejected(self.metadata(units="C"), "T_2M", "Unexpected units")

    def test_wrong_run_date_or_cycle_is_rejected(self):
        for changes in ({"dataDate": 20260901}, {"dataTime": 0}):
            with self.subTest(changes=changes):
                self.assert_decode_rejected(self.metadata(**changes), "T_2M", "Run/lead mismatch")

    def test_wrong_forecast_lead_is_rejected(self):
        self.assert_decode_rejected(self.metadata(endStep=25), "T_2M", "Run/lead mismatch")

    def test_instantaneous_temperature_cannot_be_an_average(self):
        self.assert_decode_rejected(self.metadata(stepType="avg"), "T_2M", "Unexpected time processing")

    def test_rain_must_be_accumulated_not_instantaneous(self):
        self.assert_decode_rejected(
            self.rain_metadata(stepType="instant"), "TOT_PREC", "not an accumulation since model start",
        )

    def test_rain_accumulation_must_start_at_model_initialization(self):
        self.assert_decode_rejected(
            self.rain_metadata(startStep=23), "TOT_PREC", "not an accumulation since model start",
        )

    def test_rain_accumulation_since_model_start_succeeds(self):
        stub = EcCodesStub(self.rain_metadata())
        with patch.dict("sys.modules", {"eccodes": stub}):
            result = decode_message(b"stub-message", "TOT_PREC", "2026090212", 24)
        self.assertEqual(result["metadata"]["startStep"], 0)
        self.assertEqual(result["metadata"]["stepType"], "accum")
        stub.codes_release.assert_called_once_with(stub.handle)

    def test_icon_cloud_and_msl_pressure_short_names_are_accepted(self):
        cases = (
            ("CLCT", {"shortName": "clct", "units": "%", "typeOfLevel": "surface", "level": 0}),
            ("PMSL", {"shortName": "pmsl", "units": "Pa", "typeOfLevel": "meanSea", "level": 0}),
        )
        for field, changes in cases:
            with self.subTest(field=field):
                stub = EcCodesStub(self.metadata(**changes))
                with patch.dict("sys.modules", {"eccodes": stub}):
                    result = decode_message(b"stub-message", field, "2026090212", 24)
                self.assertEqual(result["metadata"]["shortName"], changes["shortName"])
                stub.codes_release.assert_called_once_with(stub.handle)


if __name__ == "__main__":
    unittest.main()
