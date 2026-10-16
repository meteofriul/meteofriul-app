import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from app.jobs import sync_event_sources
from app.repositories.event_sources import EventSourceStateRepositoryUnavailable
from app.services.event_sources import (
    EventSourceAutomationConfigurationError,
    EventSourceAutomationRunResult,
)


class SyncEventSourcesJobTests(unittest.TestCase):
    def run_job(self, service):
        output = io.StringIO()
        with patch(
            "app.jobs.sync_event_sources.get_event_source_automation_service",
            return_value=service,
        ), redirect_stdout(output):
            exit_code = sync_event_sources.main()
        return exit_code, json.loads(output.getvalue())

    def test_success_emits_structured_monitoring_record(self):
        service = Mock()
        service.run.return_value = EventSourceAutomationRunResult(
            status="completed",
            storage="firestore",
            approved=6,
            quarantined=1,
        )

        exit_code, payload = self.run_job(service)

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["severity"], "INFO")
        self.assertEqual(payload["notification_transport"], "cloud_monitoring_email")
        self.assertEqual(payload["alert_email_to"], "info@meteofriul.it")
        self.assertEqual(payload["issues"], [])

    def test_active_incident_returns_failure_for_cloud_run_job(self):
        service = Mock()
        service.run.return_value = EventSourceAutomationRunResult(
            status="incident",
            incident_active=True,
            alert_transition="opened",
            issues=(
                "active_catalog_coverage:Codroipo:SagreFVG:error",
                "visible_catalog_incomplete",
            ),
            incident_details=(
                {
                    "type": "active_catalog_coverage",
                    "city": "Codroipo",
                    "source": "SagreFVG",
                    "status": "error",
                },
            ),
            active_catalog_coverage={
                "complete": False,
                "incomplete_cities": ["Codroipo"],
                "failures": [
                    {
                        "city": "Codroipo",
                        "source": "SagreFVG",
                        "status": "error",
                    }
                ],
                "warnings": ["Codroipo/SagreFVG: upstream timeout"],
            },
        )

        exit_code, payload = self.run_job(service)

        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["severity"], "ERROR")
        self.assertEqual(payload["event"], "event_source_automation_incident")
        self.assertEqual(
            payload["incident_details"][0]["source"],
            "SagreFVG",
        )
        self.assertEqual(
            payload["active_catalog_coverage"]["incomplete_cities"],
            ["Codroipo"],
        )

    def test_configuration_failure_is_reported_without_traceback_or_secrets(self):
        output = io.StringIO()
        with patch(
            "app.jobs.sync_event_sources.get_event_source_automation_service",
            side_effect=EventSourceAutomationConfigurationError("invalid secret"),
        ), redirect_stdout(output):
            exit_code = sync_event_sources.main()
        payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "configuration_invalid")
        self.assertEqual(payload["issues"], ["configuration_invalid"])
        self.assertNotIn("invalid secret", output.getvalue())

    def test_storage_failure_is_reported(self):
        service = Mock()
        service.run.side_effect = EventSourceStateRepositoryUnavailable("offline")

        exit_code, payload = self.run_job(service)

        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "storage_unavailable")


if __name__ == "__main__":
    unittest.main()
