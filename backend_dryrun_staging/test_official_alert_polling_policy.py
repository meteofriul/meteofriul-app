"""Tests for the pure official-alert polling policy."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "backend_dryrun_staging"
sys.path.insert(0, str(STAGING))

import official_alert_polling_policy as policy  # noqa: E402


NOW = "2026-06-26T12:00:00+02:00"


class OfficialAlertPollingPolicyTest(unittest.TestCase):
    def test_no_alert_confirmed_checks_every_30_minutes(self) -> None:
        result = policy.plan_official_alert_polling("inactive_confirmed", now=NOW)

        self.assertEqual(30, result["next_check_minutes"])
        self.assertEqual("no_alert_confirmed_standard_interval", result["reason"])
        self.assertFalse(result["diagnostics"]["telegram_fvg_allowed"])
        self.assertFalse(result["scheduler_connected"])

    def test_active_alert_checks_every_15_minutes(self) -> None:
        result = policy.plan_official_alert_polling(
            {"state": "active", "alert": {"expires_at": "2026-06-26T18:00:00+02:00"}},
            now=NOW,
        )

        self.assertEqual(15, result["next_check_minutes"])
        self.assertEqual("active_alert_standard_interval", result["reason"])
        self.assertEqual(360, result["expires_in_minutes"])

    def test_active_alert_in_last_hour_checks_every_5_minutes(self) -> None:
        result = policy.plan_official_alert_polling(
            {"state": "active", "alert": {"expires_at": "2026-06-26T12:45:00+02:00"}},
            now=NOW,
        )

        self.assertEqual(5, result["next_check_minutes"])
        self.assertEqual("active_alert_expiring_within_one_hour", result["reason"])
        self.assertEqual(45, result["expires_in_minutes"])

    def test_unreachable_source_uses_backoff(self) -> None:
        first = policy.plan_official_alert_polling(
            "unavailable",
            primary_reachable=False,
            consecutive_failures=1,
            now=NOW,
        )
        second = policy.plan_official_alert_polling(
            "unavailable",
            primary_reachable=False,
            consecutive_failures=2,
            now=NOW,
        )
        third = policy.plan_official_alert_polling(
            "unavailable",
            primary_reachable=False,
            consecutive_failures=3,
            now=NOW,
        )
        repeated = policy.plan_official_alert_polling(
            "unavailable",
            primary_reachable=False,
            consecutive_failures=4,
            now=NOW,
        )

        self.assertEqual(5, first["next_check_minutes"])
        self.assertEqual(10, second["next_check_minutes"])
        self.assertEqual(20, third["next_check_minutes"])
        self.assertEqual(30, repeated["next_check_minutes"])

    def test_diagnostics_are_allowed_only_after_repeated_fvg_failures(self) -> None:
        first = policy.plan_official_alert_polling(
            "unavailable",
            primary_reachable=False,
            consecutive_failures=1,
            now=NOW,
        )
        second = policy.plan_official_alert_polling(
            "unavailable",
            primary_reachable=False,
            consecutive_failures=2,
            now=NOW,
        )

        self.assertFalse(first["diagnostics"]["telegram_fvg_allowed"])
        self.assertFalse(first["diagnostics"]["dpc_national_allowed"])
        self.assertTrue(second["diagnostics"]["telegram_fvg_allowed"])
        self.assertTrue(second["diagnostics"]["dpc_national_allowed"])
        self.assertFalse(second["diagnostics"]["can_decide"])
        self.assertFalse(second["diagnostics"]["can_clear_previous_alert"])
        self.assertFalse(second["diagnostics"]["can_notify"])

    def test_undecided_state_retries_in_10_minutes_without_diagnostics_decision(self) -> None:
        result = policy.plan_official_alert_polling("diagnostic", now=NOW)

        self.assertEqual(10, result["next_check_minutes"])
        self.assertEqual("undecided_state_needs_near_retry", result["reason"])
        self.assertFalse(result["diagnostics"]["can_decide"])

    def test_demo_scenarios_include_core_cases(self) -> None:
        ids = {item["id"] for item in policy.demo_scenarios()}

        self.assertIn("no_alert_confirmed", ids)
        self.assertIn("active_alert", ids)
        self.assertIn("active_alert_expiring", ids)
        self.assertIn("fvg_unreachable_first_retry", ids)
        self.assertIn("fvg_unreachable_second_retry", ids)
        self.assertIn("fvg_unreachable_third_retry", ids)
        self.assertIn("fvg_unreachable_repeated_retry", ids)


if __name__ == "__main__":
    unittest.main()
