"""Isolated Linux acceptance probe: synthetic HTTP peers, never Google APIs."""
import argparse
from copy import deepcopy
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import multiprocessing
import os
from pathlib import Path
import re
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit

if Path('/app/experiments/weather_autonomy').is_dir():
    sys.path.insert(0, '/app/experiments/weather_autonomy')
from freshness_monitor import __main__ as entry, contracts, google
from freshness_monitor.collect import Budget, Unavailable
from freshness_monitor.core import evaluate, stamp
from freshness_monitor.dispatcher import Application, JobLauncher
from freshness_monitor.http import Transport
from freshness_monitor.runner import Runner
from freshness_monitor.schedule import JOB
from test_freshness_monitor import Fixture, NOW, observation


def anonymous_session():
    from google.auth.credentials import AnonymousCredentials
    from google.auth.transport.requests import AuthorizedSession
    session = AuthorizedSession(AnonymousCredentials(), max_refresh_attempts=0, refresh_timeout=5)
    session.trust_env = False
    return session


class LoopbackTransport(Transport):
    def request(self, method, url, budget, **kwargs):
        parsed = urlsplit(url)
        hosts = {urlsplit(value).netloc for value in contracts.BASES.values()}
        hosts.update({'storage.googleapis.com', 'monitoring.googleapis.com', 'run.googleapis.com'})
        assert parsed.netloc in hosts, 'Unexpected target blocked by test transport'
        local = os.environ['ICON2I_PROBE_LOOPBACK'] + parsed.path
        if parsed.query:
            local += '?' + parsed.query
        return super().request(method, local, budget, **kwargs)


class Peer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return
        self.errors += 1
        super().handle_error(request, client_address)

    def __init__(self, scenario):
        super().__init__(('127.0.0.1', 0), Handler)
        self.fixture, self.scenario = Fixture(), scenario
        self.phase, self.phase_started = 'collection', None
        self.stopped = threading.Event()
        self.lock = threading.Lock()
        previous = NOW - timedelta(minutes=30)
        self.states = {p: ('1', evaluate(p, previous, previous,
            observation(complete=p != 'fvg', critical=['http_pointer_unreadable'] if p == 'fvg' else [])))
            for p in ('fvg', 'national')}
        self.points, self.seen, self.launches = {}, set(), 0
        self.calls, self.metric_writes, self.errors = 0, 0, 0


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def send(self, value, *, status=200, raw=False, drip=False):
        body = value if raw else json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if drip:
            for byte in body:
                if self.server.stopped.wait(0.1):
                    return
                self.wfile.write(bytes([byte]))
                self.wfile.flush()
        else:
            self.wfile.write(body)

    def respond(self):
        try:
            self.route()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def route(self):
        s = self.server
        path, query = urlsplit(self.path).path, parse_qs(urlsplit(self.path).query)
        s.calls += 1
        long_case = s.scenario in {'collection_reserve', 'total_deadline'}
        if path == '/probe/slow':
            return self.send(b'x' * 10000, raw=True, drip=True)
        if path == '/probe/max':
            return self.send(b'x' * contracts.MAX_DOCUMENT, raw=True)
        if path == '/probe/over':
            return self.send(b'x' * (contracts.MAX_DOCUMENT + 1), raw=True)
        if self.command == 'POST':
            size = int(self.headers.get('Content-Length', '0'))
            assert size <= contracts.MAX_DOCUMENT
            content = json.loads(self.rfile.read(size))
            if s.scenario == 'total_deadline' and s.phase == 'persistence':
                s.stopped.wait(1)
            if path.endswith('/jobs/' + JOB + ':run'):
                s.launches += 1
                return self.send({'name': 'projects/meteo-friul/locations/europe-west1/operations/probe'})
            if path.startswith('/upload/storage/v1/b/' + google.STATE_BUCKET):
                product = query['name'][0].rsplit('/', 1)[-1].removesuffix('.json')
                with s.lock:
                    generation, old = s.states[product]
                    if generation != query['ifGenerationMatch'][0]:
                        return self.send({}, status=412)
                    generation = str(int(generation) + 1)
                    s.states[product] = generation, content
                return self.send({'generation': generation})
            if path.endswith('/timeSeries'):
                series = content['timeSeries'][0]
                key = series['metric']['labels']['product'], series['metric']['type'].rsplit('/', 1)[-1]
                with s.lock:
                    assert key not in s.points, 'Duplicate metric write'
                    s.points[key] = series
                    s.metric_writes += 1
                return self.send({})
            raise AssertionError('Unexpected synthetic POST')
        if path.startswith('/storage/v1/b/'):
            bucket, suffix = path[len('/storage/v1/b/'):].split('/o', 1)
            key = unquote(suffix.removeprefix('/'))
            if long_case and s.phase == 'collection':
                # Leave room for the initial auth-worker imports within its
                # 5s deadline; spend the full 75s in collection, not state setup.
                s.stopped.wait(2 if bucket == google.STATE_BUCKET else 3)
            elif s.scenario == 'total_deadline' and s.phase == 'persistence':
                s.stopped.wait(1)
            if bucket == google.STATE_BUCKET:
                product = key.rsplit('/', 1)[-1].removesuffix('.json')
                with s.lock:
                    generation, state = deepcopy(s.states[product])
                return self.send(state if query.get('alt') == ['media'] else {'generation': generation})
            assert bucket == google.DATA_BUCKET
            if not key:
                prefix = query['prefix'][0]
                return self.send({'items': [{'name': name, 'size': str(obj.size)}
                    for name, obj in s.fixture.data.items() if name.startswith(prefix)]})
            obj = s.fixture.data[key]
            if query.get('alt') == ['media']:
                return self.send(obj.body, raw=True)
            return self.send({'generation': obj.generation, 'size': str(obj.size), 'timeCreated': obj.time_created})
        if path.endswith('/timeSeries'):
            if s.scenario == 'total_deadline':
                s.stopped.wait(1)
            filt = query['filter'][0]
            product = re.search(r'metric.labels.product="([^"]+)"', filt).group(1)
            metric = re.search(r'metric.type="([^"]+)"', filt).group(1).rsplit('/', 1)[-1]
            value = s.points.get((product, metric))
            return self.send({'timeSeries': [value] if value else []})
        for url, body in s.fixture.public.items():
            parsed = urlsplit(url)
            if parsed.path == path and parse_qs(parsed.query) == query:
                if s.scenario == 'cold_start' and path not in s.seen:
                    s.seen.add(path)
                    if path.endswith(('latest.json', 'pilot.json')):
                        s.stopped.wait(11.4)
                return self.send(body, raw=True, drip=long_case)
        raise AssertionError('Unexpected synthetic GET')


