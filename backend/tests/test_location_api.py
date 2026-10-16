import json
import inspect
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.location import get_location_service
from app.contracts.location import LocationSearchItem
from app.main import create_app
from app.services.location import (
    LocationSearchSourceUnavailable,
    LocationService,
    LocationSourceUnavailable,
)


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = WORKSPACE_ROOT / "contracts" / "runtime-api" / "v1" / "location"


class StubReverseSource:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def fetch(self, lat, lon):
        self.calls.append((lat, lon))
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class StubSearchSource:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def search(self, query, limit):
        self.calls.append((query, limit))
        if isinstance(self.payload, Exception):
            raise self.payload
        return [item.model_copy(deep=True) for item in self.payload]


class LocationApiTests(unittest.TestCase):
    def create_client(self, service):
        app = create_app()
        app.dependency_overrides[get_location_service] = lambda: service
        return TestClient(app)

    def test_healthcheck(self):
        app = create_app()
        app.dependency_overrides[get_location_service] = lambda: LocationService(
            reverse_source=StubReverseSource({"address": {}})
        )
        client = TestClient(app)
        for path in ("/healthz", "/api/healthz"):
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ok")
            policy = response.json()["weather_provider_policy"]
            self.assertIn("valid", policy)
            self.assertIn("open_meteo_enabled", policy)
            self.assertIn("local_weather_pilot_ready", policy)

        health_route = next(
            route for route in app.routes if getattr(route, "path", "") == "/api/healthz"
        )
        self.assertTrue(inspect.iscoroutinefunction(health_route.endpoint))

    def test_search_contract(self):
        source = StubSearchSource([])
        client = self.create_client(
            LocationService(
                reverse_source=StubReverseSource({"address": {}}),
                search_source=source,
            )
        )
        response = client.get("/api/location/search", params={"q": "pord"})
        expected = json.loads((FIXTURE_ROOT / "search-success.json").read_text(encoding="utf-8"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[:3], expected)
        self.assertEqual(source.calls, [("pord", 8)])

    def test_search_contract_supports_national_places_without_fvg_identifiers(self):
        source = StubSearchSource([
            LocationSearchItem(
                name="Torino",
                admin1="Piemonte",
                latitude=45.0703,
                longitude=7.6869,
                population=847398,
                provinceName="Torino",
            )
        ])
        client = self.create_client(LocationService(search_source=source))

        response = client.get("/api/location/search", params={"q": "torino"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [{
                "name": "Torino",
                "admin1": "Piemonte",
                "latitude": 45.0703,
                "longitude": 7.6869,
                "population": 847398,
                "province": "",
                "provinceName": "Torino",
                "istatCode": "",
                "country": "Italia",
                "countryCode": "IT",
                "provider": "",
                "providerId": "",
            }],
        )
        self.assertEqual(source.calls, [("torino", 8)])

    def test_search_returns_local_results_when_national_source_fails(self):
        source = StubSearchSource(
            LocationSearchSourceUnavailable("location_search_source_failed")
        )
        client = self.create_client(LocationService(search_source=source))

        response = client.get("/api/location/search", params={"q": "pord"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["name"], "Pordenone")
        self.assertEqual(response.json()[0]["istatCode"], "093033")
        self.assertEqual(source.calls, [("pord", 8)])

    def test_search_returns_503_when_only_the_national_source_can_answer(self):
        source = StubSearchSource(
            LocationSearchSourceUnavailable("location_search_source_failed")
        )
        client = self.create_client(LocationService(search_source=source))

        response = client.get("/api/location/search", params={"q": "torino"})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "location_search_source_unavailable",
        )

    def test_reverse_contract(self):
        source = StubReverseSource(AssertionError("public reverse source called"))
        service = LocationService(reverse_source=source)
        client = self.create_client(service)
        response = client.post(
            "/api/location/reverse",
            json={"lat": 45.9567, "lon": 12.6605},
        )
        expected = json.loads(
            (FIXTURE_ROOT / "reverse-fvg-success.json").read_text(encoding="utf-8")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        self.assertEqual(source.calls, [])

    def test_reverse_without_accuracy_inside_fvg_returns_municipality_only(self):
        service = LocationService(
            reverse_source=StubReverseSource(LocationSourceUnavailable("offline"))
        )
        client = self.create_client(service)
        response = client.post(
            "/api/location/reverse",
            json={"lat": 45.9567, "lon": 12.6605},
        )
        expected = json.loads((
            FIXTURE_ROOT / "reverse-fvg-municipality-only-success.json"
        ).read_text(encoding="utf-8"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

    def test_reverse_with_accuracy_resolves_cellino_fully_offline(self):
        source = StubReverseSource(AssertionError("public reverse source called"))
        service = LocationService(reverse_source=source)
        client = self.create_client(service)
        response = client.post(
            "/api/location/reverse",
            json={
                "lat": 46.2479446,
                "lon": 12.4703415,
                "accuracyM": 30,
            },
        )
        expected = json.loads(
            (FIXTURE_ROOT / "reverse-fvg-nearest-success.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        self.assertEqual(source.calls, [])

    def test_reverse_outside_fvg_returns_the_external_place_and_canonical_point(self):
        service = LocationService(reverse_source=StubReverseSource({
            "lat": "44.4938203",
            "lon": "11.3426327",
            "name": "Bologna",
            "address": {
                "city": "Bologna",
                "state": "Emilia-Romagna",
                "country": "Italia",
                "country_code": "it",
            },
        }))
        client = self.create_client(service)
        response = client.post(
            "/api/location/reverse",
            json={"lat": 44.4949, "lon": 11.3426, "accuracyM": 20},
        )
        expected = json.loads((
            FIXTURE_ROOT / "reverse-outside-fvg-success.json"
        ).read_text(encoding="utf-8"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        self.assertEqual(response.json()["city"], "Bologna")
        self.assertEqual(response.json()["region"], "Emilia-Romagna")
        self.assertEqual(response.json()["resolution"]["status"], "external_place")
        self.assertEqual(response.json()["dataPoint"], {
            "lat": 44.4938203,
            "lon": 11.3426327,
            "source": "nominatim_place",
        })

    def test_reverse_outside_fvg_returns_503_when_external_resolution_is_unavailable(self):
        service = LocationService(
            reverse_source=StubReverseSource(LocationSourceUnavailable("offline"))
        )
        client = self.create_client(service)

        response = client.post(
            "/api/location/reverse",
            json={"lat": 44.4949, "lon": 11.3426, "accuracyM": 20},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "location_source_unavailable")

    def test_reverse_rejects_invalid_coordinates(self):
        client = self.create_client(LocationService(reverse_source=StubReverseSource({"address": {}})))
        response = client.post(
            "/api/location/reverse",
            json={"lat": 120, "lon": 12.6605},
        )
        self.assertEqual(response.status_code, 422)

    def test_reverse_rejects_untyped_body_fields(self):
        client = self.create_client(LocationService(reverse_source=StubReverseSource({"address": {}})))
        response = client.post(
            "/api/location/reverse",
            json={"lat": 45.9567, "lon": 12.6605, "label": "home"},
        )
        self.assertEqual(response.status_code, 422)

    def test_reverse_rejects_invalid_accuracy(self):
        client = self.create_client(LocationService())
        response = client.post(
            "/api/location/reverse",
            json={"lat": 45.9567, "lon": 12.6605, "accuracyM": -1},
        )
        self.assertEqual(response.status_code, 422)

    def test_reverse_get_remains_available_but_is_deprecated(self):
        service = LocationService(
            reverse_source=StubReverseSource(AssertionError("source called"))
        )
        client = self.create_client(service)

        response = client.get(
            "/api/location/reverse",
            params={"lat": 45.9567, "lon": 12.6605},
        )
        operation = client.get("/api/openapi.json").json()["paths"]["/api/location/reverse"]["get"]

        self.assertEqual(response.status_code, 200)
        self.assertTrue(operation["deprecated"])


if __name__ == "__main__":
    unittest.main()
