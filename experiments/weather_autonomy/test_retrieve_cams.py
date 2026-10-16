"""Offline security/budget tests using fake credentials and fake ADS objects.

Never reads the user's credential file and never contacts authenticated APIs.
Run with the isolated pilot venv containing the pinned official client 0.5.3.
"""

import contextlib
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import warnings

import requests
import retrieve_cams as cams
from cams_test_fixtures import TEST_DATE, write_valid_plan


FAKE_TOKEN = "synthetic-unit-test-token-do-not-log"
JOB_ID = "12345678-1234-1234-1234-123456789abc"
RESULT_URL = "https://object-store.os-api.cci2.ecmwf.int/result.grib?signature=" + FAKE_TOKEN


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cams-fake-credentials-test-")
        self.path = Path(self.temp.name)/"fake-only.txt"

    def tearDown(self):
        self.temp.cleanup()

    def fake(self, text):
        self.path.write_text(text, encoding="utf-8")
        return self.path

    def test_minimal_official_credentials_and_bom_comments(self):
        path = self.fake(f"\ufeff# fake credentials for unit testing\nurl: {cams.ADS_URL}\nkey: {FAKE_TOKEN}\n")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cams.load_credentials(path), (cams.ADS_URL, FAKE_TOKEN))
        self.assertEqual(output.getvalue(), "")

    def test_missing_file_empty_and_oversized_file(self):
        with self.assertRaises(cams.PilotError):
            cams.load_credentials(self.path)
        for text in ("", "x"*4097):
            with self.subTest(size=len(text)), self.assertRaises(cams.PilotError):
                cams.load_credentials(self.fake(text))

    def test_only_exact_official_api_url_is_accepted(self):
        for url in ("https://example.com/api", "http://ads.atmosphere.copernicus.eu/api", cams.ADS_URL+"/", "https://ads.atmosphere.copernicus.eu.evil.invalid/api", "https://user@ads.atmosphere.copernicus.eu/api"):
            with self.subTest(url=url), self.assertRaises(cams.PilotError):
                cams.load_credentials(self.fake(f"url: {url}\nkey: {FAKE_TOKEN}"))

    def test_missing_duplicate_unknown_and_invalid_key_fields(self):
        samples = (f"url: {cams.ADS_URL}", f"key: {FAKE_TOKEN}", f"url: {cams.ADS_URL}\nkey: {FAKE_TOKEN}\nkey: other",
                   f"url: {cams.ADS_URL}\nkey: {FAKE_TOKEN}\nverify: false", f"url: {cams.ADS_URL}\nkey: two words",
                   f"url: {cams.ADS_URL}\nkey: {'x'*2049}", f"url: {cams.ADS_URL}\n{FAKE_TOKEN}")
        for text in samples:
            with self.subTest(sample_length=len(text)), self.assertRaises(cams.PilotError) as error:
                cams.load_credentials(self.fake(text))
            self.assertNotIn(FAKE_TOKEN, str(error.exception))


class ApiBoundaryTests(unittest.TestCase):
    def test_official_api_subpaths_and_https_port_443_are_allowed(self):
        for url in (cams.ADS_URL+"/retrieve/v1/processes/x", "https://ads.atmosphere.copernicus.eu:443/api/catalogue/v1/messages"):
            self.assertTrue(cams.is_ads_api(url))

    def test_foreign_host_insecure_scheme_userinfo_and_wrong_path_are_rejected(self):
        urls = ("https://example.com/api/x", "http://ads.atmosphere.copernicus.eu/api/x", "https://ads.atmosphere.copernicus.eu.evil.invalid/api/x",
                "https://user:pass@ads.atmosphere.copernicus.eu/api/x", "https://ads.atmosphere.copernicus.eu:444/api/x",
                "https://ads.atmosphere.copernicus.eu/not-api/x", "https://ads.atmosphere.copernicus.eu/apix/x")
        for url in urls:
            with self.subTest(url=url):
                self.assertFalse(cams.is_ads_api(url))

    def test_forbidden_requests_are_blocked_before_transport(self):
        session = cams.AdsOnlySession()
        with patch.object(requests.Session, "request") as transport, self.assertRaises(cams.PilotError):
            session.get("https://other.invalid/api/x", headers={"PRIVATE-TOKEN": FAKE_TOKEN})
        transport.assert_not_called()
        session.close()

    def test_redirect_is_refused_and_response_closed(self):
        for status in (301, 302, 307, 308):
            session = cams.AdsOnlySession()
            response = Mock(status_code=status)
            with patch.object(requests.Session, "request", return_value=response) as transport, self.subTest(status=status), self.assertRaises(cams.PilotError):
                session.get(cams.ADS_URL+"/retrieve/x", allow_redirects=True)
            self.assertFalse(transport.call_args.kwargs["allow_redirects"])
            response.close.assert_called_once()
            session.close()

    def test_no_api_retry_in_session(self):
        session = cams.AdsOnlySession()
        with patch.object(requests.Session, "request", side_effect=requests.ConnectionError(FAKE_TOKEN)) as transport, self.assertRaises(requests.ConnectionError):
            session.post(cams.ADS_URL+"/retrieve/execution")
        transport.assert_called_once()
        session.close()

    def test_official_retry_wrapper_with_one_try_calls_only_once(self):
        from multiurl import robust
        call = Mock(side_effect=requests.ConnectionError("synthetic failure"))
        with self.assertRaises(requests.ConnectionError):
            robust(call, maximum_tries=1, retry_after=0)("POST")
        call.assert_called_once()


