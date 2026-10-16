"""Offline, fail-closed ICON-2I national bundle contract, version 2.

The v1 FVG contract deliberately remains untouched.  This module defines an
independent publication artifact for a future national data plane:

* municipalities are assigned to the geographic tile containing their ICON
  cell (rather than their administrative representative point);
* a cell is materialized once and can serve several municipalities;
* block metadata and the forecast time axis occur once per block, never once
  per municipality or cell;
* every byte-bearing document is canonical JSON and is covered by a SHA-256
  descriptor in the manifest;
* the manifest is the last document in ``publication_order`` and validation
  rejects missing, extra, non-canonical, oversized, or inconsistent objects.

The module performs no file, network, provider, or cloud I/O.  Builders accept
plain Python data and return immutable byte documents ready for an external
publisher to upload with create-only semantics before committing the manifest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = 2
CONTRACT_ID = "weather/v2/icon2i"
PROVIDER = "icon2i"

BLOCK_KIND = "meteofriul.weather.icon.national.block"
INDEX_KIND = "meteofriul.weather.icon.national.index"
MANIFEST_KIND = "meteofriul.weather.icon.national.manifest"

DEFAULT_TILE_SIZE_DEGREES = Decimal("0.5")
MICRODEGREES_PER_DEGREE = 1_000_000

# These are contract limits, not tuning suggestions.  Increasing one is a
# schema/release decision and must be accompanied by a national benchmark.
MAX_MUNICIPALITIES = 10_000
MAX_BLOCKS = 2_048
MAX_MUNICIPALITIES_PER_BLOCK = 512
MAX_CELLS_PER_BLOCK = 512
MAX_TIME_STEPS = 193
MAX_VARIABLES = 32
MAX_GRID_POINTS = 10_000_000
MAX_RAW_CELL_RECORDS = 20_000
MAX_BLOCK_JSON_BYTES = 2 * 1024 * 1024
MAX_INDEX_JSON_BYTES = 2 * 1024 * 1024
MAX_MANIFEST_JSON_BYTES = 512 * 1024
MAX_BUNDLE_JSON_BYTES = 256 * 1024 * 1024

_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z$")
_ISTAT_RE = re.compile(r"^\d{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VARIABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_CELL_ID_RE = re.compile(r"^g\d{6,8}$")
_BLOCK_ID_RE = re.compile(r"^t\d{7}-y\d{4}-x\d{4}$")


class NationalIconBundleError(ValueError):
    """The input or artifact violates the national ICON v2 contract."""


@dataclass(frozen=True)
class NationalIconBundle:
    """Immutable, complete set of canonical publication documents.

    ``publication_order`` intentionally places the manifest last.  A storage
    adapter must upload all earlier immutable objects successfully before it
    exposes the manifest (and, in a later layer, advances a latest pointer).
    """

    manifest_path: str
    manifest_json: bytes
    index_path: str
    index_json: bytes
    block_documents: tuple[tuple[str, bytes], ...]

    @property
    def manifest_sha256(self) -> str:
        return sha256_hex(self.manifest_json)

    def publication_order(self) -> tuple[tuple[str, bytes], ...]:
        return self.block_documents + (
            (self.index_path, self.index_json),
            (self.manifest_path, self.manifest_json),
        )

    def documents(self) -> dict[str, bytes]:
        """Return a new path-to-bytes map; duplicate paths are impossible."""

        result: dict[str, bytes] = {}
        for path, payload in self.publication_order():
            if path in result:
                raise NationalIconBundleError(f"duplicate bundle path: {path}")
            result[path] = payload
        return result


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize the sole JSON representation accepted and hashed by v2."""

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise NationalIconBundleError("document is not canonical JSON data") from error


def sha256_hex(value: bytes) -> str:
    if not isinstance(value, bytes):
        raise NationalIconBundleError("SHA-256 input must be bytes")
    return hashlib.sha256(value).hexdigest()


def canonical_run_id(run_at: str) -> str:
    return _parse_utc(run_at, "run_at", on_hour=True).strftime("%Y%m%dT%H%M%SZ")


