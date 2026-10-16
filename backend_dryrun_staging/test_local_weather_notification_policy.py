"""Tests for the pure local weather notification policy."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "backend_dryrun_staging"
sys.path.insert(0, str(STAGING))

import local_weather_notification_policy as policy  # noqa: E402


def candidate(kind: str, event_at: str, priority: int | None = None, **extra):
    return {
        "kind": kind,
        "category": extra.pop("category", kind),
        "priority": policy.NOTICE_PRIORITY.get(kind, priority or 0),
        "severity": extra.pop("severity", 1),
        "status": extra.pop("status", "ready"),
        "candidate_can_notify": extra.pop("candidate_can_notify", True),
        "can_notify": False,
        "event_at": event_at,
        "starts_at": event_at,
        "notification_policy": "",
        "notification_reason": "",
        **extra,
    }


class LocalWeatherNotificationPolicyTest(unittest.TestCase):
    def test_later_higher_priority_event_wins_within_window(self):
        result = policy.apply_notification_policy([
            candidate("rain", "2026-06-27T15:00"),
            candidate("hail", "2026-06-27T17:00", category="storms", severity=3),
        ])
        by_kind = {notice["kind"]: notice for notice in result}

        self.assertFalse(by_kind["rain"]["can_notify"])
        self.assertTrue(by_kind["hail"]["can_notify"])
        self.assertEqual(by_kind["rain"]["notification_policy"], "held_by_temporal_cluster")

    def test_same_priority_keeps_earlier_event(self):
        result = policy.apply_notification_policy([
            candidate("rain", "2026-06-27T15:00"),
            candidate("rain_later", "2026-06-27T17:00", priority=policy.NOTICE_PRIORITY["rain"]),
        ])
        by_kind = {notice["kind"]: notice for notice in result}

        self.assertTrue(by_kind["rain"]["can_notify"])
        self.assertFalse(by_kind["rain_later"]["can_notify"])

    def test_heat_is_blocked_by_more_important_event_inside_heat_window(self):
        result = policy.apply_notification_policy([
            candidate("heat", "2026-06-27T09:00"),
            candidate("storm", "2026-06-27T16:00", category="storms", severity=2),
        ])
        by_kind = {notice["kind"]: notice for notice in result}

        self.assertFalse(by_kind["heat"]["can_notify"])
        self.assertTrue(by_kind["storm"]["can_notify"])
        self.assertEqual(by_kind["heat"]["notification_policy"], "held_by_more_important_nearby_event")

    def test_separated_events_can_both_notify(self):
        result = policy.apply_notification_policy([
            candidate("heat", "2026-06-27T09:00"),
            candidate("storm", "2026-06-27T20:00", category="storms", severity=2),
        ])
        by_kind = {notice["kind"]: notice for notice in result}

        self.assertTrue(by_kind["heat"]["can_notify"])
        self.assertTrue(by_kind["storm"]["can_notify"])

    def test_input_candidates_are_not_mutated(self):
        notices = [
            candidate("rain", "2026-06-27T15:00"),
            candidate("hail", "2026-06-27T17:00", category="storms", severity=3),
        ]

        policy.apply_notification_policy(notices)

        self.assertFalse(notices[0]["can_notify"])
        self.assertEqual(notices[0]["notification_policy"], "")


if __name__ == "__main__":
    unittest.main()
