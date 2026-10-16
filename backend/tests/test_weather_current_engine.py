import os
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.weather import current_engine, forecast_engine
from app.infrastructure.open_meteo_policy import OPEN_METEO_ENABLED_ENV


OPEN_METEO_FIXTURE = {
    "timezone": "Europe/Rome",
    "utc_offset_seconds": 7200,
    "current": {
        "temperature_2m": 24.4,
        "relative_humidity_2m": 70,
        "apparent_temperature": 25.1,
        "pressure_msl": 1012.2,
        "cloud_cover": 25,
        "wind_speed_10m": 7.2,
        "wind_direction_10m": 180,
        "wind_gusts_10m": 12.1,
        "precipitation": 0,
        "rain": 0,
        "showers": 0,
        "snowfall": 0,
        "visibility": 20000,
        "weather_code": 1,
        "is_day": 1,
    },
    "hourly": {
        "time": ["2099-01-01T12:00"],
        "temperature_2m": [25],
        "precipitation_probability": [10],
        "weather_code": [1],
        "wind_speed_10m": [8],
        "wind_gusts_10m": [13],
    },
    "daily": {
        "precipitation_probability_max": [10],
        "sunrise": ["2099-01-01T07:00"],
        "sunset": ["2099-01-01T17:00"],
    },
}

POLLEN_FIXTURE = {
    "summary": "Bassi (graminacee)",
    "level": "Bassi",
    "main": "graminacee",
    "values": {"graminacee": 4},
}


