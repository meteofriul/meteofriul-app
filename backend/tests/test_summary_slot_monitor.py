import io
import json
from copy import deepcopy
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.jobs.inspect_summary_slots import main
from app.services.summary_slot_monitor import expected_slot, latest_slots, evaluate_slot, instant, stamp


def summary(**changes):
    value = dict(status="sent", eligible_devices=2, attempted=2, sent=2,
                 deduplicated=0, failed=0, sent_unconfirmed=0, in_progress=0, retry_scheduled=0)
    value.update(changes)
    return value


def bundle(slot=None, *, observed="2026-10-25T06:50:00Z"):
    slot = slot or expected_slot("morning", date(2026, 10, 25))
    scheduled = instant(slot["scheduled_at"])
    name = slot["job"] + "/executions/" + slot["job"].rsplit("/", 1)[-1] + "-abc12"
    return {"schema_version": 1, "observed_at": observed, "complete": True,
            "window_start": stamp(scheduled - timedelta(days=1)), "window_end": observed,
            "bindings": [{"basis": "scheduler_run_job_audit", "job": slot["job"],
                          "scheduler": slot["scheduler"], "scheduled_at": slot["scheduled_at"], "execution": name}],
            "executions": [{"name": name, "job": slot["job"], "origin": "scheduler",
                            "created_at": stamp(scheduled + timedelta(seconds=4)),
                            "completed_at": stamp(scheduled + timedelta(minutes=2)),
                            "runtime_status": "succeeded", "summary": summary()}]}


