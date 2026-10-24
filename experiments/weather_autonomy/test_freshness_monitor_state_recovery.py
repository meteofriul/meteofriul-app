"""Offline recovery of Storage errors, without weather or notification writes."""
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock

from freshness_monitor.collect import Budget, BudgetExpired, Unavailable
from freshness_monitor.google import MonitorState, json_bytes
from freshness_monitor.runner import Conflict, Runner
from test_freshness_monitor import MemoryMetrics, NOW, observation


class StorageTransport:
    def __init__(self, faults=None):
        self.generation, self.value = "0", None
        self.faults = faults or {}
        self.posts = []
        self.fail_read = False

    def request(self, method, url, budget, **kwargs):
        budget.remaining()
        if method == "GET":
            if self.fail_read:
                raise Unavailable("state read unavailable", transient=True)
            if self.value is None:
                return 404, b"{}", {}
            if kwargs.get("params", {}).get("alt") == "media":
                assert kwargs["params"]["generation"] == self.generation
                return 200, json_bytes(self.value), {}
            return 200, json_bytes({"generation": self.generation}), {}
        assert method == "POST"
        self.posts.append(deepcopy(kwargs))
        fault = self.faults.get(len(self.posts))
        if isinstance(fault, int):
            return fault, b"private response must not appear in logs", {}
        if kwargs["params"]["ifGenerationMatch"] != self.generation:
            return 412, b"{}", {}
        self.generation = str(int(self.generation) + 1)
        self.value = json.loads(kwargs["data"])
        if fault == "concurrent":
            self.value = {"newer": True}
            return 503, b"{}", {}
        if fault in ("lost", "unreadable"):
            self.fail_read = fault == "unreadable"
            raise Unavailable("request absolute deadline exceeded", transient=True,
                              failure_kind="timeout")
        return 200, json_bytes({"generation": self.generation}), {}


class StateRecoveryTests(unittest.TestCase):
    def test_transient_status_retries_same_generation_and_bytes(self):
        for status in (408, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                transport, sleep = StorageTransport({1: status}), Mock()
                state = MonitorState(transport, sleep=sleep)
                self.assertEqual(state.cas("fvg", "0", {"value": 1}, Budget()), "1")
                self.assertEqual(transport.posts[0], transport.posts[1])
                sleep.assert_called_once_with(1)

    def test_lost_acknowledgement_reads_back_without_writing_twice(self):
        transport, sleep = StorageTransport({1: "lost"}), Mock()
        state = MonitorState(transport, sleep=sleep)
        self.assertEqual(state.cas("fvg", "0", {"value": 1}, Budget()), "1")
        self.assertEqual(len(transport.posts), 1)
        sleep.assert_not_called()

    def test_concurrent_value_is_never_overwritten_or_acknowledged(self):
        transport = StorageTransport({1: "concurrent"})
        with self.assertRaises(Conflict):
            MonitorState(transport, sleep=Mock()).cas("fvg", "0", {"value": 1}, Budget())
        self.assertEqual(transport.value, {"newer": True})
        self.assertEqual(len(transport.posts), 1)

    def test_unreadable_uncertain_commit_is_not_reported_as_success(self):
        transport = StorageTransport({1: "unreadable"})
        with self.assertRaises(Unavailable):
            MonitorState(transport, sleep=Mock()).cas("fvg", "0", {"value": 1}, Budget())
        self.assertEqual(len(transport.posts), 1)

    def test_persistent_failure_has_bounded_attempts_and_safe_status(self):
        transport, sleep = StorageTransport({1: 429, 2: 429, 3: 429}), Mock()
        with self.assertRaisesRegex(Unavailable, '^monitor state commit HTTP 429$'):
            MonitorState(transport, sleep=sleep).cas("fvg", "0", {"value": 1}, Budget())
        self.assertEqual(len(transport.posts), 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])
        self.assertIsNone(transport.value)

    def test_permanent_failure_is_not_retried(self):
        for status in (400, 401, 403, 404):
            with self.subTest(status=status):
                transport, sleep = StorageTransport({1: status}), Mock()
                with self.assertRaisesRegex(Unavailable, f'HTTP {status}$'):
                    MonitorState(transport, sleep=sleep).cas("fvg", "0", {}, Budget())
                self.assertEqual(len(transport.posts), 1)
                sleep.assert_not_called()

    def test_recovery_cannot_extend_existing_deadline(self):
        transport, sleep = StorageTransport({1: 429}), Mock()
        with self.assertRaises(BudgetExpired):
            MonitorState(transport, sleep=sleep).cas("fvg", "0", {}, Budget(seconds=0.5))
        self.assertEqual(len(transport.posts), 1)
        sleep.assert_not_called()

    def test_metric_prepare_and_finish_recover_without_duplicate_metrics(self):
        # Initial evaluation, metric preparation and completion use the same CAS.
        for call in (1, 2, 3, 4, 5, 6, 7):
            for fault in (429, "lost"):
                with self.subTest(call=call, fault=fault):
                    transport = StorageTransport({call: fault})
                    state = MonitorState(transport, sleep=Mock())
                    metrics, collector, logs = MemoryMetrics(), Mock(), []
                    collector.collect.return_value = observation()
                    runner = Runner(state, metrics, collector, now=lambda: NOW,
                                    budget=Budget(), emit=logs.append)
                    result = runner.run_product("national", NOW)
                    self.assertTrue(all(p["status"] == "confirmed"
                                        for p in result["outbox"].values()))
                    self.assertEqual(len(metrics.writes), 3)
                    runner.run_product("national", NOW)
                    self.assertEqual(len(metrics.writes), 3)
                    self.assertEqual(collector.collect.call_count, 1)


if __name__ == "__main__":
    unittest.main()