class CurrentWeatherEngineTests(unittest.TestCase):
    def setUp(self):
        self.open_meteo_override = patch.dict(
            os.environ,
            {OPEN_METEO_ENABLED_ENV: "1"},
        )
        self.open_meteo_override.start()
        self.addCleanup(self.open_meteo_override.stop)
        current_engine.clear_current_weather_caches()

    def test_hourly_evolution_uses_open_meteo_local_hour_and_explicit_offset(self):
        first_hour = datetime(2026, 8, 18, 18, 0)
        times = [
            (first_hour + timedelta(hours=index)).isoformat(timespec="minutes")
            for index in range(16)
        ]
        hourly = {
            "time": times,
            "temperature_2m": list(range(len(times))),
        }

        result = current_engine.build_hourly_next_12h(
            hourly,
            timezone_name="Europe/Rome",
            utc_offset_seconds=7200,
            now=datetime(2026, 8, 18, 18, 18, tzinfo=timezone.utc),
        )

        self.assertEqual(len(result), 12)
        self.assertEqual(result[0]["time"], "2026-08-18T20:00+02:00")
        self.assertEqual(result[0]["temperature"], 2)
        self.assertEqual(result[-1]["time"], "2026-08-19T07:00+02:00")

    def test_hourly_forecast_can_keep_a_48_hour_cache_reservoir(self):
        first_hour = datetime(2026, 8, 18, 18, 0)
        times = [
            (first_hour + timedelta(hours=index)).isoformat(timespec="minutes")
            for index in range(60)
        ]

        result = current_engine.build_hourly_forecast(
            {"time": times, "temperature_2m": list(range(len(times)))},
            limit=current_engine.HOURLY_FORECAST_RESERVOIR_HOURS,
            timezone_name="Europe/Rome",
            utc_offset_seconds=7200,
            now=datetime(2026, 8, 18, 18, 18, tzinfo=timezone.utc),
        )

        self.assertEqual(len(result), 48)
        self.assertEqual(result[0]["time"], "2026-08-18T20:00+02:00")
        self.assertEqual(result[-1]["time"], "2026-08-20T19:00+02:00")

    def test_hourly_evolution_uses_winter_offset(self):
        hourly = {
            "time": ["2026-01-14T19:00", "2026-01-14T20:00", "2026-01-14T21:00"],
        }

        result = current_engine.build_hourly_next_12h(
            hourly,
            timezone_name="Europe/Rome",
            utc_offset_seconds=3600,
            now=datetime(2026, 1, 14, 19, 18, tzinfo=timezone.utc),
        )

        self.assertEqual(
            [item["time"] for item in result],
            ["2026-01-14T20:00+01:00", "2026-01-14T21:00+01:00"],
        )

    def test_hourly_evolution_preserves_dst_transition_offsets(self):
        spring = current_engine.build_hourly_next_12h(
            {"time": ["2026-03-29T01:00", "2026-03-29T03:00", "2026-03-29T04:00"]},
            timezone_name="Europe/Rome",
            utc_offset_seconds=3600,
            now=datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc),
        )
        autumn = current_engine.build_hourly_next_12h(
            {
                "time": [
                    "2026-10-25T01:00",
                    "2026-10-25T02:00",
                    "2026-10-25T02:00",
                    "2026-10-25T03:00",
                ],
            },
            timezone_name="Europe/Rome",
            utc_offset_seconds=7200,
            now=datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc),
        )
        autumn_second_hour = current_engine.build_hourly_next_12h(
            {
                "time": [
                    "2026-10-25T01:00",
                    "2026-10-25T02:00",
                    "2026-10-25T02:00",
                    "2026-10-25T03:00",
                ],
            },
            timezone_name="Europe/Rome",
            utc_offset_seconds=3600,
            now=datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(
            [item["time"] for item in spring],
            ["2026-03-29T01:00+01:00", "2026-03-29T03:00+02:00", "2026-03-29T04:00+02:00"],
        )
        self.assertEqual(
            [item["time"] for item in autumn],
            [
                "2026-10-25T02:00+02:00",
                "2026-10-25T02:00+01:00",
                "2026-10-25T03:00+01:00",
            ],
        )
        self.assertEqual(
            [item["time"] for item in autumn_second_hour],
            ["2026-10-25T02:00+01:00", "2026-10-25T03:00+01:00"],
        )

    @patch.object(current_engine, "get_pollen_data", return_value=POLLEN_FIXTURE)
    @patch.object(forecast_engine, "open_meteo_forecast", return_value=OPEN_METEO_FIXTURE)
    @patch.object(forecast_engine, "get_osmer_official_weather")
    def test_open_meteo_supplies_current_values_while_osmer_stays_separate(
        self,
        osmer_loader,
        _model_loader,
        _pollen_loader,
    ):
        osmer_loader.return_value = {
            "station": {
                "station": "Pordenone",
                "station_scope": "exact",
                "station_distance_km": 0,
                "temperature": 26.3,
                "humidity": 64,
                "wind_speed": 2,
                "wind_gusts": 5,
                "precipitation": 0,
                "pressure": 1012.6,
                "condition": "nuvoloso",
            },
            "it": {"forecasts": []},
        }

        result = current_engine.get_real_current_weather(
            "Pordenone",
            45.9567,
            12.6605,
        )

        self.assertEqual(result["temperature"], 24)
        self.assertEqual(result["feels_like"], 25)
        self.assertEqual(result["humidity"], 70)
        self.assertEqual(result["wind_speed"], 7)
        self.assertEqual(result["wind_gusts"], 12)
        self.assertEqual(result["pressure"], 1012)
        self.assertEqual(result["condition"], "Poco nuvoloso")
        self.assertEqual(result["weathercode"], 1)
        self.assertEqual(result["primary_source"], "open_meteo")
        self.assertIsNone(result["fallback_used"])
        self.assertEqual(result["data_quality"]["certainty"], "model")
        self.assertEqual(result["data_quality"]["source"], "open_meteo")
        self.assertEqual(result["source"]["active"], "open_meteo")
        self.assertEqual(result["source"]["current_policy"], current_engine.CURRENT_WEATHER_POLICY)
        self.assertEqual(result["station"], osmer_loader.return_value["station"])
        self.assertEqual(result["official"], osmer_loader.return_value)
        _model_loader.assert_called_once_with(45.9567, 12.6605, forecast_engine.WEATHER_REQUEST_TIMEOUT)
        self.assertEqual(result["source"]["station_scope"], "exact")
        self.assertEqual(result["hourly_next_12h"][0]["temperature"], 25)
        self.assertEqual(result["hourly_forecast"][0]["temperature"], 25)
        self.assertEqual(result["pollen_data"]["level"], "Bassi")

    @patch.object(current_engine, "get_pollen_data", return_value=POLLEN_FIXTURE)
    @patch.object(forecast_engine, "open_meteo_forecast", return_value=OPEN_METEO_FIXTURE)
    @patch.object(forecast_engine, "get_osmer_official_weather", return_value=None)
    def test_model_only_location_is_declared_as_open_meteo(
        self,
        _osmer_loader,
        _model_loader,
        _pollen_loader,
    ):
        result = current_engine.get_real_current_weather("Venezia", 45.44, 12.33)

        self.assertEqual(result["temperature"], 24)
        self.assertEqual(result["condition"], "Poco nuvoloso")
        self.assertEqual(result["primary_source"], "open_meteo")
        self.assertIsNone(result["fallback_used"])
        self.assertFalse(result["source"]["is_fvg"])

    @patch.object(forecast_engine, "open_meteo_forecast", side_effect=OSError("offline"))
    @patch.object(forecast_engine, "get_osmer_official_weather", return_value=None)
    def test_missing_verified_sources_returns_none(self, _osmer_loader, _model_loader):
        result = current_engine.get_real_current_weather("Venezia", 45.44, 12.33)

        self.assertIsNone(result)

    @patch.object(forecast_engine, "open_meteo_forecast", side_effect=OSError("offline"))
    @patch.object(forecast_engine, "get_osmer_official_weather")
    def test_missing_model_does_not_substitute_station_or_bulletin(self, osmer_loader, _model_loader):
        osmer_loader.return_value = {
            "station": {"temperature": 30, "condition": "sereno"},
            "it": {"forecasts": [{"text": "Cielo sereno."}]},
        }

        self.assertIsNone(current_engine.get_real_current_weather("Udine", 46.06, 13.23))

    @patch.object(current_engine, "get_pollen_data", return_value=POLLEN_FIXTURE)
    @patch.object(forecast_engine, "open_meteo_forecast")
    @patch.object(forecast_engine, "get_osmer_official_weather")
    def test_partial_model_never_borrows_missing_values_from_osmer(
        self, osmer_loader, model_loader, _pollen_loader,
    ):
        model_loader.return_value = deepcopy(OPEN_METEO_FIXTURE)
        model_loader.return_value["current"].update({
            "temperature_2m": None, "apparent_temperature": None, "weather_code": 0,
        })
        osmer_loader.return_value = {
            "station": {"temperature": 30, "condition": "temporale", "precipitation": 20},
            "it": {"forecasts": [{"text": "Temporali forti."}]},
        }

        result = current_engine.get_real_current_weather("Udine", 46.06, 13.23)

        self.assertIsNone(result["temperature"])
        self.assertIsNone(result["feels_like"])
        self.assertEqual(result["weathercode"], 0)
        self.assertEqual(result["condition"], "Soleggiato")
        self.assertEqual(result["precipitation"], 0)
        self.assertEqual(result["official"], osmer_loader.return_value)

    @patch.object(current_engine, "get_pollen_data", return_value=POLLEN_FIXTURE)
    @patch.object(forecast_engine, "open_meteo_forecast", return_value=OPEN_METEO_FIXTURE)
    @patch.object(forecast_engine, "get_osmer_official_weather", return_value=None)
    def test_model_outage_reuses_only_verified_model_cache_as_stale(
        self, _osmer_loader, model_loader, _pollen_loader,
    ):
        fresh = current_engine.get_real_current_weather("Udine", 46.06, 13.23)
        key = next(iter(current_engine.weather_cache))
        current_engine.weather_cache[key] = (
            fresh, datetime.now() - timedelta(seconds=current_engine.WEATHER_CURRENT_CACHE_TTL + 1),
        )
        model_loader.side_effect = OSError("offline")

        stale = current_engine.get_real_current_weather("Udine", 46.06, 13.23)

        self.assertEqual(stale["temperature"], 24)
        self.assertEqual(stale["feels_like"], 25)
        self.assertEqual(stale["primary_source"], "open_meteo")
        self.assertEqual(stale["cache"]["status"], "stale")
        self.assertEqual(stale["data_quality"]["status"], "stale")

    @patch.object(forecast_engine, "open_meteo_forecast", side_effect=OSError("offline"))
    @patch.object(forecast_engine, "get_osmer_official_weather", return_value=None)
    def test_old_mixed_cache_cannot_be_reused_as_open_meteo(self, _osmer_loader, _model_loader):
        legacy_key = forecast_engine.make_cache_key(
            forecast_engine.WEATHER_PIPELINE_VERSION, "current", "Udine", 46.06, 13.23,
        )
        forecast_engine.set_cache(current_engine.weather_cache, legacy_key, {
            "temperature": 30, "primary_source": "arpa_fvg_osmer",
        })

        self.assertIsNone(current_engine.get_real_current_weather("Udine", 46.06, 13.23))


if __name__ == "__main__":
    unittest.main()
