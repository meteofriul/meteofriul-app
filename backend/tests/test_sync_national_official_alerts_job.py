import io
import json
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from unittest.mock import patch

from app.jobs import sync_national_official_alerts
from app.services.dpc_national_source import DpcNationalSourceError
from app.services.national_official_alerts_state import (
    NationalOfficialAlertSyncResult,
)

from tests.test_national_official_alerts import reconciled_snapshot


class FakeService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def refresh(self):
        if self.error is not None:
            raise self.error
        return self.result


class SyncNationalOfficialAlertsJobTests(unittest.TestCase):
    def run_job(self, service, *, require_persistent=True):
        output = io.StringIO()
        with (
            patch.object(
                sync_national_official_alerts,
                "get_national_official_alerts_state_service",
                return_value=service,
            ),
            patch.dict(
                sync_national_official_alerts.os.environ,
                {
                    "NATIONAL_OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE": (
                        "true" if require_persistent else "false"
                    )
                },
                clear=False,
            ),
            redirect_stdout(output),
        ):
            exit_code = sync_national_official_alerts.main()
        return exit_code, json.loads(output.getvalue())

    def test_new_revision_succeeds_only_when_persisted(self):
        snapshot = reconciled_snapshot()
        result = NationalOfficialAlertSyncResult(
            payload=deepcopy(snapshot),
            refreshed=True,
            stored_in="firestore",
            reason="stored",
        )
        exit_code, summary = self.run_job(FakeService(result=result))

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["revision"], "20260924_1434")
        self.assertEqual(summary["push"], "disabled_by_design")
        self.assertEqual(summary["record_count"], 600)

    def test_same_persisted_revision_is_a_successful_noop(self):
        result = NationalOfficialAlertSyncResult(
            payload=reconciled_snapshot(),
            refreshed=False,
            stored_in="firestore",
            reason="already_current",
        )
        exit_code, summary = self.run_job(FakeService(result=result))
        self.assertEqual(exit_code, 0)
        self.assertFalse(summary["refreshed"])

    def test_non_public_cap_with_safe_previous_is_explicitly_deferred(self):
        result = NationalOfficialAlertSyncResult(
            payload=reconciled_snapshot(),
            refreshed=False,
            stored_in="firestore",
            reason="source_cap_not_public_held",
        )
        exit_code, summary = self.run_job(FakeService(result=result))
        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["status"], "deferred")
        self.assertEqual(summary["push"], "disabled_by_design")
        self.assertFalse(summary["refreshed"])

    def test_non_public_cap_without_previous_remains_a_failure(self):
        exit_code, summary = self.run_job(
            FakeService(error=DpcNationalSourceError("dpc_source_cap_not_public"))
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["reason"], "dpc_source_cap_not_public")

    def test_memory_only_write_fails_when_persistence_is_required(self):
        result = NationalOfficialAlertSyncResult(
            payload=reconciled_snapshot(),
            refreshed=True,
            stored_in="memory",
            reason="stored",
        )
        exit_code, summary = self.run_job(FakeService(result=result))
        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["status"], "failed")

        exit_code, _ = self.run_job(
            FakeService(result=result), require_persistent=False
        )
        self.assertEqual(exit_code, 0)

    def test_source_failure_is_sanitized_and_fails(self):
        exit_code, summary = self.run_job(
            FakeService(error=DpcNationalSourceError("dpc_source_request_failed"))
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["reason"], "dpc_source_request_failed")
        self.assertNotIn("records", summary)

    def test_rollback_is_not_reported_as_success(self):
        result = NationalOfficialAlertSyncResult(
            payload=reconciled_snapshot(),
            refreshed=False,
            stored_in="firestore",
            reason="revision_rollback_rejected",
        )
        exit_code, summary = self.run_job(FakeService(result=result))
        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["reason"], "revision_rollback_rejected")


if __name__ == "__main__":
    unittest.main()
