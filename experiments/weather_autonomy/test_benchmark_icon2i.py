"""Offline contract tests; synthetic GRIB headers are not physical model data."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from benchmark_icon2i import (
    COLUMNS,
    FIELDS,
    PointDecoder,
    SHORT_NAMES,
    compact_json,
    derive_row,
    forecast_steps,
    load_points,
    message_span,
    split_messages,
    validate_metadata,
)
from probe_icon2i import BASE, PublicHTTPError, PublicReader
from thermal_comfort import calculate_thermal_comfort


RUN = "2026090212"
RUN_TIME = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)


def synthetic_message(length=32, fill=b"x"):
    """Exercise framing only, without pretending to form a decodable GRIB."""
    if length < 20:
        raise ValueError("Synthetic frame must contain header and end marker")
    return b"GRIB\x00\x00\x00\x02" + length.to_bytes(8, "big") + fill * (length - 20) + b"7777"


def metadata(field="T_2M", step=24, **changes):
    _, level_type, level, units = FIELDS[field]
    valid = RUN_TIME + timedelta(hours=step)
    result = {
        "shortName": SHORT_NAMES[field],
        "paramId": 167,
        "units": units or "Code table",
        "typeOfLevel": level_type,
        "level": level,
        "dataDate": 20260902,
        "dataTime": 1200,
        "validityDate": int(valid.strftime("%Y%m%d")),
        "validityTime": int(valid.strftime("%H%M")),
        "startStep": 0 if field == "TOT_PREC" else step,
        "endStep": step,
        "stepUnits": 1,
        "stepType": "accum" if field == "TOT_PREC" else "instant",
        "gridType": "regular_ll",
        "Ni": 761,
        "Nj": 761,
        "numberOfPoints": 761 * 761,
        "uvRelativeToGrid": 0,
        "md5GridSection": "synthetic-grid",
    }
    result.update(changes)
    return result


def raw_values(**changes):
    result = {
        "T_2M": 293.15,
        "TD_2M": 283.15,
        "U_10M": 3.0,
        "V_10M": 4.0,
        "PMSL": 101325.0,
        "CLCT": 37.5,
        "TOT_PREC": 5.25,
        "WW": 3.0,
    }
    result.update(changes)
    return result


def row_dict(raw=None, previous_rain=4.0):
    return dict(zip(COLUMNS, derive_row(raw or raw_values(), previous_rain), strict=True))


class ForecastStepsTests(unittest.TestCase):
    def test_has_49_consecutive_instants_covering_48_hours(self):
        steps = forecast_steps(RUN_TIME, RUN_TIME + timedelta(hours=8, minutes=17))
        self.assertEqual(steps, list(range(9, 58)))
        self.assertEqual(len(steps), 49)
        self.assertEqual(steps[-1] - steps[0], 48)

    def test_exact_hour_starts_at_the_next_hour(self):
        self.assertEqual(forecast_steps(RUN_TIME, RUN_TIME + timedelta(hours=8))[0], 9)

    def test_first_run_hour_retains_step_zero_for_precipitation_baseline(self):
        steps = forecast_steps(RUN_TIME, RUN_TIME + timedelta(minutes=1))
        rain_steps = [steps[0] - 1] + steps
        self.assertEqual(steps, list(range(1, 50)))
        self.assertEqual(rain_steps, list(range(50)))
        self.assertEqual(len(rain_steps), 50)

    def test_latest_permitted_start_finishes_at_72_hours(self):
        steps = forecast_steps(RUN_TIME, RUN_TIME + timedelta(hours=23, minutes=59))
        self.assertEqual((steps[0], steps[-1]), (24, 72))

    def test_old_run_without_a_full_window_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not cover"):
            forecast_steps(RUN_TIME, RUN_TIME + timedelta(hours=24))

    def test_future_run_without_preceding_accumulation_is_rejected(self):
        with self.assertRaises(ValueError):
            forecast_steps(RUN_TIME, RUN_TIME - timedelta(hours=1))

    def test_timezone_equivalent_now_produces_same_utc_steps(self):
        local = datetime(2026, 9, 2, 22, 17, tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(forecast_steps(RUN_TIME, local), list(range(9, 58)))


class AuthoritativePointsTests(unittest.TestCase):
    def test_default_points_use_official_local_sources_not_legacy_coordinates(self):
        points, digest = load_points()

        self.assertEqual(215, len(points))
        self.assertEqual(64, len(digest))
        self.assertEqual(215, len({point["istatCode"] for point in points}))
        self.assertTrue(all(
            point["coordinateSource"].startswith(("irdat_", "istat_"))
            for point in points
        ))


class MessageSpanTests(unittest.TestCase):
    def test_constant_size_message_ranges(self):
        self.assertEqual(message_span(100, 100, 0, 0), (0, 99))
        self.assertEqual(message_span(100, 100, 9, 16), (900, 1699))
        self.assertEqual(message_span(100, 100, 72, 72), (7200, 7299))

    def test_short_first_accumulation_is_accounted_for(self):
        self.assertEqual(message_span(20, 100, 0, 0), (0, 19))
        self.assertEqual(message_span(20, 100, 0, 7), (0, 719))
        self.assertEqual(message_span(20, 100, 1, 8), (20, 819))
        self.assertEqual(message_span(20, 100, 72, 72), (7120, 7219))

    def test_adjacent_batches_have_neither_gaps_nor_overlap(self):
        first = message_span(20, 100, 0, 7)
        second = message_span(20, 100, 8, 15)
        self.assertEqual(first[1] + 1, second[0])

    def test_invalid_step_ranges_are_rejected(self):
        for start, end in ((-1, 0), (5, 4), (0, 73), (73, 73)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                message_span(20, 100, start, end)


class SplitMessagesTests(unittest.TestCase):
    def test_frames_are_returned_unmodified_in_order(self):
        frames = [synthetic_message(20), synthetic_message(32), synthetic_message(44, b"y")]
        self.assertEqual(list(split_messages(b"".join(frames), 3)), frames)

    def test_truncated_header_is_rejected(self):
        with self.assertRaises(ValueError):
            list(split_messages(synthetic_message()[:15], 1))

    def test_truncated_body_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Truncated/corrupt"):
            list(split_messages(synthetic_message()[:-1], 1))

    def test_second_frame_truncation_is_rejected(self):
        with self.assertRaises(ValueError):
            list(split_messages(synthetic_message() + synthetic_message()[:-5], 2))

    def test_end_marker_is_required(self):
        with self.assertRaisesRegex(ValueError, "Truncated/corrupt"):
            list(split_messages(synthetic_message()[:-4] + b"0000", 1))

    def test_extra_byte_is_rejected_when_iterator_is_exhausted(self):
        with self.assertRaisesRegex(ValueError, "Unexpected extra"):
            list(split_messages(synthetic_message() + b"x", 1))

    def test_extra_complete_message_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unexpected extra"):
            list(split_messages(synthetic_message() * 2, 1))

    def test_too_few_messages_is_rejected(self):
        with self.assertRaises(ValueError):
            list(split_messages(synthetic_message(), 2))

    def test_invalid_signature_or_edition_is_rejected(self):
        good = synthetic_message()
        for data in (b"HTML" + good[4:], good[:7] + b"\x01" + good[8:]):
            with self.subTest(data=data), self.assertRaises(ValueError):
                list(split_messages(data, 1))


class MetadataTests(unittest.TestCase):
    def test_accepts_all_eight_expected_field_contracts(self):
        for field in FIELDS:
            with self.subTest(field=field):
                validate_metadata(metadata(field), field, RUN, 24)

    def test_rejects_wrong_parameter_and_level(self):
        for changes in ({"shortName": "2d"}, {"typeOfLevel": "isobaricInhPa"}, {"level": 1000}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "Parameter/level"):
                validate_metadata(metadata(**changes), "T_2M", RUN, 24)

    def test_rejects_wrong_physical_units(self):
        for field in FIELDS:
            if field == "WW":
                continue
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Unit mismatch"):
                validate_metadata(metadata(field, units="wrong-units"), field, RUN, 24)

    def test_mslp_must_be_mean_sea_level_not_surface_pressure(self):
        with self.assertRaisesRegex(ValueError, "Parameter/level"):
            validate_metadata(metadata("PMSL", typeOfLevel="surface"), "PMSL", RUN, 24)

    def test_rejects_wrong_run_lead_or_time_units(self):
        for changes in ({"dataDate": 20260901}, {"dataTime": 0}, {"endStep": 25}, {"stepUnits": 0}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "Run/lead"):
                validate_metadata(metadata(**changes), "T_2M", RUN, 24)

    def test_rejects_wrong_validity_date_hour_or_minute(self):
        for changes in ({"validityDate": 20260904}, {"validityTime": 1300}, {"validityTime": 1201}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "Validity timestamp"):
                validate_metadata(metadata(**changes), "T_2M", RUN, 24)

    def test_precipitation_must_accumulate_from_same_run(self):
        for changes in ({"startStep": 1}, {"stepType": "instant"}, {"stepType": "avg"}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "Rain is not accumulated"):
                validate_metadata(metadata("TOT_PREC", **changes), "TOT_PREC", RUN, 24)

    def test_temperature_cannot_be_an_average_or_accumulation(self):
        for step_type in ("avg", "accum"):
            with self.subTest(step_type=step_type), self.assertRaisesRegex(ValueError, "instantaneous"):
                validate_metadata(metadata(stepType=step_type), "T_2M", RUN, 24)

    def test_instantaneous_variable_requires_matching_start_and_end(self):
        with self.assertRaises(ValueError):
            validate_metadata(metadata(startStep=0), "T_2M", RUN, 24)

    def test_grid_representation_and_point_count_are_verified(self):
        for changes in ({"gridType": "unstructured_grid"}, {"numberOfPoints": 10}, {"Ni": 760}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "grid"):
                validate_metadata(metadata(**changes), "T_2M", RUN, 24)

    def test_grid_dimensions_must_be_positive(self):
        for changes in ({"Ni": -761, "Nj": -761}, {"Ni": 0, "numberOfPoints": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_metadata(metadata(**changes), "T_2M", RUN, 24)

    def test_both_wind_components_require_earth_relative_orientation(self):
        for field in ("U_10M", "V_10M"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "grid rotation"):
                validate_metadata(metadata(field, uvRelativeToGrid=1), field, RUN, 24)


class EcCodesPointStub:
    """Isolate PointDecoder control flow; never decode or fetch a real GRIB."""

    def __init__(self):
        self.metadata = metadata(missingValue=9999.0)
        self.nearest = [
            {"lat": 45.96, "lon": 12.65, "distance": 0.8, "index": 0, "value": 293.15},
            {"lat": 46.50, "lon": 13.575, "distance": 1.0, "index": 452, "value": 283.15},
        ]
        self.values = [294.15, 284.15]
        self.handles = []
        self.handle_metadata = {}
        self.codes_new_from_message = Mock(side_effect=self._new)
        self.codes_set = Mock(side_effect=self._set)
        self.codes_get = Mock(side_effect=lambda handle, key: self.handle_metadata[handle][key])
        self.codes_grib_find_nearest_multiple = Mock(side_effect=lambda *args: [dict(row) for row in self.nearest])
        self.codes_get_elements = Mock(side_effect=lambda *args: list(self.values))
        self.codes_release = Mock()

    def _new(self, _message):
        handle = object()
        self.handles.append(handle)
        self.handle_metadata[handle] = dict(self.metadata)
        return handle

    def _set(self, handle, key, value):
        self.handle_metadata[handle][key] = value


class PointDecoderTests(unittest.TestCase):
    def setUp(self):
        self.ec = EcCodesPointStub()
        self.points = [
            {"slug": "pordenone", "latitude": 45.95689, "longitude": 12.66051},
            {"slug": "tarvisio", "latitude": 46.50567, "longitude": 13.58689},
        ]
        with patch.dict("sys.modules", {"eccodes": self.ec}):
            self.decoder = PointDecoder(self.points)

    def decode_first(self):
        return self.decoder.decode(b"synthetic-first-message", "T_2M", RUN, 24)

    def prepare_second(self, **changes):
        self.ec.metadata = metadata(step=25, missingValue=9999.0, **changes)

    def decode_second(self):
        return self.decoder.decode(b"synthetic-second-message", "T_2M", RUN, 25)

    def assert_every_handle_released(self):
        self.assertEqual(self.ec.codes_release.call_count, len(self.ec.handles))
        self.assertEqual([call.args[0] for call in self.ec.codes_release.call_args_list], self.ec.handles)

    def test_first_message_maps_points_once_and_uses_nearest_values(self):
        values, meta = self.decode_first()
        self.assertEqual(values, [293.15, 283.15])
        self.assertEqual(meta["stepUnits"], 1)
        self.ec.codes_set.assert_called_once_with(self.ec.handles[0], "stepUnits", 1)
        self.ec.codes_grib_find_nearest_multiple.assert_called_once_with(
            self.ec.handles[0], False, [45.95689, 46.50567], [12.66051, 13.58689]
        )
        self.ec.codes_get_elements.assert_not_called()
        self.assertEqual(self.decoder.indexes, [0, 452])
        self.assertEqual(self.decoder.grid_hash, "synthetic-grid")
        self.assertEqual(self.decoder.mapping_builds, 1)
        self.assertEqual(self.decoder.seen, {("T_2M", RUN, 24)})
        self.assertNotIn("value", self.decoder.grid_points[0])
        self.assert_every_handle_released()

    def test_second_message_reuses_indexes_and_fetches_only_point_elements(self):
        self.decode_first()
        first_indexes = self.decoder.indexes
        self.prepare_second()
        values, _ = self.decode_second()
        self.assertEqual(values, [294.15, 284.15])
        self.assertIs(self.decoder.indexes, first_indexes)
        self.ec.codes_get_elements.assert_called_once_with(self.ec.handles[1], "values", first_indexes)
        self.assertEqual(self.ec.codes_grib_find_nearest_multiple.call_count, 1)
        self.assertEqual(self.decoder.mapping_builds, 1)
        self.assertEqual(len(self.decoder.seen), 2)
        self.assert_every_handle_released()

    def test_indexes_may_be_shared_between_different_municipalities(self):
        self.ec.nearest[1]["index"] = 0
        self.ec.nearest[1]["value"] = 293.15
        values, _ = self.decode_first()
        self.assertEqual(values, [293.15, 293.15])
        self.assertEqual(self.decoder.indexes, [0, 0])
        self.assertEqual(len(self.decoder.grid_points), 2)
        self.assert_every_handle_released()

    def test_mapping_is_reused_across_fields_with_identical_grid(self):
        self.decode_first()
        self.ec.metadata = metadata("TD_2M", missingValue=9999.0)
        self.ec.values = [280.15, 275.15]
        values, _ = self.decoder.decode(b"synthetic-dewpoint", "TD_2M", RUN, 24)
        self.assertEqual(values, self.ec.values)
        self.assertEqual(self.ec.codes_grib_find_nearest_multiple.call_count, 1)
        self.assertIn(("TD_2M", RUN, 24), self.decoder.seen)
        self.assert_every_handle_released()

    def test_grid_hash_change_refuses_reusing_indexes_and_releases_handle(self):
        self.decode_first()
        self.prepare_second(md5GridSection="changed-grid")
        with self.assertRaisesRegex(ValueError, "Grid changed"):
            self.decode_second()
        self.ec.codes_get_elements.assert_not_called()
        self.assertEqual(self.ec.codes_grib_find_nearest_multiple.call_count, 1)
        self.assertEqual(self.decoder.seen, {("T_2M", RUN, 24)})
        self.assert_every_handle_released()

    def test_duplicate_identity_fails_before_allocating_another_handle(self):
        self.decode_first()
        with self.assertRaisesRegex(ValueError, "Duplicate GRIB"):
            self.decode_first()
        self.assertEqual(self.ec.codes_new_from_message.call_count, 1)
        self.assert_every_handle_released()

    def test_metadata_failure_releases_handle_without_attempting_mapping(self):
        self.ec.metadata["units"] = "wrong"
        with self.assertRaisesRegex(ValueError, "Unit mismatch"):
            self.decode_first()
        self.ec.codes_grib_find_nearest_multiple.assert_not_called()
        self.assertEqual(self.decoder.seen, set())
        self.assert_every_handle_released()

    def test_normalization_failure_releases_handle(self):
        self.ec.codes_set.side_effect = RuntimeError("cannot set step units")
        with self.assertRaisesRegex(RuntimeError, "step units"):
            self.decode_first()
        self.assert_every_handle_released()

    def test_nearest_lookup_failure_releases_handle(self):
        self.ec.codes_grib_find_nearest_multiple.side_effect = RuntimeError("nearest lookup failed")
        with self.assertRaisesRegex(RuntimeError, "nearest lookup"):
            self.decode_first()
        self.assert_every_handle_released()

    def test_incomplete_nearest_mapping_is_rejected_and_released(self):
        self.ec.nearest.pop()
        with self.assertRaisesRegex(ValueError, "Incomplete nearest-cell"):
            self.decode_first()
        self.assertEqual(self.decoder.seen, set())
        self.assert_every_handle_released()

    def test_invalid_distances_are_rejected_and_released(self):
        for distance in (5.001, float("nan"), float("inf")):
            with self.subTest(distance=distance):
                self.ec.nearest[0]["distance"] = distance
                with self.assertRaisesRegex(ValueError, "Invalid cell index"):
                    self.decode_first()
                self.assertEqual(self.decoder.seen, set())
                self.assert_every_handle_released()

    def test_exact_five_kilometre_distance_is_accepted(self):
        self.ec.nearest[0]["distance"] = 5.0
        self.decode_first()
        self.assertEqual(self.decoder.grid_points[0]["distance"], 5.0)
        self.assert_every_handle_released()

    def test_out_of_bounds_indexes_are_rejected_and_released(self):
        for index in (-1, 761 * 761):
            with self.subTest(index=index):
                self.ec.nearest[0]["index"] = index
                with self.assertRaisesRegex(ValueError, "Invalid cell index"):
                    self.decode_first()
                self.assertEqual(self.decoder.seen, set())
                self.assert_every_handle_released()

    def test_first_message_missing_or_nonfinite_values_are_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf"), 9999.0):
            with self.subTest(value=value):
                # A failed decode is terminal for this run; use a fresh decoder.
                with patch.dict("sys.modules", {"eccodes": self.ec}):
                    self.decoder = PointDecoder(self.points)
                self.ec.nearest[0]["value"] = value
                with self.assertRaisesRegex(ValueError, "Missing/nonfinite"):
                    self.decode_first()
                self.assertEqual(self.decoder.seen, set())
                self.assert_every_handle_released()

    def test_reused_mapping_rejects_missing_or_nonfinite_values(self):
        self.decode_first()
        self.prepare_second()
        for value in (float("nan"), float("inf"), -float("inf"), 9999.0):
            with self.subTest(value=value):
                self.ec.values = [value, 284.15]
                with self.assertRaisesRegex(ValueError, "Missing/nonfinite"):
                    self.decode_second()
                self.assertEqual(self.decoder.seen, {("T_2M", RUN, 24)})
                self.assert_every_handle_released()

    def test_reused_mapping_rejects_incomplete_value_array(self):
        self.decode_first()
        self.prepare_second()
        self.ec.values = [294.15]
        with self.assertRaisesRegex(ValueError, "Missing/nonfinite"):
            self.decode_second()
        self.assert_every_handle_released()

    def test_value_extraction_error_releases_handle(self):
        self.decode_first()
        self.prepare_second()
        self.ec.codes_get_elements.side_effect = RuntimeError("value extraction failed")
        with self.assertRaisesRegex(RuntimeError, "value extraction"):
            self.decode_second()
        self.assertEqual(self.decoder.seen, {("T_2M", RUN, 24)})
        self.assert_every_handle_released()

    def test_handle_creation_failure_does_not_release_nonexistent_handle(self):
        self.ec.codes_new_from_message.side_effect = RuntimeError("invalid GRIB")
        with self.assertRaisesRegex(RuntimeError, "invalid GRIB"):
            self.decode_first()
        self.ec.codes_release.assert_not_called()


class PublicReaderBoundaryTests(unittest.TestCase):
    """HTTP stubs exercise refusal paths without importing requests or networking."""

    def reader(self, *, status=206, content_range="bytes 0-15/100", chunks=None, max_bytes=1000):
        response = MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.status_code = status
        response.headers = {"Content-Range": content_range}
        response.iter_content.return_value = chunks if chunks is not None else [b"x" * 16]
        reader = PublicReader.__new__(PublicReader)
        reader.session = Mock()
        reader.session.get.return_value = response
        reader.max_bytes = max_bytes
        reader.bytes_read = 0
        reader.requests = 0
        return reader, response

    def test_matching_206_range_succeeds_and_counts_transferred_bytes(self):
        reader, response = self.reader()
        data, total = reader.get(BASE + "synthetic.grib", 0, 15)
        self.assertEqual((data, total), (b"x" * 16, 100))
        self.assertEqual((reader.bytes_read, reader.requests), (16, 1))
        reader.session.get.assert_called_once_with(
            BASE + "synthetic.grib", headers={"Range": "bytes=0-15"}, stream=True,
            timeout=30, allow_redirects=False,
        )
        response.__exit__.assert_called_once()

    def test_http_200_is_rejected_before_reading_whole_file(self):
        reader, response = self.reader(status=200)
        with self.assertRaisesRegex(ValueError, "refusing full-file fallback"):
            reader.get(BASE + "synthetic.grib", 0, 15)
        response.iter_content.assert_not_called()
        self.assertEqual(reader.bytes_read, 0)
        response.__exit__.assert_called_once()

    def test_redirect_is_rejected_without_following_it(self):
        reader, response = self.reader(status=302)
        with self.assertRaisesRegex(ValueError, "Unexpected HTTP 302"):
            reader.get(BASE + "synthetic.grib", 0, 15)
        response.iter_content.assert_not_called()
        self.assertFalse(reader.session.get.call_args.kwargs["allow_redirects"])

    def test_http_status_survives_for_controlled_retry_without_sensitive_response(self):
        from local_pipeline.gcs_object_store import _http_status
        from local_pipeline.operational_diagnostics import error_fields

        for status in (408, 429, 500, 502, 503, 504, 200, 302, 400, 401, 403, 404):
            with self.subTest(status=status):
                reader, response = self.reader(status=status)
                response.url = BASE + "synthetic.grib?credential=secret"
                response.text = "private response credential=secret"
                with self.assertRaises(PublicHTTPError) as caught:
                    reader.get(BASE + "synthetic.grib", 0, 15)
                error = caught.exception
                retryable = status in {408, 429} or status >= 500
                self.assertEqual((_http_status(error), error.http_status), (status, status))
                self.assertEqual(error.retryable, retryable)
                self.assertEqual(error_fields(error)["http_status"], status)
                self.assertEqual(error_fields(error)["operation"], "source_range")
                self.assertFalse(hasattr(error, "response"))
                self.assertNotIn("secret", str(error) + repr(vars(error)))
                self.assertNotIn(BASE, str(error) + repr(vars(error)))
                response.iter_content.assert_not_called()
                response.__exit__.assert_called_once()
                self.assertEqual((reader.requests, reader.bytes_read), (1, 0))

    def test_listing_status_is_preserved_without_reading_or_retrying(self):
        reader, response = self.reader(status=503, max_bytes=256 * 1024)
        with self.assertRaises(PublicHTTPError) as caught:
            reader.links(BASE)
        self.assertEqual(caught.exception.code, 503)
        self.assertEqual(caught.exception.weather_diagnostics["operation"], "source_metadata")
        response.iter_content.assert_not_called()
        self.assertEqual(reader.requests, 1)

    def test_content_range_must_match_requested_start_and_end(self):
        for content_range in ("", "bytes 1-16/100", "bytes 0-16/100", "bytes 0-15/*"):
            with self.subTest(content_range=content_range):
                reader, response = self.reader(content_range=content_range)
                with self.assertRaisesRegex(ValueError, "Invalid Content-Range"):
                    reader.get(BASE + "synthetic.grib", 0, 15)
                response.iter_content.assert_not_called()

    def test_truncated_range_body_is_rejected(self):
        reader, response = self.reader(chunks=[b"x" * 15])
        with self.assertRaisesRegex(ValueError, "Truncated byte-range"):
            reader.get(BASE + "synthetic.grib", 0, 15)
        self.assertEqual(reader.bytes_read, 15)
        response.__exit__.assert_called_once()

    def test_oversized_body_is_stopped_at_chunk_boundary(self):
        reader, response = self.reader(chunks=[b"x" * 17])
        with self.assertRaisesRegex(ValueError, "Response exceeds transfer budget"):
            reader.get(BASE + "synthetic.grib", 0, 15)
        self.assertEqual(reader.bytes_read, 17)
        response.__exit__.assert_called_once()

    def test_insufficient_remaining_budget_prevents_http_request(self):
        reader, _ = self.reader(max_bytes=15)
        with self.assertRaisesRegex(ValueError, "Probe transfer budget exceeded"):
            reader.get(BASE + "synthetic.grib", 0, 15)
        reader.session.get.assert_not_called()
        self.assertEqual(reader.requests, 0)

    def test_outside_origin_is_rejected_before_network(self):
        reader, _ = self.reader()
        with self.assertRaisesRegex(ValueError, "Only the public ICON-2I"):
            reader.get("https://example.com/synthetic.grib", 0, 15)
        reader.session.get.assert_not_called()


class DeriveRowTests(unittest.TestCase):
    def test_columns_and_conversions_preserve_physical_meaning(self):
        row = row_dict()
        self.assertEqual(len(row), len(COLUMNS))
        self.assertEqual(row["temperature_c"], 20)
        self.assertEqual(row["dewpoint_c"], 10)
        self.assertAlmostEqual(row["relative_humidity_derived_pct"], 52.56, delta=0.1)
        self.assertEqual(row["wind_10m_m_s"], 5)
        self.assertEqual(row["pressure_msl_hpa"], 1013.25)
        self.assertEqual(row["cloud_cover_pct"], 37.5)
        self.assertEqual(row["precipitation_previous_hour_mm"], 1.25)
        self.assertEqual(row["quality_flags"], [])

    def test_wind_direction_is_meteorological_from_not_to(self):
        for u, v, expected in ((1, 0, 270), (0, 1, 180), (-1, 0, 90), (0, -1, 0)):
            with self.subTest(u=u, v=v):
                self.assertEqual(row_dict(raw_values(U_10M=u, V_10M=v))["wind_from_degrees"], expected)

    def test_near_north_wind_direction_wraps_after_rounding(self):
        row = row_dict(raw_values(U_10M=0.000001, V_10M=-1.0))
        self.assertEqual(row["wind_from_degrees"], 0.0)

    def test_calm_has_no_invented_wind_direction(self):
        row = row_dict(raw_values(U_10M=0, V_10M=0))
        self.assertEqual(row["wind_10m_m_s"], 0)
        self.assertIsNone(row["wind_from_degrees"])

    def test_dewpoint_above_temperature_is_flagged_not_clipped(self):
        row = row_dict(raw_values(TD_2M=293.151))
        self.assertGreater(row["dewpoint_c"], row["temperature_c"])
        for key in ("relative_humidity_derived_pct", "apparent_temperature_shade_c", "heat_index_c", "wind_chill_c"):
            self.assertIsNone(row[key])
        self.assertIn("invalid_T_Td_for_RH_no_clipping", row["quality_flags"])

    def test_invalid_rh_does_not_call_thermal_calculation(self):
        with patch("benchmark_icon2i.calculate_thermal_comfort") as calculate:
            row_dict(raw_values(TD_2M=294.15))
        calculate.assert_not_called()

    def test_negative_increment_or_accumulation_is_not_clipped_to_zero(self):
        for total, previous in ((1, 2), (-1, 0), (1, -1), (-1, -2)):
            with self.subTest(total=total, previous=previous):
                row = row_dict(raw_values(TOT_PREC=total), previous)
                self.assertIsNone(row["precipitation_previous_hour_mm"])
                self.assertIn("negative_rain_accumulation_or_increment_no_clipping", row["quality_flags"])

    def test_equal_accumulations_mean_zero_rain_without_warning(self):
        row = row_dict(raw_values(TOT_PREC=5.25), 5.25)
        self.assertEqual(row["precipitation_previous_hour_mm"], 0)
        self.assertEqual(row["quality_flags"], [])

    def test_out_of_range_cloud_cover_is_flagged_not_clipped(self):
        for cloud in (-0.01, 100.01):
            with self.subTest(cloud=cloud):
                row = row_dict(raw_values(CLCT=cloud))
                self.assertIsNone(row["cloud_cover_pct"])
                self.assertIn("invalid_cloud_cover", row["quality_flags"])

    def test_unknown_weather_code_is_retained_with_warning_not_icon_mapping(self):
        for code in (-1, 100, 3.5):
            with self.subTest(code=code):
                row = row_dict(raw_values(WW=code))
                self.assertEqual(row["weather_code_raw"], code)
                self.assertIn("unverified_noninteger_or_out_of_range_WW", row["quality_flags"])

    def test_thermal_indices_remain_separate_without_switching(self):
        thermal = SimpleNamespace(
            apparent_temperature=SimpleNamespace(value_c=11.125),
            heat_index=SimpleNamespace(value_c=42.5),
            wind_chill=SimpleNamespace(value_c=-8.75),
        )
        with patch("benchmark_icon2i.calculate_thermal_comfort", return_value=thermal):
            row = row_dict()
        self.assertEqual(row["apparent_temperature_shade_c"], 11.125)
        self.assertEqual(row["heat_index_c"], 42.5)
        self.assertEqual(row["wind_chill_c"], -8.75)
        self.assertNotIn("feels_like", row)

    def test_warm_and_cold_rows_do_not_replace_shade_apparent_temperature(self):
        for temperature, dewpoint in ((35, 25), (-5, -8)):
            with self.subTest(temperature=temperature):
                raw = raw_values(T_2M=temperature + 273.15, TD_2M=dewpoint + 273.15)
                row = row_dict(raw)
                from probe_icon2i import relative_humidity_from_dewpoint

                rh = relative_humidity_from_dewpoint(temperature, dewpoint)
                expected = calculate_thermal_comfort(temperature_c=temperature, relative_humidity_pct=rh, wind_10m_m_s=5)
                self.assertEqual(row["apparent_temperature_shade_c"], round(expected.apparent_temperature.value_c, 3))
                if temperature > 0:
                    self.assertIsNotNone(row["heat_index_c"])
                    self.assertIsNone(row["wind_chill_c"])
                    self.assertNotEqual(row["apparent_temperature_shade_c"], row["heat_index_c"])
                else:
                    self.assertIsNone(row["heat_index_c"])
                    self.assertIsNotNone(row["wind_chill_c"])
                    self.assertNotEqual(row["apparent_temperature_shade_c"], row["wind_chill_c"])

    def test_output_json_refuses_nonfinite_numbers(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                compact_json({"value": value})


if __name__ == "__main__":
    unittest.main()
