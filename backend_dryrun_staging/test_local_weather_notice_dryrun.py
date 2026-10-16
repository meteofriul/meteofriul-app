"""Tests for the local weather notice dry-run report."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "backend_dryrun_staging"
sys.path.insert(0, str(STAGING))

import local_weather_notice_dryrun as dryrun  # noqa: E402
import local_weather_notification_policy as policy  # noqa: E402


class LocalWeatherNoticeDryRunTest(unittest.TestCase):
    def test_report_uses_pure_detector_without_side_effects(self):
        report = dryrun.build_report()

        self.assertTrue(report["dry_run"])
        self.assertEqual(
            report["source"],
            "fixture dichiarate -> local_weather_notice_detector.detect_local_weather_notices",
        )
        self.assertEqual(
            report["side_effects"],
            {
                "network": False,
                "firestore": False,
                "fcm": False,
                "workflow": False,
            },
        )

        by_city = {city["city"]: city for city in report["cities"]}
        pordenone_kinds = {notice["kind"]: notice for notice in by_city["Pordenone"]["notices"]}
        self.assertEqual(pordenone_kinds["heat"]["body"], "Caldo previsto oggi a Pordenone.")
        self.assertEqual(pordenone_kinds["rain"]["body"], "Pioggia prevista a Pordenone verso le 17:00.")
        self.assertEqual(pordenone_kinds["rain"]["copy_normalizations"], ["inserted_city"])
        self.assertTrue(pordenone_kinds["rain"]["can_notify"])
        self.assertFalse(pordenone_kinds["heat"]["can_notify"])
        self.assertEqual(
            pordenone_kinds["heat"]["notification_policy"],
            "held_by_more_important_nearby_event",
        )

        self.assertEqual(by_city["Udine"]["status"], "no_notice")

        trieste_kinds = {notice["kind"] for notice in by_city["Trieste"]["notices"]}
        self.assertIn("bora", trieste_kinds)

        tarvisio_kinds = {notice["kind"] for notice in by_city["Tarvisio"]["notices"]}
        self.assertIn("hail", tarvisio_kinds)
        self.assertIn("snow", tarvisio_kinds)
        tarvisio_by_kind = {notice["kind"]: notice for notice in by_city["Tarvisio"]["notices"]}
        self.assertTrue(tarvisio_by_kind["hail"]["can_notify"])
        self.assertFalse(tarvisio_by_kind["snow"]["can_notify"])
        self.assertEqual(tarvisio_by_kind["snow"]["notification_policy"], "held_by_temporal_cluster")

        cividale_by_kind = {notice["kind"]: notice for notice in by_city["Cividale del Friuli"]["notices"]}
        self.assertTrue(cividale_by_kind["storm"]["can_notify"])
        self.assertTrue(cividale_by_kind["heat"]["can_notify"])
        self.assertEqual(cividale_by_kind["storm"]["notification_policy"], "selected_by_priority_and_time")
        self.assertEqual(cividale_by_kind["heat"]["notification_policy"], "selected_by_priority_and_time")

    def test_text_report_is_readable(self):
        report = dryrun.build_report(["Pordenone", "Udine"])
        text = dryrun.format_text_report(report)

        self.assertIn("Politica audit: priorita + distanza temporale", text)
        self.assertIn("Pordenone - caldo + pioggia nello stesso pomeriggio", text)
        self.assertIn("frase: Caldo previsto oggi a Pordenone.", text)
        self.assertIn("normalizzazione copy: inserted_city", text)
        self.assertIn("motivo notifica: trattenuta: rain piu importante entro 8 ore", text)
        self.assertIn("Udine - giornata senza soglie locali", text)
        self.assertIn("status: no_notice", text)

    def test_separated_heat_and_storm_can_both_be_selected(self):
        report = dryrun.build_report(["Cividale del Friuli"])
        city = report["cities"][0]
        by_kind = {notice["kind"]: notice for notice in city["notices"]}

        self.assertTrue(by_kind["storm"]["can_notify"])
        self.assertTrue(by_kind["heat"]["can_notify"])
        self.assertEqual(by_kind["heat"]["event_at"], "2026-06-27T09:00")
        self.assertEqual(by_kind["storm"]["event_at"], "2026-06-27T20:00")

    def test_official_alert_overlap_suppresses_matching_local_notice(self):
        report = dryrun.build_report(
            ["Cividale del Friuli"],
            official_alerts=[
                {
                    "risks": ["temporali"],
                    "official_text": "Possibili temporali forti.",
                }
            ],
        )
        city = report["cities"][0]
        by_kind = {notice["kind"]: notice for notice in city["notices"]}

        self.assertEqual(by_kind["storm"]["status"], "suppressed_by_official_alert")
        self.assertFalse(by_kind["storm"]["can_notify"])
        self.assertTrue(by_kind["heat"]["can_notify"])

    def test_later_hail_beats_earlier_rain_inside_same_window(self):
        notices = [
            {
                "kind": "rain",
                "category": "rain",
                "priority": policy.NOTICE_PRIORITY["rain"],
                "severity": 1,
                "status": "ready",
                "candidate_can_notify": True,
                "can_notify": False,
                "event_at": "2026-06-27T15:00",
                "starts_at": "2026-06-27T15:00",
                "notification_policy": "",
                "notification_reason": "",
            },
            {
                "kind": "hail",
                "category": "storms",
                "priority": policy.NOTICE_PRIORITY["hail"],
                "severity": 3,
                "status": "ready",
                "candidate_can_notify": True,
                "can_notify": False,
                "event_at": "2026-06-27T17:00",
                "starts_at": "2026-06-27T17:00",
                "notification_policy": "",
                "notification_reason": "",
            },
        ]

        evaluated = policy.apply_notification_policy(notices)
        by_kind = {notice["kind"]: notice for notice in evaluated}

        self.assertTrue(by_kind["hail"]["can_notify"])
        self.assertFalse(by_kind["rain"]["can_notify"])
        self.assertEqual(by_kind["rain"]["notification_policy"], "held_by_temporal_cluster")

    def test_equal_priority_inside_window_keeps_earlier_event(self):
        notices = [
            {
                "kind": "rain",
                "category": "rain",
                "priority": policy.NOTICE_PRIORITY["rain"],
                "severity": 1,
                "status": "ready",
                "candidate_can_notify": True,
                "can_notify": False,
                "event_at": "2026-06-27T15:00",
                "starts_at": "2026-06-27T15:00",
                "notification_policy": "",
                "notification_reason": "",
            },
            {
                "kind": "rain_later",
                "category": "rain",
                "priority": policy.NOTICE_PRIORITY["rain"],
                "severity": 1,
                "status": "ready",
                "candidate_can_notify": True,
                "can_notify": False,
                "event_at": "2026-06-27T17:00",
                "starts_at": "2026-06-27T17:00",
                "notification_policy": "",
                "notification_reason": "",
            },
        ]

        evaluated = policy.apply_notification_policy(notices)
        by_kind = {notice["kind"]: notice for notice in evaluated}

        self.assertTrue(by_kind["rain"]["can_notify"])
        self.assertFalse(by_kind["rain_later"]["can_notify"])
        self.assertEqual(by_kind["rain_later"]["notification_policy"], "held_by_temporal_cluster")


if __name__ == "__main__":
    unittest.main()
