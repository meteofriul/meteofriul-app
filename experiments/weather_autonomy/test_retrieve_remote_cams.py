import base64
from contextlib import redirect_stdout
import hashlib
from io import StringIO
import itertools
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch, Mock
import retrieve_cams as cams
from retrieve_remote_cams import retrieve_remote_cams, FILES
from retrieve_cams import PilotError
from local_pipeline.gcs_object_store import GCSObjectStore
from local_pipeline.operational_diagnostics import error_fields
from local_pipeline.sqlite_object_store import SQLiteObjectStore, ObjectNotFound
from cams_request_plan import request_sha256
from cams_test_fixtures import TEST_DATE, write_valid_plan


class RemoteCamsTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = SQLiteObjectStore(self.root / "objects.sqlite")
        self.request = {"date": "2026-09-06"}
        self.plan = {"run_date": "2026-09-06", "request_groups": [{"request": self.request}]}
        mocked = patch("retrieve_remote_cams._preflight_plan", return_value=(self.plan, b"plan", "hash", {}))
        mocked.start()
        self.addCleanup(mocked.stop)
        self.prefix = "state/ads/2026-09-06/" + request_sha256(self.request) + "/"

    def run_acquisition(self, fn):
        return retrieve_remote_cams(credentials_path="unused", request_plan_path="unused",
                                    scratch=self.root, state_store=self.store, retrieve_fn=fn)

    def test_intent_without_job_refuses_second_submission(self):
        self.store.put(self.prefix + "intent.json", b"{}")
        fn = Mock()
        with self.assertRaises(PilotError):
            self.run_acquisition(fn)
        fn.assert_not_called()

    def test_saved_job_uses_resume(self):
        files = {name: base64.b64encode(b"plan" if name == "request-plan.json" else b"{}").decode()
                 for name in FILES + ("job.json",)}
        self.store.put(self.prefix + "submitted.json", json.dumps(files).encode())
        fn = Mock(return_value="resumed")
        self.assertEqual(self.run_acquisition(fn), "resumed")
        self.assertIn("resume", fn.call_args.kwargs)
        self.assertNotIn("artifacts_directory", fn.call_args.kwargs)

    def test_new_submission_exports_only_allowlisted_files(self):
        def fake(_credentials, **kwargs):
            directory = kwargs["artifacts_directory"]
            directory.mkdir()
            for name in FILES:
                (directory / name).write_bytes(b"plan" if name == "request-plan.json" else b"{}")
            (directory / "private-key.txt").write_text("secret")
            kwargs["checkpoint_saver"]("intent", directory)
            return "queued"
        self.assertEqual(self.run_acquisition(fake), "queued")
        raw = self.store.get(self.prefix + "intent.json").body
        self.assertEqual(set(json.loads(raw)), set(FILES))
        self.assertNotIn(b"secret", raw)

    def test_unique_existing_job_is_checkpointed_then_resumed_without_submission(self):
        files = {name: base64.b64encode(b"plan" if name == "request-plan.json" else b"{}").decode()
                 for name in FILES}
        self.store.put(self.prefix + "intent.json", json.dumps(files).encode())
        def reconcile(_credentials, directory, **kwargs):
            self.assertEqual(kwargs["scope"], "fvg")
            (directory / "job.json").write_bytes(b"{}")
            return {"result": "unique_existing_job_restored"}
        fn = Mock(return_value="resumed")
        with patch("retrieve_remote_cams.remote_cams_context"):
            result = retrieve_remote_cams(credentials_path="unused", request_plan_path="unused",
                scratch=self.root, state_store=self.store, retrieve_fn=fn, reconcile_fn=reconcile)
        self.assertEqual(result, "resumed")
        self.assertIn("resume", fn.call_args.kwargs)
        self.assertNotIn("artifacts_directory", fn.call_args.kwargs)
        self.assertEqual(set(json.loads(self.store.get(self.prefix + "submitted.json").body)),
                         set(FILES + ("job.json",)))

    def test_nonunique_reconciliation_never_invokes_acquisition(self):
        for outcome in ("no_matching_job_found", "multiple_matching_jobs_stop"):
            with self.subTest(outcome=outcome), TemporaryDirectory() as directory:
                root = Path(directory)
                store = SQLiteObjectStore(root / "objects.sqlite")
                files = {name: base64.b64encode(b"plan" if name == "request-plan.json" else b"{}").decode()
                         for name in FILES}
                store.put(self.prefix + "intent.json", json.dumps(files).encode())
                fn = Mock()
                result = retrieve_remote_cams(credentials_path="unused", request_plan_path="unused",
                    scratch=root, state_store=store, retrieve_fn=fn,
                    reconcile_fn=Mock(return_value={"result": outcome}))
                self.assertEqual(result["status"], "submission_reconciliation_pending")
                fn.assert_not_called()

    def test_invalid_reconciliation_preflight_propagates_without_new_submission(self):
        files = {name: base64.b64encode(b"plan" if name == "request-plan.json" else b"{}").decode()
                 for name in FILES}
        self.store.put(self.prefix + "intent.json", json.dumps(files).encode())
        fn = Mock()
        with self.assertRaises(PilotError):
            retrieve_remote_cams(credentials_path="unused", request_plan_path="unused",
                scratch=self.root, state_store=self.store, retrieve_fn=fn,
                reconcile_fn=Mock(side_effect=PilotError("invalid saved plan")))
        fn.assert_not_called()

    def test_inconclusive_remote_reconciliation_is_pending_without_new_submission(self):
        from reconcile_cams_job import ReconciliationInconclusive
        files = {name: base64.b64encode(b"plan" if name == "request-plan.json" else b"{}").decode()
                 for name in FILES}
        self.store.put(self.prefix + "intent.json", json.dumps(files).encode())
        fn = Mock()
        result = retrieve_remote_cams(credentials_path="unused", request_plan_path="unused",
            scratch=self.root, state_store=self.store, retrieve_fn=fn,
            reconcile_fn=Mock(side_effect=ReconciliationInconclusive("Recent job page is full")))
        self.assertEqual(result["status"], "submission_reconciliation_pending")
        self.assertEqual(result["reason_code"], "reconciliation_inconclusive")
        fn.assert_not_called()