class SummarySlotMonitorTests(unittest.TestCase):
    def setUp(self):
        self.slot = expected_slot("morning", date(2026, 10, 25))
        self.evidence = bundle(self.slot)

    def check(self, state, reason=None, evidence=None, now=None):
        evidence = self.evidence if evidence is None else evidence
        result = evaluate_slot(self.slot, evidence, now=now or evidence["observed_at"])
        self.assertEqual(result["state"], state, result)
        if reason:
            self.assertEqual(result["reason"], reason)
        return result

    def test_23_24_25_hour_days_keep_both_local_times(self):
        for kind in ("morning", "evening"):
            for day, expected_hours in ((date(2026,3,29),23),(date(2026,10,25),25),
                                        (date(2026,10,26),24),(date(2027,3,28),23)):
                before = expected_slot(kind, day - timedelta(days=1))
                after = expected_slot(kind, day)
                self.assertEqual(instant(after["scheduled_at"]) - instant(before["scheduled_at"]), timedelta(hours=expected_hours))
        self.assertEqual(self.slot["scheduled_at"], "2026-10-25T06:30:00Z")
        self.assertEqual(expected_slot("evening", date(2026,10,25))["scheduled_at"], "2026-10-25T19:45:00Z")

    def test_latest_due_does_not_forget_previous_day_at_midnight(self):
        slots = latest_slots("2026-10-25T23:30:00Z")
        self.assertEqual([s["local_date"] for s in slots], ["2026-10-25"] * 2)
        slots = latest_slots("2026-10-26T06:30:00Z")
        self.assertEqual([s["local_date"] for s in slots], ["2026-10-26", "2026-10-25"])

    def test_not_due_does_not_require_evidence(self):
        self.check("not_due", evidence={}, now="2026-10-25T06:29:59Z")

    def test_waiting_before_deadline(self):
        self.evidence["bindings"] = []; self.evidence["executions"] = []
        self.evidence["observed_at"] = "2026-10-25T06:44:59Z"
        self.check("waiting")

    def test_missing_exactly_at_deadline(self):
        self.evidence["bindings"] = []; self.evidence["executions"] = []
        self.evidence["observed_at"] = "2026-10-25T06:45:00Z"
        self.check("missing")

    def test_observation_before_deadline_cannot_prove_missing_after_it(self):
        self.evidence["bindings"] = []; self.evidence["executions"] = []
        self.evidence["observed_at"] = "2026-10-25T06:44:00Z"
        self.check("waiting", now="2026-10-25T06:46:00Z")

    def test_yesterday_success_does_not_cover_today(self):
        old = bundle(expected_slot("morning", date(2026,10,24)))
        self.check("missing", evidence=old)

    def test_manual_success_does_not_cover_ordinary(self):
        self.evidence["bindings"] = []
        self.evidence["executions"][0]["origin"] = "manual"
        self.check("missing")

    def test_nearby_execution_or_worker_context_does_not_prove_origin(self):
        self.evidence["bindings"] = []
        self.evidence["executions"][0]["summary"]["execution_context"] = {"origin":"scheduler"}
        self.check("origin_unverified")

    def test_wrong_job_scheduler_or_slot_cannot_bind(self):
        for key,value in (("scheduler","other"),("job","other"),("scheduled_at","2026-10-24T05:30:00Z"),
                          ("basis","timestamp_correlation")):
            with self.subTest(key=key):
                b=deepcopy(self.evidence); b["bindings"][0][key]=value
                self.check("origin_unverified", evidence=b)

    def test_duplicate_log_binding_is_idempotent_but_two_executions_ambiguous(self):
        self.evidence["bindings"].append(deepcopy(self.evidence["bindings"][0]))
        self.check("completed")
        self.evidence["bindings"][1]["execution"] += "x"
        self.check("ambiguous")

    def test_running_and_running_late(self):
        self.evidence["executions"][0]["completed_at"] = None
        self.check("running_late")
        self.evidence["observed_at"] = "2026-10-25T06:35:00Z"
        self.check("running")

    def test_late_success_is_distinct_and_recovers_current_alarm(self):
        self.evidence["executions"][0]["completed_at"] = "2026-10-25T06:46:00Z"
        result=self.check("completed_late")
        self.assertFalse(result["attention"])
        self.assertTrue(result["completion_late"])

    def test_fcm_acceptance_is_not_device_delivery(self):
        result=self.check("completed", "fcm_accepted")
        self.assertEqual(result["delivery"]["sent"],2)
        self.assertIsNone(result["source_trace"])

    def test_no_audience_and_deduplication_are_valid_distinct_outcomes(self):
        self.evidence["executions"][0]["summary"] = summary(status="no_eligible_device",eligible_devices=0,attempted=0,sent=0)
        self.check("completed", "no_eligible_device")
        self.evidence["executions"][0]["summary"] = summary(status="deduplicated", sent=0, deduplicated=2)
        self.check("completed", "deduplicated")

    def test_partial_preserves_accepted_fcm_even_with_failed_runtime(self):
        e=self.evidence["executions"][0]; e["runtime_status"]="failed"
        e["summary"]=summary(status="partial",sent=1,failed=1)
        self.check("partial", "delivery_incomplete")

    def test_unconfirmed_or_retry_never_counts_as_completed(self):
        e=self.evidence["executions"][0]
        e["summary"]=summary(sent=1,sent_unconfirmed=1)
        self.check("partial")
        e["summary"]=summary(status="sent",sent=1,retry_scheduled=1)
        self.check("delivery_pending")

    def test_disabled_dry_run_and_missing_forecast_not_green(self):
        for status,state in (("disabled","inactive"),("dry_run","inactive"),("no_forecast","no_forecast")):
            self.evidence["executions"][0]["summary"]=summary(status=status,sent=0)
            self.check(state)

    def test_runtime_failure_without_summary_and_inconsistent_success(self):
        e=self.evidence["executions"][0]; e["runtime_status"]="failed"
        self.check("failed", "runtime_application_conflict")
        e["summary"]=None
        self.check("failed", "runtime_failure")
        e["runtime_status"]="succeeded"
        self.check("check_unavailable", "application_result_missing")

    def test_terminal_counts_cannot_hide_unaccounted_devices(self):
        self.evidence["executions"][0]["summary"] = summary(sent=1)
        self.check("check_unavailable")
        self.evidence["executions"][0]["summary"] = summary(sent=1,opted_out=1)
        self.check("completed")
        self.evidence["executions"][0]["summary"] = summary(status="retired_targets",sent=0,retired_targets=2)
        self.check("completed","retired_targets")

    def test_eligible_device_without_attempt_cannot_be_complete(self):
        for status, counts in (("sent", {"sent": 1}),
                               ("deduplicated", {"sent": 0, "deduplicated": 1}),
                               ("opted_out", {"sent": 0, "opted_out": 1}),
                               ("retired_targets", {"sent": 0, "retired_targets": 1})):
            with self.subTest(status=status):
                self.evidence["executions"][0]["summary"] = summary(status=status, attempted=1, **counts)
                self.check("check_unavailable", "evidence_invalid")

    def test_legacy_missing_trace_allowed_but_explicit_invalid_trace_rejected(self):
        self.check("completed")
        for trace in (None, "private", [], False, {"fetched_groups": 0}):
            with self.subTest(trace=trace):
                self.evidence["executions"][0]["summary"]["source_trace"] = trace
                self.check("check_unavailable", "evidence_invalid")

    def test_failure_and_conflicting_execution_identity(self):
        e=self.evidence["executions"][0]
        e["summary"]=summary(status="failed",sent=0,failed=2)
        e["runtime_status"]="failed"
        self.check("failed")
        e["origin"]="manual"
        self.check("check_unavailable")

    def test_bad_counts_never_green(self):
        for value in (None, True, -1, "2", float("nan"),float("inf")):
            with self.subTest(value=value):
                b=deepcopy(self.evidence); b["executions"][0]["summary"]["sent"]=value
                self.check("check_unavailable", evidence=b)

    def test_incomplete_stale_future_or_truncated_inventory_not_missing(self):
        for key,value in (("complete",False),("schema_version",True),
                          ("window_start","2026-10-25T06:31:00Z"),("window_end","2026-10-25T06:49:59Z")):
            b=deepcopy(self.evidence);b[key]=value
            self.check("check_unavailable",evidence=b)
        self.check("check_unavailable",now="2026-10-25T07:00:00Z")
        self.check("check_unavailable",now="2026-10-25T06:49:00Z")

    def test_naive_dates_and_modified_schedule_rejected(self):
        with self.assertRaises(ValueError):latest_slots("2026-10-25T07:30:00")
        self.slot["scheduled_at"]="2026-10-25T07:30:00Z"
        with self.assertRaises(ValueError):self.check("completed")

    def test_malicious_evidence_fields_not_echoed(self):
        e=self.evidence["executions"][0];e["summary"]["token"]="PRIVATE"
        e["private"]="PRIVATE";self.evidence["private"]="PRIVATE"
        self.assertNotIn("PRIVATE",json.dumps(self.check("completed")))

    def test_cli_reads_only_local_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"evidence.json";path.write_text(json.dumps(self.evidence),encoding="utf-8")
            output=io.StringIO()
            with patch("socket.socket",side_effect=AssertionError("network forbidden")),redirect_stdout(output):
                code=main(["--evidence",str(path),"--local-date","2026-10-25"])
            self.assertEqual(code,0)
            result=json.loads(output.getvalue())
            self.assertEqual([x["state"] for x in result["evaluations"]],["completed","not_due"])


if __name__ == "__main__":
    unittest.main()