def _exact_keys(
    value: Any,
    expected: set[str] | frozenset[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise NationalIconBundleError(f"{label} has missing or extra fields")
    return value


def _trimmed_string(value: Any, label: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise NationalIconBundleError(f"{label} must be a trimmed non-empty string")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise NationalIconBundleError(
            f"{label} must be 64 lowercase hexadecimal characters"
        )
    return value


def _integer(
    value: Any,
    label: str,
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise NationalIconBundleError(f"{label} must be an integer >= {minimum}")
    if maximum is not None and value > maximum:
        raise NationalIconBundleError(f"{label} exceeds {maximum}")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NationalIconBundleError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise NationalIconBundleError(f"{label} must be a finite number")
    return 0.0 if result == 0 else result


def _parse_utc(value: Any, label: str, *, on_hour: bool = False) -> datetime:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        raise NationalIconBundleError(f"{label} must use canonical UTC seconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as error:
        raise NationalIconBundleError(f"{label} is not a valid UTC timestamp") from error
    if on_hour and (parsed.minute or parsed.second):
        raise NationalIconBundleError(f"{label} must fall on an exact UTC hour")
    return parsed


def _tile_size_microdegrees(value: Decimal | float | int | str) -> int:
    try:
        size = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise NationalIconBundleError("tile size must be a decimal number") from error
    if not size.is_finite() or size <= 0:
        raise NationalIconBundleError("tile size must be positive and finite")
    scaled = size * MICRODEGREES_PER_DEGREE
    if scaled != scaled.to_integral_value():
        raise NationalIconBundleError("tile size supports at most six decimal places")
    microdegrees = int(scaled)
    if not 50_000 <= microdegrees <= 5_000_000:
        raise NationalIconBundleError("tile size must be between 0.05 and 5 degrees")
    if 180 * MICRODEGREES_PER_DEGREE % microdegrees:
        raise NationalIconBundleError("tile size must divide 180 degrees exactly")
    return microdegrees


def tile_id_for_coordinate(
    latitude: float,
    longitude: float,
    *,
    tile_size_degrees: Decimal | float | int | str = DEFAULT_TILE_SIZE_DEGREES,
) -> str:
    """Return a stable global-grid tile ID for a cell coordinate.

    South and west boundaries are inclusive; north and east boundaries are
    exclusive.  Decimal arithmetic avoids binary-float drift at tile edges.
    """

    lat = _number(latitude, "latitude")
    lon = _number(longitude, "longitude")
    if not -90 <= lat < 90:
        raise NationalIconBundleError("latitude must be in [-90, 90)")
    if not -180 <= lon < 180:
        raise NationalIconBundleError("longitude must be in [-180, 180)")
    size_microdegrees = _tile_size_microdegrees(tile_size_degrees)
    size = Decimal(size_microdegrees) / MICRODEGREES_PER_DEGREE
    y = int(
        ((Decimal(str(lat)) + Decimal(90)) / size).to_integral_value(
            rounding=ROUND_FLOOR
        )
    )
    x = int(
        ((Decimal(str(lon)) + Decimal(180)) / size).to_integral_value(
            rounding=ROUND_FLOOR
        )
    )
    return f"t{size_microdegrees:07d}-y{y:04d}-x{x:04d}"


def _tile_bounds_microdegrees(block_id: str) -> dict[str, int]:
    if not isinstance(block_id, str) or not _BLOCK_ID_RE.fullmatch(block_id):
        raise NationalIconBundleError("block_id is not canonical")
    size = int(block_id[1:8])
    y = int(block_id[10:14])
    x = int(block_id[16:20])
    if size != _tile_size_microdegrees(Decimal(size) / MICRODEGREES_PER_DEGREE):
        raise NationalIconBundleError("block_id tile size is invalid")
    max_y = 180 * MICRODEGREES_PER_DEGREE // size
    max_x = 360 * MICRODEGREES_PER_DEGREE // size
    if not 0 <= y < max_y or not 0 <= x < max_x:
        raise NationalIconBundleError("block_id tile coordinate is out of range")
    south = -90 * MICRODEGREES_PER_DEGREE + y * size
    west = -180 * MICRODEGREES_PER_DEGREE + x * size
    return {
        "south": south,
        "west": west,
        "north": south + size,
        "east": west + size,
    }


def _normalize_catalog(value: Any) -> dict[str, Any]:
    source = _exact_keys(
        value,
        {
            "version",
            "sha256",
            "municipality_count",
            "municipality_codes_sha256",
        },
        "catalog reference",
    )
    count = _integer(
        source["municipality_count"],
        "catalog municipality_count",
        minimum=1,
        maximum=MAX_MUNICIPALITIES,
    )
    return {
        "version": _trimmed_string(source["version"], "catalog version", maximum=128),
        "sha256": _sha256(source["sha256"], "catalog sha256"),
        "municipality_count": count,
        "municipality_codes_sha256": _sha256(
            source["municipality_codes_sha256"],
            "catalog municipality_codes_sha256",
        ),
    }


def _normalize_grid(value: Any) -> dict[str, Any]:
    source = _exact_keys(value, {"sha256", "ni", "nj"}, "grid reference")
    ni = _integer(source["ni"], "grid ni", minimum=1, maximum=10_000)
    nj = _integer(source["nj"], "grid nj", minimum=1, maximum=10_000)
    if ni * nj > MAX_GRID_POINTS:
        raise NationalIconBundleError("grid exceeds maximum point count")
    return {"sha256": _sha256(source["sha256"], "grid sha256"), "ni": ni, "nj": nj}


def _normalize_metadata(
    value: Any,
    *,
    catalog: Mapping[str, Any],
    grid: Mapping[str, Any],
    run_at: str,
    generated_at: str,
) -> dict[str, Any]:
    source = _exact_keys(value, {"model", "source", "variables"}, "metadata")
    model = _exact_keys(source["model"], {"id", "product"}, "metadata model")
    normalized_model = {
        "id": _trimmed_string(model["id"], "model id", maximum=64),
        "product": _trimmed_string(model["product"], "model product", maximum=128),
    }
    if normalized_model["id"] != "icon-2i":
        raise NationalIconBundleError("national bundle model must be icon-2i")
    provider_source = _exact_keys(
        source["source"],
        {"attribution", "license", "license_url"},
        "metadata source",
    )
    license_url = _trimmed_string(
        provider_source["license_url"], "source license_url", maximum=512
    )
    if not license_url.startswith("https://"):
        raise NationalIconBundleError("source license_url must use HTTPS")
    normalized_source = {
        "attribution": _trimmed_string(
            provider_source["attribution"], "source attribution", maximum=512
        ),
        "license": _trimmed_string(
            provider_source["license"], "source license", maximum=128
        ),
        "license_url": license_url,
    }
    variables_source = source["variables"]
    if (
        not isinstance(variables_source, Sequence)
        or isinstance(variables_source, (str, bytes))
        or not 1 <= len(variables_source) <= MAX_VARIABLES
    ):
        raise NationalIconBundleError(
            f"metadata variables must contain 1..{MAX_VARIABLES} entries"
        )
    variables: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(variables_source):
        variable = _exact_keys(
            raw, {"id", "unit", "data_type", "nullable"}, f"variable {index}"
        )
        variable_id = variable["id"]
        if not isinstance(variable_id, str) or not _VARIABLE_ID_RE.fullmatch(variable_id):
            raise NationalIconBundleError(f"variable {index} id is not canonical")
        if variable_id in seen:
            raise NationalIconBundleError(f"duplicate variable id: {variable_id}")
        seen.add(variable_id)
        data_type = variable["data_type"]
        if data_type not in ("float", "integer"):
            raise NationalIconBundleError("variable data_type must be float or integer")
        nullable = variable["nullable"]
        if not isinstance(nullable, bool):
            raise NationalIconBundleError("variable nullable must be boolean")
        variables.append(
            {
                "id": variable_id,
                "unit": _trimmed_string(variable["unit"], "variable unit", maximum=64),
                "data_type": data_type,
                "nullable": nullable,
            }
        )
    variables.sort(key=lambda item: item["id"])
    return {
        "provider": PROVIDER,
        "model": normalized_model,
        "source": normalized_source,
        "catalog": dict(catalog),
        "grid": dict(grid),
        "run_at": run_at,
        "generated_at": generated_at,
        "variables": variables,
    }


def _normalize_time_axis(value: Any, *, run_at: str) -> list[str]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not 1 <= len(value) <= MAX_TIME_STEPS
    ):
        raise NationalIconBundleError(
            f"time_axis must contain 1..{MAX_TIME_STEPS} timestamps"
        )
    parsed = [_parse_utc(item, f"time_axis[{index}]", on_hour=True) for index, item in enumerate(value)]
    run = _parse_utc(run_at, "run_at", on_hour=True)
    if parsed[0] != run:
        raise NationalIconBundleError("time_axis must start at run_at")
    for previous, current in zip(parsed, parsed[1:]):
        if current != previous + timedelta(hours=1):
            raise NationalIconBundleError("time_axis must be consecutive hourly UTC instants")
    return list(value)


def _cell_id(grid_index: int) -> str:
    result = f"g{grid_index:06d}"
    if not _CELL_ID_RE.fullmatch(result):
        raise NationalIconBundleError("grid index cannot form a canonical cell id")
    return result


def _normalize_series_value(value: Any, variable: Mapping[str, Any], label: str) -> Any:
    if value is None:
        if not variable["nullable"]:
            raise NationalIconBundleError(f"{label} cannot be null")
        return None
    if variable["data_type"] == "integer":
        return _integer(value, label, minimum=-2_147_483_648, maximum=2_147_483_647)
    return _number(value, label)


def _normalize_cell(
    value: Any,
    *,
    grid: Mapping[str, Any],
    variables: Sequence[Mapping[str, Any]],
    time_step_count: int,
) -> dict[str, Any]:
    source = _exact_keys(
        value, {"grid_index", "latitude", "longitude", "values"}, "ICON cell"
    )
    max_index = grid["ni"] * grid["nj"] - 1
    grid_index = _integer(source["grid_index"], "cell grid_index", maximum=max_index)
    latitude = _number(source["latitude"], "cell latitude")
    longitude = _number(source["longitude"], "cell longitude")
    if not -90 <= latitude < 90 or not -180 <= longitude < 180:
        raise NationalIconBundleError("cell coordinates are outside the global grid")
    values = source["values"]
    expected_ids = {item["id"] for item in variables}
    if not isinstance(values, Mapping) or set(values) != expected_ids:
        raise NationalIconBundleError("cell values do not match metadata variables")
    normalized_values: dict[str, list[Any]] = {}
    for variable in variables:
        variable_id = variable["id"]
        series = values[variable_id]
        if (
            not isinstance(series, Sequence)
            or isinstance(series, (str, bytes))
            or len(series) != time_step_count
        ):
            raise NationalIconBundleError(
                f"cell {grid_index} variable {variable_id} length differs from time_axis"
            )
        normalized_values[variable_id] = [
            _normalize_series_value(
                item,
                variable,
                f"cell {grid_index} {variable_id}[{index}]",
            )
            for index, item in enumerate(series)
        ]
    return {
        "cell_id": _cell_id(grid_index),
        "grid_index": grid_index,
        "latitude": latitude,
        "longitude": longitude,
        "values": normalized_values,
    }


def _normalize_municipality_cells(
    value: Any,
    *,
    catalog: Mapping[str, Any],
    maximum_grid_index: int,
) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise NationalIconBundleError("municipality_cells must be a mapping")
    if len(value) != catalog["municipality_count"]:
        raise NationalIconBundleError(
            "municipality_cells must exactly cover the catalog municipality_count"
        )
    if not 1 <= len(value) <= MAX_MUNICIPALITIES:
        raise NationalIconBundleError("municipality_cells exceeds contract limits")
    result: dict[str, int] = {}
    for istat_code, grid_index in value.items():
        if not isinstance(istat_code, str) or not _ISTAT_RE.fullmatch(istat_code):
            raise NationalIconBundleError("municipality ISTAT code must contain six digits")
        result[istat_code] = _integer(
            grid_index,
            f"municipality {istat_code} grid_index",
            maximum=maximum_grid_index,
        )
    result = dict(sorted(result.items()))
    observed_codes_sha256 = sha256_hex(canonical_json_bytes(list(result)))
    if observed_codes_sha256 != catalog["municipality_codes_sha256"]:
        raise NationalIconBundleError(
            "municipality_cells identities differ from the canonical catalog"
        )
    return result


def _descriptor(path: str, payload: bytes) -> dict[str, Any]:
    return {"path": path, "json_bytes": len(payload), "sha256": sha256_hex(payload)}


def _commit_digest_record(manifest_without_digest: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact record covered by ``bundle_sha256``."""

    return dict(manifest_without_digest)


def build_national_icon_bundle(
    *,
    run_at: str,
    generated_at: str,
    catalog: Mapping[str, Any],
    grid: Mapping[str, Any],
    metadata: Mapping[str, Any],
    time_axis: Sequence[str],
    municipality_cells: Mapping[str, int],
    cells: Sequence[Mapping[str, Any]],
    tile_size_degrees: Decimal | float | int | str = DEFAULT_TILE_SIZE_DEGREES,
) -> NationalIconBundle:
    """Build and fully validate one all-or-nothing national ICON artifact.

    ``municipality_cells`` maps every catalog ISTAT code to a native ICON
    ``grid_index``.  Duplicate cell records are accepted only when their
    normalized contents are byte-identical and are emitted once.
    """

    run = _parse_utc(run_at, "run_at", on_hour=True)
    generated = _parse_utc(generated_at, "generated_at")
    if generated < run:
        raise NationalIconBundleError("generated_at cannot precede run_at")
    source_run_id = canonical_run_id(run_at)
    normalized_catalog = _normalize_catalog(catalog)
    normalized_grid = _normalize_grid(grid)
    normalized_time_axis = _normalize_time_axis(time_axis, run_at=run_at)
    normalized_metadata = _normalize_metadata(
        metadata,
        catalog=normalized_catalog,
        grid=normalized_grid,
        run_at=run_at,
        generated_at=generated_at,
    )
    assignments = _normalize_municipality_cells(
        municipality_cells,
        catalog=normalized_catalog,
        maximum_grid_index=normalized_grid["ni"] * normalized_grid["nj"] - 1,
    )
    if not isinstance(cells, Sequence) or isinstance(cells, (str, bytes)):
        raise NationalIconBundleError("cells must be an array")
    if not 1 <= len(cells) <= MAX_RAW_CELL_RECORDS:
        raise NationalIconBundleError(
            f"cells must contain 1..{MAX_RAW_CELL_RECORDS} raw records"
        )
    normalized_cells: dict[int, dict[str, Any]] = {}
    for raw_cell in cells:
        cell = _normalize_cell(
            raw_cell,
            grid=normalized_grid,
            variables=normalized_metadata["variables"],
            time_step_count=len(normalized_time_axis),
        )
        grid_index = cell["grid_index"]
        previous = normalized_cells.get(grid_index)
        if previous is not None and canonical_json_bytes(previous) != canonical_json_bytes(cell):
            raise NationalIconBundleError(f"conflicting duplicate ICON cell: {grid_index}")
        normalized_cells[grid_index] = cell
    referenced = set(assignments.values())
    if set(normalized_cells) != referenced:
        missing = referenced - set(normalized_cells)
        extra = set(normalized_cells) - referenced
        raise NationalIconBundleError(
            f"cell set must exactly match municipality references; missing={len(missing)} extra={len(extra)}"
        )

    tile_size_microdegrees = _tile_size_microdegrees(tile_size_degrees)
    decimal_tile_size = Decimal(tile_size_microdegrees) / MICRODEGREES_PER_DEGREE
    block_cells: dict[str, set[int]] = {}
    municipality_blocks: dict[str, str] = {}
    municipalities_by_block: dict[str, dict[str, str]] = {}
    for istat_code, grid_index in assignments.items():
        cell = normalized_cells[grid_index]
        block_id = tile_id_for_coordinate(
            cell["latitude"],
            cell["longitude"],
            tile_size_degrees=decimal_tile_size,
        )
        municipality_blocks[istat_code] = block_id
        municipalities_by_block.setdefault(block_id, {})[istat_code] = cell["cell_id"]
        block_cells.setdefault(block_id, set()).add(grid_index)

    if not 1 <= len(block_cells) <= MAX_BLOCKS:
        raise NationalIconBundleError("block count exceeds contract limits")

    metadata_sha256 = sha256_hex(canonical_json_bytes(normalized_metadata))
    time_axis_sha256 = sha256_hex(canonical_json_bytes(normalized_time_axis))
    descriptors: list[dict[str, Any]] = []
    block_documents: list[tuple[str, bytes]] = []
    for block_id in sorted(block_cells):
        municipality_map = dict(sorted(municipalities_by_block[block_id].items()))
        cell_indexes = sorted(block_cells[block_id])
        if len(municipality_map) > MAX_MUNICIPALITIES_PER_BLOCK:
            raise NationalIconBundleError(
                f"block {block_id} exceeds municipality limit"
            )
        if len(cell_indexes) > MAX_CELLS_PER_BLOCK:
            raise NationalIconBundleError(f"block {block_id} exceeds cell limit")
        block = {
            "kind": BLOCK_KIND,
            "schema_version": SCHEMA_VERSION,
            "contract": CONTRACT_ID,
            "source_run_id": source_run_id,
            "block_id": block_id,
            "tile": {
                "size_microdegrees": tile_size_microdegrees,
                "bounds_microdegrees": _tile_bounds_microdegrees(block_id),
            },
            "metadata": normalized_metadata,
            "time_axis": normalized_time_axis,
            "municipality_cells": municipality_map,
            "cells": [normalized_cells[index] for index in cell_indexes],
        }
        encoded = canonical_json_bytes(block)
        if not 1 <= len(encoded) <= MAX_BLOCK_JSON_BYTES:
            raise NationalIconBundleError(f"block {block_id} exceeds byte limit")
        path = f"runs/{source_run_id}/blocks/{block_id}.json"
        descriptor = {
            "block_id": block_id,
            **_descriptor(path, encoded),
            "municipality_count": len(municipality_map),
            "cell_count": len(cell_indexes),
        }
        descriptors.append(descriptor)
        block_documents.append((path, encoded))

    index = {
        "kind": INDEX_KIND,
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT_ID,
        "source_run_id": source_run_id,
        "catalog": normalized_catalog,
        "grid_sha256": normalized_grid["sha256"],
        "tile_size_microdegrees": tile_size_microdegrees,
        "municipality_blocks": dict(sorted(municipality_blocks.items())),
    }
    index_json = canonical_json_bytes(index)
    if not 1 <= len(index_json) <= MAX_INDEX_JSON_BYTES:
        raise NationalIconBundleError("municipality index exceeds byte limit")
    index_path = f"runs/{source_run_id}/municipality-index.json"
    index_descriptor = _descriptor(index_path, index_json)

    manifest_base = {
        "kind": MANIFEST_KIND,
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT_ID,
        "source_run_id": source_run_id,
        "run_at": run_at,
        "generated_at": generated_at,
        "catalog": normalized_catalog,
        "grid": normalized_grid,
        "tile_size_microdegrees": tile_size_microdegrees,
        "metadata_sha256": metadata_sha256,
        "time_axis_sha256": time_axis_sha256,
        "time_step_count": len(normalized_time_axis),
        "variable_count": len(normalized_metadata["variables"]),
        "municipality_count": len(assignments),
        "unique_cell_count": len(normalized_cells),
        "block_count": len(descriptors),
        "index": index_descriptor,
        "blocks": descriptors,
    }
    manifest = {
        **manifest_base,
        "bundle_sha256": sha256_hex(
            canonical_json_bytes(_commit_digest_record(manifest_base))
        ),
    }
    manifest_json = canonical_json_bytes(manifest)
    if not 1 <= len(manifest_json) <= MAX_MANIFEST_JSON_BYTES:
        raise NationalIconBundleError("manifest exceeds byte limit")
    manifest_path = f"runs/{source_run_id}/manifest.json"
    total_bytes = len(manifest_json) + len(index_json) + sum(
        len(payload) for _, payload in block_documents
    )
    if total_bytes > MAX_BUNDLE_JSON_BYTES:
        raise NationalIconBundleError("bundle exceeds total byte limit")

    bundle = NationalIconBundle(
        manifest_path=manifest_path,
        manifest_json=manifest_json,
        index_path=index_path,
        index_json=index_json,
        block_documents=tuple(block_documents),
    )
    validate_national_icon_bundle(bundle)
    return bundle


def _parse_canonical_document(payload: Any, label: str, maximum: int) -> Any:
    if not isinstance(payload, bytes) or not 1 <= len(payload) <= maximum:
        raise NationalIconBundleError(f"{label} bytes violate contract limits")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NationalIconBundleError(f"{label} is not UTF-8 JSON") from error
    if canonical_json_bytes(value) != payload:
        raise NationalIconBundleError(f"{label} is not canonical JSON")
    return value


def _validate_descriptor(value: Any, label: str, *, block: bool) -> Mapping[str, Any]:
    expected = {"path", "json_bytes", "sha256"}
    if block:
        expected |= {"block_id", "municipality_count", "cell_count"}
    descriptor = _exact_keys(value, expected, label)
    _trimmed_string(descriptor["path"], f"{label} path", maximum=256)
    _integer(descriptor["json_bytes"], f"{label} json_bytes", minimum=1)
    _sha256(descriptor["sha256"], f"{label} sha256")
    if block:
        block_id = descriptor["block_id"]
        if not isinstance(block_id, str) or not _BLOCK_ID_RE.fullmatch(block_id):
            raise NationalIconBundleError(f"{label} block_id is not canonical")
        _integer(
            descriptor["municipality_count"],
            f"{label} municipality_count",
            minimum=1,
            maximum=MAX_MUNICIPALITIES_PER_BLOCK,
        )
        _integer(
            descriptor["cell_count"],
            f"{label} cell_count",
            minimum=1,
            maximum=MAX_CELLS_PER_BLOCK,
        )
    return descriptor


def _validate_manifest(value: Any) -> Mapping[str, Any]:
    manifest = _exact_keys(
        value,
        {
            "kind",
            "schema_version",
            "contract",
            "source_run_id",
            "run_at",
            "generated_at",
            "catalog",
            "grid",
            "tile_size_microdegrees",
            "metadata_sha256",
            "time_axis_sha256",
            "time_step_count",
            "variable_count",
            "municipality_count",
            "unique_cell_count",
            "block_count",
            "index",
            "blocks",
            "bundle_sha256",
        },
        "manifest",
    )
    if (
        manifest["kind"] != MANIFEST_KIND
        or manifest["schema_version"] != SCHEMA_VERSION
        or manifest["contract"] != CONTRACT_ID
    ):
        raise NationalIconBundleError("manifest identity is invalid")
    run_at = manifest["run_at"]
    generated_at = manifest["generated_at"]
    run = _parse_utc(run_at, "manifest run_at", on_hour=True)
    generated = _parse_utc(generated_at, "manifest generated_at")
    if generated < run:
        raise NationalIconBundleError("manifest generated_at precedes run_at")
    if manifest["source_run_id"] != canonical_run_id(run_at):
        raise NationalIconBundleError("manifest source_run_id is invalid")
    catalog = _normalize_catalog(manifest["catalog"])
    grid = _normalize_grid(manifest["grid"])
    size = _integer(
        manifest["tile_size_microdegrees"],
        "manifest tile_size_microdegrees",
        minimum=1,
    )
    if size != _tile_size_microdegrees(Decimal(size) / MICRODEGREES_PER_DEGREE):
        raise NationalIconBundleError("manifest tile size is invalid")
    _sha256(manifest["metadata_sha256"], "manifest metadata_sha256")
    _sha256(manifest["time_axis_sha256"], "manifest time_axis_sha256")
    _sha256(manifest["bundle_sha256"], "manifest bundle_sha256")
    _integer(
        manifest["time_step_count"],
        "manifest time_step_count",
        minimum=1,
        maximum=MAX_TIME_STEPS,
    )
    _integer(
        manifest["variable_count"],
        "manifest variable_count",
        minimum=1,
        maximum=MAX_VARIABLES,
    )
    municipality_count = _integer(
        manifest["municipality_count"],
        "manifest municipality_count",
        minimum=1,
        maximum=MAX_MUNICIPALITIES,
    )
    if municipality_count != catalog["municipality_count"]:
        raise NationalIconBundleError("manifest municipality count differs from catalog")
    _integer(
        manifest["unique_cell_count"],
        "manifest unique_cell_count",
        minimum=1,
        maximum=municipality_count,
    )
    block_count = _integer(
        manifest["block_count"],
        "manifest block_count",
        minimum=1,
        maximum=MAX_BLOCKS,
    )
    _validate_descriptor(manifest["index"], "manifest index", block=False)
    blocks = manifest["blocks"]
    if not isinstance(blocks, list) or len(blocks) != block_count:
        raise NationalIconBundleError("manifest blocks do not match block_count")
    descriptors = [
        _validate_descriptor(item, f"manifest block {index}", block=True)
        for index, item in enumerate(blocks)
    ]
    block_ids = [item["block_id"] for item in descriptors]
    if block_ids != sorted(set(block_ids)):
        raise NationalIconBundleError("manifest block descriptors are not sorted and unique")
    expected_paths = [
        f"runs/{manifest['source_run_id']}/blocks/{block_id}.json"
        for block_id in block_ids
    ]
    if [item["path"] for item in descriptors] != expected_paths:
        raise NationalIconBundleError("manifest block path is not canonical")
    if manifest["index"]["path"] != (
        f"runs/{manifest['source_run_id']}/municipality-index.json"
    ):
        raise NationalIconBundleError("manifest index path is not canonical")
    without_digest = dict(manifest)
    without_digest.pop("bundle_sha256")
    if manifest["bundle_sha256"] != sha256_hex(
        canonical_json_bytes(_commit_digest_record(without_digest))
    ):
        raise NationalIconBundleError("manifest bundle_sha256 is invalid")
    # Keep normalized references live for static type/readability purposes.
    if grid["ni"] * grid["nj"] < manifest["unique_cell_count"]:
        raise NationalIconBundleError("manifest has more cells than the grid")
    return manifest


def validate_national_icon_bundle(bundle: NationalIconBundle) -> None:
    """Validate every relation and hash; accept no partial publication set."""

    if not isinstance(bundle, NationalIconBundle):
        raise NationalIconBundleError("bundle has an invalid type")
    manifest = _validate_manifest(
        _parse_canonical_document(
            bundle.manifest_json, "manifest", MAX_MANIFEST_JSON_BYTES
        )
    )
    expected_manifest_path = f"runs/{manifest['source_run_id']}/manifest.json"
    if bundle.manifest_path != expected_manifest_path:
        raise NationalIconBundleError("manifest path is not canonical")
    index_descriptor = manifest["index"]
    if bundle.index_path != index_descriptor["path"]:
        raise NationalIconBundleError("bundle index path differs from manifest")
    if (
        len(bundle.index_json) != index_descriptor["json_bytes"]
        or sha256_hex(bundle.index_json) != index_descriptor["sha256"]
    ):
        raise NationalIconBundleError("bundle index bytes differ from manifest")
    index = _parse_canonical_document(
        bundle.index_json, "municipality index", MAX_INDEX_JSON_BYTES
    )
    index = _exact_keys(
        index,
        {
            "kind",
            "schema_version",
            "contract",
            "source_run_id",
            "catalog",
            "grid_sha256",
            "tile_size_microdegrees",
            "municipality_blocks",
        },
        "municipality index",
    )
    if (
        index["kind"] != INDEX_KIND
        or index["schema_version"] != SCHEMA_VERSION
        or index["contract"] != CONTRACT_ID
        or index["source_run_id"] != manifest["source_run_id"]
        or index["catalog"] != manifest["catalog"]
        or index["grid_sha256"] != manifest["grid"]["sha256"]
        or index["tile_size_microdegrees"] != manifest["tile_size_microdegrees"]
    ):
        raise NationalIconBundleError("municipality index identity is inconsistent")
    municipality_blocks = index["municipality_blocks"]
    if not isinstance(municipality_blocks, Mapping):
        raise NationalIconBundleError("municipality index mapping is invalid")
    if len(municipality_blocks) != manifest["municipality_count"]:
        raise NationalIconBundleError("municipality index is incomplete")
    for istat_code, block_id in municipality_blocks.items():
        if not isinstance(istat_code, str) or not _ISTAT_RE.fullmatch(istat_code):
            raise NationalIconBundleError("municipality index contains invalid ISTAT")
        if not isinstance(block_id, str) or not _BLOCK_ID_RE.fullmatch(block_id):
            raise NationalIconBundleError("municipality index contains invalid block_id")
    if (
        sha256_hex(canonical_json_bytes(sorted(municipality_blocks)))
        != manifest["catalog"]["municipality_codes_sha256"]
    ):
        raise NationalIconBundleError(
            "municipality index identities differ from the canonical catalog"
        )

    provided_blocks: dict[str, bytes] = {}
    for path, payload in bundle.block_documents:
        if path in provided_blocks:
            raise NationalIconBundleError(f"duplicate block path: {path}")
        provided_blocks[path] = payload
    descriptors = manifest["blocks"]
    expected_block_paths = {item["path"] for item in descriptors}
    if set(provided_blocks) != expected_block_paths:
        raise NationalIconBundleError("block document set is missing or has extras")

    observed_municipalities: dict[str, str] = {}
    observed_cells: set[str] = set()
    observed_municipality_total = 0
    observed_cell_total = 0
    for descriptor in descriptors:
        payload = provided_blocks[descriptor["path"]]
        if (
            len(payload) != descriptor["json_bytes"]
            or sha256_hex(payload) != descriptor["sha256"]
        ):
            raise NationalIconBundleError(
                f"block {descriptor['block_id']} bytes differ from manifest"
            )
        block = _parse_canonical_document(
            payload, f"block {descriptor['block_id']}", MAX_BLOCK_JSON_BYTES
        )
        block = _exact_keys(
            block,
            {
                "kind",
                "schema_version",
                "contract",
                "source_run_id",
                "block_id",
                "tile",
                "metadata",
                "time_axis",
                "municipality_cells",
                "cells",
            },
            f"block {descriptor['block_id']}",
        )
        block_id = descriptor["block_id"]
        if (
            block["kind"] != BLOCK_KIND
            or block["schema_version"] != SCHEMA_VERSION
            or block["contract"] != CONTRACT_ID
            or block["source_run_id"] != manifest["source_run_id"]
            or block["block_id"] != block_id
        ):
            raise NationalIconBundleError(f"block {block_id} identity is inconsistent")
        tile = _exact_keys(
            block["tile"],
            {"size_microdegrees", "bounds_microdegrees"},
            f"block {block_id} tile",
        )
        if (
            tile["size_microdegrees"] != manifest["tile_size_microdegrees"]
            or tile["bounds_microdegrees"] != _tile_bounds_microdegrees(block_id)
        ):
            raise NationalIconBundleError(f"block {block_id} tile is inconsistent")
        metadata = _normalize_metadata(
            {
                "model": block["metadata"].get("model") if isinstance(block["metadata"], Mapping) else None,
                "source": block["metadata"].get("source") if isinstance(block["metadata"], Mapping) else None,
                "variables": block["metadata"].get("variables") if isinstance(block["metadata"], Mapping) else None,
            },
            catalog=manifest["catalog"],
            grid=manifest["grid"],
            run_at=manifest["run_at"],
            generated_at=manifest["generated_at"],
        )
        if metadata != block["metadata"]:
            raise NationalIconBundleError(f"block {block_id} metadata is inconsistent")
        if sha256_hex(canonical_json_bytes(metadata)) != manifest["metadata_sha256"]:
            raise NationalIconBundleError(f"block {block_id} metadata hash is inconsistent")
        time_axis = _normalize_time_axis(block["time_axis"], run_at=manifest["run_at"])
        if (
            len(time_axis) != manifest["time_step_count"]
            or sha256_hex(canonical_json_bytes(time_axis)) != manifest["time_axis_sha256"]
        ):
            raise NationalIconBundleError(f"block {block_id} time axis is inconsistent")
        if len(metadata["variables"]) != manifest["variable_count"]:
            raise NationalIconBundleError(f"block {block_id} variable count is inconsistent")

        municipality_cells = block["municipality_cells"]
        cells = block["cells"]
        if not isinstance(municipality_cells, Mapping) or not isinstance(cells, list):
            raise NationalIconBundleError(f"block {block_id} collections are invalid")
        if len(municipality_cells) != descriptor["municipality_count"]:
            raise NationalIconBundleError(f"block {block_id} municipality count differs")
        if len(cells) != descriptor["cell_count"]:
            raise NationalIconBundleError(f"block {block_id} cell count differs")
        normalized_cell_by_id: dict[str, dict[str, Any]] = {}
        last_grid_index = -1
        for raw_cell in cells:
            cell = _normalize_cell(
                {
                    "grid_index": raw_cell.get("grid_index") if isinstance(raw_cell, Mapping) else None,
                    "latitude": raw_cell.get("latitude") if isinstance(raw_cell, Mapping) else None,
                    "longitude": raw_cell.get("longitude") if isinstance(raw_cell, Mapping) else None,
                    "values": raw_cell.get("values") if isinstance(raw_cell, Mapping) else None,
                },
                grid=manifest["grid"],
                variables=metadata["variables"],
                time_step_count=len(time_axis),
            )
            if raw_cell != cell:
                raise NationalIconBundleError(f"block {block_id} cell is not normalized")
            cell_id = cell["cell_id"]
            if (
                cell["grid_index"] <= last_grid_index
                or cell_id in normalized_cell_by_id
            ):
                raise NationalIconBundleError(f"block {block_id} cells are not sorted and unique")
            last_grid_index = cell["grid_index"]
            if tile_id_for_coordinate(
                cell["latitude"],
                cell["longitude"],
                tile_size_degrees=Decimal(manifest["tile_size_microdegrees"])
                / MICRODEGREES_PER_DEGREE,
            ) != block_id:
                raise NationalIconBundleError(f"block {block_id} contains a foreign cell")
            if cell_id in observed_cells:
                raise NationalIconBundleError(f"cell {cell_id} occurs in multiple blocks")
            observed_cells.add(cell_id)
            normalized_cell_by_id[cell_id] = cell
        referenced_local_cells: set[str] = set()
        for istat_code, cell_id in municipality_cells.items():
            if not isinstance(istat_code, str) or not _ISTAT_RE.fullmatch(istat_code):
                raise NationalIconBundleError(f"block {block_id} contains invalid ISTAT")
            if istat_code in observed_municipalities:
                raise NationalIconBundleError(f"municipality {istat_code} occurs twice")
            if cell_id not in normalized_cell_by_id:
                raise NationalIconBundleError(
                    f"municipality {istat_code} references a foreign cell"
                )
            if municipality_blocks.get(istat_code) != block_id:
                raise NationalIconBundleError(
                    f"municipality {istat_code} index mapping differs from block"
                )
            observed_municipalities[istat_code] = block_id
            referenced_local_cells.add(cell_id)
        if referenced_local_cells != set(normalized_cell_by_id):
            raise NationalIconBundleError(f"block {block_id} contains an unreferenced cell")
        observed_municipality_total += len(municipality_cells)
        observed_cell_total += len(cells)

    if observed_municipalities != dict(municipality_blocks):
        raise NationalIconBundleError("manifest blocks do not completely cover the index")
    if observed_municipality_total != manifest["municipality_count"]:
        raise NationalIconBundleError("manifest municipality total is inconsistent")
    if observed_cell_total != manifest["unique_cell_count"]:
        raise NationalIconBundleError("manifest unique cell total is inconsistent")
    if len(descriptors) != manifest["block_count"]:
        raise NationalIconBundleError("manifest block total is inconsistent")
    total_bytes = len(bundle.manifest_json) + len(bundle.index_json) + sum(
        len(payload) for payload in provided_blocks.values()
    )
    if total_bytes > MAX_BUNDLE_JSON_BYTES:
        raise NationalIconBundleError("bundle exceeds total byte limit")


__all__ = [
    "BLOCK_KIND",
    "CONTRACT_ID",
    "DEFAULT_TILE_SIZE_DEGREES",
    "INDEX_KIND",
    "MANIFEST_KIND",
    "MAX_BLOCK_JSON_BYTES",
    "MAX_CELLS_PER_BLOCK",
    "MAX_MUNICIPALITIES_PER_BLOCK",
    "MAX_RAW_CELL_RECORDS",
    "NationalIconBundle",
    "NationalIconBundleError",
    "build_national_icon_bundle",
    "canonical_json_bytes",
    "canonical_run_id",
    "sha256_hex",
    "tile_id_for_coordinate",
    "validate_national_icon_bundle",
]
