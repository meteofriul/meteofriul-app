"""Convert the verified local ICON/CAMS pilot snapshots into contract-v1 data.

This module is deliberately offline.  It proves that the real 215-municipality
pilot artifacts can be split into independent, immutable provider documents
without contacting ICON, ADS, Open-Meteo or any application endpoint.

The complete 28-variable CAMS extraction remains both the verified analysis
input and the lossless v1 municipality payload.  The user interface may later
choose a smaller display subset without discarding data at materialization.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping
import zipfile

from .operational_diagnostics import attach_error_fields

from .contract_v1 import (
    CATALOG_VERSION,
    CAMS_POLLEN_PROVIDER,
    CAMS_VARIABLE_IDS,
    CAMS_PROVIDER,
    DEFAULT_CATALOG_PATH,
    ICON_PROVIDER,
    LEGACY_FIXTURE_CATALOG_VERSION,
    Catalog,
    ContractError,
    build_cams_payload,
    build_cams_pollen_payload,
    build_icon_condition,
    build_icon_payload,
    build_run_manifest,
    canonical_json_bytes,
    load_catalog,
    validate_cams_payload,
    validate_cams_pollen_payload,
    validate_icon_payload,
    validate_run_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ICON_ARCHIVE = ROOT / "icon2i_integrated_payload_20260903.zip"
DEFAULT_ICON_REPORT = ROOT / "icon2i_integrated_report_20260903.json"
DEFAULT_CAMS_PAYLOAD = ROOT / "cams_fvg_payload_20260903.json"
DEFAULT_CAMS_REPORT = ROOT / "cams_fvg_decode_report_20260903.json"

ICON_ARCHIVE_MEMBER = "pilot.json"
# Full 215x73 snapshots include per-hour accumulation provenance. The
# 2026-10-20 run produced 34,601,901 bytes, beyond the legacy 32 MiB cap.
# Keep a finite 64 MiB input cap; checkpoint and per-object limits are separate.
MAX_ICON_JSON_BYTES = 64 * 1024 * 1024
MAX_CAMS_JSON_BYTES = 64 * 1024 * 1024
EXPECTED_CAMS_VARIABLES = 28
EXPECTED_ICON_HOURS = 73
EXPECTED_CAMS_HOURS = 97


class SnapshotMaterializationError(ContractError):
    """A verified source snapshot cannot be materialized into v1 documents."""


def _read_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SnapshotMaterializationError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise SnapshotMaterializationError(f"{label} must be a JSON object")
    return value


def _size_error(label: str, observed: int, maximum: int) -> SnapshotMaterializationError:
    return attach_error_fields(
        SnapshotMaterializationError(f"{label} exceeds its local size bound"),
        artifact_kind=label.lower().replace(" ", "_"),
        observed_bytes=observed,
        limit_bytes=maximum,
    )


def _read_bounded(path: Path, maximum: int, label: str) -> bytes:
    path = Path(path)
    if not path.is_file():
        raise SnapshotMaterializationError(f"{label} is missing")
    size = path.stat().st_size
    if not 1 <= size <= maximum:
        raise _size_error(label, size, maximum)
    # Bound the actual read too: the file can grow after stat().
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise _size_error(label, len(raw), maximum)
    if len(raw) != size:
        raise SnapshotMaterializationError(f"{label} changed while it was read")
    return raw


def _report_digest(report: Mapping[str, Any], field: str, label: str) -> str:
    digest = report.get(field)
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise SnapshotMaterializationError(f"{label} does not contain a valid SHA-256")
    return digest


def _canonical_second(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise SnapshotMaterializationError(f"{label} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SnapshotMaterializationError(f"{label} is not a valid UTC timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SnapshotMaterializationError(f"{label} must include a UTC offset")
    parsed = parsed.astimezone(timezone.utc).replace(microsecond=0)
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_verified_icon_snapshot(
    *,
    icon_archive: str | Path = DEFAULT_ICON_ARCHIVE,
    icon_report: str | Path = DEFAULT_ICON_REPORT,
) -> dict[str, Any]:
    """Read and authenticate the ICON artifact without touching CAMS."""

    icon_report_value = _read_json_bytes(
        _read_bounded(Path(icon_report), 4 * 1024 * 1024, "ICON report"),
        "ICON report",
    )
    archive_path = Path(icon_archive)
    if archive_path.suffix.lower() == ".zip":
        if not archive_path.is_file():
            raise SnapshotMaterializationError("ICON archive is missing")
        try:
            with zipfile.ZipFile(archive_path) as archive:
                names = archive.namelist()
                if names != [ICON_ARCHIVE_MEMBER]:
                    raise SnapshotMaterializationError("ICON archive member set is unexpected")
                info = archive.getinfo(ICON_ARCHIVE_MEMBER)
                if not 1 <= info.file_size <= MAX_ICON_JSON_BYTES:
                    raise _size_error("ICON JSON", info.file_size, MAX_ICON_JSON_BYTES)
                with archive.open(info) as stream:
                    icon_raw = stream.read(MAX_ICON_JSON_BYTES + 1)
        except (OSError, zipfile.BadZipFile, KeyError) as error:
            raise SnapshotMaterializationError("ICON archive cannot be read") from error
        if len(icon_raw) > MAX_ICON_JSON_BYTES:
            raise _size_error("ICON JSON", len(icon_raw), MAX_ICON_JSON_BYTES)
        if len(icon_raw) != info.file_size:
            raise SnapshotMaterializationError("ICON archive member is truncated")
    else:
        icon_raw = _read_bounded(archive_path, MAX_ICON_JSON_BYTES, "ICON payload")
    expected_icon = _report_digest(icon_report_value, "payload_sha256", "ICON report")
    if hashlib.sha256(icon_raw).hexdigest() != expected_icon:
        raise SnapshotMaterializationError("ICON snapshot hash differs from its report")

    icon = _read_json_bytes(icon_raw, "ICON snapshot")
    icon_catalog_sha256 = _report_digest(
        icon_report_value, "catalog_sha256", "ICON report"
    )
    embedded_icon_catalog = icon.get("catalog_sha256")
    if embedded_icon_catalog not in (None, icon_catalog_sha256):
        raise SnapshotMaterializationError(
            "ICON snapshot catalog differs from its report"
        )
    # Older and current ICON pilot payloads keep the catalog fingerprint in the
    # independently verified report rather than duplicating it in the large
    # payload. Carry that verified sidecar value into the in-memory envelope so
    # it can be checked directly against the selected authoritative catalog.
    if embedded_icon_catalog is None:
        icon = dict(icon)
        icon["catalog_sha256"] = icon_catalog_sha256

    if icon.get("schema_version") != 1 or icon.get("status") != "partial_pilot_not_production":
        raise SnapshotMaterializationError("ICON snapshot envelope is not the verified pilot")
    report_run = _canonical_second(icon_report_value.get("run_utc"), "ICON report run")
    payload_run = _canonical_second(icon.get("run_utc"), "ICON snapshot run")
    if report_run != payload_run:
        raise SnapshotMaterializationError(
            "ICON report and snapshot identify different model runs"
        )
    return icon


def load_verified_cams_snapshot(
    *,
    cams_payload: str | Path = DEFAULT_CAMS_PAYLOAD,
    cams_report: str | Path = DEFAULT_CAMS_REPORT,
) -> dict[str, Any]:
    """Read and authenticate the CAMS artifact without touching ICON."""

    cams_raw = _read_bounded(Path(cams_payload), MAX_CAMS_JSON_BYTES, "CAMS payload")
    cams_report_value = _read_json_bytes(
        _read_bounded(Path(cams_report), 4 * 1024 * 1024, "CAMS report"),
        "CAMS report",
    )
    expected_cams = _report_digest(cams_report_value, "payload_sha256", "CAMS report")
    if hashlib.sha256(cams_raw).hexdigest() != expected_cams:
        raise SnapshotMaterializationError("CAMS snapshot hash differs from its report")

    cams = _read_json_bytes(cams_raw, "CAMS snapshot")

    cams_catalog_sha256 = _report_digest(
        cams_report_value, "catalog_sha256", "CAMS report"
    )
    if cams.get("catalog_sha256") != cams_catalog_sha256:
        raise SnapshotMaterializationError(
            "CAMS snapshot catalog differs from its report"
        )
    if cams.get("schema_version") != 2 or cams.get("kind") != "cams_region_point_extraction":
        raise SnapshotMaterializationError("CAMS snapshot envelope is not the verified extraction")
    identity_fields = ("run_date", "request_plan_sha256", "request_sha256")
    # The earliest measurement fixture predates immutable acquisition evidence.
    # Current lifecycle reports carry all three fields; once any appears, treat
    # the set as an atomic identity and fail closed when it is incomplete.
    if any(field in cams_report_value for field in identity_fields):
        if not all(field in cams_report_value for field in identity_fields):
            raise SnapshotMaterializationError(
                "CAMS report acquisition identity is incomplete"
            )
        run_date = cams_report_value.get("run_date")
        if not isinstance(run_date, str):
            raise SnapshotMaterializationError("CAMS report run date is missing")
        try:
            parsed_run_date = datetime.strptime(run_date, "%Y-%m-%d")
        except ValueError as error:
            raise SnapshotMaterializationError("CAMS report run date is invalid") from error
        if parsed_run_date.strftime("%Y-%m-%d") != run_date:
            raise SnapshotMaterializationError("CAMS report run date is invalid")
        payload_run = _canonical_second(cams.get("run_utc"), "CAMS snapshot run")
        if payload_run != f"{run_date}T00:00:00Z":
            raise SnapshotMaterializationError(
                "CAMS report and snapshot identify different model runs"
            )
        for field in ("request_plan_sha256", "request_sha256"):
            report_value = _report_digest(cams_report_value, field, "CAMS report")
            if cams.get(field) != report_value:
                raise SnapshotMaterializationError(
                    f"CAMS snapshot {field} differs from its report"
                )
    return cams


def load_verified_snapshots(
    *,
    icon_archive: str | Path = DEFAULT_ICON_ARCHIVE,
    icon_report: str | Path = DEFAULT_ICON_REPORT,
    cams_payload: str | Path = DEFAULT_CAMS_PAYLOAD,
    cams_report: str | Path = DEFAULT_CAMS_REPORT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read both independently authenticated artifacts for compatibility tests."""

    icon = load_verified_icon_snapshot(
        icon_archive=icon_archive,
        icon_report=icon_report,
    )
    cams = load_verified_cams_snapshot(
        cams_payload=cams_payload,
        cams_report=cams_report,
    )
    return icon, cams


