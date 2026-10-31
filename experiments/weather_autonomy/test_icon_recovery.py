"""Offline recovery state-machine tests; no Cloud SDK or network required."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest import TestCase, main
from unittest.mock import Mock, patch

from local_pipeline.contract_v1 import canonical_json_bytes
from local_pipeline.icon_recovery import Recovery, FenceLost, FEATURE_FLAG, enabled, window, result
from local_pipeline.sqlite_object_store import SQLiteObjectStore

NOW = datetime(2026, 10, 31, 6, tzinfo=timezone.utc)
RUN = "20261031T000000Z"
PM = "20261031T120000Z"


class RecoveryTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = SQLiteObjectStore(Path(self.temp.name) / "state.sqlite")
        self.recovery = Recovery(self.state, "fvg")
        self.checkpoints = {}
        self.published = []
        self.discover = Mock(return_value="2026103100")
        self.acquisitions = []

    def checkpoint(self, cycle, slot):
        return self.checkpoints.get((cycle, slot))

    def acquire(self, cycle, slot):
        self.acquisitions.append(cycle)
        frozen = {"cycle": cycle}
        self.checkpoints[(cycle, slot)] = frozen
        return frozen

    def publish(self, frozen):
        self.published.append(frozen["cycle"])
        return result("published", "publication_committed", frozen["cycle"])

    def call(self, *, now=NOW, execution="owner-one", **overrides):
        args = dict(now=now, execution=execution, high_water=max(self.published) if self.published else None,
            verified_run=max(self.published) if self.published else None, discover=self.discover,
            checkpoint=self.checkpoint, acquire=self.acquire, publish=self.publish,
            verify=lambda cycle: cycle in self.published)
        args.update(overrides)
        return self.recovery.run(**args)

    def test_default_off_and_strict_opt_in(self):
        self.assertFalse(enabled({}))
        self.assertFalse(enabled({FEATURE_FLAG: "false"}))
        self.assertTrue(enabled({FEATURE_FLAG: "true"}))
        for value in ("TRUE", "1", "", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                enabled({FEATURE_FLAG: value})

    def test_windows_are_utc_bounded_and_same_poll_within_hour(self):
        self.assertEqual([hour for hour in range(24) if window(NOW.replace(hour=hour))], [6,7,8,10,18,19,20,22])
        self.assertEqual(window(NOW), window(NOW.replace(minute=59, second=59)))
        self.assertEqual(window(NOW.replace(hour=22))["offset_hours"], 4)
        with self.assertRaises(ValueError): window(NOW.replace(tzinfo=None))

    def test_missing_source_does_not_claim_acquisition_and_recovers_at_four_hours(self):
        self.discover.side_effect = [None, None, None, "2026103100"]
        statuses=[]
        for offset in (0, 1, 2, 4):
            statuses.append(self.call(now=NOW+timedelta(hours=offset), execution=f"owner-{offset}")["status"])
            if offset < 4:
                self.assertIsNone(self.recovery.active())
                self.assertEqual(self.acquisitions, [])
        self.assertEqual(statuses, ["pending", "pending", "pending", "published"])
        self.assertEqual(self.acquisitions, [RUN])
        self.assertEqual(len(self.state.list_keys(self.recovery.prefix+"runs/")), 1)

    def test_cloud_task_retry_and_duplicate_execution_reuse_poll(self):
        self.discover.return_value = None
        first=self.call()
        for execution in ("owner-one", "owner-one", "owner-two"):
            self.assertEqual(self.call(execution=execution), first)
        self.discover.assert_called_once()
        self.assertIsNone(self.recovery.active())

    def test_transport_budget_is_two_per_poll_not_per_task_retry(self):
        self.discover.side_effect = TimeoutError()
        with patch("local_pipeline.icon_recovery.sleep") as sleep:
            self.assertEqual(self.call()["reason"], "source_transport_pending")
            self.call(execution="owner-two")
            self.assertEqual(self.discover.call_count, 2)
            self.call(now=NOW+timedelta(hours=1), execution="owner-three")
            self.assertEqual(self.discover.call_count, 4)
            self.assertEqual(sleep.call_count, 2)
        self.assertEqual(self.acquisitions, [])

    def test_hard_probe_error_is_review_not_retry_or_claim(self):
        self.discover.side_effect = ValueError("malformed source")
        self.assertEqual(self.call()["status"], "manual_review")
        self.discover.assert_called_once()
        self.assertIsNone(self.recovery.active())

    def test_outside_schedule_cannot_probe_or_acquire(self):
        self.assertEqual(self.call(now=NOW.replace(hour=11))["reason"], "outside_recovery_window")
        self.discover.assert_not_called()
        self.assertEqual(self.state.list_keys(self.recovery.prefix+"polls/"), [])
        self.assertIsNone(self.recovery.active())

    def test_task_retry_across_hour_and_outside_window_keeps_original_poll(self):
        self.discover.return_value = None
        first = self.call()
        for hours in (1, 3, 12, 24):
            self.assertEqual(self.call(now=NOW+timedelta(hours=hours)), first)
        self.discover.assert_called_once()
        self.assertEqual(len(self.state.list_keys(self.recovery.prefix+"polls/")),1)

    def test_execution_started_outside_window_cannot_spend_later_poll(self):
        self.call(now=NOW.replace(hour=5))
        self.assertEqual(self.call()["reason"], "outside_recovery_window")
        self.discover.assert_not_called()

    def test_remote_store_temporary_error_keeps_complete_checkpoint_resumable(self):
        from local_pipeline.gcs_object_store import RemoteObjectStoreError
        error=RemoteObjectStoreError("temporary",original_type="ServiceUnavailable",http_status=503,retryable=True)
        self.assertEqual(self.call(publish=Mock(side_effect=error))["status"],"pending")
        self.assertEqual(self.recovery.active().record["phase"],"checkpointed")

    def test_older_or_future_source_never_acquires(self):
        self.discover.return_value = "2026103012"
        self.assertEqual(self.call()["status"], "pending")
        self.discover.return_value = "2026110100"
        self.assertEqual(self.call(now=NOW+timedelta(hours=1), execution="owner-two")["reason"], "source_cycle_in_future")
        self.assertEqual(self.acquisitions, [])

    def test_source_regression_against_verified_high_water_fails_closed(self):
        self.assertEqual(self.call(high_water=RUN)["status"], "manual_review")
        self.assertEqual(self.acquisitions, [])

    def test_duplicate_while_acquiring_does_not_claim_next_window(self):
        entered, release = Event(), Event()
        def acquire(cycle, slot):
            entered.set()
            if not release.wait(5): raise AssertionError("test barrier timed out")
            return self.acquire(cycle, slot)
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.call, acquire=acquire)
            self.assertTrue(entered.wait(5))
            try:
                second=self.call(now=NOW+timedelta(hours=1), execution="owner-two")
                self.assertEqual(second["status"], "in_progress")
                self.assertEqual(len(self.state.list_keys(self.recovery.prefix+"polls/")), 1)
            finally: release.set()
            self.assertEqual(first.result(timeout=5)["status"], "published")
        self.assertEqual(self.acquisitions, [RUN])

    def test_abandoned_owner_is_never_released_by_clock_or_new_cycle(self):
        with self.assertRaises(KeyboardInterrupt):
            self.call(acquire=Mock(side_effect=KeyboardInterrupt()))
        before = self.recovery.active()
        outcome=self.call(now=NOW+timedelta(days=5), execution="owner-new")
        self.assertEqual(outcome["status"], "in_progress")
        self.assertEqual(self.recovery.active(), before)
        self.assertEqual(self.discover.call_count, 1)

    def test_complete_checkpoint_resumes_before_source_probe_even_outside_window(self):
        def freeze_then_die(cycle, slot):
            self.acquire(cycle, slot)
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.call(acquire=freeze_then_die)
        self.discover.side_effect=AssertionError("source must not be contacted")
        self.assertEqual(self.call(now=NOW.replace(hour=9), execution="owner-two")["status"], "published")
        self.assertEqual(self.acquisitions, [RUN])
        self.assertEqual(self.discover.call_count, 1)

    def test_corrupt_checkpoint_never_reacquires_or_releases_owner(self):
        with self.assertRaises(KeyboardInterrupt): self.call(acquire=Mock(side_effect=KeyboardInterrupt()))
        before=self.recovery.active()
        with self.assertRaises(ValueError):
            self.call(execution="owner-two", checkpoint=Mock(side_effect=ValueError("corrupt")))
        self.assertEqual(before, self.recovery.active())
        self.assertEqual(self.discover.call_count, 1)

    def test_quality_failure_blocks_later_acquisitions(self):
        self.assertEqual(self.call(acquire=Mock(side_effect=ValueError("quality")))["status"], "manual_review")
        self.assertEqual(self.call(now=NOW+timedelta(hours=12), execution="owner-two")["status"], "manual_review")
        self.assertEqual(self.discover.call_count, 1)

    def test_publication_transport_failure_reuses_checkpoint(self):
        outcome=self.call(publish=Mock(side_effect=TimeoutError()))
        self.assertEqual(outcome["status"], "pending")
        self.assertEqual(self.recovery.active().record["phase"], "checkpointed")
        self.assertEqual(self.call(execution="owner-two")["status"], "published")
        self.assertEqual(self.acquisitions, [RUN])

    def test_success_without_readback_is_manual_review(self):
        outcome=self.call(publish=lambda _: result("published", "claimed", RUN), verify=lambda _:False)
        self.assertEqual(outcome["reason"], "publication_readback_failed")
        self.assertEqual(self.recovery.active().record["phase"], "manual_review")

    def test_stale_owner_cannot_complete_after_checkpoint_handoff(self):
        first=self.recovery.begin(None,RUN,"20261031-am","owner-one")
        next_owner=self.recovery.replace(first,{**first.record,"phase":"checkpointed","execution":"owner-two","fence":"a"*32})
        with self.assertRaises(FenceLost): self.recovery.transition(first,"completed")
        self.assertEqual(self.recovery.active(),next_owner)

    def test_completed_product_advances_once_and_products_are_independent(self):
        self.assertEqual(self.call()["status"],"published")
        self.assertEqual(self.call(execution="owner-two")["reason"],"publication_already_verified")
        self.discover.return_value="2026103112"
        self.assertEqual(self.call(now=NOW+timedelta(hours=12),execution="owner-three")["status"],"published")
        self.assertEqual(self.acquisitions,[RUN,PM])
        national=Recovery(self.state,"national")
        self.assertIsNone(national.active())
        self.assertIsNotNone(national.begin(None,RUN,"20261031-am","national-one"))

    def test_legacy_unknown_claim_is_not_adopted(self):
        legacy=Mock(return_value={"checkpoint":None,"slot":"20261031-am"})
        self.assertEqual(self.call(legacy=legacy)["reason"],"legacy_acquisition_owner_unresolved")
        self.discover.assert_not_called()
        self.assertEqual(self.acquisitions,[])

    def test_legacy_complete_checkpoint_is_adopted_without_discovery(self):
        frozen={"cycle":RUN}
        old={"checkpoint":frozen,"source_run_id":RUN,"slot":"20261031-am"}
        self.assertEqual(self.call(legacy=lambda:old)["status"],"published")
        self.discover.assert_not_called()
        self.assertEqual(self.acquisitions,[])

    def test_poll_crash_is_not_reprobed_by_task_retry(self):
        self.discover.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.call()
        self.assertEqual(self.call()["status"],"in_progress")
        self.assertEqual(self.discover.call_count,1)

    def test_corrupt_durable_state_fails_closed(self):
        self.state.put(self.recovery.key,b'{}',content_type='application/json')
        with self.assertRaises(ValueError):self.call()
        self.discover.assert_not_called()


if __name__ == "__main__": main()