class MetadataTests(unittest.TestCase):
    def test_regional_scope_contains_all_catalog_municipalities_with_margin(self):
        area, metadata = cams.study_scope("fvg")
        self.assertEqual(tuple(area), (46.7, 12.2, 45.5, 14.0))
        self.assertEqual(metadata["municipality_count"], 215)
        self.assertEqual(len({point["slug"] for point in metadata["municipalities"]}), 215)
        self.assertEqual(len(metadata["catalog_sha256"]), 64)

    def test_unknown_scope_rejected(self):
        with self.assertRaises(cams.PilotError):
            cams.study_scope("europe")

    def test_only_status_and_normalized_timestamps_survive(self):
        raw = {"status": "successful", "created": "2026-09-03T12:00:00+02:00", "finished": "2026-09-03T10:01:00Z",
               "log": FAKE_TOKEN, "request": {"key": FAKE_TOKEN}, "location": RESULT_URL, "links": [RESULT_URL], "user": FAKE_TOKEN}
        result = cams.safe_job_metadata(raw)
        self.assertEqual(set(result), {"status", "created", "finished"})
        self.assertEqual(result["created"], "2026-09-03T10:00:00Z")
        self.assertNotIn(FAKE_TOKEN, json.dumps(result))

    def test_unknown_status_and_invalid_times_are_rejected(self):
        for raw in ({"status": FAKE_TOKEN}, {"status": "running", "created": FAKE_TOKEN}, {"status": "running", "created": 123}):
            with self.assertRaises(cams.PilotError) as error:
                cams.safe_job_metadata(raw)
            self.assertNotIn(FAKE_TOKEN, str(error.exception))

    def test_naive_ads_timestamps_match_pinned_official_client_utc_semantics(self):
        from ecmwf.datastores.utils import string_to_datetime
        naive = "2026-09-03T10:00:00.125"
        expected = string_to_datetime(naive).isoformat().replace("+00:00", "Z")
        self.assertEqual(cams.safe_job_metadata({"status": "running", "created": naive})["created"], expected)

    def test_durations_are_separate_and_missing_times_are_not_zero(self):
        result = cams.job_durations({"created": "2026-09-03T10:00:00Z", "started": "2026-09-03T10:01:00Z", "finished": "2026-09-03T10:01:30Z"})
        self.assertEqual(result, {"server_queue_seconds": 60, "server_processing_seconds": 30, "server_total_seconds": 90})
        self.assertTrue(all(value is None for value in cams.job_durations({}).values()))

    def test_negative_server_duration_is_not_hidden(self):
        with self.assertRaises(cams.PilotError):
            cams.job_durations({"created": "2026-09-03T10:00:00Z", "started": "2026-09-03T09:59:59Z"})


