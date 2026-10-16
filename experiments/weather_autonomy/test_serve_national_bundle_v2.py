"""Focused tests for the loopback-only national ICON v2 pilot server."""

from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

try:
    from experiments.weather_autonomy.local_pipeline.national_icon_bundle import (
        build_national_icon_bundle,
        canonical_json_bytes,
    )
    from experiments.weather_autonomy import serve_national_bundle_v2 as server_module
except ModuleNotFoundError:
    from local_pipeline.national_icon_bundle import (
        build_national_icon_bundle,
        canonical_json_bytes,
    )
    import serve_national_bundle_v2 as server_module


RUN_AT = "2026-09-20T00:00:00Z"
GENERATED_AT = "2026-09-20T00:05:00Z"
CODES = ("001001", "001002", "002001")
CATALOG_SHA = "a" * 64
GRID_SHA = "b" * 64
CODES_SHA = hashlib.sha256(canonical_json_bytes(list(CODES))).hexdigest()
ORIGIN = "http://127.0.0.1:5174"


def _iso(hour: int) -> str:
    value = datetime(2026, 9, 20, tzinfo=timezone.utc) + timedelta(hours=hour)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sample_bundle():
    variables = [
        {"id": "temperature_c", "unit": "degC", "data_type": "float", "nullable": False},
        {"id": "weather_code", "unit": "wmo_code", "data_type": "integer", "nullable": False},
    ]
    cells = []
    for grid_index, latitude, longitude, offset in (
        (11, 41.9, 12.5, 0),
        (12, 45.0, 9.0, 1),
        (13, 40.0, 15.0, 2),
    ):
        cells.append(
            {
                "grid_index": grid_index,
                "latitude": latitude,
                "longitude": longitude,
                "values": {
                    "temperature_c": [20.0 + offset, 21.0 + offset, 22.0 + offset],
                    "weather_code": [0, 1, 2],
                },
            }
        )
    return build_national_icon_bundle(
        run_at=RUN_AT,
        generated_at=GENERATED_AT,
        catalog={
            "version": "test-national-v1",
            "sha256": CATALOG_SHA,
            "municipality_count": len(CODES),
            "municipality_codes_sha256": CODES_SHA,
        },
        grid={"sha256": GRID_SHA, "ni": 20, "nj": 20},
        metadata={
            "model": {"id": "icon-2i", "product": "test_profile"},
            "source": {
                "attribution": "Agenzia ItaliaMeteo",
                "license": "CC BY 4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
            },
            "variables": variables,
        },
        time_axis=[_iso(0), _iso(1), _iso(2)],
        municipality_cells={"001001": 11, "001002": 12, "002001": 13},
        cells=cells,
        tile_size_degrees="0.25",
    )


def _municipality(
    istat_code: str,
    name: str,
    province: str,
    province_name: str,
    latitude: float,
    longitude: float,
) -> dict:
    return {
        "istat_code": istat_code,
        "name": name,
        "italian_name": name,
        "alternate_name": "",
        "province_abbreviation": province,
        "uts_name": province_name,
        "region_name": "Regione test",
        "region_iso": "IT-00",
        "representative_point": {
            "latitude": latitude,
            "longitude": longitude,
            "method": "test",
        },
    }


def _sample_catalog() -> dict:
    return {
        "catalog_version": "test-national-v1",
        "catalog_sha256": CATALOG_SHA,
        "municipality_count": len(CODES),
        "municipality_codes_sha256": CODES_SHA,
        "municipalities": [
            _municipality("001001", "Roma", "RM", "Roma", 41.9, 12.5),
            _municipality("001002", "San Pietro", "AA", "Provincia Alfa", 45.0, 9.0),
            _municipality("002001", "San Pietro", "BB", "Provincia Beta", 40.0, 15.0),
        ],
    }


def _write_bundle(root: Path):
    bundle = _sample_bundle()
    for relative, payload in bundle.publication_order():
        target = root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return bundle