def cgroup_measurement():
    root = Path('/sys/fs/cgroup')
    if (root / 'memory.max').is_file():
        return {'cgroup': 2, 'limit_bytes': int((root / 'memory.max').read_text()),
                'peak_bytes': int((root / 'memory.peak').read_text()),
                'events': dict(line.split() for line in (root / 'memory.events').read_text().splitlines()),
                'cpu_max': (root / 'cpu.max').read_text().strip()}
    root /= 'memory'
    if (root / 'memory.limit_in_bytes').is_file():
        cpu = Path('/sys/fs/cgroup/cpu')
        return {'cgroup': 1, 'limit_bytes': int((root / 'memory.limit_in_bytes').read_text()),
                'peak_bytes': int((root / 'memory.max_usage_in_bytes').read_text()),
                'failcnt': int((root / 'memory.failcnt').read_text()),
                'cpu_quota': (cpu / 'cpu.cfs_quota_us').read_text().strip(),
                'cpu_period': (cpu / 'cpu.cfs_period_us').read_text().strip()}
    return {'cgroup': None}


def run_case(scenario):
    if scenario == 'unit':
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), 'test_freshness_monitor*.py')
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        assert result.wasSuccessful() and not result.skipped
        return {'tests': result.testsRun, 'skipped': 0}
    # Include the real catalog footprint even though synthetic weather has fewer cells.
    catalog_hold = contracts.catalogs()
    assert len(catalog_hold[0].istat_codes) == 215 and catalog_hold[1]['municipality_count'] == 7894
    peer = Peer(scenario)
    thread = threading.Thread(target=peer.serve_forever, kwargs={'poll_interval': 0.02}, daemon=True)
    thread.start()
    os.environ['ICON2I_PROBE_LOOPBACK'] = 'http://127.0.0.1:' + str(peer.server_port)
    auth = LoopbackTransport('authorized', session_factory=anonymous_session)
    public = LoopbackTransport('public')
    detail = {}
    try:
        if scenario in {'limits', 'memory_caps'}:
            local = os.environ['ICON2I_PROBE_LOOPBACK']
            for name, transport, cap in (('public', public, 15), ('google', auth, 5)):
                # Bypass only URL rewriting; exercise the production worker unchanged.
                if scenario == 'limits':
                    started = time.monotonic()
                    try:
                        Transport.request(transport, 'GET', local + '/probe/slow', Budget(25), timeout_seconds=cap)
                        raise AssertionError('Slow response unexpectedly completed')
                    except Unavailable as error:
                        assert error.failure_kind == 'timeout'
                    duration = time.monotonic() - started
                    assert cap - 0.4 <= duration <= cap + 0.5
                    assert transport._process is None
                    detail[name + '_deadline_seconds'] = round(duration, 3)
                else:
                    for _ in range(3):
                        body = Transport.request(transport, 'GET', local + '/probe/max', Budget(5))[1]
                        assert len(body) == contracts.MAX_DOCUMENT
                        try:
                            Transport.request(transport, 'GET', local + '/probe/over', Budget(5))
                            raise AssertionError('Oversized body accepted')
                        except ValueError:
                            pass
                    detail[name + '_accepted_bytes'] = len(body)
            return detail
        if scenario == 'dispatcher':
            app = Application(lambda: JobLauncher(auth, owns_transport=True), now=lambda: NOW, log=lambda row: None)
            status, _ = app.dispatch({'x-cloudscheduler': 'true', 'x-cloudscheduler-jobname': JOB,
                                     'x-cloudscheduler-scheduletime': stamp(NOW)})
            assert status == 202 and peer.launches == 1 and auth._process is None
            return {'dispatch_status': status, 'synthetic_launches': peer.launches}
        logs, captured = [], {}
        class ObservedRunner(Runner):
            def run_product(self, *args, **kwargs):
                if peer.phase_started is None:
                    peer.phase_started = time.monotonic()
                    peer.phase = 'persistence'
                return super().run_product(*args, **kwargs)

            def run(self, *args, **kwargs):
                value = super().run(*args, **kwargs)
                captured.update(value)
                return value
        real_collector = entry.Collector
        def collector(*args, **kwargs):
            return real_collector(*args, **kwargs, catalog_pair=peer.fixture.catalog_pair)
        env = {'ICON2I_MONITOR_ALLOW_CLOUD': '1', 'GOOGLE_CLOUD_PROJECT': 'meteo-friul',
               'CLOUD_RUN_JOB': JOB, 'CLOUD_RUN_TASK_COUNT': '1', 'CLOUD_RUN_TASK_ATTEMPT': '0'}
        started = time.monotonic()
        with patch.dict(os.environ, env), patch.object(entry, 'transports', return_value=(auth, public)), \
                patch.object(entry, 'Collector', side_effect=collector), patch.object(entry, 'Runner', ObservedRunner), \
                patch.object(entry, 'emit', side_effect=logs.append), patch.object(entry, 'datetime') as clock:
            clock.now.return_value = NOW
            code = entry.main(['--cloud', '--scheduled-slot', stamp(NOW)])
        elapsed = time.monotonic() - started
        assert peer.phase_started is not None, str([row for row in logs if row.get('error_type')])
        detail.update(application_seconds=round(elapsed, 3), exit_code=code, metric_writes=peer.metric_writes,
                      collection_seconds=round(peer.phase_started - started, 3), http_calls=peer.calls)
        assert elapsed < 112 and not multiprocessing.active_children()
        if scenario == 'total_deadline':
            assert code == 1 and 108 <= elapsed <= 112
            assert any(row.get('error_type') == 'BudgetExpired' for row in logs)
            assert peer.states['fvg'][1]['critical_active'] == 1
            detail['partial_persistence_explicitly_failed'] = True
        else:
            assert code == 0 and peer.metric_writes == 6
            for product, state in captured.items():
                assert state['check_completed'] == 1
                assert all(point['status'] == 'confirmed' for point in state['outbox'].values())
                assert state['check_state'] == (3 if scenario == 'collection_reserve' else 0)
            if scenario == 'collection_reserve':
                assert 73 <= detail['collection_seconds'] <= 75.5
                assert captured['fvg']['critical_active'] == 1
                detail['reserve_remaining_at_persistence_seconds'] = round(110 - detail['collection_seconds'], 3)
                assert detail['reserve_remaining_at_persistence_seconds'] >= 34.5
        return detail
    finally:
        public.close()
        auth.close()
        peer.stopped.set()
        peer.shutdown()
        peer.server_close()
        thread.join(timeout=1)
        assert peer.errors == 0, 'Synthetic peer failed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scenario', choices=['unit', 'healthy', 'cold_start', 'limits', 'memory_caps',
                                            'collection_reserve', 'total_deadline', 'dispatcher'])
    parser.add_argument('--allow-non-linux', action='store_true', help='Development only, never Linux acceptance')
    args = parser.parse_args()
    linux = sys.platform == 'linux'
    assert linux or args.allow_non_linux
    assert not linux or os.getuid() == 65532
    started = time.monotonic()
    report = {'scenario': args.scenario, 'platform': sys.platform, 'python': sys.version.split()[0],
              'uid': os.getuid() if linux else None, 'passed': False}
    try:
        report.update(run_case(args.scenario))
        if linux:
            memory = cgroup_measurement()
            expected = (256 if args.scenario == 'dispatcher' else 512) * 1024**2
            assert memory['cgroup'] in (1, 2), 'Container memory accounting required'
            assert memory['limit_bytes'] == expected and memory['peak_bytes'] < expected
            assert int(memory.get('events', {}).get('oom_kill', 0)) == 0 and memory.get('failcnt', 0) == 0
            if memory['cgroup'] == 2:
                quota, period = memory['cpu_max'].split()
            else:
                quota, period = memory['cpu_quota'], memory['cpu_period']
            assert int(quota) == int(period), 'Exactly one CPU quota required'
        report['passed'] = True
    finally:
        report['probe_seconds'] = round(time.monotonic() - started, 3)
        report['memory'] = cgroup_measurement() if linux else {'cgroup': None}
        report['remaining_children'] = len(multiprocessing.active_children())
        print('CONTAINER_PROBE ' + json.dumps(report, sort_keys=True), flush=True)
    assert not report['remaining_children']


if __name__ == '__main__':
    main()
