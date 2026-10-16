"""Tests for pure local weather notice detection."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "backend_dryrun_staging"
sys.path.insert(0, str(STAGING))

import local_weather_notice_detector as detector  # noqa: E402


def fixture_weather(*slots, temperature=24.0, feels_like=24.0, **extra):
    return {
        "temperature": temperature,
        "feels_like": feels_like,
        "hourly_next_12h": list(slots),
        **extra,
    }


def slot(time, **extra):
    return {
        "time": time,
        "weathercode": extra.pop("weathercode", 2),
        "temperature": extra.pop("temperature", 24.0),
        "precipitation": extra.pop("precipitation", 0),
        "rain": extra.pop("rain", 0),
        "showers": extra.pop("showers", 0),
        "precipitation_probability": extra.pop("precipitation_probability", 0),
        "wind_gusts": extra.pop("wind_gusts", 10),
        "wind_direction": extra.pop("wind_direction", 180),
        "snowfall": extra.pop("snowfall", 0),
        **extra,
    }


class LocalWeatherNoticeDetectorTest(unittest.TestCase):
    def test_heat_uses_temperature_and_hourly_peak(self):
        notices = detector.detect_local_weather_notices(
            "Pordenone",
            fixture_weather(
                slot("2026-06-27T15:00", temperature=34.5),
                temperature=34.1,
                feels_like=35.2,
                observed_at="2026-06-27T13:00",
            ),
        )

        self.assertEqual(len(notices), 1)
        heat = notices[0]
        self.assertEqual(heat["kind"], "heat")
        self.assertEqual(heat["body"], "Caldo previsto oggi a Pordenone.")
        self.assertEqual(heat["source"], "osmer_station_and_open_meteo_support")
        self.assertEqual(heat["event_at"], "2026-06-27T13:00")
        self.assertEqual(heat["trigger_source"], "current_feels_like")
        self.assertEqual(heat["trigger_value"], 35.2)
        self.assertIn("peak 34.5 C", heat["evidence"])
        self.assertIn("trigger current_feels_like 35.2 C", heat["evidence"])

    def test_heat_uses_hourly_peak_when_current_values_are_below_threshold(self):
        notices = detector.detect_local_weather_notices(
            "Pordenone",
            fixture_weather(
                slot("2026-06-27T15:00", temperature=34.5),
                temperature=30.0,
                feels_like=31.0,
                observed_at="2026-06-27T12:00",
            ),
        )

        self.assertEqual(len(notices), 1)
        heat = notices[0]
        self.assertEqual(heat["kind"], "heat")
        self.assertEqual(heat["event_at"], "2026-06-27T15:00")
        self.assertEqual(heat["trigger_source"], "hourly_temperature")
        self.assertEqual(heat["trigger_value"], 34.5)

    def test_rain_threshold_uses_amount_or_probability(self):
        notices = detector.detect_local_weather_notices(
            "Pordenone",
            fixture_weather(
                slot(
                    "2026-06-27T17:00",
                    weathercode=61,
                    precipitation=1.2,
                    rain=1.2,
                    precipitation_probability=75,
                ),
            ),
        )

        self.assertEqual(len(notices), 1)
        rain = notices[0]
        self.assertEqual(rain["kind"], "rain")
        self.assertEqual(rain["severity"], 2)
        self.assertEqual(rain["body"], "Pioggia prevista verso le 17:00.")
        self.assertIn("rain 1.2 mm", rain["evidence"])

    def test_storm_suppresses_generic_rain_detection(self):
        notices = detector.detect_local_weather_notices(
            "Cividale del Friuli",
            fixture_weather(
                slot(
                    "2026-06-27T18:00",
                    weathercode=95,
                    precipitation=1.4,
                    precipitation_probability=80,
                ),
            ),
        )

        self.assertEqual([notice["kind"] for notice in notices], ["storm"])

    def test_hail_and_snow_are_both_candidates(self):
        notices = detector.detect_local_weather_notices(
            "Tarvisio",
            fixture_weather(
                slot("2026-06-27T18:00", weathercode=96),
                slot("2026-06-27T21:00", weathercode=71, temperature=-1, snowfall=0.4),
                temperature=6,
                feels_like=4,
            ),
        )

        by_kind = {notice["kind"]: notice for notice in notices}
        self.assertIn("hail", by_kind)
        self.assertIn("snow", by_kind)
        self.assertEqual(by_kind["hail"]["severity"], 3)
        self.assertEqual(by_kind["snow"]["event_at"], "2026-06-27T21:00")

    def test_ice_uses_freezing_precipitation_code(self):
        notices = detector.detect_local_weather_notices(
            "Tarvisio",
            fixture_weather(
                slot("2026-01-12T06:00", weathercode=66, temperature=-2),
            ),
        )

        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["kind"], "ice")
        self.assertEqual(notices[0]["category"], "snow")

    def test_bora_requires_wind_threshold_and_exposure(self):
        notices = detector.detect_local_weather_notices(
            "Trieste",
            fixture_weather(
                slot("2026-06-27T21:00", wind_gusts=62, wind_direction=55),
            ),
        )

        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["kind"], "bora")
        self.assertEqual(notices[0]["category"], "wind")

    def test_plain_wind_when_city_is_not_bora_exposed(self):
        notices = detector.detect_local_weather_notices(
            "Pordenone",
            fixture_weather(
                slot("2026-06-27T21:00", wind_gusts=62, wind_direction=55),
            ),
        )

        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["kind"], "wind")

    def test_below_thresholds_returns_no_notice(self):
        notices = detector.detect_local_weather_notices(
            "Udine",
            fixture_weather(
                slot("2026-06-27T15:00", temperature=26, precipitation_probability=15),
                temperature=25,
                feels_like=25.5,
            ),
        )

        self.assertEqual(notices, [])

    def test_official_alert_overlap_uses_matching_risk_text(self):
        notice = {
            "category": "storms",
        }
        official_alerts = [
            {
                "risks": ["temporali"],
                "official_text": "",
            }
        ]

        self.assertTrue(detector.local_notice_suppressed_by_official_alert(notice, official_alerts))


if __name__ == "__main__":
    unittest.main()
