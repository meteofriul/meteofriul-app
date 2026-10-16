"""HTTP-level tests for the loopback SQLite data-plane reader."""

from __future__ import annotations

from contextlib import closing
import gzip
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

try:
    from experiments.weather_autonomy.local_pipeline.http_data_plane import (
        IMMUTABLE_CACHE_CONTROL,
        LATEST_CACHE_CONTROL,
        make_server,
    )
    from experiments.weather_autonomy.local_pipeline.sqlite_object_store import (
        ObjectStoreError,
        SQLiteObjectStore,
    )
except ModuleNotFoundError:  # unittest discovery with weather_autonomy on sys.path
    from local_pipeline.http_data_plane import (
        IMMUTABLE_CACHE_CONTROL,
        LATEST_CACHE_CONTROL,
        make_server,
    )
    from local_pipeline.sqlite_object_store import ObjectStoreError, SQLiteObjectStore


ALLOWED_WEB_ORIGIN = "http://127.0.0.1:5174"
ALLOWED_CAPACITOR_ORIGIN = "https://localhost"
ALLOWED_LOCAL_PILOT_CAPACITOR_ORIGIN = "https://localhost"
RUN_ID = "20260903T000000Z"
LATEST_KEY = "weather/v1/icon2i/latest.json"
CAMS_LEGACY_LATEST_KEY = "weather/v1/cams_europe/latest.json"
CAMS_POLLEN_LEGACY_LATEST_KEY = "weather/v1/cams_europe_pollen/latest.json"
CAMS_FAMILY_LATEST_KEY = "weather/v1/families/cams/latest.json"
CAMS_FAMILY_RELEASE_KEY = (
    f"weather/v1/families/cams/runs/{RUN_ID}/release.json"
)
MANIFEST_KEY = f"weather/v1/icon2i/runs/{RUN_ID}/manifest.json"
CAMS_MANIFEST_KEY = f"weather/v1/cams_europe/runs/{RUN_ID}/manifest.json"
CAMS_POLLEN_MANIFEST_KEY = (
    f"weather/v1/cams_europe_pollen/runs/{RUN_ID}/manifest.json"
)
OBJECT_KEY = f"weather/v1/icon2i/runs/{RUN_ID}/municipalities/030129.json"
CAMS_OBJECT_KEY = (
    f"weather/v1/cams_europe/runs/{RUN_ID}/municipalities/093033.json"
)
CAMS_POLLEN_OBJECT_KEY = (
    f"weather/v1/cams_europe_pollen/runs/{RUN_ID}/municipalities/093033.json"
)
LARGE_KEY = f"weather/v1/icon2i/runs/{RUN_ID}/municipalities/030130.json"


class HttpDataPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="meteofriul-http-plane-")
        self.store = SQLiteObjectStore(Path(self.temporary.name) / "objects.sqlite3")
        self.latest_body = json.dumps(
            {
                "schema_version": 1,
                "provider": "icon2i",
                "run_id": RUN_ID,
                "manifest_key": MANIFEST_KEY,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        self.manifest_body = json.dumps(
            {"schema_version": 1, "provider": "icon2i", "object_count": 1},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        self.object_body = json.dumps(
            {"city": "Pordenone", "hours": list(range(48)), "source": "ICON-2I"},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        self.family_latest_body = json.dumps(
            {"family": "cams", "run_id": RUN_ID, "revision": 1},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        self.family_release_body = json.dumps(
            {
                "family": "cams",
                "run_id": RUN_ID,
                "components": ["core", "pollen"],
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        for key, body, kind in (
            (LATEST_KEY, self.latest_body, "latest-pointer"),
            (MANIFEST_KEY, self.manifest_body, "run-manifest"),
            (CAMS_MANIFEST_KEY, self.manifest_body, "run-manifest"),
            (CAMS_POLLEN_MANIFEST_KEY, self.manifest_body, "run-manifest"),
            (OBJECT_KEY, self.object_body, "run-object"),
            (CAMS_OBJECT_KEY, self.object_body, "run-object"),
            (CAMS_POLLEN_OBJECT_KEY, self.object_body, "run-object"),
            (
                CAMS_FAMILY_LATEST_KEY,
                self.family_latest_body,
                "cams-family-latest",
            ),
            (
                CAMS_FAMILY_RELEASE_KEY,
                self.family_release_body,
                "cams-family-release",
            ),
            (CAMS_LEGACY_LATEST_KEY, self.latest_body, "latest-pointer"),
            (CAMS_POLLEN_LEGACY_LATEST_KEY, self.latest_body, "latest-pointer"),
            (LARGE_KEY, b'"' + b"x" * 2048 + b'"', "run-object"),
        ):
            self.store.put(
                key,
                body,
                content_type="application/json",
                metadata={"kind": kind},
            )
        self.server = make_server(
            self.store,
            port=0,
            allowed_origins={ALLOWED_WEB_ORIGIN, ALLOWED_CAPACITOR_ORIGIN},
            max_response_bytes=1024,
        )
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        server=None,
    ) -> tuple[int, dict[str, str], bytes]:
        selected_server = server or self.server
        with closing(
            http.client.HTTPConnection(
                "127.0.0.1", selected_server.server_port, timeout=3
            )
        ) as connection:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            response_body = response.read()
            return (
                response.status,
                {key.lower(): value for key, value in response.getheaders()},
                response_body,
            )

    def test_json_headers_host_validation_and_explicit_cors(self):
        status, headers, body = self.request(
            "GET", "/" + OBJECT_KEY, headers={"Origin": ALLOWED_WEB_ORIGIN}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, self.object_body)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        self.assertEqual(headers["access-control-allow-origin"], ALLOWED_WEB_ORIGIN)
        self.assertEqual(headers["access-control-expose-headers"], "ETag")
        self.assertNotIn("access-control-allow-credentials", headers)
        self.assertEqual(
            {part.strip() for part in headers["vary"].split(",")},
            {"Origin", "Accept-Encoding"},
        )

        status, headers, _body = self.request(
            "GET", "/" + OBJECT_KEY, headers={"Origin": "http://evil.invalid"}
        )
        self.assertEqual(status, 403)
        self.assertNotIn("access-control-allow-origin", headers)

        status, _headers, _body = self.request(
            "GET",
            "/" + OBJECT_KEY,
            headers={"Host": f"evil.invalid:{self.server.server_port}"},
        )
        self.assertEqual(status, 403)

    def test_options_is_narrow_and_capacitor_origin_is_allowed(self):
        status, headers, body = self.request(
            "OPTIONS",
            "/" + LATEST_KEY,
            headers={
                "Origin": ALLOWED_CAPACITOR_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "If-None-Match",
            },
        )
        self.assertEqual(status, 204)
        self.assertEqual(body, b"")
        self.assertEqual(headers["access-control-allow-origin"], ALLOWED_CAPACITOR_ORIGIN)
        self.assertEqual(headers["access-control-allow-methods"], "GET, HEAD, OPTIONS")
        self.assertEqual(headers["access-control-allow-headers"], "If-None-Match")

        local_pilot = make_server(self.store, port=0, max_response_bytes=1024)
        local_pilot_thread = threading.Thread(
            target=local_pilot.serve_forever,
            daemon=True,
        )
        local_pilot_thread.start()
        try:
            local_response = self.request(
                "GET",
                "/" + LATEST_KEY,
                headers={"Origin": ALLOWED_LOCAL_PILOT_CAPACITOR_ORIGIN},
                server=local_pilot,
            )
            self.assertEqual(local_response[0], 200)
            self.assertEqual(
                local_response[1]["access-control-allow-origin"],
                ALLOWED_LOCAL_PILOT_CAPACITOR_ORIGIN,
            )
            obsolete_origin_response = self.request(
                "GET",
                "/" + LATEST_KEY,
                headers={"Origin": "http://localhost"},
                server=local_pilot,
            )
            self.assertEqual(obsolete_origin_response[0], 403)
            self.assertNotIn(
                "access-control-allow-origin",
                obsolete_origin_response[1],
            )
        finally:
            local_pilot.shutdown()
            local_pilot.server_close()
            local_pilot_thread.join(timeout=5)

        denied = self.request(
            "OPTIONS",
            "/" + LATEST_KEY,
            headers={
                "Origin": ALLOWED_WEB_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(denied[0], 403)
        denied_header = self.request(
            "OPTIONS",
            "/" + LATEST_KEY,
            headers={
                "Origin": ALLOWED_WEB_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        self.assertEqual(denied_header[0], 403)

    def test_path_queries_traversal_directories_and_missing_objects_are_rejected(self):
        rejected_paths = (
            f"/weather/v1/icon2i/runs/{RUN_ID}/objects/030129.json",
            f"/weather/v1/icon2i/runs/{RUN_ID}/municipalities/../latest.json",
            "/weather/v1/icon2i/runs/%2e%2e/latest.json",
            "/weather/v1/icon2i/latest.json?cache=no",
            "/weather/v1/icon2i/",
            "/weather/v1/icon2i/latest.txt",
            "/other/v1/icon2i/latest.json",
            "/weather/v1/cams/latest.json",
            "/weather/v1/cams_europe/latest.json",
            "/weather/v1/cams_europe_pollen/latest.json",
            "/weather/v1/unknown/latest.json",
            "/weather/v1/families/cams/runs/latest/release.json",
            f"/weather/v1/families/cams/runs/{RUN_ID}/manifest.json",
            f"/weather/v1/families/cams/runs/{RUN_ID}/release.json/extra",
            "/weather/v1/families/other/latest.json",
            "/weather/v1/icon2i/runs/20260903000000/manifest.json",
            "/weather/v1/icon2i/runs/20260903T000000/manifest.json",
            f"/weather/v1/icon2i/runs/{RUN_ID}/municipalities/30129.json",
            f"/weather/v1/icon2i/runs/{RUN_ID}/municipalities/0301290.json",
            f"/weather/v1/icon2i/runs/{RUN_ID}/municipalities/030129.json/extra",
            f"/weather/v1/icon2i/runs/{RUN_ID}/manifest.json/extra",
        )
        for path in rejected_paths:
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 400)
        self.assertEqual(
            self.request(
                "GET",
                f"/weather/v1/cams_europe/runs/{RUN_ID}/municipalities/030129.json",
            )[0],
            404,
        )

    def test_both_cams_components_serve_only_immutable_contract_objects(self):
        icon = self.request("GET", "/" + OBJECT_KEY)
        cams = self.request("GET", "/" + CAMS_OBJECT_KEY)
        pollen = self.request("GET", "/" + CAMS_POLLEN_OBJECT_KEY)
        core_manifest = self.request("GET", "/" + CAMS_MANIFEST_KEY)
        pollen_manifest = self.request("GET", "/" + CAMS_POLLEN_MANIFEST_KEY)
        self.assertEqual(
            (icon[0], cams[0], pollen[0], core_manifest[0], pollen_manifest[0]),
            (200, 200, 200, 200, 200),
        )
        self.assertEqual(icon[2], self.object_body)
        self.assertEqual(cams[2], self.object_body)
        self.assertEqual(pollen[2], self.object_body)
        self.assertEqual(core_manifest[2], self.manifest_body)
        self.assertEqual(pollen_manifest[2], self.manifest_body)

    def test_cams_family_routes_are_exposed_but_legacy_latest_are_denied(self):
        self.assertEqual(self.request("GET", "/" + LATEST_KEY)[0], 200)
        self.assertEqual(
            self.request("GET", "/" + CAMS_FAMILY_LATEST_KEY)[0],
            200,
        )
        self.assertEqual(
            self.request("GET", "/" + CAMS_FAMILY_RELEASE_KEY)[0],
            200,
        )
        # These objects deliberately exist in the backing store.  The HTTP
        # route rejects them before lookup, preventing independently selected
        # CAMS core and pollen pointers from ever reaching a client.
        for key in (CAMS_LEGACY_LATEST_KEY, CAMS_POLLEN_LEGACY_LATEST_KEY):
            with self.subTest(key=key):
                status, headers, body = self.request("GET", "/" + key)
                self.assertEqual(status, 400)
                self.assertEqual(headers["cache-control"], "no-store")
                self.assertEqual(json.loads(body)["error"], "object_path_not_allowed")

    def test_cams_family_latest_supports_cors_gzip_and_conditional_reads(self):
        first = self.request(
            "GET",
            "/" + CAMS_FAMILY_LATEST_KEY,
            headers={
                "Origin": ALLOWED_WEB_ORIGIN,
                "Accept-Encoding": "gzip",
            },
        )
        self.assertEqual(first[0], 200)
        self.assertEqual(gzip.decompress(first[2]), self.family_latest_body)
        self.assertEqual(first[1]["content-encoding"], "gzip")
        self.assertEqual(first[1]["cache-control"], LATEST_CACHE_CONTROL)
        self.assertEqual(
            first[1]["access-control-allow-origin"],
            ALLOWED_WEB_ORIGIN,
        )

        cached = self.request(
            "GET",
            "/" + CAMS_FAMILY_LATEST_KEY,
            headers={
                "Origin": ALLOWED_WEB_ORIGIN,
                "Accept-Encoding": "gzip",
                "If-None-Match": first[1]["etag"],
            },
        )
        self.assertEqual(cached[0], 304)
        self.assertEqual(cached[2], b"")
        self.assertEqual(cached[1]["cache-control"], LATEST_CACHE_CONTROL)

    def test_head_matches_get_headers_without_body(self):
        get_status, get_headers, get_body = self.request("GET", "/" + OBJECT_KEY)
        head_status, head_headers, head_body = self.request("HEAD", "/" + OBJECT_KEY)
        self.assertEqual((get_status, head_status), (200, 200))
        self.assertTrue(get_body)
        self.assertEqual(head_body, b"")
        for name in ("content-type", "content-length", "cache-control", "etag", "vary"):
            self.assertEqual(head_headers[name], get_headers[name])

    def test_gzip_is_deterministic_decodable_and_has_encoding_etag(self):
        first = self.request(
            "GET", "/" + OBJECT_KEY, headers={"Accept-Encoding": "br, gzip"}
        )
        second = self.request(
            "GET", "/" + OBJECT_KEY, headers={"Accept-Encoding": "gzip;q=1"}
        )
        self.assertEqual(first[0], 200)
        self.assertEqual(first[1]["content-encoding"], "gzip")
        self.assertEqual(gzip.decompress(first[2]), self.object_body)
        self.assertEqual(first[2], second[2])
        self.assertEqual(first[1]["etag"], second[1]["etag"])

        identity = self.request(
            "GET", "/" + OBJECT_KEY, headers={"Accept-Encoding": "gzip;q=0"}
        )
        self.assertNotIn("content-encoding", identity[1])
        self.assertNotEqual(identity[1]["etag"], first[1]["etag"])

    def test_if_none_match_returns_304_for_selected_representation(self):
        status, headers, _body = self.request("GET", "/" + OBJECT_KEY)
        self.assertEqual(status, 200)
        cached = self.request(
            "GET",
            "/" + OBJECT_KEY,
            headers={
                "If-None-Match": headers["etag"],
                "Origin": ALLOWED_WEB_ORIGIN,
            },
        )
        self.assertEqual(cached[0], 304)
        self.assertEqual(cached[2], b"")
        self.assertEqual(cached[1]["etag"], headers["etag"])
        self.assertEqual(cached[1]["access-control-expose-headers"], "ETag")
        self.assertEqual(cached[1]["cache-control"], IMMUTABLE_CACHE_CONTROL)

    def test_latest_is_short_lived_while_run_data_is_immutable(self):
        latest = self.request("GET", "/" + LATEST_KEY)
        family_latest = self.request("GET", "/" + CAMS_FAMILY_LATEST_KEY)
        family_release = self.request("GET", "/" + CAMS_FAMILY_RELEASE_KEY)
        manifest = self.request("GET", "/" + MANIFEST_KEY)
        run_object = self.request("GET", "/" + OBJECT_KEY)
        self.assertEqual(latest[1]["cache-control"], LATEST_CACHE_CONTROL)
        self.assertEqual(
            family_latest[1]["cache-control"],
            LATEST_CACHE_CONTROL,
        )
        self.assertEqual(
            family_release[1]["cache-control"],
            IMMUTABLE_CACHE_CONTROL,
        )
        self.assertEqual(manifest[1]["cache-control"], IMMUTABLE_CACHE_CONTROL)
        self.assertEqual(run_object[1]["cache-control"], IMMUTABLE_CACHE_CONTROL)

    def test_response_limit_is_checked_before_serving_body(self):
        status, headers, body = self.request(
            "GET", "/" + LARGE_KEY, headers={"Accept-Encoding": "gzip"}
        )
        self.assertEqual(status, 413)
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertEqual(json.loads(body)["error"], "response_limit_exceeded")

    def test_mutating_methods_are_405_and_cannot_change_objects(self):
        before_keys = self.store.list_keys()
        before = {key: self.store.get(key) for key in before_keys}
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                status, headers, body = self.request(
                    method,
                    "/" + LATEST_KEY,
                    headers={"Content-Type": "application/json"},
                    body=b'{"run_id":"attacker"}',
                )
                self.assertEqual(status, 405)
                self.assertEqual(headers["allow"], "GET, HEAD, OPTIONS")
                self.assertEqual(json.loads(body)["error"], "read_only")
        self.assertEqual(self.store.list_keys(), before_keys)
        self.assertEqual({key: self.store.get(key) for key in before_keys}, before)

    def test_server_operates_with_a_head_get_only_capability(self):
        calls = []

        class HeadGetOnlyReader:
            def head(_self, key):
                calls.append(("head", key))
                return self.store.head(key)

            def get(_self, key):
                calls.append(("get", key))
                return self.store.get(key)

        server = make_server(
            HeadGetOnlyReader(),
            port=0,
            allowed_origins={ALLOWED_WEB_ORIGIN},
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _headers, body = self.request(
                "GET", "/" + LATEST_KEY, server=server
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertEqual(200, status)
        self.assertEqual(self.latest_body, body)
        self.assertEqual(
            [("head", LATEST_KEY), ("get", LATEST_KEY)],
            calls,
        )

    def test_head_store_failure_returns_503_and_server_remains_available(self):
        class FailHeadOnceReader:
            failed = False

            def head(reader, key):
                if not reader.failed:
                    reader.failed = True
                    raise ObjectStoreError("private backing-store detail")
                return self.store.head(key)

            def get(reader, key):
                return self.store.get(key)

        server = make_server(FailHeadOnceReader(), port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            failed = self.request("GET", "/" + LATEST_KEY, server=server)
            recovered = self.request("GET", "/" + LATEST_KEY, server=server)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(503, failed[0])
        self.assertEqual("no-store", failed[1]["cache-control"])
        self.assertEqual(
            {"error": "object_store_unavailable"},
            json.loads(failed[2]),
        )
        self.assertNotIn(b"private", failed[2])
        self.assertEqual((200, self.latest_body), (recovered[0], recovered[2]))

    def test_get_store_failure_returns_503_and_head_keeps_server_available(self):
        class FailGetOnceReader:
            failed = False

            def head(reader, key):
                return self.store.head(key)

            def get(reader, key):
                if not reader.failed:
                    reader.failed = True
                    raise ObjectStoreError("private backing-store detail")
                return self.store.get(key)

        server = make_server(FailGetOnceReader(), port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            failed = self.request("GET", "/" + LATEST_KEY, server=server)
            recovered = self.request("HEAD", "/" + LATEST_KEY, server=server)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(503, failed[0])
        self.assertEqual("no-store", failed[1]["cache-control"])
        self.assertEqual(
            {"error": "object_store_unavailable"},
            json.loads(failed[2]),
        )
        self.assertNotIn(b"private", failed[2])
        self.assertEqual(200, recovered[0])
        self.assertEqual(b"", recovered[2])


if __name__ == "__main__":
    unittest.main()
