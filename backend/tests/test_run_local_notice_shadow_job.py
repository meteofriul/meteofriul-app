import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from app.jobs import run_local_notice_shadow
from app.services.local_notice_shadow import (
    LocalNoticeShadowConfigurationError,
    LocalNoticeShadowDeviceStateUnavailable,
    LocalNoticeShadowRepositoryUnavailable,
)


def result(status="completed", *, failed=0):
    return SimpleNamespace(
        summary=lambda: {
            "status": status,
            "eligible_municipalities": 1,
            "evaluated": 1,
            "candidates": 0,
            "rejected": 0,
            "persisted": 1,
            "failed": failed,
        }
    )


class RunLocalNoticeShadowJobTests(unittest.TestCase):
    def run_job(self, *, value=None, error=None):
        service = SimpleNamespace()
        if error is None:
            service.run = lambda: value
        else:
            def raise_error():
                raise error

            service.run = raise_error

        output = io.StringIO()
        with (
            patch.object(
                run_local_notice_shadow,
                "get_local_notice_shadow_service",
                return_value=service,
            ),
            redirect_stdout(output),
        ):
            exit_code = run_local_notice_shadow.main()
        return exit_code, json.loads(output.getvalue()), output.getvalue()

    def test_completed_run_succeeds_with_sanitized_fixed_shape(self):
        exit_code, summary, raw = self.run_job(value=result())

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(
            set(summary),
            {
                "status",
                "eligible_municipalities",
                "evaluated",
                "candidates",
                "rejected",
                "persisted",
                "failed",
            },
        )
        self.assertNotIn("token", raw.lower())
        self.assertNotIn("device", raw.lower())

    def test_disabled_and_no_target_are_successful_noop_results(self):
        for status in ("disabled", "no_eligible_municipality"):
            with self.subTest(status=status):
                exit_code, summary, _ = self.run_job(
                    value=result(status, failed=0)
                )
                self.assertEqual(exit_code, 0)
                self.assertEqual(summary["status"], status)

    def test_rejected_or_failed_result_fails_closed(self):
        for status in (
            "rejected",
            "source_unavailable",
            "target_limit_exceeded",
            "invalid_target_state",
        ):
            with self.subTest(status=status):
                exit_code, summary, _ = self.run_job(
                    value=result(status, failed=1)
                )
                self.assertEqual(exit_code, 1)
                self.assertEqual(summary["failed"], 1)

    def test_known_runtime_errors_are_sanitized_and_fail(self):
        cases = (
            (
                LocalNoticeShadowConfigurationError("private detail"),
                "configuration_invalid",
            ),
            (
                LocalNoticeShadowDeviceStateUnavailable("private detail"),
                "device_state_unavailable",
            ),
            (
                LocalNoticeShadowRepositoryUnavailable("private detail"),
                "storage_unavailable",
            ),
        )
        for error, status in cases:
            with self.subTest(status=status):
                exit_code, summary, raw = self.run_job(error=error)
                self.assertEqual(exit_code, 1)
                self.assertEqual(summary["status"], status)
                self.assertEqual(summary["failed"], 1)
                self.assertNotIn("private detail", raw)


if __name__ == "__main__":
    unittest.main()
