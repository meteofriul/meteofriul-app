"""Offline regressions for the observed Cloud Run cold-start latency."""
import unittest
from unittest.mock import Mock

from freshness_monitor.collect import Budget, Collector
from freshness_monitor.core import evaluate
from freshness_monitor.google import PublicHTTP, Transport
from test_freshness_monitor import Fixture, NOW


class Clock:
    value = 0.0
    def __call__(self):
        return self.value


class Response:
    status_code = 200
    headers = {"content-type": "application/json"}
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def iter_content(self, size):
        yield self.body


class DelayedSession:
    def __init__(self, fixture, clock, delay, *, status=200, error=None):
        self.fixture, self.clock, self.delay = fixture, clock, delay
        self.status, self.error, self.calls = status, error, []
    def request(self, method, url, *, timeout, **kwargs):
        self.calls.append(timeout)
        if self.error:
            raise self.error
        self.clock.value += min(self.delay, timeout)
        if self.delay > timeout:
            raise TimeoutError("private request URL/token must not be logged")
        response = Response(self.fixture.public[url])
        response.status_code = self.status
        return response


class ColdStartTests(unittest.TestCase):
    def collect(self, product="fvg", *, delay=11.4, status=200, error=None, budget_seconds=75):
        fixture, clock = Fixture(), Clock()
        session = DelayedSession(fixture, clock, delay, status=status, error=error)
        collector = Collector(fixture, PublicHTTP(Transport(session)), now=lambda: NOW,
            budget=Budget(budget_seconds, clock=clock), catalog_pair=fixture.catalog_pair)
        return collector.collect(product), session, clock

    def test_observed_cold_start_completes_without_false_critical(self):
        obs, session, clock = self.collect()
        self.assertTrue(obs["complete"])
        self.assertEqual(obs["critical_causes"], [])
        self.assertEqual(session.calls, [15])
        self.assertEqual(obs["http_comparison"]["ordinary"]["attempts"], 1)
        self.assertEqual(evaluate("fvg", NOW, NOW, obs)["critical_active"], 0)

    def test_national_pointer_and_resolver_fit_existing_product_budget(self):
        obs, session, clock = self.collect("national", delay=12)
        self.assertTrue(obs["complete"])
        self.assertEqual(session.calls, [15, 15])
        self.assertLess(clock.value, 35)

    def test_persistent_timeout_still_raises_critical_after_one_retry(self):
        obs, session, clock = self.collect(delay=16)
        self.assertEqual(session.calls, [15, 15])
        self.assertEqual(clock.value, 30)
        self.assertIn("http_pointer_unreadable", obs["critical_causes"])
        entry = obs["http_comparison"]["ordinary"]
        self.assertEqual(entry["failure_kind"], "timeout")
        self.assertEqual(entry["attempts"], 2)
        self.assertNotIn("private", str(obs))
        self.assertEqual(evaluate("fvg", NOW, NOW, obs)["critical_active"], 1)

    def test_remaining_budget_caps_read_and_never_claims_recovery(self):
        obs, session, clock = self.collect(delay=10, budget_seconds=3)
        self.assertEqual(session.calls, [3])
        self.assertLessEqual(clock.value, 3)
        self.assertFalse(obs["complete"])
        self.assertTrue(obs["indeterminate"])
        self.assertTrue(obs["budget_exhausted"])

    def test_http_errors_and_sensitive_exception_remain_failed_and_sanitized(self):
        for options, attempts, kind in [({"status": 503, "delay": 0}, 2, "http_status"),
                                        ({"status": 403, "delay": 0}, 1, "http_status"),
                                        ({"error": ConnectionError("secret-token")}, 2, "connection")]:
            with self.subTest(options=options):
                obs, session, clock = self.collect(**options)
                entry = obs["http_comparison"]["ordinary"]
                self.assertEqual(entry["attempts"], attempts)
                self.assertEqual(entry["failure_kind"], kind)
                self.assertFalse(obs["complete"])
                self.assertNotIn("secret-token", str(obs))

    def test_google_api_timeout_remains_five_seconds(self):
        session = Mock()
        session.request.return_value = Response(b"{}")
        transport = Transport(session)
        transport.read_json("https://example.invalid/google", Budget())
        self.assertEqual(session.request.call_args.kwargs["timeout"], 5)


if __name__ == "__main__":
    unittest.main()
