"""Offline national-only operator supersession tests; no cloud client or job."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import Mock, patch

from local_pipeline.contract_v1 import canonical_json_bytes
from local_pipeline.icon_recovery import FenceLost, Recovery, result
from local_pipeline.sqlite_object_store import ObjectNotFound, ObjectStoreError, PreconditionFailed, SQLiteObjectStore


NOW = datetime(2026, 11, 25, 15, tzinfo=timezone.utc)
PUBLISHED = "20261121T000000Z"
FAILED = "20261121T120000Z"
NEW = "20261125T000000Z"
INCIDENT = "a" * 32


class OperatorRecoveryTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = SQLiteObjectStore(Path(self.temp.name) / "state.sqlite")
        self.recovery = Recovery(self.state, "national")
        original = self.recovery.begin(None, FAILED, "20261121-pm", "national-old")
        self.old = self.recovery.transition(original, "manual_review")
        self.prepared = {}
        self.published = {PUBLISHED}
        self.acquire = Mock(side_effect=self.freeze)
        self.discover = Mock(return_value="2026112500")
        self.quiescent = Mock(return_value=self.guard())
        self.current_run = Mock(return_value=PUBLISHED)

    def guard(self, **changes):
        value = {"scheduler_paused": True, "active_executions": 0,
            "deployed_fence_aware": True, "legacy_invocations_blocked": True,
            "observed_at_utc": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evidence_sha256": "c" * 64}
        value.update(changes)
        return value

    def freeze(self, cycle, slot):
        self.prepared[(cycle, slot)] = {"cycle": cycle}
        return self.prepared[(cycle, slot)]

    def checkpoint(self, cycle, slot):
        return self.prepared.get((cycle, slot))

    def publish(self, prepared):
        self.published.add(prepared["cycle"])
        self.current_run.return_value = prepared["cycle"]
        return result("published", "publication_committed", prepared["cycle"])

    def call(self, **overrides):
        args = dict(now=NOW, incident_id=INCIDENT, expected_etag=self.old.etag,
            expected_owner_sha256=hashlib.sha256(canonical_json_bytes(self.old.record)).hexdigest(),
            failed_run=FAILED, new_run=NEW, published_run=PUBLISHED,
            execution="national-operator-one", quiescent=self.quiescent,
            guard_clock=lambda: NOW,
            current_run=self.current_run, discover=self.discover,
            failed_cycle_evidence=lambda _: {"intent": True, "mapping": False,
                                              "prepared": False, "manifest": False},
            checkpoint=self.checkpoint, acquire=self.acquire, publish=self.publish,
            verify=lambda cycle: cycle in self.published)
        args.update(overrides)
        return self.recovery.supersede_manual_review(**args)

    def incident(self):
        key = self.recovery.prefix + f"incidents/{INCIDENT}.json"
        return json.loads(self.state.get(key).body)

    def claim(self):
        return self.state.get(self.recovery.prefix + f"runs/{NEW}/acquisition.json")

    def test_exact_incident_and_generation_cas_publish_once(self):
        outcome = self.call()
        self.assertEqual(outcome["status"], "published")
        self.assertEqual(self.recovery.active().record["phase"], "completed")
        incident = self.incident()
        self.assertEqual(incident["failed_owner"], self.old.record)
        self.assertEqual(incident["failed_owner_etag"], self.old.etag)
        self.assertEqual(incident["quiescence_at_creation"], self.guard())
        self.assertEqual(incident["new_owner"]["source_run_id"], NEW)
        self.assertEqual(json.loads(self.claim().body), incident["new_owner"])
        self.assertEqual(self.acquire.call_count, 1)
        self.assertEqual(self.call()["reason"], "operator_publication_already_completed")
        self.assertEqual(self.acquire.call_count, 1)
        self.assertEqual(self.published, {PUBLISHED, NEW})

    def test_guard_clock_tracks_checks_after_operation_start(self):
        checked = datetime(2026, 11, 25, 15, 0, 20, tzinfo=timezone.utc)
        observed = self.guard(observed_at_utc="2026-11-25T15:00:15Z")
        order = []
        def quiescent():
            order.append("cloud_read")
            return observed
        def guard_clock():
            order.append("clock_read")
            return checked
        outcome = self.call(quiescent=quiescent, guard_clock=guard_clock)
        self.assertEqual(outcome["status"], "published")
        self.assertEqual(self.incident()["quiescence_at_creation"], observed)
        self.assertEqual(order, ["cloud_read", "clock_read"] * 3)

    def test_wrong_product_identity_generation_and_cycle_refuse_before_incident(self):
        for changes in ({"expected_etag": "1"}, {"expected_owner_sha256": "b" * 64},
                        {"failed_run": PUBLISHED}, {"new_run": FAILED},
                        {"incident_id": "bad"}, {"published_run": FAILED}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, FenceLost)):
                self.call(**changes)
        with self.assertRaises(ValueError):
            Recovery(self.state, "fvg").supersede_manual_review(**self.args_for_fvg())
        self.assertEqual(self.recovery.active(), self.old)
        with self.assertRaises(ObjectNotFound): self.incident()

    def args_for_fvg(self):
        # Reuse the exact caller arguments; product gate must run before reads.
        return dict(now=NOW, incident_id=INCIDENT, expected_etag=self.old.etag,
            expected_owner_sha256=hashlib.sha256(canonical_json_bytes(self.old.record)).hexdigest(),
            failed_run=FAILED, new_run=NEW, published_run=PUBLISHED,
            execution="national-operator-one", quiescent=self.quiescent,
            guard_clock=lambda: NOW,
            current_run=self.current_run, discover=self.discover,
            failed_cycle_evidence=lambda _: {}, checkpoint=self.checkpoint,
            acquire=self.acquire, publish=self.publish,
            verify=lambda cycle: cycle in self.published)

    def test_missing_or_conflicting_evidence_never_changes_owner(self):
        cases = ({"quiescent": lambda: False},
                 {"quiescent": lambda: self.guard(scheduler_paused=False)},
                 {"quiescent": lambda: self.guard(active_executions=1)},
                 {"quiescent": lambda: self.guard(deployed_fence_aware=False)},
                 {"quiescent": lambda: self.guard(legacy_invocations_blocked=False)},
                 {"quiescent": lambda: self.guard(observed_at_utc="2026-11-25T14:58:00Z")},
                 {"current_run": lambda: FAILED},
                 {"discover": lambda _: "2026112412"},
                 {"failed_cycle_evidence": lambda _: {"intent": False}},
                 {"checkpoint": lambda *_: {"cycle": FAILED}})
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises((ValueError, FenceLost)):
                self.call(**changes)
            self.assertEqual(self.recovery.active(), self.old)
        with patch.object(self.state, "get", side_effect=lambda key, get=self.state.get: (
                (_ for _ in ()).throw(ObjectNotFound(key)) if key.endswith(f"runs/{FAILED}/acquisition.json")
                else get(key))):
            with self.assertRaises(ObjectNotFound): self.call()
        self.assertEqual(self.recovery.active(), self.old)
        self.acquire.assert_not_called()

    def test_lost_cas_response_reconciles_exact_new_owner(self):
        original = self.state.compare_and_swap
        losses = []
        def lose(key, body, **kwargs):
            response = original(key, body, **kwargs)
            if key == self.recovery.key and not losses:
                losses.append(True)
                raise ObjectStoreError("response lost")
            return response
        with patch.object(self.state, "compare_and_swap", side_effect=lose):
            self.assertEqual(self.call()["status"], "published")
        self.assertEqual(len(losses), 1)
        self.assertEqual(self.acquire.call_count, 1)
        self.assertEqual(self.recovery.active().record["phase"], "completed")

    def test_lost_incident_create_response_reconciles_exact_bytes(self):
        original = self.state.put
        losses = []
        def lose(key, body, **kwargs):
            response = original(key, body, **kwargs)
            if key.endswith(f"incidents/{INCIDENT}.json") and not losses:
                losses.append(True)
                raise ObjectStoreError("response lost")
            return response
        with patch.object(self.state, "put", side_effect=lose):
            self.assertEqual(self.call()["status"], "published")
        self.assertEqual(len(losses), 1)
        self.assertEqual(self.acquire.call_count, 1)

    def test_guard_revoked_after_cas_leaves_claim_absent_until_safe_retry(self):
        guards = [self.guard(), self.guard(), self.guard(scheduler_paused=False)]
        def guard():
            return guards.pop(0)
        with self.assertRaises(FenceLost):
            self.call(quiescent=guard)
        self.assertEqual(self.recovery.active().record["phase"], "acquiring")
        with self.assertRaises(ObjectNotFound): self.claim()
        self.acquire.assert_not_called()
        self.assertEqual(self.call()["status"], "published")
        self.assertEqual(self.acquire.call_count, 1)

    def test_crash_after_cas_before_claim_retries_same_incident_once(self):
        original = self.recovery.create_record
        interrupted = []
        def crash(key, record):
            if key.endswith(f"runs/{NEW}/acquisition.json") and not interrupted:
                interrupted.append(True)
                raise KeyboardInterrupt()
            return original(key, record)
        with patch.object(self.recovery, "create_record", side_effect=crash):
            with self.assertRaises(KeyboardInterrupt): self.call()
        self.assertEqual(self.recovery.active().record["phase"], "acquiring")
        with self.assertRaises(ObjectNotFound): self.claim()
        self.assertEqual(self.call()["status"], "published")
        self.assertEqual(self.acquire.call_count, 1)
        self.assertEqual(self.incident()["new_owner"]["fence"], json.loads(self.claim().body)["fence"])

    def test_crash_after_claim_never_reacquires_without_checkpoint(self):
        self.acquire.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.call()
        self.assertEqual(self.recovery.active().record["phase"], "acquiring")
        self.assertEqual(json.loads(self.claim().body)["source_run_id"], NEW)
        self.assertEqual(self.call()["reason"], "operator_acquisition_owner_unresolved")
        self.assertEqual(self.acquire.call_count, 1)
        self.assertEqual(self.published, {PUBLISHED})

    def test_complete_checkpoint_after_lost_acquisition_response_resumes_without_source(self):
        self.acquire.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.call()
        self.prepared[(NEW, "20261125-am")] = {"cycle": NEW}
        self.assertEqual(self.call()["status"], "published")
        self.assertEqual(self.acquire.call_count, 1)
        self.assertEqual(self.recovery.active().record["phase"], "completed")

    def test_concurrent_active_cas_conflict_leaves_only_incident(self):
        original = self.state.compare_and_swap
        def compete(key, body, **kwargs):
            if key == self.recovery.key and kwargs.get("expected_etag") == self.old.etag:
                competing = {**self.old.record, "execution": "another-owner", "fence": "b" * 32}
                original(key, canonical_json_bytes(competing), **kwargs)
                raise PreconditionFailed(key)
            return original(key, body, **kwargs)
        with patch.object(self.state, "compare_and_swap", side_effect=compete):
            with self.assertRaises(FenceLost): self.call()
        self.assertEqual(self.incident()["failed_owner"], self.old.record)
        self.assertEqual(self.recovery.active().record["execution"], "another-owner")
        with self.assertRaises(ObjectNotFound): self.claim()
        self.acquire.assert_not_called()

    def test_duplicate_incident_or_cycle_claim_fails_closed(self):
        self.state.put(self.recovery.prefix + f"runs/{NEW}/acquisition.json", b"{}")
        with self.assertRaises(FenceLost): self.call()
        self.assertEqual(self.recovery.active(), self.old)
        self.assertEqual(self.published, {PUBLISHED})


if __name__ == "__main__": main()
