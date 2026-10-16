"""Offline acceptance tests: no credentials, network, weather download or cloud writes."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import unittest
from unittest.mock import patch, Mock

from freshness_monitor import contracts as c
from freshness_monitor.core import (evaluate, future_samples, instant, stamp, slot,
                                    METRICS, log_record)
from freshness_monitor.collect import Collector, Budget, BudgetExpired, Object, Unavailable
from freshness_monitor.runner import Runner, Conflict, Rejected, validate_state
from freshness_monitor.google import WeatherData, MonitorState, Metrics, PublicHTTP, Transport
from local_pipeline import contract_v1 as v1, national_icon_bundle as v2
from national_cloud_publication import reader_for_bundle
from test_serve_national_bundle_v2 import _sample_catalog

UTC = timezone.utc
RUN = datetime(2026, 10, 15, 12, tzinfo=UTC)
NOW = RUN + timedelta(hours=6, minutes=10)
PLANNED = stamp(NOW)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def observation(run=RUN, *, complete=True, indeterminate=False, critical=(), created=None, hours=72):
    return {"complete": complete, "indeterminate": indeterminate, "critical_causes": list(critical),
            "run": {"source_run_id": run.strftime("%Y%m%dT%H%M%SZ"), "run_at": stamp(run),
                    "generation": "9", "time_created": stamp(created or run + timedelta(hours=6))},
            "last_at": stamp(run + timedelta(hours=hours))}


class Fixture:
    def __init__(self, run=RUN, created=None):
        created = created or run + timedelta(hours=6, minutes=4)
        self.run, self.created = run, created
        self.data, self.public = {}, {}
        self.fvg_catalog = v1.load_catalog()
        nat = _sample_catalog()
        nat["municipalities"][0]["istat_code"] = "058091"
        codes = sorted(item["istat_code"] for item in nat["municipalities"])
        nat["municipality_codes_sha256"] = hashlib.sha256(encoded(codes)).hexdigest()
        self.catalog_pair = self.fvg_catalog, nat
        runid = run.strftime("%Y%m%dT%H%M%SZ")
        objects = {code: {"path": f"runs/{runid}/municipalities/{code}.json",
                         "json_bytes": 2, "sha256": hashlib.sha256(b"{}").hexdigest()}
                   for code in self.fvg_catalog.istat_codes}
        manifest = v1.build_run_manifest(provider="icon2i", run_at=run.strftime("%Y-%m-%dT%H:%M:%SZ"),
            generated_at=(run + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            catalog=self.fvg_catalog, objects=objects)
        ptr = v1.build_latest_document(provider="icon2i", revision=1,
            published_at=created.strftime("%Y-%m-%dT%H:%M:%SZ"), run_manifest=manifest, catalog=self.fvg_catalog)
        self.add("fvg", "latest.json", encoded(ptr))
        self.add("fvg", f"runs/{runid}/manifest.json", encoded(manifest))
        for item in objects.values():
            self.add("fvg", item["path"], b"{}")
        bundle = v2.build_national_icon_bundle(
            run_at=run.strftime("%Y-%m-%dT%H:%M:%SZ"),
            generated_at=(run + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            catalog={"version": nat["catalog_version"], "sha256": nat["catalog_sha256"],
                     "municipality_count": 3, "municipality_codes_sha256": nat["municipality_codes_sha256"]},
            grid={"sha256": "b" * 64, "ni": 20, "nj": 20},
            metadata={"model": {"id": "icon-2i", "product": "test_profile"},
                      "source": {"attribution": "Agenzia ItaliaMeteo", "license": "CC BY 4.0",
                                 "license_url": "https://creativecommons.org/licenses/by/4.0/"},
                      "variables": [{"id": "temperature_c", "unit": "degC", "data_type": "float", "nullable": False}]},
            time_axis=[(run + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ") for h in range(73)],
            municipality_cells={code: n + 11 for n, code in enumerate(codes)},
            cells=[{"grid_index": n+11, "latitude": 41.9+n, "longitude": 12.5,
                    "values": {"temperature_c": [20.0] * 73}} for n in range(3)],
            tile_size_degrees="0.25")
        reader = reader_for_bundle(bundle, nat)
        for path, body in bundle.publication_order():
            self.add("national", path, body)
        self.add("national", "pilot.json", encoded({**reader.pointer,
            "published_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"), "revision": 1, "previous": None}))
        self.public[c.BASES["national"] + "pilot.json"] = encoded(dict(reader.pointer))
        self.public[c.BASES["national"] + c.RESOLVER] = reader.resolve(city="Roma", province="RM", latitude=None, longitude=None)
        self.reads, self.http_calls, self.head_calls = [], [], 0
        self.head_hook = None
        self.http_hook = None

    def add(self, product, path, body):
        self.data[c.ROOTS[product] + path] = Object(body, "9", stamp(self.created), len(body))
        self.public[c.BASES[product] + path] = body

    def get(self, key, *args):
        if key.startswith("https://"):
            headers, budget = args
            self.http_calls.append((key, deepcopy(headers)))
            if self.http_hook:
                result = self.http_hook(key, headers)
                if result is not None:
                    return result
            return {"status": 200, "body": self.public[key], "headers": {"cache-control": "no-store"}}
        self.reads.append(key)
        if key not in self.data:
            raise Unavailable("missing")
        return self.data[key]

    def head(self, key, budget):
        self.head_calls += 1
        if self.head_hook:
            result = self.head_hook(key)
            if result is not None:
                return result
        obj = self.data[key]
        return Object(b"", obj.generation, obj.time_created, obj.size)

    def list(self, prefix, budget):
        return {key: obj.size for key, obj in self.data.items() if key.startswith(prefix)}

    def collector(self, now=NOW, budget=None):
        return Collector(self, self, now=lambda: now, budget=budget or Budget(),
                         catalog_pair=self.catalog_pair)


class PureTests(unittest.TestCase):
    def test_run_age_and_job_success_never_reset_age(self):
        for hours, expected in ((18.99, 0), (19, 1), (19.99, 1), (20, 2)):
            now = RUN + timedelta(hours=hours)
            planned = slot(now.replace(minute=10, second=0, microsecond=0))
            if planned > now:
                planned -= timedelta(minutes=30)
            state = evaluate("fvg", planned, now, observation())
            self.assertEqual(state["check_state"], expected)
        old_run = observation(created=RUN + timedelta(hours=20))
        self.assertEqual(evaluate("fvg", RUN+timedelta(hours=20, minutes=10),
                                 RUN+timedelta(hours=20, minutes=10), old_run)["critical_active"], 1)

    def test_coverage_boundaries_are_inclusive_on_the_hour(self):
        for samples in (11, 12, 23, 24):
            now = RUN + timedelta(hours=1)
            obs = observation(hours=samples)
            state = evaluate("national", RUN+timedelta(minutes=40), now, obs)
            self.assertEqual(state["future_samples"], samples)
            self.assertEqual(state["check_state"], 2 if samples < 12 else 1 if samples < 24 else 0)
        self.assertEqual(future_samples(RUN, RUN+timedelta(hours=12), RUN), 13)
        self.assertEqual(future_samples(RUN, RUN+timedelta(hours=12), RUN+timedelta(microseconds=1)), 12)

    def test_bootstrap_and_rewrites_do_not_invent_publication(self):
        first = evaluate("fvg", NOW, NOW, observation())
        self.assertIsNone(first["publication"])
        changed = observation(RUN+timedelta(hours=12), created=RUN+timedelta(hours=18))
        second = evaluate("fvg", NOW+timedelta(hours=12), NOW+timedelta(hours=12), changed, first)
        rewritten = deepcopy(changed)
        rewritten["run"]["time_created"] = stamp(NOW+timedelta(hours=13))
        third = evaluate("fvg", NOW+timedelta(hours=13), NOW+timedelta(hours=13), rewritten, second)
        self.assertEqual(third["publication"], second["publication"])

    def test_publication_thresholds_strict_and_one_incident(self):
        base = evaluate("fvg", NOW, NOW, observation())
        base["publication"] = {"at": stamp(NOW-timedelta(hours=13)), "source_run_id": "old",
                               "generation": "1", "basis": "observed_run_change"}
        for age, code in ((13, None), (13.01, "publication_age_attention"), (14, "publication_age_attention"),
                          (14.01, "publication_age_critical")):
            old = deepcopy(base)
            future = NOW+timedelta(minutes=30)
            old["publication"]["at"] = stamp(future-timedelta(hours=age))
            state = evaluate("fvg", future, future, observation(), old)
            codes = [c for c in state["causes"] if c.startswith("publication_age")]
            self.assertEqual(codes, [code] if code else [])

    def test_two_indeterminates_and_explicit_recovery(self):
        bad = observation(complete=False, indeterminate=True)
        a = evaluate("fvg", NOW, NOW, bad)
        b = evaluate("fvg", NOW+timedelta(minutes=30), NOW+timedelta(minutes=30), bad, a)
        self.assertEqual((a["check_state"], a["critical_active"]), (3, 0))
        self.assertEqual((b["check_state"], b["critical_active"]), (3, 1))
        cstate = evaluate("fvg", NOW+timedelta(hours=1), NOW+timedelta(hours=1), observation(), b)
        self.assertEqual(cstate["critical_active"], 0)

    def test_intermittence_missing_slots_and_duplicates(self):
        current = None
        for n in range(6):
            t = NOW+timedelta(minutes=30*n)
            current = evaluate("fvg", t, t, observation(complete=n%2==1, indeterminate=n%2==0), current)
        self.assertEqual((current["indeterminate_count_last6"], current["check_state"], current["critical_active"]), (3, 1, 0))
        self.assertIsNone(evaluate("fvg", t, t, observation(), current))
        t += timedelta(hours=2)
        later = evaluate("fvg", t, t, observation(complete=False, indeterminate=True), current)
        self.assertEqual(later["history"][-2]["indeterminate"], None)
        self.assertNotIn("comparison_indeterminate_consecutive", later["causes"])

    def test_prior_critical_is_latched_and_run_does_not_regress(self):
        a = evaluate("fvg", NOW, NOW, observation(complete=False, critical=["resolver_unreadable"]))
        b = evaluate("fvg", NOW+timedelta(minutes=30), NOW+timedelta(minutes=30),
                     observation(complete=False, indeterminate=True), a)
        self.assertIn("resolver_unreadable", b["critical_causes"])
        good = evaluate("fvg", NOW, NOW, observation())
        regression = evaluate("fvg", NOW+timedelta(minutes=30), NOW+timedelta(minutes=30),
                              observation(RUN-timedelta(hours=12)), good)
        self.assertIn("run_regression", regression["critical_causes"])
        self.assertEqual(regression["last_verified"], good["last_verified"])

    def test_dst_slots(self):
        from zoneinfo import ZoneInfo
        rome = ZoneInfo("Europe/Rome")
        for date in ("2026-03-29T00:40:00Z", "2026-03-29T01:10:00Z",
                     "2026-10-25T00:40:00Z", "2026-10-25T01:10:00Z"):
            self.assertEqual(slot(instant(date).astimezone(rome)), instant(date))
        with self.assertRaises(ValueError):
            slot("2026-10-15T18:11:00Z")


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.block_network = patch("socket.socket.connect", side_effect=AssertionError("network forbidden"))
        self.block_network.start()
        self.addCleanup(self.block_network.stop)
        self.fixture = Fixture()

    def test_happy_paths_and_no_payload_downloads(self):
        for product in ("fvg", "national"):
            obs = self.fixture.collector().collect(product)
            self.assertTrue(obs["complete"], obs)
            self.assertFalse(obs["critical_causes"])
        self.assertTrue(all("/blocks/" not in key and "/municipalities/" not in key for key in self.fixture.reads))
        calls = self.fixture.http_calls
        self.assertEqual(calls[0][1]["Cache-Control"], "max-age=0")
        self.assertEqual(calls[-1][1]["Cache-Control"], "no-cache")
        self.assertEqual(calls[-1][1]["Pragma"], "no-cache")
        self.assertEqual(calls[-1][1]["Accept"], "*/*")
        self.assertNotIn("If-None-Match", calls[0][1])

    def test_resolver_unavailable_despite_good_pointer(self):
        def broken(url, headers):
            if "resolve.json" in url:
                raise Unavailable("503", transient=True)
        self.fixture.http_hook = broken
        obs = self.fixture.collector().collect("national")
        self.assertIn("resolver_unreadable", obs["critical_causes"])
        self.assertEqual(sum("resolve.json" in u for u, _ in self.fixture.http_calls), 2)

    def test_resolver_wrong_istat_and_block_are_critical(self):
        url = c.BASES["national"] + c.RESOLVER
        original = json.loads(self.fixture.public[url])
        for mutate in (lambda x: x["municipality"].update(istat_code="001001"),
                       lambda x: x.update(block_sha256="a"*64),
                       lambda x: x.update(municipality=None), lambda x: x.update(cell_id=None)):
            value = deepcopy(original)
            mutate(value)
            self.fixture.public[url] = encoded(value)
            obs = self.fixture.collector().collect("national")
            self.assertIn("resolver_incompatible", obs["critical_causes"])

    def test_http_newer_requires_stable_storage(self):
        newer = Fixture(RUN+timedelta(hours=12))
        url = c.BASES["fvg"] + "latest.json"
        self.fixture.public[url] = newer.public[url]
        obs = self.fixture.collector().collect("fvg")
        self.assertIn("http_pointer_newer_than_storage", obs["critical_causes"])

    def test_generation_changes_reconstruct_once_then_indeterminate(self):
        counter = [10]
        def moving(key):
            counter[0] += 1
            return Object(b"", str(counter[0]), stamp(self.fixture.created), 1)
        self.fixture.head_hook = moving
        obs = self.fixture.collector().collect("national")
        self.assertTrue(obs["indeterminate"])
        self.assertEqual(obs["snapshots_attempted"], 2)
        self.assertFalse(obs["critical_causes"])

    def test_publication_between_pointer_and_resolver(self):
        newer = Fixture(RUN+timedelta(hours=12), created=NOW+timedelta(hours=12)-timedelta(seconds=60))
        old_resolve = self.fixture.public[c.BASES["national"]+c.RESOLVER]
        def swap(url, headers):
            if "resolve.json" in url:
                self.fixture.data = newer.data
                self.fixture.public = newer.public
                self.fixture.http_hook = None
                return {"status": 200, "body": old_resolve, "headers": {}}
        # Ensure the generation changes too, as real Storage does.
        newer.data = {key: Object(v.body, "10", v.time_created, v.size) for key, v in newer.data.items()}
        self.fixture.http_hook = swap
        obs = self.fixture.collector(now=NOW+timedelta(hours=12)).collect("national")
        self.assertTrue(obs["complete"], obs)
        self.assertEqual(obs["snapshots_attempted"], 2)

    def test_older_http_grace_and_diagnostic_does_not_erase_first(self):
        older = Fixture(RUN-timedelta(hours=12))
        url = c.BASES["fvg"]+"latest.json"
        original = self.fixture.public[url]
        self.fixture.public[url] = older.public[url]
        def diagnostic(url, headers):
            if headers["Cache-Control"] == "no-cache":
                return {"status": 200, "body": original, "headers": {}}
        self.fixture.http_hook = diagnostic
        for age, indeterminate in ((59, True), (60, True), (61, False)):
            obs = self.fixture.collector(now=self.fixture.created+timedelta(seconds=age)).collect("fvg")
            self.assertEqual(obs["indeterminate"], indeterminate)
            self.assertEqual(obs["http_comparison"]["ordinary"]["result"], "http_older")
            self.assertEqual(obs["http_comparison"]["diagnostic"]["result"], "coherent")
            if not indeterminate:
                self.assertIn("http_pointer_older_than_storage", obs["critical_causes"])

    def test_same_run_hash_mismatch_and_invalid_manifest(self):
        url = c.BASES["fvg"]+"latest.json"
        value = json.loads(self.fixture.public[url])
        value["latest"]["manifest_sha256"] = "b"*64
        self.fixture.public[url] = encoded(value)
        self.assertIn("http_pointer_incompatible", self.fixture.collector().collect("fvg")["critical_causes"])
        key = next(k for k in self.fixture.data if k.endswith("manifest.json") and "/v1/" in k)
        obj = self.fixture.data[key]
        self.fixture.data[key] = Object(b"{}", obj.generation, obj.time_created, 2)
        self.assertIn("document_invalid", self.fixture.collector().collect("fvg")["critical_causes"])

    def test_missing_payload_metadata_and_304(self):
        key = next(k for k in self.fixture.data if "/municipalities/" in k)
        del self.fixture.data[key]
        self.assertIn("referenced_object_missing_or_wrong_size", self.fixture.collector().collect("fvg")["critical_causes"])
        self.fixture.http_hook = lambda *args: {"status": 304, "body": b"", "headers": {}}
        self.assertIn("http_pointer_unreadable", self.fixture.collector().collect("fvg")["critical_causes"])

    def test_proven_http_anomaly_survives_later_budget_expiry(self):
        newer = Fixture(RUN+timedelta(hours=12))
        url = c.BASES["fvg"]+"latest.json"
        self.fixture.public[url] = newer.public[url]
        original = self.fixture.get
        def expire(key, *args):
            if not key.startswith("https://") and key.endswith("manifest.json"):
                raise BudgetExpired()
            return original(key, *args)
        self.fixture.get = expire
        obs = self.fixture.collector().collect("fvg")
        self.assertTrue(obs["indeterminate"])
        self.assertIn("http_pointer_newer_than_storage", obs["critical_causes"])
        self.assertEqual(evaluate("fvg", NOW, NOW, obs)["critical_active"], 1)

    def test_budget_expires_without_false_green(self):
        times = iter([0, 76])
        budget = Budget(75, clock=lambda: next(times))
        obs = self.fixture.collector(budget=budget).collect("fvg")
        self.assertTrue(obs["indeterminate"])
        self.assertFalse(obs["complete"])


class MemoryState:
    def __init__(self):
        self.items = {}
        self.fail = False
        self.lost_once = False

    def read(self, product, budget):
        if self.fail:
            raise Unavailable("state unavailable")
        return deepcopy(self.items.get(product, ("0", None)))

    def cas(self, product, version, value, budget):
        old, _ = self.items.get(product, ("0", None))
        if old != version:
            raise Conflict()
        self.items[product] = str(int(old)+1), deepcopy(value)
        if self.lost_once:
            self.lost_once = False
            raise Unavailable("lost CAS response")
        return str(int(old)+1)


class MemoryMetrics:
    def __init__(self):
        self.points, self.writes, self.fail, self.uncertain = {}, [], set(), set()

    def latest(self, product, metric, timestamp, budget):
        return self.points.get((product, metric))

    def write(self, product, metric, timestamp, value, budget):
        if metric in self.fail:
            raise Rejected()
        old = self.points.get((product, metric))
        if old and instant(timestamp) <= instant(old[0]):
            raise Rejected()
        self.writes.append((product, metric, timestamp, value))
        self.points[product, metric] = timestamp, value
        if metric in self.uncertain:
            raise Unavailable("lost response")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.state, self.metrics, self.logs = MemoryState(), MemoryMetrics(), []
        self.collector = Mock()
        self.collector.collect.return_value = observation()
        self.now = NOW
        self.runner = Runner(self.state, self.metrics, self.collector, now=lambda: self.now,
                             budget=Budget(), emit=self.logs.append)

    def test_duplicates_do_not_recompute_or_resend(self):
        self.runner.run_product("fvg", NOW)
        self.runner.run_product("fvg", NOW)
        self.assertEqual(len(self.metrics.writes), 3)
        self.assertEqual(self.collector.collect.call_count, 1)
        self.assertTrue(all(p["status"] == "confirmed" for p in self.state.items["fvg"][1]["outbox"].values()))

    def test_partial_write_recovers_only_missing_metric(self):
        self.metrics.fail.add("critical_active")
        first = self.runner.run_product("fvg", NOW)
        self.assertEqual(first["outbox"]["critical_active"]["status"], "rejected")
        self.metrics.fail.clear()
        second = self.runner.run_product("fvg", NOW)
        self.assertEqual(len(self.metrics.writes), 3)
        self.assertEqual(len({p[2] for p in self.metrics.writes}), 1)
        self.assertEqual(second["outbox"]["critical_active"]["status"], "confirmed")

    def test_uncertain_commit_reconciles_without_resend(self):
        self.metrics.uncertain.add("check_state")
        self.runner.run_product("fvg", NOW)
        second = self.runner.run_product("fvg", NOW)
        self.assertEqual(len(self.metrics.writes), 3)
        self.assertEqual(second["outbox"]["check_state"]["status"], "confirmed")

    def test_unknown_absent_prepared_point_is_not_blindly_retried(self):
        def lost_before_commit(*args):
            raise Unavailable("unknown")
        self.metrics.write = lost_before_commit
        first = self.runner.run_product("fvg", NOW)
        self.assertTrue(all(p["status"] == "prepared" for p in first["outbox"].values()))
        self.metrics.write = Mock()
        self.runner.run_product("fvg", NOW)
        self.metrics.write.assert_not_called()

    def test_lost_state_response_and_superseded_slot(self):
        self.state.lost_once = True
        self.runner.run_product("fvg", NOW)
        self.now += timedelta(minutes=30)
        newer = self.runner.run_product("fvg", self.now)
        before = len(self.metrics.writes)
        old = self.runner.run_product("fvg", NOW)
        self.assertEqual(old, newer)
        self.assertEqual(len(self.metrics.writes), before)

    def test_metric_conflict_is_not_silently_acknowledged(self):
        self.metrics.points["fvg", "critical_active"] = stamp(NOW), 1
        state = self.runner.run_product("fvg", NOW)
        self.assertEqual(state["outbox"]["critical_active"]["status"], "conflict")
        self.assertEqual(len(self.metrics.writes), 2)

    def test_concurrent_duplicate_cas_loser_does_not_publish_own_result(self):
        original = self.state.cas
        triggered = [False]
        winner_collector = Mock()
        winner_collector.collect.return_value = observation(complete=False, critical=["document_invalid"])
        winner = Runner(self.state, self.metrics, winner_collector, now=lambda: NOW,
                        budget=Budget(), emit=self.logs.append)
        def racing(product, version, value, budget):
            if not triggered[0]:
                triggered[0] = True
                winner.run_product(product, NOW)
            return original(product, version, value, budget)
        self.state.cas = racing
        state = self.runner.run_product("fvg", NOW)
        self.assertEqual(state["critical_active"], 1)
        self.assertEqual(len(self.metrics.writes), 3)
        self.assertEqual(self.metrics.points["fvg", "critical_active"][1], 1)

    def test_late_metric_write_cannot_replace_a_newer_timestamp(self):
        real_write = self.metrics.write
        def delayed(product, metric, timestamp, value, budget):
            self.metrics.points[product, metric] = stamp(NOW+timedelta(minutes=30)), 1
            real_write(product, metric, timestamp, value, budget)
        self.metrics.write = delayed
        self.runner.run_product("fvg", NOW)
        final = self.runner.run_product("fvg", NOW)
        self.assertTrue(all(p["status"] == "superseded" for p in final["outbox"].values()))
        self.assertFalse(self.metrics.writes)

    def test_critical_is_logged_even_if_metric_read_fails(self):
        self.collector.collect.return_value = observation(complete=False, critical=["document_invalid"])
        self.metrics.latest = Mock(side_effect=Unavailable("Monitoring down"))
        self.runner.run(NOW)
        records = [r for r in self.logs if r["event"] == "icon2i_freshness_check"]
        self.assertEqual(len(records), 2)
        self.assertTrue(all(r["critical_active"] == 1 for r in records))
        self.assertTrue(all("document_invalid" in r["causes"] for r in records))

    def test_failed_metric_read_is_logged_and_critical_history_survives(self):
        self.collector.collect.return_value = observation(complete=False, critical=["resolver_unreadable"])
        self.metrics.fail.add("critical_active")
        first = self.runner.run_product("fvg", NOW)
        self.now += timedelta(minutes=30)
        self.collector.collect.return_value = observation(complete=False, indeterminate=True)
        second = self.runner.run_product("fvg", self.now)
        self.assertEqual(second["critical_active"], 1)
        self.assertIn("resolver_unreadable", second["causes"])
        self.assertEqual(first["outbox"]["critical_active"]["status"], "rejected")

    def test_corrupt_state_never_resets_critical_to_zero(self):
        self.state.items["fvg"] = ("1", {"schema_version": 1})
        self.runner.run(NOW)
        self.assertFalse(any(product == "fvg" for product, *_ in self.metrics.writes))
        self.assertTrue(any(r["event"] == "icon2i_freshness_monitor_error" and r["product"] == "fvg" for r in self.logs))

    def test_state_failure_produces_no_heartbeat(self):
        self.state.fail = True
        result = self.runner.run(NOW)
        self.assertEqual(result, {"fvg": None, "national": None})
        self.assertFalse(self.metrics.writes)
        self.assertEqual(len(self.logs), 2)

    def test_stable_logs_and_six_series(self):
        result = self.runner.run(NOW)
        self.assertEqual(len(self.metrics.writes), 6)
        for state in result.values():
            validate_state(state, state["product"])
            record = log_record(state)
            for key in ("product", "scheduled_slot_utc", "check_state", "causes",
                        "indeterminate_count_last6", "http_comparison"):
                self.assertIn(key, record)


class AdapterTests(unittest.TestCase):
    def test_no_weather_write_capability(self):
        adapter = WeatherData(Mock())
        for forbidden in ("put", "cas", "delete", "upload"):
            self.assertFalse(hasattr(adapter, forbidden))
        with self.assertRaises(ValueError):
            adapter.url("private/other")
        with self.assertRaises(ValueError):
            MonitorState.key("../latest")

    def test_state_cas_uses_precondition_and_monitor_bucket(self):
        transport = Mock()
        transport.request.return_value = (200, b'{"generation":"12"}', {})
        adapter = MonitorState(transport)
        adapter.cas("fvg", "11", {"example": 1}, Budget())
        args, kwargs = transport.request.call_args
        self.assertIn("meteo-friul-weather-state", args[1])
        self.assertEqual(kwargs["params"]["ifGenerationMatch"], "11")
        self.assertEqual(kwargs["params"]["name"], "monitoring/icon2i-freshness/v1/fvg.json")

    def test_storage_rejects_invalid_generation_before_download(self):
        transport = Mock()
        transport.read_json.return_value = {"generation": "0", "size": "12", "timeCreated": PLANNED}
        with self.assertRaises(ValueError):
            WeatherData(transport).get(c.ROOTS["fvg"]+"latest.json", Budget())
        transport.request.assert_not_called()

    def test_metric_identity_and_timestamp(self):
        transport = Mock()
        transport.request.return_value = (200, b"{}", {})
        Metrics(transport).write("national", "critical_active", PLANNED, 1, Budget())
        series = transport.request.call_args.kwargs["json"]["timeSeries"][0]
        self.assertEqual(series["metric"]["labels"], {"product": "national"})
        self.assertEqual(series["resource"], {"type": "global", "labels": {"project_id": "meteo-friul"}})
        self.assertEqual(series["points"][0]["interval"]["endTime"], PLANNED)

    def test_cloud_mode_requires_explicit_slot_contract_before_credentials(self):
        from freshness_monitor.__main__ import main
        env = {"ICON2I_MONITOR_ALLOW_CLOUD": "1", "GOOGLE_CLOUD_PROJECT": "meteo-friul",
               "CLOUD_RUN_JOB": "meteofriul-icon2i-freshness",
               "CLOUD_RUN_TASK_COUNT": "1", "CLOUD_RUN_TASK_ATTEMPT": "0"}
        with patch.dict("os.environ", env, clear=True), patch("freshness_monitor.__main__.transports") as network, patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                main(["--cloud"])
            with self.assertRaises(SystemExit):
                main(["--cloud", "--scheduled-slot", PLANNED, "--use-execution-slot"])
            network.assert_not_called()

    def test_cli_and_import_are_safe_by_default(self):
        from freshness_monitor.__main__ import main
        with patch.dict("os.environ", {}, clear=True), patch("freshness_monitor.__main__.transports") as network, patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                main([])
            with self.assertRaises(SystemExit):
                main(["--cloud"])
            network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