def _finite_or_null(value: Any, label: str, *, minimum: float | None = None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SnapshotMaterializationError(f"{label} must be finite or null")
    if minimum is not None and value < minimum:
        raise SnapshotMaterializationError(f"{label} is below its minimum")


def _catalog_by_slug(catalog: Catalog) -> dict[str, Any]:
    result = {municipality.slug: municipality for municipality in catalog.municipalities}
    if len(result) != catalog.municipality_count:
        raise SnapshotMaterializationError("catalog contains duplicate municipality slugs")
    return result


def _legacy_source_catalog_sha256() -> str:
    return hashlib.sha256(Path(DEFAULT_CATALOG_PATH).read_bytes()).hexdigest()


def _validate_source_catalog(source: Mapping[str, Any], catalog: Catalog, label: str) -> None:
    observed = source.get("catalog_sha256")
    expected = (
        catalog.sha256
        if catalog.version == CATALOG_VERSION
        else _legacy_source_catalog_sha256()
        if catalog.version == LEGACY_FIXTURE_CATALOG_VERSION
        else None
    )
    if observed != expected:
        raise SnapshotMaterializationError(
            f"{label} source catalog differs from the selected representative points"
        )


def _towns_by_slug(value: Any, label: str, catalog: Catalog) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, list) or len(value) != catalog.municipality_count:
        raise SnapshotMaterializationError(f"{label} must cover all 215 municipalities")
    result: dict[str, Mapping[str, Any]] = {}
    for town in value:
        if not isinstance(town, Mapping):
            raise SnapshotMaterializationError(f"{label} contains a non-object municipality")
        slug = town.get("id")
        if not isinstance(slug, str) or slug in result:
            raise SnapshotMaterializationError(f"{label} contains an invalid or duplicate slug")
        result[slug] = town
    if set(result) != set(_catalog_by_slug(catalog)):
        raise SnapshotMaterializationError(f"{label} and the canonical catalog differ")
    return result


