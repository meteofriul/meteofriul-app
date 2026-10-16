"""Offline reconciliation tests: synthetic intents/jobs only, no real tokens.

All credential loading and official-client construction are replaced. A global
HTTP transport tripwire makes accidental network access fail before transport.
"""

import contextlib
import copy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import UUID
import warnings

import requests

from cams_request_plan import DATASET
from cams_test_fixtures import TEST_DATE, write_valid_plan
import reconcile_cams_job as subject
import retrieve_cams


FAKE_TOKEN = "synthetic-reconciliation-token-never-real"
FAKE_URL = "https://object-store.os-api.cci2.ecmwf.int/result?signature=" + FAKE_TOKEN
INTENT = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)


def job_id(number):
    return str(UUID(int=number))


def created_at(seconds):
    return (INTENT + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


class FakeSession:
    def __init__(self):
        self.trust_env = True
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class CanonicalTests(unittest.TestCase):
    def test_list_order_is_irrelevant_except_geographic_area(self):
        original = {"variable": ["ozone", "dust"], "leadtime_hour": ["2", "1"],
                    "date": ["2026-09-03"], "area": [46.7, 12.2, 45.5, 14.0]}
        equivalent = copy.deepcopy(original)
        equivalent["variable"].reverse()
        equivalent["leadtime_hour"].reverse()
        snapshot = copy.deepcopy(original)
        self.assertEqual(subject.canonical(original), subject.canonical(equivalent))
        self.assertEqual(original, snapshot)
        equivalent["area"].reverse()
        self.assertNotEqual(subject.canonical(original), subject.canonical(equivalent))

    def test_duplicates_dates_and_extra_keys_are_not_erased(self):
        request = {"variable": ["dust"], "date": ["2026-09-03"]}
        for different in ({"variable": ["dust", "dust"], "date": ["2026-09-03"]},
                          {"variable": ["dust"], "date": ["2026-09-04"]},
                          {**request, "unexpected": "field"}):
            with self.subTest(different=different):
                self.assertNotEqual(subject.canonical(request), subject.canonical(different))


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cams-reconciliation-offline-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / f"artifacts-{TEST_DATE}"
        self.directory.mkdir()
        self.credentials = self.root / "never-read-credentials.txt"
        self.plan_path, self.plan, self.plan_bytes, self.plan_hash = write_valid_plan(
            self.root, area=retrieve_cams.DEFAULT_AREA
        )
        (self.directory / "request-plan.json").write_bytes(self.plan_bytes)
        _, scope_metadata = retrieve_cams.study_scope("fvg")
        self.desired = retrieve_cams._request_record(
            self.plan, self.plan_hash, "fvg", scope_metadata
        )
        self.request = self.desired["request"]
        retrieve_cams.write_new(self.directory / "request.json", self.desired)
        retrieve_cams.write_new(self.directory / "submission-intent.json",
                                {"schema_version": 2, "at_utc": created_at(0),
                                 "dataset": DATASET, "scope": "fvg", "run_date": TEST_DATE,
                                 "request_plan_sha256": self.plan_hash,
                                 "request_sha256": self.desired["request_sha256"], "post_retries": 0})
        self.network = self.start_patch(patch.object(requests.Session, "request",
                                                    side_effect=AssertionError("Network forbidden in offline tests")))
        self.load = self.start_patch(patch.object(subject, "load_credentials",
                                                 return_value=(retrieve_cams.ADS_URL, FAKE_TOKEN)))
        self.session = FakeSession()
        self.session_factory = self.start_patch(patch.object(subject, "ReadOnlyAdsSession", return_value=self.session))
        self.remotes = {}
        self.page = SimpleNamespace(request_ids=[], next=None)
        self.client = Mock()
        self.client.get_jobs.return_value = self.page
        self.client.get_remote.side_effect = lambda identifier: SimpleNamespace(json=self.remotes[identifier])
        self.client.submit.side_effect = AssertionError("Submission forbidden during reconciliation")
        self.client.delete.side_effect = AssertionError("Deletion forbidden during reconciliation")
        self.factory = self.start_patch(patch("ecmwf.datastores.Client", return_value=self.client))

    def start_patch(self, patcher):
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    def add_job(self, number, *, seconds=1, request=None, dataset=DATASET, status="running"):
        identifier = job_id(number)
        raw = {"jobID": identifier, "processID": dataset, "created": created_at(seconds),
               "status": status, "metadata": {"request": {"ids": copy.deepcopy(self.request if request is None else request)}},
               "location": FAKE_URL, "provider_log": FAKE_TOKEN}
        self.page.request_ids.append(identifier)
        self.remotes[identifier] = raw
        return identifier

    def run_reconcile(self):
        with contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
            result = subject.reconcile(
                self.credentials, self.directory,
                request_plan_path=self.plan_path, scope="fvg"
            )
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.network.assert_not_called()
        self.client.submit.assert_not_called()
        self.client.delete.assert_not_called()
        safe_output = json.dumps(result)
        self.assertNotIn(FAKE_TOKEN, safe_output)
        self.assertNotIn(FAKE_URL, safe_output)
        for identifier in self.page.request_ids:
            self.assertNotIn(identifier, safe_output)
        return result

    def assert_no_handle(self):
        self.assertFalse((self.directory / "job.json").exists())

    def test_unique_recent_exact_match_restores_minimal_handle(self):
        identifier = self.add_job(1)
        result = self.run_reconcile()
        self.assertEqual(result, {"result": "unique_existing_job_restored", "job_status": "running", "checked": 1})
        saved = json.loads((self.directory / "job.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["schema_version"], 2)
        self.assertEqual(saved["dataset"], DATASET)
        self.assertEqual(saved["request_id"], identifier)
        self.assertEqual(saved["scope"], "fvg")
        self.assertEqual(saved["run_date"], TEST_DATE)
        self.assertEqual(saved["request_plan_sha256"], self.plan_hash)
        self.assertEqual(saved["request_sha256"], self.desired["request_sha256"])
        self.client.get_jobs.assert_called_once_with(limit=20, sortby="-created")
        self.assertFalse(self.session.trust_env)
        self.assertTrue(self.session.closed)
        self.assertEqual(self.factory.call_args.kwargs["maximum_tries"], 1)
        self.assertFalse(self.factory.call_args.kwargs["cleanup"])
        self.assertEqual(self.factory.call_args.kwargs["timeout"], (15, 45))

    def test_reordered_variables_and_leads_still_match(self):
        reordered = copy.deepcopy(self.request)
        reordered["variable"].reverse()
        reordered["leadtime_hour"].reverse()
        self.add_job(1, request=reordered)
        self.assertEqual(self.run_reconcile()["result"], "unique_existing_job_restored")

    def test_mismatched_date_area_model_variables_leads_format_or_keys_never_match(self):
        alternatives = [dict(self.request, date=["2026-09-04"]),
                        dict(self.request, area=[46.1, 12.5, 45.8, 12.8]),
                        dict(self.request, model=["silam"]),
                        dict(self.request, variable=self.request["variable"][:-1]),
                        dict(self.request, leadtime_hour=["0", "1"]),
                        dict(self.request, data_format="netcdf_zip"),
                        dict(self.request, extra="not-identical")]
        for number, different in enumerate(alternatives, 1):
            self.add_job(number, request=different)
        self.assertEqual(self.run_reconcile()["result"], "no_matching_job_found")
        self.assert_no_handle()

    def test_same_payload_in_another_dataset_is_not_a_match(self):
        self.add_job(1, dataset="different-dataset")
        self.assertEqual(self.run_reconcile()["result"], "no_matching_job_found")
        self.assert_no_handle()

    def test_multiple_exact_matches_stop_without_a_handle(self):
        self.add_job(1, seconds=2)
        self.add_job(2, seconds=1)
        self.assertEqual(self.run_reconcile(), {"result": "multiple_matching_jobs_stop", "matches": 2, "checked": 2})
        self.assert_no_handle()

    def test_empty_page_has_no_match(self):
        self.assertEqual(self.run_reconcile(), {"result": "no_matching_job_found", "matches": 0, "checked": 0})
        self.assert_no_handle()

    def test_job_older_than_intent_minus_five_seconds_is_not_restored(self):
        self.add_job(1, seconds=-6)
        self.assertEqual(self.run_reconcile()["result"], "no_matching_job_found")
        self.assert_no_handle()

    def test_lower_boundary_is_inclusive(self):
        self.add_job(1, seconds=-5)
        self.assertEqual(self.run_reconcile()["result"], "unique_existing_job_restored")

    def test_upper_five_minute_boundary_is_inclusive(self):
        self.add_job(1, seconds=300)
        self.assertEqual(self.run_reconcile()["result"], "unique_existing_job_restored")

    def test_later_identical_job_cannot_be_attributed_to_original_submission(self):
        self.add_job(1, seconds=301)
        self.assertEqual(self.run_reconcile()["result"], "no_matching_job_found")
        self.assert_no_handle()

    def test_skip_too_late_job_but_find_original_recent_job(self):
        self.add_job(1, seconds=86400)
        original = self.add_job(2, seconds=1)
        self.assertEqual(self.run_reconcile()["result"], "unique_existing_job_restored")
        saved = json.loads((self.directory / "job.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["request_id"], original)

    def test_full_page_without_old_cutoff_cannot_establish_uniqueness(self):
        for number in range(1, 21):
            self.add_job(number, seconds=21-number, dataset=DATASET if number == 1 else "other")
        self.page.next = SimpleNamespace(request_ids=[job_id(21)])
        with self.assertRaises(subject.PilotError):
            self.run_reconcile()
        self.assert_no_handle()

    def test_full_page_with_older_cutoff_can_establish_uniqueness(self):
        original = self.add_job(1, seconds=1)
        for number in range(2, 21):
            self.add_job(number, seconds=-number-5, dataset="other")
        self.assertEqual(self.run_reconcile()["result"], "unique_existing_job_restored")
        saved = json.loads((self.directory / "job.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["request_id"], original)
        self.assertEqual(self.client.get_remote.call_count, 2)

    def test_non_descending_jobs_fail_instead_of_assuming_sorted_cutoff(self):
        self.add_job(1, seconds=1)
        self.add_job(2, seconds=2, dataset="other")
        with self.assertRaises(subject.PilotError):
            self.run_reconcile()
        self.assert_no_handle()

    def test_missing_request_metadata_is_inconclusive_even_after_matching_job(self):
        self.add_job(1, seconds=2)
        broken = self.add_job(2, seconds=1)
        self.remotes[broken]["metadata"] = {}
        with self.assertRaises(subject.PilotError):
            self.run_reconcile()
        self.assert_no_handle()

    def test_unrelated_dataset_without_request_metadata_is_ignored(self):
        unrelated = self.add_job(1, seconds=2, dataset="different-dataset")
        self.remotes[unrelated]["metadata"] = {}
        self.add_job(2, seconds=1)
        self.assertEqual(self.run_reconcile()["result"], "unique_existing_job_restored")

    def test_invalid_uuid_never_reaches_get_remote(self):
        self.page.request_ids = ["not-a-uuid/" + FAKE_TOKEN]
        with self.assertRaises((subject.PilotError, ValueError)):
            self.run_reconcile()
        self.client.get_remote.assert_not_called()
        self.assert_no_handle()

    def test_noncanonical_uppercase_uuid_is_rejected(self):
        self.page.request_ids = ["ABCDEFAB-1234-1234-1234-123456789ABC"]
        with self.assertRaises(subject.PilotError):
            self.run_reconcile()
        self.client.get_remote.assert_not_called()
        self.assert_no_handle()

    def test_existing_handle_preserved_without_reading_credentials(self):
        saved = {"dataset": DATASET, "request_id": job_id(88), "scope": "fvg"}
        retrieve_cams.write_new(self.directory / "job.json", saved)
        original = (self.directory / "job.json").read_bytes()
        with self.assertRaises(subject.PilotError):
            self.run_reconcile()
        self.assertEqual((self.directory / "job.json").read_bytes(), original)
        self.load.assert_not_called()
        self.factory.assert_not_called()

    def test_plan_or_intent_hash_mismatch_fails_before_credentials(self):
        copied = self.directory / "request-plan.json"
        copied.write_bytes(self.plan_bytes + b" ")
        with self.assertRaises(subject.PilotError):
            self.run_reconcile()
        self.load.assert_not_called()
        self.factory.assert_not_called()
        copied.write_bytes(self.plan_bytes)
        intent_path = self.directory / "submission-intent.json"
        intent = json.loads(intent_path.read_text(encoding="utf-8"))
        intent["request_plan_sha256"] = "0" * 64
        intent_path.write_text(json.dumps(intent), encoding="utf-8")
        with self.assertRaises(subject.PilotError):
            self.run_reconcile()
        self.load.assert_not_called()
        self.factory.assert_not_called()

    def test_exclusive_write_preserves_handle_created_during_reconciliation(self):
        self.add_job(1)
        concurrent = {"dataset": DATASET, "request_id": job_id(88), "scope": "fvg"}

        def race_write(path, value):
            retrieve_cams.write_new(path, concurrent)
            retrieve_cams.write_new(path, value)

        with patch.object(subject, "write_new", side_effect=race_write), self.assertRaises(FileExistsError):
            self.run_reconcile()
        self.assertEqual(json.loads((self.directory / "job.json").read_text(encoding="utf-8")), concurrent)

    def test_unexpected_credential_endpoint_rejected_before_client(self):
        self.load.return_value = ("https://not-ads.invalid/api", FAKE_TOKEN)
        with self.assertRaises(subject.PilotError):
            self.run_reconcile()
        self.factory.assert_not_called()
        self.assert_no_handle()

    def test_naive_intent_fails_before_credential_loading(self):
        intent_path = self.directory / "submission-intent.json"
        intent = json.loads(intent_path.read_text(encoding="utf-8"))
        intent["at_utc"] = "2026-09-04T12:00:00"
        intent_path.write_text(json.dumps(intent), encoding="utf-8")
        with self.assertRaises(subject.PilotError):
            self.run_reconcile()
        self.load.assert_not_called()
        self.factory.assert_not_called()
        self.assert_no_handle()

    def test_client_constructor_warnings_are_suppressed(self):
        self.add_job(1)

        def warn_then_client(**kwargs):
            warnings.warn(FAKE_TOKEN + FAKE_URL)
            return self.client

        self.factory.side_effect = warn_then_client
        with warnings.catch_warnings(record=True) as leaked:
            self.assertEqual(self.run_reconcile()["result"], "unique_existing_job_restored")
        self.assertEqual(leaked, [])

    def test_http_error_message_not_serialized_by_cli(self):
        response = requests.Response()
        response.status_code = 502
        self.factory.side_effect = requests.HTTPError(FAKE_TOKEN + FAKE_URL, response=response)
        argv = [str(Path(subject.__file__)), "--credentials-file", str(self.credentials),
                "--directory", str(self.directory), "--request-plan", str(self.plan_path),
                "--scope", "fvg"]
        with patch.object(retrieve_cams, "load_credentials", return_value=(retrieve_cams.ADS_URL, FAKE_TOKEN)), \
                patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()) as stdout, \
                contextlib.redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit) as exit_status:
            runpy.run_path(str(Path(subject.__file__)), run_name="__main__")
        self.assertEqual(exit_status.exception.code, 1)
        self.assertEqual(json.loads(stdout.getvalue()), {"result": "inconclusive", "error_type": "HTTPError", "http_status": 502})
        self.assertNotIn(FAKE_TOKEN, stdout.getvalue() + stderr.getvalue())
        self.assertNotIn(FAKE_URL, stdout.getvalue() + stderr.getvalue())
        self.assert_no_handle()

    def test_cli_is_successful_only_for_unique_restoration(self):
        argv = ["--credentials-file", str(self.credentials), "--directory", str(self.directory),
                "--request-plan", str(self.plan_path), "--scope", "fvg"]
        for result, expected_code in (
            ({"result": "unique_existing_job_restored", "job_status": "running", "checked": 1}, 0),
            ({"result": "no_matching_job_found", "matches": 0, "checked": 0}, 1),
            ({"result": "multiple_matching_jobs_stop", "matches": 2, "checked": 2}, 1),
        ):
            with self.subTest(result=result["result"]), patch.object(
                subject, "reconcile", return_value=result
            ), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(subject.main(argv), expected_code)


class ReadOnlyTransportTests(unittest.TestCase):
    def test_client_cannot_issue_mutating_method_during_reconciliation(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method), tempfile.TemporaryDirectory(prefix="cams-read-only-gate-") as tmp:
                root = Path(tmp)
                directory = root / f"artifacts-{TEST_DATE}"
                directory.mkdir()
                plan_path, plan, plan_bytes, plan_hash = write_valid_plan(
                    root, area=retrieve_cams.DEFAULT_AREA
                )
                (directory / "request-plan.json").write_bytes(plan_bytes)
                _, scope_metadata = retrieve_cams.study_scope("fvg")
                desired = retrieve_cams._request_record(
                    plan, plan_hash, "fvg", scope_metadata
                )
                retrieve_cams.write_new(directory / "request.json", desired)
                retrieve_cams.write_new(
                    directory / "submission-intent.json",
                    {"schema_version": 2, "at_utc": created_at(0), "dataset": DATASET,
                     "scope": "fvg", "run_date": TEST_DATE,
                     "request_plan_sha256": plan_hash,
                     "request_sha256": desired["request_sha256"], "post_retries": 0},
                )

                def unexpected_mutation(**kwargs):
                    kwargs["session"].request(method, retrieve_cams.ADS_URL + "/retrieve/v1/jobs/test")
                    raise AssertionError("Mutating method was not rejected by guard")

                with patch.object(subject, "load_credentials", return_value=(retrieve_cams.ADS_URL, FAKE_TOKEN)), \
                        patch("ecmwf.datastores.Client", side_effect=unexpected_mutation), \
                        patch.object(requests.Session, "request", return_value=Mock(status_code=200)) as transport, \
                        self.assertRaises(subject.PilotError):
                    subject.reconcile(
                        directory / "never-read.txt", directory,
                        request_plan_path=plan_path, scope="fvg"
                    )
                transport.assert_not_called()
                self.assertFalse((directory / "job.json").exists())


class CompleteReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.request = {"variable": ["uv"], "date": "2026-09-04", "area": [47, 12, 45, 14]}
        self.remotes = {}
        self.client = Mock()
        self.client.get_remote.side_effect = lambda identifier: SimpleNamespace(json=self.remotes[identifier])
        self.network = patch.object(requests.Session, "request", side_effect=AssertionError("Network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def add_job(self, number, seconds, *, dataset=DATASET, request=None):
        identifier = job_id(number)
        self.remotes[identifier] = {"jobID": identifier, "processID": dataset,
                                   "created": created_at(seconds), "status": "running",
                                   "metadata": {"request": {"ids": copy.deepcopy(
                                       self.request if request is None else request)}},
                                   "provider_log": FAKE_TOKEN, "location": FAKE_URL}
        return identifier

    def page(self, identifiers=(), *, next_page=None, link=None):
        return SimpleNamespace(
            request_ids=list(identifiers), next=next_page,
            json={"jobs": [{"jobID": identifier} for identifier in identifiers],
                  "links": [] if link is None else [{"rel": "next", "href": link}]})

    def run_complete(self, first, **kwargs):
        self.client.get_jobs.return_value = first
        result = subject.find_existing_job_complete(
            self.client, dataset=DATASET, request=self.request, intended_at=INTENT,
            observed_at=INTENT + timedelta(seconds=1000), **kwargs)
        self.client.submit.assert_not_called()
        self.client.delete.assert_not_called()
        self.assertNotIn(FAKE_TOKEN, json.dumps(result))
        self.assertNotIn(FAKE_URL, json.dumps(result))
        return result

    def test_empty_explicit_page_proves_zero_matches_with_safe_bound_evidence(self):
        matches, evidence = self.run_complete(self.page())
        self.assertEqual(matches, [])
        self.assertEqual(evidence["coverage_reason"], "end_of_results")
        self.assertTrue(evidence["complete"])
        self.assertEqual(evidence["since_utc"], created_at(-5))
        self.assertEqual(evidence["until_utc"], created_at(1000))
        self.assertEqual(evidence["page_count"], 1)
        self.assertEqual(evidence["checked_count"], 0)
        self.assertEqual(evidence["matched_ids"], [])
        self.assertEqual(evidence["match_count"], 0)
        self.assertEqual(evidence["dataset"], DATASET)
        self.assertRegex(evidence["request_sha256"], r"^[a-f0-9]{64}$")
        self.assertTrue(evidence["completed_at_utc"].endswith("Z"))

    def test_delayed_original_and_both_interval_boundaries_match(self):
        ids = [self.add_job(1, 1000), self.add_job(2, 900), self.add_job(3, -5)]
        matches, evidence = self.run_complete(self.page(ids))
        self.assertEqual([identifier for identifier, _ in matches], ids)
        self.assertEqual(evidence["matched_ids"], ids)
        self.assertEqual(evidence["match_count"], 3)
        self.assertEqual(evidence["checked_count"], 3)
        self.assertEqual(set(evidence["checked_jobs"][0]), {"id", "created", "status", "dataset"})

    def test_all_pages_until_exhaustion_are_searched(self):
        first_ids = [self.add_job(number, 900-number, dataset="another-dataset") for number in range(1, 21)]
        matched = self.add_job(21, 20)
        second = self.page([matched])
        first = self.page(first_ids, next_page=second, link=retrieve_cams.ADS_URL + "/retrieve/v1/jobs?cursor=2")
        matches, evidence = self.run_complete(first)
        self.assertEqual(matches[0][0], matched)
        self.assertEqual(evidence["page_count"], 2)
        self.assertEqual(evidence["checked_count"], 21)

    def test_short_page_next_link_is_followed_and_old_cutoff_stops_next_fetch(self):
        current, older = self.add_job(1, 20), self.add_job(2, -6)
        second = self.page([older], next_page=object(), link=retrieve_cams.ADS_URL + "/retrieve/v1/jobs?cursor=3")
        first = self.page([current], next_page=second, link=retrieve_cams.ADS_URL + "/retrieve/v1/jobs?cursor=2")
        matches, evidence = self.run_complete(first)
        self.assertEqual(matches[0][0], current)
        self.assertEqual(evidence["coverage_reason"], "crossed_lower_cutoff")
        self.assertEqual(evidence["page_count"], 2)

    def test_after_observation_unrelated_job_is_excluded_but_checked(self):
        future = self.add_job(1, 1001, dataset="another-dataset")
        matches, evidence = self.run_complete(self.page([future]))
        self.assertEqual(matches, [])
        self.assertEqual(evidence["checked_count"], 1)

    def test_same_payload_after_observation_is_inconclusive_known_new_evidence(self):
        future = self.add_job(1, 1001)
        with self.assertRaises(subject.ReconciliationInconclusive):
            self.run_complete(self.page([future]))

    def test_malformed_or_missing_explicit_pagination_is_inconclusive(self):
        bad_pages = [SimpleNamespace(request_ids=[], next=None),
                     SimpleNamespace(request_ids=[], json={"jobs": []}),
                     SimpleNamespace(request_ids=[], json={"jobs": [], "links": None}),
                     SimpleNamespace(request_ids=[], json={"jobs": [], "links": [{"rel": "next"}]})]
        for page in bad_pages:
            with self.subTest(page=page), self.assertRaises(subject.ReconciliationInconclusive):
                self.run_complete(page)

    def test_full_page_without_next_and_empty_page_with_next_are_inconclusive(self):
        ids = [self.add_job(number, 100-number, dataset="another-dataset") for number in range(1, 21)]
        for page in [self.page(ids), self.page(link=retrieve_cams.ADS_URL + "/retrieve/v1/jobs?cursor=2")]:
            with self.subTest(page=page), self.assertRaises(subject.ReconciliationInconclusive):
                self.run_complete(page)

    def test_external_duplicate_or_disappearing_next_link_is_inconclusive(self):
        identifier = self.add_job(1, 20)
        external = self.page([identifier], link="https://untrusted.invalid/api/jobs")
        duplicate = self.page([identifier], link=retrieve_cams.ADS_URL + "/retrieve/v1/jobs?cursor=2")
        duplicate.json["links"].append(dict(duplicate.json["links"][0]))
        missing = self.page([identifier], link=retrieve_cams.ADS_URL + "/retrieve/v1/jobs?cursor=2")
        for page in (external, duplicate, missing):
            with self.subTest(page=page), self.assertRaises(subject.ReconciliationInconclusive):
                self.run_complete(page)

    def test_duplicate_identifiers_within_or_across_pages_are_inconclusive(self):
        identifier = self.add_job(1, 20)
        duplicated = self.page([identifier, identifier])
        across = self.page([identifier], next_page=self.page([identifier]),
                           link=retrieve_cams.ADS_URL + "/retrieve/v1/jobs?cursor=2")
        for page in (duplicated, across):
            with self.subTest(page=page), self.assertRaises(subject.ReconciliationInconclusive):
                self.run_complete(page)

    def test_repeated_pagination_link_is_inconclusive(self):
        one, two = self.add_job(1, 20), self.add_job(2, 10)
        link = retrieve_cams.ADS_URL + "/retrieve/v1/jobs?cursor=2"
        second = self.page([two], link=link, next_page=self.page())
        with self.assertRaises(subject.ReconciliationInconclusive):
            self.run_complete(self.page([one], link=link, next_page=second))

    def test_remote_identity_dataset_creation_or_request_missing_is_inconclusive(self):
        identifier = self.add_job(1, 20)
        valid = copy.deepcopy(self.remotes[identifier])
        for key, value in (("jobID", job_id(2)), ("processID", None), ("processID", FAKE_TOKEN + "?"),
                           ("created", None), ("metadata", {}), ("status", "unknown")):
            self.remotes[identifier] = {**valid, key: value}
            with self.subTest(key=key, value=value), self.assertRaises(subject.ReconciliationInconclusive):
                self.run_complete(self.page([identifier]))

    def test_ordering_must_continue_across_pages(self):
        one, two = self.add_job(1, 20), self.add_job(2, 30)
        with self.assertRaises(subject.ReconciliationInconclusive):
            self.run_complete(self.page([one], next_page=self.page([two]),
                                       link=retrieve_cams.ADS_URL + "/retrieve/v1/jobs?cursor=2"))

    def test_http_or_timeout_during_metadata_never_returns_evidence(self):
        identifier = self.add_job(1, 20)
        for error in (requests.ReadTimeout(FAKE_TOKEN), requests.HTTPError(FAKE_TOKEN)):
            self.client.get_remote.side_effect = error
            with self.subTest(error=error), self.assertRaises(type(error)):
                self.run_complete(self.page([identifier]))

    def test_next_page_http_or_timeout_discards_partial_match_evidence(self):
        identifier = self.add_job(1, 20)
        first = self.page([identifier], link=retrieve_cams.ADS_URL + "/retrieve/v1/jobs?cursor=2")
        for error in (requests.ReadTimeout(FAKE_TOKEN), requests.HTTPError(FAKE_TOKEN)):
            class BrokenContinuation(SimpleNamespace):
                @property
                def next(self):
                    raise error
            broken = BrokenContinuation(json=first.json, request_ids=first.request_ids)
            with self.subTest(error=error), self.assertRaises(type(error)):
                self.run_complete(broken)

    def test_page_job_and_elapsed_budgets_fail_closed(self):
        one, two = self.add_job(1, 20), self.add_job(2, 10)
        first = self.page([one], next_page=self.page([two]),
                          link=retrieve_cams.ADS_URL + "/retrieve/v1/jobs?cursor=2")
        for constant in ("MAX_COMPLETE_PAGES", "MAX_COMPLETE_JOBS"):
            with self.subTest(constant=constant), patch.object(subject, constant, 1), \
                    self.assertRaises(subject.ReconciliationInconclusive):
                self.run_complete(first)
        with patch.object(subject, "monotonic", side_effect=[0, 46]), \
                self.assertRaises(subject.ReconciliationInconclusive):
            self.run_complete(self.page())

    def test_invalid_interval_and_client_version_fail_before_get(self):
        for intended, observed in ((INTENT.replace(tzinfo=None), INTENT),
                                   (INTENT, INTENT.replace(tzinfo=None)),
                                   (INTENT, INTENT-timedelta(seconds=1))):
            with self.subTest(intended=intended, observed=observed), \
                    self.assertRaises(subject.ReconciliationInconclusive):
                subject.find_existing_job_complete(self.client, dataset=DATASET, request=self.request,
                                                   intended_at=intended, observed_at=observed)
        with patch.object(subject.importlib.metadata, "version", return_value="0.6.0"), \
                self.assertRaises(subject.ReconciliationInconclusive):
            self.run_complete(self.page())
        self.client.get_jobs.assert_not_called()


    def test_pinned_client_follows_next_using_only_guarded_get_transport(self):
        from ecmwf.datastores import Client
        first_id, second_id = self.add_job(1, 20), self.add_job(2, 10)
        jobs_url = retrieve_cams.ADS_URL + "/retrieve/v1/jobs"
        next_url = jobs_url + "?cursor=2"
        for identifier in (first_id, second_id):
            self.remotes[identifier]["links"] = [{"rel": "self", "href": jobs_url + "/" + identifier}]
        responses = {
            retrieve_cams.ADS_URL + "/catalogue/v1/messages": {"messages": []},
            jobs_url: self.page([first_id], link=next_url).json,
            next_url: self.page([second_id]).json,
            jobs_url + "/" + first_id: self.remotes[first_id],
            jobs_url + "/" + second_id: self.remotes[second_id],
        }
        calls = []

        def transport(method, url, **kwargs):
            self.assertEqual(method.lower(), "get")
            self.assertFalse(kwargs["allow_redirects"])
            calls.append(url)
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps(responses[url]).encode()
            response.url = url
            response.request = requests.Request("GET", url).prepare()
            return response

        with patch.object(requests.Session, "request", side_effect=transport), \
                subject.ReadOnlyAdsSession() as session, warnings.catch_warnings(record=True):
            session.trust_env = False
            client = Client(url=retrieve_cams.ADS_URL, key=FAKE_TOKEN, session=session,
                            maximum_tries=1, retry_after=0, timeout=(1, 1), cleanup=False,
                            progress=False, log_callback=lambda *args, **kwargs: None)
            calls.clear()  # The client constructor also reads catalogue messages.
            matches, evidence = subject.find_existing_job_complete(
                client, dataset=DATASET, request=self.request, intended_at=INTENT,
                observed_at=INTENT+timedelta(seconds=1000))
        self.assertEqual([identifier for identifier, _ in matches], [first_id, second_id])
        self.assertEqual(evidence["page_count"], 2)
        self.assertEqual(calls, [jobs_url, jobs_url + "/" + first_id, jobs_url + "/" + first_id,
                                 next_url, jobs_url + "/" + second_id, jobs_url + "/" + second_id])


if __name__ == "__main__":
    unittest.main()
