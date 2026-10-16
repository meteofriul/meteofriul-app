import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from app.jobs import send_evening_forecast
from app.services.evening_forecast_delivery import (
    EveningForecastConfigurationError,
)


def result(status="sent", *, failed=0):
    return SimpleNamespace(
        summary=lambda: {
            "status": status,
            "eligible_devices": 1,
            "evaluated": 1,
            "attempted": 1,
            "sent": int(status == "sent"),
            "sent_unconfirmed": int(status == "sent_unconfirmed"),
            "deduplicated": int(status == "deduplicated"),
            "failed": failed,
            "groups": 1,
            "failed_groups": int(failed > 0),
            "in_progress": int(status == "in_progress"),
            "retry_scheduled": int(status == "retry_scheduled"),
            "opted_out": int(status == "opted_out"),
            "duplicate_targets": 0,
            "security_failed": 0,
            "device_failed": 0,
            "storage_failed": int(status == "sent_unconfirmed"),
            "source_failed": 0,
            "pages_processed": 1,
            "delivery_batches": int(status == "sent"),
        }
    )


class SendEveningForecastJobTests(unittest.TestCase):
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
                send_evening_forecast,
                "get_evening_forecast_delivery_service",
                return_value=service,
            ),
            redirect_stdout(output),
        ):
            exit_code = send_evening_forecast.main()
        return exit_code, json.loads(output.getvalue()), output.getvalue()

    def test_success_statuses_are_sanitized(self):
        for status in (
            "disabled",
            "no_eligible_device",
            "no_forecast",
            "dry_run",
            "sent",
            "deduplicated",
            "in_progress",
            "retry_scheduled",
            "opted_out",
        ):
            with self.subTest(status=status):
                exit_code, summary, raw = self.run_job(value=result(status))
                self.assertEqual(exit_code, 0)
                self.assertEqual(summary["status"], status)
                self.assertNotIn("token", raw.lower())
                self.assertNotIn("installation", raw.lower())

    def test_single_target_guard_failure_is_nonzero(self):
        exit_code, summary, _ = self.run_job(
            value=result("target_count_invalid", failed=1)
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["status"], "target_count_invalid")

    def test_configuration_error_is_sanitized(self):
        exit_code, summary, raw = self.run_job(
            error=EveningForecastConfigurationError("secret")
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["status"], "configuration_invalid")
        self.assertNotIn("secret", raw)


if __name__ == "__main__":
    unittest.main()
