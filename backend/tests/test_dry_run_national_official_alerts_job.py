import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from app.jobs import dry_run_national_official_alerts as job
from app.repositories.push import PushDeviceReadResult
from app.services.national_alert_push_dry_run import NationalAlertDryRunPolicy


def config(mode="dry_run"):
    return SimpleNamespace(
        mode=mode,
        enrollment_mode="play_beta",
        enrollment_generation="play-beta-v1",
        android_app_ids=frozenset({"1:49007668366:android:725bf6f8b339177a852ddf"}),
        min_app_version_code=300029,
        max_devices=100,
    )


class NationalOfficialAlertsDryRunJobTests(unittest.TestCase):
    def test_send_mode_stops_before_any_database_read(self):
        output = io.StringIO()
        with (
            patch.object(job.PushPilotConfig, "from_environment", return_value=config("send")),
            patch.object(job, "get_firestore_client") as firestore,
            redirect_stdout(output),
        ):
            self.assertEqual(job.main(), 1)
        firestore.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), {
            "status": "failed",
            "reason": "dry_run_mode_required",
            "push": "disabled_by_design",
            "sent": 0,
        })

    def test_runner_reads_only_snapshot_and_devices_and_reports_aggregate(self):
        output = io.StringIO()
        safe_summary = {
            "status": "dry_run",
            "candidate_status": "no_candidate",
            "push": "disabled_by_design",
            "sent": 0,
            "outbox_writes": 0,
        }
        devices = PushDeviceReadResult(devices=[{"device_id": "private-id"}], pages_processed=2)
        with (
            patch.object(job.PushPilotConfig, "from_environment", return_value=config()),
            patch.object(job, "NationalOfficialAlertSnapshotRepository") as snapshot_repo,
            patch.object(job, "PushDeviceRepository") as device_repo,
            patch.object(job, "evaluate_national_alert_push_dry_run", return_value=safe_summary) as evaluate,
            redirect_stdout(output),
        ):
            snapshot_repo.return_value.load.return_value = ({"contract": "fixture"}, "firestore")
            device_repo.return_value.read_active_devices.return_value = devices
            self.assertEqual(job.main(), 0)
        snapshot_repo.return_value.load.assert_called_once_with()
        device_repo.return_value.read_active_devices.assert_called_once_with(
            max_devices=100,
            enrollment_generation="play-beta-v1",
        )
        evaluate.assert_called_once()
        self.assertEqual(evaluate.call_args.kwargs["storage"], "firestore")
        self.assertIsInstance(evaluate.call_args.kwargs["policy"], NationalAlertDryRunPolicy)
        snapshot_repo.return_value.save.assert_not_called()
        device_repo.return_value.upsert_device.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), safe_summary | {"pages_processed": 2})
        self.assertNotIn("private-id", output.getvalue())


if __name__ == "__main__":
    unittest.main()
