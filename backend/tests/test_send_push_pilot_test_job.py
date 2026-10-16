import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from app.jobs import send_push_pilot_test
from app.services.push import PushConfigurationError


class SendPushPilotTestJobTests(unittest.TestCase):
    def test_success_output_is_sanitized_and_contains_no_device_secret(self):
        service = SimpleNamespace(
            send_pilot_test=lambda: SimpleNamespace(
                status="sent",
                sent=1,
                summary=lambda: {
                    "status": "sent",
                    "attempted": 1,
                    "sent": 1,
                    "deduplicated": 0,
                    "failed": 0,
                },
            )
        )
        output = io.StringIO()
        with (
            patch.object(
                send_push_pilot_test,
                "get_push_pilot_service",
                return_value=service,
            ),
            redirect_stdout(output),
        ):
            exit_code = send_push_pilot_test.main()

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["sent"], 1)
        self.assertNotIn("token", output.getvalue())
        self.assertNotIn("device", output.getvalue())

    def test_explicit_test_switch_failure_returns_nonzero(self):
        service = SimpleNamespace(
            send_pilot_test=lambda: (_ for _ in ()).throw(
                PushConfigurationError("not_enabled")
            )
        )
        with (
            patch.object(
                send_push_pilot_test,
                "get_push_pilot_service",
                return_value=service,
            ),
            redirect_stdout(io.StringIO()),
        ):
            exit_code = send_push_pilot_test.main()

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
