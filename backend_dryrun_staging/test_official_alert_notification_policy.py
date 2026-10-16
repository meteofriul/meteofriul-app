"""Tests for the pure official-alert notification policy."""

from __future__ import annotations

import json
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "backend_dryrun_staging"
MATRIX_FILE = STAGING / "data_pipeline_case_matrix.json"
sys.path.insert(0, str(STAGING))

import official_alert_notification_policy as policy  # noqa: E402


def load_notification_cases() -> list[dict]:
    matrix = json.loads(MATRIX_FILE.read_text(encoding="utf-8"))
    return matrix["notification_cases"]


def previous(level: str = "yellow", signature: str = "yellow-1") -> dict:
    return {
        "state": "active",
        "alert": {
            "level": level,
            "label": f"Allerta {level}",
            "signature": signature,
        },
    }


def final_active(level: str = "yellow", signature: str = "yellow-2", **extra) -> dict:
    alert = {
        "level": level,
        "label": f"Allerta {level}",
        "signature": signature,
    }
    alert.update(extra.pop("alert_extra", {}))
    return {
        "state": "active",
        "source_authority": extra.pop("source_authority", "regional_fvg_primary"),
        "alert": alert,
        **extra,
    }


def previous_from_case(case: dict) -> dict:
    if case.get("previous_state") != "active":
        return {}
    level = case.get("previous_severity") or case.get("severity") or "yellow"
    signature = "same" if case.get("same_signature") else f"previous-{level}"
    return previous(level, signature)


def final_from_case(case: dict) -> dict:
    alert: dict = {}
    if case.get("severity"):
        alert["level"] = case["severity"]
        alert["label"] = f"Allerta {case['severity']}"
        alert["signature"] = "same" if case.get("same_signature") else f"{case['id']}-signature"
    if case.get("change_kind"):
        alert["change_kind"] = case["change_kind"]
    if case.get("important_change"):
        alert["important_signature_change"] = True
    return {
        "state": case["final_state"],
        "source_authority": case.get("source_authority", ""),
        "alert": alert,
    }


class OfficialAlertNotificationPolicyTest(unittest.TestCase):
    def test_notification_matrix_has_required_cases(self) -> None:
        ids = {case["id"] for case in load_notification_cases()}

        self.assertEqual(
            {
                "new_yellow_fvg_alert",
                "new_orange_fvg_alert",
                "new_red_fvg_alert",
                "same_alert_already_known",
                "yellow_to_orange",
                "same_level_text_change",
                "important_same_level_change",
                "fvg_unreachable_held_previous",
                "inactive_confirmed",
                "expired_without_fvg_confirmation",
                "telegram_diagnostic",
                "dpc_diagnostic",
            },
            ids,
        )

    def test_notification_matrix_matches_policy(self) -> None:
        for case in load_notification_cases():
            with self.subTest(case=case["id"]):
                result = policy.decide_official_alert_notification(
                    previous_from_case(case),
                    final_from_case(case),
                )

                self.assertEqual(case["can_notify"], result["can_notify"])
                self.assertEqual(case["reason"], result["reason"])
                self.assertFalse(result["live_connected"])

    def test_new_fvg_yellow_orange_red_alerts_can_notify(self) -> None:
        for level in ("yellow", "orange", "red"):
            with self.subTest(level=level):
                result = policy.decide_official_alert_notification(
                    {},
                    final_active(level, f"{level}-1"),
                )

                self.assertTrue(result["can_notify"])
                self.assertEqual("new_fvg_alert", result["reason"])
                self.assertEqual(level, result["severity"])
                self.assertFalse(result["live_connected"])

    def test_same_alert_already_known_does_not_notify(self) -> None:
        result = policy.decide_official_alert_notification(
            previous("yellow", "same"),
            final_active("yellow", "same"),
        )

        self.assertFalse(result["can_notify"])
        self.assertEqual("same_alert_already_known", result["reason"])

    def test_severity_change_can_notify(self) -> None:
        result = policy.decide_official_alert_notification(
            previous("yellow", "yellow-1"),
            final_active("orange", "orange-1"),
        )

        self.assertTrue(result["can_notify"])
        self.assertEqual("severity_changed", result["reason"])
        self.assertEqual("orange", result["severity"])

    def test_same_level_text_change_is_suppressed_without_important_flag(self) -> None:
        result = policy.decide_official_alert_notification(
            previous("yellow", "yellow-1"),
            final_active("yellow", "yellow-text-2"),
        )

        self.assertFalse(result["can_notify"])
        self.assertEqual("same_level_text_change_suppressed", result["reason"])

    def test_same_level_important_signature_change_can_notify(self) -> None:
        result = policy.decide_official_alert_notification(
            previous("yellow", "yellow-1"),
            final_active(
                "yellow",
                "yellow-important-2",
                alert_extra={"important_signature_change": True},
            ),
        )

        self.assertTrue(result["can_notify"])
        self.assertEqual("important_signature_changed", result["reason"])

    def test_unreachable_fvg_with_held_previous_alert_does_not_notify(self) -> None:
        result = policy.decide_official_alert_notification(
            previous("yellow", "yellow-1"),
            {
                "state": "stale_held_active",
                "source_authority": "regional_fvg_primary_unreachable",
                "alert": {"level": "yellow", "signature": "yellow-1"},
            },
        )

        self.assertFalse(result["can_notify"])
        self.assertEqual("stale_held_active_does_not_notify", result["reason"])

    def test_confirmed_no_alert_expired_and_diagnostic_do_not_notify(self) -> None:
        for state in ("inactive_confirmed", "expired", "diagnostic", "unavailable"):
            with self.subTest(state=state):
                result = policy.decide_official_alert_notification(
                    previous("yellow", "yellow-1"),
                    {"state": state, "source_authority": "regional_fvg_primary"},
                )

                self.assertFalse(result["can_notify"])
                self.assertEqual(f"{state}_does_not_notify", result["reason"])

    def test_telegram_and_dpc_diagnostics_never_notify(self) -> None:
        for source_authority in ("telegram_public_channel", "national_dpc"):
            with self.subTest(source_authority=source_authority):
                result = policy.decide_official_alert_notification(
                    previous("yellow", "yellow-1"),
                    final_active(
                        "orange",
                        "diagnostic-orange",
                        source_authority=source_authority,
                    ),
                )

                self.assertFalse(result["can_notify"])
                self.assertEqual("non_primary_fvg_source_does_not_notify", result["reason"])

    def test_demo_scenarios_include_core_matrix(self) -> None:
        ids = {item["id"] for item in policy.demo_scenarios()}

        self.assertIn("new_yellow", ids)
        self.assertIn("duplicate_yellow", ids)
        self.assertIn("yellow_to_orange", ids)
        self.assertIn("same_level_text_change", ids)
        self.assertIn("important_same_level_change", ids)
        self.assertIn("held_previous_unreachable", ids)
        self.assertIn("telegram_diagnostic", ids)


if __name__ == "__main__":
    unittest.main()
