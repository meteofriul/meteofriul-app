import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app.infrastructure.open_meteo_policy import (
    OPEN_METEO_ENABLED_ENV,
    OpenMeteoDisabled,
)
from app.weather import forecast_engine


class ForecastEngineTests(unittest.TestCase):
    def setUp(self):
        forecast_engine.clear_weather_caches()

    def tearDown(self):
        forecast_engine.clear_weather_caches()

    def test_valvasone_arzene_resolves_without_client_coordinates(self):
        self.assertEqual(
            forecast_engine.geocode_city("Valvasone Arzene"),
            (45.99648, 12.85846),
        )

        station = forecast_engine.resolve_osmer_station_context("Valvasone Arzene")

        self.assertEqual(station["station"], "Codroipo")
        self.assertEqual(station["scope"], "mapped")
        self.assertEqual(station["reason"], "curated_fvg_locality_station_map")

    def test_all_fvg_municipalities_have_local_coordinates_for_osmer_only_mode(self):
        self.assertEqual(len(forecast_engine.FVG_MUNICIPALITY_COORDS), 215)
        with (
            patch.dict(os.environ, {OPEN_METEO_ENABLED_ENV: "0"}),
            patch.object(forecast_engine.requests, "get") as request_get,
        ):
            coordinates = forecast_engine.geocode_city(
                "Aiello del Friuli",
                allow_open_meteo=False,
            )

        self.assertEqual(coordinates, (45.87276, 13.36038))
        request_get.assert_not_called()

    def test_fvg_source_detection_uses_the_administrative_boundary_when_coordinates_exist(self):
        self.assertTrue(
            forecast_engine.is_fvg_location("Pordenone", 45.9567, 12.6605)
        )
        self.assertFalse(
            forecast_engine.is_fvg_location("Gorizia", 45.956, 13.648)
        )

    def test_disabled_provider_blocks_forecast_before_cache_or_network(self):
        forecast_engine.set_cache(
            forecast_engine.open_meteo_raw_cache,
            forecast_engine.make_cache_key(
                "open-meteo-forecast",
                round(45.9567, 4),
                round(12.6605, 4),
            ),
            {"daily": {"time": ["cached"]}},
        )

        with (
            patch.dict(os.environ, {OPEN_METEO_ENABLED_ENV: "0"}),
            patch.object(forecast_engine.requests, "get") as request_get,
        ):
            with self.assertRaises(OpenMeteoDisabled):
                forecast_engine.open_meteo_forecast(45.9567, 12.6605)

        request_get.assert_not_called()

    def test_osmer_remains_primary_when_open_meteo_supports_temperatures(self):
        today = datetime.now().date()
        tomorrow = (today + timedelta(days=1)).isoformat()
        day_after = (today + timedelta(days=2)).isoformat()
        official = {
            "source": "ARPA FVG OSMER",
            "station": {"station": "Pordenone", "station_scope": "exact"},
            "it": {"forecasts": []},
            "fur": {"forecasts": []},
        }
        open_meteo = {
            "daily": {
                "time": [today.isoformat(), tomorrow, day_after],
                "temperature_2m_max": [33.0, 34.2, 35.1],
                "temperature_2m_min": [21.0, 22.1, 23.2],
                "weather_code": [0, 1, 2],
            }
        }

        with (
            patch.object(
                forecast_engine,
                "get_osmer_official_weather",
                return_value=official,
            ),
            patch.object(
                forecast_engine,
                "fetch_osmer_structured_forecast",
                return_value=None,
            ),
            patch.object(
                forecast_engine,
                "complete_osmer_structured_with_official_projections",
                return_value=None,
            ),
            patch.object(
                forecast_engine,
                "open_meteo_forecast",
                return_value=open_meteo,
            ),
        ):
            payload = forecast_engine.get_real_forecast(
                "Pordenone",
                45.9567,
                12.6605,
            )

        self.assertEqual(payload["primary_source"], "arpa_fvg_osmer")
        self.assertEqual(payload["fallback_used"], "open_meteo")
        self.assertEqual(payload["forecast"][0]["date"], tomorrow)
        self.assertEqual(payload["forecast"][0]["max_temp"], 34)
        self.assertEqual(payload["data_quality"]["certainty"], "official")

    def test_osmer_only_forecast_never_calls_open_meteo_and_has_separate_cache(self):
        tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
        official = {
            "source": forecast_engine.OSMER_SOURCE,
            "station": {"station": "Pordenone", "station_scope": "exact"},
            "it": {
                "forecasts": [
                    {
                        "date": tomorrow,
                        "date_source": "official_label",
                        "date_label": "Domani",
                        "text": "Cielo sereno.",
                        "emission": "oggi",
                    }
                ]
            },
            "fur": {"forecasts": []},
        }

        with (
            patch.object(
                forecast_engine,
                "get_osmer_official_weather",
                return_value=official,
            ),
            patch.object(
                forecast_engine,
                "fetch_osmer_structured_forecast",
                return_value=None,
            ),
            patch.object(
                forecast_engine,
                "complete_osmer_structured_with_official_projections",
                return_value=None,
            ),
            patch.object(
                forecast_engine,
                "open_meteo_forecast",
                side_effect=AssertionError("Open-Meteo must stay off"),
            ) as open_meteo_loader,
        ):
            payload = forecast_engine.get_osmer_only_forecast(
                "Pordenone",
                45.9567,
                12.6605,
            )

        open_meteo_loader.assert_not_called()
        self.assertEqual(payload["primary_source"], "arpa_fvg_osmer")
        self.assertIsNone(payload["fallback_used"])
        self.assertEqual(payload["model_support"]["open_meteo"], False)
        self.assertEqual(
            [source["id"] for source in payload["source"]["priority"]],
            ["arpa_fvg_osmer"],
        )
        self.assertNotIn("open_meteo_date", {
            item.get("date_source") for item in payload["forecast"]
        })
        self.assertTrue(any("osmer-only" in key for key in forecast_engine.forecast_cache))

    def test_merge_osmer_structured_snapshots_carries_emission_metadata_per_day(self):
        snapshots = [
            {
                "id_emissione": "PW26091706",
                "data_emissione": "2026-09-17T06:00:00Z",
                "published_at": "2026-09-17T06:00:00Z",
                "updated_at": "2026-09-17T06:23:00Z",
                "raw_hash": "newer-hash",
                "source_date": "2026-09-17",
                "source_url": "https://example.test/PW26091706.xml",
                "requested_date": "2026-09-17",
                "days": [
                    {
                        "valid_date": "2026-09-18",
                        "areas9": {"A5": {"condition": "rain"}},
                    }
                ],
            },
            {
                "id_emissione": "PW26091606",
                "data_emissione": "2026-09-16T06:00:00Z",
                "published_at": "2026-09-16T06:00:00Z",
                "updated_at": "2026-09-16T06:19:00Z",
                "raw_hash": "older-hash",
                "source_date": "2026-09-16",
                "source_url": "https://example.test/PW26091606.xml",
                "requested_date": "2026-09-17",
                "days": [
                    {
                        "valid_date": "2026-09-17",
                        "areas9": {"A5": {"condition": "cloudy"}},
                    }
                ],
            },
        ]

        merged = forecast_engine.merge_osmer_structured_snapshots(
            snapshots,
            requested_date="2026-09-17",
        )

        self.assertIsNotNone(merged)
        sources_by_date = {
            day["valid_date"]: day["osmer_structured_source"]
            for day in merged["days"]
        }
        self.assertEqual(
            sources_by_date["2026-09-17"],
            {
                "id_emissione": "PW26091606",
                "data_emissione": "2026-09-16T06:00:00Z",
                "published_at": "2026-09-16T06:00:00Z",
                "updated_at": "2026-09-16T06:19:00Z",
                "raw_hash": "older-hash",
                "source_url": "https://example.test/PW26091606.xml",
                "source_date": "2026-09-16",
                "requested_date": "2026-09-17",
                "source_status": None,
                "is_stale": None,
                "stale_reason": None,
                "parser_version": None,
                "schema_version": None,
            },
        )
        self.assertEqual(
            sources_by_date["2026-09-18"]["data_emissione"],
            "2026-09-17T06:00:00Z",
        )
        self.assertEqual(
            sources_by_date["2026-09-18"]["published_at"],
            "2026-09-17T06:00:00Z",
        )
        self.assertEqual(
            sources_by_date["2026-09-18"]["updated_at"],
            "2026-09-17T06:23:00Z",
        )
        self.assertEqual(sources_by_date["2026-09-18"]["raw_hash"], "newer-hash")

    def test_merge_osmer_structured_snapshots_keeps_newest_duplicate_day_and_metadata(self):
        snapshots = [
            {
                "id_emissione": "PW26091606",
                "data_emissione": "2026-09-16T06:00:00Z",
                "published_at": "2026-09-16T06:00:00Z",
                "updated_at": "2026-09-16T06:19:00Z",
                "raw_hash": "older-hash",
                "source_date": "2026-09-16",
                "days": [
                    {
                        "valid_date": "2026-09-18",
                        "areas9": {"A5": {"condition": "cloudy"}},
                    }
                ],
            },
            {
                "id_emissione": "PW26091706",
                "data_emissione": "2026-09-17T06:00:00Z",
                "published_at": "2026-09-17T06:00:00Z",
                "updated_at": "2026-09-17T06:23:00Z",
                "raw_hash": "newer-hash",
                "source_date": "2026-09-17",
                "days": [
                    {
                        "valid_date": "2026-09-18",
                        "areas9": {"A5": {"condition": "rain"}},
                    }
                ],
            },
        ]

        merged = forecast_engine.merge_osmer_structured_snapshots(
            snapshots,
            requested_date="2026-09-17",
        )

        self.assertEqual(merged["days"][0]["areas9"]["A5"]["condition"], "rain")
        self.assertEqual(
            merged["days"][0]["osmer_structured_source"],
            {
                "id_emissione": "PW26091706",
                "data_emissione": "2026-09-17T06:00:00Z",
                "published_at": "2026-09-17T06:00:00Z",
                "updated_at": "2026-09-17T06:23:00Z",
                "raw_hash": "newer-hash",
                "source_url": None,
                "source_date": "2026-09-17",
                "requested_date": None,
                "source_status": None,
                "is_stale": None,
                "stale_reason": None,
                "parser_version": None,
                "schema_version": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
