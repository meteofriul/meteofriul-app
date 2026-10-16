"""Offline tests for the real-GRIB national benchmark orchestration."""

from __future__ import annotations

from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark_national_icon_real as real
from local_pipeline.national_icon_bundle import (
    DEFAULT_TILE_SIZE_DEGREES,
    canonical_json_bytes,
    sha256_hex,
    validate_national_icon_bundle,
)
from local_pipeline.national_forecast_points import (
    METHOD_BY_QUALITY,
    QUALITY_OFFICIAL_ISTAT_CAPOLUOGO,
    build_approved_forecast_points_artifact,
    write_forecast_points_create_only,
)
from run_pilot import BASE, CONTRACTS


RUN = "2026092000"
RUN_TIME = datetime(2026, 9, 20, tzinfo=timezone.utc)
SECTION3 = b"\x00\x00\x00\x08\x03abc"


def _sample_catalog():
    municipalities = [
        {
            "istat_code": "001001",
            "representative_point": {
                "latitude": 45.20,
                "longitude": 12.20,
                "method": "istat_boundary_interior_point_v1",
            },
        },
        {
            "istat_code": "001002",
            "representative_point": {
                "latitude": 45.21,
                "longitude": 12.21,
                "method": "istat_boundary_interior_point_v1",
            },
        },
        {
            "istat_code": "001003",
            "representative_point": {
                "latitude": 45.70,
                "longitude": 12.70,
                "method": "istat_boundary_interior_point_v1",
            },
        },
    ]
    codes = [item["istat_code"] for item in municipalities]
    document = {
        "catalog_version": "fixture-v1",
        "effective_at": "2026-09-20",
        "municipality_count": len(municipalities),
        "municipality_codes_sha256": sha256_hex(canonical_json_bytes(codes)),
        "municipalities": municipalities,
        "sources": {
            "boundaries": {
                "dataset": "ISTAT generalized municipality boundaries",
                "reference_date": "2026-01-01",
                "sha256": "b" * 64,
                "url": "https://www.istat.it/example-boundaries.zip",
            }
        },
    }
    document["catalog_sha256"] = sha256_hex(canonical_json_bytes(document))
    return document


def _approved_points(catalog):
    raw = []
    for index, municipality in enumerate(catalog["municipalities"], start=1):
        proxy = municipality["representative_point"]
        code = municipality["istat_code"]
        raw.append(
            {
                "istat_code": code,
                "latitude": proxy["latitude"],
                "longitude": proxy["longitude"],
                "method": METHOD_BY_QUALITY[QUALITY_OFFICIAL_ISTAT_CAPOLUOGO],
                "quality": QUALITY_OFFICIAL_ISTAT_CAPOLUOGO,
                "source": {
                    "authority": "Istituto nazionale di statistica (Istat)",
                    "current_istat_code": code,
                    "dataset": "Località italiane ISTAT",
                    "dataset_sha256": "a" * 64,
                    "loc_id": str(1_000_000 + index),
                    "mapping_method": "direct_current_istat_code_v1",
                    "reference_date": "2021-12-31",
                    "source_crs": "EPSG:32632",
                    "source_istat_code": code,
                    "url": "https://www.istat.it/example-localities.zip",
                },
            }
        )
    return build_approved_forecast_points_artifact(
        catalog=catalog,
        points=raw,
        boundary_sha256="b" * 64,
        source_manifest_sha256="c" * 64,
        resolution_policy_sha256="d" * 64,
    )


def _message(field, step, section=SECTION3):
    body = json.dumps(
        {"field": field, "step": step}, separators=(",", ":")
    ).encode("ascii")
    size = 16 + len(section) + len(body) + 4
    return (
        b"GRIB"
        + b"\x00\x00\x00"
        + b"\x02"
        + size.to_bytes(8, "big")
        + section
        + body
        + b"7777"
    )


