"""Deterministic offline structural sizing for the national ICON v2 bundle.

This is deliberately *not* a meteorological or ecCodes benchmark.  It reads
the reviewed, checked-in ISTAT catalog and approximates the documented native
ICON-2I regular grid by rounding representative points to 0.02 degrees in
latitude and 0.025 degrees in longitude, with an explicitly assumed 35N/5E
alignment.  A production run must replace that approximation with
``codes_grib_find_nearest_multiple`` against the verified GRIB grid hash.

For reproducible structural sizing, the script creates one block at a time
with 73 forecast instants and fourteen deterministic, smoothly varying or
sparse numeric series.  Documents use the v2 canonical compact JSON shape and
are measured both raw and as independent gzip level-6 responses.  No file is
written and there is no network, cloud, scheduler, or application access.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import gzip
import json
import math
from pathlib import Path
import statistics
from typing import Any, Mapping, Sequence

try:  # Direct script execution from experiments/weather_autonomy.
    from local_pipeline.national_icon_bundle import (
        BLOCK_KIND,
        CONTRACT_ID,
        INDEX_KIND,
        MANIFEST_KIND,
        MAX_BLOCK_JSON_BYTES,
        NationalIconBundle,
        canonical_json_bytes,
        sha256_hex,
        tile_id_for_coordinate,
        validate_national_icon_bundle,
    )
    from national_catalog import validate_catalog
except ModuleNotFoundError:  # Package import from the repository root.
    from .local_pipeline.national_icon_bundle import (
        BLOCK_KIND,
        CONTRACT_ID,
        INDEX_KIND,
        MANIFEST_KIND,
        MAX_BLOCK_JSON_BYTES,
        NationalIconBundle,
        canonical_json_bytes,
        sha256_hex,
        tile_id_for_coordinate,
        validate_national_icon_bundle,
    )
    from .national_catalog import validate_catalog


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = ROOT / "backend" / "app" / "data" / "italy_municipalities_2026.json"

RUN_AT = "2026-09-20T00:00:00Z"
GENERATED_AT = "2026-09-20T00:07:00Z"
SOURCE_RUN_ID = "20260920T000000Z"
FORECAST_HOURS = 73
TILE_SIZE_DEGREES = 0.5

# Structural approximation only.  The increments were observed in the pilot;
# the origins are declared assumptions, not reconstructed provider metadata.
GRID_NI = 761
GRID_NJ = 761
LATITUDE_ORIGIN = 35.0
LONGITUDE_ORIGIN = 5.0
LATITUDE_INCREMENT = 0.02
LONGITUDE_INCREMENT = 0.025

VARIABLE_SPECS = (
    ("t_2m_k", "K", "float"),
    ("td_2m_k", "K", "float"),
    ("u_10m_m_s", "m/s", "float"),
    ("v_10m_m_s", "m/s", "float"),
    ("cloud_cover_pct", "percent", "float"),
    ("pressure_msl_pa", "Pa", "float"),
    ("total_precipitation_mm", "mm", "float"),
    ("weather_code", "wmo_code", "integer"),
    ("wind_gust_max_m_s", "m/s", "float"),
    ("convective_rain_mm", "mm", "float"),
    ("grid_scale_rain_mm", "mm", "float"),
    ("convective_snow_mm", "mm", "float"),
    ("grid_scale_snow_mm", "mm", "float"),
    ("grid_scale_graupel_mm", "mm", "float"),
)

GRID_APPROXIMATION = {
    "status": "assumed_regular_grid_for_structural_sizing_only",
    "ni": GRID_NI,
    "nj": GRID_NJ,
    "latitude_origin": LATITUDE_ORIGIN,
    "longitude_origin": LONGITUDE_ORIGIN,
    "latitude_increment": LATITUDE_INCREMENT,
    "longitude_increment": LONGITUDE_INCREMENT,
    "nearest_rule": "floor(relative_position + 0.5)",
    "production_requirement": "replace with ecCodes nearest-cell mapping and verified GRIB grid hash",
}
GRID_APPROXIMATION_SHA256 = sha256_hex(canonical_json_bytes(GRID_APPROXIMATION))


def load_checked_in_catalog(path: str | Path = DEFAULT_CATALOG_PATH) -> dict[str, Any]:
    """Load and fully validate the reviewed catalog without external I/O."""

    source = Path(path)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"national catalog is unreadable: {source}") from error
    validate_catalog(document)
    return document


def _approximate_cell(latitude: float, longitude: float) -> dict[str, Any]:
    row = math.floor((latitude - LATITUDE_ORIGIN) / LATITUDE_INCREMENT + 0.5)
    column = math.floor(
        (longitude - LONGITUDE_ORIGIN) / LONGITUDE_INCREMENT + 0.5
    )
    if not 0 <= row < GRID_NJ or not 0 <= column < GRID_NI:
        raise ValueError("catalog point lies outside the declared approximate grid")
    cell_latitude = round(LATITUDE_ORIGIN + row * LATITUDE_INCREMENT, 6)
    cell_longitude = round(LONGITUDE_ORIGIN + column * LONGITUDE_INCREMENT, 6)
    grid_index = row * GRID_NI + column
    return {
        "cell_id": f"g{grid_index:06d}",
        "grid_index": grid_index,
        "latitude": cell_latitude,
        "longitude": cell_longitude,
        "block_id": tile_id_for_coordinate(
            cell_latitude,
            cell_longitude,
            tile_size_degrees=TILE_SIZE_DEGREES,
        ),
    }


def _nearest_rank(values: Sequence[int], probability: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * probability) - 1)]


def _distribution(values: Sequence[int]) -> dict[str, int | float]:
    if not values:
        raise ValueError("cannot summarize an empty distribution")
    return {
        "min": min(values),
        "median": statistics.median(values),
        "p95": _nearest_rank(values, 0.95),
        "max": max(values),
        "total": sum(values),
    }


def analyze_catalog_layout(catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Return fast headline counts without materializing synthetic time series."""

    municipalities = catalog.get("municipalities")
    if not isinstance(municipalities, list) or not municipalities:
        raise ValueError("catalog municipalities are missing")
    blocks: Counter[str] = Counter()
    block_cells: dict[str, set[int]] = defaultdict(set)
    cell_uses: Counter[int] = Counter()
    seen_istat: set[str] = set()
    for municipality in municipalities:
        if not isinstance(municipality, Mapping):
            raise ValueError("catalog municipality is invalid")
        istat_code = municipality.get("istat_code")
        point = municipality.get("representative_point")
        if not isinstance(istat_code, str) or istat_code in seen_istat:
            raise ValueError("catalog ISTAT identities are invalid")
        if not isinstance(point, Mapping):
            raise ValueError(f"municipality {istat_code} has no representative point")
        cell = _approximate_cell(point["latitude"], point["longitude"])
        seen_istat.add(istat_code)
        blocks[cell["block_id"]] += 1
        block_cells[cell["block_id"]].add(cell["grid_index"])
        cell_uses[cell["grid_index"]] += 1
    municipality_counts = list(blocks.values())
    cell_counts = [len(block_cells[block_id]) for block_id in blocks]
    use_counts = list(cell_uses.values())
    return {
        "municipality_count": len(municipalities),
        "block_count": len(blocks),
        "unique_cell_count": len(cell_uses),
        "municipalities_per_block": _distribution(municipality_counts),
        "unique_cells_per_block": _distribution(cell_counts),
        "municipalities_per_cell": {
            **_distribution(use_counts),
            "shared_cell_count": sum(value > 1 for value in use_counts),
        },
    }


