"""Mock-only live evidence checks; never contacts Cloud or writes objects."""
from datetime import datetime, timezone
from contextlib import redirect_stdout
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
import base64
import hashlib
import json
import io
from unittest import TestCase, main
from unittest.mock import Mock, patch

from icon_operator_cli import LiveCloudEvidence, _inventory_bytes, main as cli_main
from local_pipeline.contract_v1 import canonical_json_bytes
from local_pipeline.icon_recovery import Recovery, result
from local_pipeline.sqlite_object_store import SQLiteObjectStore


NOW = datetime(2026, 11, 25, 16, 40, tzinfo=timezone.utc)
PROJECT = "meteofriul-pilot-20260906"
REGION = "europe-west1"
JOB = "pilot-national-icon"
OPERATOR_JOB = "pilot-national-icon-operator"
SCHEDULER = "pilot-national-icon-refresh"
IMAGE = "europe-west1-docker.pkg.dev/" + PROJECT + "/weather/national@sha256:" + "a" * 64
COMMIT = "b" * 40
SERVICE_ACCOUNT = "pilot-national-operator@" + PROJECT + ".iam.gserviceaccount.com"
ROOT = f"projects/{PROJECT}/locations/{REGION}/jobs/"


class Response:
    def __init__(self, data): self.data = data
    def raise_for_status(self): pass
    def json(self): return self.data