class FakeEcCodes:
    def __init__(self):
        self.mapping_calls = 0
        self.element_calls = 0
        self.releases = 0
        self.field_order = {field: index for index, field in enumerate(CONTRACTS)}

    def codes_new_from_message(self, message):
        payload = json.loads(message[24:-4].decode("ascii"))
        field = payload["field"]
        step = payload["step"]
        spec = CONTRACTS[field]
        valid = RUN_TIME + timedelta(hours=step)
        start = 0 if field in real.ACCUM_FIELDS else max(0, step - 1) if field == "VMAX_10M" else step
        values = []
        for index in range(4):
            if field == "WW":
                values.append(float((step + index) % 100))
            else:
                values.append(float(self.field_order[field] * 1_000 + step + index / 10))
        return {
            "message": message,
            "values": values,
            "shortName": spec["short_name"],
            "paramId": spec.get("param_id", self.field_order[field] + 1),
            "units": spec["units"] or "~",
            "typeOfLevel": spec["level_type"],
            "level": spec["level"],
            "dataDate": 20260920,
            "dataTime": 0,
            "validityDate": int(valid.strftime("%Y%m%d")),
            "validityTime": int(valid.strftime("%H%M")),
            "startStep": start,
            "endStep": step,
            "stepUnits": 1,
            "stepType": spec["step_type"],
            "gridType": "regular_ll",
            "numberOfPoints": 4,
            "Ni": 2,
            "Nj": 2,
            "uvRelativeToGrid": 0,
            "md5GridSection": "f" * 32,
            "packingType": "grid_simple",
            "bitsPerValue": 16,
            "referenceValue": 0.0,
            "binaryScaleFactor": 0,
            "decimalScaleFactor": 0,
            "latitudeOfFirstGridPointInDegrees": 45.25,
            "longitudeOfFirstGridPointInDegrees": 12.25,
            "latitudeOfLastGridPointInDegrees": 45.75,
            "longitudeOfLastGridPointInDegrees": 12.75,
            "iDirectionIncrementInDegrees": 0.5,
            "jDirectionIncrementInDegrees": 0.5,
            "iScansNegatively": 0,
            "jScansPositively": 1,
            "jPointsAreConsecutive": 0,
            "alternativeRowScanning": 0,
            "offsetSection3": 16,
            "section3Length": len(SECTION3),
            "missingValue": -9999.0,
        }

    def codes_set(self, handle, key, value):
        handle[key] = value

    def codes_get(self, handle, key):
        return handle[key]

    def codes_grib_find_nearest_multiple(self, handle, same_grid, latitudes, longitudes):
        self.mapping_calls += 1
        self.assert_false = same_grid
        indexes = [0, 0, 1]
        coordinates = [(45.25, 12.25), (45.25, 12.25), (45.75, 12.75)]
        return [
            {
                "index": index,
                "lat": coordinates[position][0],
                "lon": coordinates[position][1],
                "distance": 1.0 + position / 10,
                "value": handle["values"][index],
            }
            for position, index in enumerate(indexes[: len(latitudes)])
        ]

    def codes_get_elements(self, handle, key, indexes):
        self.element_calls += 1
        return [handle["values"][index] for index in indexes]

    def codes_release(self, handle):
        self.releases += 1


class FakeReader:
    def __init__(self):
        self.calls = []
        self.bytes_read = 0
        self.requests = 0
        self.network_seconds = 0.0

    def links(self, url):
        self.requests += 1
        if url == BASE:
            return [f"{RUN}/"]
        if url == f"{BASE}{RUN}/":
            return [f"{field}/" for field in CONTRACTS]
        for field, spec in CONTRACTS.items():
            if url == f"{BASE}{RUN}/{field}/":
                return [f"fixture_{spec['suffix']}.grib"]
        raise AssertionError(f"unexpected listing URL {url}")

    def chunks(self, url):
        self.requests += 1
        field = url.rstrip("/").split("/")[-2]
        data = b"".join(_message(field, step) for step in range(73))
        digest = hashlib.sha256(data).hexdigest()
        count = 0
        for offset in range(0, len(data), 97):
            chunk = data[offset : offset + 97]
            count += len(chunk)
            self.bytes_read += len(chunk)
            yield chunk
        self.calls.append(
            {
                "kind": "full_variable_stream",
                "bytes": count,
                "sha256": digest,
                "success": True,
            }
        )


def _memory():
    return {"working_set_bytes": 10, "peak_working_set_bytes": 20}