def validate_complete_cams_archive(cams: Mapping[str, Any], catalog: Catalog) -> dict[str, Any]:
    """Validate that the private source still contains all 28 requested fields."""

    towns = _towns_by_slug(cams.get("municipalities"), "CAMS municipalities", catalog)
    raw_variables = cams.get("variables")
    times = cams.get("times_utc")
    cells = cams.get("cells")
    if not isinstance(raw_variables, list) or len(raw_variables) != EXPECTED_CAMS_VARIABLES:
        raise SnapshotMaterializationError("CAMS archive must contain all 28 variables")
    variable_ids = [item.get("id") for item in raw_variables if isinstance(item, Mapping)]
    if len(variable_ids) != EXPECTED_CAMS_VARIABLES or len(set(variable_ids)) != len(variable_ids):
        raise SnapshotMaterializationError("CAMS archive variable identities are invalid")
    if set(variable_ids) != set(CAMS_VARIABLE_IDS):
        raise SnapshotMaterializationError(
            "CAMS archive variables differ from the approved 28-variable contract"
        )
    if not isinstance(times, list) or len(times) != EXPECTED_CAMS_HOURS:
        raise SnapshotMaterializationError("CAMS archive must contain 97 hourly instants")
    normalized_times = [_canonical_second(value, "CAMS valid time") for value in times]
    if normalized_times != times:
        raise SnapshotMaterializationError("CAMS valid times must already use canonical UTC seconds")
    if not isinstance(cells, list) or not cells:
        raise SnapshotMaterializationError("CAMS archive has no decoded cells")
    cell_by_id: dict[str, Mapping[str, Any]] = {}
    for cell in cells:
        if not isinstance(cell, Mapping) or not isinstance(cell.get("id"), str):
            raise SnapshotMaterializationError("CAMS archive contains an invalid cell")
        if cell["id"] in cell_by_id:
            raise SnapshotMaterializationError("CAMS archive contains duplicate cells")
        values = cell.get("values")
        raw_values = cell.get("raw_values")
        if not isinstance(values, Mapping) or set(values) != set(variable_ids):
            raise SnapshotMaterializationError("CAMS cell converted variables are incomplete")
        if not isinstance(raw_values, Mapping) or set(raw_values) != set(variable_ids):
            raise SnapshotMaterializationError("CAMS cell raw variables are incomplete")
        for variable in variable_ids:
            for collection, minimum in ((values, 0), (raw_values, None)):
                series = collection[variable]
                if not isinstance(series, list) or len(series) != EXPECTED_CAMS_HOURS:
                    raise SnapshotMaterializationError("CAMS cell variable timeline is incomplete")
                for sample in series:
                    _finite_or_null(sample, f"CAMS {variable}", minimum=minimum)
        cell_by_id[cell["id"]] = cell
    for town in towns.values():
        if town.get("cell_id") not in cell_by_id:
            raise SnapshotMaterializationError("CAMS municipality references an unknown cell")
    return {
        "municipality_count": len(towns),
        "unique_cell_count": len(cell_by_id),
        "hourly_instants": len(times),
        "variable_count": len(variable_ids),
        "variable_ids": tuple(sorted(variable_ids)),
        "catalog_sha256": catalog.sha256,
    }


