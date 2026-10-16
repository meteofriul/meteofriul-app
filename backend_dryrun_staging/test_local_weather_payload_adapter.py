"""Tests for adapting real/saved weather payloads."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "backend_dryrun_staging"
sys.path.insert(0, str(STAGING))

import local_weather_payload_adapter as adapter  # noqa: E402


class LocalWeatherPayloadAdapterTest(unittest.TestCase):
    def test_bootstrap_payload_reports_data_gaps_and_regional_text_signals(self):
        payload = {
            "city": "Pordenone",
            "current": {
                "city": "Pordenone",
                "temperature": 30,
                "feels_like": None,
                "weathercode": None,
                "precipitation": 0,
                "wind_gusts": 8,
                "hourly_next_12h": [],
                "source": {
                    "active": "arpa_fvg_osmer",
                    "primary_source": "arpa_fvg_osmer",
                    "model_support": {"hourly": False},
                },
                "data_quality": {"status": "fresh"},
                "station": {"time": "20:00"},
                "cache": {"generated_at": "2026-06-27T21:19:07"},
            },
            "forecast": {
                "forecast": [
                    {
                        "official_text": "Sara una giornata molto calda in pianura.",
                    }
                ]
            },
            "official_alerts": {"active": False, "alerts": []},
        }

        adapted = adapter.adapt_weather_payload(payload)

        self.assertEqual(adapted["city"], "Pordenone")
        self.assertEqual(adapted["source_shape"], "weather_bootstrap")
        self.assertEqual(adapted["weather"]["temperature"], 30)
        self.assertEqual(adapted["weather"]["observed_at"], "2026-06-27T20:00")
        self.assertEqual(adapted["numeric_snapshot"]["temperature"], 30)
        self.assertIsNone(adapted["numeric_snapshot"]["feels_like"])
        self.assertEqual(adapted["numeric_snapshot"]["hourly_count"], 0)
        self.assertIn("missing_hourly_next_12h", adapted["data_gaps"])
        self.assertIn("hourly_model_support_false", adapted["data_gaps"])
        self.assertEqual(adapted["official_alerts"], [])
        heat_signals = [signal for signal in adapted["text_signals"] if signal["kind"] == "heat"]
        self.assertEqual(len(heat_signals), 1)
        self.assertFalse(heat_signals[0]["used_for_local_push"])

    def test_direct_weather_snapshot_is_preserved(self):
        payload = {
            "city": "Pordenone",
            "weather": {
                "temperature": 24,
                "feels_like": 24,
                "hourly_next_12h": [
                    {
                        "time": "2026-06-27T17:00",
                        "weathercode": 61,
                        "temperature": 24,
                        "precipitation": 1.2,
                        "rain": 1.2,
                        "showers": 0,
                        "precipitation_probability": 75,
                    }
                ],
            },
        }

        adapted = adapter.adapt_weather_payload(payload)

        self.assertEqual(adapted["source_shape"], "direct_weather_snapshot")
        self.assertEqual(adapted["weather"]["hourly_next_12h"][0]["rain"], 1.2)
        self.assertEqual(adapted["numeric_snapshot"]["peak_temperature"], 24)
        self.assertEqual(adapted["numeric_snapshot"]["max_precipitation"], 1.2)
        self.assertEqual(adapted["numeric_snapshot"]["max_probability"], 75)
        self.assertNotIn("missing_hourly_next_12h", adapted["data_gaps"])

    def test_iter_payload_objects_accepts_lists_and_wrapped_payloads(self):
        payloads = [{"city": "Udine"}, {"city": "Pordenone"}]

        self.assertEqual(adapter.iter_payload_objects(payloads), payloads)
        self.assertEqual(adapter.iter_payload_objects({"payloads": payloads}), payloads)


if __name__ == "__main__":
    unittest.main()
