import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import requests

from app.weather import forecast_engine, radar_engine


class FakeJsonResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


def radar_payload(product_type, timestamp=1785741000000):
    return {
        "total": 1,
        "lastProducts": [
            {
                "productType": product_type,
                "time": timestamp,
                "period": "PT5M",
            }
        ],
    }


class WeatherRadarEngineTests(unittest.TestCase):
    def setUp(self):
        radar_engine.clear_radar_cache()

    @patch.object(forecast_engine, "is_fvg_location", return_value=True)
    @patch.object(radar_engine.requests, "get")
    def test_exposes_dpc_products_without_proxying_images(self, requests_get, _is_fvg):
        requests_get.side_effect = [
            FakeJsonResponse(radar_payload("SRI")),
            FakeJsonResponse(radar_payload("SRT1")),
        ]

        result = radar_engine.get_weather_radar(
            "Pordenone",
            45.9567,
            12.6605,
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["status"], "fresh")
        self.assertEqual(result["mode"], "radar_dpc_v2_tiles")
        self.assertEqual(result["source"]["id"], "radar_dpc")
        self.assertEqual(
            result["tiles"]["base_url"],
            radar_engine.RADAR_DPC_TILES_BASE_URL,
        )
        self.assertEqual(result["tiles"]["encoding"], "red_channel_normalized")
        self.assertEqual(result["wms"]["url"], radar_engine.RADAR_DPC_WMS_URL)
        self.assertEqual(
            [product["id"] for product in result["products"]],
            ["rain", "accumulation_1h"],
        )
        self.assertNotIn("frames", result)
        for call in requests_get.call_args_list:
            self.assertEqual(
                call.kwargs["headers"]["Origin"],
                radar_engine.RADAR_DPC_ORIGIN,
            )
            self.assertEqual(
                call.kwargs["headers"]["Referer"],
                radar_engine.RADAR_DPC_REFERER,
            )

    @patch.object(forecast_engine, "is_fvg_location", return_value=True)
    @patch.object(radar_engine.requests, "get")
    def test_keeps_available_product_when_optional_product_fails(
        self,
        requests_get,
        _is_fvg,
    ):
        requests_get.side_effect = [
            FakeJsonResponse(radar_payload("SRI")),
            requests.RequestException("accumulation offline"),
        ]

        result = radar_engine.get_weather_radar("Pordenone", 45.9567, 12.6605)

        self.assertTrue(result["available"])
        self.assertEqual([product["id"] for product in result["products"]], ["rain"])

    @patch.object(forecast_engine, "is_fvg_location", return_value=True)
    @patch.object(
        radar_engine,
        "fetch_radar_dpc_metadata",
        side_effect=requests.RequestException("offline"),
    )
    def test_uses_stale_metadata_when_refresh_fails(self, _fetch, _is_fvg):
        metadata = {
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
            ]
        }
        radar_engine.radar_cache[radar_engine.RADAR_CACHE_KEY] = (
            metadata,
            datetime.now() - timedelta(minutes=10),
        )

        result = radar_engine.get_weather_radar(
            "Udine",
            46.0635,
            13.2358,
            force=True,
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["products"], metadata["products"])

    @patch.object(forecast_engine, "is_fvg_location", return_value=True)
    @patch.object(
        radar_engine,
        "fetch_radar_dpc_metadata",
        side_effect=requests.RequestException("offline"),
    )
    def test_does_not_serve_radar_metadata_older_than_thirty_minutes(
        self,
        _fetch,
        _is_fvg,
    ):
        radar_engine.radar_cache[radar_engine.RADAR_CACHE_KEY] = (
            {"products": [{"id": "rain"}]},
            datetime.now() - timedelta(minutes=31),
        )

        result = radar_engine.get_weather_radar(
            "Udine",
            46.0635,
            13.2358,
            force=True,
        )

        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "unavailable")

    @patch.object(forecast_engine, "is_fvg_location", return_value=True)
    @patch.object(
        radar_engine,
        "fetch_radar_dpc_metadata",
        side_effect=requests.RequestException("offline"),
    )
    def test_failure_does_not_fall_back_to_forecast_or_alerts(self, _fetch, _is_fvg):
        result = radar_engine.get_weather_radar("Gorizia", 45.94, 13.62)

        self.assertFalse(result["available"])
        self.assertEqual(result["mode"], "radar_temporarily_unavailable")
        self.assertEqual(result["source"]["id"], "radar_dpc")
        self.assertEqual(result["products"], [])

    @patch.object(forecast_engine, "is_fvg_location", return_value=False)
    def test_outside_fvg_is_explicitly_unavailable(self, _is_fvg):
        result = radar_engine.get_weather_radar("Venezia", 45.44, 12.33)

        self.assertFalse(result["available"])
        self.assertEqual(result["mode"], "not_available_outside_fvg")


if __name__ == "__main__":
    unittest.main()
