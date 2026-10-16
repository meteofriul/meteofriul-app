"""Tests for dry-running local notices from real/saved payloads."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "backend_dryrun_staging"
sys.path.insert(0, str(STAGING))

import local_weather_real_payload_dryrun as real_dryrun  # noqa: E402


def direct_payload(city: str, *slots, **weather_extra):
    return {
        "city": city,
        "weather": {
            "temperature": weather_extra.pop("temperature", 24),
            "feels_like": weather_extra.pop("feels_like", 24),
            "hourly_next_12h": list(slots),
            **weather_extra,
        },
    }


def slot(time: str, **extra):
    return {
        "time": time,
        "weathercode": extra.pop("weathercode", 2),
        "temperature": extra.pop("temperature", 24),
        "precipitation": extra.pop("precipitation", 0),
        "rain": extra.pop("rain", 0),
        "showers": extra.pop("showers", 0),
        "precipitation_probability": extra.pop("precipitation_probability", 0),
        "wind_gusts": extra.pop("wind_gusts", 10),
        "wind_direction": extra.pop("wind_direction", 180),
        "snowfall": extra.pop("snowfall", 0),
        **extra,
    }


class LocalWeatherRealPayloadDryRunTest(unittest.TestCase):
    def test_build_city_url_encodes_city_name(self):
        url = real_dryrun.build_city_url(
            "http://127.0.0.1:5173/api/weather/bootstrap",
            "Lignano Sabbiadoro",
        )

        self.assertEqual(
            url,
            "http://127.0.0.1:5173/api/weather/bootstrap?city=Lignano+Sabbiadoro",
        )

    def test_build_city_url_preserves_existing_query(self):
        url = real_dryrun.build_city_url(
            "http://127.0.0.1:5173/api/weather/bootstrap?lang=it",
            "Cividale del Friuli",
        )

        self.assertEqual(
            url,
            "http://127.0.0.1:5173/api/weather/bootstrap?lang=it&city=Cividale+del+Friuli",
        )

    def test_regional_text_signal_does_not_create_local_notice_without_numeric_threshold(self):
        payload = {
            "city": "Pordenone",
            "current": {
                "city": "Pordenone",
                "temperature": 30,
                "feels_like": None,
                "weathercode": None,
                "hourly_next_12h": [],
                "source": {"model_support": {"hourly": False}},
            },
            "forecast": {
                "forecast": [
                    {"official_text": "Fara molto caldo, specie in pianura e nelle valli."}
                ]
            },
        }

        report = real_dryrun.build_report_from_payloads([payload])
        item = report["payloads"][0]

        self.assertEqual(report["summary"]["payloads"], 1)
        self.assertEqual(report["summary"]["candidate_notices"], 0)
        self.assertEqual(report["summary"]["dry_run_notifiable"], 0)
        self.assertEqual(item["status"], "no_notice")
        self.assertEqual(item["numeric_snapshot"]["temperature"], 30)
        self.assertIn("missing_hourly_next_12h", item["data_gaps"])
        self.assertEqual(item["notices"], [])
        self.assertEqual(item["text_signals"][0]["kind"], "heat")
        self.assertFalse(item["text_signals"][0]["used_for_local_push"])

    def test_direct_payload_can_generate_local_rain_notice(self):
        report = real_dryrun.build_report_from_payloads([
            direct_payload(
                "Pordenone",
                slot(
                    "2026-06-27T17:00",
                    weathercode=61,
                    precipitation=1.2,
                    rain=1.2,
                    precipitation_probability=75,
                ),
            )
        ])
        item = report["payloads"][0]
        by_kind = {notice["kind"]: notice for notice in item["notices"]}

        self.assertEqual(report["summary"]["candidate_notices"], 1)
        self.assertEqual(report["summary"]["dry_run_notifiable"], 1)
        self.assertEqual(item["status"], "ready")
        self.assertTrue(by_kind["rain"]["can_notify"])
        self.assertEqual(by_kind["rain"]["body"], "Pioggia prevista a Pordenone verso le 17:00.")

    def test_current_feels_like_heat_uses_observed_time_not_future_hourly_slot(self):
        report = real_dryrun.build_report_from_payloads([
            direct_payload(
                "Pordenone",
                slot("2026-06-27T22:00", temperature=28.7),
                temperature=30,
                feels_like=34,
                observed_at="2026-06-27T20:00",
            )
        ])
        notice = report["payloads"][0]["notices"][0]

        self.assertEqual(notice["kind"], "heat")
        self.assertEqual(notice["trigger_source"], "current_feels_like")
        self.assertEqual(notice["trigger_value"], 34)
        self.assertEqual(notice["event_at"], "2026-06-27T20:00")
        self.assertIn("trigger current_feels_like 34 C", notice["evidence"])

    def test_official_alert_suppresses_matching_storm_notice(self):
        payload = direct_payload(
            "Cividale del Friuli",
            slot("2026-06-27T20:00", weathercode=95),
        )
        payload["official_alerts"] = {
            "active": True,
            "alerts": [
                {
                    "risks": ["temporali"],
                    "official_text": "Possibili temporali forti.",
                }
            ],
        }

        report = real_dryrun.build_report_from_payloads([payload])
        notice = report["payloads"][0]["notices"][0]

        self.assertEqual(notice["kind"], "storm")
        self.assertEqual(notice["status"], "suppressed_by_official_alert")
        self.assertFalse(notice["can_notify"])

    def test_text_report_shows_data_gaps(self):
        report = real_dryrun.build_report_from_payloads([
            {
                "city": "Pordenone",
                "current": {
                    "city": "Pordenone",
                    "temperature": 30,
                    "hourly_next_12h": [],
                },
                "forecast": {"forecast": [{"official_text": "Molto caldo in pianura."}]},
            }
        ])
        text = real_dryrun.format_text_report(report)

        self.assertIn("Sintesi: payload=1", text)
        self.assertIn("numeri locali: temp=30.0 C", text)
        self.assertIn("gap dati: missing_hourly_next_12h", text)
        self.assertIn("segnali testuali regionali non usati per push", text)
        self.assertIn("notifiche locali: nessuna", text)


if __name__ == "__main__":
    unittest.main()