class OperatorCliTests(TestCase):
    def setUp(self):
        self.scheduler = {"name": f"projects/{PROJECT}/locations/{REGION}/jobs/{SCHEDULER}",
            "state": "PAUSED", "httpTarget": {"uri": f"https://run.googleapis.com/v2/{ROOT}{JOB}:run"}}
        self.job = {"name": ROOT + JOB, "template": {"template": {"containers": [{"image": IMAGE,
            "env": [{"name": "WEATHER_ICON_AUTOMATIC_RECOVERY_ENABLED", "value": "true"},
                    {"name": "WEATHER_SOURCE_COMMIT", "value": COMMIT}]}]}}}
        self.operator = {"name": ROOT + OPERATOR_JOB, "template": {"taskCount": 1,
            "parallelism": 1, "template": {"containers": [{"image": IMAGE,
                "command": ["python", "icon_operator_cli.py"],
                "resources": {"limits": {"memory": "2Gi"}}, "env": [
                    {"name": "WEATHER_NATIONAL_ACQUISITION", "value": "approved"},
                    {"name": "WEATHER_SOURCE_COMMIT", "value": COMMIT}]}],
                "timeout": "1800s", "maxRetries": 0, "serviceAccount": SERVICE_ACCOUNT}}}
        self.inventory = {"schema_version": 1, "project": PROJECT, "region": REGION,
            "state_bucket": PROJECT + "-state", "data_bucket": PROJECT + "-data",
            "object_prefix": "pilot", "scheduled_job": JOB, "operator_job": OPERATOR_JOB,
            "approved_image": IMAGE, "approved_source_commit": COMMIT,
            "other_writers_blocked": True, "observed_at_utc": NOW.strftime("%Y-%m-%dT%H:%M:%SZ")}
        self.routes = {
            "https://cloudscheduler.googleapis.com/v1/" + self.scheduler["name"]: self.scheduler,
            "https://run.googleapis.com/v2/" + ROOT + JOB: self.job,
            "https://run.googleapis.com/v2/" + ROOT + OPERATOR_JOB: self.operator,
            "https://run.googleapis.com/v2/" + ROOT + JOB + "/executions?pageSize=100": {
                "executions": [{"name": ROOT + JOB + "/executions/old", "completionTime": "2026-11-24T12:00:00Z"}]},
            "https://run.googleapis.com/v2/" + ROOT + OPERATOR_JOB + "/executions?pageSize=100": {
                "executions": [{"name": ROOT + OPERATOR_JOB + "/executions/" + OPERATOR_JOB + "-one"}]},
        }
        self.session = Mock()
        self.session.get.side_effect = lambda url, timeout: Response(self.routes[url])

    def evidence(self, execution=None):
        return LiveCloudEvidence(self.session, project=PROJECT, region=REGION, job=JOB,
            scheduler=SCHEDULER, operator_job=OPERATOR_JOB, image=IMAGE,
            source_commit=COMMIT, state_bucket=PROJECT + "-state",
            data_bucket=PROJECT + "-data", object_prefix="pilot",
            writer_inventory=self.inventory, operator_service_account=SERVICE_ACCOUNT,
            execution=execution, clock=lambda: NOW)

    def test_read_only_inspection_and_isolated_operator_gate(self):
        self.assertTrue(self.evidence().guard()["legacy_invocations_blocked"])
        self.assertTrue(self.evidence(OPERATOR_JOB + "-one").guard()["deployed_fence_aware"])
        self.assertTrue(all(call.args[0].startswith("https://") for call in self.session.get.call_args_list))
        self.assertTrue(all(call.kwargs["timeout"] == 15 for call in self.session.get.call_args_list))

    def test_scheduler_image_executions_inventory_and_runtime_fail_closed(self):
        changes = [
            (self.scheduler, "state", "ENABLED"),
            (self.scheduler["httpTarget"], "uri", "https://example.invalid"),
            (self.job["template"]["template"]["containers"][0], "image", IMAGE[:-1] + "b"),
            (self.job["template"]["template"]["containers"][0]["env"][0], "value", "false"),
            (self.inventory, "other_writers_blocked", False),
            (self.operator["template"]["template"], "maxRetries", 1),
            (self.operator["template"]["template"]["containers"][0]["resources"]["limits"], "memory", "1Gi"),
        ]
        for target, key, replacement in changes:
            with self.subTest(key=key, replacement=replacement):
                original = target[key]
                target[key] = replacement
                try:
                    with self.assertRaises(ValueError):
                        self.evidence(OPERATOR_JOB + "-one").guard()
                finally:
                    target[key] = original
        url = "https://run.googleapis.com/v2/" + ROOT + JOB + "/executions?pageSize=100"
        self.routes[url]["executions"].append({"name": ROOT + JOB + "/executions/active"})
        with self.assertRaises(ValueError): self.evidence().guard()

    def test_workstation_execute_rejected_before_credentials_or_cloud_calls(self):
        args = ["--project", PROJECT, "--region", REGION, "--job", JOB,
            "--scheduler", SCHEDULER, "--operator-job", OPERATOR_JOB,
            "--state-bucket", PROJECT + "-state", "--data-bucket", PROJECT + "-data",
            "--object-prefix", "pilot", "--approved-image", IMAGE,
            "--approved-source-commit", COMMIT, "--writer-inventory", "missing.json",
            "--writer-inventory-sha256", "c" * 64, "--execute"]
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "isolated Cloud Run operator job"):
                cli_main(args)

    def test_fresh_inventory_can_be_passed_as_digest_bound_base64(self):
        data = json.dumps(self.inventory, sort_keys=True).encode()
        encoded = base64.urlsafe_b64encode(data).decode()
        args = SimpleNamespace(writer_inventory=None, writer_inventory_b64=encoded,
            writer_inventory_sha256=hashlib.sha256(data).hexdigest())
        self.assertEqual(_inventory_bytes(args), self.inventory)
        args.writer_inventory_sha256 = "0" * 64
        with self.assertRaises(ValueError): _inventory_bytes(args)

    def test_live_guard_shape_drives_full_recovery_protocol(self):
        with TemporaryDirectory() as folder:
            recovery = Recovery(SQLiteObjectStore(Path(folder) / "operator.sqlite"), "national")
            failed = "20261121T120000Z"
            published = "20261121T000000Z"
            new = "20261125T000000Z"
            old = recovery.transition(recovery.begin(None, failed, "20261121-pm", "national-old"),
                                      "manual_review")
            prepared = {}
            current = [published]
            acquire = Mock(side_effect=lambda cycle, slot: prepared.setdefault((cycle, slot), {"cycle": cycle}))
            def publish(bundle):
                current[0] = bundle["cycle"]
                return result("published", "publication_committed", bundle["cycle"])
            outcome = recovery.supersede_manual_review(now=NOW,
                incident_id="a" * 32, expected_etag=old.etag,
                expected_owner_sha256=hashlib.sha256(canonical_json_bytes(old.record)).hexdigest(),
                failed_run=failed, new_run=new, published_run=published,
                execution=OPERATOR_JOB + "-one",
                quiescent=self.evidence(OPERATOR_JOB + "-one").guard,
                guard_clock=lambda: NOW,
                current_run=lambda: current[0], discover=lambda _: "2026112500",
                failed_cycle_evidence=lambda _: {"intent": True, "mapping": False,
                    "prepared": False, "manifest": False},
                checkpoint=lambda cycle, slot: prepared.get((cycle, slot)),
                acquire=acquire, publish=publish, verify=lambda _: True)
            self.assertEqual(outcome["status"], "published")
            self.assertEqual(acquire.call_count, 1)
            self.assertEqual(recovery.active().record["phase"], "completed")

    def test_inspect_reports_fence_when_live_scheduler_is_enabled(self):
        self.scheduler["state"] = "ENABLED"
        args = ["--project", PROJECT, "--region", REGION, "--job", JOB,
            "--scheduler", SCHEDULER, "--operator-job", OPERATOR_JOB,
            "--state-bucket", PROJECT + "-state", "--data-bucket", PROJECT + "-data",
            "--object-prefix", "pilot", "--approved-image", IMAGE,
            "--approved-source-commit", COMMIT]
        output = io.StringIO()
        active = SimpleNamespace(record={"phase": "manual_review", "source_run_id": "20261121T120000Z"},
                                 etag="7")
        with patch("google.auth.default", return_value=(object(), PROJECT)), \
             patch("google.auth.transport.requests.AuthorizedSession", return_value=self.session), \
             patch("google.cloud.storage.Client"), \
             patch("local_pipeline.gcs_object_store.GCSObjectStore", return_value=object()), \
             patch("national_cloud_assets.load_inputs", return_value=({}, {})), \
             patch("local_pipeline.icon_recovery.Recovery") as controller, \
             patch("national_cloud_publication.read_pointer", return_value=({"source_run_id": "20261121T000000Z"}, "8")), \
             redirect_stdout(output):
            controller.return_value.active.return_value = active
            self.assertEqual(cli_main(args), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["operator_guard"], "blocked")
        self.assertEqual(report["active_phase"], "manual_review")
        self.assertEqual(report["active_run"], "20261121T120000Z")
        self.assertEqual(report["published_run"], "20261121T000000Z")
        self.assertEqual(self.session.get.call_count, 1)


if __name__ == "__main__": main()
