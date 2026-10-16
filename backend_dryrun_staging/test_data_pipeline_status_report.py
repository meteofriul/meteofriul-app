"""Local non-regression tests for the data-pipeline status report.

These tests do not call network sources and do not write app state. They verify
the saved-audit report and the decision matrix before any future live wiring.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "backend_dryrun_staging"
MATRIX_FILE = STAGING / "data_pipeline_case_matrix.json"
sys.path.insert(0, str(STAGING))

import data_pipeline_status_report as status_report  # noqa: E402


def load_matrix() -> dict:
    return json.loads(MATRIX_FILE.read_text(encoding="utf-8"))


def ready_osmer() -> dict:
    return {
        "available": True,
        "state": "ready",
        "can_use_as_current": True,
        "can_render_native_map": True,
    }


def no_alert_confirmed() -> dict:
    return {
        "available": True,
        "state": "inactive_confirmed",
        "can_notify": False,
        "can_clear_previous_alert": True,
    }


def alert_from_case(case: dict) -> dict:
    severity = str(case.get("severity") or "").strip()
    return {
        "available": True,
        "state": case["state"],
        "can_notify": bool(case["can_notify"]),
        "can_clear_previous_alert": bool(case["can_clear_previous_alert"]),
        "home": {
            "show_alert": bool(case["home_show_alert"]),
            "label": f"Allerta {severity}" if severity else "",
        },
        "bulletin": {
            "show_notice": bool(case["bulletin_show_notice"]),
            "notice": f"Allerta {severity}" if severity else "",
        },
    }


def osmer_from_case(case: dict) -> dict:
    return {
        "available": True,
        "state": case["state"],
        "source_status": case.get("source_status", ""),
        "can_use_as_current": bool(case["can_use_as_current"]),
        "can_render_native_map": bool(case["can_render_native_map"]),
    }


class DataPipelineStatusReportTest(unittest.TestCase):
    def test_matrix_has_required_cases(self) -> None:
        matrix = load_matrix()
        alert_ids = {case["id"] for case in matrix["official_alert_cases"]}
        osmer_ids = {case["id"] for case in matrix["osmer_cases"]}

        self.assertEqual(
            {
                "no_alert_confirmed",
                "yellow_alert",
                "orange_alert",
                "red_alert",
                "primary_unreachable_keep_previous_alert",
                "source_unavailable",
                "page_changed_parse_error",
                "stale_data",
            },
            alert_ids,
        )
        self.assertEqual(
            {
                "xml_complete",
                "xml_404_recovered_from_window",
                "missing_a1_a9",
                "text_without_map",
                "source_unavailable",
            },
            osmer_ids,
        )

    def test_official_alert_matrix_drives_overall_decision(self) -> None:
        matrix = load_matrix()
        osmer = ready_osmer()

        for case in matrix["official_alert_cases"]:
            with self.subTest(case=case["id"]):
                alert = alert_from_case(case)
                decision = status_report.build_decision(alert, osmer)
                self.assertEqual(
                    case["expected_overall_with_ready_osmer"],
                    decision["overall"],
                )
                self.assertEqual(
                    case["can_clear_previous_alert"],
                    decision["can_clear_previous_alert"],
                )
                self.assertEqual(
                    case["can_notify"],
                    decision["notification_dry_run_allowed"],
                )

    def test_primary_unreachable_keeps_previous_alert_without_user_uncertainty_copy(self) -> None:
        matrix = load_matrix()
        case = next(
            item
            for item in matrix["official_alert_cases"]
            if item["id"] == "primary_unreachable_keep_previous_alert"
        )
        alert = alert_from_case(case)
        decision = status_report.build_decision(alert, ready_osmer())

        self.assertEqual("stale_held_active", case["state"])
        self.assertTrue(case["previous_alert_valid"])
        self.assertFalse(case["primary_source_reachable"])
        self.assertEqual(
            ["telegram_public_channel", "national_dpc"],
            case["diagnostics_only"],
        )
        self.assertFalse(case["diagnostics_can_decide"])
        self.assertFalse(case["can_clear_previous_alert"])
        self.assertFalse(case["can_notify"])
        self.assertTrue(case["home_show_alert"])
        self.assertEqual("retain_previous_alert", case["home_copy_mode"])
        self.assertFalse(case["home_show_uncertainty_copy"])
        self.assertEqual("retain_previous_alert", case["bulletin_copy_mode"])
        self.assertFalse(case["bulletin_show_unreachable_copy"])
        self.assertEqual("needs_review", decision["overall"])
        self.assertFalse(decision["can_clear_previous_alert"])
        self.assertFalse(decision["notification_dry_run_allowed"])

    def test_osmer_matrix_drives_overall_decision(self) -> None:
        matrix = load_matrix()
        alert = no_alert_confirmed()

        for case in matrix["osmer_cases"]:
            with self.subTest(case=case["id"]):
                osmer = osmer_from_case(case)
                decision = status_report.build_decision(alert, osmer)
                self.assertEqual(
                    case["expected_overall_with_no_alert_confirmed"],
                    decision["overall"],
                )
                self.assertEqual(
                    case["can_use_as_current"],
                    decision["can_show_bulletin"],
                )
                self.assertEqual(
                    case["can_render_native_map"],
                    decision["can_render_map"],
                )

    def test_filter_scope_keeps_live_sample_and_invalidated_separate(self) -> None:
        rows = [
            {
                "audit_id": "live-1",
                "created_at": "2026-06-26T10:00:00+02:00",
                "ok": True,
                "source": {"raw_snapshot_file": "raw.html"},
            },
            {
                "audit_id": "sample-1",
                "created_at": "2026-06-26T10:01:00+02:00",
                "ok": True,
                "source": {"raw_snapshot_file": ""},
            },
            {
                "audit_id": "bad-1",
                "created_at": "2026-06-26T10:02:00+02:00",
                "ok": False,
                "source": {"raw_snapshot_file": "raw.html"},
            },
        ]

        live = status_report.filter_scope(rows, "live", status_report.is_live_official_alert)
        sample = status_report.filter_scope(rows, "sample", status_report.is_live_official_alert)
        all_rows = status_report.filter_scope(rows, "all", status_report.is_live_official_alert)

        self.assertEqual(["live-1"], [row["audit_id"] for row in live])
        self.assertEqual(["sample-1"], [row["audit_id"] for row in sample])
        self.assertEqual(["live-1", "sample-1"], [row["audit_id"] for row in all_rows])

        osmer_rows = [
            {
                "audit_id": "osmer-live",
                "ok": True,
                "discovery": {"dev_page": {"ok": True}},
                "observation": {"source_status": "merged_xml_window"},
                "sources": [{"status": "fetched"}],
            },
            {
                "audit_id": "osmer-invalid",
                "ok": True,
                "discovery": {"dev_page": {"ok": False}},
                "observation": {"source_status": "source_unavailable"},
                "sources": [{"status": "error"}],
            },
        ]
        filtered = status_report.filter_scope(
            osmer_rows,
            "all",
            status_report.is_live_osmer,
            {"osmer-invalid"},
        )
        self.assertEqual(["osmer-live"], [row["audit_id"] for row in filtered])

    def test_clean_checkout_without_local_audits_reports_unavailable(self) -> None:
        with (
            patch.object(status_report, "read_jsonl", return_value=[]),
            patch.object(status_report, "read_invalidated_osmer", return_value={}),
        ):
            report = status_report.build_report("live")

        self.assertEqual("live", report["scope"])
        self.assertFalse(report["official_alerts"]["available"])
        self.assertEqual(0, report["counts"]["official_alert_candidates"])
        self.assertEqual(0, report["counts"]["osmer_candidates"])
        self.assertEqual(5, report["polling"]["next_check_minutes"])
        self.assertEqual("fvg_unreachable_retry_1", report["polling"]["reason"])
        self.assertFalse(report["notification_decision"]["can_notify"])
        self.assertEqual(
            "unavailable_does_not_notify",
            report["notification_decision"]["reason"],
        )
        self.assertFalse(report["osmer_bulletin"]["available"])
        self.assertEqual("needs_review", report["decision"]["overall"])

        rendered = status_report.render_text(report)
        self.assertIn("DATA PIPELINE STATUS REPORT", rendered)
        self.assertIn("Scope: live", rendered)
        self.assertIn("Prossimo controllo FVG", rendered)
        self.assertIn("tra: 5 minuti", rendered)
        self.assertIn("Decisione notifica", rendered)
        self.assertIn("motivo: unavailable_does_not_notify", rendered)

    def test_report_polling_handles_unreachable_fvg_source(self) -> None:
        rows = [
            {
                "audit_id": "fvg-fail-1",
                "created_at": "2026-06-26T10:00:00+02:00",
                "state": {"state": "unavailable"},
                "parser": {"status": "unavailable"},
                "source": {"raw_sha256": ""},
            },
            {
                "audit_id": "fvg-fail-2",
                "created_at": "2026-06-26T10:05:00+02:00",
                "state": {"state": "unavailable"},
                "parser": {"status": "unavailable"},
                "source": {"raw_sha256": ""},
            },
        ]
        alert = {
            "available": True,
            "state": "unavailable",
            "source_reachable": False,
            "created_at": "2026-06-26T10:05:00+02:00",
        }

        polling = status_report.build_polling_summary(alert, rows)

        self.assertEqual(10, polling["next_check_minutes"])
        self.assertEqual("fvg_unreachable_retry_2", polling["reason"])
        self.assertTrue(polling["diagnostics"]["telegram_fvg_allowed"])
        self.assertFalse(polling["diagnostics"]["can_decide"])

    def test_report_notification_decision_uses_policy_for_new_fvg_alert(self) -> None:
        entry = {
            "state": {
                "state": "active",
                "source_authority": "regional_fvg_primary",
            },
            "payload": {"file": "generated-alert.json"},
        }
        alert = {
            "available": True,
            "state": "active",
            "previous_state_file": "",
        }

        with patch.object(
            status_report,
            "read_json_file",
            side_effect=lambda path: (
                {
                    "alerts": [
                        {
                            "level": "yellow",
                            "signature": "yellow-1",
                        }
                    ]
                }
                if path
                else {}
            ),
        ):
            notification = status_report.build_notification_summary(entry, alert)

        self.assertTrue(notification["can_notify"])
        self.assertEqual("new_fvg_alert", notification["reason"])
        self.assertEqual("yellow", notification["severity"])
        self.assertFalse(notification["live_connected"])


if __name__ == "__main__":
    unittest.main()