class NationalBundleV2ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="meteofriul-national-server-")
        self.root = Path(self.temporary.name) / "bundle"
        self.root.mkdir()
        self.bundle = _write_bundle(self.root)
        self.catalog = _sample_catalog()
        self.catalog_path = Path(self.temporary.name) / "catalog.json"
        self.catalog_path.write_text("{}", encoding="utf-8")
        self.service = self._build_service()
        self.thread = threading.Thread(
            target=self.service.server.serve_forever,
            daemon=True,
        )
        self.thread.start()

    def tearDown(self) -> None:
        if getattr(self, "service", None) is not None:
            self.service.server.shutdown()
            self.service.close()
        if getattr(self, "thread", None) is not None:
            self.thread.join(timeout=5)
        self.temporary.cleanup()

    def _build_service(self, *, root: Path | None = None, catalog: dict | None = None):
        selected_catalog = self.catalog if catalog is None else catalog
        return server_module.build_service(
            server_module.ServerConfig(
                bundle_dir=root or self.root,
                catalog_json=self.catalog_path,
                port=0,
            ),
            catalog_loader=lambda _path: selected_catalog,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        with closing(
            http.client.HTTPConnection(
                "127.0.0.1",
                self.service.server.server_port,
                timeout=3,
            )
        ) as connection:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return (
                response.status,
                {key.lower(): value for key, value in response.getheaders()},
                response.read(),
            )

    def test_serves_verified_pointer_manifest_index_and_blocks_with_http_cache_contract(self):
        prefix = server_module.PROVIDER_PREFIX
        pointer_status, pointer_headers, pointer_body = self.request(
            "GET",
            f"{prefix}/pilot.json",
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(pointer_status, 200)
        pointer = json.loads(pointer_body)
        self.assertEqual(pointer["contract"], "weather/v2/icon2i")
        self.assertEqual(pointer["source_run_id"], "20260920T000000Z")
        self.assertEqual(pointer_headers["cache-control"], "no-store")
        self.assertEqual(pointer_headers["access-control-allow-origin"], ORIGIN)

        for descriptor in (pointer["manifest"], pointer["index"]):
            with self.subTest(path=descriptor["path"]):
                status, headers, body = self.request(
                    "GET",
                    f"{prefix}/{descriptor['path']}",
                    headers={"Accept-Encoding": "gzip"},
                )
                decoded = gzip.decompress(body)
                self.assertEqual(status, 200)
                self.assertEqual(len(decoded), descriptor["json_bytes"])
                self.assertEqual(hashlib.sha256(decoded).hexdigest(), descriptor["sha256"])
                self.assertEqual(headers["content-encoding"], "gzip")
                self.assertEqual(headers["cache-control"], server_module.IMMUTABLE_CACHE_CONTROL)

        block_path, block_body = self.bundle.block_documents[0]
        status, headers, body = self.request("GET", f"{prefix}/{block_path}")
        self.assertEqual((status, body), (200, block_body))
        cached = self.request(
            "GET",
            f"{prefix}/{block_path}",
            headers={"If-None-Match": headers["etag"]},
        )
        self.assertEqual((cached[0], cached[2]), (304, b""))
        head = self.request("HEAD", f"{prefix}/{block_path}")
        self.assertEqual((head[0], head[2]), (200, b""))
        self.assertEqual(head[1]["content-length"], str(len(block_body)))

    def test_resolver_uses_exact_name_province_or_same_name_coordinate_tie_break_only(self):
        prefix = server_module.PROVIDER_PREFIX
        exact = self.request("GET", f"{prefix}/resolve.json?city=Roma")
        self.assertEqual(exact[0], 200)
        exact_document = json.loads(exact[2])
        self.assertEqual(exact_document["municipality"]["istat_code"], "001001")
        self.assertEqual(exact_document["cell_id"], "g000011")
        self.assertEqual(exact_document["block_path"], exact_document["manifest"]["path"].replace(
            "manifest.json", f"blocks/{exact_document['block_id']}.json"
        ))
        self.assertEqual(exact[1]["cache-control"], "no-store")

        province = self.request(
            "GET",
            f"{prefix}/resolve.json?city=San%20Pietro&province=BB&lat=&lon=",
        )
        self.assertEqual(province[0], 200)
        self.assertEqual(json.loads(province[2])["municipality"]["istat_code"], "002001")

        coordinate = self.request(
            "GET",
            f"{prefix}/resolve.json?city=San%20Pietro&lat=45.1&lon=9.1",
        )
        self.assertEqual(coordinate[0], 200)
        self.assertEqual(json.loads(coordinate[2])["municipality"]["istat_code"], "001002")

        ambiguous = self.request("GET", f"{prefix}/resolve.json?city=San%20Pietro")
        self.assertEqual(ambiguous[0], 409)
        self.assertEqual(json.loads(ambiguous[2]), {"error": "municipality_ambiguous"})
        # Coordinates do not turn a non-matching name into a nearest search.
        unknown = self.request(
            "GET",
            f"{prefix}/resolve.json?city=Nome%20inesistente&lat=41.9&lon=12.5",
        )
        self.assertEqual(unknown[0], 404)
        self.assertEqual(json.loads(unknown[2]), {"error": "municipality_not_found"})

    def test_search_is_bounded_ranked_deduplicated_and_returns_complete_identity(self):
        prefix = server_module.PROVIDER_PREFIX

        exact = self.request("GET", f"{prefix}/search.json?q=Roma")
        self.assertEqual(exact[0], 200)
        self.assertEqual(exact[1]["cache-control"], "no-store")
        exact_document = json.loads(exact[2])
        self.assertEqual(
            exact_document,
            {
                "schema_version": 1,
                "kind": server_module.SEARCH_KIND,
                "contract": "weather/v2/icon2i",
                "status": "experimental_local_pilot_only",
                "query": "roma",
                "results": [
                    {
                        "name": "Roma",
                        "province": "RM",
                        "province_name": "Roma",
                        "region_name": "Regione test",
                        "region_iso": "IT-00",
                        "latitude": 41.9,
                        "longitude": 12.5,
                        "istat_code": "001001",
                    }
                ],
            },
        )

        prefix_match = json.loads(
            self.request("GET", f"{prefix}/search.json?q=san")[2]
        )
        self.assertEqual(
            [result["istat_code"] for result in prefix_match["results"]],
            ["001002", "002001"],
        )
        self.assertLessEqual(
            len(prefix_match["results"]), server_module.MAX_SEARCH_RESULTS
        )
        word_match = json.loads(
            self.request("GET", f"{prefix}/search.json?q=piet")[2]
        )
        self.assertEqual(len(word_match["results"]), 2)
        punctuated_match = json.loads(
            self.request("GET", f"{prefix}/search.json?q=san-p")[2]
        )
        self.assertEqual(punctuated_match["query"], "san p")
        self.assertEqual(len(punctuated_match["results"]), 2)
        contains_match = json.loads(
            self.request("GET", f"{prefix}/search.json?q=ietr")[2]
        )
        self.assertEqual(len(contains_match["results"]), 2)
        missing = json.loads(
            self.request("GET", f"{prefix}/search.json?q=urbino")[2]
        )
        self.assertEqual(missing["results"], [])

    def test_strict_query_path_host_cors_and_method_guards(self):
        prefix = server_module.PROVIDER_PREFIX
        rejected = (
            f"{prefix}/resolve.json?city=Roma&lat=41.9",
            f"{prefix}/resolve.json?city=Roma&city=Milano",
            f"{prefix}/resolve.json?city=Roma&extra=1",
            f"{prefix}/resolve.json?city=%ZZ",
            f"{prefix}/search.json?q=r",
            f"{prefix}/search.json?q=roma&q=milano",
            f"{prefix}/search.json?city=roma",
            f"{prefix}/search.json?q=%ZZ",
            f"{prefix}/pilot.json?x=1",
            f"{prefix}/runs/%2e%2e/manifest.json",
            f"{prefix}//pilot.json",
            "/weather/v1/icon2i/latest.json",
        )
        for path in rejected:
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 400)

        denied_origin = self.request(
            "GET",
            f"{prefix}/pilot.json",
            headers={"Origin": "http://evil.invalid"},
        )
        self.assertEqual(denied_origin[0], 403)
        self.assertNotIn("access-control-allow-origin", denied_origin[1])
        denied_host = self.request(
            "GET",
            f"{prefix}/pilot.json",
            headers={"Host": f"evil.invalid:{self.service.server.server_port}"},
        )
        self.assertEqual(denied_host[0], 403)
        read_only = self.request("POST", f"{prefix}/pilot.json", body=b"{}")
        self.assertEqual(read_only[0], 405)
        self.assertEqual(read_only[1]["allow"], "GET, HEAD, OPTIONS")

        preflight = self.request(
            "OPTIONS",
            f"{prefix}/resolve.json?city=Roma",
            headers={
                "Origin": "https://localhost",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "If-None-Match",
            },
        )
        self.assertEqual(preflight[0], 204)
        self.assertEqual(preflight[1]["access-control-allow-origin"], "https://localhost")

    def test_startup_rejects_tampering_extra_files_and_catalog_mismatch_before_binding(self):
        self.service.server.shutdown()
        self.service.close()
        self.thread.join(timeout=5)
        self.service = None
        self.thread = None

        block_path = self.root.joinpath(*self.bundle.block_documents[0][0].split("/"))
        original = block_path.read_bytes()
        block_path.write_bytes(original[:-1] + (b" " if original[-1:] != b" " else b"\n"))
        with self.assertRaisesRegex(server_module.NationalBundleServerError, "validation|canonical"):
            self._build_service()
        block_path.write_bytes(original)

        extra = self.root / "extra.json"
        extra.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(server_module.NationalBundleServerError, "extra"):
            self._build_service()
        extra.unlink()

        mismatched = deepcopy(self.catalog)
        mismatched["catalog_sha256"] = "c" * 64
        with self.assertRaisesRegex(server_module.NationalBundleServerError, "differs"):
            self._build_service(catalog=mismatched)

    def test_non_loopback_server_factory_is_rejected_and_closed(self):
        self.service.server.shutdown()
        self.service.close()
        self.thread.join(timeout=5)
        self.service = None
        self.thread = None

        class FakeServer:
            server_address = ("0.0.0.0", 8782)

            def __init__(self):
                self.closed = False

            def server_close(self):
                self.closed = True

        fake = FakeServer()
        with self.assertRaisesRegex(server_module.NationalBundleServerError, "loopback"):
            server_module.build_service(
                server_module.ServerConfig(self.root, self.catalog_path, 8782),
                catalog_loader=lambda _path: self.catalog,
                server_factory=lambda _reader, *, port: fake,
            )
        self.assertTrue(fake.closed)

    def test_repository_catalog_accepts_its_single_terminal_lf(self):
        repository_root = Path(__file__).resolve().parents[2]
        catalog_path = (
            repository_root
            / "backend"
            / "app"
            / "data"
            / "italy_municipalities_2026.json"
        )
        payload = catalog_path.read_bytes()
        self.assertTrue(payload.endswith(b"\n"))
        self.assertFalse(payload.endswith(b"\n\n"))

        catalog = server_module._load_catalog(catalog_path)

        self.assertEqual(catalog["municipality_count"], 7_894)
        self.assertEqual(len(catalog["municipalities"]), 7_894)


if __name__ == "__main__":
    unittest.main()