class Metadata404Store(SQLiteObjectStore):
    """Persist locally, but produce the real GCS adapter's missing-object error."""

    def __init__(self, path):
        super().__init__(path)
        self.missing = []

    def get(self, key):
        try:
            return super().get(key)
        except ObjectNotFound:
            pass
        error = Exception("synthetic absent checkpoint")
        error.code = 404
        try:
            return GCSObjectStore._call(Mock(side_effect=error),
                _operation="metadata_read", _key=key)
        except ObjectNotFound as missing:
            self.missing.append(error_fields(missing))
            raise


class RemoteCamsExceptionContextTests(TestCase):
    """Exercise the real retriever and classification with fake external services."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Metadata404Store(self.root / "objects.sqlite")
        self.plan_path, self.plan, _, _ = write_valid_plan(self.root, area=cams.DEFAULT_AREA)
        self.prefix = f"state/ads/{TEST_DATE}/" + request_sha256(self.plan["request_groups"][0]["request"]) + "/"
        self.client = Mock()
        self.remote = Mock()
        self.remote.request_id = "12345678-1234-1234-1234-123456789abc"
        self.remote.json = {"status": "queued"}
        self.client.submit.return_value = self.remote
        self.client.get_remote.return_value = self.remote
        self.download = Mock()

    def acquire(self, name):
        scratch = self.root / name
        scratch.mkdir()
        with patch.object(cams, "load_credentials", return_value=(cams.ADS_URL, "synthetic-secret")), \
                patch.object(cams.importlib.metadata, "version", return_value="0.5.3"), \
                patch("ecmwf.datastores.Client", return_value=self.client), \
                patch.object(cams.time, "perf_counter", side_effect=itertools.count(0, 2)), \
                patch.object(cams.time, "sleep"), \
                patch.object(cams, "download_result", self.download), \
                redirect_stdout(StringIO()):
            return retrieve_remote_cams(credentials_path="unused", request_plan_path=self.plan_path,
                scratch=scratch, state_store=self.store, max_wait=1)

    def test_expected_missing_checkpoints_do_not_poison_wait_or_resubmit_saved_job(self):
        from cloud_worker import _cams_acquisition_outcome

        first = self.acquire("first")
        self.assertEqual([row["object_key"] for row in self.store.missing],
                         [self.prefix + "submitted.json", self.prefix + "intent.json"])
        self.assertTrue(all(row["http_status"] == 404 and row["retryable"] is False
                            and row["operation"] == "metadata_read" for row in self.store.missing))
        self.assertIn("wait budget", first["safe_reason"])
        self.assertNotIn("retryable", first)
        self.assertEqual(_cams_acquisition_outcome(first, "20260904T000000Z")["status"], "remote_pending")
        submitted = self.store.get(self.prefix + "submitted.json").body
        saved_job = json.loads(base64.b64decode(json.loads(submitted)["job.json"]))
        self.assertEqual(saved_job["request_id"], self.remote.request_id)

        resumed = self.acquire("second")
        self.assertTrue(resumed["resumed_existing_job"])
        self.assertNotIn("retryable", resumed)
        self.assertEqual(_cams_acquisition_outcome(resumed, "20260904T000000Z")["status"], "remote_pending")
        self.assertEqual(self.store.get(self.prefix + "submitted.json").body, submitted)
        self.client.submit.assert_called_once()
        self.client.get_remote.assert_called_once_with(self.remote.request_id)
        self.download.assert_not_called()
        self.remote.delete.assert_not_called()

    def test_reconciliation_failure_does_not_inherit_missing_submitted_checkpoint(self):
        # First obtain a valid durable intent/job pair, then expose only the
        # intent to represent a lost response after the original submission.
        self.acquire("first")
        intent = self.store.get(self.prefix + "intent.json")
        restored_store = Metadata404Store(self.root / "reconcile.sqlite")
        restored_store.put(self.prefix + "intent.json", intent.body)
        scratch = self.root / "reconciliation"
        scratch.mkdir()
        retrieve_fn = Mock()

        def reconcile(*args, **kwargs):
            raise PilotError("invalid saved request binding")

        with self.assertRaises(PilotError) as caught:
            retrieve_remote_cams(credentials_path="unused", request_plan_path=self.plan_path,
                scratch=scratch, state_store=restored_store,
                retrieve_fn=retrieve_fn, reconcile_fn=reconcile)
        fields = error_fields(caught.exception)
        self.assertNotIn("retryable", fields)
        self.assertNotIn("http_status", fields)
        self.assertNotIn("object_key", fields)
        retrieve_fn.assert_not_called()

    def test_actual_certificate_failure_remains_terminal_after_missing_checkpoints(self):
        import ssl
        import requests
        from cloud_worker import _cams_acquisition_outcome

        self.client.submit.side_effect = requests.exceptions.SSLError(
            ssl.SSLCertVerificationError(1, "synthetic certificate failure"))
        report = self.acquire("certificate-failure")
        self.assertEqual(report["transport_reason"], "tls_certificate_invalid")
        self.assertFalse(report["retryable"])
        self.assertEqual(_cams_acquisition_outcome(report, "20260904T000000Z")["status"], "manual_review")
        self.client.submit.assert_called_once()
        self.client.get_remote.assert_not_called()
        self.download.assert_not_called()

    def test_actual_checkpoint_integrity_failure_stops_before_any_submission(self):
        bucket = Mock()
        bucket.name = "meteofriul-pilot-weather"
        blob = bucket.blob.return_value
        blob.size = 2
        blob.generation = 17
        blob.content_type = "application/json"
        blob.metadata = {"mf-sha256": hashlib.sha256(b"{}").hexdigest()}
        blob.download_as_bytes.return_value = b"[]"
        store = GCSObjectStore(bucket)
        fn = Mock()
        from local_pipeline.sqlite_object_store import ObjectStoreError

        with self.assertRaises(ObjectStoreError) as caught:
            retrieve_remote_cams(credentials_path="unused", request_plan_path=self.plan_path,
                scratch=self.root, state_store=store, retrieve_fn=fn)
        self.assertEqual(error_fields(caught.exception)["operation"], "verify_integrity")
        fn.assert_not_called()
        self.client.submit.assert_not_called()


if __name__ == "__main__":
    main()
