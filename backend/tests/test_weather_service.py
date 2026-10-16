import unittest

from app.services.weather import WeatherService
from tests.test_weather_api import ALERTS_FIXTURE, CURRENT_FIXTURE, FORECAST_FIXTURE, RADAR_FIXTURE


class WeatherServiceTests(unittest.TestCase):
    def test_local_pilot_forecast_uses_only_the_dedicated_loader(self):
        calls = []
        service = WeatherService(
            forecast_loader=lambda city, lat, lon: calls.append("default"),
            local_pilot_forecast_loader=lambda city, lat, lon: (
                calls.append("osmer-only") or {
                    **FORECAST_FIXTURE,
                    "city": city,
                    "fallback_used": None,
                    "model_support": {"open_meteo": False, "daily": False},
                }
            ),
        )

        response = service.get_local_pilot_forecast(
            city="Pordenone",
            lat=45.9567,
            lon=12.6605,
        )

        self.assertEqual(calls, ["osmer-only"])
        self.assertEqual(response.primary_source, "arpa_fvg_osmer")
        self.assertFalse(response.model_support["open_meteo"])

    def test_bootstrap_force_is_forwarded_to_alert_state_loader(self):
        alert_forces = []
        service = WeatherService(
            current_loader=lambda city, lat, lon: {**CURRENT_FIXTURE, "city": city},
            forecast_loader=lambda city, lat, lon: {**FORECAST_FIXTURE, "city": city},
            alerts_loader=lambda *, force=False: (
                alert_forces.append(force) or ALERTS_FIXTURE
            ),
            radar_loader=lambda city, lat, lon, force=False: {
                **RADAR_FIXTURE,
                "city": city,
            },
        )

        response = service.get_bootstrap(
            city="Pordenone",
            lat=45.9567,
            lon=12.6605,
            force=True,
        )

        self.assertEqual(response.city, "Pordenone")
        self.assertEqual(response.current.primary_source, "open_meteo")
        self.assertEqual(response.forecast.primary_source, "arpa_fvg_osmer")
        self.assertEqual(response.forecast.official, FORECAST_FIXTURE["official"])
        self.assertEqual(response.official_alerts.source, ALERTS_FIXTURE["source"])
        self.assertEqual(response.official_alerts.source_mode, "official_widget")
        self.assertEqual(alert_forces, [True])


if __name__ == "__main__":
    unittest.main()
