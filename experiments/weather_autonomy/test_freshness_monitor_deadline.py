"""Real loopback sockets: no cloud, credentials or production data."""
from datetime import timedelta
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import os
import threading
import time
import unittest
from unittest.mock import Mock, patch

from freshness_monitor import __main__ as entry, contracts
from freshness_monitor.collect import Budget, BudgetExpired, Collector, Unavailable
from freshness_monitor.core import evaluate
from freshness_monitor.google import PublicHTTP, WeatherData
from freshness_monitor.http import Transport, PUBLIC_DOCUMENT_BYTES
from freshness_monitor.runner import Runner
from test_freshness_monitor import Fixture, MemoryState, MemoryMetrics, NOW, observation


def stalled_session_setup():
    # Models credential/metadata discovery before the worker becomes ready.
    time.sleep(3)
    raise RuntimeError("private credential setup detail")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        try:
            self.respond()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_POST(self):
        self.server.posts.append(self.path)
        self.do_GET()

    def respond(self):
        if self.path in {"/headers", "/post-held"}:
            self.server.stopped.wait(2)
        self.send_response(200)
        body = b'{"status":true}'
        if self.path == "/oversize-header":
            self.send_header("Content-Length", str(PUBLIC_DOCUMENT_BYTES + 1))
            self.end_headers()
            return
        if self.path == "/oversize-body":
            self.end_headers()
            self.wfile.write(b"x" * (PUBLIC_DOCUMENT_BYTES + 1))
            return
        if self.path == "/compressed":
            body = gzip.compress(b"x" * (PUBLIC_DOCUMENT_BYTES + 1))
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.path.startswith("/slow"):
            for byte in body:
                if self.server.stopped.is_set():
                    return
                self.wfile.write(bytes([byte]))
                self.wfile.flush()
                self.server.stopped.wait(0.1)
        else:
            self.wfile.write(body)


class DeadlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.daemon_threads = True
        cls.server.block_on_close = False
        cls.server.stopped = threading.Event()
        cls.server.posts = []
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.stopped.set()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=1)

    def transport(self):
        transport = Transport("public")
        self.addCleanup(transport.close)
        self.assertEqual(transport.request("GET", self.url + "/ok", Budget(5))[0], 200)
        return transport

    def test_dripping_body_and_stalled_headers_stop_at_absolute_request_deadline(self):
        for path in ("/slow-body", "/headers"):
            with self.subTest(path=path):
                transport = self.transport()
                process = transport._process
                started = time.monotonic()
                with self.assertRaises(Unavailable) as error:
                    transport.request("GET", self.url + path, Budget(3), timeout_seconds=0.45)
                self.assertLess(time.monotonic() - started, 0.8)
                self.assertEqual(error.exception.failure_kind, "timeout")
                self.assertIsNone(transport._process)
                self.assertTrue(process._closed)
                # A later read creates a fresh worker; no stale connection reuse.
                self.assertEqual(transport.request("GET", self.url + "/ok", Budget(5))[0], 200)

    def test_collection_deadline_stops_slow_body_with_cleanup_inside_allowance(self):
        transport = self.transport()
        started = time.monotonic()
        with self.assertRaises(BudgetExpired):
            transport.request("GET", self.url + "/slow-body", Budget(0.45), timeout_seconds=15)
        self.assertLess(time.monotonic() - started, 0.7)
        self.assertIsNone(transport._process)

    def test_credential_initialization_is_also_cancelled(self):
        transport = Transport(session_factory=stalled_session_setup)
        self.addCleanup(transport.close)
        started = time.monotonic()
        with self.assertRaises(Unavailable) as error:
            transport.request("GET", self.url + "/ok", Budget(3), timeout_seconds=0.45)
        self.assertLess(time.monotonic() - started, 0.8)
        self.assertEqual(error.exception.failure_kind, "timeout")
        self.assertNotIn("private", str(error.exception))
        self.assertIsNone(transport._process)

    def test_header_actual_and_decompressed_byte_caps(self):
        transport = self.transport()
        public = PublicHTTP(transport)
        for path in ("/oversize-header", "/oversize-body", "/compressed"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                public.get(self.url + path, {}, Budget(5))

    def test_uncertain_post_is_not_retried_by_transport(self):
        transport = self.transport()
        before = self.server.posts.count("/post-held")
        with self.assertRaises(Unavailable):
            transport.request("POST", self.url + "/post-held", Budget(3),
                              timeout_seconds=0.45, json={"synthetic": True})
        self.assertEqual(self.server.posts.count("/post-held"), before + 1)
        self.assertIsNone(transport._process)

    def test_storage_metadata_uses_the_same_cancellable_transport(self):
        transport = self.transport()
        data = WeatherData(transport)
        started = time.monotonic()
        with patch.object(data, "url", return_value=self.url + "/slow-body"):
            with self.assertRaises(BudgetExpired):
                data.get(contracts.ROOTS["fvg"] + "latest.json", Budget(0.45))
        self.assertLess(time.monotonic() - started, 0.7)
        self.assertIsNone(transport._process)

    def test_slow_collection_preserves_reserve_and_records_both_products(self):
        for source in ("public", "storage"):
            with self.subTest(source=source):
                transport = self.transport()
                fixture, state, metrics, logs = Fixture(), MemoryState(), MemoryMetrics(), []
                previous = NOW - timedelta(minutes=30)
                state.items["fvg"] = ("1", evaluate("fvg", previous, previous,
                    observation(complete=False, critical=["http_pointer_unreadable"])))
                data = fixture
                if source == "storage":
                    data = WeatherData(transport)
                    data.url = lambda key: self.url + "/slow-storage"
                app_budget = Budget(3)
                collection = app_budget.child(0.75, reserve=2.25)
                collector = Collector(data, PublicHTTP(transport), now=lambda: NOW,
                    budget=collection, catalog_pair=fixture.catalog_pair)
                with patch.dict(contracts.BASES, {p: self.url + "/slow-" + p + "/" for p in ("fvg", "national")}):
                    results = Runner(state, metrics, collector, now=lambda: NOW,
                        budget=app_budget, collection_budget=collection, emit=logs.append).run(NOW)
                self.assertGreater(app_budget.remaining(3), 2.0)
                self.assertEqual(len(metrics.writes), 6)
                for product, result in results.items():
                    self.assertEqual(result["check_state"], 3)
                    self.assertEqual(result["check_completed"], 1)
                    self.assertTrue(all(p["status"] == "confirmed" for p in result["outbox"].values()))
                self.assertEqual(results["fvg"]["critical_active"], 1)
                self.assertEqual(results["national"]["critical_active"], 0)
                self.assertTrue(any(row.get("phase") == "telemetry_result" for row in logs))

    def test_child_deadline_never_extends_parent_or_telemetry_reserve(self):
        clock = Mock(return_value=0)
        parent = Budget(110, clock=clock)
        clock.return_value = 20
        collection = parent.child(75, reserve=35)
        self.assertEqual(collection.end, 75)
        clock.return_value = 60
        self.assertEqual(collection.child(35).end, 75)
        clock.return_value = 75
        with self.assertRaises(BudgetExpired):
            collection.child(35)

    def test_process_start_failure_is_sanitized_and_does_not_leak_handles(self):
        transport = Transport()
        self.addCleanup(transport.close)
        with patch("multiprocessing.process.BaseProcess.start", side_effect=OSError("private spawn detail")):
            with self.assertRaises(Unavailable) as error:
                transport.request("GET", self.url + "/ok", Budget(5))
        self.assertNotIn("private", str(error.exception))
        self.assertIsNone(transport._connection)
        self.assertIsNone(transport._process)

    def test_scheduled_configuration_uses_environment_and_cli_override(self):
        env = {"ICON2I_MONITOR_ALLOW_CLOUD": "1", "GOOGLE_CLOUD_PROJECT": "meteo-friul",
               "CLOUD_RUN_JOB": "meteofriul-icon2i-freshness", "CLOUD_RUN_TASK_COUNT": "1",
               "ICON2I_PUBLIC_HTTP_TIMEOUT_SECONDS": "8", "ICON2I_API_HTTP_TIMEOUT_SECONDS": "3"}
        auth, public = Mock(), Mock()
        with patch.dict(os.environ, env, clear=True), patch.object(entry, "datetime") as clock, \
                patch.object(entry, "transports", return_value=(auth, public)) as transports, \
                patch.object(entry, "PublicHTTP") as public_http, patch.object(entry, "Runner") as runner, \
                patch.object(entry, "emit") as emit:
            clock.now.return_value = NOW
            runner.return_value.run.return_value = {p: {"outbox": {"point": {"status": "confirmed"}}}
                                                   for p in ("fvg", "national")}
            self.assertEqual(entry.main(["--cloud", "--scheduled-slot", entry.stamp(NOW),
                                         "--public-http-timeout-seconds", "12"]), 0)
            transports.assert_called_once_with(api_timeout_seconds=3)
            public_http.assert_called_once_with(public, timeout_seconds=12)
            limits = next(call.args[0] for call in emit.call_args_list
                          if call.args[0]["event"] == "icon2i_freshness_runtime_limits")
            self.assertEqual(limits["public_http_timeout_seconds"], 12)
            auth.close.assert_called_once()
            public.close.assert_called_once()

    def test_invalid_timeout_configuration_fails_before_credentials(self):
        for flag, value in (("--public-http-timeout-seconds", "nan"),
                            ("--public-http-timeout-seconds", "16"),
                            ("--public-http-timeout-seconds", "0"),
                            ("--api-http-timeout-seconds", "6"),
                            ("--api-http-timeout-seconds", "inf")):
            with self.subTest(flag=flag, value=value), patch.object(entry, "transports") as credentials:
                with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
                    entry.main([flag, value])
                credentials.assert_not_called()


if __name__ == "__main__":
    unittest.main()
