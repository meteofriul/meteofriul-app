import unittest

from fastapi.testclient import TestClient

from app.api.weather import get_national_official_alerts_service
from app.main import create_app
from app.services.national_official_alerts_state import (
    NationalOfficialAlertsUnavailable,
)

from tests.test_national_official_alerts import NOW, reconciled_snapshot
from tests.test_national_official_alerts_state import FakeRepository
from app.services.national_official_alerts_state import (
    NationalOfficialAlertsStateService,
)


class ErrorService:
    def __init__(self, error):
        self.error = error

    def get_for_municipality(self, municipality_istat):
        raise NationalOfficialAlertsUnavailable(self.error)


class NationalOfficialAlertsApiTests(unittest.TestCase):
    def client(self, service):
        app = create_app()
        app.dependency_overrides[get_national_official_alerts_service] = (
            lambda: service
        )
        return TestClient(app)

    def test_returns_location_aware_national_contract(self):
        service = NationalOfficialAlertsStateService(
            repository=FakeRepository(reconciled_snapshot()),
            loader=lambda: None,
            now=lambda: NOW,
        )
        response = self.client(service).get(
            "/api/weather/official-alerts/national",
            params={"municipality_istat": "041067"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["municipality"]["name"], "Urbino")
        self.assertEqual(payload["zones"], ["DPC:Marc-1", "DPC:Marc-2"])
        self.assertTrue(payload["standalone_display_allowed"])
        self.assertEqual(payload["cache"]["storage"], "firestore")

    def test_fvg_response_carries_the_non_replacement_guard(self):
        service = NationalOfficialAlertsStateService(
            repository=FakeRepository(reconciled_snapshot(zone="Friu-A")),
            loader=lambda: None,
            now=lambda: NOW,
        )
        response = self.client(service).get(
            "/api/weather/official-alerts/national",
            params={"municipality_istat": "093033"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["standalone_display_allowed"])
        self.assertTrue(payload["regional_detail"]["required"])

    def test_unavailable_and_unknown_municipality_have_distinct_statuses(self):
        unavailable = self.client(
            ErrorService("national_official_alert_snapshot_unavailable")
        ).get(
            "/api/weather/official-alerts/national",
            params={"municipality_istat": "041067"},
        )
        unknown = self.client(
            ErrorService("national_alert_municipality_unresolved")
        ).get(
            "/api/weather/official-alerts/national",
            params={"municipality_istat": "999999"},
        )
        malformed = self.client(ErrorService("unused")).get(
            "/api/weather/official-alerts/national",
            params={"municipality_istat": "41067"},
        )

        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(malformed.status_code, 422)


if __name__ == "__main__":
    unittest.main()
