import unittest

from fastapi.testclient import TestClient

from app.api.events import get_events_service
from app.contracts.events import LocalEventDetailResponse, LocalEventsResponse
from app.main import create_app


class FixtureEventsService:
    def get_event_detail(self, source, url):
        return LocalEventDetailResponse.model_validate(
            {
                "source": source,
                "url": url,
                "description": "Descrizione verificata sulla pagina ufficiale.",
            }
        )

    def get_local_events(self, city, limit, lat, lon):
        return LocalEventsResponse.model_validate(
            {
                "city": city,
                "events": [
                    {
                        "title": "Sagra dell'Assunta",
                        "place": "Porcia",
                        "event_city": "Porcia",
                        "date": "dal 31 luglio al 16 agosto 2026",
                        "source": "TurismoFVG",
                        "url": "https://www.turismofvg.it/eventi/sagra-dell-assunta-498528",
                        "lat": 45.96301,
                        "lon": 12.61642,
                        "is_real": True,
                        "category": "sagra",
                        "category_label": "Sagra / festa locale",
                    }
                ],
                "events_scope": "nearby",
                "source": "TurismoFVG",
                "sources": ["TurismoFVG"],
                "is_real": True,
                "cache": {"status": "fresh"},
            }
        )


class EventsApiTests(unittest.TestCase):
    def create_client(self):
        app = create_app()
        app.dependency_overrides[get_events_service] = FixtureEventsService
        return TestClient(app)

    def test_local_events_contract_keeps_nearby_municipality(self):
        response = self.create_client().get(
            "/api/local/events",
            params={
                "city": "Pordenone",
                "limit": 100,
                "lat": 45.9567,
                "lon": 12.6605,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["events_scope"], "nearby")
        self.assertEqual(payload["events"][0]["event_city"], "Porcia")
        self.assertEqual(payload["cache"]["status"], "fresh")

    def test_local_events_reject_invalid_coordinates(self):
        response = self.create_client().get(
            "/api/local/events",
            params={"city": "Pordenone", "lat": 120, "lon": 12.6605},
        )
        self.assertEqual(response.status_code, 422)

    def test_local_event_detail_contract_returns_verified_description(self):
        event_url = "https://www.turismofvg.it/eventi/armonie-in-citta"
        response = self.create_client().get(
            "/api/local/events/detail",
            params={"source": "TurismoFVG", "url": event_url},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "source": "TurismoFVG",
                "url": event_url,
                "description": "Descrizione verificata sulla pagina ufficiale.",
            },
        )


if __name__ == "__main__":
    unittest.main()
