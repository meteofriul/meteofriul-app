import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from app.jobs import sync_official_alerts


def make_result(*, refreshed=True, stored_in="firestore"):
    return SimpleNamespace(
        payload={
            "active": False,
            "cache": {"status": "fresh"},
            "count": 0,
            "source_mode": "official_widget",
        },
        refreshed=refreshed,
        stored_in=stored_in,
    )


class SyncOfficialAlertsJobTests(unittest.TestCase):
    def run_job(self, result, *, require_persistent_storage):
        service = SimpleNamespace(refresh=lambda: result)
        environment = {
            "OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE": (
                "true" if require_persistent_storage else "false"
            ),
            "PUSH_OFFICIAL_ALERTS_REQUIRED": "false",
        }
        output = io.StringIO()
        with (
            patch.object(
                sync_official_alerts,
                "get_official_alerts_state_service",
                return_value=service,
            ),
            patch.dict(sync_official_alerts.os.environ, environment, clear=False),
            redirect_stdout(output),
        ):
            exit_code = sync_official_alerts.main()
        self.last_output = output.getvalue()
        return exit_code

    def test_persisted_refresh_succeeds_when_firestore_is_required(self):
        exit_code = self.run_job(
            make_result(stored_in="firestore"),
            require_persistent_storage=True,
        )

        self.assertEqual(exit_code, 0)
        self.assertNotIn("local_notice_shadow", json.loads(self.last_output))

    def test_memory_only_refresh_fails_when_firestore_is_required(self):
        exit_code = self.run_job(
            make_result(stored_in="memory"),
            require_persistent_storage=True,
        )

        self.assertEqual(exit_code, 1)

    def test_memory_refresh_remains_valid_for_local_runs(self):
        exit_code = self.run_job(
            make_result(stored_in="memory"),
            require_persistent_storage=False,
        )

        self.assertEqual(exit_code, 0)

    def test_unconfirmed_refresh_fails_even_when_firestore_is_available(self):
        exit_code = self.run_job(
            make_result(refreshed=False, stored_in="firestore"),
            require_persistent_storage=True,
        )

        self.assertEqual(exit_code, 1)

    def test_failed_refresh_prints_only_sanitized_upstream_diagnostics(self):
        result = make_result(refreshed=False, stored_in="firestore")
        result.payload["cache"] = {
            "status": "unavailable",
            "upstream_failure": {
                "attempts": [
                    {
                        "source": "widget",
                        "category": "http",
                        "status_code": 503,
                        "url": "https://secret.test/?token=private",
                        "body": "private response",
                    },
                    {"source": "html", "category": "parser", "detail": "private"},
                ]
            },
        }

        exit_code = self.run_job(result, require_persistent_storage=True)

        summary = json.loads(self.last_output)
        self.assertEqual(exit_code, 1)
        self.assertEqual(
            summary["upstream_failure"],
            {
                "attempts": [
                    {"source": "widget", "category": "http", "status_code": 503},
                    {"source": "html", "category": "parser"},
                ]
            },
        )
        self.assertNotIn("secret.test", self.last_output)
        self.assertNotIn("private", self.last_output)
        self.assertNotIn("token", self.last_output)

    def test_trusted_sync_dispatches_sanitized_push_summary(self):
        service = SimpleNamespace(refresh=lambda: make_result())
        push_result = SimpleNamespace(
            status="sent",
            summary=lambda: {
                "status": "sent",
                "attempted": 1,
                "sent": 1,
                "sent_unconfirmed": 0,
                "deduplicated": 0,
                "failed": 0,
            },
        )
        dispatched = []
        push_service = SimpleNamespace(
            dispatch_official_alerts=lambda payload: (
                dispatched.append(payload) or push_result
            )
        )
        output = io.StringIO()
        with (
            patch.object(
                sync_official_alerts,
                "get_official_alerts_state_service",
                return_value=service,
            ),
            patch.object(
                sync_official_alerts,
                "get_push_pilot_service",
                return_value=push_service,
            ),
            patch.dict(
                sync_official_alerts.os.environ,
                {"OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE": "true"},
                clear=False,
            ),
            redirect_stdout(output),
        ):
            exit_code = sync_official_alerts.main()

        summary = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(summary["push"]["status"], "sent")
        self.assertNotIn("token", output.getvalue())

    def test_push_delivery_failure_fails_the_trusted_job(self):
        service = SimpleNamespace(refresh=lambda: make_result())
        push_service = SimpleNamespace(
            dispatch_official_alerts=lambda payload: SimpleNamespace(
                status="failed",
                summary=lambda: {
                    "status": "failed",
                    "attempted": 1,
                    "sent": 0,
                    "deduplicated": 0,
                    "failed": 1,
                },
            )
        )
        with (
            patch.object(
                sync_official_alerts,
                "get_official_alerts_state_service",
                return_value=service,
            ),
            patch.object(
                sync_official_alerts,
                "get_push_pilot_service",
                return_value=push_service,
            ),
            patch.dict(
                sync_official_alerts.os.environ,
                {"OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE": "true"},
                clear=False,
            ),
            redirect_stdout(io.StringIO()),
        ):
            exit_code = sync_official_alerts.main()

        self.assertEqual(exit_code, 1)

    def test_unconfirmed_fcm_send_is_sanitized_and_fails_the_job(self):
        service = SimpleNamespace(refresh=lambda: make_result())
        push_service = SimpleNamespace(
            dispatch_official_alerts=lambda payload: SimpleNamespace(
                status="sent_unconfirmed",
                summary=lambda: {
                    "status": "sent_unconfirmed",
                    "attempted": 1,
                    "sent": 0,
                    "sent_unconfirmed": 1,
                    "deduplicated": 0,
                    "failed": 1,
                },
            )
        )
        output = io.StringIO()
        with (
            patch.object(
                sync_official_alerts,
                "get_official_alerts_state_service",
                return_value=service,
            ),
            patch.object(
                sync_official_alerts,
                "get_push_pilot_service",
                return_value=push_service,
            ),
            patch.dict(
                sync_official_alerts.os.environ,
                {"OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE": "true"},
                clear=False,
            ),
            redirect_stdout(output),
        ):
            exit_code = sync_official_alerts.main()

        summary = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["push"]["status"], "sent_unconfirmed")
        self.assertEqual(summary["push"]["sent"], 0)
        self.assertEqual(summary["push"]["sent_unconfirmed"], 1)
        self.assertEqual(summary["push"]["failed"], 1)
        self.assertNotIn("token", output.getvalue())

    def test_required_push_mode_rejects_a_disabled_dispatch(self):
        service = SimpleNamespace(refresh=lambda: make_result())
        push_service = SimpleNamespace(
            dispatch_official_alerts=lambda payload: SimpleNamespace(
                status="disabled",
                summary=lambda: {
                    "status": "disabled",
                    "attempted": 0,
                    "sent": 0,
                    "deduplicated": 0,
                    "failed": 0,
                },
            )
        )
        output = io.StringIO()
        with (
            patch.object(
                sync_official_alerts,
                "get_official_alerts_state_service",
                return_value=service,
            ),
            patch.object(
                sync_official_alerts,
                "get_push_pilot_service",
                return_value=push_service,
            ),
            patch.dict(
                sync_official_alerts.os.environ,
                {
                    "OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE": "true",
                    "PUSH_OFFICIAL_ALERTS_REQUIRED": "true",
                },
                clear=False,
            ),
            redirect_stdout(output),
        ):
            exit_code = sync_official_alerts.main()

        summary = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(summary["push"]["status"], "send_mode_required")

    def test_push_is_not_dispatched_after_unconfirmed_refresh(self):
        service = SimpleNamespace(
            refresh=lambda: make_result(refreshed=False, stored_in="firestore")
        )
        push_service = SimpleNamespace(
            dispatch_official_alerts=lambda payload: self.fail(
                "push must not run after a failed official refresh"
            )
        )
        with (
            patch.object(
                sync_official_alerts,
                "get_official_alerts_state_service",
                return_value=service,
            ),
            patch.object(
                sync_official_alerts,
                "get_push_pilot_service",
                return_value=push_service,
            ),
            patch.dict(
                sync_official_alerts.os.environ,
                {"OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE": "true"},
                clear=False,
            ),
            redirect_stdout(io.StringIO()),
        ):
            exit_code = sync_official_alerts.main()

        self.assertEqual(exit_code, 1)

if __name__ == "__main__":
    unittest.main()
