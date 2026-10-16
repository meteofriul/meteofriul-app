import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from app.jobs import send_national_official_alerts
from app.services.national_alert_delivery import NationalAlertDeliveryUnavailable


class NationalAlertSendJobTests(unittest.TestCase):
    def run_job(self, result=None, error=None):
        service = SimpleNamespace(run=lambda: result)
        if error is not None:
            def fail():
                raise error
            service.run = fail
        output = io.StringIO()
        with patch.object(send_national_official_alerts, "get_national_alert_delivery_service", return_value=service):
            with redirect_stdout(output):
                code = send_national_official_alerts.main()
        return code, json.loads(output.getvalue())

    def test_disabled_dry_run_and_no_candidate_are_successful_without_sending(self):
        for status in ("disabled", "dry_run", "no_candidate", "deduplicated"):
            with self.subTest(status=status):
                code, summary = self.run_job({"status": status, "sent": 0, "outbox_writes": 0})
                self.assertEqual(code, 0)
                self.assertEqual(summary["sent"], 0)

    def test_partial_delivery_is_failure_for_scheduler(self):
        code, summary = self.run_job({"status": "partial", "sent": 1, "failed": 1})
        self.assertEqual(code, 1)
        self.assertEqual(summary["status"], "partial")

    def test_known_guard_error_is_sanitized(self):
        code, summary = self.run_job(error=NationalAlertDeliveryUnavailable("national_alert_send_gate_closed"))
        self.assertEqual(code, 1)
        self.assertEqual(summary["reason"], "national_alert_send_gate_closed")

    def test_unknown_exception_does_not_leak_device_details(self):
        code, summary = self.run_job(error=RuntimeError("secret-device-token"))
        self.assertEqual(code, 1)
        self.assertEqual(summary["reason"], "national_alert_internal_error")
        self.assertNotIn("secret-device-token", str(summary))


if __name__ == "__main__":
    unittest.main()