def materialize_icon_documents(
    icon: Mapping[str, Any],
    catalog: Catalog | None = None,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    catalog = catalog or load_catalog()
    _validate_source_catalog(icon, catalog, "ICON")
    towns = _towns_by_slug(icon.get("municipalities"), "ICON municipalities", catalog)
    run_at = _canonical_second(icon.get("run_utc"), "ICON run")
    generated_at = _canonical_second(icon.get("generated_at_utc"), "ICON generation")
    catalog_slugs = _catalog_by_slug(catalog)
    documents: dict[str, bytes] = {}

    for slug, municipality in catalog_slugs.items():
        town = towns[slug]
        source_rows = town.get("hourly")
        grid = town.get("grid_point")
        if not isinstance(source_rows, list) or len(source_rows) != EXPECTED_ICON_HOURS:
            raise SnapshotMaterializationError("ICON municipality timeline is incomplete")
        if not isinstance(grid, Mapping):
            raise SnapshotMaterializationError("ICON municipality grid point is missing")
        hourly: list[dict[str, Any]] = []
        for lead, source in enumerate(source_rows):
            if not isinstance(source, Mapping):
                raise SnapshotMaterializationError("ICON hourly sample is not an object")
            valid_at = _canonical_second(source.get("valid_at_utc"), "ICON valid time")
            condition = source.get("condition")
            condition_is_valid = (
                isinstance(condition, Mapping) and condition.get("status") == "valid"
            )
            native_code = condition.get("code") if condition_is_valid else None
            flags = list(source.get("quality_flags") or [])
            if not condition_is_valid:
                flags.append("native_condition_unavailable")
            hourly.append(
                {
                    "valid_at": valid_at,
                    "interval_start": None if lead == 0 else _canonical_second(
                        source_rows[lead - 1].get("valid_at_utc"), "ICON interval start"
                    ),
                    "interval_end": None if lead == 0 else valid_at,
                    "temperature_c": source.get("temperature_c"),
                    "apparent_temperature_c": source.get("apparent_temperature_c"),
                    "relative_humidity_pct": source.get("relative_humidity_pct"),
                    "pressure_msl_hpa": source.get("pressure_msl_hpa"),
                    "wind_speed_m_s": source.get("wind_m_s"),
                    "wind_from_degrees": source.get("wind_from_degrees"),
                    "wind_gust_max_m_s": source.get("wind_gust_m_s"),
                    "cloud_cover_pct": source.get("cloud_cover_pct"),
                    "precipitation_mm": source.get("precipitation_previous_hour_mm"),
                    "liquid_rain_mm": source.get("rain_previous_hour_mm"),
                    "snow_water_equivalent_mm": source.get(
                        "snow_water_equivalent_previous_hour_mm"
                    ),
                    "condition": build_icon_condition(native_code),
                    "quality_flags": flags,
                    **({"accumulation_quality": source["accumulation_quality"]}
                       if "accumulation_quality" in source else {}),
                }
            )
        payload = build_icon_payload(
            catalog=catalog,
            istat_code=municipality.istat_code,
            run_at=run_at,
            generated_at=generated_at,
            model_point={
                "lat": grid.get("lat"),
                "lon": grid.get("lon"),
                "distance_km": grid.get("distance"),
                "grid_index": grid.get("index"),
            },
            hourly=hourly,
        )
        validate_icon_payload(payload, catalog, expected_istat_code=municipality.istat_code)
        documents[municipality.istat_code] = canonical_json_bytes(payload)

    manifest = build_run_manifest(
        provider=ICON_PROVIDER,
        run_at=run_at,
        generated_at=generated_at,
        catalog=catalog,
        objects=documents,
    )
    validate_run_manifest(manifest, catalog, expected_provider=ICON_PROVIDER, object_bodies=documents)
    return documents, manifest


def materialize_cams_core_documents(
    cams: Mapping[str, Any],
    catalog: Catalog | None = None,
) -> tuple[
    dict[str, bytes],
    dict[str, Any],
    dict[str, bytes],
    dict[str, Any],
    dict[str, Any],
]:
    catalog = catalog or load_catalog()
    _validate_source_catalog(cams, catalog, "CAMS")
    archive_summary = validate_complete_cams_archive(cams, catalog)
    towns = _towns_by_slug(cams.get("municipalities"), "CAMS municipalities", catalog)
    catalog_slugs = _catalog_by_slug(catalog)
    cells = {cell["id"]: cell for cell in cams["cells"]}
    variables = {item["id"]: item for item in cams["variables"]}
    run_at = _canonical_second(cams.get("run_utc"), "CAMS run")
    generated_at = _canonical_second(cams.get("generated_at_utc"), "CAMS generation")
    documents: dict[str, bytes] = {}
    pollen_documents: dict[str, bytes] = {}

    for slug, municipality in catalog_slugs.items():
        town = towns[slug]
        cell = cells[town["cell_id"]]
        hourly: list[dict[str, Any]] = []
        for index, valid_at in enumerate(cams["times_utc"]):
            values: dict[str, Any] = {}
            quality_flags: dict[str, list[str]] = {}
            for variable_id in CAMS_VARIABLE_IDS:
                values[variable_id] = cell["values"][variable_id][index]
                per_sample = (
                    cell.get("quality_flags", {})
                    .get(variable_id, {})
                    .get(str(index), [])
                )
                quality_flags[variable_id] = sorted(
                    set(variables[variable_id].get("quality_flags", []))
                    | set(per_sample or [])
                )
            hourly.append(
                {
                    "valid_at": _canonical_second(valid_at, "CAMS valid time"),
                    "values": values,
                    "quality_flags": quality_flags,
                }
            )
        payload = build_cams_payload(
            catalog=catalog,
            istat_code=municipality.istat_code,
            run_at=run_at,
            generated_at=generated_at,
            model_point={
                "lat": cell.get("lat"),
                "lon": cell.get("lon"),
                "distance_km": town.get("distance_km"),
                "grid_index": cell.get("grid_index"),
            },
            hourly=hourly,
        )
        validate_cams_payload(payload, catalog, expected_istat_code=municipality.istat_code)
        documents[municipality.istat_code] = canonical_json_bytes(payload)
        pollen_payload = build_cams_pollen_payload(
            catalog=catalog,
            istat_code=municipality.istat_code,
            run_at=run_at,
            generated_at=generated_at,
            model_point={
                "lat": cell.get("lat"),
                "lon": cell.get("lon"),
                "distance_km": town.get("distance_km"),
                "grid_index": cell.get("grid_index"),
            },
            hourly=hourly,
        )
        validate_cams_pollen_payload(
            pollen_payload,
            catalog,
            expected_istat_code=municipality.istat_code,
        )
        pollen_documents[municipality.istat_code] = canonical_json_bytes(pollen_payload)

    manifest = build_run_manifest(
        provider=CAMS_PROVIDER,
        run_at=run_at,
        generated_at=generated_at,
        catalog=catalog,
        objects=documents,
    )
    validate_run_manifest(manifest, catalog, expected_provider=CAMS_PROVIDER, object_bodies=documents)
    pollen_manifest = build_run_manifest(
        provider=CAMS_POLLEN_PROVIDER,
        run_at=run_at,
        generated_at=generated_at,
        catalog=catalog,
        objects=pollen_documents,
    )
    validate_run_manifest(
        pollen_manifest,
        catalog,
        expected_provider=CAMS_POLLEN_PROVIDER,
        object_bodies=pollen_documents,
    )
    return documents, manifest, pollen_documents, pollen_manifest, archive_summary


def materialize_snapshots(
    icon: Mapping[str, Any],
    cams: Mapping[str, Any],
    *,
    catalog: Catalog | None = None,
) -> dict[str, Any]:
    """Materialize already verified in-memory snapshots without mutating them."""

    if icon.get("catalog_sha256") != cams.get("catalog_sha256"):
        raise SnapshotMaterializationError("ICON and CAMS source catalogs differ")
    if catalog is None:
        authoritative = load_catalog()
        catalog = (
            authoritative
            if icon.get("catalog_sha256") == authoritative.sha256
            else load_catalog(DEFAULT_CATALOG_PATH)
            if icon.get("catalog_sha256") == _legacy_source_catalog_sha256()
            else None
        )
        if catalog is None:
            raise SnapshotMaterializationError("snapshot catalog fingerprint is unknown")
    icon_documents, icon_manifest = materialize_icon_documents(icon, catalog)
    (
        cams_documents,
        cams_manifest,
        cams_pollen_documents,
        cams_pollen_manifest,
        cams_archive,
    ) = materialize_cams_core_documents(cams, catalog)
    return {
        "catalog": catalog,
        "icon": {"documents": icon_documents, "manifest": icon_manifest},
        "cams": {
            "documents": cams_documents,
            "manifest": cams_manifest,
            "archive_summary": cams_archive,
        },
        "cams_pollen": {
            "documents": cams_pollen_documents,
            "manifest": cams_pollen_manifest,
            "derived_from": CAMS_PROVIDER,
        },
    }


def materialize_verified_icon(
    *,
    catalog: Catalog | None = None,
    icon_archive: str | Path = DEFAULT_ICON_ARCHIVE,
    icon_report: str | Path = DEFAULT_ICON_REPORT,
) -> dict[str, Any]:
    """Verify and materialize only ICON against the selected catalog."""

    catalog = catalog or load_catalog()
    icon = load_verified_icon_snapshot(
        icon_archive=icon_archive,
        icon_report=icon_report,
    )
    documents, manifest = materialize_icon_documents(icon, catalog)
    return {
        "catalog": catalog,
        "icon": {"documents": documents, "manifest": manifest},
    }


def materialize_verified_cams(
    *,
    catalog: Catalog | None = None,
    cams_payload: str | Path = DEFAULT_CAMS_PAYLOAD,
    cams_report: str | Path = DEFAULT_CAMS_REPORT,
) -> dict[str, Any]:
    """Verify CAMS once, then materialize its full and pollen providers."""

    catalog = catalog or load_catalog()
    cams = load_verified_cams_snapshot(
        cams_payload=cams_payload,
        cams_report=cams_report,
    )
    (
        documents,
        manifest,
        pollen_documents,
        pollen_manifest,
        archive_summary,
    ) = materialize_cams_core_documents(cams, catalog)
    return {
        "catalog": catalog,
        "cams": {
            "documents": documents,
            "manifest": manifest,
            "archive_summary": archive_summary,
        },
        "cams_pollen": {
            "documents": pollen_documents,
            "manifest": pollen_manifest,
            "derived_from": CAMS_PROVIDER,
        },
    }


def materialize_verified_pilot(
    *,
    catalog: Catalog | None = None,
    icon_archive: str | Path = DEFAULT_ICON_ARCHIVE,
    icon_report: str | Path = DEFAULT_ICON_REPORT,
    cams_payload: str | Path = DEFAULT_CAMS_PAYLOAD,
    cams_report: str | Path = DEFAULT_CAMS_REPORT,
) -> dict[str, Any]:
    """Materialize both providers independently from the real local artifacts."""

    icon, cams = load_verified_snapshots(
        icon_archive=icon_archive,
        icon_report=icon_report,
        cams_payload=cams_payload,
        cams_report=cams_report,
    )
    return materialize_snapshots(icon, cams, catalog=catalog)


__all__ = [
    "SnapshotMaterializationError",
    "load_verified_cams_snapshot",
    "load_verified_icon_snapshot",
    "load_verified_snapshots",
    "materialize_cams_core_documents",
    "materialize_icon_documents",
    "materialize_snapshots",
    "materialize_verified_cams",
    "materialize_verified_icon",
    "materialize_verified_pilot",
    "validate_complete_cams_archive",
]
