import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from app.jobs import send_local_weather_notices
from app.repositories.push import PushRepositoryUnavailable
from app.services.local_notice_delivery import (
    LocalNoticeDeliveryAuditUnavailable,
    LocalNoticeDeliveryConfigurationError,
    LocalNoticeDeliveryDeviceStateUnavailable,
)


def result(status="sent", *, failed=0):
    return SimpleNamespace(
        summary=lambda: {
            "status": status,
            "eligible_devices": 1,
            "evaluated": 1,
            "candidates": 1,
            "selected_kind": "wind",
            "attempted": 1,
            "sent": int(status == "sent"),
            "sent_unconfirmed": int(status == "sent_unconfirmed"),
            "deduplicated": int(status == "deduplicated"),
            "persisted": 1,
            "failed": failed,
            "groups": 1,
            "failed_groups": int(failed > 0),
            "in_progress": int(status == "in_progress"),
            "retry_scheduled": int(status == "retry_scheduled"),
            "opted_out": int(status == "opted_out"),
            "expired": int(status == "expired"),
            "duplicate_targets": 0,
            "security_failed": 0,
            "device_failed": 0,
            "storage_failed": int(status == "sent_unconfirmed"),
            "audit_failed": 0,
            "source_failed": 0,
            "pages_processed": 1,
            "delivery_batches": int(status == "sent"),
        }
    )


class SendLocalWeatherNoticesJobTests(unittest.TestCase):
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
                send_local_weather_notices,
                "get_local_notice_delivery_service",
                return_value=service,
            ),
            redirect_stdout(output),
        ):
            exit_code = send_local_weather_notices.main()
        return exit_code, json.loads(output.getvalue()), output.getvalue()

    def test_success_output_has_fixed_sanitized_shape(self):
        for status in (
            "disabled",
            "no_eligible_device",
            "no_candidate",
            "not_eligible",
            "dry_run",
            "sent",
            "deduplicated",
            "in_progress",
            "retry_scheduled",
            "opted_out",
            "expired",
        ):
            with self.subTest(status=status):
                exit_code, summary, raw = self.run_job(value=result(status))
                self.assertEqual(exit_code, 0)
                self.assertEqual(summary["status"], status)
                self.assertEqual(len(summary), 25)
                self.assertNotIn("token", raw.lower())
                self.assertNotIn("installation", raw.lower())

    def test_sent_unconfirmed_is_sanitized_and_fails_the_job(self):
        exit_code, summary, raw = self.run_job(
            value=result("sent_unconfirmed", failed=1)
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["status"], "sent_unconfirmed")
        self.assertEqual(summary["sent"], 0)
        self.assertEqual(summary["sent_unconfirmed"], 1)
        self.assertEqual(summary["storage_failed"], 1)
        self.assertNotIn("token", raw.lower())
        self.assertNotIn("installation", raw.lower())

    def test_runtime_errors_are_sanitized_and_fail(self):
        cases = (
            (LocalNoticeDeliveryConfigurationError("secret"), "configuration_invalid"),
            (
                LocalNoticeDeliveryDeviceStateUnavailable("secret"),
                "device_state_unavailable",
            ),
            (
                LocalNoticeDeliveryAuditUnavailable("secret"),
                "audit_storage_unavailable",
            ),
            (PushRepositoryUnavailable("secret"), "delivery_storage_unavailable"),
        )
        for error, status in cases:
            with self.subTest(status=status):
                exit_code, summary, raw = self.run_job(error=error)
                self.assertEqual(exit_code, 1)
                self.assertEqual(summary["status"], status)
                self.assertEqual(summary["sent_unconfirmed"], 0)
                self.assertNotIn("secret", raw)


if __name__ == "__main__":
    unittest.main()
