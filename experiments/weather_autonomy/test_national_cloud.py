"""Offline failure/race tests for the isolated national pilot cloud boundary."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import gzip
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import national_cloud_reader as http
import national_cloud_worker as worker
from national_cloud_publication import (PREFIX, POINTER_KEY, descriptor_for, load_run,
    publish_bundle, read_pointer, require_current_coverage)
from local_pipeline.national_icon_bundle import build_national_icon_bundle, canonical_json_bytes
from local_pipeline.sqlite_object_store import SQLiteObjectStore, ObjectNotFound, ObjectStoreError, PreconditionFailed
from test_serve_national_bundle_v2 import _sample_catalog

NOW = datetime(2026, 9, 20, 18, tzinfo=timezone.utc)


def sample_bundle(hour=0):
    catalog = _sample_catalog()
    run = datetime(2026, 9, 20, hour, tzinfo=timezone.utc)
    dates = [(run + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ") for h in range(73)]
    return build_national_icon_bundle(run_at=dates[0], generated_at=dates[0],
        catalog={"version": catalog["catalog_version"], "sha256": catalog["catalog_sha256"],
            "municipality_count": 3, "municipality_codes_sha256": catalog["municipality_codes_sha256"]},
        grid={"sha256": "b" * 64, "ni": 20, "nj": 20},
        metadata={"model": {"id": "icon-2i", "product": "test_profile"},
            "source": {"attribution": "Agenzia ItaliaMeteo", "license": "CC BY 4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/"},
            "variables": [{"id": "temperature_c", "unit": "degC", "data_type": "float", "nullable": False}]},
        time_axis=dates, municipality_cells={"001001": 11, "001002": 12, "002001": 13},
        cells=[{"grid_index": index, "latitude": lat, "longitude": lon,
            "values": {"temperature_c": [20.0 + hour] * 73}}
            for index, lat, lon in ((11, 41.9, 12.5), (12, 45., 9.), (13, 40., 15.))],
        tile_size_degrees="0.25")


class CloudNationalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="national-cloud-tests-")
        self.data = SQLiteObjectStore(Path(self.temp.name) / "data.sqlite")
        self.state = SQLiteObjectStore(Path(self.temp.name) / "state.sqlite")
        self.catalog = _sample_catalog()
        self.bundle = sample_bundle()

    def tearDown(self):
        self.temp.cleanup()

    def publish(self, bundle=None):
        return publish_bundle(self.data, bundle or self.bundle, self.catalog, now=NOW)

    def request(self, app, **env):
        response = []
        body = b"".join(app({"REQUEST_METHOD": "GET", "PATH_INFO": "/" + POINTER_KEY,
            "HTTP_HOST": http.PUBLIC_HOST, **env}, lambda status, headers: response.append((status, dict(headers)))))
        return *response[0], body

    def test_publish_manifest_last_readback_then_pointer_and_no_v1_write(self):
        keys = []
        original_put = self.data.put
        def put(key, body, **kwargs):
            keys.append(key)
            return original_put(key, body, **kwargs)
        with patch.object(self.data, "put", side_effect=put):
            pointer = self.publish()
        self.assertEqual(keys[-1], PREFIX + self.bundle.manifest_path)
        self.assertTrue(all(key.startswith(PREFIX + "runs/") for key in keys))
        self.assertEqual(pointer["previous"], None)
        self.assertEqual(pointer["catalog"]["municipality_count"], 3)
        self.assertEqual(read_pointer(self.data, self.catalog)[0], pointer)
        self.assertEqual(load_run(self.data, pointer["manifest"], self.catalog)[0], self.bundle)

    def test_incomplete_write_never_publishes_pointer(self):
        failing_key = PREFIX + self.bundle.block_documents[1][0]
        original_put = self.data.put
        def put(key, body, **kwargs):
            if key == failing_key:
                raise ObjectStoreError("transport down")
            return original_put(key, body, **kwargs)
        with patch.object(self.data, "put", side_effect=put), self.assertRaises(ObjectStoreError):
            self.publish()
        with self.assertRaises(ObjectNotFound):
            self.data.get(POINTER_KEY)
        # Identical immutable partial writes can be resumed.
        self.publish()

    def test_corrupt_immutable_object_is_never_replaced_or_promoted(self):
        path, _body = self.bundle.block_documents[0]
        self.data.put(PREFIX + path, b"{}")
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.data.get(PREFIX + path).body, b"{}")
        with self.assertRaises(ObjectNotFound):
            self.data.get(POINTER_KEY)

    def test_pointer_cas_conflict_keeps_winner_and_lost_response_reconciles(self):
        original_cas = self.data.compare_and_swap
        def lost_response(key, body, **kwargs):
            result = original_cas(key, body, **kwargs)
            if key == POINTER_KEY:
                raise ObjectStoreError("response lost")
            return result
        with patch.object(self.data, "compare_and_swap", side_effect=lost_response):
            first = self.publish()
        with patch.object(self.data, "compare_and_swap", side_effect=PreconditionFailed(POINTER_KEY)):
            with self.assertRaises(PreconditionFailed):
                self.publish(sample_bundle(12))
        self.assertEqual(read_pointer(self.data, self.catalog)[0], first)

    def test_regression_rejected_and_previous_run_remains_available(self):
        first = self.publish()
        plane = http.NationalReadPlane(self.data, self.catalog, clock=lambda: 0, now=lambda: NOW)
        plane.current()
        second = self.publish(sample_bundle(12))
        plane.refresh_at = 0
        self.assertEqual(plane.current().source_run_id, second["source_run_id"])
        self.assertEqual(plane.document(self.bundle.block_documents[0][0]), self.bundle.block_documents[0][1])
        self.assertEqual(second["previous"]["manifest"], first["manifest"])
        with self.assertRaises(ValueError):
            self.publish()
        with self.assertRaises(ObjectNotFound):
            plane.document("runs/20260919T000000Z/manifest.json")

    def test_freshness_boundary_and_stale_reader_fail_closed(self):
        self.publish()
        manifest = json.loads(self.bundle.manifest_json)
        boundary = datetime(2026, 9, 22, 13, tzinfo=timezone.utc)
        require_current_coverage(manifest, boundary)
        with self.assertRaises(ValueError):
            require_current_coverage(manifest, boundary + timedelta(microseconds=1))
        plane = http.NationalReadPlane(self.data, self.catalog, now=lambda: boundary + timedelta(hours=1))
        self.assertTrue(self.request(http.NationalApplication(lambda: plane))[0].startswith("503"))

    def test_publication_rechecks_freshness_after_full_readback(self):
        with self.assertRaises(ValueError):
            publish_bundle(self.data, self.bundle, self.catalog, now=NOW,
                clock=lambda: datetime(2026, 9, 23, tzinfo=timezone.utc))
        with self.assertRaises(ObjectNotFound):
            self.data.get(POINTER_KEY)

    def test_http_guards_do_not_open_storage(self):
        factory = Mock()
        app = http.NationalApplication(factory)
        cases = [{"REQUEST_METHOD": "POST"}, {"PATH_INFO": "/weather/v1/icon2i/latest.json"},
            {"PATH_INFO": "/state/national-icon/private"}, {"HTTP_HOST": "evil.test"},
            {"HTTP_ORIGIN": "https://evil.test"}, {"QUERY_STRING": "x=1"},
            {"RAW_URI": "/weather/v2/%69con2i/pilot.json"},
            {"PATH_INFO": "/" + PREFIX + "resolve.json", "QUERY_STRING": "city=Roma&city=Milano"}]
        for env in cases:
            with self.subTest(env=env):
                self.assertNotEqual(self.request(app, **env)[0], "200 OK")
        factory.assert_not_called()

    def test_http_resolve_search_blocks_gzip_head_etag(self):
        self.publish()
        plane = http.NationalReadPlane(self.data, self.catalog, now=lambda: NOW)
        app = http.NationalApplication(lambda: plane)
        status, headers, body = self.request(app, PATH_INFO="/" + PREFIX + "resolve.json", QUERY_STRING="city=Roma&province=RM")
        self.assertEqual(status, "200 OK")
        resolution = json.loads(body)
        self.assertEqual(resolution["municipality"]["istat_code"], "001001")
        self.assertEqual(headers["Cache-Control"], "no-store")
        path = "/" + PREFIX + resolution["block_path"]
        status, headers, body = self.request(app, PATH_INFO=path, HTTP_ACCEPT_ENCODING="gzip")
        self.assertEqual(status, "200 OK")
        self.assertEqual(json.loads(gzip.decompress(body))["source_run_id"], "20260920T000000Z")
        self.assertEqual(self.request(app, PATH_INFO=path, HTTP_ACCEPT_ENCODING="gzip", HTTP_IF_NONE_MATCH=headers["ETag"])[0], "304 Not Modified")
        self.assertEqual(self.request(app, PATH_INFO=path, REQUEST_METHOD="HEAD")[2], b"")
        status, _headers, body = self.request(app, PATH_INFO="/" + PREFIX + "search.json", QUERY_STRING="q=San")
        self.assertEqual(status, "200 OK")
        self.assertEqual(len(json.loads(body)["results"]), 2)

    def test_cold_resolver_fetches_only_pointer_manifest_index_and_selected_block(self):
        self.publish()
        plane = http.NationalReadPlane(self.data, self.catalog, clock=lambda: 0, now=lambda: NOW)
        reads = []
        original_get = self.data.get
        def get(key):
            reads.append(key)
            return original_get(key)
        with patch.object(self.data, "get", side_effect=get):
            reader = plane.current()
            self.assertEqual(len(reads), 3)
            resolution = json.loads(reader.resolve(city="Roma", province="RM", latitude=None, longitude=None))
            self.assertEqual(reads, [POINTER_KEY, PREFIX + self.bundle.manifest_path,
                PREFIX + self.bundle.index_path, PREFIX + resolution["block_path"]])
            reader.search("Roma")
            plane.document(resolution["block_path"])
            reader.resolve(city="Roma", province="RM", latitude=None, longitude=None)
            self.assertEqual(len(reads), 4)

    def test_lazy_reader_rejects_corrupt_selected_block_without_reading_other_blocks(self):
        self.publish()
        plane = http.NationalReadPlane(self.data, self.catalog, clock=lambda: 0, now=lambda: NOW)
        reader = plane.current()
        original_get = self.data.get
        def get(key):
            obj = original_get(key)
            return Mock(body=b"{}") if "/blocks/" in key else obj
        with patch.object(self.data, "get", side_effect=get), self.assertRaises(ValueError):
            reader.resolve(city="Roma", province="RM", latitude=None, longitude=None)
        self.assertEqual(reader.cache_bytes, 0)

    def test_wrong_project_and_unapproved_job_fail_before_cloud_client(self):
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "meteo-friul"}, clear=True):
            with self.assertRaises(ValueError): http.build_reader()
            with self.assertRaises(ValueError): worker.run()
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "meteofriul-pilot-20260906"}, clear=True):
            with self.assertRaises(ValueError): worker.run()

    def test_worker_single_slot_and_no_source_download_for_existing_run(self):
        acquire = Mock(return_value=(self.bundle, {"fixture": "mapping"}))
        discover = Mock(return_value="2026092000")
        points = {"artifact_sha256": "c" * 64}
        result = worker.run_once(self.state, self.data, self.catalog, points,
            now=NOW, execution="pilot-national-icon-first", acquire=acquire, discover=discover)
        self.assertEqual(result["status"], "published")
        second = worker.run_once(self.state, self.data, self.catalog, points,
            now=NOW, execution="pilot-national-icon-other", acquire=acquire, discover=discover)
        self.assertEqual(second["reason"], "slot_already_claimed")
        discover.return_value = None
        later = worker.run_once(self.state, self.data, self.catalog, points,
            now=NOW + timedelta(hours=7), execution="pilot-national-icon-next", acquire=acquire, discover=discover)
        self.assertEqual(later["reason"], "source_not_advanced")
        self.assertEqual(acquire.call_count, 1)

    def test_worker_missing_referenced_data_is_not_treated_as_empty_state(self):
        self.publish()
        original_get = self.data.get
        path = PREFIX + self.bundle.block_documents[0][0]
        def get(key):
            if key == path: raise ObjectNotFound(key)
            return original_get(key)
        acquire, discover = Mock(), Mock()
        with patch.object(self.data, "get", side_effect=get), self.assertRaises(ObjectNotFound):
            worker.run_once(self.state, self.data, self.catalog, {}, now=NOW,
                execution="pilot-national-icon-test", acquire=acquire, discover=discover)
        acquire.assert_not_called()
        discover.assert_not_called()

    def test_worker_recovers_complete_manifest_without_redownloading_source(self):
        points = {"artifact_sha256": "c" * 64}
        worker.record_preparation(self.state, self.bundle, {"fixture": "mapping"}, self.catalog, points)
        for path, body in self.bundle.publication_order():
            self.data.put(PREFIX + path, body)
        acquire = Mock()
        result = worker.run_once(self.state, self.data, self.catalog, points, now=NOW,
            execution="pilot-national-icon-recovery", acquire=acquire, discover=lambda *_: "2026092000")
        self.assertEqual(result["status"], "published")
        acquire.assert_not_called()

    def test_acquisition_removes_elapsed_measurements_from_immutable_mapping(self):
        snapshot = {"provenance": {"T_2M": {"elapsed_seconds": 1.234, "sha256": "a" * 64}}}
        with patch("benchmark_national_icon_real.acquire_real_source", return_value=snapshot), \
                patch("benchmark_national_icon_real.build_real_bundle", return_value=self.bundle), \
                patch("benchmark_national_icon_real.build_mapping_artifact", side_effect=lambda **kwargs: kwargs["snapshot"]["provenance"]):
            _bundle, mapping = worker.acquire_real_bundle(catalog=self.catalog, points={},
                run="2026092000", generated_at="2026-09-20T18:00:00Z", now=NOW)
        self.assertEqual(mapping, {"T_2M": {"sha256": "a" * 64}})


if __name__ == "__main__":
    unittest.main()
