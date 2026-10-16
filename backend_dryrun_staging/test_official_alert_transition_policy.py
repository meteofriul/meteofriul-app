"""Tests for the pure official-alert transition policy."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "backend_dryrun_staging"
MATRIX_FILE = STAGING / "data_pipeline_case_matrix.json"
sys.path.insert(0, str(STAGING))

import official_alert_transition_policy as policy  # noqa: E402


NOW = "2026-06-26T12:00:00+02:00"


def previous_yellow(expires_at: str = "2026-06-26T18:00:00+02:00") -> dict:
    return {
        "state": "active",
        "alert": {
            "level": "yellow",
            "label": "Allerta gialla",
            "expires_at": expires_at,
            "signature": "previous-yellow",
        },
    }


def primary_yellow(signature: str = "primary-yellow") -> dict:
    return {
        "state": "active",
        "alert": {
            "level": "yellow",
            "label": "Allerta gialla",
            "expires_at": "2026-06-26T18:00:00+02:00",
            "signature": signature,
        },
    }


def matrix_case(case_id: str) -> dict:
    import json

    matrix = json.loads(MATRIX_FILE.read_text(encoding="utf-8"))
    return next(case for case in matrix["official_alert_cases"] if case["id"] == case_id)


class OfficialAlertTransitionPolicyTest(unittest.TestCase):
    def test_primary_active_decides_and_can_notify_when_new(self) -> None:
        result = policy.transition_official_alert(
            {},
            primary_yellow("new-yellow"),
            now=NOW,
        )

        self.assertEqual("active", result["final_alert_state"]["state"])
        self.assertEqual("regional_fvg_primary", result["final_alert_state"]["source_authority"])
        self.assertFalse(result["final_alert_state"]["can_clear_previous_alert"])
        self.assertTrue(result["notification_effect"]["can_notify"])
        self.assertFalse(result["notification_effect"]["live_connected"])
        self.assertEqual("Allerta gialla", result["home_effect"]["label"])
        self.assertFalse(result["home_effect"]["show_uncertainty_copy"])

    def test_primary_active_same_level_signature_change_does_not_notify_by_default(self) -> None:
        result = policy.transition_official_alert(
            previous_yellow(),
            primary_yellow("text-change-yellow"),
            now=NOW,
        )

        self.assertEqual("active", result["final_alert_state"]["state"])
        self.assertFalse(result["notification_effect"]["can_notify"])
        self.assertEqual(
            "same_level_text_change_suppressed",
            result["notification_effect"]["reason"],
        )

    def test_primary_active_duplicate_does_not_notify(self) -> None:
        result = policy.transition_official_alert(
            previous_yellow(),
            primary_yellow("previous-yellow"),
            now=NOW,
        )

        self.assertEqual("active", result["final_alert_state"]["state"])
        self.assertFalse(result["notification_effect"]["can_notify"])
        self.assertEqual("same_alert_already_known", result["notification_effect"]["reason"])

    def test_primary_inactive_confirmed_clears_previous_alert(self) -> None:
        result = policy.transition_official_alert(
            previous_yellow(),
            {"state": "inactive_confirmed"},
            now=NOW,
        )

        self.assertEqual("inactive_confirmed", result["final_alert_state"]["state"])
        self.assertTrue(result["final_alert_state"]["can_clear_previous_alert"])
        self.assertFalse(result["home_effect"]["show_alert"])
        self.assertFalse(result["bulletin_effect"]["show_notice"])
        self.assertFalse(result["notification_effect"]["can_notify"])

    def test_primary_unreachable_keeps_valid_previous_alert_without_user_uncertainty(self) -> None:
        case = matrix_case("primary_unreachable_keep_previous_alert")
        result = policy.transition_official_alert(
            previous_yellow(),
            {"state": "unavailable", "reachable": False},
            telegram_diagnostic={"status": "checked", "alert_signature": "telegram-yellow"},
            dpc_diagnostic={"status": "checked", "alert_signature": "dpc-yellow"},
            now=NOW,
        )

        self.assertEqual(case["state"], result["final_alert_state"]["state"])
        self.assertEqual(
            "regional_fvg_primary_unreachable",
            result["final_alert_state"]["source_authority"],
        )
        self.assertEqual(case["can_clear_previous_alert"], result["final_alert_state"]["can_clear_previous_alert"])
        self.assertEqual(case["can_notify"], result["notification_effect"]["can_notify"])
        self.assertEqual(case["home_show_alert"], result["home_effect"]["show_alert"])
        self.assertEqual("Allerta gialla", result["home_effect"]["label"])
        self.assertEqual(case["home_copy_mode"], result["home_effect"]["copy_mode"])
        self.assertEqual(case["home_show_uncertainty_copy"], result["home_effect"]["show_uncertainty_copy"])
        self.assertEqual(case["bulletin_show_notice"], result["bulletin_effect"]["show_notice"])
        self.assertEqual(case["bulletin_copy_mode"], result["bulletin_effect"]["copy_mode"])
        self.assertEqual(case["bulletin_show_unreachable_copy"], result["bulletin_effect"]["show_unreachable_copy"])
        self.assertEqual("unavailable_previous_valid_retained", result["audit_reason"])

        for diagnostic in result["final_alert_state"]["diagnostics"]:
            self.assertEqual("diagnostic_only", diagnostic["decision_role"])
            self.assertFalse(diagnostic["can_decide"])
            self.assertFalse(diagnostic["can_clear_previous_alert"])
            self.assertFalse(diagnostic["can_notify"])

    def test_diagnostic_primary_keeps_valid_previous_alert(self) -> None:
        result = policy.transition_official_alert(
            previous_yellow(),
            {"state": "diagnostic", "reachable": True},
            telegram_diagnostic={"status": "checked"},
            dpc_diagnostic={"status": "checked"},
            now=NOW,
        )

        self.assertEqual("stale_held_active", result["final_alert_state"]["state"])
        self.assertEqual("diagnostic_previous_valid_retained", result["audit_reason"])
        self.assertEqual("Allerta gialla", result["home_effect"]["label"])
        self.assertFalse(result["home_effect"]["show_uncertainty_copy"])

    def test_unreachable_with_expired_previous_does_not_show_alert(self) -> None:
        result = policy.transition_official_alert(
            previous_yellow("2026-06-26T10:00:00+02:00"),
            {"state": "unavailable", "reachable": False},
            telegram_diagnostic={"status": "active_alert_seen", "can_decide": True},
            dpc_diagnostic={"status": "active_alert_seen", "can_decide": True},
            now=NOW,
        )

        self.assertEqual("unavailable", result["final_alert_state"]["state"])
        self.assertFalse(result["home_effect"]["show_alert"])
        self.assertFalse(result["bulletin_effect"]["show_notice"])
        self.assertFalse(result["final_alert_state"]["can_clear_previous_alert"])
        self.assertFalse(result["notification_effect"]["can_notify"])

        for diagnostic in result["final_alert_state"]["diagnostics"]:
            self.assertFalse(diagnostic["can_decide"])

    def test_demo_scenarios_include_primary_unreachable_case(self) -> None:
        ids = {item["id"] for item in policy.demo_scenarios()}

        self.assertIn("primary_active_yellow_new", ids)
        self.assertIn("primary_active_yellow_duplicate", ids)
        self.assertIn("primary_unreachable_keep_previous_alert", ids)
        self.assertIn("primary_inactive_confirmed", ids)


if __name__ == "__main__":
    unittest.main()