class FakeResponse:
    def __init__(self, body=b"GRIB7777", status=200, headers=None, chunks=None):
        self.body = body
        self.status_code = status
        self.headers = {"Content-Length": str(len(body)), "Content-Encoding": "identity"} if headers is None else headers
        self.chunks = chunks
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def iter_content(self, chunk_size):
        if self.chunks is None:
            yield self.body
        else:
            yield from self.chunks


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cams-fake-download-test-")
        self.path = Path(self.temp.name)/"result.grib"
        self.results = SimpleNamespace(location=RESULT_URL, content_length=8, content_type="application/x-grib")
        self.identity = {
            "dataset": cams.DATASET,
            "request_id": JOB_ID,
            "run_date": TEST_DATE,
            "request_plan_sha256": "a" * 64,
            "request_sha256": "b" * 64,
        }

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, response=None):
        response = response or FakeResponse()
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        session.get.return_value = response
        with patch.object(cams.requests, "Session", return_value=session):
            result = cams.download_result(
                self.results, self.path, identity=self.identity
            )
        return result, session, response

    def test_download_uses_separate_session_without_auth_netrc_or_redirects(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result, session, response = self.invoke()
        self.assertFalse(session.trust_env)
        kwargs = session.get.call_args.kwargs
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["headers"], {"Accept-Encoding": "identity"})
        self.assertNotIn("auth", kwargs)
        self.assertEqual(self.path.read_bytes(), b"GRIB7777")
        self.assertEqual(result["sha256"], hashlib.sha256(b"GRIB7777").hexdigest())
        self.assertFalse(result["credentials_sent_to_result_host"])
        self.assertNotIn(FAKE_TOKEN, json.dumps(result)+output.getvalue())
        self.assertTrue(response.closed)

    def test_foreign_result_host_userinfo_and_port_are_refused_before_download(self):
        for url in ("http://object-store.ecmwf.int/r", "https://example.com/r", "https://x.ecmwf.int.evil.invalid/r", "https://user:pass@x.ecmwf.int/r", "https://x.ecmwf.int:444/r"):
            self.results.location = url
            with self.subTest(url=url), patch.object(cams.requests, "Session") as session, self.assertRaises(cams.PilotError):
                cams.download_result(self.results, self.path, identity=self.identity)
            session.assert_not_called()

    def test_zero_or_oversized_result_is_rejected_before_session(self):
        for size in (0, -1, cams.MAX_DOWNLOAD_BYTES+1):
            self.results.content_length = size
            with patch.object(cams.requests, "Session") as session, self.assertRaises(cams.PilotError):
                cams.download_result(self.results, self.path, identity=self.identity)
            session.assert_not_called()

    def test_result_type_must_be_positive_integer_not_bool(self):
        for size in (True, 8.5, "8"):
            self.results.content_length = size
            with self.subTest(size=size), self.assertRaises(cams.PilotError):
                self.invoke()
            self.assertFalse(self.path.exists())

    def test_unexpected_content_type_cannot_persist_arbitrary_provider_strings(self):
        for content_type in ("text/html", "application/zip", RESULT_URL, FAKE_TOKEN, None):
            self.results.content_type = content_type
            with self.subTest(content_type=content_type), self.assertRaises(cams.PilotError) as error:
                self.invoke()
            self.assertNotIn(FAKE_TOKEN, str(error.exception))
            self.assertFalse(self.path.exists())

    def test_redirect_or_failure_is_not_followed(self):
        for status in (206, 302, 307, 403, 500):
            with self.subTest(status=status), self.assertRaises(cams.PilotError):
                self.invoke(FakeResponse(status=status))
            self.assertFalse(self.path.exists())

    def test_content_length_mismatch_rejected_before_writing(self):
        with self.assertRaises(cams.PilotError):
            self.invoke(FakeResponse(headers={"Content-Length": "9"}))
        self.assertFalse(self.path.exists())

    def test_content_encoding_must_be_identity(self):
        with self.assertRaises(cams.PilotError):
            self.invoke(FakeResponse(headers={"Content-Length": "8", "Content-Encoding": "gzip"}))
        self.assertFalse(self.path.exists())

    def test_extra_or_truncated_bytes_never_succeed(self):
        for body in (b"GRIB777", b"GRIB7777extra"):
            with self.subTest(size=len(body)), self.assertRaises(cams.PilotError):
                self.invoke(FakeResponse(body=body, headers={"Content-Length": "8"}))
            if self.path.exists():
                self.path.unlink()

    def test_marked_partial_is_replaced_only_when_same_job_is_resumed(self):
        with self.assertRaises(cams.PilotError):
            self.invoke(FakeResponse(body=b"GRIB777", headers={"Content-Length": "8"}))
        partial = self.path.with_name(self.path.name + ".part")
        marker = self.path.with_name(self.path.name + ".part.json")
        self.assertFalse(self.path.exists())
        self.assertEqual(partial.read_bytes(), b"GRIB777")
        self.assertTrue(marker.is_file())

        result, _, _ = self.invoke()
        self.assertEqual(result["download_bytes"], 8)
        self.assertEqual(self.path.read_bytes(), b"GRIB7777")
        self.assertFalse(partial.exists())
        self.assertFalse(marker.exists())

    def test_unmarked_or_foreign_partial_is_never_deleted(self):
        partial = self.path.with_name(self.path.name + ".part")
        marker = self.path.with_name(self.path.name + ".part.json")
        partial.write_bytes(b"unowned")
        with self.assertRaisesRegex(cams.PilotError, "Unmarked partial"):
            self.invoke()
        self.assertEqual(partial.read_bytes(), b"unowned")

        partial.unlink()
        foreign = dict(
            cams._partial_download_record(
                self.path,
                expected=8,
                content_type=self.results.content_type,
                host="object-store.os-api.cci2.ecmwf.int",
                identity=self.identity,
            )
        )
        foreign["request_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        cams.write_new(marker, foreign)
        partial.write_bytes(b"foreign")
        with self.assertRaisesRegex(cams.PilotError, "does not match"):
            self.invoke()
        self.assertEqual(partial.read_bytes(), b"foreign")
        self.assertTrue(marker.exists())

    def test_download_wall_time_limit(self):
        with patch.object(cams.time, "perf_counter", side_effect=[0, 181]), self.assertRaises(cams.PilotError):
            self.invoke()

    def test_existing_output_is_never_overwritten(self):
        self.path.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            self.invoke()
        self.assertEqual(self.path.read_bytes(), b"original")


class RetrievalFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cams-retrieval-flow-test-")
        self.directory = Path(self.temp.name)/f"artifacts-{TEST_DATE}"
        self.plan_path, self.plan, self.plan_bytes, self.plan_hash = write_valid_plan(
            self.temp.name, area=cams.PORDENONE_AREA
        )
        self.client = Mock()
        self.remote = Mock()
        self.remote.request_id = JOB_ID
        self.remote.json = {"status": "successful", "created": "2026-09-03T10:00:00Z", "started": "2026-09-03T10:00:10Z", "finished": "2026-09-03T10:00:20Z", "logs": FAKE_TOKEN}
        self.client.submit.return_value = self.remote
        self.client.get_remote.return_value = self.remote
        self.download = {"download_bytes": 8, "download_seconds": .1, "sha256": "a"*64, "result_host": "object-store.os-api.cci2.ecmwf.int", "credentials_sent_to_result_host": False}

    def tearDown(self):
        self.temp.cleanup()

    def run_fake(self, *, constructor=None, **kwargs):
        constructor = constructor or Mock(return_value=self.client)
        scope = kwargs.get("scope", "pordenone")
        if scope == "fvg":
            fvg_plan_directory = Path(self.temp.name) / "fvg-plan"
            fvg_plan_directory.mkdir()
            self.plan_path, self.plan, self.plan_bytes, self.plan_hash = write_valid_plan(
                fvg_plan_directory, area=cams.DEFAULT_AREA
            )
        kwargs.setdefault("request_plan_path", self.plan_path)
        if "resume" not in kwargs:
            kwargs.setdefault("artifacts_directory", self.directory)
        with patch.object(cams, "load_credentials", return_value=(cams.ADS_URL, FAKE_TOKEN)), patch.object(cams.importlib.metadata, "version", return_value="0.5.3"), patch("ecmwf.datastores.Client", constructor), patch.object(cams, "download_result", return_value=self.download) as download, contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as errors:
            report = cams.retrieve(Path("FAKE-NOT-A-REAL-CREDENTIAL-FILE"), **kwargs)
        self.assertNotIn(FAKE_TOKEN, output.getvalue()+errors.getvalue())
        for path in self.directory.glob("*.json"):
            self.assertNotIn(FAKE_TOKEN, path.read_text(encoding="utf-8"))
        return report, constructor, download

    def prepare_resume(self, *, scope="pordenone", request_id=JOB_ID):
        if scope == "fvg":
            fvg_plan_directory = Path(self.temp.name) / "fvg-plan"
            fvg_plan_directory.mkdir()
            self.plan_path, self.plan, self.plan_bytes, self.plan_hash = write_valid_plan(
                fvg_plan_directory, area=cams.DEFAULT_AREA
            )
        area, scope_metadata = cams.study_scope(scope)
        self.directory.mkdir()
        (self.directory / "request-plan.json").write_bytes(self.plan_bytes)
        record = cams._request_record(self.plan, self.plan_hash, scope, scope_metadata)
        cams.write_new(self.directory / "request.json", record)
        cams.write_new(
            self.directory / "submission-intent.json",
            {
                "schema_version": 2,
                "at_utc": f"{TEST_DATE}T10:00:00Z",
                "dataset": cams.DATASET,
                "scope": scope,
                "run_date": TEST_DATE,
                "request_plan_sha256": self.plan_hash,
                "request_sha256": record["request_sha256"],
                "post_retries": 0,
            },
        )
        cams.write_new(
            self.directory / "job.json",
            {
                "schema_version": 2,
                "dataset": cams.DATASET,
                "request_id": request_id,
                "scope": scope,
                "run_date": TEST_DATE,
                "request_plan_sha256": self.plan_hash,
                "request_sha256": record["request_sha256"],
            },
        )
        return record

    def test_single_submission_preserves_correct_scope_and_safety_options(self):
        report, constructor, download = self.run_fake()
        self.client.submit.assert_called_once()
        dataset, request = self.client.submit.call_args.args
        self.assertEqual(dataset, cams.DATASET)
        self.assertEqual(request["area"], [46.1, 12.5, 45.8, 12.8])
        self.assertEqual(request["model"], ["ensemble"])
        self.assertEqual(request["level"], ["0"])
        self.assertEqual(len(request["variable"]), 28)
        self.assertEqual(request["leadtime_hour"], [str(hour) for hour in range(97)])
        self.assertEqual(request["data_format"], "grib")
        options = constructor.call_args.kwargs
        self.assertEqual(options["url"], cams.ADS_URL)
        self.assertEqual(options["key"], FAKE_TOKEN)
        self.assertFalse(options["session"].trust_env)
        self.assertIsInstance(options["session"], cams.AdsOnlySession)
        self.assertEqual(options["maximum_tries"], 1)
        self.assertFalse(options["cleanup"])
        self.assertFalse(options["progress"])
        self.assertEqual(report["status"], "downloaded_pending_decode_validation")
        self.assertEqual(report["server_queue_seconds"], 10)
        self.assertEqual(report["request_plan_sha256"], self.plan_hash)
        request_record = json.loads((self.directory / "request.json").read_text(encoding="utf-8"))
        intent = json.loads((self.directory / "submission-intent.json").read_text(encoding="utf-8"))
        job = json.loads((self.directory / "job.json").read_text(encoding="utf-8"))
        self.assertEqual((self.directory / "request-plan.json").read_bytes(), self.plan_bytes)
        self.assertEqual({request_record["request_plan_sha256"], intent["request_plan_sha256"], job["request_plan_sha256"]}, {self.plan_hash})
        self.assertEqual({request_record["request_sha256"], intent["request_sha256"], job["request_sha256"]}, {report["request_sha256"]})
        self.remote._make_results.assert_called_once_with(wait=False)
        download.assert_called_once()
        self.remote.delete.assert_not_called()

    def test_submission_intent_exists_before_post_and_ambiguous_error_is_not_retried(self):
        def submit(*args):
            self.assertTrue((self.directory/"submission-intent.json").exists())
            raise requests.ConnectionError("transport detail " + FAKE_TOKEN)
        self.client.submit.side_effect = submit
        report, _, download = self.run_fake()
        self.assertEqual(report["status"], "stopped")
        self.assertNotIn("safe_reason", report)
        self.client.submit.assert_called_once()
        download.assert_not_called()
        self.assertFalse((self.directory/"job.json").exists())
        self.assertTrue((self.directory/"submission-intent.json").exists())

    def test_regional_request_is_one_post_not_one_per_municipality(self):
        report, _, _ = self.run_fake(scope="fvg")
        self.client.submit.assert_called_once()
        request = self.client.submit.call_args.args[1]
        self.assertEqual(request["area"], [46.7, 12.2, 45.5, 14.0])
        self.assertEqual(len(request["variable"])*len(request["leadtime_hour"]), 2716)
        saved = json.loads((self.directory/"request.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["scope_metadata"]["municipality_count"], 215)
        self.assertEqual(report["scope"], "fvg")

    def test_resume_refuses_different_scope(self):
        self.prepare_resume(scope="fvg")
        with patch.object(cams, "load_credentials") as credentials, self.assertRaises(cams.PilotError):
            cams.retrieve(Path("FAKE"), request_plan_path=self.plan_path,
                          resume=self.directory, scope="pordenone")
        credentials.assert_not_called()
        self.client.get_remote.assert_not_called()
        self.client.submit.assert_not_called()

    def test_constructor_warnings_never_emit_provider_exception_text(self):
        def constructor(**kwargs):
            warnings.warn("provider token or signed URL " + FAKE_TOKEN, UserWarning)
            return self.client
        report, _, _ = self.run_fake(constructor=constructor)
        self.assertEqual(report["status"], "downloaded_pending_decode_validation")

    def test_constructor_failure_is_static_and_no_post_occurs(self):
        report, _, download = self.run_fake(constructor=Mock(side_effect=RuntimeError(FAKE_TOKEN)))
        self.assertEqual(report["status"], "stopped")
        self.client.submit.assert_not_called()
        download.assert_not_called()

    def test_provider_http_error_stores_status_only(self):
        response = requests.Response()
        response.status_code = 403
        self.client.submit.side_effect = requests.HTTPError(FAKE_TOKEN, response=response)
        report, _, _ = self.run_fake()
        self.assertEqual(report["http_status"], 403)
        self.assertNotIn("safe_reason", report)

    def test_remote_failure_never_attempts_download_or_deletes_job(self):
        self.remote.json = {"status": "failed", "log": FAKE_TOKEN}
        report, _, download = self.run_fake()
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(report["last_job_metadata"], {"status": "failed"})
        download.assert_not_called()
        self.remote.delete.assert_not_called()
        self.assertTrue((self.directory/"job.json").exists())

    def test_wait_budget_stops_with_saved_job_and_no_resubmission(self):
        self.remote.json = {"status": "queued"}
        with patch.object(cams.time, "perf_counter", side_effect=itertools.count(0, 2)), patch.object(cams.time, "sleep") as sleep:
            report, _, download = self.run_fake(max_wait=1)
        self.assertEqual(report["status"], "stopped")
        self.assertIn("wait budget", report["safe_reason"])
        self.client.submit.assert_called_once()
        sleep.assert_not_called()
        download.assert_not_called()
        self.assertTrue((self.directory/"job.json").exists())

    def test_explicit_resume_never_posts_again(self):
        self.prepare_resume()
        report, _, _ = self.run_fake(resume=self.directory)
        self.client.submit.assert_not_called()
        self.client.get_remote.assert_called_once_with(JOB_ID)
        self.assertTrue(report["resumed_existing_job"])

    def test_resume_recovers_crash_after_atomic_link_without_credentials(self):
        record = self.prepare_resume()
        final = self.directory / "source.grib"
        partial = self.directory / "source.grib.part"
        marker = self.directory / "source.grib.part.json"
        complete = self.directory / "source.grib.complete.json"
        identity = {
            "dataset": cams.DATASET,
            "request_id": JOB_ID,
            "run_date": TEST_DATE,
            "request_plan_sha256": self.plan_hash,
            "request_sha256": record["request_sha256"],
        }
        base = cams._partial_download_record(
            final,
            expected=8,
            content_type="application/x-grib",
            host="object-store.os-api.cci2.ecmwf.int",
            identity=identity,
        )
        partial.write_bytes(b"GRIB7777")
        cams.write_new(marker, base)
        cams.write_new(
            complete,
            cams._completion_record(base, hashlib.sha256(b"GRIB7777").hexdigest()),
        )
        os.link(partial, final)

        with patch.object(cams, "load_credentials") as credentials, \
                patch.object(cams.importlib.metadata, "version", return_value="0.5.3"), \
                patch("ecmwf.datastores.Client") as client, \
                contextlib.redirect_stdout(io.StringIO()):
            report = cams.retrieve(
                Path("FAKE"), request_plan_path=self.plan_path,
                resume=self.directory, scope="pordenone",
            )
        credentials.assert_not_called()
        client.assert_not_called()
        self.assertEqual(report["status"], "downloaded_pending_decode_validation")
        self.assertTrue(report["download_recovered_after_atomic_publication"])
        self.assertEqual(final.read_bytes(), b"GRIB7777")
        self.assertFalse(partial.exists())
        self.assertFalse(marker.exists())
        self.assertTrue(complete.exists())

    def test_resume_with_existing_download_does_not_overwrite_it(self):
        self.prepare_resume()
        source = self.directory/"source.grib"
        source.write_bytes(b"original data")
        with patch.object(cams, "load_credentials") as credentials, self.assertRaises(cams.PilotError):
            cams.retrieve(Path("FAKE"), request_plan_path=self.plan_path, resume=self.directory)
        credentials.assert_not_called()
        self.client.get_remote.assert_not_called()
        self.client.submit.assert_not_called()
        self.assertEqual(source.read_bytes(), b"original data")

    def test_unreviewed_client_version_never_constructs_client(self):
        with patch.object(cams, "load_credentials", return_value=(cams.ADS_URL, FAKE_TOKEN)), patch.object(cams.importlib.metadata, "version", return_value="0.6.0"), patch("ecmwf.datastores.Client") as client, self.assertRaises(cams.PilotError):
            cams.retrieve(Path("FAKE-NOT-A-REAL-CREDENTIAL-FILE"), request_plan_path=self.plan_path,
                          artifacts_directory=self.directory)
        client.assert_not_called()

    def test_invalid_returned_request_id_is_never_persisted_as_job(self):
        self.remote.request_id = FAKE_TOKEN
        report, _, download = self.run_fake()
        self.assertEqual(report["status"], "stopped")
        self.assertFalse((self.directory/"job.json").exists())
        self.client.submit.assert_called_once()
        download.assert_not_called()

    def test_invalid_saved_job_id_does_not_reach_api(self):
        self.prepare_resume(request_id="../other-job")
        with patch.object(cams, "load_credentials") as credentials, self.assertRaises(cams.PilotError):
            cams.retrieve(Path("FAKE"), request_plan_path=self.plan_path, resume=self.directory)
        credentials.assert_not_called()
        self.client.get_remote.assert_not_called()
        self.client.submit.assert_not_called()

    def test_invalid_wait_budgets_do_not_construct_client(self):
        for wait in (0, -1, 901):
            with patch.object(cams, "load_credentials", return_value=(cams.ADS_URL, FAKE_TOKEN)) as credentials, patch("ecmwf.datastores.Client") as client, self.assertRaises(cams.PilotError):
                cams.retrieve(Path("FAKE-NOT-A-REAL-CREDENTIAL-FILE"), request_plan_path=self.plan_path,
                              artifacts_directory=self.directory, max_wait=wait)
            credentials.assert_not_called()
            client.assert_not_called()

    def test_tampered_plan_stops_before_credentials_client_or_artifacts(self):
        raw = json.loads(self.plan_path.read_text(encoding="utf-8"))
        raw["request_groups"][0]["request"]["leadtime_hour"].pop()
        tampered = Path(self.temp.name) / "tampered-plan.json"
        tampered.write_text(json.dumps(raw), encoding="utf-8")
        with patch.object(cams, "load_credentials") as credentials, patch("ecmwf.datastores.Client") as client, self.assertRaises(cams.PilotError):
            cams.retrieve(Path("FAKE"), request_plan_path=tampered,
                          artifacts_directory=self.directory)
        credentials.assert_not_called()
        client.assert_not_called()
        self.assertFalse(self.directory.exists())

    def test_netcdf_plan_is_rejected_before_credentials(self):
        netcdf_directory = Path(self.temp.name) / "netcdf-plan"
        netcdf_directory.mkdir()
        path, _, _, _ = write_valid_plan(
            netcdf_directory, area=cams.PORDENONE_AREA, data_format="netcdf_zip"
        )
        with patch.object(cams, "load_credentials") as credentials, self.assertRaises(cams.PilotError):
            cams.retrieve(Path("FAKE"), request_plan_path=path,
                          artifacts_directory=self.directory)
        credentials.assert_not_called()

    def test_main_suppresses_warnings_from_entire_retrieval_lifetime(self):
        def retrieval(*args, **kwargs):
            warnings.warn(FAKE_TOKEN, UserWarning)
            return {"status": "stopped"}
        with patch("sys.argv", ["retrieve_cams", "--credentials-file", "FAKE-NOT-A-REAL-CREDENTIAL-FILE",
                                "--request-plan", str(self.plan_path), "--artifacts-directory", str(self.directory)]), patch.object(cams, "retrieve", side_effect=retrieval), contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as errors:
            result = cams.main()
        self.assertEqual(result, 1)
        self.assertNotIn(FAKE_TOKEN, output.getvalue()+errors.getvalue())


if __name__ == "__main__":
    unittest.main()
