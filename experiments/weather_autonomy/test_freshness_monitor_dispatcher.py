"""Offline Scheduler -> HTTP relay -> Job -> state/metrics acceptance tests."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import io
import json
import os
import socket
import threading
import time
from urllib.request import Request, urlopen
import unittest
from unittest.mock import Mock, patch

from freshness_monitor import __main__ as worker
from freshness_monitor.dispatcher import Application, JobLauncher, RUN_URL, main as dispatcher_main
from freshness_monitor.schedule import (JOB, PROJECT, SCHEDULER, DISPATCHER, ExpiredSlot,
    scheduler_slot, require_delivery, job_overrides)
from freshness_monitor.core import instant, stamp
from freshness_monitor.collect import Budget, Unavailable
from freshness_monitor.runner import Runner
from test_freshness_monitor import NOW, observation, MemoryState, MemoryMetrics

CONNECT = socket.socket.connect


def loopback_only(sock, address):
    if not isinstance(address, tuple) or address[0] not in ("127.0.0.1", "::1"):
        raise AssertionError("external network forbidden")
    return CONNECT(sock, address)


SOURCE = stamp(NOW)
HEADERS = {"x-cloudscheduler": "true", "x-cloudscheduler-jobname": SCHEDULER,
           "x-cloudscheduler-scheduletime": SOURCE}
ENV = {"ICON2I_MONITOR_ALLOW_CLOUD": "1", "GOOGLE_CLOUD_PROJECT": PROJECT,
       "CLOUD_RUN_JOB": JOB, "CLOUD_RUN_TASK_COUNT": "1", "CLOUD_RUN_TASK_ATTEMPT": "0"}
OPERATION = "projects/meteo-friul/locations/europe-west1/operations/test-operation"


def request(app, headers=None, body=b"{}", method="POST", path="/dispatch", query=b""):
    sent = []
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    async def send(message):
        sent.append(message)
    headers = list((k.encode(), v.encode()) for k, v in HEADERS.items()) if headers is None else headers
    asyncio.run(app({"type": "http", "path": path, "query_string": query,
                     "method": method, "headers": headers}, receive, send))
    return sent[0]["status"], sent[1]["body"]


class ScheduleTests(unittest.TestCase):
    def test_identity_comes_from_source_not_delivery_time(self):
        # Same immutable source remains 18:10 whether received at 18:11 or 18:39.
        for minutes in (1, 29):
            self.assertEqual(require_delivery(NOW, SOURCE, NOW+timedelta(minutes=minutes)), NOW)
        for minutes in (30, 31, 60):
            with self.assertRaises(ExpiredSlot):
                require_delivery(NOW, SOURCE, NOW+timedelta(minutes=minutes))

    def test_bounded_source_seconds_are_preserved_in_forwarded_args(self):
        for seconds in (0, 44.36995, 74, 120):
            source = stamp(NOW+timedelta(seconds=seconds))
            self.assertEqual(scheduler_slot(source), NOW)
            args = job_overrides(NOW, source)["overrides"]["containerOverrides"][0]["args"]
            self.assertEqual(args[args.index("--scheduler-schedule-time")+1], source)
            self.assertEqual(args[args.index("--scheduled-slot")+1], SOURCE)
        for seconds in (121, 300, 1799):
            with self.assertRaises(ValueError):
                scheduler_slot(stamp(NOW+timedelta(seconds=seconds)))

    def test_future_inconsistent_and_invalid_source_are_rejected(self):
        with self.assertRaises(ValueError):
            require_delivery(NOW, stamp(NOW+timedelta(seconds=30)), NOW)
        with self.assertRaises(ValueError):
            require_delivery(NOW+timedelta(minutes=30), SOURCE, NOW+timedelta(minutes=31))
        for value in (None, "", "2026-10-15", "2026-10-15T18:10:00", SOURCE+","+SOURCE):
            with self.assertRaises(ValueError):
                scheduler_slot(value)

    def test_dst_and_rfc3339_offset_normalize_only_the_source(self):
        for source, expected in (("2026-10-25T02:10:00+02:00", "2026-10-25T00:10:00Z"),
                                 ("2026-10-25T02:10:00+01:00", "2026-10-25T01:10:00Z"),
                                 ("2026-03-29T03:40:00+02:00", "2026-03-29T01:40:00Z")):
            self.assertEqual(scheduler_slot(source), instant(expected))


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.now = NOW+timedelta(minutes=1)
        self.logs = []
        self.launcher = Mock()
        self.launcher.launch.return_value = OPERATION
        self.factory = Mock(return_value=self.launcher)
        self.app = Application(self.factory, now=lambda: self.now, log=self.logs.append)
        self.guard = patch("socket.socket.connect", new=loopback_only)
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def test_http_dispatch_passes_original_identity(self):
        self.assertEqual(request(self.app)[0], 202)
        self.launcher.launch.assert_called_once_with(NOW, SOURCE)
        self.assertEqual(self.logs[-1]["scheduled_slot_utc"], SOURCE)
        self.assertEqual(self.logs[-1]["outcome"], "launch_accepted")

    def test_actual_cloud_headers_preserve_offset_and_canonical_slot(self):
        source = "2026-10-16T00:40:00.711959-07:00"
        self.now = instant("2026-10-16T07:40:05Z")
        headers = {"x-cloudscheduler": "true", "x-cloudscheduler-jobname": JOB,
                   "x-cloudscheduler-scheduletime": source}
        self.assertEqual(request(self.app, headers=[(k.encode(), v.encode())
                                                   for k, v in headers.items()])[0], 202)
        self.launcher.launch.assert_called_once_with(instant("2026-10-16T07:40:00Z"), source)
        self.assertEqual(self.logs[-1]["scheduler_job_received"], JOB)
        self.assertEqual(self.logs[-1]["scheduler_job"], SCHEDULER)
        self.assertEqual(self.logs[-1]["scheduler_schedule_time"], source)

    def test_short_name_allowlist_rejects_other_jobs_and_foreign_resources(self):
        for name in (JOB + "-other", "projects/other/locations/europe-west1/jobs/" + JOB,
                     "prefix/" + JOB, SCHEDULER.replace("europe-west1", "europe-west8")):
            self.assertEqual(self.app.dispatch(dict(HEADERS, **{"x-cloudscheduler-jobname": name}))[0], 400)
        self.factory.assert_not_called()

    def test_late_delivery_is_acknowledged_without_launch(self):
        for minutes in (30, 60):
            self.now = NOW+timedelta(minutes=minutes)
            self.assertEqual(request(self.app)[0], 204)
        self.factory.assert_not_called()
        self.assertTrue(all(r["scheduled_slot_utc"] == SOURCE for r in self.logs))

    def test_expiry_during_factory_setup_never_launches(self):
        def create():
            self.now = NOW+timedelta(minutes=30)
            return self.launcher
        self.factory.side_effect = create
        self.assertEqual(request(self.app)[0], 204)
        self.launcher.launch.assert_not_called()

    def test_missing_duplicate_wrong_and_body_supplied_headers_rejected(self):
        good = [(k.encode(), v.encode()) for k, v in HEADERS.items()]
        variants = [[], good[:-1], good+[good[-1]],
                    [(k, b"other" if k==b"x-cloudscheduler-jobname" else v) for k,v in good],
                    [(k, b"yesterday" if k==b"x-cloudscheduler-scheduletime" else v) for k,v in good]]
        for headers in variants:
            self.assertEqual(request(self.app, headers=headers)[0], 400)
        for body in (b'{"scheduled_slot":"2026-10-15T18:40:00Z"}', b"[1]", b"x"*1025, b"not-json"):
            self.assertEqual(request(self.app, body=body)[0], 400)
        self.factory.assert_not_called()

    def test_invalid_delivery_logs_bounded_metadata_without_credentials(self):
        headers = dict(HEADERS, **{"x-cloudscheduler-jobname": "other" * 100,
                                  "authorization": "Bearer sensitive-credential"})
        self.assertEqual(self.app.dispatch(headers)[0], 400)
        record = self.logs[-1]
        self.assertEqual(record["validation_stage"], "scheduler_identity")
        self.assertEqual(len(record["scheduler_headers"]["x-cloudscheduler-jobname"]), 200)
        self.assertEqual(record["scheduler_headers"]["x-cloudscheduler-scheduletime"], SOURCE)
        self.assertNotIn("authorization", json.dumps(record))
        self.assertNotIn("sensitive-credential", json.dumps(record))
        self.factory.assert_not_called()

    def test_method_route_and_query_cannot_override_target(self):
        self.assertEqual(request(self.app, method="GET")[0], 405)
        self.assertEqual(request(self.app, path="/other")[0], 404)
        self.assertEqual(request(self.app, query=b"slot=other")[0], 404)
        self.factory.assert_not_called()

    def test_unknown_launch_is_not_retried_or_reported_successful(self):
        self.launcher.launch.side_effect = Unavailable("lost response with sensitive details")
        self.assertEqual(request(self.app)[0], 503)
        self.assertEqual(self.launcher.launch.call_count, 1)
        self.assertNotIn("sensitive", json.dumps(self.logs))
        self.assertEqual(self.logs[-1]["outcome"], "launch_uncertain")

    def test_launcher_has_fixed_target_and_real_api_override_contract(self):
        transport = Mock()
        transport.request.return_value = (200, json.dumps({"name": OPERATION}).encode(), {})
        self.assertEqual(JobLauncher(transport).launch(NOW, SOURCE), OPERATION)
        args, kwargs = transport.request.call_args
        self.assertEqual(args[:2], ("POST", RUN_URL))
        self.assertEqual(kwargs["json"], job_overrides(NOW, SOURCE))
        self.assertEqual(kwargs["json"]["overrides"]["taskCount"], 1)
        self.assertEqual(transport.request.call_count, 1)
        transport.request.return_value = (200, b'{"name":"another-project"}', {})
        with self.assertRaises(Unavailable):
            JobLauncher(transport).launch(NOW, SOURCE)

    def test_real_local_http_server_uses_the_same_asgi_dispatch(self):
        import uvicorn
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(self.app, lifespan="off", access_log=False,
                                               log_level="critical", ws="none", proxy_headers=False))
        thread = threading.Thread(target=lambda: asyncio.run(server.serve(sockets=[listener])), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic()+5
            while not server.started and thread.is_alive() and time.monotonic()<deadline:
                time.sleep(0.01)
            self.assertTrue(server.started)
            req = Request(f"http://127.0.0.1:{port}/dispatch", data=b"{}", headers=HEADERS, method="POST")
            with urlopen(req, timeout=5) as response:
                self.assertEqual(response.status, 202)
                self.assertEqual(json.load(response), {"status":"launch_accepted"})
            self.launcher.launch.assert_called_once_with(NOW, SOURCE)
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            listener.close()
        self.assertFalse(thread.is_alive())

    def test_disabled_entrypoint_never_starts_server_or_credentials(self):
        with patch.dict(os.environ, {}, clear=True), patch("uvicorn.run") as serve, patch("freshness_monitor.dispatcher.transports") as creds, patch("sys.stderr", new_callable=io.StringIO):
            for argv in ([], ["--serve"], ["--serve", "--cloud"]):
                with self.assertRaises(SystemExit):
                    dispatcher_main(argv)
            serve.assert_not_called(); creds.assert_not_called()


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.now = NOW+timedelta(minutes=1)
        self.state, self.metrics = MemoryState(), MemoryMetrics()
        self.collector = Mock()
        self.collector.collect.return_value = observation()
        self.worker_logs, self.dispatch_logs = [], []
        self.jobs = []
        self.app = Application(lambda: self, now=lambda: self.now, log=self.dispatch_logs.append)
        self.guard = patch("socket.socket.connect", new=loopback_only)
        self.guard.start(); self.addCleanup(self.guard.stop)

    def launch(self, planned, source):
        args = job_overrides(planned, source)["overrides"]["containerOverrides"][0]["args"]
        self.jobs.append(args)
        self.assertEqual(self.execute(args), 0)
        return OPERATION

    def execute(self, args):
        with patch.dict(os.environ, ENV, clear=True), patch.object(worker, "datetime") as clock, patch.object(worker, "transports", return_value=(Mock(), Mock())) as credentials, patch.object(worker, "MonitorState", return_value=self.state), patch.object(worker, "Metrics", return_value=self.metrics), patch.object(worker, "Collector", return_value=self.collector), patch.object(worker, "emit", side_effect=self.worker_logs.append), patch("sys.stderr", new_callable=io.StringIO):
            clock.now.side_effect = lambda zone: self.now
            self.credentials = credentials
            return worker.main(args)

    def test_duplicate_deliveries_only_publish_six_points_once(self):
        self.assertEqual(request(self.app)[0], 202)
        first = deepcopy(self.state.items)
        self.now = NOW+timedelta(minutes=29)
        self.assertEqual(request(self.app)[0], 202)
        self.assertEqual(self.jobs[0], self.jobs[1])
        self.assertEqual(self.state.items, first)
        self.assertEqual(len(self.metrics.writes), 6)
        self.assertEqual(self.collector.collect.call_count, 2)

    def test_lost_launch_ack_then_duplicate_reconciles_same_slot(self):
        real_launch = self.launch
        def lost(planned, source):
            real_launch(planned, source)
            raise Unavailable("ack lost after execution")
        self.app.launcher_factory = lambda: Mock(launch=lost)
        self.assertEqual(request(self.app)[0], 503)
        self.app.launcher_factory = lambda: self
        self.now += timedelta(minutes=1)
        self.assertEqual(request(self.app)[0], 202)
        self.assertEqual(len(self.metrics.writes), 6)

    def test_job_queued_across_slot_boundary_rejected_before_credentials(self):
        self.now = NOW+timedelta(minutes=29, seconds=59)
        queued = Mock()
        queued.launch.return_value = OPERATION
        self.app.launcher_factory = lambda: queued
        self.assertEqual(request(self.app)[0], 202)
        planned, source = queued.launch.call_args.args
        args = job_overrides(planned, source)["overrides"]["containerOverrides"][0]["args"]
        self.now = NOW+timedelta(minutes=30)
        with self.assertRaises(SystemExit):
            self.execute(args)
        self.credentials.assert_not_called()
        self.assertFalse(self.state.items); self.assertFalse(self.metrics.writes)

    def test_new_slot_remains_active_after_very_late_old_duplicate(self):
        request(self.app)
        self.now = NOW+timedelta(minutes=31)
        newer = dict(HEADERS, **{"x-cloudscheduler-scheduletime":stamp(NOW+timedelta(minutes=30))})
        self.assertEqual(request(self.app, headers=[(k.encode(),v.encode()) for k,v in newer.items()])[0], 202)
        before = deepcopy(self.state.items)
        self.assertEqual(request(self.app)[0], 204)
        self.assertEqual(self.state.items, before)
        self.assertEqual(len(self.metrics.writes), 12)

    def test_inconsistent_source_and_removed_execution_mode_rejected_before_io(self):
        args = job_overrides(NOW,SOURCE)["overrides"]["containerOverrides"][0]["args"]
        args[2] = stamp(NOW+timedelta(minutes=30))
        for candidate in (args, ["--cloud", "--use-execution-slot"]):
            with self.assertRaises(SystemExit):
                self.execute(candidate)
            self.credentials.assert_not_called()

    def test_expiry_during_collection_writes_no_state_or_heartbeat(self):
        def slow(product):
            self.now = NOW+timedelta(minutes=30)
            return observation()
        self.collector.collect.side_effect = slow
        result = Runner(self.state,self.metrics,self.collector,now=lambda:self.now,
                        budget=Budget(),emit=self.worker_logs.append).run(NOW)
        self.assertEqual(result, {"fvg":None,"national":None})
        self.assertFalse(self.state.items); self.assertFalse(self.metrics.writes)

    def test_expiry_during_metric_reconciliation_does_not_write_late_point(self):
        def slow(*args):
            self.now = NOW+timedelta(minutes=30)
            return None
        self.metrics.latest = slow
        Runner(self.state,self.metrics,self.collector,now=lambda:self.now,
               budget=Budget(),emit=self.worker_logs.append).run(NOW)
        self.assertFalse(self.metrics.writes)
        self.assertEqual(self.state.items['fvg'][1]['scheduled_slot_utc'], SOURCE)


if __name__ == "__main__":
    unittest.main()
