"""Offline framing, contracts, snapshot and output tests for the integrated pilot.

Synthetic fixtures prove local control-flow and transformations, not real model
skill, current provider availability, GRIB decoder fidelity or cloud costs.
"""

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import run_pilot as pilot


RUN = "2026090300"
RUN_TIME = datetime(2026, 9, 3, tzinfo=timezone.utc)


def metadata(field="T_2M", step=1, run=RUN, **changes):
    spec = pilot.CONTRACTS[field]
    run_time = datetime.strptime(run, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    valid = run_time + timedelta(hours=step)
    constant = field in pilot.ACCUM_FIELDS and (step == 0 or field == "SNOW_CON")
    result = {
        "shortName": spec["short_name"], "paramId": spec.get("param_id", 999),
        "units": spec["units"] or "Numeric", "typeOfLevel": spec["level_type"],
        "level": spec["level"], "dataDate": int(run[:8]), "dataTime": int(run[8:])*100,
        "validityDate": int(valid.strftime("%Y%m%d")), "validityTime": int(valid.strftime("%H%M")),
        "startStep": 0 if field in pilot.ACCUM_FIELDS else max(0, step-1) if field == "VMAX_10M" else step,
        "endStep": step, "stepUnits": 1, "stepType": spec["step_type"],
        "gridType": "regular_ll", "numberOfPoints": 761*761, "Ni": 761, "Nj": 761,
        "uvRelativeToGrid": 0, "md5GridSection": "a"*32,
        "packingType": "grid_simple", "bitsPerValue": 0 if constant else 16,
        "referenceValue": 0.0, "binaryScaleFactor": -10, "decimalScaleFactor": 0,
    }
    if field in pilot.ACCUM_FIELDS:
        result["encoding_quantum_mm"] = 0.0 if constant else 2**-10
    result.update(changes)
    return result


def snapshot_fixture():
    points = [{"slug": f"town-{index:03}", "name": f"Synthetic town {index}",
               "latitude": 45.9+index/1000, "longitude": 13.0} for index in range(215)]
    raw = {}
    ordinary = {"T_2M": 293.15, "TD_2M": 283.15, "U_10M": 2.0, "V_10M": 0.0,
                "CLCT": 30.0, "PMSL": 101325.0, "WW": 2.0, "VMAX_10M": 10.0}
    increments = {"TOT_PREC": 1.0, "RAIN_CON": .1, "RAIN_GSP": .7,
                  "SNOW_CON": 0.0, "SNOW_GSP": .1, "GRAU_GSP": .1}
    for field in pilot.CONTRACTS:
        raw[field] = {
            "url": f"{pilot.BASE}{RUN}/{field}/synthetic_surface-0.grib",
            "values": [[increments[field]*step if field in increments else ordinary[field]]*215 for step in range(73)],
            "metadata": [metadata(field, step) for step in range(73)],
            "downloaded_bytes": 1000, "sha256": "c"*64, "network_seconds": .1, "decode_seconds": .01,
        }
    return {
        "schema_version": 1, "kind": "extracted_source_snapshot", "run": RUN,
        "run_utc": pilot.iso(RUN_TIME), "times_utc": [pilot.iso(RUN_TIME+timedelta(hours=h)) for h in range(73)],
        "acquired_at_utc": pilot.iso(RUN_TIME+timedelta(hours=12)),
        "acquisition_finished_at_utc": pilot.iso(RUN_TIME+timedelta(hours=12, minutes=1)),
        "points": points, "catalog_sha256": "b"*64, "grid_hash": "a"*32,
        "grid_points": [{"lat": p["latitude"], "lon": p["longitude"], "distance": .2, "index": i} for i, p in enumerate(points)],
        "raw": raw, "metrics": {"downloaded_bytes": 14000, "unique_decoded_messages": 14*73, "duplicate_decoded_messages": 0},
    }


def framed_message(body=b""):
    size = 20+len(body)
    return b"GRIB\x00\x00\x00\x02" + size.to_bytes(8, "big") + body + b"7777"


class StreamFramingTests(unittest.TestCase):
    def test_every_single_split_boundary(self):
        first, second = framed_message(b"first message"), framed_message(b"second")
        combined = first+second
        for split in range(len(combined)+1):
            with self.subTest(split=split):
                self.assertEqual(list(pilot.stream_messages([combined[:split], combined[split:]], expected_count=2)), [first, second])

    def test_one_byte_chunks_and_empty_chunks(self):
        message = framed_message(b"payload")
        self.assertEqual(list(pilot.stream_messages([b""]+[message[i:i+1] for i in range(len(message))]+[b""], 1)), [message])

    def test_native_73_messages_in_one_chunk(self):
        messages = [framed_message(bytes([i])) for i in range(73)]
        self.assertEqual(list(pilot.stream_messages([b"".join(messages)])), messages)

    def test_chunk_size_limit(self):
        with self.assertRaisesRegex(ValueError, "Unbounded source chunk"):
            list(pilot.stream_messages([b"x"*(64*1024+1)], 1))

    def test_header_and_payload_truncation(self):
        message = framed_message(b"payload")
        for length in range(len(message)):
            with self.subTest(length=length), self.assertRaises(ValueError):
                list(pilot.stream_messages([message[:length]], 1))

    def test_bad_header_edition_and_size(self):
        good = framed_message()
        malformed = (b"<html>error</html>", b"NOPE"+good[4:], good[:7]+b"\x01"+good[8:],
                     good[:8]+(19).to_bytes(8, "big")+good[16:], good[:8]+(4*1024**2+1).to_bytes(8, "big")+good[16:])
        for message in malformed:
            with self.subTest(message=message), self.assertRaises(ValueError):
                list(pilot.stream_messages([message], 1))

    def test_bad_trailer(self):
        with self.assertRaisesRegex(ValueError, "trailer"):
            list(pilot.stream_messages([framed_message(b"payload")[:-4]+b"XXXX"], 1))

    def test_missing_extra_and_trailing_garbage_are_rejected(self):
        one = framed_message()
        for stream, count in ((one, 2), (one+one, 1), (one+b"x", 1), (one+b"GRIB", 1)):
            with self.subTest(count=count), self.assertRaises(ValueError):
                list(pilot.stream_messages([stream], count))


class FakeResponse:
    def __init__(self, body, status=200, headers=None, chunks=None):
        self.status_code = status
        self.headers = {"Content-Length": str(len(body)), "Content-Encoding": "identity"} if headers is None else headers
        self.body = body
        self.chunk_source = chunks
        self.closed = False

    def iter_content(self, chunk_size):
        if self.chunk_source is not None:
            yield from self.chunk_source
        else:
            for start in range(0, len(self.body), chunk_size):
                yield self.body[start:start+chunk_size]

    def close(self):
        self.closed = True


class StreamingReaderTests(unittest.TestCase):
    url = f"{pilot.BASE}{RUN}/T_2M/synthetic.grib"

    def reader(self, response):
        # Avoid requests dependency and never create a real network session.
        reader = pilot.StreamingReader.__new__(pilot.StreamingReader)
        reader.max_bytes = pilot.MAX_BYTES
        reader.bytes_read = reader.requests = 0
        reader.network_seconds = 0.0
        reader.calls = []
        reader.session = Mock()
        reader.session.get.return_value = response
        return reader

    def test_valid_stream_measures_bytes_digest_and_closes(self):
        body = framed_message(b"payload")
        response = FakeResponse(body)
        reader = self.reader(response)
        self.assertEqual(b"".join(reader.chunks(self.url)), body)
        self.assertTrue(response.closed)
        self.assertEqual(reader.bytes_read, len(body))
        self.assertEqual(reader.requests, 1)
        self.assertEqual(reader.calls[0]["sha256"], hashlib.sha256(body).hexdigest())
        self.assertTrue(reader.calls[0]["success"])
        reader.session.get.assert_called_once_with(self.url, stream=True, timeout=(15, 45), allow_redirects=False)

    def test_off_scope_urls_do_not_make_requests(self):
        bad = ("https://example.com/a.grib", self.url.replace("https:", "http:"), self.url+"?key=secret", self.url+".html")
        for url in bad:
            reader = self.reader(FakeResponse(framed_message()))
            with self.subTest(url=url), self.assertRaises(ValueError):
                list(reader.chunks(url))
            reader.session.get.assert_not_called()

    def test_redirect_partial_and_error_responses_are_not_fallbacks(self):
        for status in (206, 301, 302, 403, 404, 500):
            response = FakeResponse(framed_message(), status=status)
            reader = self.reader(response)
            with self.subTest(status=status), self.assertRaises(ValueError):
                list(reader.chunks(self.url))
            self.assertTrue(response.closed)
            self.assertFalse(reader.calls[-1]["success"])
            self.assertEqual(reader.bytes_read, 0)

    def test_stream_http_status_preserves_retry_classification_and_closes(self):
        from local_pipeline.gcs_object_store import _http_status
        from local_pipeline.operational_diagnostics import error_fields

        for status in (408, 429, 500, 502, 503, 504, 206, 302, 400, 401, 403, 404):
            with self.subTest(status=status):
                response = FakeResponse(b"private body credential=secret", status=status)
                reader = self.reader(response)
                with self.assertRaises(pilot.PublicHTTPError) as caught:
                    list(reader.chunks(self.url))
                error = caught.exception
                self.assertEqual(_http_status(error), status)
                self.assertEqual(error.retryable, status in {408, 429} or status >= 500)
                self.assertEqual(error_fields(error)["operation"], "source_variable")
                self.assertNotIn("secret", str(error) + repr(vars(error)))
                self.assertNotIn(self.url, str(error) + repr(vars(error)))
                self.assertTrue(response.closed)
                self.assertEqual((reader.requests, reader.bytes_read), (1, 0))
                self.assertFalse(reader.calls[-1]["success"])

    def test_success_status_with_invalid_encoding_is_not_a_retryable_http_failure(self):
        response = FakeResponse(framed_message(), headers={"Content-Encoding": "gzip"})
        reader = self.reader(response)
        with self.assertRaises(ValueError) as caught:
            list(reader.chunks(self.url))
        self.assertNotIsInstance(caught.exception, pilot.PublicHTTPError)
        self.assertTrue(response.closed)

    def test_compressed_or_unbounded_content_length_is_rejected(self):
        invalid_headers = ({}, {"Content-Length": "-1"}, {"Content-Length": "twenty"}, {"Content-Length": "20.0"},
                           {"Content-Length": "20", "Content-Encoding": "gzip"}, {"Content-Length": str(pilot.MAX_FILE_BYTES+1)}, {"Content-Length": "19"})
        for headers in invalid_headers:
            response = FakeResponse(framed_message(), headers=headers)
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                list(self.reader(response).chunks(self.url))
            self.assertTrue(response.closed)

    def test_preflight_total_budget_counts_prior_metadata(self):
        response = FakeResponse(framed_message())
        reader = self.reader(response)
        reader.max_bytes = 30
        reader.bytes_read = 11
        with self.assertRaisesRegex(ValueError, "budget"):
            list(reader.chunks(self.url))
        self.assertEqual(reader.bytes_read, 11)
        self.assertTrue(response.closed)

    def test_body_larger_than_declared_never_succeeds(self):
        response = FakeResponse(framed_message()+b"extra", headers={"Content-Length": "20"})
        reader = self.reader(response)
        with self.assertRaisesRegex(ValueError, "budget"):
            list(reader.chunks(self.url))
        self.assertFalse(reader.calls[-1]["success"])
        self.assertTrue(response.closed)

    def test_truncated_body_never_succeeds(self):
        response = FakeResponse(framed_message(), headers={"Content-Length": "21"})
        reader = self.reader(response)
        with self.assertRaisesRegex(ValueError, "Truncated HTTP"):
            list(reader.chunks(self.url))
        self.assertFalse(reader.calls[-1]["success"])
        self.assertTrue(response.closed)

    def test_total_budget_still_checked_during_transfer(self):
        response = FakeResponse(framed_message())
        reader = self.reader(response)
        reader.max_bytes = 21
        def changing_budget():
            reader.bytes_read = 2
            yield framed_message()
        response.chunk_source = changing_budget()
        with self.assertRaisesRegex(ValueError, "budget"):
            list(reader.chunks(self.url))
        self.assertTrue(response.closed)

    def test_early_consumer_stop_closes_response_and_does_not_claim_success(self):
        response = FakeResponse(framed_message())
        reader = self.reader(response)
        stream = reader.chunks(self.url)
        next(stream)
        stream.close()
        self.assertTrue(response.closed)
        self.assertFalse(reader.calls[-1]["success"])


def listing_for_runs(runs, *, missing_directories=None, file_prefix="synthetic"):
    missing_directories = missing_directories or {}
    listing = {pilot.BASE: [f"{run}/" for run in runs]}
    for run in runs:
        missing = set(missing_directories.get(run, ()))
        run_url = f"{pilot.BASE}{run}/"
        listing[run_url] = [f"{field}/" for field in pilot.CONTRACTS if field not in missing]
        for field, spec in pilot.CONTRACTS.items():
            if field in missing:
                continue
            directory = f"{run_url}{field}/"
            listing[directory] = [f"{file_prefix}-{field}_{spec['suffix']}.grib"]
    return listing


class FakeListingReader:
    def __init__(self, listing):
        self.listing = listing
        self.list_calls = []

    def links(self, url):
        self.list_calls.append(url)
        if url not in self.listing:
            raise AssertionError(f"Unexpected offline listing URL: {url}")
        return list(self.listing[url])


class FakeAcquisitionReader(FakeListingReader):
    def __init__(self, listing):
        super().__init__(listing)
        self.bytes_read = 0
        self.requests = 0
        self.network_seconds = 0.0
        self.calls = []
        self.downloaded_fields = []

    def links(self, url):
        self.requests += 1
        return super().links(url)

    def chunks(self, url):
        field = next(field for field in pilot.CONTRACTS if f"/{field}/" in url)
        self.requests += 1
        self.downloaded_fields.append(field)
        self.bytes_read += 1000
        self.network_seconds += 0.1
        self.calls.append({
            "url": url, "bytes": 1000, "network_seconds": 0.1,
            "sha256": hashlib.sha256(url.encode()).hexdigest(),
            "success": True, "kind": "full_variable_stream",
        })
        yield b"offline-transport-consumed"


class FakeCheckpointDecoder:
    def __init__(self, points, fail_field=None):
        self.points = points
        self.fail_field = fail_field
        self.grid_points = None
        self.grid_hash = None
        self.indexes = None
        self.seen = set()
        self.seconds = 0.0
        self.mapping_seconds = 0.0
        self.mapping_builds = 0

    def decode(self, data, field, run, step):
        if field == self.fail_field:
            raise RuntimeError(f"synthetic crash while decoding {field}")
        if self.grid_hash is None:
            self.grid_hash = "a" * 32
            self.grid_points = [
                {"lat": point["latitude"], "lon": point["longitude"],
                 "distance": 0.2, "index": index}
                for index, point in enumerate(self.points)
            ]
            self.indexes = [item["index"] for item in self.grid_points]
            self.mapping_builds += 1
        identity = (field, run, step)
        if identity in self.seen:
            raise ValueError("duplicate synthetic decode")
        self.seen.add(identity)
        self.seconds += 0.001
        value = float(step) if field in pilot.ACCUM_FIELDS else 293.15
        return [value] * len(self.points), metadata(field, step, run=run, packingError=0.0005)


def consume_transport_and_return_messages(chunks, expected_count=73):
    list(chunks)
    return iter([b"offline-message"] * expected_count)


class RunDiscoveryTests(unittest.TestCase):
    def test_partial_newest_falls_back_to_newest_complete_usable_run(self):
        older, newest = RUN, "2026090312"
        reader = FakeListingReader(listing_for_runs(
            [older, newest], missing_directories={newest: {"GRAU_GSP"}}
        ))
        selected, run_time, times, urls = pilot.discover_complete_run(
            reader, datetime(2026, 9, 4, tzinfo=timezone.utc)
        )
        self.assertEqual(selected, older)
        self.assertEqual(run_time, RUN_TIME)
        self.assertEqual(len(times), 73)
        self.assertEqual(set(urls), set(pilot.CONTRACTS))
        self.assertNotIn(f"{pilot.BASE}{newest}/GRAU_GSP/", reader.list_calls)

    def test_newest_with_all_directories_but_missing_file_also_falls_back(self):
        older, newest = RUN, "2026090312"
        listing = listing_for_runs([older, newest])
        listing[f"{pilot.BASE}{newest}/PMSL/"] = []
        reader = FakeListingReader(listing)
        selected, *_ = pilot.discover_complete_run(
            reader, datetime(2026, 9, 4, tzinfo=timezone.utc)
        )
        self.assertEqual(selected, older)

    def test_explicit_partial_run_fails_instead_of_silently_falling_back(self):
        older, newest = RUN, "2026090312"
        reader = FakeListingReader(listing_for_runs(
            [older, newest], missing_directories={newest: {"PMSL"}}
        ))
        with self.assertRaisesRegex(ValueError, "partial"):
            pilot.discover_complete_run(
                reader, datetime(2026, 9, 4, tzinfo=timezone.utc), newest
            )

    def test_unusable_newer_run_is_skipped_before_field_discovery(self):
        usable, future = RUN, "2026090412"
        reader = FakeListingReader(listing_for_runs([usable, future]))
        selected, *_ = pilot.discover_complete_run(
            reader, datetime(2026, 9, 4, tzinfo=timezone.utc)
        )
        self.assertEqual(selected, usable)
        self.assertNotIn(f"{pilot.BASE}{future}/", reader.list_calls)

    def test_partial_newest_fallback_to_verified_current_is_typed_not_advanced(self):
        current, partial = RUN, "2026090312"
        reader = FakeListingReader(listing_for_runs(
            [current, partial], missing_directories={partial: {"GRAU_GSP"}}
        ))

        with self.assertRaises(pilot.SourceRunNotAdvanced) as caught:
            pilot.discover_complete_run(
                reader,
                datetime(2026, 9, 4, tzinfo=timezone.utc),
                source_run_high_water="20260903T000000Z",
            )

        self.assertEqual(caught.exception.source_run_id, "20260903T000000Z")

    def test_verified_current_does_not_block_a_complete_newer_run(self):
        current, newest = RUN, "2026090312"
        reader = FakeListingReader(listing_for_runs([current, newest]))

        selected, *_ = pilot.discover_complete_run(
            reader,
            datetime(2026, 9, 4, tzinfo=timezone.utc),
            source_run_high_water="20260903T000000Z",
        )

        self.assertEqual(selected, newest)

    def test_provider_pruning_to_an_older_run_is_also_not_advanced(self):
        reader = FakeListingReader(listing_for_runs([RUN]))

        with self.assertRaises(pilot.SourceRunNotAdvanced) as caught:
            pilot.discover_complete_run(
                reader,
                datetime(2026, 9, 4, tzinfo=timezone.utc),
                source_run_high_water="20260903T120000Z",
            )

        self.assertEqual(caught.exception.source_run_id, "20260903T000000Z")
        self.assertEqual(
            caught.exception.source_run_high_water, "20260903T120000Z"
        )

    def test_verified_rollback_high_water_blocks_the_newer_revoked_run(self):
        rolled_back, revoked = RUN, "2026090312"
        reader = FakeListingReader(listing_for_runs([rolled_back, revoked]))

        with self.assertRaises(pilot.SourceRunNotAdvanced) as caught:
            pilot.discover_complete_run(
                reader,
                datetime(2026, 9, 4, tzinfo=timezone.utc),
                source_run_high_water="20260903T120000Z",
            )

        self.assertEqual(caught.exception.source_run_id, "20260903T120000Z")
        self.assertEqual(caught.exception.source_run_high_water, "20260903T120000Z")
        self.assertEqual(reader.list_calls, [pilot.BASE])

    def test_verified_current_below_48h_residual_is_retryable_not_advanced(self):
        reader = FakeListingReader(listing_for_runs([RUN]))

        with self.assertRaises(pilot.SourceRunNotAdvanced) as caught:
            pilot.discover_complete_run(
                reader,
                RUN_TIME + timedelta(hours=25),
                source_run_high_water="20260903T000000Z",
            )

        self.assertEqual(caught.exception.source_run_id, "20260903T000000Z")
        self.assertEqual(reader.list_calls, [pilot.BASE])

    def test_no_published_high_water_preserves_terminal_no_usable_run_error(self):
        reader = FakeListingReader(listing_for_runs([RUN]))

        with self.assertRaisesRegex(ValueError, "No complete public run can cover"):
            pilot.discover_complete_run(
                reader,
                RUN_TIME + timedelta(hours=25),
            )

        self.assertEqual(reader.list_calls, [pilot.BASE])


class CheckpointAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="meteofriul-icon-checkpoint-")
        self.root = Path(self.directory.name)
        self.checkpoint = self.root / "checkpoint"
        self.points = snapshot_fixture()["points"]
        self.listing = listing_for_runs([RUN])
        self.now = RUN_TIME + timedelta(hours=12)

    def tearDown(self):
        self.directory.cleanup()

    def acquire(self, reader, decoder):
        with (
            patch.object(pilot, "load_points", return_value=(self.points, "b" * 64)),
            patch.object(pilot, "StreamingReader", return_value=reader),
            patch.object(pilot, "Decoder", return_value=decoder),
            patch.object(pilot, "stream_messages", side_effect=consume_transport_and_return_messages),
            patch("process_memory.process_memory_bytes", return_value={"peak_working_set_bytes": 123}),
            patch("builtins.print"),
        ):
            return pilot.acquire(checkpoint_dir=self.checkpoint, now=self.now)

    def seed_complete_checkpoint(self):
        reader = FakeAcquisitionReader(self.listing)
        snapshot = self.acquire(reader, FakeCheckpointDecoder(self.points))
        self.assertEqual(reader.downloaded_fields, list(pilot.CONTRACTS))
        return snapshot

    def test_late_failure_resumes_thirteen_validated_fields_and_downloads_only_one(self):
        fields = list(pilot.CONTRACTS)
        first_reader = FakeAcquisitionReader(self.listing)
        with self.assertRaisesRegex(RuntimeError, fields[-1]):
            self.acquire(first_reader, FakeCheckpointDecoder(self.points, fail_field=fields[-1]))
        self.assertEqual(
            {path.stem for path in (self.checkpoint / "fields").glob("*.json")},
            set(fields[:-1]),
        )

        resumed_reader = FakeAcquisitionReader(self.listing)
        snapshot = self.acquire(resumed_reader, FakeCheckpointDecoder(self.points))
        self.assertEqual(resumed_reader.downloaded_fields, [fields[-1]])
        self.assertEqual(snapshot["metrics"]["resumed_fields"], fields[:-1])
        self.assertEqual(snapshot["metrics"]["newly_acquired_fields"], [fields[-1]])
        self.assertEqual(snapshot["metrics"]["downloaded_bytes"], 1000)
        self.assertEqual(snapshot["metrics"]["source_field_downloaded_bytes"], 14_000)
        self.assertEqual(snapshot["metrics"]["unique_decoded_messages"], 14 * 73)
        pilot.validate_snapshot(snapshot)

    def test_legacy_fields_without_packing_error_resume_without_rewriting(self):
        self.seed_complete_checkpoint()
        original = {}
        for path in (self.checkpoint / "fields").glob("*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            for meta in record["data"]["metadata"]:
                meta.pop("packingError")
            record.pop("checkpoint_sha256")
            encoded = pilot._canonical_bytes(pilot._with_checkpoint_integrity(record))
            path.write_bytes(encoded)
            original[path.name] = encoded
        reader = FakeAcquisitionReader(self.listing)
        snapshot = self.acquire(reader, FakeCheckpointDecoder(self.points, fail_field="T_2M"))
        self.assertEqual(reader.downloaded_fields, [])
        self.assertEqual(snapshot["metrics"]["resumed_fields"], list(pilot.CONTRACTS))
        self.assertTrue(all("packingError" not in meta for data in snapshot["raw"].values()
                            for meta in data["metadata"]))
        self.assertEqual({path.name: path.read_bytes() for path in
                          (self.checkpoint / "fields").glob("*.json")}, original)

    def test_invalid_packing_error_or_unknown_metadata_fails_before_reuse(self):
        self.seed_complete_checkpoint()
        path = self.checkpoint / "fields" / "T_2M.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        cases = [("packingError", value) for value in (-0.001, True, False, "0.001", [], {}, 10**400)]
        cases.append(("unexpected_diagnostic", 0.001))
        for key, value in cases:
            with self.subTest(key=key, value=value):
                record = copy.deepcopy(original)
                record["data"]["metadata"][12][key] = value
                record.pop("checkpoint_sha256")
                encoded = pilot._canonical_bytes(pilot._with_checkpoint_integrity(record))
                path.write_bytes(encoded)
                reader = FakeAcquisitionReader(self.listing)
                with self.assertRaises(ValueError):
                    self.acquire(reader, FakeCheckpointDecoder(self.points))
                self.assertEqual(reader.downloaded_fields, [])
                self.assertEqual(path.read_bytes(), encoded)

    def test_tampered_field_fails_closed_without_redownload_or_overwrite(self):
        self.seed_complete_checkpoint()
        field_path = self.checkpoint / "fields" / "T_2M.json"
        record = json.loads(field_path.read_text(encoding="utf-8"))
        record["data"]["values"][0][0] += 1
        field_path.write_text(json.dumps(record), encoding="utf-8")
        tampered = field_path.read_bytes()

        reader = FakeAcquisitionReader(self.listing)
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.acquire(reader, FakeCheckpointDecoder(self.points))
        self.assertEqual(reader.downloaded_fields, [])
        self.assertEqual(field_path.read_bytes(), tampered)

    def test_semantically_tampered_but_rehashed_field_is_still_rejected(self):
        self.seed_complete_checkpoint()
        field_path = self.checkpoint / "fields" / "T_2M.json"
        record = json.loads(field_path.read_text(encoding="utf-8"))
        record["data"]["metadata"][0]["units"] = "C"
        record.pop("checkpoint_sha256")
        record = pilot._with_checkpoint_integrity(record)
        field_path.write_bytes(pilot._canonical_bytes(record))
        tampered = field_path.read_bytes()
        reader = FakeAcquisitionReader(self.listing)

        with self.assertRaisesRegex(ValueError, "Parameter, unit or level changed"):
            self.acquire(reader, FakeCheckpointDecoder(self.points))
        self.assertEqual(reader.downloaded_fields, [])
        self.assertEqual(field_path.read_bytes(), tampered)

    def test_valid_checkpoint_cannot_be_rebound_to_changed_catalog_points(self):
        self.seed_complete_checkpoint()
        changed_points = copy.deepcopy(self.points)
        changed_points[0]["latitude"] += 0.001
        reader = FakeAcquisitionReader(self.listing)
        with (
            patch.object(pilot, "load_points", return_value=(changed_points, "b" * 64)),
            patch.object(pilot, "StreamingReader", return_value=reader),
            patch.object(pilot, "Decoder", return_value=FakeCheckpointDecoder(changed_points)),
            patch("builtins.print"),
            self.assertRaisesRegex(ValueError, "catalog/contracts"),
        ):
            pilot.acquire(checkpoint_dir=self.checkpoint, now=self.now)
        self.assertEqual(reader.list_calls, [])
        self.assertEqual(reader.downloaded_fields, [])

    def test_tampered_intent_is_rejected_before_any_public_listing(self):
        self.seed_complete_checkpoint()
        intent_path = self.checkpoint / "intent.json"
        intent = json.loads(intent_path.read_text(encoding="utf-8"))
        intent["catalog_sha256"] = "0" * 64
        intent_path.write_text(json.dumps(intent), encoding="utf-8")
        reader = FakeAcquisitionReader(self.listing)

        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.acquire(reader, FakeCheckpointDecoder(self.points))
        self.assertEqual(reader.list_calls, [])
        self.assertEqual(reader.downloaded_fields, [])

    def test_valid_intent_cannot_be_rebound_to_changed_provider_urls(self):
        self.seed_complete_checkpoint()
        changed_reader = FakeAcquisitionReader(listing_for_runs([RUN], file_prefix="republished"))
        before = {
            path.name: path.read_bytes()
            for path in (self.checkpoint / "fields").glob("*.json")
        }
        with self.assertRaisesRegex(ValueError, "different inputs"):
            self.acquire(changed_reader, FakeCheckpointDecoder(self.points))
        self.assertEqual(changed_reader.downloaded_fields, [])
        self.assertEqual(
            {path.name: path.read_bytes() for path in (self.checkpoint / "fields").glob("*.json")},
            before,
        )

    def test_checkpoint_is_pinned_to_original_run_when_newer_run_appears(self):
        fields = list(pilot.CONTRACTS)
        reader = FakeAcquisitionReader(self.listing)
        with self.assertRaises(RuntimeError):
            self.acquire(reader, FakeCheckpointDecoder(self.points, fail_field=fields[-1]))
        newer = "2026090312"
        listing = listing_for_runs([RUN, newer])
        resumed_reader = FakeAcquisitionReader(listing)
        snapshot = self.acquire(resumed_reader, FakeCheckpointDecoder(self.points))
        self.assertEqual(snapshot["run"], RUN)
        self.assertNotIn(f"{pilot.BASE}{newer}/", resumed_reader.list_calls)
        self.assertEqual(resumed_reader.downloaded_fields, [fields[-1]])

    def test_crash_after_atomic_link_leaves_valid_resumable_final_and_never_replaces_it(self):
        field = "T_2M"
        run_time, _ = pilot._run_times(RUN)
        urls = {
            name: f"{pilot.BASE}{RUN}/{name}/synthetic-{name}_{spec['suffix']}.grib"
            for name, spec in pilot.CONTRACTS.items()
        }
        intent = pilot._checkpoint_intent(RUN, run_time, self.points, "b" * 64, urls)
        fields_dir, intent_sha = pilot._prepare_checkpoint(self.checkpoint, intent)
        decoder = FakeCheckpointDecoder(self.points)
        values, metas = [], []
        for step in range(73):
            value, meta = decoder.decode(b"offline", field, RUN, step)
            values.append(value)
            metas.append(meta)
        data = {
            "url": urls[field], "values": values, "metadata": metas,
            "downloaded_bytes": 1000, "sha256": "c" * 64,
            "network_seconds": 0.1, "decode_seconds": 0.01,
        }
        real_link = pilot.os.link

        def link_then_crash(source, target):
            real_link(source, target)
            raise RuntimeError("crash after link")

        with patch.object(pilot.os, "link", side_effect=link_then_crash), self.assertRaisesRegex(RuntimeError, "after link"):
            pilot._save_field_checkpoint(
                fields_dir, intent_sha=intent_sha, field=field, run=RUN,
                url=urls[field], points=self.points, decoder=decoder, data=data,
            )
        final_path = fields_dir / f"{field}.json"
        original = final_path.read_bytes()
        (fields_dir / ".T_2M.interrupted.part").write_bytes(b"partial")
        pilot._prepare_checkpoint(self.checkpoint, intent)
        restored = pilot._load_field_checkpoint(
            fields_dir, intent_sha=intent_sha, field=field, run=RUN,
            url=urls[field], points=self.points,
        )
        self.assertEqual(restored["data"], data)
        with self.assertRaises(FileExistsError):
            pilot._save_field_checkpoint(
                fields_dir, intent_sha=intent_sha, field=field, run=RUN,
                url=urls[field], points=self.points, decoder=decoder, data=data,
            )
        self.assertEqual(final_path.read_bytes(), original)


class ContractTests(unittest.TestCase):
    def test_all_fourteen_fields_and_native_steps(self):
        self.assertEqual(len(pilot.CONTRACTS), 14)
        for field in pilot.CONTRACTS:
            for step in (0, 1, 12, 24, 72):
                with self.subTest(field=field, step=step):
                    pilot.validate_contract(metadata(field, step), field, RUN, step)

    def test_invalid_leads(self):
        for step in (-1, 73, True, 1.0, "1", None):
            with self.subTest(step=step), self.assertRaises(ValueError):
                pilot.validate_contract(metadata(), "T_2M", RUN, step)

    def test_wrong_parameter_units_levels_or_identity(self):
        for field, changes in (("T_2M", {"shortName": "2d"}), ("T_2M", {"units": "C"}),
                               ("T_2M", {"level": 1000}), ("T_2M", {"typeOfLevel": "isobaricInhPa"}),
                               ("VMAX_10M", {"paramId": 49})):
            with self.subTest(field=field, changes=changes), self.assertRaises(ValueError):
                pilot.validate_contract(metadata(field, **changes), field, RUN, 1)

    def test_accumulated_rain_components_retain_documented_flux_descriptors(self):
        for field in ("RAIN_CON", "RAIN_GSP"):
            good = metadata(field)
            self.assertEqual(good["units"], "kg m**-2 s**-1")
            self.assertEqual(good["stepType"], "accum")
            pilot.validate_contract(good, field, RUN, 1)
            with self.assertRaises(ValueError):
                pilot.validate_contract(metadata(field, units="kg m**-2"), field, RUN, 1)

    def test_accumulation_must_start_at_run_and_not_be_average_flux(self):
        for field in pilot.ACCUM_FIELDS:
            for changes in ({"stepType": "instant"}, {"stepType": "avg"}, {"startStep": 1}):
                with self.subTest(field=field, changes=changes), self.assertRaises(ValueError):
                    pilot.validate_contract(metadata(field, 2, **changes), field, RUN, 2)

    def test_gust_must_be_previous_hour_maximum(self):
        for changes in ({"startStep": 0}, {"stepType": "instant"}, {"stepType": "accum"}, {"endStep": 3}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                pilot.validate_contract(metadata("VMAX_10M", 2, **changes), "VMAX_10M", RUN, 2)

    def test_instant_fields_must_have_start_equal_end(self):
        with self.assertRaises(ValueError):
            pilot.validate_contract(metadata("T_2M", 2, startStep=1), "T_2M", RUN, 2)

    def test_run_hour_units_and_validity_must_match(self):
        for changes in ({"dataDate": 20260902}, {"dataTime": 1200}, {"endStep": 2}, {"stepUnits": 0},
                        {"validityDate": 20260904}, {"validityTime": 200}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                pilot.validate_contract(metadata(**changes), "T_2M", RUN, 1)

    def test_grid_shape_must_be_consistent(self):
        for changes in ({"gridType": "unstructured_grid"}, {"Ni": 0}, {"Nj": -1}, {"numberOfPoints": 761*761+1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                pilot.validate_contract(metadata(**changes), "T_2M", RUN, 1)

    def test_grid_relative_winds_are_rejected_without_rotation(self):
        for field in ("U_10M", "V_10M"):
            with self.assertRaisesRegex(ValueError, "rotation"):
                pilot.validate_contract(metadata(field, uvRelativeToGrid=1), field, RUN, 1)


class QuantumTests(unittest.TestCase):
    def test_variable_packing_quantum_uses_both_scale_factors(self):
        self.assertEqual(pilot.accumulation_quantum(metadata("TOT_PREC", binaryScaleFactor=-3, decimalScaleFactor=2)), .00125)

    def test_constant_zero_has_zero_effective_quantum_despite_scale(self):
        self.assertEqual(pilot.accumulation_quantum(metadata("TOT_PREC", 0, binaryScaleFactor=20)), 0.0)

    def test_reference_is_converted_to_decoded_units(self):
        self.assertEqual(
            pilot.accumulation_reference_mm(
                metadata("TOT_PREC", referenceValue=125, decimalScaleFactor=2)
            ),
            1.25,
        )

    def test_invalid_or_overflowing_reference_conversion_is_rejected(self):
        for changes in (
            {"referenceValue": -1},
            {"referenceValue": float("nan")},
            {"referenceValue": True},
            {"packingType": "grid_complex"},
            {"decimalScaleFactor": "0"},
            {"decimalScaleFactor": -100000},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                pilot.accumulation_reference_mm(metadata("TOT_PREC", **changes))

    def test_finite_nonnegative_reference_is_supported_by_simple_packing(self):
        baseline = pilot.accumulation_quantum(metadata("TOT_PREC"))
        self.assertEqual(
            baseline,
            pilot.accumulation_quantum(metadata("TOT_PREC", referenceValue=1.959571780507001e-25)),
        )
        self.assertEqual(baseline, pilot.accumulation_quantum(metadata("TOT_PREC", referenceValue=1)))

    def test_invalid_reference_and_non_simple_packing_are_rejected(self):
        for changes in ({"referenceValue": -1}, {"referenceValue": float("nan")},
                        {"referenceValue": True}, {"packingType": "grid_complex"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                pilot.accumulation_quantum(metadata("TOT_PREC", **changes))

    def test_precision_range_type_and_fractional_bits_are_rejected(self):
        for bits in (-1, 33, True, .5, "16", None):
            with self.subTest(bits=bits), self.assertRaises(ValueError):
                pilot.accumulation_quantum(metadata("TOT_PREC", bitsPerValue=bits))

    def test_invalid_or_overflowing_scales_fail_as_value_error(self):
        for changes in ({"binaryScaleFactor": True}, {"binaryScaleFactor": .5}, {"binaryScaleFactor": float("nan")},
                        {"binaryScaleFactor": 100000}, {"decimalScaleFactor": "0"}, {"decimalScaleFactor": -100000}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                pilot.accumulation_quantum(metadata("TOT_PREC", **changes))


class DecoderTests(unittest.TestCase):
    def setUp(self):
        self.meta = metadata()
        self.nearest = [{"lat": 46.0, "lon": 13.0, "distance": .2, "index": i, "value": 293.15+i} for i in range(2)]
        self.ec = Mock()
        self.handle = object()
        self.ec.codes_new_from_message.return_value = self.handle
        self.ec.codes_get.side_effect = lambda handle, key: 1e30 if key == "missingValue" else self.meta[key]
        self.ec.codes_grib_find_nearest_multiple.side_effect = lambda *args: self.nearest
        self.ec.codes_get_elements.return_value = [293.15, 294.15]
        self.points = [{"latitude": 46.0, "longitude": 13.0}, {"latitude": 46.001, "longitude": 13.001}]
        with patch.dict("sys.modules", {"eccodes": self.ec}):
            self.decoder = pilot.Decoder(self.points)

    def test_one_mapping_for_multiple_messages_and_released_handles(self):
        first, first_meta = self.decoder.decode(b"fake", "T_2M", RUN, 1)
        self.assertEqual(first, [293.15, 294.15])
        self.assertEqual(first_meta["endStep"], 1)
        self.meta = metadata(step=2)
        self.decoder.decode(b"fake2", "T_2M", RUN, 2)
        self.assertEqual(self.decoder.mapping_builds, 1)
        self.ec.codes_grib_find_nearest_multiple.assert_called_once()
        self.ec.codes_get_elements.assert_called_once_with(self.handle, "values", [0, 1])
        self.assertEqual(self.ec.codes_release.call_count, 2)
        self.assertEqual(len(self.decoder.seen), 2)

    def test_real_decoder_metadata_survives_checkpoint_save_and_read(self):
        # Keep Decoder.decode real: mocking it hid the packingError regression.
        for field in pilot.CONTRACTS:
            for packing_error in (0.0, 0.0005, None):
                with self.subTest(field=field, packing_error=packing_error):
                    self.setUp()
                    values, metas = [], []
                    for step in range(73):
                        self.meta = metadata(field, step, packingError=packing_error)
                        value, meta = self.decoder.decode(b"synthetic-grib", field, RUN, step)
                        values.append(value)
                        metas.append(meta)
                    data = dict(url="https://example.invalid/unused.grib", values=values, metadata=metas,
                                downloaded_bytes=1000, sha256="c" * 64,
                                network_seconds=0.1, decode_seconds=0.01)
                    kwargs = dict(intent_sha="d" * 64, field=field, run=RUN,
                                  url=data["url"], points=self.points)
                    with tempfile.TemporaryDirectory(prefix="icon-field-metadata-") as directory:
                        root = Path(directory)
                        pilot._save_field_checkpoint(root, decoder=self.decoder, data=data, **kwargs)
                        restored = pilot._load_field_checkpoint(root, **kwargs)
                    self.assertEqual(restored["data"], data)
                    self.assertEqual([meta["packingError"] for meta in restored["data"]["metadata"]],
                                     [packing_error] * 73)
                    self.assertEqual(self.ec.codes_release.call_count, 73)

    def test_missing_or_invalid_optional_packing_error_stays_unavailable(self):
        missing = object()
        for value in (missing, None, -0.001, True, False, "0.001", [], {},
                      float("nan"), float("inf"), -float("inf"), 10**400):
            with self.subTest(value=value):
                self.setUp()
                if value is not missing:
                    self.meta["packingError"] = value
                values, meta = self.decoder.decode(b"synthetic-grib", "T_2M", RUN, 1)
                self.assertEqual(values, [293.15, 294.15])
                self.assertIsNone(meta["packingError"])
                self.ec.codes_release.assert_called_once_with(self.handle)

    def test_duplicate_identity_rejected_before_redecode(self):
        self.decoder.decode(b"fake", "T_2M", RUN, 1)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.decoder.decode(b"fake", "T_2M", RUN, 1)
        self.ec.codes_new_from_message.assert_called_once()

    def test_parameter_validation_failure_still_releases_handle(self):
        self.meta["units"] = "C"
        with self.assertRaises(ValueError):
            self.decoder.decode(b"fake", "T_2M", RUN, 1)
        self.ec.codes_release.assert_called_once_with(self.handle)
        self.assertEqual(self.decoder.seen, set())

    def test_changed_grid_rejected_without_using_cached_indexes(self):
        self.decoder.decode(b"fake", "T_2M", RUN, 1)
        self.meta = metadata(step=2, md5GridSection="b"*32)
        with self.assertRaisesRegex(ValueError, "Grid changed"):
            self.decoder.decode(b"fake2", "T_2M", RUN, 2)
        self.ec.codes_get_elements.assert_not_called()
        self.assertEqual(self.ec.codes_release.call_count, 2)

    def test_missing_or_nonfinite_values_fail_before_being_seen(self):
        for value in (float("nan"), float("inf"), 1e30):
            self.setUp()
            self.nearest[0]["value"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.decoder.decode(b"fake", "T_2M", RUN, 1)
            self.ec.codes_release.assert_called_once_with(self.handle)
            self.assertEqual(self.decoder.seen, set())

    def test_cached_extraction_must_still_return_all_towns(self):
        self.decoder.decode(b"fake", "T_2M", RUN, 1)
        self.meta = metadata(step=2)
        self.ec.codes_get_elements.return_value = [293.15]
        with self.assertRaises(ValueError):
            self.decoder.decode(b"fake2", "T_2M", RUN, 2)
        self.assertEqual(len(self.decoder.seen), 1)

    def test_bad_grid_mapping_fails_at_first_message(self):
        cases = (("distance", -1), ("distance", 6), ("distance", float("nan")),
                 ("index", -.1), ("index", .5), ("index", True), ("index", 761*761),
                 ("lat", float("nan")), ("lon", float("inf")))
        for key, value in cases:
            self.setUp()
            self.nearest[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.decoder.decode(b"fake", "T_2M", RUN, 1)
            self.ec.codes_release.assert_called_once_with(self.handle)


class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.valid = snapshot_fixture()

    def setUp(self):
        self.snapshot = copy.deepcopy(self.valid)

    def test_synthetic_full_215_by_73_snapshot_validates(self):
        pilot.validate_snapshot(self.snapshot)

    def test_schema_kind_and_missing_fields_fail_closed(self):
        for key, value in (("schema_version", 2), ("kind", "estimated_data")):
            changed = dict(self.snapshot, **{key: value})
            with self.assertRaises(ValueError):
                pilot.validate_snapshot(changed)
        self.snapshot["raw"].pop("SNOW_GSP")
        with self.assertRaises(ValueError):
            pilot.validate_snapshot(self.snapshot)

    def test_extra_field_is_not_silently_accepted(self):
        self.snapshot["raw"]["UNKNOWN"] = self.snapshot["raw"]["T_2M"]
        with self.assertRaises(ValueError):
            pilot.validate_snapshot(self.snapshot)

    def test_missing_hour_and_tampered_timestamp_are_rejected(self):
        self.snapshot["times_utc"][12] = self.snapshot["times_utc"][11]
        with self.assertRaises(ValueError):
            pilot.validate_snapshot(self.snapshot)

    def test_run_label_must_match_run_code(self):
        self.snapshot["run_utc"] = "2026-09-02T00:00:00Z"
        with self.assertRaises(ValueError):
            pilot.validate_snapshot(self.snapshot)

    def test_exact_municipality_count_and_unique_slugs_are_required(self):
        self.snapshot["points"][1]["slug"] = self.snapshot["points"][0]["slug"]
        with self.assertRaises(ValueError):
            pilot.validate_snapshot(self.snapshot)

    def test_native_field_and_point_counts_are_required(self):
        for member in ("values", "metadata"):
            changed = copy.deepcopy(self.valid)
            changed["raw"]["T_2M"][member].pop()
            with self.assertRaises(ValueError):
                pilot.validate_snapshot(changed)
        self.snapshot["raw"]["T_2M"]["values"][0].pop()
        with self.assertRaises(ValueError):
            pilot.validate_snapshot(self.snapshot)

    def test_nonfinite_boolean_or_text_raw_values_are_rejected(self):
        for value in (float("nan"), float("inf"), True, "293.15", None):
            with self.subTest(value=value):
                self.snapshot["raw"]["T_2M"]["values"][0][0] = value
                with self.assertRaises(ValueError):
                    pilot.validate_snapshot(self.snapshot)

    def test_grid_hash_changes_are_rejected(self):
        self.snapshot["raw"]["T_2M"]["metadata"][12]["md5GridSection"] = "d"*32
        with self.assertRaises(ValueError):
            pilot.validate_snapshot(self.snapshot)

    def test_tampered_quantum_is_not_trusted_on_replay(self):
        self.snapshot["raw"]["TOT_PREC"]["metadata"][12]["encoding_quantum_mm"] = 0.0
        with self.assertRaises(ValueError):
            pilot.validate_snapshot(self.snapshot)

    def test_nonfinite_or_out_of_range_point_coordinates_are_rejected(self):
        for key, value in (("latitude", float("nan")), ("latitude", 91), ("longitude", -181), ("latitude", True)):
            changed = copy.deepcopy(self.valid)
            changed["points"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                pilot.validate_snapshot(changed)

    def test_invalid_mapping_distance_or_index_is_rejected(self):
        for key, value in (("distance", float("nan")), ("distance", -1), ("distance", 6),
                           ("index", -1), ("index", 761*761), ("index", .5), ("lat", float("nan"))):
            changed = copy.deepcopy(self.valid)
            changed["grid_points"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                pilot.validate_snapshot(changed)


class DeriveTests(unittest.TestCase):
    def test_near_north_wind_direction_wraps_after_rounding(self):
        snapshot = snapshot_fixture()
        snapshot["raw"]["U_10M"]["values"][1][0] = 0.000001
        snapshot["raw"]["V_10M"]["values"][1][0] = -1.0
        snapshot["raw"]["U_10M"]["values"][2][0] = 0.0
        snapshot["raw"]["V_10M"]["values"][2][0] = 0.0

        payload = pilot.derive(snapshot, now=RUN_TIME + timedelta(hours=12))
        hourly = payload["municipalities"][0]["hourly"]
        self.assertEqual(hourly[1]["wind_from_degrees"], 0.0)
        self.assertIsNone(hourly[2]["wind_from_degrees"])
        self.assertTrue(
            all(
                row["wind_from_degrees"] is None
                or 0 <= row["wind_from_degrees"] < 360
                for town in payload["municipalities"]
                for row in town["hourly"]
            )
        )

    def test_entire_215_by_73_synthetic_chain_preserves_semantics_and_limits(self):
        snapshot = snapshot_fixture()
        snapshot["raw"]["WW"]["values"][2][0] = 99
        snapshot["raw"]["CLCT"]["values"][3][0] = 150
        snapshot["raw"]["TD_2M"]["values"][4][0] = 294.15
        snapshot["raw"]["VMAX_10M"]["values"][5][0] = -2
        snapshot["raw"]["TOT_PREC"]["values"][10][0] = 8.9995
        snapshot["raw"]["TOT_PREC"]["values"][20][0] = 18.0
        before = hashlib.sha256(pilot.compact_json(snapshot)).hexdigest()
        payload = pilot.derive(snapshot, now=RUN_TIME+timedelta(hours=12, minutes=30))
        self.assertEqual(hashlib.sha256(pilot.compact_json(snapshot)).hexdigest(), before)
        self.assertEqual(len(payload["municipalities"]), 215)
        self.assertTrue(all(len(town["hourly"]) == 73 for town in payload["municipalities"]))
        self.assertTrue(all(len(town["two_hourly"]) == 36 for town in payload["municipalities"]))
        self.assertEqual(payload["validation"]["status"], "fresh")
        self.assertEqual(payload["validation"]["coverage_hours"], 59.5)
        self.assertEqual(payload["status"], "partial_pilot_not_production")
        self.assertEqual(payload["sources"]["cams"]["status"], "not_acquired")
        self.assertEqual(payload["sources"]["observations"]["status"], "not_compared")
        town = payload["municipalities"][0]
        hourly = town["hourly"]
        self.assertEqual(town["current"]["valid_at_utc"], pilot.iso(RUN_TIME+timedelta(hours=12)))
        self.assertIsNone(town["pollen"]["values"])
        self.assertEqual(town["daily"], [])
        self.assertEqual(hourly[1]["temperature_c"], 20)
        self.assertEqual(hourly[1]["pressure_msl_hpa"], 1013.25)
        self.assertEqual(hourly[1]["wind_m_s"], 2)
        self.assertEqual(hourly[1]["wind_from_degrees"], 270)
        self.assertEqual(hourly[1]["wind_gust_m_s"], 10)
        self.assertAlmostEqual(hourly[1]["relative_humidity_pct"], 52.56, delta=.1)
        self.assertIsNotNone(hourly[1]["apparent_temperature_c"])
        self.assertIsNone(hourly[1]["heat_index_c"])
        self.assertIsNone(hourly[1]["wind_chill_c"])
        self.assertEqual(hourly[1]["condition"]["status"], "valid")
        self.assertNotIn("WW_unknown_or_unverified", hourly[1]["quality_flags"])
        self.assertEqual(hourly[2]["condition"]["status"], "unknown")
        self.assertIn("WW_unknown_or_unverified", hourly[2]["quality_flags"])
        self.assertIsNone(hourly[3]["cloud_cover_pct"])
        self.assertIn("invalid_cloud_cover", hourly[3]["quality_flags"])
        self.assertIsNone(hourly[4]["relative_humidity_pct"])
        self.assertIsNone(hourly[4]["apparent_temperature_c"])
        self.assertIn("invalid_T_Td_for_RH_no_clipping", hourly[4]["quality_flags"])
        self.assertIsNone(hourly[5]["wind_gust_m_s"])
        self.assertIsNone(hourly[0]["wind_gust_m_s"])
        self.assertIsNone(hourly[0]["precipitation_previous_hour_mm"])
        self.assertEqual(hourly[1]["precipitation_previous_hour_mm"], 1)
        self.assertAlmostEqual(hourly[1]["rain_previous_hour_mm"], .8)
        self.assertAlmostEqual(hourly[1]["convective_rain_previous_hour_mm"], .1)
        self.assertAlmostEqual(hourly[1]["snow_water_equivalent_previous_hour_mm"], .1)
        self.assertAlmostEqual(hourly[1]["graupel_water_equivalent_previous_hour_mm"], .1)
        self.assertEqual(hourly[1]["precipitation_encoding"]["SNOW_CON"]["value_mm"], 0)
        self.assertEqual(hourly[1]["precipitation_encoding"]["SNOW_CON"]["uncertainty_mm"], 0)
        self.assertEqual(hourly[10]["precipitation_encoding"]["TOT_PREC"]["status"], "negative_within_encoding_resolution")
        self.assertLess(hourly[10]["precipitation_encoding"]["TOT_PREC"]["raw_increment_mm"], 0)
        self.assertIsNone(hourly[10]["precipitation_previous_hour_mm"])
        self.assertEqual(hourly[20]["precipitation_encoding"]["TOT_PREC"]["status"], "invalid")
        self.assertIsNone(hourly[20]["precipitation_previous_hour_mm"])
        self.assertIsNone(hourly[1]["precipitation_probability_pct"])
        self.assertIsNone(hourly[1]["visibility_m"])
        first_pair = town["two_hourly"][0]
        self.assertEqual(first_pair["precipitation_mm"], 2)
        self.assertEqual(first_pair["wind_gust_max_m_s"], 10)
        self.assertIn("WW_unknown_or_unverified", first_pair["quality_flags"])
        self.assertEqual(payload["quality_flag_counts"]["WW_unknown_or_unverified"], 1)
        self.assertEqual(payload["quality_flag_counts"]["TOT_PREC:negative_within_encoding_resolution"], 1)
        self.assertEqual(payload["quality_flag_counts"]["TOT_PREC:invalid"], 1)
        json.dumps(payload, allow_nan=False)


class OutputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="meteofriul-pilot-test-")
        self.root = Path(self.directory.name)
        self.source = self.root/"source.json"
        self.payload = self.root/"payload.json"
        self.report = self.root/"report.json"

    def tearDown(self):
        self.directory.cleanup()

    def call(self, **changes):
        args = dict(source_path=self.source, payload_path=self.payload, report_path=self.report)
        args.update(changes)
        return pilot.run_outputs(**args)

    def test_existing_output_is_never_overwritten_and_no_network_starts(self):
        for path in (self.source, self.payload, self.report):
            with self.subTest(path=path):
                pilot.write_new(path, {"original": True})
                before = path.read_bytes()
                with patch.object(pilot, "acquire") as acquire, self.assertRaises(ValueError):
                    self.call()
                acquire.assert_not_called()
                self.assertEqual(path.read_bytes(), before)
                path.unlink()

    def test_alias_outputs_are_rejected_before_acquisition(self):
        with patch.object(pilot, "acquire") as acquire, self.assertRaises(ValueError):
            self.call(payload_path=self.source)
        acquire.assert_not_called()

    def test_missing_output_parent_is_rejected_before_acquisition(self):
        with patch.object(pilot, "acquire") as acquire, self.assertRaises(ValueError):
            self.call(payload_path=self.root/"missing"/"out.json")
        acquire.assert_not_called()

    def test_checkpoint_cannot_alias_or_contain_a_final_output(self):
        for checkpoint in (self.source, self.root):
            with self.subTest(checkpoint=checkpoint), patch.object(pilot, "acquire") as acquire, self.assertRaises(ValueError):
                self.call(checkpoint_dir=checkpoint)
            acquire.assert_not_called()

    def test_live_acquisition_automatically_uses_source_bound_checkpoint_directory(self):
        snapshot = {"complete_extraction": True}
        with (
            patch.object(pilot, "acquire", return_value=snapshot) as acquire,
            patch.object(pilot, "derive", side_effect=ValueError("stop after source")),
            self.assertRaisesRegex(ValueError, "stop after source"),
        ):
            self.call()
        acquire.assert_called_once_with(
            None,
            checkpoint_dir=self.root / "source.json.checkpoint",
            source_run_high_water=None,
        )

    def test_offline_replay_rejects_live_checkpoint_argument(self):
        pilot.write_new(self.source, {"original": True})
        with patch.object(pilot, "acquire") as acquire, self.assertRaisesRegex(ValueError, "Offline replay"):
            self.call(source_path=None, replay=self.source, checkpoint_dir=self.root / "checkpoint")
        acquire.assert_not_called()

    def test_write_new_uses_exclusive_creation(self):
        pilot.write_new(self.source, {"original": 1})
        original = self.source.read_bytes()
        with self.assertRaises(FileExistsError):
            pilot.write_new(self.source, {"replacement": 2})
        self.assertEqual(self.source.read_bytes(), original)

    def test_failed_acquisition_does_not_create_payload_or_replace_source(self):
        with patch.object(pilot, "acquire", side_effect=ValueError("network failed")), self.assertRaisesRegex(ValueError, "network failed"):
            self.call()
        self.assertFalse(any(path.exists() for path in (self.source, self.payload, self.report)))

    def test_failed_derivation_preserves_complete_extracted_snapshot(self):
        snapshot = {"complete_extraction": True}
        with patch.object(pilot, "acquire", return_value=snapshot), patch.object(pilot, "derive", side_effect=ValueError("derive failed")), self.assertRaisesRegex(ValueError, "derive failed"):
            self.call()
        self.assertEqual(json.loads(self.source.read_text()), snapshot)
        self.assertFalse(self.payload.exists())
        self.assertFalse(self.report.exists())

    def test_replay_source_is_never_overwritten_on_failure(self):
        pilot.write_new(self.source, {"original": True})
        before = self.source.read_bytes()
        with patch.object(pilot, "acquire") as acquire, patch.object(pilot, "derive", side_effect=ValueError("bad replay")), self.assertRaises(ValueError):
            self.call(source_path=None, replay=self.source)
        acquire.assert_not_called()
        self.assertEqual(self.source.read_bytes(), before)
        self.assertFalse(self.payload.exists())
        self.assertFalse(self.report.exists())

    def test_output_cannot_alias_replay_source(self):
        pilot.write_new(self.source, {"original": True})
        before = self.source.read_bytes()
        with patch.object(pilot, "acquire") as acquire, self.assertRaises(ValueError):
            self.call(source_path=None, replay=self.source, payload_path=self.source)
        acquire.assert_not_called()
        self.assertEqual(self.source.read_bytes(), before)

    def test_successful_offline_replay_is_explicit_and_hashes_actual_output(self):
        snapshot = snapshot_fixture()
        pilot.write_new(self.source, snapshot)
        source_bytes = self.source.read_bytes()
        minimal_payload = pilot.derive(snapshot)
        with patch.object(pilot, "acquire") as acquire, patch.object(pilot, "derive", return_value=minimal_payload), patch("process_memory.process_memory_bytes", return_value={"peak_working_set_bytes": 100}), patch("builtins.print"):
            report = self.call(source_path=None, replay=self.source)
        acquire.assert_not_called()
        self.assertEqual(self.source.read_bytes(), source_bytes)
        self.assertEqual(report["execution_mode"], "offline_replay")
        self.assertEqual(report["metrics"]["execution_mode"], "offline_replay")
        self.assertEqual(report["payload_bytes"], self.payload.stat().st_size)
        self.assertEqual(report["payload_sha256"], hashlib.sha256(self.payload.read_bytes()).hexdigest())
        self.assertEqual(report["source_snapshot_sha256"], hashlib.sha256(source_bytes).hexdigest())
        self.assertEqual(report["source_quality"]["source_snapshot_sha256"], report["source_snapshot_sha256"])
        self.assertEqual(json.loads(self.report.read_text())["source_quality"], report["source_quality"])
        self.assertEqual(report["municipalities"], 215)
        self.assertEqual(len(report["single_municipality_sizes"]), 215)
        self.assertEqual(json.loads(self.report.read_text())["payload_sha256"], report["payload_sha256"])


if __name__ == "__main__":
    unittest.main()