class ForecastPointGateTests(unittest.TestCase):
    def test_checked_in_proxy_points_require_explicit_opt_in(self):
        catalog = _sample_catalog()
        with self.assertRaisesRegex(real.NationalRealBenchmarkError, "opt-in"):
            real.load_forecast_points(
                catalog, None, allow_experimental_proxy=False
            )
        artifact = real.load_forecast_points(
            catalog, None, allow_experimental_proxy=True
        )
        self.assertEqual(artifact["status"], real.EXPERIMENTAL_POINTS_STATUS)
        self.assertEqual(artifact["point_count"], 3)
        self.assertEqual(
            artifact["points_sha256"],
            sha256_hex(canonical_json_bytes(artifact["points"])),
        )
        self.assertEqual(artifact["schema_version"], 2)
        self.assertIn("artifact_sha256", artifact)
        self.assertIn("resolution_policy_sha256", artifact)

    def test_approved_v2_artifact_loads_without_proxy_opt_in(self):
        catalog = _sample_catalog()
        artifact = _approved_points(catalog)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "approved-points.json"
            write_forecast_points_create_only(path, artifact, catalog=catalog)
            self.assertEqual(
                real.load_forecast_points(
                    catalog, path, allow_experimental_proxy=False
                ),
                artifact,
            )

    def test_benchmark_status_truth_table_covers_both_independent_gates(self):
        self.assertEqual(
            real._benchmark_status(
                real.EXPERIMENTAL_POINTS_STATUS,
                "experimental_benchmark_not_production",
            ),
            "experimental_proxy_and_product_profile_not_production",
        )
        self.assertEqual(
            real._benchmark_status(
                real.EXPERIMENTAL_POINTS_STATUS, "approved"
            ),
            "experimental_proxy_not_production",
        )
        self.assertEqual(
            real._benchmark_status(
                real.APPROVED_POINTS_STATUS,
                "experimental_benchmark_not_production",
            ),
            "experimental_product_profile_not_production",
        )
        self.assertEqual(
            real._benchmark_status(real.APPROVED_POINTS_STATUS, "approved"),
            "approved_inputs_benchmark_complete",
        )

    def test_cli_product_profile_and_proxy_permissions_are_separate(self):
        base = [
            "--bundle-dir",
            "bundle",
            "--mapping",
            "mapping.json",
            "--report",
            "report.json",
            "--confirm-full-download",
        ]
        with (
            redirect_stderr(StringIO()),
            self.assertRaises(SystemExit) as missing_profile_permission,
        ):
            real.main([*base, "--allow-experimental-proxy"])
        self.assertEqual(missing_profile_permission.exception.code, 2)

        with (
            patch.object(real, "preflight_output_paths"),
            patch.object(real, "load_national_catalog", return_value=_sample_catalog()),
        ):
            with self.assertRaisesRegex(
                real.NationalRealBenchmarkError, "proxy use needs explicit opt-in"
            ):
                real.main([*base, "--allow-experimental-product-profile"])

    def test_product_profile_is_explicitly_non_production(self):
        self.assertEqual(len(real.VARIABLE_PROFILE), 14)
        self.assertNotEqual(real.PRODUCT_PROFILE_STATUS, "approved")
        self.assertIn("not_production", real.PRODUCT_PROFILE_STATUS)

    def test_real_national_layout_is_fixed_without_changing_generic_default(self):
        self.assertEqual(str(DEFAULT_TILE_SIZE_DEGREES), "0.5")
        self.assertEqual(
            real.NATIONAL_BUNDLE_LAYOUT["tile_size_degrees"], "0.25"
        )
        self.assertEqual(
            real.NATIONAL_BUNDLE_LAYOUT["tile_size_microdegrees"], 250_000
        )
        self.assertEqual(
            real.NATIONAL_BUNDLE_LAYOUT_SHA256,
            sha256_hex(canonical_json_bytes(real.NATIONAL_BUNDLE_LAYOUT)),
        )


class NationalDecoderTests(unittest.TestCase):
    def test_section_three_change_fails_closed(self):
        points = real._proxy_forecast_points(_sample_catalog())["points"]
        ec = FakeEcCodes()
        decoder = real.NationalPointDecoder(points, ec)
        decoder.decode(_message("T_2M", 0), field="T_2M", run=RUN, step=0)
        changed = b"\x00\x00\x00\x08\x03abd"
        with self.assertRaisesRegex(real.NationalRealBenchmarkError, "grid changed"):
            decoder.decode(
                _message("TD_2M", 0, changed),
                field="TD_2M",
                run=RUN,
                step=0,
            )
        self.assertEqual(ec.mapping_calls, 1)
        self.assertEqual(ec.releases, 2)


