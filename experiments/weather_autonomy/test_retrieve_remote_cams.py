import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch, Mock
from retrieve_remote_cams import retrieve_remote_cams, FILES
from retrieve_cams import PilotError
from local_pipeline.sqlite_object_store import SQLiteObjectStore
from cams_request_plan import request_sha256


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


if __name__ == "__main__":
    main()
