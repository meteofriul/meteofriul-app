"""Bounded local benchmark of one real national ICON-2I run.

This module is an experiment, not an application provider or publisher.  It
discovers one anonymous public ICON-2I run, streams the fourteen already
reviewed pilot fields, validates all 73 GRIB messages per field with ecCodes,
maps every municipality point once, deduplicates native cells, and feeds the
result into the offline ``weather/v2/icon2i`` bundle builder.

The real national payload uses a fixed 0.25-degree geographic tile.  This is
deliberately narrower than the generic bundle contract's default: fourteen
variables times 73 steps can make a 0.5-degree Italian tile exceed the
unchanged 2 MiB per-block contract limit.  The layout is therefore an explicit,
hashed benchmark input and is recorded in both the mapping and report.

There are deliberately no cloud, scheduler, application, Firebase, Cloudflare,
or ``latest`` pointer imports.  Outputs are new local files/directories only;
existing paths are never replaced.  The command line requires an explicit
full-download acknowledgement because one current run is about 1.1 GB.

The checked-in national catalog currently contains generalized-boundary
interior points, not approved municipal forecast points.  They can be used only
with ``--allow-experimental-proxy``.  Likewise the fourteen-variable national
product profile remains explicitly experimental until separately reviewed.
Neither case may be labelled production.
"""

from __future__ import annotations

import argparse
from array import array
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import gc
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
from typing import Any, Mapping, Sequence