class RealBenchmarkFixtureTests(unittest.TestCase):
    def setUp(self):
        self.catalog = _sample_catalog()
        self.points = real._proxy_forecast_points(self.catalog)
        self.reader = FakeReader()
        self.ec = FakeEcCodes()

    def test_mock_14_by_73_run_builds_mapping_and_valid_v2_bundle(self):
        bundle, mapping, report = real.run_real_benchmark(
            catalog=self.catalog,
            forecast_points=self.points,
            run=RUN,
            now=RUN_TIME + timedelta(hours=1),
            reader=self.reader,
            ec_module=self.ec,
            memory_reader=_memory,
        )
        validate_national_icon_bundle(bundle)
        self.assertEqual(
            report["status"],
            "experimental_proxy_and_product_profile_not_production",
        )
        self.assertEqual(report["source"]["field_count"], 14)
        self.assertEqual(report["source"]["message_count"], 14 * 73)
        self.assertEqual(report["mapping"]["municipality_count"], 3)
        self.assertEqual(report["mapping"]["unique_cell_count"], 2)
        self.assertEqual(report["mapping"]["shared_cell_count"], 1)
        self.assertEqual(self.ec.mapping_calls, 1)
        self.assertEqual(self.ec.element_calls, 14 * 73 - 1)
        self.assertEqual(self.ec.releases, 14 * 73)
        self.assertEqual(
            mapping["grid"]["sha256"], hashlib.sha256(SECTION3).hexdigest()
        )
        self.assertEqual(len(mapping["municipality_mappings"]), 3)
        expected_layout = {
            **real.NATIONAL_BUNDLE_LAYOUT,
            "sha256": real.NATIONAL_BUNDLE_LAYOUT_SHA256,
        }
        self.assertEqual(mapping["bundle_layout"], expected_layout)
        self.assertEqual(report["bundle_layout"], expected_layout)
        manifest = json.loads(bundle.manifest_json)
        index = json.loads(bundle.index_json)
        self.assertEqual(manifest["tile_size_microdegrees"], 250_000)
        self.assertEqual(index["tile_size_microdegrees"], 250_000)
        for _, payload in bundle.block_documents:
            self.assertEqual(
                json.loads(payload)["tile"]["size_microdegrees"], 250_000
            )
        descriptors = manifest["blocks"]
        self.assertEqual(report["bundle"]["layout"], expected_layout)
        self.assertEqual(report["bundle"]["tile_size_microdegrees"], 250_000)
        self.assertEqual(report["bundle"]["block_count"], len(descriptors))
        self.assertEqual(
            report["bundle"]["max_block_municipality_count"],
            max(item["municipality_count"] for item in descriptors),
        )
        self.assertEqual(
            report["bundle"]["max_block_cell_count"],
            max(item["cell_count"] for item in descriptors),
        )
        for artifact_view in (mapping["forecast_points"], report["forecast_points"]):
            self.assertEqual(
                artifact_view["artifact_sha256"], self.points["artifact_sha256"]
            )
            self.assertEqual(
                artifact_view["resolution_policy_sha256"],
                self.points["resolution_policy_sha256"],
            )
        for field in CONTRACTS:
            source = mapping["source_fields"][field]
            self.assertEqual(source["message_count"], 73)
            self.assertEqual(len(source["messages"]), 73)
            self.assertEqual(
                source["sha256"],
                hashlib.sha256(
                    b"".join(_message(field, step) for step in range(73))
                ).hexdigest(),
            )
        mapping_body = dict(mapping)
        mapping_sha = mapping_body.pop("mapping_sha256")
        self.assertEqual(
            mapping_sha, sha256_hex(canonical_json_bytes(mapping_body))
        )
        report_body = dict(report)
        report_sha = report_body.pop("report_sha256")
        self.assertEqual(report_sha, sha256_hex(canonical_json_bytes(report_body)))

    def test_outputs_are_create_only_and_manifest_is_written_last_in_contract_order(self):
        bundle, mapping, report = real.run_real_benchmark(
            catalog=self.catalog,
            forecast_points=self.points,
            run=RUN,
            now=RUN_TIME + timedelta(hours=1),
            reader=self.reader,
            ec_module=self.ec,
            memory_reader=_memory,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle_dir = root / "bundle"
            mapping_path = root / "mapping.json"
            report_path = root / "report.json"
            real.write_outputs_create_only(
                bundle=bundle,
                mapping=mapping,
                report=report,
                bundle_dir=bundle_dir,
                mapping_path=mapping_path,
                report_path=report_path,
            )
            self.assertEqual(
                mapping_path.read_bytes(), canonical_json_bytes(mapping)
            )
            self.assertEqual(report_path.read_bytes(), canonical_json_bytes(report))
            for relative, payload in bundle.publication_order():
                self.assertEqual((bundle_dir / relative).read_bytes(), payload)
            with self.assertRaises(FileExistsError):
                real.write_outputs_create_only(
                    bundle=bundle,
                    mapping=mapping,
                    report=report,
                    bundle_dir=bundle_dir,
                    mapping_path=mapping_path,
                    report_path=report_path,
                )


if __name__ == "__main__":
    unittest.main()
