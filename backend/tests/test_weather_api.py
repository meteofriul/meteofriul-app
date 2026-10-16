import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.weather import get_weather_service
from app.contracts.weather import (
    OfficialAlertsResponse,
    WeatherBootstrapResponse,
    WeatherCurrentResponse,
    WeatherForecastResponse,
    WeatherRadarResponse,
)
from app.main import create_app
from app.infrastructure.open_meteo_policy import (
    LOCAL_WEATHER_PILOT_ENV,
    LOCAL_WEATHER_PILOT_HEADER,
    OPEN_METEO_ENABLED_ENV,
)
from app.services.weather import WeatherSourceUnavailable


FORECAST_FIXTURE = {
    "city": "Pordenone",
    "forecast": [
        {
            "date": "2026-08-10",
            "condition": "Poco nuvoloso",
            "weathercode": 3,
            "min_temp": 23,
            "max_temp": 36,
            "official_text": "Cielo in genere sereno o poco nuvoloso.",
        }
    ],
    "daily": {
        "time": ["2026-08-10"],
        "temperature_2m_max": [36],
        "temperature_2m_min": [23],
        "weathercode": [3],
        "weather_code": [3],
    },
    "official": {"source": "ARPA FVG OSMER"},
    "osmer_structured": {"days": []},
    "source": {"active": "arpa_fvg_osmer"},
    "fallback_used": "open_meteo",
    "primary_source": "arpa_fvg_osmer",
    "model_support": {"open_meteo": True, "daily": True},
    "cache": {"status": "fresh"},
    "data_quality": {"certainty": "official", "status": "fresh"},
}

ALERTS_FIXTURE = {
    "active": False,
    "count": 0,
    "alerts": [],
    "source": {"id": "protezione_civile_fvg_alerts"},
    "source_mode": "official_widget",
    "fetched_at": "2026-08-09T23:00:00+02:00",
    "expires_at": "",
    "cache": {"status": "fresh"},
}

CURRENT_FIXTURE = {
    "city": "Pordenone",
    "temperature": 26,
    "condition": "Poco nuvoloso",
    "weathercode": 1,
    "wind_speed": 4,
    "wind_direction": 180,
    "wind_gusts": 9,
    "cloud_cover": 20,
    "precipitation": 0,
    "rain": 0,
    "showers": 0,
    "snowfall": 0,
    "phrase": "",
    "is_bora": False,
    "humidity": 64,
    "pressure": 1013,
    "feels_like": 28,
    "visibility": 20000,
    "pop": "0%",
    "sunrise": "2026-08-09T06:01",
    "sunset": "2026-08-09T20:28",
    "hourly_next_12h": [{"time": "2026-08-09T23:00", "temperature": 25}],
    "pollen": "Bassi (graminacee)",
    "pollen_data": {"level": "Bassi", "values": {"graminacee": 4}},
    "is_day": 0,
    "source": {"active": "open_meteo"},
    "station": {"station": "Pordenone"},
    "official": {"source": {"id": "arpa_fvg_osmer"}},
    "fallback_used": None,
    "primary_source": "open_meteo",
    "model_support": {"open_meteo": True, "hourly": True, "daily": True},
    "cache": {"status": "fresh"},
    "data_quality": {"certainty": "model", "status": "fresh"},
}

RADAR_FIXTURE = {
    "city": "Pordenone",
    "available": True,
    "mode": "radar_dpc_v2_tiles",
    "status": "fresh",
    "source": {"id": "radar_dpc", "label": "Radar-DPC"},
    "location": {"lat": 45.9567, "lon": 12.6605},
    "products": [
        {
            "id": "rain",
            "product_type": "SRI",
            "layer": "radar:sri",
            "style": "",
            "unit": "mm/h",
            "period": "PT5M",
            "period_minutes": 5,
            "time": "2026-08-10T08:00:00Z",
            "updated_at": "2026-08-10T08:00:00Z",
        }
    ],
    "tiles": {
        "provider": "radar_dpc_v2",
        "base_url": "https://tiles.example.test",
        "format": "webp",
        "tile_size": 256,
        "zoom": 7,
        "encoding": "red_channel_normalized",
    },
    "wms": {
        "url": "https://radar.example.test/wms",
        "version": "1.1.1",
        "crs": "EPSG:3857",
    },
    "links": {"platform": "https://radar.example.test"},
    "generated_at": "2026-08-10T08:01:00Z",
    "message": "Radar observation only.",
}


