"""Offline tests for the independent national ICON bundle v2 contract."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest

from local_pipeline.national_icon_bundle import (
    MAX_MUNICIPALITIES_PER_BLOCK,
    MAX_RAW_CELL_RECORDS,
    MAX_TIME_STEPS,
    NationalIconBundleError,
    build_national_icon_bundle,
    canonical_json_bytes,
    tile_id_for_coordinate,
    validate_national_icon_bundle,
)
from benchmark_national_icon_bundle import (
    GRID_APPROXIMATION_SHA256,
    analyze_catalog_layout,
    load_checked_in_catalog,
)


RUN_AT = "2026-09-20T00:00:00Z"
GENERATED_AT = "2026-09-20T00:07:00Z"
CATALOG_SHA = "a" * 64
GRID_SHA = "b" * 64
SAMPLE_CODES = ("001001", "001002", "001003", "001004")
SAMPLE_CODES_SHA = hashlib.sha256(
    canonical_json_bytes(list(SAMPLE_CODES))
).hexdigest()


def iso(hour: int) -> str:
    value = datetime(2026, 9, 20, tzinfo=timezone.utc) + timedelta(hours=hour)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def metadata():
    return {
        "model": {"id": "icon-2i", "product": "surface_pressure_levels"},
        "source": {
            "attribution": "Agenzia ItaliaMeteo",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
        },
        # Deliberately unsorted: the builder must produce stable canonical order.
        "variables": [
            {
                "id": "weather_code",
                "unit": "wmo_code",
                "data_type": "integer",
                "nullable": False,
            },
            {
                "id": "precipitation_mm",
                "unit": "mm",
                "data_type": "float",
                "nullable": True,
            },
            {
                "id": "temperature_c",
                "unit": "degC",
                "data_type": "float",
                "nullable": False,
            },
        ],
    }


def cell(grid_index, latitude, longitude, offset=0):
    return {
        "grid_index": grid_index,
        "latitude": latitude,
        "longitude": longitude,
        "values": {
            "temperature_c": [20 + offset, 21 + offset, 22 + offset],
            "weather_code": [0, 1, 2],
            "precipitation_mm": [None, 0, 0.5 + offset],
        },
    }


def build_sample(**changes):
    arguments = {
        "run_at": RUN_AT,
        "generated_at": GENERATED_AT,
        "catalog": {
            "version": "istat-2026-national-representative-points-v1",
            "sha256": CATALOG_SHA,
            "municipality_count": 4,
            "municipality_codes_sha256": SAMPLE_CODES_SHA,
        },
        "grid": {"sha256": GRID_SHA, "ni": 20, "nj": 20},
        "metadata": metadata(),
        "time_axis": [iso(0), iso(1), iso(2)],
        "municipality_cells": {
            "001001": 11,
            "001002": 11,
            "001003": 12,
            "001004": 80,
        },
        "cells": [
            cell(11, 45.0, 12.0),
            # An identical duplicate must collapse to one native ICON cell.
            deepcopy(cell(11, 45.0, 12.0)),
            cell(12, 45.24, 12.24, 1),
            cell(80, 45.5, 12.5, 2),
        ],
    }
    arguments.update(changes)
    return build_national_icon_bundle(**arguments)


def parse(payload):
    return json.loads(payload.decode("utf-8"))


class GeographicTileTests(unittest.TestCase):
    def test_default_half_degree_tiles_have_stable_boundary_semantics(self):
        self.assertEqual(
            "t0500000-y0270-x0384", tile_id_for_coordinate(45.0, 12.0)
        )
        self.assertEqual(
            "t0500000-y0270-x0384", tile_id_for_coordinate(45.499999, 12.499999)
        )
        self.assertEqual(
            "t0500000-y0271-x0385", tile_id_for_coordinate(45.5, 12.5)
        )

    def test_tile_size_is_configurable_but_must_partition_the_globe(self):
        self.assertEqual(
            "t1000000-y0135-x0192",
            tile_id_for_coordinate(45.5, 12.5, tile_size_degrees="1.0"),
        )
        for invalid in (0, -0.5, 0.7, 0.000001, 6):
            with self.subTest(invalid=invalid), self.assertRaises(NationalIconBundleError):
                tile_id_for_coordinate(45, 12, tile_size_degrees=invalid)

    def test_global_edges_are_explicit_and_fail_closed(self):
        self.assertEqual(
            "t0500000-y0000-x0000", tile_id_for_coordinate(-90, -180)
        )
        for latitude, longitude in ((90, 12), (-90.1, 12), (45, 180), (45, -180.1)):
            with self.subTest(latitude=latitude, longitude=longitude), self.assertRaises(
                NationalIconBundleError
            ):
                tile_id_for_coordinate(latitude, longitude)


class NationalBundleBenchmarkTests(unittest.TestCase):
    def test_checked_in_catalog_has_stable_approximate_layout_headlines(self):
        report = analyze_catalog_layout(load_checked_in_catalog())

        self.assertEqual(7894, report["municipality_count"])
        self.assertEqual(209, report["block_count"])
        self.assertEqual(7775, report["unique_cell_count"])
        self.assertEqual(
            {"min": 1, "median": 29, "p95": 114, "max": 261, "total": 7894},
            report["municipalities_per_block"],
        )
        self.assertEqual(
            {"min": 1, "median": 29, "p95": 113, "max": 236, "total": 7775},
            report["unique_cells_per_block"],
        )
        self.assertEqual(117, report["municipalities_per_cell"]["shared_cell_count"])
        self.assertRegex(GRID_APPROXIMATION_SHA256, r"^[0-9a-f]{64}$")


class NationalIconBundleTests(unittest.TestCase):
    def test_builds_complete_deduplicated_blocks_and_manifest_last(self):
        bundle = build_sample()
        validate_national_icon_bundle(bundle)

        manifest = parse(bundle.manifest_json)
        index = parse(bundle.index_json)
        blocks = [parse(payload) for _, payload in bundle.block_documents]

        self.assertEqual(4, manifest["municipality_count"])
        self.assertEqual(3, manifest["unique_cell_count"])
        self.assertEqual(2, manifest["block_count"])
        self.assertEqual(4, len(index["municipality_blocks"]))
        self.assertEqual(
            "t0500000-y0270-x0384", index["municipality_blocks"]["001001"]
        )
        self.assertEqual(
            "t0500000-y0271-x0385", index["municipality_blocks"]["001004"]
        )

        first = blocks[0]
        self.assertEqual(["g000011", "g000012"], [row["cell_id"] for row in first["cells"]])
        self.assertEqual("g000011", first["municipality_cells"]["001001"])
        self.assertEqual("g000011", first["municipality_cells"]["001002"])
        self.assertIn("metadata", first)
        self.assertIn("time_axis", first)
        self.assertTrue(all("metadata" not in row for row in first["cells"]))
        self.assertTrue(all("time_axis" not in row for row in first["cells"]))

        publication = bundle.publication_order()
        self.assertEqual(bundle.manifest_path, publication[-1][0])
        self.assertEqual(bundle.index_path, publication[-2][0])
        self.assertEqual(len(publication), len(bundle.block_documents) + 2)
        self.assertEqual(hashlib.sha256(bundle.manifest_json).hexdigest(), bundle.manifest_sha256)

    def test_one_degree_tile_configuration_merges_the_sample_blocks(self):
        bundle = build_sample(tile_size_degrees=1)
        manifest = parse(bundle.manifest_json)
        index = parse(bundle.index_json)
        self.assertEqual(1, manifest["block_count"])
        self.assertEqual({"t1000000-y0135-x0192"}, set(index["municipality_blocks"].values()))

    def test_all_hashes_and_bytes_are_independent_of_input_order(self):
        first = build_sample()
        reverse_assignments = dict(
            reversed(
                [
                    ("001001", 11),
                    ("001002", 11),
                    ("001003", 12),
                    ("001004", 80),
                ]
            )
        )
        reversed_metadata = metadata()
        reversed_metadata["variables"].reverse()
        second = build_sample(
            municipality_cells=reverse_assignments,
            cells=list(reversed([
                cell(11, 45.0, 12.0),
                cell(12, 45.24, 12.24, 1),
                cell(80, 45.5, 12.5, 2),
            ])),
            metadata=reversed_metadata,
        )
        self.assertEqual(first.manifest_json, second.manifest_json)
        self.assertEqual(first.index_json, second.index_json)
        self.assertEqual(first.block_documents, second.block_documents)

    def test_validator_rejects_partial_extra_or_tampered_object_sets(self):
        bundle = build_sample()
        with self.assertRaisesRegex(NationalIconBundleError, "missing or has extras"):
            validate_national_icon_bundle(
                replace(bundle, block_documents=bundle.block_documents[:-1])
            )

        with self.assertRaisesRegex(NationalIconBundleError, "missing or has extras"):
            validate_national_icon_bundle(
                replace(
                    bundle,
                    block_documents=bundle.block_documents
                    + (("runs/extra.json", canonical_json_bytes({"extra": True})),),
                )
            )

        path, payload = bundle.block_documents[0]
        changed = parse(payload)
        changed["cells"][0]["values"]["temperature_c"][0] = 999.0
        with self.assertRaisesRegex(NationalIconBundleError, "bytes differ from manifest"):
            validate_national_icon_bundle(
                replace(
                    bundle,
                    block_documents=((path, canonical_json_bytes(changed)),)
                    + bundle.block_documents[1:],
                )
            )

    def test_validator_rejects_noncanonical_json_even_if_semantically_equal(self):
        bundle = build_sample()
        noncanonical = json.dumps(parse(bundle.index_json), indent=2).encode("utf-8")
        manifest = parse(bundle.manifest_json)
        # Update the descriptor and commit digest so canonicality, not a stale
        # hash, is what closes the validation path.
        manifest["index"]["json_bytes"] = len(noncanonical)
        manifest["index"]["sha256"] = hashlib.sha256(noncanonical).hexdigest()
        base = dict(manifest)
        base.pop("bundle_sha256")
        manifest["bundle_sha256"] = hashlib.sha256(canonical_json_bytes(base)).hexdigest()
        broken = replace(
            bundle,
            index_json=noncanonical,
            manifest_json=canonical_json_bytes(manifest),
        )
        with self.assertRaisesRegex(NationalIconBundleError, "not canonical JSON"):
            validate_national_icon_bundle(broken)

    def test_builder_rejects_incomplete_catalog_or_cell_sets(self):
        with self.assertRaisesRegex(NationalIconBundleError, "exactly cover"):
            build_sample(
                municipality_cells={"001001": 11, "001002": 11, "001003": 12}
            )
        with self.assertRaisesRegex(NationalIconBundleError, "exactly match"):
            build_sample(cells=[cell(11, 45.0, 12.0), cell(12, 45.24, 12.24, 1)])

    def test_catalog_code_digest_rejects_same_count_with_invented_identity(self):
        with self.assertRaisesRegex(NationalIconBundleError, "canonical catalog"):
            build_sample(
                municipality_cells={
                    "001001": 11,
                    "001002": 11,
                    "001003": 12,
                    "999999": 80,
                }
            )

    def test_conflicting_duplicate_native_cell_is_rejected(self):
        conflicting = cell(11, 45.0, 12.0)
        conflicting["values"]["temperature_c"][0] = 99
        with self.assertRaisesRegex(NationalIconBundleError, "conflicting duplicate"):
            build_sample(
                cells=[
                    cell(11, 45.0, 12.0),
                    conflicting,
                    cell(12, 45.24, 12.24, 1),
                    cell(80, 45.5, 12.5, 2),
                ]
            )

    def test_raw_duplicate_cell_input_is_bounded_before_normalization(self):
        repeated = cell(11, 45.0, 12.0)
        with self.assertRaisesRegex(NationalIconBundleError, "raw records"):
            build_sample(cells=[repeated] * (MAX_RAW_CELL_RECORDS + 1))

    def test_nonfinite_and_wrong_integer_series_values_are_rejected(self):
        bad_float = cell(11, 45.0, 12.0)
        bad_float["values"]["temperature_c"][1] = float("nan")
        with self.assertRaisesRegex(NationalIconBundleError, "finite number"):
            build_sample(
                cells=[bad_float, cell(12, 45.24, 12.24, 1), cell(80, 45.5, 12.5, 2)]
            )

        bad_integer = cell(11, 45.0, 12.0)
        bad_integer["values"]["weather_code"][1] = 1.5
        with self.assertRaisesRegex(NationalIconBundleError, "integer"):
            build_sample(
                cells=[bad_integer, cell(12, 45.24, 12.24, 1), cell(80, 45.5, 12.5, 2)]
            )

    def test_hard_time_and_per_block_municipality_limits_are_enforced(self):
        too_many_times = [iso(hour) for hour in range(MAX_TIME_STEPS + 1)]
        with self.assertRaisesRegex(NationalIconBundleError, "time_axis"):
            build_sample(time_axis=too_many_times)

        count = MAX_MUNICIPALITIES_PER_BLOCK + 1
        assignments = {f"{index:06d}": 11 for index in range(1, count + 1)}
        assignment_codes_sha = hashlib.sha256(
            canonical_json_bytes(sorted(assignments))
        ).hexdigest()
        with self.assertRaisesRegex(NationalIconBundleError, "municipality limit"):
            build_sample(
                catalog={
                    "version": "istat-2026-national-representative-points-v1",
                    "sha256": CATALOG_SHA,
                    "municipality_count": count,
                    "municipality_codes_sha256": assignment_codes_sha,
                },
                municipality_cells=assignments,
                cells=[cell(11, 45.0, 12.0)],
            )

    def test_cell_ordering_remains_numeric_above_six_digit_grid_indexes(self):
        codes = ("001001", "001002")
        catalog = {
            "version": "istat-2026-national-representative-points-v1",
            "sha256": CATALOG_SHA,
            "municipality_count": len(codes),
            "municipality_codes_sha256": hashlib.sha256(
                canonical_json_bytes(list(codes))
            ).hexdigest(),
        }

        bundle = build_sample(
            catalog=catalog,
            grid={"sha256": GRID_SHA, "ni": 1001, "nj": 1000},
            municipality_cells={"001001": 999_999, "001002": 1_000_000},
            cells=[
                cell(999_999, 45.0, 12.0),
                cell(1_000_000, 45.1, 12.1, 1),
            ],
        )

        validate_national_icon_bundle(bundle)
        block = parse(bundle.block_documents[0][1])
        self.assertEqual(
            ["g999999", "g1000000"],
            [item["cell_id"] for item in block["cells"]],
        )

    def test_manifest_digest_covers_every_descriptor_and_count(self):
        bundle = build_sample()
        manifest = parse(bundle.manifest_json)
        manifest["unique_cell_count"] += 1
        # Leaving bundle_sha256 untouched must fail before relational checks.
        with self.assertRaisesRegex(NationalIconBundleError, "bundle_sha256"):
            validate_national_icon_bundle(
                replace(bundle, manifest_json=canonical_json_bytes(manifest))
            )


if __name__ == "__main__":
    unittest.main()
