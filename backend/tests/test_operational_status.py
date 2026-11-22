import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.infrastructure.events_admin_auth import require_events_admin
from app.main import create_app
from app.services.operational_status import build_operational_status


NOW = datetime(2026, 11, 22, 20, 0, tzinfo=timezone.utc)


def run(kind, day, *, sent=0, failed=1, source_failed=0, status="failed"):
    return {"jsonPayload": {
        "status": status, "sent": sent, "failed": failed,
        "eligible_devices": 66, "source_failed": source_failed,
        "execution_context": {
            "kind": kind, "completed_at": f"2026-11-{day}T19:45:30Z",
        },
    }}


class OperationalStatusTests(unittest.TestCase):
    def test_one_missed_evening_is_check_and_second_is_urgent(self):
        once = build_operational_status(
            entries=[run("morning", "22", sent=65, failed=0, status="sent"),
                     run("evening", "22", source_failed=20),
                     run("evening", "21", sent=65, failed=0, status="sent")],
            catalog={"schema": "pilot-events-v1", "sources": {}}, now=NOW)
        evening = next(item for item in once["issues"] if item["id"] == "forecast:evening")
        self.assertEqual(evening["severity"], "check")
        self.assertIn("fonte meteo", evening["advice"])

        twice = build_operational_status(
            entries=[run("morning", "22", sent=65, failed=0, status="sent"),
                     run("evening", "22", source_failed=20),
                     run("evening", "21", source_failed=20),
                     run("evening", "20", sent=65, failed=0, status="sent")],
            catalog={"schema": "pilot-events-v1", "sources": {}}, now=NOW)
        self.assertEqual(next(item for item in twice["issues"]
                              if item["id"] == "forecast:evening")["severity"], "urgent")
        self.assertEqual(twice["urgentCount"], 1)

    def test_success_resolves_missed_forecast_and_small_partial_is_log_only(self):
        result = build_operational_status(
            entries=[run("morning", "22", sent=65, failed=1, status="partial"),
                     run("evening", "22", sent=66, failed=0, status="sent"),
                     run("evening", "21", source_failed=20)],
            catalog={"schema": "pilot-events-v1", "sources": {}}, now=NOW)
        self.assertEqual(result["count"], 0)

    def test_yesterday_success_does_not_hide_today_missing_run(self):
        result = build_operational_status(
            entries=[run("morning", "22", sent=65, failed=0, status="sent"),
                     run("evening", "21", sent=65, failed=0, status="sent")],
            catalog={"schema": "pilot-events-v1", "sources": {}}, now=NOW)
        self.assertEqual([item["id"] for item in result["issues"]], ["forecast:evening"])
        self.assertEqual(result["issues"][0]["severity"], "check")

    def test_a_small_number_of_successful_deliveries_is_not_a_healthy_run(self):
        result = build_operational_status(
            entries=[run("morning", "22", sent=1, failed=59, status="partial"),
                     run("morning", "21", sent=60, failed=0, status="sent"),
                     run("evening", "22", sent=60, failed=0, status="sent")],
            catalog={"schema": "pilot-events-v1", "sources": {}}, now=NOW)
        self.assertEqual([item["id"] for item in result["issues"]], ["forecast:morning"])
        self.assertIn("solo per una parte", result["issues"][0]["detail"])

    def test_stale_events_are_one_actionable_group_and_candidates_are_reviews(self):
        catalog = {"schema": "pilot-events-v1", "attempted_at": NOW.isoformat(),
                   "paused_sources": ["Galleria Spazzapan"],
                   "sources": {
                       "Azalea": {"status": "stale", "updated_at": "2026-11-20T04:00:00Z"},
                       "Barcolana": {"status": "unavailable"},
                       "CSS Udine": {"status": "partial", "updated_at": NOW.isoformat()},
                       "Galleria Spazzapan": {"status": "stale"},
                   },
                   "monitors": {"GiroFVG": {"status": "review_required"}}}
        result = build_operational_status(
            entries=[run("morning", "22", sent=65, failed=0, status="sent"),
                     run("evening", "22", sent=65, failed=0, status="sent")],
            catalog=catalog, now=NOW)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["issues"][0]["title"], "Eventi · 2 fonti da controllare")
        self.assertIn("Azalea, Barcolana", result["issues"][0]["detail"])
        self.assertEqual(len(result["reviews"]), 1)

    def test_missing_evidence_is_not_green(self):
        result = build_operational_status(entries=None, catalog=None, now=NOW)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["coverage"], {"forecasts": False, "events": False})


class OperationalStatusApiTests(unittest.TestCase):
    def test_owner_only_and_no_store(self):
        app = create_app()
        client = TestClient(app)
        self.assertEqual(client.get("/api/admin/operations").status_code, 401)
        app.dependency_overrides[require_events_admin] = lambda: {"uid": "owner"}
        with patch("app.api.operations_admin._forecast_entries", return_value=[]), \
             patch("app.api.operations_admin._catalog", return_value={
                 "schema": "pilot-events-v1", "sources": {}}), \
             patch("app.api.operations_admin.read_controls", return_value=({"sources": {}}, None)), \
             patch("app.api.operations_admin._blob"):
            response = client.get("/api/admin/operations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(set(response.json()),
                         {"checkedAt", "coverage", "count", "urgentCount", "issues", "reviews"})

    def test_source_read_failure_is_reported_without_leaking_error_details(self):
        app = create_app()
        app.dependency_overrides[require_events_admin] = lambda: {"uid": "owner"}
        with patch("app.api.operations_admin._forecast_entries", side_effect=RuntimeError("private")), \
             patch("app.api.operations_admin._catalog", side_effect=RuntimeError("private")):
            response = TestClient(app).get("/api/admin/operations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertNotIn("private", response.text)


if __name__ == "__main__":
    unittest.main()