class FixtureWeatherService:
    def __init__(self):
        self.current_force = None
        self.forecast_force = None
        self.local_pilot_forecast_force = None
        self.alerts_force = None
        self.bootstrap_force = None
        self.radar_force = None

    def get_current(self, *, city, lat, lon, force=False):
        self.current_force = force
        return WeatherCurrentResponse.model_validate({**CURRENT_FIXTURE, "city": city})

    def get_forecast(self, *, city, lat, lon, force=False):
        self.forecast_force = force
        return WeatherForecastResponse.model_validate({**FORECAST_FIXTURE, "city": city})

    def get_local_pilot_forecast(self, *, city, lat, lon, force=False):
        self.local_pilot_forecast_force = force
        return WeatherForecastResponse.model_validate(
            {
                **FORECAST_FIXTURE,
                "city": city,
                "fallback_used": None,
                "model_support": {"open_meteo": False, "daily": False},
            }
        )

    def get_official_alerts(self, *, force=False):
        self.alerts_force = force
        return OfficialAlertsResponse.model_validate(ALERTS_FIXTURE)

    def get_bootstrap(self, *, city, lat, lon, force=False):
        self.bootstrap_force = force
        return WeatherBootstrapResponse.model_validate(
            {
                "city": city,
                "current": {**CURRENT_FIXTURE, "city": city},
                "forecast": {**FORECAST_FIXTURE, "city": city},
                "official_alerts": ALERTS_FIXTURE,
                "cache": {"status": "fresh"},
            }
        )

    def get_radar(self, *, city, lat, lon, force=False):
        self.radar_force = force
        return WeatherRadarResponse.model_validate({**RADAR_FIXTURE, "city": city})


class UnavailableForecastService(FixtureWeatherService):
    def get_forecast(self, *, city, lat, lon, force=False):
        raise WeatherSourceUnavailable("official_forecast_unavailable")


class UnavailableCurrentService(FixtureWeatherService):
    def get_current(self, *, city, lat, lon, force=False):
        raise WeatherSourceUnavailable("current_weather_unavailable")