def _forecast_times() -> list[str]:
    start = datetime(2026, 9, 20, tzinfo=timezone.utc)
    return [
        (start + timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for hour in range(FORECAST_HOURS)
    ]


def _rounded(value: float, digits: int = 3) -> float:
    result = float(round(value, digits))
    return 0.0 if result == 0 else result


def _synthetic_values(cell: Mapping[str, Any]) -> dict[str, list[int | float]]:
    """Generate stable structural data; values make no forecast claim."""

    grid_index = cell["grid_index"]
    latitude = cell["latitude"]
    result: dict[str, list[int | float]] = {}
    for variable_id, _, data_type in VARIABLE_SPECS:
        series: list[int | float] = []
        for hour in range(FORECAST_HOURS):
            wave = math.sin((hour % 24) * math.pi / 12)
            seed = (grid_index % 97) / 97
            if variable_id == "t_2m_k":
                value = _rounded(278.15 + (latitude - 35) * 0.55 + wave * 4 + seed)
            elif variable_id == "td_2m_k":
                value = _rounded(274.15 + (latitude - 35) * 0.48 + wave * 2 + seed * 0.5)
            elif variable_id == "u_10m_m_s":
                value = _rounded(math.sin((hour + grid_index % 11) / 5) * 6)
            elif variable_id == "v_10m_m_s":
                value = _rounded(math.cos((hour + grid_index % 13) / 6) * 5)
            elif variable_id == "cloud_cover_pct":
                value = _rounded((grid_index * 7 + hour * 11) % 101, 1)
            elif variable_id == "pressure_msl_pa":
                value = _rounded(
                    100_400 + (grid_index % 31) * 17 + math.cos(hour / 8) * 650,
                    1,
                )
            elif variable_id == "total_precipitation_mm":
                value = _rounded(math.floor(hour / 6) * ((grid_index % 9) + 1) * 0.07)
            elif variable_id == "weather_code":
                value = (0, 1, 2, 3, 61, 80, 95)[(grid_index + hour * 3) % 7]
            elif variable_id == "wind_gust_max_m_s":
                value = _rounded(
                    2 + abs(math.sin((hour + grid_index % 17) / 4)) * 12
                )
            elif variable_id == "convective_rain_mm":
                value = _rounded(((grid_index % 7) + 1) * 0.08 if hour % 9 == 0 else 0)
            elif variable_id == "grid_scale_rain_mm":
                value = _rounded(((grid_index % 11) + 1) * 0.06 if hour % 7 == 0 else 0)
            elif variable_id == "convective_snow_mm":
                value = _rounded(
                    (grid_index % 3) * 0.03
                    if latitude > 44 and hour % 17 == 0
                    else 0
                )
            elif variable_id == "grid_scale_snow_mm":
                value = _rounded(
                    (grid_index % 5) * 0.04
                    if latitude > 45 and hour % 13 == 0
                    else 0
                )
            else:
                value = _rounded((grid_index % 2) * 0.02 if hour % 19 == 0 else 0)
            if data_type == "integer" and not isinstance(value, int):
                raise AssertionError("integer synthetic variable produced a float")
            series.append(value)
        result[variable_id] = series
    return result


def _tile_bounds(block_id: str) -> dict[str, int]:
    size = int(block_id[1:8])
    y = int(block_id[10:14])
    x = int(block_id[16:20])
    south = -90_000_000 + y * size
    west = -180_000_000 + x * size
    return {
        "south": south,
        "west": west,
        "north": south + size,
        "east": west + size,
    }


def benchmark_national_bundle(catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Measure deterministic v2-shaped blocks while bounding working memory."""

    headline = analyze_catalog_layout(catalog)
    cells: dict[int, dict[str, Any]] = {}
    municipality_cells_by_block: dict[str, dict[str, str]] = defaultdict(dict)
    cells_by_block: dict[str, set[int]] = defaultdict(set)
    municipality_blocks: dict[str, str] = {}
    for municipality in catalog["municipalities"]:
        point = municipality["representative_point"]
        cell = _approximate_cell(point["latitude"], point["longitude"])
        cells.setdefault(cell["grid_index"], cell)
        block_id = cell["block_id"]
        istat_code = municipality["istat_code"]
        municipality_blocks[istat_code] = block_id
        municipality_cells_by_block[block_id][istat_code] = cell["cell_id"]
        cells_by_block[block_id].add(cell["grid_index"])

    catalog_reference = {
        "version": catalog["catalog_version"],
        "sha256": catalog["catalog_sha256"],
        "municipality_count": catalog["municipality_count"],
        "municipality_codes_sha256": catalog["municipality_codes_sha256"],
    }
    grid_reference = {
        "sha256": GRID_APPROXIMATION_SHA256,
        "ni": GRID_NI,
        "nj": GRID_NJ,
    }
    variables = sorted(
        (
            {
                "id": variable_id,
                "unit": unit,
                "data_type": data_type,
                "nullable": False,
            }
            for variable_id, unit, data_type in VARIABLE_SPECS
        ),
        key=lambda item: item["id"],
    )
    metadata = {
        "provider": "icon2i",
        "model": {"id": "icon-2i", "product": "surface_pressure_levels"},
        "source": {
            "attribution": "Agenzia ItaliaMeteo",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
        },
        "catalog": catalog_reference,
        "grid": grid_reference,
        "run_at": RUN_AT,
        "generated_at": GENERATED_AT,
        "variables": variables,
    }
    time_axis = _forecast_times()
    block_metrics: list[dict[str, Any]] = []
    descriptors: list[dict[str, Any]] = []
    block_documents: list[tuple[str, bytes]] = []
    for block_id in sorted(cells_by_block):
        materialized_cells = []
        for grid_index in sorted(cells_by_block[block_id]):
            cell = cells[grid_index]
            materialized_cells.append(
                {
                    "cell_id": cell["cell_id"],
                    "grid_index": grid_index,
                    "latitude": cell["latitude"],
                    "longitude": cell["longitude"],
                    "values": _synthetic_values(cell),
                }
            )
        municipality_mapping = dict(
            sorted(municipality_cells_by_block[block_id].items())
        )
        block = {
            "kind": BLOCK_KIND,
            "schema_version": 2,
            "contract": CONTRACT_ID,
            "source_run_id": SOURCE_RUN_ID,
            "block_id": block_id,
            "tile": {
                "size_microdegrees": 500_000,
                "bounds_microdegrees": _tile_bounds(block_id),
            },
            "metadata": metadata,
            "time_axis": time_axis,
            "municipality_cells": municipality_mapping,
            "cells": materialized_cells,
        }
        encoded = canonical_json_bytes(block)
        if len(encoded) > MAX_BLOCK_JSON_BYTES:
            raise ValueError(
                f"synthetic block {block_id} exceeds v2 limit: {len(encoded)} bytes"
            )
        compressed = gzip.compress(encoded, compresslevel=6, mtime=0)
        block_metrics.append(
            {
                "block_id": block_id,
                "municipalities": len(municipality_mapping),
                "unique_cells": len(materialized_cells),
                "json_bytes": len(encoded),
                "gzip_bytes": len(compressed),
            }
        )
        descriptors.append(
            {
                "block_id": block_id,
                "path": f"runs/{SOURCE_RUN_ID}/blocks/{block_id}.json",
                "json_bytes": len(encoded),
                "sha256": sha256_hex(encoded),
                "municipality_count": len(municipality_mapping),
                "cell_count": len(materialized_cells),
            }
        )
        block_documents.append(
            (f"runs/{SOURCE_RUN_ID}/blocks/{block_id}.json", encoded)
        )

    index = {
        "kind": INDEX_KIND,
        "schema_version": 2,
        "contract": CONTRACT_ID,
        "source_run_id": SOURCE_RUN_ID,
        "catalog": catalog_reference,
        "grid_sha256": GRID_APPROXIMATION_SHA256,
        "tile_size_microdegrees": 500_000,
        "municipality_blocks": dict(sorted(municipality_blocks.items())),
    }
    index_json = canonical_json_bytes(index)
    index_gzip = gzip.compress(index_json, compresslevel=6, mtime=0)
    manifest_base = {
        "kind": MANIFEST_KIND,
        "schema_version": 2,
        "contract": CONTRACT_ID,
        "source_run_id": SOURCE_RUN_ID,
        "run_at": RUN_AT,
        "generated_at": GENERATED_AT,
        "catalog": catalog_reference,
        "grid": grid_reference,
        "tile_size_microdegrees": 500_000,
        "metadata_sha256": sha256_hex(canonical_json_bytes(metadata)),
        "time_axis_sha256": sha256_hex(canonical_json_bytes(time_axis)),
        "time_step_count": FORECAST_HOURS,
        "variable_count": len(VARIABLE_SPECS),
        "municipality_count": headline["municipality_count"],
        "unique_cell_count": headline["unique_cell_count"],
        "block_count": headline["block_count"],
        "index": {
            "path": f"runs/{SOURCE_RUN_ID}/municipality-index.json",
            "json_bytes": len(index_json),
            "sha256": sha256_hex(index_json),
        },
        "blocks": descriptors,
    }
    manifest = {
        **manifest_base,
        "bundle_sha256": sha256_hex(canonical_json_bytes(manifest_base)),
    }
    manifest_json = canonical_json_bytes(manifest)
    manifest_gzip = gzip.compress(manifest_json, compresslevel=6, mtime=0)
    validate_national_icon_bundle(
        NationalIconBundle(
            manifest_path=f"runs/{SOURCE_RUN_ID}/manifest.json",
            manifest_json=manifest_json,
            index_path=f"runs/{SOURCE_RUN_ID}/municipality-index.json",
            index_json=index_json,
            block_documents=tuple(block_documents),
        )
    )

    block_json_sizes = [item["json_bytes"] for item in block_metrics]
    block_gzip_sizes = [item["gzip_bytes"] for item in block_metrics]
    largest = max(block_metrics, key=lambda item: item["json_bytes"])
    return {
        "status": "deterministic_structural_approximation_not_grib_measurement",
        "assumptions": {
            "catalog_path": str(DEFAULT_CATALOG_PATH.relative_to(ROOT)).replace("\\", "/"),
            "catalog_sha256": catalog["catalog_sha256"],
            "tile_degrees": TILE_SIZE_DEGREES,
            "cell_mapping": GRID_APPROXIMATION,
            "cell_mapping_sha256": GRID_APPROXIMATION_SHA256,
            "forecast_hours": FORECAST_HOURS,
            "variables": len(VARIABLE_SPECS),
            "payload_values": "deterministic synthetic smooth and sparse numeric series",
            "representative_points": (
                "interior points derived from generalized ISTAT boundaries; not "
                "municipal seats and not approved production forecast points"
            ),
            "json": "UTF-8 canonical compact JSON with sorted keys",
            "compression": "each document independently gzip level 6 with mtime 0",
            "production_caveat": (
                "cell counts, payload entropy and sizes must be remeasured from a "
                "verified ICON GRIB run through ecCodes; this benchmark proves neither "
                "forecast quality nor Cloud Run cost"
            ),
            "contract_validation": "all generated v2 documents validated in memory",
        },
        "layout": headline,
        "block_json_bytes": _distribution(block_json_sizes),
        "block_gzip_bytes": _distribution(block_gzip_sizes),
        "index": {"json_bytes": len(index_json), "gzip_bytes": len(index_gzip)},
        "manifest": {
            "json_bytes": len(manifest_json),
            "gzip_bytes": len(manifest_gzip),
        },
        "complete_bundle": {
            "json_bytes": sum(block_json_sizes) + len(index_json) + len(manifest_json),
            "gzip_bytes": sum(block_gzip_sizes) + len(index_gzip) + len(manifest_gzip),
        },
        "largest_block": largest,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
        help="reviewed checked-in national catalog",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="emit compact canonical JSON instead of indented JSON",
    )
    arguments = parser.parse_args(argv)
    report = benchmark_national_bundle(load_checked_in_catalog(arguments.catalog))
    if arguments.compact:
        print(canonical_json_bytes(report).decode("utf-8"))
    else:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