from local_pipeline.national_icon_bundle import (
    NationalIconBundle,
    build_national_icon_bundle,
    canonical_json_bytes,
    canonical_run_id,
    sha256_hex,
    validate_national_icon_bundle,
)
from local_pipeline.national_forecast_points import (
    APPROVED_POINTS_STATUS,
    EXPERIMENTAL_POINTS_STATUS,
    FORECAST_POINTS_KIND,
    FORECAST_POINTS_SCHEMA_VERSION,
    NationalForecastPointsError,
    build_experimental_proxy_artifact,
    load_forecast_points_artifact,
    validate_forecast_points_artifact,
)
from national_catalog import validate_catalog
from process_memory import process_memory_bytes
from run_pilot import (
    ACCUM_FIELDS,
    BASE,
    CONTRACTS,
    MAX_BYTES as PILOT_MAX_BYTES,
    MAX_FILE_BYTES as PILOT_MAX_FILE_BYTES,
    META_KEYS,
    StreamingReader,
    accumulation_quantum,
    discover_complete_run,
    stream_messages,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = (
    ROOT / "backend" / "app" / "data" / "italy_municipalities_2026.json"
)

EXPECTED_MUNICIPALITIES = 7_894
FORECAST_STEPS = 73
EXPECTED_MESSAGES = len(CONTRACTS) * FORECAST_STEPS
MAX_TOTAL_SOURCE_BYTES = PILOT_MAX_BYTES
MAX_SOURCE_FILE_BYTES = PILOT_MAX_FILE_BYTES
MAX_GRID_DISTANCE_KM = 5.0

MAPPING_KIND = "meteofriul.weather.icon.national.mapping"
MAPPING_SCHEMA_VERSION = 2
REPORT_KIND = "meteofriul.weather.icon.national.real_grib_benchmark"
REPORT_SCHEMA_VERSION = 2

PRODUCT_PROFILE_ID = "icon2i_surface_pressure_levels_14x73_v1"
PRODUCT_PROFILE_STATUS = "experimental_benchmark_not_production"

# National real-GRIB layout, intentionally local to this benchmark.  Do not
# change the generic national_icon_bundle default: other producers must opt in
# to a layout appropriate for their own variable/time-axis payload.
NATIONAL_BUNDLE_LAYOUT = {
    "id": "italy_quarter_degree_tiles_v1",
    "scope": "national_real_grib_benchmark",
    "tile_size_degrees": "0.25",
    "tile_size_microdegrees": 250_000,
}
NATIONAL_BUNDLE_LAYOUT_SHA256 = sha256_hex(
    canonical_json_bytes(NATIONAL_BUNDLE_LAYOUT)
)

# Output IDs and units are the v2 wire semantics.  Accumulated kg/m2 fields are
# water-equivalent millimetres (1 kg/m2 == 1 mm).  RAIN_CON/RAIN_GSP retain a
# flux-looking GRIB unit in this product even though their stepType and provider
# documentation describe accumulated values; they must never be multiplied by
# 3600.  No interval differencing or meteorological derivation is performed in
# this source bundle benchmark.
VARIABLE_PROFILE: tuple[dict[str, str], ...] = (
    {"source_field": "T_2M", "id": "t_2m_k", "unit": "K", "data_type": "float", "transform": "identity"},
    {"source_field": "TD_2M", "id": "td_2m_k", "unit": "K", "data_type": "float", "transform": "identity"},
    {"source_field": "U_10M", "id": "u_10m_m_s", "unit": "m/s", "data_type": "float", "transform": "identity"},
    {"source_field": "V_10M", "id": "v_10m_m_s", "unit": "m/s", "data_type": "float", "transform": "identity"},
    {"source_field": "CLCT", "id": "cloud_cover_pct", "unit": "percent", "data_type": "float", "transform": "identity"},
    {"source_field": "PMSL", "id": "pressure_msl_pa", "unit": "Pa", "data_type": "float", "transform": "identity"},
    {"source_field": "TOT_PREC", "id": "total_precipitation_mm", "unit": "mm", "data_type": "float", "transform": "water_equivalent_identity"},
    {"source_field": "WW", "id": "weather_code", "unit": "wmo_code", "data_type": "integer", "transform": "exact_integer"},
    {"source_field": "RAIN_CON", "id": "convective_rain_mm", "unit": "mm", "data_type": "float", "transform": "provider_accumulation_identity_no_x3600"},
    {"source_field": "RAIN_GSP", "id": "grid_scale_rain_mm", "unit": "mm", "data_type": "float", "transform": "provider_accumulation_identity_no_x3600"},
    {"source_field": "SNOW_CON", "id": "convective_snow_mm", "unit": "mm", "data_type": "float", "transform": "water_equivalent_identity"},
    {"source_field": "SNOW_GSP", "id": "grid_scale_snow_mm", "unit": "mm", "data_type": "float", "transform": "water_equivalent_identity"},
    {"source_field": "GRAU_GSP", "id": "grid_scale_graupel_mm", "unit": "mm", "data_type": "float", "transform": "water_equivalent_identity"},
    {"source_field": "VMAX_10M", "id": "wind_gust_max_m_s", "unit": "m/s", "data_type": "float", "transform": "identity"},
)

PRODUCT_PROFILE = {
    "id": PRODUCT_PROFILE_ID,
    "status": PRODUCT_PROFILE_STATUS,
    "native_steps": FORECAST_STEPS,
    "variables": list(VARIABLE_PROFILE),
}
PRODUCT_PROFILE_SHA256 = sha256_hex(canonical_json_bytes(PRODUCT_PROFILE))

GRID_DESCRIPTOR_KEYS = (
    "gridType",
    "numberOfPoints",
    "Ni",
    "Nj",
    "md5GridSection",
    "latitudeOfFirstGridPointInDegrees",
    "longitudeOfFirstGridPointInDegrees",
    "latitudeOfLastGridPointInDegrees",
    "longitudeOfLastGridPointInDegrees",
    "iDirectionIncrementInDegrees",
    "jDirectionIncrementInDegrees",
    "iScansNegatively",
    "jScansPositively",
    "jPointsAreConsecutive",
    "alternativeRowScanning",
)


class NationalRealBenchmarkError(ValueError):
    """A local input or public GRIB violates the benchmark contract."""


def _national_bundle_layout_reference() -> dict[str, Any]:
    """Return the immutable-by-convention layout record bound into evidence."""

    return {
        **NATIONAL_BUNDLE_LAYOUT,
        "sha256": NATIONAL_BUNDLE_LAYOUT_SHA256,
    }


def _utc_seconds(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise NationalRealBenchmarkError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _read_json(path: str | Path, label: str) -> Any:
    source = Path(path)
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NationalRealBenchmarkError(f"{label} is unreadable: {source}") from error


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NationalRealBenchmarkError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise NationalRealBenchmarkError(f"{label} must be finite")
    return 0.0 if result == 0 else result


def _catalog_reference(catalog: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": catalog["catalog_version"],
        "sha256": catalog["catalog_sha256"],
        "municipality_count": catalog["municipality_count"],
        "municipality_codes_sha256": catalog["municipality_codes_sha256"],
    }


def load_national_catalog(
    path: str | Path = DEFAULT_CATALOG_PATH,
    *,
    expected_count: int = EXPECTED_MUNICIPALITIES,
) -> dict[str, Any]:
    """Load the self-verifying identity catalog used by this benchmark."""

    document = _read_json(path, "national municipality catalog")
    try:
        validate_catalog(document)
    except ValueError as error:
        raise NationalRealBenchmarkError("national catalog failed validation") from error
    if document["municipality_count"] != expected_count:
        raise NationalRealBenchmarkError(
            f"national catalog must contain exactly {expected_count} municipalities"
        )
    return document


def _proxy_forecast_points(catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Compatibility wrapper backed exclusively by the shared v2 contract."""

    try:
        return build_experimental_proxy_artifact(catalog)
    except NationalForecastPointsError as error:
        raise NationalRealBenchmarkError(
            "experimental forecast-point proxy failed validation"
        ) from error


def load_forecast_points(
    catalog: Mapping[str, Any],
    path: str | Path | None,
    *,
    allow_experimental_proxy: bool,
) -> dict[str, Any]:
    """Load approved points, or explicitly opt into catalog proxy points."""

    if path is None:
        if not allow_experimental_proxy:
            raise NationalRealBenchmarkError(
                "approved forecast points are required; proxy use needs explicit opt-in"
            )
        return _proxy_forecast_points(catalog)
    try:
        return load_forecast_points_artifact(
            path,
            catalog=catalog,
            allow_experimental=allow_experimental_proxy,
        )
    except (NationalForecastPointsError, OSError) as error:
        raise NationalRealBenchmarkError(
            "forecast-point artifact failed the shared v2 contract"
        ) from error


def _grid_section_sha256(ec: Any, handle: Any, message: bytes) -> tuple[str, bytes]:
    offset = ec.codes_get(handle, "offsetSection3")
    length = ec.codes_get(handle, "section3Length")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or isinstance(length, bool)
        or not isinstance(length, int)
        or offset < 16
        or length < 5
        or offset + length > len(message)
    ):
        raise NationalRealBenchmarkError("GRIB Section 3 bounds are invalid")
    section = message[offset : offset + length]
    if int.from_bytes(section[:4], "big") != length or section[4] != 3:
        raise NationalRealBenchmarkError("GRIB Section 3 framing is invalid")
    return hashlib.sha256(section).hexdigest(), section


def _normalized_source_value(field: str, value: Any) -> int | float:
    number = _finite(value, f"{field} decoded value")
    if field == "WW":
        if not number.is_integer() or not 0 <= number <= 99:
            raise NationalRealBenchmarkError("WW must be an integer from 0 to 99")
        return int(number)
    return number


class NationalPointDecoder:
    """Validate GRIB messages and extract each unique native cell once."""

    def __init__(self, points: Sequence[Mapping[str, Any]], ec_module: Any):
        if not points:
            raise NationalRealBenchmarkError("forecast point set is empty")
        self.points = list(points)
        self.ec = ec_module
        self.grid: dict[str, Any] | None = None
        self.grid_descriptor: dict[str, Any] | None = None
        self.section3_bytes: bytes | None = None
        self.unique_indexes: list[int] | None = None
        self.grid_points: dict[int, dict[str, float | int]] = {}
        self.municipality_cells: dict[str, int] = {}
        self.mapping_records: list[dict[str, Any]] = []
        self.seen: set[tuple[str, str, int]] = set()
        self.mapping_seconds = 0.0
        self.decode_seconds = 0.0
        self.mapping_builds = 0

    def _map_points(
        self,
        handle: Any,
        meta: Mapping[str, Any],
        missing: float,
    ) -> list[int | float]:
        started = time.perf_counter()
        nearest = self.ec.codes_grib_find_nearest_multiple(
            handle,
            False,
            [point["latitude"] for point in self.points],
            [point["longitude"] for point in self.points],
        )
        if len(nearest) != len(self.points):
            raise NationalRealBenchmarkError("ecCodes returned an incomplete point mapping")
        first_values: dict[int, int | float] = {}
        for point, match in zip(self.points, nearest, strict=True):
            if not isinstance(match, Mapping):
                raise NationalRealBenchmarkError("ecCodes nearest result is invalid")
            index = match.get("index")
            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or not 0 <= index < meta["numberOfPoints"]
            ):
                raise NationalRealBenchmarkError("ecCodes grid index is invalid")
            cell_latitude = _finite(match.get("lat"), "nearest cell latitude")
            cell_longitude = _finite(match.get("lon"), "nearest cell longitude")
            distance = _finite(match.get("distance"), "nearest cell distance")
            if not -90 <= cell_latitude < 90 or not -180 <= cell_longitude < 180:
                raise NationalRealBenchmarkError("nearest cell lies outside Earth")
            if not 0 <= distance <= MAX_GRID_DISTANCE_KM:
                raise NationalRealBenchmarkError(
                    f"municipality {point['istat_code']} exceeds grid distance limit"
                )
            value = _normalized_source_value(meta["field"], match.get("value"))
            existing_cell = self.grid_points.get(index)
            cell = {
                "grid_index": index,
                "latitude": cell_latitude,
                "longitude": cell_longitude,
            }
            if existing_cell is not None and existing_cell != cell:
                raise NationalRealBenchmarkError("one grid index has conflicting coordinates")
            existing_value = first_values.get(index)
            if existing_value is not None and existing_value != value:
                raise NationalRealBenchmarkError("one grid index has conflicting values")
            self.grid_points[index] = cell
            first_values[index] = value
            self.municipality_cells[point["istat_code"]] = index
            self.mapping_records.append(
                {
                    "istat_code": point["istat_code"],
                    "requested_latitude": point["latitude"],
                    "requested_longitude": point["longitude"],
                    "point_method": point["method"],
                    "point_quality": point["quality"],
                    "point_source": point["source"],
                    "grid_index": index,
                    "cell_latitude": cell_latitude,
                    "cell_longitude": cell_longitude,
                    "distance_km": distance,
                }
            )
        self.unique_indexes = sorted(first_values)
        self.mapping_records.sort(key=lambda item: item["istat_code"])
        self.mapping_seconds += time.perf_counter() - started
        self.mapping_builds += 1
        return [first_values[index] for index in self.unique_indexes]

    def decode(
        self,
        message: bytes,
        *,
        field: str,
        run: str,
        step: int,
    ) -> tuple[list[int | float], dict[str, Any]]:
        identity = (field, run, step)
        if identity in self.seen:
            raise NationalRealBenchmarkError("duplicate GRIB message identity")
        started = time.perf_counter()
        handle = self.ec.codes_new_from_message(message)
        if handle is None:
            raise NationalRealBenchmarkError("ecCodes could not open the GRIB message")
        try:
            self.ec.codes_set(handle, "stepUnits", 1)
            metadata = {key: self.ec.codes_get(handle, key) for key in META_KEYS}
            metadata["field"] = field
            try:
                validate_contract(metadata, field, run, step)
            except ValueError as error:
                raise NationalRealBenchmarkError(
                    f"GRIB metadata validation failed for {field} step {step}"
                ) from error
            if field in ACCUM_FIELDS:
                metadata["encoding_quantum_mm"] = accumulation_quantum(metadata)
            section_sha256, section = _grid_section_sha256(
                self.ec, handle, message
            )
            descriptor = {
                key: self.ec.codes_get(handle, key) for key in GRID_DESCRIPTOR_KEYS
            }
            descriptor["section3_sha256"] = section_sha256
            descriptor["section3_bytes"] = len(section)
            if self.grid_descriptor is None:
                self.grid_descriptor = descriptor
                self.section3_bytes = section
                self.grid = {
                    "sha256": section_sha256,
                    "ni": descriptor["Ni"],
                    "nj": descriptor["Nj"],
                }
            elif descriptor != self.grid_descriptor or section != self.section3_bytes:
                raise NationalRealBenchmarkError("ICON grid changed within the source run")
            missing = _finite(
                self.ec.codes_get(handle, "missingValue"), "GRIB missingValue"
            )
            if self.unique_indexes is None:
                values = self._map_points(handle, metadata, missing)
            else:
                extracted = self.ec.codes_get_elements(
                    handle, "values", self.unique_indexes
                )
                if len(extracted) != len(self.unique_indexes):
                    raise NationalRealBenchmarkError("ecCodes value extraction is incomplete")
                values = [
                    _normalized_source_value(field, value) for value in extracted
                ]
            if any(value == missing for value in values):
                raise NationalRealBenchmarkError("source contains a missing cell value")
            self.seen.add(identity)
            metadata.pop("field")
            return values, metadata
        finally:
            self.ec.codes_release(handle)
            self.decode_seconds += time.perf_counter() - started


def _hashed_chunks(
    chunks: Any,
    *,
    field: str,
    total_counter: list[int],
    digest: Any,
    field_counter: list[int],
):
    for chunk in chunks:
        if not isinstance(chunk, bytes):
            raise NationalRealBenchmarkError(f"{field} source yielded a non-byte chunk")
        if not chunk:
            continue
        field_counter[0] += len(chunk)
        total_counter[0] += len(chunk)
        if field_counter[0] > MAX_SOURCE_FILE_BYTES:
            raise NationalRealBenchmarkError(f"{field} exceeds the per-file byte limit")
        if total_counter[0] > MAX_TOTAL_SOURCE_BYTES:
            raise NationalRealBenchmarkError("ICON run exceeds the total byte limit")
        digest.update(chunk)
        yield chunk


def _field_call_crosscheck(reader: Any, *, bytes_read: int, sha256: str) -> None:
    calls = getattr(reader, "calls", None)
    if not isinstance(calls, list) or not calls:
        return
    call = calls[-1]
    if not isinstance(call, Mapping) or call.get("kind") != "full_variable_stream":
        return
    if call.get("bytes") != bytes_read or call.get("sha256") != sha256:
        raise NationalRealBenchmarkError("reader/source digest cross-check failed")
    if call.get("success") is not True:
        raise NationalRealBenchmarkError("reader did not complete the source stream")


def _benchmark_status(points_status: str, product_profile_status: str) -> str:
    """Describe both independent experimental gates without conflating them."""

    if points_status not in {APPROVED_POINTS_STATUS, EXPERIMENTAL_POINTS_STATUS}:
        raise NationalRealBenchmarkError("forecast-point status is invalid")
    proxy_is_experimental = points_status == EXPERIMENTAL_POINTS_STATUS
    profile_is_experimental = product_profile_status != "approved"
    if proxy_is_experimental and profile_is_experimental:
        return "experimental_proxy_and_product_profile_not_production"
    if proxy_is_experimental:
        return "experimental_proxy_not_production"
    if profile_is_experimental:
        return "experimental_product_profile_not_production"
    return "approved_inputs_benchmark_complete"


def acquire_real_source(
    *,
    forecast_points: Mapping[str, Any],
    run: str | None = None,
    now: datetime | None = None,
    reader: Any | None = None,
    ec_module: Any | None = None,
) -> dict[str, Any]:
    """Acquire and decode one complete run without retaining national GRIBs."""

    benchmark_status = _benchmark_status(
        forecast_points["status"], PRODUCT_PROFILE_STATUS
    )
    if reader is None:
        reader = StreamingReader()
    if ec_module is None:
        try:
            import eccodes as ec_module  # type: ignore[no-redef]
        except ImportError as error:
            raise NationalRealBenchmarkError(
                "ecCodes is required in an isolated benchmark environment"
            ) from error
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise NationalRealBenchmarkError("benchmark clock must be timezone-aware")
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    selected_run, run_time, time_axis, field_urls = discover_complete_run(
        reader, now, run
    )
    expected_fields = [item["source_field"] for item in VARIABLE_PROFILE]
    if expected_fields != list(CONTRACTS) or set(field_urls) != set(expected_fields):
        raise NationalRealBenchmarkError("product profile and source contracts differ")
    decoder = NationalPointDecoder(forecast_points["points"], ec_module)
    total_counter = [0]
    matrices: dict[str, array] = {}
    provenance: dict[str, Any] = {}
    unique_cell_count: int | None = None
    for field in expected_fields:
        digest = hashlib.sha256()
        field_counter = [0]
        message_ranges: list[dict[str, Any]] = []
        matrix_type = "i" if field == "WW" else "d"
        matrix = array(matrix_type)
        first_metadata = last_metadata = None
        offset = 0
        field_started = time.perf_counter()
        chunks = _hashed_chunks(
            reader.chunks(field_urls[field]),
            field=field,
            total_counter=total_counter,
            digest=digest,
            field_counter=field_counter,
        )
        for step, message in enumerate(
            stream_messages(chunks, expected_count=FORECAST_STEPS)
        ):
            values, metadata = decoder.decode(
                message, field=field, run=selected_run, step=step
            )
            if unique_cell_count is None:
                unique_cell_count = len(values)
            if len(values) != unique_cell_count:
                raise NationalRealBenchmarkError("field cell count changed")
            matrix.extend(values)
            message_ranges.append(
                {
                    "step": step,
                    "offset": offset,
                    "bytes": len(message),
                    "sha256": hashlib.sha256(message).hexdigest(),
                }
            )
            offset += len(message)
            first_metadata = first_metadata or metadata
            last_metadata = metadata
        source_sha256 = digest.hexdigest()
        if offset != field_counter[0]:
            raise NationalRealBenchmarkError("GRIB framing does not cover the HTTP body")
        _field_call_crosscheck(
            reader, bytes_read=field_counter[0], sha256=source_sha256
        )
        if unique_cell_count is None or len(matrix) != FORECAST_STEPS * unique_cell_count:
            raise NationalRealBenchmarkError("field matrix is incomplete")
        matrices[field] = matrix
        provenance[field] = {
            "url": field_urls[field],
            "bytes": field_counter[0],
            "sha256": source_sha256,
            "message_count": FORECAST_STEPS,
            "messages": message_ranges,
            "first_metadata": first_metadata,
            "last_metadata": last_metadata,
            "elapsed_seconds": time.perf_counter() - field_started,
        }
    if (
        len(decoder.seen) != EXPECTED_MESSAGES
        or decoder.mapping_builds != 1
        or decoder.grid is None
        or decoder.grid_descriptor is None
        or decoder.unique_indexes is None
        or unique_cell_count != len(decoder.unique_indexes)
    ):
        raise NationalRealBenchmarkError("decoded source run is incomplete")
    return {
        "status": benchmark_status,
        "run": selected_run,
        "run_at": _utc_seconds(run_time),
        "time_axis": list(time_axis),
        "forecast_points": forecast_points,
        "decoder": decoder,
        "field_matrices": matrices,
        "provenance": provenance,
        "metrics": {
            "source_field_bytes": total_counter[0],
            "reader_bytes_including_discovery": getattr(reader, "bytes_read", None),
            "http_get_requests": getattr(reader, "requests", None),
            "network_seconds_including_discovery": getattr(
                reader, "network_seconds", None
            ),
            "decode_seconds": decoder.decode_seconds,
            "mapping_seconds": decoder.mapping_seconds,
            "mapping_builds": decoder.mapping_builds,
            "unique_decoded_messages": len(decoder.seen),
            "duplicate_decoded_messages": 0,
            "acquisition_wall_seconds": time.perf_counter() - started_wall,
            "acquisition_cpu_seconds": time.process_time() - started_cpu,
        },
    }


def _materialize_cells(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    decoder: NationalPointDecoder = snapshot["decoder"]
    indexes = decoder.unique_indexes
    if indexes is None:
        raise NationalRealBenchmarkError("cell mapping has not been built")
    matrices = snapshot["field_matrices"]
    cell_count = len(indexes)
    cells = []
    for position, grid_index in enumerate(indexes):
        values: dict[str, list[int | float]] = {}
        for variable in VARIABLE_PROFILE:
            source_field = variable["source_field"]
            matrix = matrices[source_field]
            series = [
                matrix[step * cell_count + position]
                for step in range(FORECAST_STEPS)
            ]
            if variable["data_type"] == "integer":
                series = [int(value) for value in series]
            else:
                series = [float(value) for value in series]
            values[variable["id"]] = series
        point = decoder.grid_points[grid_index]
        cells.append(
            {
                "grid_index": grid_index,
                "latitude": point["latitude"],
                "longitude": point["longitude"],
                "values": values,
            }
        )
    return cells


def build_real_bundle(
    *,
    snapshot: dict[str, Any],
    catalog: Mapping[str, Any],
    generated_at: str,
) -> NationalIconBundle:
    decoder: NationalPointDecoder = snapshot["decoder"]
    if decoder.grid is None:
        raise NationalRealBenchmarkError("grid reference is unavailable")
    cells = _materialize_cells(snapshot)
    metadata = {
        "model": {
            "id": "icon-2i",
            "product": "surface_pressure_levels_14x73_experimental",
        },
        "source": {
            "attribution": "Agenzia ItaliaMeteo",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
        },
        "variables": [
            {
                "id": variable["id"],
                "unit": variable["unit"],
                "data_type": variable["data_type"],
                "nullable": False,
            }
            for variable in VARIABLE_PROFILE
        ],
    }
    try:
        bundle = build_national_icon_bundle(
            run_at=snapshot["run_at"],
            generated_at=generated_at,
            catalog=_catalog_reference(catalog),
            grid=decoder.grid,
            metadata=metadata,
            time_axis=snapshot["time_axis"],
            municipality_cells=decoder.municipality_cells,
            cells=cells,
            tile_size_degrees=NATIONAL_BUNDLE_LAYOUT["tile_size_degrees"],
        )
    finally:
        cells.clear()
        snapshot["field_matrices"].clear()
        gc.collect()
    validate_national_icon_bundle(bundle)
    manifest = json.loads(bundle.manifest_json)
    if (
        manifest.get("tile_size_microdegrees")
        != NATIONAL_BUNDLE_LAYOUT["tile_size_microdegrees"]
    ):
        raise NationalRealBenchmarkError(
            "bundle manifest does not bind the fixed national layout"
        )
    return bundle


def _nearest_rank(values: Sequence[int], probability: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * probability) - 1)]


def _distribution(values: Sequence[int]) -> dict[str, int | float]:
    if not values:
        raise NationalRealBenchmarkError("cannot summarize an empty distribution")
    return {
        "min": min(values),
        "median": statistics.median(values),
        "p95": _nearest_rank(values, 0.95),
        "max": max(values),
        "total": sum(values),
    }


def _bundle_metrics(bundle: NationalIconBundle) -> dict[str, Any]:
    manifest = json.loads(bundle.manifest_json)
    descriptors = manifest["blocks"]
    block_json = [len(payload) for _, payload in bundle.block_documents]
    block_gzip = [
        len(gzip.compress(payload, compresslevel=6, mtime=0))
        for _, payload in bundle.block_documents
    ]
    index_gzip = gzip.compress(bundle.index_json, compresslevel=6, mtime=0)
    manifest_gzip = gzip.compress(bundle.manifest_json, compresslevel=6, mtime=0)
    return {
        "layout": _national_bundle_layout_reference(),
        "tile_size_microdegrees": manifest["tile_size_microdegrees"],
        "block_count": len(descriptors),
        "max_block_municipality_count": max(
            descriptor["municipality_count"] for descriptor in descriptors
        ),
        "max_block_cell_count": max(
            descriptor["cell_count"] for descriptor in descriptors
        ),
        "block_json_bytes": _distribution(block_json),
        "block_gzip_bytes": _distribution(block_gzip),
        "index": {
            "json_bytes": len(bundle.index_json),
            "gzip_bytes": len(index_gzip),
        },
        "manifest": {
            "json_bytes": len(bundle.manifest_json),
            "gzip_bytes": len(manifest_gzip),
            "sha256": bundle.manifest_sha256,
        },
        "complete_bundle": {
            "json_bytes": sum(block_json)
            + len(bundle.index_json)
            + len(bundle.manifest_json),
            "gzip_bytes": sum(block_gzip) + len(index_gzip) + len(manifest_gzip),
        },
    }


def _input_run_digest(provenance: Mapping[str, Any]) -> str:
    digest_record = {
        field: {
            "url": record["url"],
            "bytes": record["bytes"],
            "sha256": record["sha256"],
            "messages": record["messages"],
        }
        for field, record in provenance.items()
    }
    return sha256_hex(canonical_json_bytes(digest_record))


def build_mapping_artifact(
    *,
    snapshot: Mapping[str, Any],
    catalog: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    decoder: NationalPointDecoder = snapshot["decoder"]
    if decoder.grid_descriptor is None or decoder.grid is None:
        raise NationalRealBenchmarkError("grid mapping is incomplete")
    base = {
        "kind": MAPPING_KIND,
        "schema_version": MAPPING_SCHEMA_VERSION,
        "status": snapshot["status"],
        "method": "eccodes_nearest_v1",
        "source_run_id": canonical_run_id(snapshot["run_at"]),
        "run_at": snapshot["run_at"],
        "generated_at": generated_at,
        "catalog": _catalog_reference(catalog),
        "forecast_points": {
            "kind": snapshot["forecast_points"]["kind"],
            "schema_version": snapshot["forecast_points"]["schema_version"],
            "status": snapshot["forecast_points"]["status"],
            "point_count": snapshot["forecast_points"]["point_count"],
            "points_sha256": snapshot["forecast_points"]["points_sha256"],
            "artifact_sha256": snapshot["forecast_points"]["artifact_sha256"],
            "resolution_policy_sha256": snapshot["forecast_points"][
                "resolution_policy_sha256"
            ],
        },
        "product_profile": {
            "id": PRODUCT_PROFILE_ID,
            "status": PRODUCT_PROFILE_STATUS,
            "sha256": PRODUCT_PROFILE_SHA256,
        },
        "bundle_layout": _national_bundle_layout_reference(),
        "grid": {**decoder.grid_descriptor, "sha256": decoder.grid["sha256"]},
        "input_run_sha256": _input_run_digest(snapshot["provenance"]),
        "source_fields": snapshot["provenance"],
        "municipality_mappings": decoder.mapping_records,
    }
    return {
        **base,
        "mapping_sha256": sha256_hex(canonical_json_bytes(base)),
    }


def _mapping_metrics(decoder: NationalPointDecoder) -> dict[str, Any]:
    cells = Counter(decoder.municipality_cells.values())
    distances = [record["distance_km"] for record in decoder.mapping_records]
    return {
        "municipality_count": len(decoder.mapping_records),
        "unique_cell_count": len(cells),
        "shared_cell_count": sum(count > 1 for count in cells.values()),
        "max_municipalities_per_cell": max(cells.values()),
        "max_distance_km": max(distances),
        "mean_distance_km": statistics.fmean(distances),
    }


def _with_self_sha256(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    if field in value:
        raise NationalRealBenchmarkError(f"self digest field already exists: {field}")
    return {**dict(value), field: sha256_hex(canonical_json_bytes(value))}


def run_real_benchmark(
    *,
    catalog: Mapping[str, Any],
    forecast_points: Mapping[str, Any],
    run: str | None = None,
    now: datetime | None = None,
    reader: Any | None = None,
    ec_module: Any | None = None,
    memory_reader=process_memory_bytes,
) -> tuple[NationalIconBundle, dict[str, Any], dict[str, Any]]:
    """Run the in-memory benchmark.  Callers decide whether to write outputs."""

    try:
        validate_forecast_points_artifact(
            forecast_points,
            catalog=catalog,
            allow_experimental=(
                forecast_points.get("status") == EXPERIMENTAL_POINTS_STATUS
            ),
        )
    except NationalForecastPointsError as error:
        raise NationalRealBenchmarkError(
            "forecast points failed the shared v2 contract"
        ) from error

    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    memory_initial = memory_reader()
    snapshot = acquire_real_source(
        forecast_points=forecast_points,
        run=run,
        now=now,
        reader=reader,
        ec_module=ec_module,
    )
    generated_at = _utc_seconds(datetime.now(timezone.utc))
    bundle_started = time.perf_counter()
    bundle = build_real_bundle(
        snapshot=snapshot, catalog=catalog, generated_at=generated_at
    )
    bundle_seconds = time.perf_counter() - bundle_started
    mapping = build_mapping_artifact(
        snapshot=snapshot, catalog=catalog, generated_at=generated_at
    )
    metrics_started = time.perf_counter()
    bundle_metrics = _bundle_metrics(bundle)
    serialization_seconds = time.perf_counter() - metrics_started
    memory_final = memory_reader()
    decoder: NationalPointDecoder = snapshot["decoder"]
    report_base = {
        "kind": REPORT_KIND,
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": snapshot["status"],
        "run_at": snapshot["run_at"],
        "source_run_id": canonical_run_id(snapshot["run_at"]),
        "generated_at": generated_at,
        "catalog": _catalog_reference(catalog),
        "forecast_points": {
            "kind": forecast_points["kind"],
            "schema_version": forecast_points["schema_version"],
            "status": forecast_points["status"],
            "point_count": forecast_points["point_count"],
            "points_sha256": forecast_points["points_sha256"],
            "artifact_sha256": forecast_points["artifact_sha256"],
            "resolution_policy_sha256": forecast_points[
                "resolution_policy_sha256"
            ],
        },
        "product_profile": {
            "id": PRODUCT_PROFILE_ID,
            "status": PRODUCT_PROFILE_STATUS,
            "sha256": PRODUCT_PROFILE_SHA256,
            "variable_count": len(VARIABLE_PROFILE),
            "time_step_count": FORECAST_STEPS,
        },
        "bundle_layout": _national_bundle_layout_reference(),
        "mapping": {
            "sha256": mapping["mapping_sha256"],
            **_mapping_metrics(decoder),
        },
        "source": {
            "provider": "Agenzia ItaliaMeteo",
            "base_url": BASE,
            "input_run_sha256": mapping["input_run_sha256"],
            "field_count": len(snapshot["provenance"]),
            "message_count": len(decoder.seen),
            "fields": snapshot["provenance"],
        },
        "bundle": bundle_metrics,
        "execution": {
            **snapshot["metrics"],
            "bundle_build_seconds": bundle_seconds,
            "bundle_measurement_seconds": serialization_seconds,
            "total_wall_seconds": time.perf_counter() - started_wall,
            "total_cpu_seconds": time.process_time() - started_cpu,
            "memory_initial": memory_initial,
            "memory_final": memory_final,
        },
        "limits": [
            "This is one local run, not forecast-accuracy validation, reliability statistics, a Cloud Run benchmark, or a cost guarantee.",
            "No source GRIB is retained; full-field and per-message SHA-256 evidence binds the measured inputs, but provider retention controls later byte-for-byte replay.",
            "No cloud object, scheduler, application runtime, pilot dataset, notification, or latest pointer is read or changed.",
            "The product profile is explicitly experimental and cannot be labelled production.",
        ],
    }
    return bundle, mapping, _with_self_sha256(report_base, "report_sha256")


def _resolved_distinct(paths: Sequence[Path]) -> None:
    resolved = [path.resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise NationalRealBenchmarkError("output paths must be distinct")


def preflight_output_paths(
    *,
    bundle_dir: str | Path,
    mapping_path: str | Path,
    report_path: str | Path,
) -> tuple[Path, Path, Path]:
    bundle = Path(bundle_dir)
    mapping = Path(mapping_path)
    report = Path(report_path)
    _resolved_distinct((bundle, mapping, report))
    for path in (bundle, mapping, report):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"output already exists: {path}")
        if not path.parent.is_dir():
            raise NationalRealBenchmarkError(
                f"output parent directory does not exist: {path.parent}"
            )
    return bundle, mapping, report


def _write_new(path: Path, payload: bytes) -> None:
    with path.open("xb") as destination:
        destination.write(payload)


def write_outputs_create_only(
    *,
    bundle: NationalIconBundle,
    mapping: Mapping[str, Any],
    report: Mapping[str, Any],
    bundle_dir: str | Path,
    mapping_path: str | Path,
    report_path: str | Path,
) -> None:
    bundle_target, mapping_target, report_target = preflight_output_paths(
        bundle_dir=bundle_dir, mapping_path=mapping_path, report_path=report_path
    )
    bundle_target.mkdir()
    try:
        for relative, payload in bundle.publication_order():
            parts = Path(relative).parts
            if not parts or any(part in ("", ".", "..") for part in parts):
                raise NationalRealBenchmarkError("bundle contains an unsafe path")
            target = bundle_target.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_new(target, payload)
        _write_new(mapping_target, canonical_json_bytes(mapping))
        _write_new(report_target, canonical_json_bytes(report))
    except Exception:
        # Do not delete material evidence or an existing caller path.  The
        # directory was proven absent and created by this invocation, so a
        # failure remains visibly partial and can be inspected or removed by
        # the operator; it is never treated as a complete benchmark.
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument(
        "--points",
        type=Path,
        help="approved national forecast-points artifact; omit only with proxy opt-in",
    )
    parser.add_argument("--run", help="public ICON run YYYYMMDDHH; default newest complete")
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--allow-experimental-proxy",
        action="store_true",
        help="permit generalized-boundary forecast points",
    )
    parser.add_argument(
        "--allow-experimental-product-profile",
        action="store_true",
        help="permit the separately experimental fourteen-variable product profile",
    )
    parser.add_argument(
        "--confirm-full-download",
        action="store_true",
        help="acknowledge the bounded ~1.1 GB anonymous source transfer",
    )
    arguments = parser.parse_args(argv)
    if not arguments.confirm_full_download:
        parser.error("--confirm-full-download is required before any network access")
    if (
        PRODUCT_PROFILE_STATUS != "approved"
        and not arguments.allow_experimental_product_profile
    ):
        parser.error(
            "the current product profile is experimental; use its explicit profile opt-in"
        )
    preflight_output_paths(
        bundle_dir=arguments.bundle_dir,
        mapping_path=arguments.mapping,
        report_path=arguments.report,
    )
    catalog = load_national_catalog(arguments.catalog)
    points = load_forecast_points(
        catalog,
        arguments.points,
        allow_experimental_proxy=arguments.allow_experimental_proxy,
    )
    bundle, mapping, report = run_real_benchmark(
        catalog=catalog,
        forecast_points=points,
        run=arguments.run,
    )
    write_outputs_create_only(
        bundle=bundle,
        mapping=mapping,
        report=report,
        bundle_dir=arguments.bundle_dir,
        mapping_path=arguments.mapping,
        report_path=arguments.report,
    )
    summary = {
        "status": report["status"],
        "source_run_id": report["source_run_id"],
        "source_field_bytes": report["execution"]["source_field_bytes"],
        "unique_cell_count": report["mapping"]["unique_cell_count"],
        "bundle_json_bytes": report["bundle"]["complete_bundle"]["json_bytes"],
        "bundle_gzip_bytes": report["bundle"]["complete_bundle"]["gzip_bytes"],
        "bundle_dir": str(arguments.bundle_dir),
        "mapping": str(arguments.mapping),
        "report": str(arguments.report),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