class WeatherApiTests(unittest.TestCase):
    def create_client(self, service):
        app = create_app()
        app.dependency_overrides[get_weather_service] = lambda: service
        return TestClient(app)

    def test_forecast_contract_and_force_token(self):
        service = FixtureWeatherService()
        response = self.create_client(service).get(
            "/api/weather/forecast",
            params={
                "city": "Pordenone",
                "lat": 45.9567,
                "lon": 12.6605,
                "_": 123,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["primary_source"], "arpa_fvg_osmer")
        self.assertTrue(service.forecast_force)

    def test_current_contract_and_force_token(self):
        service = FixtureWeatherService()
        response = self.create_client(service).get(
            "/api/weather/current",
            params={"city": "Pordenone", "lat": 45.9567, "lon": 12.6605, "_": 123},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["temperature"], 26)
        self.assertEqual(response.json()["hourly_forecast"], [])
        self.assertEqual(response.json()["primary_source"], "open_meteo")
        self.assertTrue(service.current_force)

    def test_local_pilot_rejects_legacy_current_before_loader(self):
        service = FixtureWeatherService()
        with patch.dict(
            os.environ,
            {
                LOCAL_WEATHER_PILOT_ENV: "1",
                OPEN_METEO_ENABLED_ENV: "0",
            },
        ):
            response = self.create_client(service).get(
                "/api/weather/current",
                params={"city": "Pordenone", "lat": 45.9567, "lon": 12.6605},
                headers={
                    "Host": "127.0.0.1:8002",
                    LOCAL_WEATHER_PILOT_HEADER: "1",
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["error"],
            "legacy_current_disabled_for_local_weather_pilot",
        )
        self.assertIsNone(service.current_force)

    def test_bootstrap_contract_and_force_token(self):
        service = FixtureWeatherService()
        response = self.create_client(service).get(
            "/api/weather/bootstrap",
            params={"city": "Pordenone", "lat": 45.9567, "lon": 12.6605, "_": 123},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["current"]["temperature"], 26)
        self.assertEqual(response.json()["current"]["primary_source"], "open_meteo")
        self.assertEqual(response.json()["forecast"]["primary_source"], "arpa_fvg_osmer")
        self.assertEqual(response.json()["official_alerts"]["source_mode"], "official_widget")
        self.assertTrue(service.bootstrap_force)

    def test_local_pilot_rejects_legacy_bootstrap_before_loader(self):
        service = FixtureWeatherService()
        with patch.dict(
            os.environ,
            {
                LOCAL_WEATHER_PILOT_ENV: "1",
                OPEN_METEO_ENABLED_ENV: "0",
            },
        ):
            response = self.create_client(service).get(
                "/api/weather/bootstrap",
                params={"city": "Pordenone", "lat": 45.9567, "lon": 12.6605},
                headers={
                    "Host": "localhost:8002",
                    LOCAL_WEATHER_PILOT_HEADER: "1",
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["error"],
            "legacy_bootstrap_disabled_for_local_weather_pilot",
        )
        self.assertIsNone(service.bootstrap_force)

    def test_local_pilot_forecast_uses_dedicated_osmer_only_loader(self):
        service = FixtureWeatherService()
        with patch.dict(
            os.environ,
            {
                LOCAL_WEATHER_PILOT_ENV: "true",
                OPEN_METEO_ENABLED_ENV: "false",
            },
        ):
            response = self.create_client(service).get(
                "/api/weather/forecast",
                params={
                    "city": "Pordenone",
                    "lat": 45.9567,
                    "lon": 12.6605,
                    "_": 123,
                },
                headers={
                    "Host": "127.0.0.1:8002",
                    LOCAL_WEATHER_PILOT_HEADER: "1",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["model_support"]["open_meteo"])
        self.assertIsNone(service.forecast_force)
        self.assertTrue(service.local_pilot_forecast_force)

    def test_local_pilot_signal_fails_closed_when_backend_is_not_ready(self):
        service = FixtureWeatherService()
        with patch.dict(
            os.environ,
            {
                LOCAL_WEATHER_PILOT_ENV: "1",
                OPEN_METEO_ENABLED_ENV: "1",
            },
        ):
            response = self.create_client(service).get(
                "/api/weather/forecast",
                params={"city": "Pordenone", "lat": 45.9567, "lon": 12.6605},
                headers={
                    "Host": "127.0.0.1:8002",
                    LOCAL_WEATHER_PILOT_HEADER: "1",
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["error"],
            "local_weather_pilot_backend_not_ready",
        )
        self.assertIsNone(service.forecast_force)
        self.assertIsNone(service.local_pilot_forecast_force)

    def test_local_pilot_signal_rejects_non_loopback_host(self):
        service = FixtureWeatherService()
        with patch.dict(
            os.environ,
            {
                LOCAL_WEATHER_PILOT_ENV: "1",
                OPEN_METEO_ENABLED_ENV: "0",
            },
        ):
            response = self.create_client(service).get(
                "/api/weather/forecast",
                params={"city": "Pordenone", "lat": 45.9567, "lon": 12.6605},
                headers={
                    "Host": "pilot.example.test",
                    LOCAL_WEATHER_PILOT_HEADER: "1",
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["error"],
            "local_weather_pilot_requires_loopback_host",
        )
        self.assertIsNone(service.forecast_force)
        self.assertIsNone(service.local_pilot_forecast_force)

    def test_official_alert_contract_and_force_token(self):
        service = FixtureWeatherService()
        response = self.create_client(service).get(
            "/api/weather/official-alerts",
            params={"_": 123},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_mode"], "official_widget")
        self.assertTrue(service.alerts_force)

    def test_local_pilot_header_does_not_change_official_alerts(self):
        service = FixtureWeatherService()
        with patch.dict(
            os.environ,
            {
                LOCAL_WEATHER_PILOT_ENV: "1",
                OPEN_METEO_ENABLED_ENV: "0",
            },
        ):
            response = self.create_client(service).get(
                "/api/weather/official-alerts",
                params={"_": 123},
                headers={
                    "Host": "127.0.0.1:8002",
                    LOCAL_WEATHER_PILOT_HEADER: "1",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_mode"], "official_widget")
        self.assertTrue(service.alerts_force)

    def test_radar_contract_and_force_token(self):
        service = FixtureWeatherService()
        response = self.create_client(service).get(
            "/api/weather/radar",
            params={"city": "Pordenone", "lat": 45.9567, "lon": 12.6605, "_": 123},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["available"])
        self.assertEqual(response.json()["products"][0]["layer"], "radar:sri")
        self.assertEqual(
            response.json()["tiles"]["base_url"],
            "https://tiles.example.test",
        )
        self.assertTrue(service.radar_force)

    def test_unavailable_forecast_is_explicit(self):
        response = self.create_client(UnavailableForecastService()).get(
            "/api/weather/forecast",
            params={"city": "Pordenone"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["error"],
            "official_forecast_unavailable",
        )

    def test_unavailable_current_is_explicit(self):
        response = self.create_client(UnavailableCurrentService()).get(
            "/api/weather/current",
            params={"city": "Pordenone"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["error"],
            "current_weather_unavailable",
        )


if __name__ == "__main__":
    unittest.main()
