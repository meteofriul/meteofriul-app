"""Tests for local weather notice candidate normalization."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "backend_dryrun_staging"
sys.path.insert(0, str(STAGING))

import local_weather_notice_normalizer as normalizer  # noqa: E402


class LocalWeatherNoticeNormalizerTest(unittest.TestCase):
    def test_known_body_without_city_is_normalized(self):
        candidate = normalizer.normalize_notice_candidate(
            {
                "kind": "rain",
                "category": "rain",
                "city": "Pordenone",
                "starts_at": "2026-06-27T17:00",
                "body": "Pioggia prevista verso le 17:00.",
                "source": "open_meteo_model_support",
            },
            event_at="2026-06-27T17:00",
        )

        self.assertEqual(candidate["state"], "ready")
        self.assertEqual(candidate["body"], "Pioggia prevista a Pordenone verso le 17:00.")
        self.assertEqual(candidate["copy_normalizations"], ["inserted_city"])
        self.assertTrue(candidate["candidate_can_notify"])

    def test_unknown_body_without_city_is_rejected(self):
        candidate = normalizer.normalize_notice_candidate(
            {
                "kind": "rain",
                "category": "rain",
                "city": "Pordenone",
                "starts_at": "2026-06-27T17:00",
                "body": "Precipitazioni in aumento nel pomeriggio.",
                "source": "open_meteo_model_support",
            },
            event_at="2026-06-27T17:00",
        )

        self.assertEqual(candidate["state"], "invalid_candidate")
        self.assertIn("body_missing_city", candidate["validation_errors"])
        self.assertFalse(candidate["candidate_can_notify"])

    def test_macro_location_is_rejected(self):
        candidate = normalizer.normalize_notice_candidate(
            {
                "kind": "storm",
                "category": "storms",
                "city": "monti",
                "starts_at": "2026-06-27T18:00",
                "body": "Temporali previsti a monti verso le 18:00.",
                "source": "open_meteo_model_support",
            },
            event_at="2026-06-27T18:00",
        )

        self.assertEqual(candidate["state"], "invalid_candidate")
        self.assertIn("invalid_city", candidate["validation_errors"])

    def test_forbidden_alert_terms_are_rejected(self):
        candidate = normalizer.normalize_notice_candidate(
            {
                "kind": "storm",
                "category": "storms",
                "city": "Udine",
                "starts_at": "2026-06-27T18:00",
                "body": "Allerta temporali a Udine verso le 18:00.",
                "source": "open_meteo_model_support",
            },
            event_at="2026-06-27T18:00",
        )

        self.assertEqual(candidate["state"], "invalid_candidate")
        self.assertIn("forbidden_body_terms", candidate["validation_errors"])

    def test_unknown_source_is_low_confidence(self):
        candidate = normalizer.normalize_notice_candidate(
            {
                "kind": "heat",
                "category": "heat",
                "city": "Pordenone",
                "starts_at": "2026-06-27",
                "body": "Caldo previsto oggi a Pordenone.",
                "source": "mystery_source",
            }
        )

        self.assertEqual(candidate["state"], "low_confidence")
        self.assertIn("unknown_source", candidate["validation_errors"])
        self.assertFalse(candidate["candidate_can_notify"])

    def test_official_alert_overlap_suppresses_candidate(self):
        candidate = normalizer.normalize_notice_candidate(
            {
                "kind": "wind",
                "category": "wind",
                "city": "Trieste",
                "starts_at": "2026-06-27T21:00",
                "body": "Bora prevista a Trieste verso le 21:00.",
                "source": "open_meteo_model_support",
            },
            event_at="2026-06-27T21:00",
            official_alert_overlap=True,
        )

        self.assertEqual(candidate["state"], "suppressed_by_official_alert")
        self.assertFalse(candidate["candidate_can_notify"])

    def test_trigger_metadata_is_preserved(self):
        candidate = normalizer.normalize_notice_candidate(
            {
                "kind": "heat",
                "category": "heat",
                "city": "Pordenone",
                "starts_at": "2026-06-27T20:00",
                "body": "Caldo previsto oggi a Pordenone.",
                "source": "osmer_station_and_open_meteo_support",
                "trigger_source": "current_feels_like",
                "trigger_value": 34,
                "trigger_unit": "C",
            },
            event_at="2026-06-27T20:00",
        )

        self.assertEqual(candidate["state"], "ready")
        self.assertEqual(candidate["trigger_source"], "current_feels_like")
        self.assertEqual(candidate["trigger_value"], 34)
        self.assertEqual(candidate["trigger_unit"], "C")


if __name__ == "__main__":
    unittest.main()
