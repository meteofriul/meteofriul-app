"""Resolve current Italian municipalities to official ISTAT capoluogo points.

This module is an offline, fail-closed bridge between the current national
municipality catalog and ISTAT's 2021 ``Localita puntuali`` release.  It does
not download inputs.  Callers must supply the exact reviewed source files;
their SHA-256 digests are checked before parsing.  The CLI can either audit in
memory or create a paired resolution report and approved forecast-point
artifact with create-only semantics.

The identity policy is deliberately narrow:

* use the current ISTAT code when it exists in the 2021 capoluogo rows;
* otherwise use registry column Q (the 2017--2025 code);
* otherwise accept one of seven reviewed post-2021 seat overrides.

Coordinates are transformed from EPSG:32632 to EPSG:4326 with pyproj and
``always_xy=True``.  pyproj is a required runtime dependency: there is no
approximate or silently substituted transformation path.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import hashlib
from io import BytesIO, StringIO
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable, Mapping, Protocol, Sequence
import unicodedata
from zipfile import BadZipFile, ZipFile

try:  # pragma: no cover - direct-script fallback is exercised by the CLI
    from .municipal_seat_reconciliation import (
        MunicipalSeatReconciliationError,
        _read_xlsx_table_bytes,
    )
    from .national_catalog import (
        BOUNDARIES_REFERENCE_DATE,
        BOUNDARIES_PROJECTION_SHA256,
        BOUNDARY_COMPONENTS,
        EXPECTED_MUNICIPALITY_COUNT,
        NationalCatalogError,
        REGISTRY_REFERENCE_DATE,
        REGISTRY_SOURCE_SHA256,
        REGISTRY_SOURCE_URL,
        canonical_json_bytes,
        _BoundaryGeometry,
        _point_in_polygon,
        _read_dbf_records,
        _read_shapefile_polygons,
        validate_catalog,
    )
    from .local_pipeline.national_forecast_points import (
        build_approved_forecast_points_artifact,
        write_forecast_points_create_only,
    )
except ImportError:  # pragma: no cover
    from municipal_seat_reconciliation import (  # type: ignore
        MunicipalSeatReconciliationError,
        _read_xlsx_table_bytes,
    )
    from national_catalog import (  # type: ignore
        BOUNDARIES_REFERENCE_DATE,
        BOUNDARIES_PROJECTION_SHA256,
        BOUNDARY_COMPONENTS,
        EXPECTED_MUNICIPALITY_COUNT,
        NationalCatalogError,
        REGISTRY_REFERENCE_DATE,
        REGISTRY_SOURCE_SHA256,
        REGISTRY_SOURCE_URL,
        canonical_json_bytes,
        _BoundaryGeometry,
        _point_in_polygon,
        _read_dbf_records,
        _read_shapefile_polygons,
        validate_catalog,
    )
    from local_pipeline.national_forecast_points import (  # type: ignore
        build_approved_forecast_points_artifact,
        write_forecast_points_create_only,
    )


RESOLUTION_KIND = "meteofriul.weather.istat_capoluogo_point_resolution"
RESOLUTION_SCHEMA_VERSION = 1
RESOLUTION_POLICY_ID = "istat_localita_puntuali_capoluogo_v1"

ISTAT_AUTHORITY = "Istituto nazionale di statistica (Istat)"
LOCALITIES_DATASET = "Basi territoriali 2021 - Localita puntuali"
LOCALITIES_SOURCE_URL = (
    "https://www.istat.it/storage/cartografia/basi_territoriali/2021/"
    "LocalitaPuntuali_21.zip"
)
LOCALITIES_SOURCE_SHA256 = (
    "67ba8a957b9c1ea21ed6144cc33ec1ac3c3a0b1370ba4443452e63ae37e2b9f9"
)
LOCALITIES_REFERENCE_DATE = "2021-12-31"
LOCALITIES_CSV_BASENAME = "Localita_2021_Point.csv"
CONTAINMENT_BOUNDARIES_DATASET = (
    "Confini delle unita amministrative a fini statistici - "
    "Comuni non generalizzati 2026"
)
CONTAINMENT_BOUNDARIES_SOURCE_URL = (
    "https://www.istat.it/storage/cartografia/confini_amministrativi/"
    "non_generalizzati/2026/Limiti01012026.zip"
)
CONTAINMENT_BOUNDARIES_SOURCE_SHA256 = (
    "a9075f8d839dcb2b409099703da7bdd37cc214f8967fa7372b32305875ad046f"
)
CONTAINMENT_BOUNDARIES_BASE = "Com01012026/Com01012026_WGS84"
SOURCE_CRS = "EPSG:32632"
TARGET_CRS = "EPSG:4326"
ROUNDING_DECIMAL_PLACES = 7

EXPECTED_LOCALITY_ROWS = 69_003
EXPECTED_CAPOLUOGO_ROWS = 7_904
EXPECTED_CAPOLUOGO_TIPO_1_ROWS = 7_902
EXPECTED_CAPOLUOGO_OTHER_TIPO_ROWS = 2
EXPECTED_DIRECT_COUNT = 7_510
EXPECTED_LEGACY_COUNT = 377
EXPECTED_OVERRIDE_COUNT = 7

METHOD_DIRECT = "direct_current_istat_code_v1"
METHOD_REGISTRY_LEGACY = "registry_2017_2025_code_v1"
METHOD_REVIEWED_OVERRIDE = "reviewed_post_2021_seat_override_v1"
POINT_METHOD = "official_istat_capoluogo_v1"
POINT_QUALITY = "official_istat_capoluogo"

_REGISTRY_HEADERS = (
    "Codice Comune formato alfanumerico",
    "Denominazione (Italiana e straniera)",
    "Codice Comune formato numerico",
    "Codice Comune numerico con 107 Province (dal 2017 al 2025)",
)
_LOCALITY_HEADERS = (
    "COD_REG",
    "COD_UTS",
    "PRO_COM",
    "LOC_ID",
    "LOC",
    "TIPO_LOC",
    "NOME",
    "CENTRO_CL",
    "ALTITUDINE",
    "POP21",
    "FAM21",
    "ABI21",
    "EDI21",
    "POINT_X",
    "POINT_Y",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ISTAT_RE = re.compile(r"^\d{6}$")
_POSITIVE_INTEGER_RE = re.compile(r"^[1-9]\d*$")
_MAX_SOURCE_BYTES = 128 * 1024 * 1024
_MAX_RESOLUTION_BYTES = 128 * 1024 * 1024
_MAX_ZIP_MEMBERS = 64
_MAX_ZIP_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
_MIN_EASTING = 100_000.0
# The nationwide dataset is deliberately expressed in the single UTM zone 32N;
# eastern Italian points consequently extend well beyond the conventional zone.
_MAX_EASTING = 1_500_000.0
_MIN_NORTHING = 3_800_000.0
_MAX_NORTHING = 5_600_000.0
_MIN_LATITUDE = 35.0
_MAX_LATITUDE = 48.8
_MIN_LONGITUDE = 5.8
_MAX_LONGITUDE = 19.8


class IstatCapoluogoResolutionError(ValueError):
    """The reviewed sources cannot produce an unambiguous point set."""


@dataclass(frozen=True)
class RegistryRow:
    current_istat_code: str
    name: str
    legacy_istat_code: str


@dataclass(frozen=True)
class LocalityPoint:
    source_istat_code: str
    loc_id: str
    name: str
    tipo_loc: str
    easting: float
    northing: float


@dataclass(frozen=True)
class LocalityDataset:
    points: tuple[LocalityPoint, ...]
    total_row_count: int
    capoluogo_tipo_1_count: int
    capoluogo_other_tipo_count: int


class _PyprojTransformer(Protocol):
    def transform(self, xx: float, yy: float) -> tuple[float, float]: ...


@dataclass(frozen=True)
class TransformerRuntime:
    transformer: _PyprojTransformer
    pyproj_version: str
    proj_version: str


@dataclass(frozen=True)
class _Override:
    source_istat_code: str
    loc_id: str
    source_name: str
    authority_url: str


REVIEWED_OVERRIDES: Mapping[str, _Override] = {
    "005122": _Override(
        "005110",
        "511010001",
        "Tonengo",
        "https://comune.moransengotonengo.at.it/Portals/2075/"
        "SiscomArchivio/Statuto/statutomoransengotonengo.pdf",
    ),
    "012144": _Override(
        "012018",
        "1201810001",
        "Bregano",
        "https://comune.bardelloconmalgessoebregano.va.it/ccbdmgbn/hh/index.php",
    ),
    "013256": _Override(
        "013228",
        "1322810002",
        "Uggiate Trevano",
        "https://comune.uggiateconronago.co.it/",
    ),
    "024128": _Override(
        "024103",
        "2410310002",
        "Sovizzo",
        "https://www.comune.sovizzo.vi.it/novita/nuovi-riferimenti-del-comune-di-sovizzo/",
    ),
    "024129": _Override(
        "024071",
        "2407110003",
        "Ponte di Nanto",
        "https://bur.regione.veneto.it/BurvServices/pubblica/DettaglioLegge.aspx?id=576774",
    ),
    "025075": _Override(
        "025070",
        "2507010002",
        "Quero",
        "https://bur.regione.veneto.it/BurvServices/pubblica/DettaglioAttoEntiVari.aspx?id=590086",
    ),
    "028108": _Override(
        "028022",
        "2802210002",
        "Carceri",
        "https://bur.regione.veneto.it/BurvServices/pubblica/DettaglioAttoEntiVari.aspx?id=537642",
    ),
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _required_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise IstatCapoluogoResolutionError(f"{label} is not a SHA-256 digest")
    return value


def _normalise_istat_code(value: Any, label: str, *, allow_empty: bool = False) -> str:
    text = _clean_text(value)
    if allow_empty and not text:
        return ""
    if re.fullmatch(r"\d{1,6}(?:\.0+)?", text) is None:
        raise IstatCapoluogoResolutionError(f"{label} is not an ISTAT code")
    code = text.split(".", 1)[0].zfill(6)
    if _ISTAT_RE.fullmatch(code) is None:
        raise IstatCapoluogoResolutionError(f"{label} is not an ISTAT code")
    return code


def _decimal_comma(value: Any, label: str) -> float:
    text = _clean_text(value)
    if not text or ("," in text and "." in text):
        raise IstatCapoluogoResolutionError(f"{label} is not a decimal-comma number")
    try:
        result = float(text.replace(",", "."))
    except ValueError as error:
        raise IstatCapoluogoResolutionError(
            f"{label} is not a decimal-comma number"
        ) from error
    if not math.isfinite(result):
        raise IstatCapoluogoResolutionError(f"{label} is non-finite")
    return result


def _read_snapshot(path: str | Path) -> bytes:
    try:
        with Path(path).open("rb") as stream:
            body = stream.read(_MAX_SOURCE_BYTES + 1)
    except OSError as error:
        raise IstatCapoluogoResolutionError(f"source is unreadable: {path}") from error
    if len(body) > _MAX_SOURCE_BYTES:
        raise IstatCapoluogoResolutionError("source exceeds the safe size limit")
    return body


def parse_registry_xlsx_bytes(body: bytes) -> tuple[RegistryRow, ...]:
    """Parse current code/name and the reviewed 2017--2025 code (column Q)."""

    if not isinstance(body, bytes) or not body:
        raise IstatCapoluogoResolutionError("ISTAT registry XLSX is empty")
    try:
        rows = _read_xlsx_table_bytes(
            body,
            required_headers=_REGISTRY_HEADERS,
            selected_headers=_REGISTRY_HEADERS,
        )
    except MunicipalSeatReconciliationError as error:
        raise IstatCapoluogoResolutionError(
            "ISTAT registry XLSX is invalid"
        ) from error

    output: list[RegistryRow] = []
    seen_current: set[str] = set()
    seen_legacy: set[str] = set()
    for row in rows:
        alpha = _normalise_istat_code(
            row.get("codice_comune_formato_alfanumerico"),
            "registry column E code",
            allow_empty=True,
        )
        numeric = _normalise_istat_code(
            row.get("codice_comune_formato_numerico"),
            "registry column P code",
            allow_empty=True,
        )
        if not alpha and not numeric:
            continue
        if alpha != numeric:
            raise IstatCapoluogoResolutionError(
                "registry columns E and P identify different municipalities"
            )
        legacy = _normalise_istat_code(
            row.get("codice_comune_numerico_con_107_province_dal_2017_al_2025"),
            "registry column Q code",
        )
        name = _clean_text(row.get("denominazione_italiana_e_straniera"))
        if not name:
            raise IstatCapoluogoResolutionError(
                f"registry municipality {numeric} has no name"
            )
        if numeric in seen_current:
            raise IstatCapoluogoResolutionError(
                f"registry current ISTAT code is duplicated: {numeric}"
            )
        if legacy in seen_legacy:
            raise IstatCapoluogoResolutionError(
                f"registry column Q code is duplicated: {legacy}"
            )
        output.append(RegistryRow(numeric, name, legacy))
        seen_current.add(numeric)
        seen_legacy.add(legacy)
    if not output:
        raise IstatCapoluogoResolutionError("ISTAT registry has no municipality rows")
    return tuple(sorted(output, key=lambda item: item.current_istat_code))


# Backwards-compatible descriptive alias used by early experiments.
parse_capoluogo_xlsx_bytes = parse_registry_xlsx_bytes


def _guard_locality_archive(archive: ZipFile) -> str:
    members = archive.infolist()
    if not members or len(members) > _MAX_ZIP_MEMBERS:
        raise IstatCapoluogoResolutionError(
            "ISTAT locality ZIP has an invalid member count"
        )
    names = [member.filename for member in members]
    if len(names) != len(set(names)):
        raise IstatCapoluogoResolutionError(
            "ISTAT locality ZIP contains duplicate members"
        )
    if sum(member.file_size for member in members) > _MAX_ZIP_UNCOMPRESSED_BYTES:
        raise IstatCapoluogoResolutionError(
            "ISTAT locality ZIP exceeds the safe uncompressed limit"
        )
    candidates: list[str] = []
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts or member.flag_bits & 0x1:
            raise IstatCapoluogoResolutionError(
                "ISTAT locality ZIP contains an unsafe member"
            )
        if path.name == LOCALITIES_CSV_BASENAME:
            candidates.append(member.filename)
    if len(candidates) != 1:
        raise IstatCapoluogoResolutionError(
            f"ISTAT locality ZIP must contain exactly one {LOCALITIES_CSV_BASENAME}"
        )
    return candidates[0]


def parse_coordinate_zip_bytes(
    body: bytes,
    *,
    expected_total_rows: int | None = None,
    expected_capoluogo_rows: int | None = None,
) -> LocalityDataset:
    """Parse the cp1252, tab-delimited locality CSV and retain CENTRO_CL=1."""

    if not isinstance(body, bytes) or not body:
        raise IstatCapoluogoResolutionError("ISTAT locality ZIP is empty")
    try:
        with ZipFile(BytesIO(body)) as archive:
            member = _guard_locality_archive(archive)
            csv_body = archive.read(member)
    except (BadZipFile, KeyError, OSError, RuntimeError) as error:
        raise IstatCapoluogoResolutionError(
            "ISTAT locality ZIP is unreadable"
        ) from error
    try:
        text = csv_body.decode("cp1252", errors="strict")
    except UnicodeDecodeError as error:
        raise IstatCapoluogoResolutionError(
            "ISTAT locality CSV is not valid cp1252"
        ) from error

    reader = csv.DictReader(StringIO(text, newline=""), delimiter="\t", strict=True)
    if reader.fieldnames != list(_LOCALITY_HEADERS):
        raise IstatCapoluogoResolutionError(
            "ISTAT locality CSV headers differ from the reviewed schema"
        )

    points: list[LocalityPoint] = []
    seen_all_loc_ids: set[str] = set()
    seen_source_codes: set[str] = set()
    total = 0
    tipo_1 = 0
    tipo_other = 0
    try:
        for raw in reader:
            total += 1
            if None in raw or any(value is None for value in raw.values()):
                raise IstatCapoluogoResolutionError(
                    "ISTAT locality CSV row has the wrong field count"
                )
            loc_id = _clean_text(raw["LOC_ID"])
            if _POSITIVE_INTEGER_RE.fullmatch(loc_id) is None:
                raise IstatCapoluogoResolutionError(
                    f"ISTAT locality LOC_ID is invalid: {loc_id!r}"
                )
            if loc_id in seen_all_loc_ids:
                raise IstatCapoluogoResolutionError(
                    f"ISTAT locality LOC_ID is duplicated: {loc_id}"
                )
            seen_all_loc_ids.add(loc_id)
            centro_cl = _clean_text(raw["CENTRO_CL"])
            if centro_cl not in {"0", "1"}:
                raise IstatCapoluogoResolutionError(
                    f"ISTAT locality CENTRO_CL is invalid: {centro_cl!r}"
                )
            if centro_cl != "1":
                continue
            source_code = _normalise_istat_code(raw["PRO_COM"], "locality PRO_COM")
            if source_code in seen_source_codes:
                raise IstatCapoluogoResolutionError(
                    f"ISTAT capoluogo PRO_COM is duplicated: {source_code}"
                )
            name = _clean_text(raw["NOME"])
            tipo_loc = _clean_text(raw["TIPO_LOC"])
            if not name or not tipo_loc:
                raise IstatCapoluogoResolutionError(
                    f"ISTAT capoluogo {source_code} has incomplete identity"
                )
            easting = _decimal_comma(raw["POINT_X"], f"{source_code} POINT_X")
            northing = _decimal_comma(raw["POINT_Y"], f"{source_code} POINT_Y")
            if not _MIN_EASTING <= easting <= _MAX_EASTING:
                raise IstatCapoluogoResolutionError(
                    f"ISTAT capoluogo {source_code} easting is implausible"
                )
            if not _MIN_NORTHING <= northing <= _MAX_NORTHING:
                raise IstatCapoluogoResolutionError(
                    f"ISTAT capoluogo {source_code} northing is implausible"
                )
            points.append(
                LocalityPoint(source_code, loc_id, name, tipo_loc, easting, northing)
            )
            seen_source_codes.add(source_code)
            if tipo_loc == "1":
                tipo_1 += 1
            else:
                tipo_other += 1
    except csv.Error as error:
        raise IstatCapoluogoResolutionError(
            "ISTAT locality CSV syntax is invalid"
        ) from error

    if expected_total_rows is not None and total != expected_total_rows:
        raise IstatCapoluogoResolutionError(
            f"ISTAT locality row count is {total}, expected {expected_total_rows}"
        )
    if expected_capoluogo_rows is not None and len(points) != expected_capoluogo_rows:
        raise IstatCapoluogoResolutionError(
            "ISTAT capoluogo row count is "
            f"{len(points)}, expected {expected_capoluogo_rows}"
        )
    if not points:
        raise IstatCapoluogoResolutionError("ISTAT locality CSV has no capoluogo rows")
    return LocalityDataset(tuple(points), total, tipo_1, tipo_other)


def read_boundary_geometry_zip(
    source: str | Path | BytesIO,
) -> dict[str, _BoundaryGeometry]:
    """Read the reviewed non-generalized 2026 municipality geometries.

    ``national_catalog.read_boundary_geometry_zip`` intentionally pins the
    generalized catalog source and its ``*_g`` member names.  Containment is a
    separate evidentiary purpose: this reader reuses the same hardened DBF and
    shapefile decoders but pins the official non-generalized member set.
    """

    try:
        with ZipFile(source) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if (
                not members
                or len(members) > _MAX_ZIP_MEMBERS
                or len(names) != len(set(names))
                or sum(member.file_size for member in members)
                > _MAX_ZIP_UNCOMPRESSED_BYTES
            ):
                raise IstatCapoluogoResolutionError(
                    "ISTAT boundary ZIP archive structure is invalid"
                )
            for member in members:
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts or member.flag_bits & 0x1:
                    raise IstatCapoluogoResolutionError(
                        "ISTAT boundary ZIP contains an unsafe member"
                    )
            projection = archive.read(CONTAINMENT_BOUNDARIES_BASE + ".prj")
            if _sha256(projection) != BOUNDARIES_PROJECTION_SHA256:
                raise IstatCapoluogoResolutionError(
                    "ISTAT boundary projection differs from reviewed EPSG:32632"
                )
            identities = _read_dbf_records(
                archive.read(CONTAINMENT_BOUNDARIES_BASE + ".dbf")
            )
            geometries = _read_shapefile_polygons(
                archive.read(CONTAINMENT_BOUNDARIES_BASE + ".shp")
            )
    except IstatCapoluogoResolutionError:
        raise
    except (BadZipFile, KeyError, OSError, RuntimeError, NationalCatalogError) as error:
        raise IstatCapoluogoResolutionError(
            "ISTAT non-generalized boundary ZIP is unreadable"
        ) from error
    if len(identities) != len(geometries):
        raise IstatCapoluogoResolutionError(
            "ISTAT boundary geometry and identity counts differ"
        )
    result: dict[str, _BoundaryGeometry] = {}
    for identity, rings in zip(identities, geometries):
        code = _clean_text(identity.get("PRO_COM_T"))
        if _ISTAT_RE.fullmatch(code) is None or code in result or not rings:
            raise IstatCapoluogoResolutionError(
                "ISTAT boundary geometry identity is invalid or duplicated"
            )
        result[code] = _BoundaryGeometry(identity=identity, rings=rings)
    if not result:
        raise IstatCapoluogoResolutionError(
            "ISTAT boundary ZIP has no municipality geometries"
        )
    return result


def _validate_catalog_identity(
    catalog: Mapping[str, Any], *, expected_count: int | None
) -> tuple[dict[str, str], ...]:
    if not isinstance(catalog, Mapping):
        raise IstatCapoluogoResolutionError("national catalog must be an object")
    if expected_count == EXPECTED_MUNICIPALITY_COUNT:
        try:
            validate_catalog(catalog)
        except NationalCatalogError as error:
            raise IstatCapoluogoResolutionError("national catalog is invalid") from error
    municipalities = catalog.get("municipalities")
    count = catalog.get("municipality_count")
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or not isinstance(municipalities, list)
        or len(municipalities) != count
        or (expected_count is not None and count != expected_count)
    ):
        raise IstatCapoluogoResolutionError("national catalog count is invalid")
    catalog_sha = _required_sha256(catalog.get("catalog_sha256"), "catalog SHA-256")
    content = dict(catalog)
    content.pop("catalog_sha256", None)
    if _sha256(canonical_json_bytes(content)) != catalog_sha:
        raise IstatCapoluogoResolutionError("national catalog SHA-256 mismatch")

    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in municipalities:
        if not isinstance(item, Mapping):
            raise IstatCapoluogoResolutionError("catalog municipality is invalid")
        code = _normalise_istat_code(item.get("istat_code"), "catalog ISTAT code")
        name = _clean_text(item.get("name"))
        if not name or code in seen:
            raise IstatCapoluogoResolutionError(
                "catalog municipality identity is incomplete or duplicated"
            )
        seen.add(code)
        output.append({"istat_code": code, "name": name})
    codes = sorted(seen)
    observed_codes_sha = _sha256(canonical_json_bytes(codes))
    supplied_codes_sha = catalog.get("municipality_codes_sha256")
    if supplied_codes_sha is not None and supplied_codes_sha != observed_codes_sha:
        raise IstatCapoluogoResolutionError(
            "national catalog municipality-code SHA-256 mismatch"
        )
    return tuple(sorted(output, key=lambda item: item["istat_code"]))


def _create_transformer() -> TransformerRuntime:
    """Create the sole approved CRS transformer, failing closed if unavailable."""

    try:
        import pyproj  # type: ignore
    except (ImportError, ModuleNotFoundError) as error:
        raise IstatCapoluogoResolutionError(
            "pyproj is required for EPSG:32632 to EPSG:4326 transformation"
        ) from error
    try:
        transformer = pyproj.Transformer.from_crs(32632, 4326, always_xy=True)
        pyproj_version = _clean_text(pyproj.__version__)
        proj_version = _clean_text(pyproj.proj_version_str)
    except Exception as error:  # pyproj exposes backend-specific exception types
        raise IstatCapoluogoResolutionError(
            "pyproj could not initialize the reviewed CRS transformation"
        ) from error
    if not pyproj_version or not proj_version:
        raise IstatCapoluogoResolutionError("pyproj runtime version is unavailable")
    return TransformerRuntime(transformer, pyproj_version, proj_version)


def _runtime(
    transformer: _PyprojTransformer | TransformerRuntime | None,
    *,
    pyproj_version: str | None,
    proj_version: str | None,
) -> TransformerRuntime:
    if transformer is None:
        if pyproj_version is not None or proj_version is not None:
            raise IstatCapoluogoResolutionError(
                "runtime versions cannot override the installed pyproj runtime"
            )
        return _create_transformer()
    if isinstance(transformer, TransformerRuntime):
        if pyproj_version is not None or proj_version is not None:
            raise IstatCapoluogoResolutionError(
                "runtime versions were supplied twice"
            )
        return transformer
    if not callable(getattr(transformer, "transform", None)):
        raise IstatCapoluogoResolutionError("coordinate transformer has no transform method")
    pyproj_version = _clean_text(pyproj_version)
    proj_version = _clean_text(proj_version)
    if not pyproj_version or not proj_version:
        raise IstatCapoluogoResolutionError(
            "injected transformer requires pyproj_version and proj_version evidence"
        )
    return TransformerRuntime(transformer, pyproj_version, proj_version)


def _transform_point(
    point: LocalityPoint, runtime: TransformerRuntime
) -> tuple[float, float]:
    try:
        longitude, latitude = runtime.transformer.transform(
            point.easting, point.northing
        )
        longitude = float(longitude)
        latitude = float(latitude)
    except Exception as error:
        raise IstatCapoluogoResolutionError(
            f"coordinate transformation failed for LOC_ID {point.loc_id}"
        ) from error
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise IstatCapoluogoResolutionError(
            f"coordinate transformation is non-finite for LOC_ID {point.loc_id}"
        )
    latitude = round(latitude, ROUNDING_DECIMAL_PLACES)
    longitude = round(longitude, ROUNDING_DECIMAL_PLACES)
    if not _MIN_LATITUDE <= latitude <= _MAX_LATITUDE:
        raise IstatCapoluogoResolutionError(
            f"latitude is outside Italy bounds for LOC_ID {point.loc_id}"
        )
    if not _MIN_LONGITUDE <= longitude <= _MAX_LONGITUDE:
        raise IstatCapoluogoResolutionError(
            f"longitude is outside Italy bounds for LOC_ID {point.loc_id}"
        )
    return latitude, longitude


def _boundary_rings(value: Any, code: str) -> Sequence[Sequence[tuple[float, float]]]:
    rings = getattr(value, "rings", None)
    if rings is None and isinstance(value, Mapping):
        rings = value.get("rings")
    if not isinstance(rings, (tuple, list)) or not rings:
        raise IstatCapoluogoResolutionError(
            f"boundary geometry is invalid for component {code}"
        )
    return rings


def _municipality_boundary_rings(
    current_istat_code: str,
    boundary_geometries: Mapping[str, Any],
) -> tuple[Sequence[tuple[float, float]], ...]:
    component_codes = BOUNDARY_COMPONENTS.get(
        current_istat_code, (current_istat_code,)
    )
    combined: list[Sequence[tuple[float, float]]] = []
    for component_code in component_codes:
        if component_code not in boundary_geometries:
            raise IstatCapoluogoResolutionError(
                f"boundary component {component_code} is absent for municipality "
                f"{current_istat_code}"
            )
        combined.extend(_boundary_rings(boundary_geometries[component_code], component_code))
    return tuple(combined)


def _normalise_registry_rows(
    rows: Iterable[RegistryRow | Mapping[str, Any]],
) -> tuple[RegistryRow, ...]:
    output: list[RegistryRow] = []
    seen_current: set[str] = set()
    seen_legacy: set[str] = set()
    for raw in rows:
        if isinstance(raw, RegistryRow):
            item = raw
        elif isinstance(raw, Mapping):
            item = RegistryRow(
                _normalise_istat_code(
                    raw.get("current_istat_code", raw.get("istat_code")),
                    "registry current ISTAT code",
                ),
                _clean_text(raw.get("name")),
                _normalise_istat_code(
                    raw.get("legacy_istat_code", raw.get("legacy_code")),
                    "registry legacy ISTAT code",
                ),
            )
        else:
            raise IstatCapoluogoResolutionError("registry row is invalid")
        if not item.name or item.current_istat_code in seen_current:
            raise IstatCapoluogoResolutionError(
                "registry identity is incomplete or duplicated"
            )
        if item.legacy_istat_code in seen_legacy:
            raise IstatCapoluogoResolutionError("registry legacy code is duplicated")
        seen_current.add(item.current_istat_code)
        seen_legacy.add(item.legacy_istat_code)
        output.append(item)
    return tuple(sorted(output, key=lambda item: item.current_istat_code))


def _normalise_locality_rows(
    rows: LocalityDataset | Iterable[LocalityPoint | Mapping[str, Any]],
) -> tuple[LocalityPoint, ...]:
    values = rows.points if isinstance(rows, LocalityDataset) else rows
    output: list[LocalityPoint] = []
    seen_codes: set[str] = set()
    seen_loc_ids: set[str] = set()
    for raw in values:
        if isinstance(raw, LocalityPoint):
            item = raw
        elif isinstance(raw, Mapping):
            item = LocalityPoint(
                _normalise_istat_code(
                    raw.get("source_istat_code", raw.get("pro_com")),
                    "locality source ISTAT code",
                ),
                _clean_text(raw.get("loc_id")),
                _clean_text(raw.get("name")),
                _clean_text(raw.get("tipo_loc", "1")),
                float(raw.get("easting")),
                float(raw.get("northing")),
            )
        else:
            raise IstatCapoluogoResolutionError("locality row is invalid")
        if (
            not item.name
            or _POSITIVE_INTEGER_RE.fullmatch(item.loc_id) is None
            or item.source_istat_code in seen_codes
            or item.loc_id in seen_loc_ids
            or not math.isfinite(item.easting)
            or not math.isfinite(item.northing)
        ):
            raise IstatCapoluogoResolutionError(
                "locality point identity or coordinates are invalid or duplicated"
            )
        output.append(item)
        seen_codes.add(item.source_istat_code)
        seen_loc_ids.add(item.loc_id)
    return tuple(sorted(output, key=lambda item: item.source_istat_code))


def resolve_istat_capoluogo_points(
    catalog: Mapping[str, Any],
    registry_rows: Iterable[RegistryRow | Mapping[str, Any]],
    coordinate_rows: LocalityDataset | Iterable[LocalityPoint | Mapping[str, Any]],
    *,
    boundary_geometries: Mapping[str, Any],
    transformer: _PyprojTransformer | TransformerRuntime | None = None,
    pyproj_version: str | None = None,
    proj_version: str | None = None,
    catalog_file_sha256: str | None = None,
    registry_sha256: str = REGISTRY_SOURCE_SHA256,
    localities_sha256: str = LOCALITIES_SOURCE_SHA256,
    boundaries_sha256: str = CONTAINMENT_BOUNDARIES_SOURCE_SHA256,
    registry_url: str = REGISTRY_SOURCE_URL,
    localities_url: str = LOCALITIES_SOURCE_URL,
    boundaries_url: str = CONTAINMENT_BOUNDARIES_SOURCE_URL,
    reference_date: str = LOCALITIES_REFERENCE_DATE,
    expected_count: int | None = None,
    enforce_official_distribution: bool = False,
) -> dict[str, Any]:
    """Resolve rows into an in-memory, evidence-rich point document."""

    catalog_rows = _validate_catalog_identity(catalog, expected_count=expected_count)
    registry = _normalise_registry_rows(registry_rows)
    localities = _normalise_locality_rows(coordinate_rows)
    runtime = _runtime(
        transformer, pyproj_version=pyproj_version, proj_version=proj_version
    )
    registry_sha256 = _required_sha256(registry_sha256, "registry SHA-256")
    localities_sha256 = _required_sha256(localities_sha256, "localities SHA-256")
    boundaries_sha256 = _required_sha256(boundaries_sha256, "boundaries SHA-256")
    if catalog_file_sha256 is None:
        catalog_file_sha256 = _sha256(canonical_json_bytes(catalog))
    catalog_file_sha256 = _required_sha256(
        catalog_file_sha256, "catalog file SHA-256"
    )
    catalog_boundary_sha256: str | None = None
    catalog_sources = catalog.get("sources")
    if isinstance(catalog_sources, Mapping):
        catalog_boundaries = catalog_sources.get("boundaries")
        if isinstance(catalog_boundaries, Mapping):
            candidate = catalog_boundaries.get("sha256")
            if isinstance(candidate, str) and _SHA256_RE.fullmatch(candidate):
                catalog_boundary_sha256 = candidate

    catalog_by_code = {row["istat_code"]: row for row in catalog_rows}
    registry_by_code = {row.current_istat_code: row for row in registry}
    locality_by_code = {row.source_istat_code: row for row in localities}
    if not isinstance(boundary_geometries, Mapping):
        raise IstatCapoluogoResolutionError("boundary geometries must be a mapping")
    if set(registry_by_code) != set(catalog_by_code):
        raise IstatCapoluogoResolutionError(
            "registry codes do not exactly cover the national catalog"
        )
    for code, catalog_row in catalog_by_code.items():
        if registry_by_code[code].name != catalog_row["name"]:
            raise IstatCapoluogoResolutionError(
                f"registry/catalog name mismatch for municipality {code}"
            )

    policy = {
        "boundary_containment": {
            "boundary_components": {
                code: list(components)
                for code, components in sorted(BOUNDARY_COMPONENTS.items())
                if code in catalog_by_code
            },
            "checked_point_count": len(catalog_by_code),
            "coordinate_reference_system": SOURCE_CRS,
            "dataset_sha256": boundaries_sha256,
            "result": "all_inside_current_municipality",
            "url": boundaries_url,
        },
        "coordinate_transformation": {
            "always_xy": True,
            "proj_version": runtime.proj_version,
            "pyproj_version": runtime.pyproj_version,
            "rounding_decimal_places": ROUNDING_DECIMAL_PLACES,
            "source_crs": SOURCE_CRS,
            "target_crs": TARGET_CRS,
        },
        "id": RESOLUTION_POLICY_ID,
        "mapping_priority": [
            METHOD_DIRECT,
            METHOD_REGISTRY_LEGACY,
            METHOD_REVIEWED_OVERRIDE,
        ],
        "overrides": {
            code: {
                "authority_url": override.authority_url,
                "loc_id": override.loc_id,
                "source_istat_code": override.source_istat_code,
                "source_name": override.source_name,
            }
            for code, override in sorted(REVIEWED_OVERRIDES.items())
        },
        "selection": {"field": "CENTRO_CL", "value": "1"},
    }
    policy_sha256 = _sha256(canonical_json_bytes(policy))
    source_manifest = {
        "catalog": {
            "boundary_sha256": catalog_boundary_sha256,
            "catalog_sha256": catalog["catalog_sha256"],
            "file_sha256": catalog_file_sha256,
        },
        "current_registry": {
            "reference_date": REGISTRY_REFERENCE_DATE,
            "sha256": registry_sha256,
            "url": registry_url,
        },
        "municipality_boundaries": {
            "dataset": CONTAINMENT_BOUNDARIES_DATASET,
            "reference_date": BOUNDARIES_REFERENCE_DATE,
            "sha256": boundaries_sha256,
            "source_crs": SOURCE_CRS,
            "url": boundaries_url,
        },
        "localities": {
            "dataset": LOCALITIES_DATASET,
            "reference_date": reference_date,
            "sha256": localities_sha256,
            "source_crs": SOURCE_CRS,
            "url": localities_url,
        },
    }
    source_manifest_sha256 = _sha256(canonical_json_bytes(source_manifest))

    records: list[dict[str, Any]] = []
    method_counts: Counter[str] = Counter()
    selected_loc_ids: set[str] = set()
    for code in sorted(catalog_by_code):
        registry_row = registry_by_code[code]
        override_url: str | None = None
        if code in locality_by_code:
            point = locality_by_code[code]
            mapping_method = METHOD_DIRECT
        elif (
            registry_row.legacy_istat_code != code
            and registry_row.legacy_istat_code in locality_by_code
        ):
            point = locality_by_code[registry_row.legacy_istat_code]
            mapping_method = METHOD_REGISTRY_LEGACY
        elif code in REVIEWED_OVERRIDES:
            reviewed = REVIEWED_OVERRIDES[code]
            try:
                point = locality_by_code[reviewed.source_istat_code]
            except KeyError as error:
                raise IstatCapoluogoResolutionError(
                    f"reviewed override source is absent for municipality {code}"
                ) from error
            if point.loc_id != reviewed.loc_id or point.name != reviewed.source_name:
                raise IstatCapoluogoResolutionError(
                    f"reviewed override evidence differs for municipality {code}"
                )
            mapping_method = METHOD_REVIEWED_OVERRIDE
            override_url = reviewed.authority_url
        else:
            raise IstatCapoluogoResolutionError(
                f"municipality {code} has no reviewed ISTAT capoluogo mapping"
            )
        if point.loc_id in selected_loc_ids:
            raise IstatCapoluogoResolutionError(
                f"resolved LOC_ID is reused: {point.loc_id}"
            )
        selected_loc_ids.add(point.loc_id)
        boundary_rings = _municipality_boundary_rings(code, boundary_geometries)
        if not _point_in_polygon(point.easting, point.northing, boundary_rings):
            raise IstatCapoluogoResolutionError(
                f"LOC_ID {point.loc_id} lies outside current municipality {code}"
            )
        latitude, longitude = _transform_point(point, runtime)
        source = {
            "authority": ISTAT_AUTHORITY,
            "current_istat_code": code,
            "dataset": LOCALITIES_DATASET,
            "dataset_sha256": localities_sha256,
            "loc_id": point.loc_id,
            "mapping_method": mapping_method,
            "reference_date": reference_date,
            "source_istat_code": point.source_istat_code,
            "source_crs": SOURCE_CRS,
            "url": localities_url,
        }
        evidence = {
            "boundary_component_codes": list(
                BOUNDARY_COMPONENTS.get(code, (code,))
            ),
            "boundaries_sha256": boundaries_sha256,
            "boundaries_url": boundaries_url,
            "current_istat_code": code,
            "localities_sha256": localities_sha256,
            "localities_url": localities_url,
            "loc_id": point.loc_id,
            "mapping_method": mapping_method,
            "override_authority_url": override_url,
            "policy_id": RESOLUTION_POLICY_ID,
            "registry_legacy_istat_code": registry_row.legacy_istat_code,
            "registry_sha256": registry_sha256,
            "registry_url": registry_url,
            "selection_field": "CENTRO_CL",
            "selection_value": "1",
            "source_istat_code": point.source_istat_code,
            "source_locality_name": point.name,
            "source_locality_type": point.tipo_loc,
        }
        records.append(
            {
                "evidence": evidence,
                "istat_code": code,
                "latitude": latitude,
                "longitude": longitude,
                "method": POINT_METHOD,
                "name": catalog_by_code[code]["name"],
                "quality": POINT_QUALITY,
                "source": source,
            }
        )
        method_counts[mapping_method] += 1

    if len(records) != len(catalog_by_code):
        raise IstatCapoluogoResolutionError("resolved point count is incomplete")
    if enforce_official_distribution:
        expected_distribution = {
            METHOD_DIRECT: EXPECTED_DIRECT_COUNT,
            METHOD_REGISTRY_LEGACY: EXPECTED_LEGACY_COUNT,
            METHOD_REVIEWED_OVERRIDE: EXPECTED_OVERRIDE_COUNT,
        }
        if dict(method_counts) != expected_distribution:
            raise IstatCapoluogoResolutionError(
                "mapping distribution differs from the reviewed 7510/377/7 policy"
            )

    summary = {
        "mapping_method_counts": {
            method: method_counts[method]
            for method in (METHOD_DIRECT, METHOD_REGISTRY_LEGACY, METHOD_REVIEWED_OVERRIDE)
        },
        "point_count": len(records),
        "boundary_containment_checked_count": len(records),
        "unique_loc_id_count": len(selected_loc_ids),
    }
    document: dict[str, Any] = {
        "catalog_file_sha256": catalog_file_sha256,
        "catalog_sha256": catalog["catalog_sha256"],
        "kind": RESOLUTION_KIND,
        "municipality_count": len(records),
        "records": records,
        "records_sha256": _sha256(canonical_json_bytes(records)),
        "resolution_policy": policy,
        "resolution_policy_sha256": policy_sha256,
        "schema_version": RESOLUTION_SCHEMA_VERSION,
        "source_manifest": source_manifest,
        "source_manifest_sha256": source_manifest_sha256,
        "summary": summary,
    }
    document["resolution_sha256"] = _sha256(canonical_json_bytes(document))
    validate_resolution_document(document)
    return document


def forecast_point_records(document: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return only the exact fields accepted by national_forecast_points."""

    records = document.get("records")
    if not isinstance(records, list):
        raise IstatCapoluogoResolutionError("resolution document has no records")
    point_keys = (
        "istat_code",
        "latitude",
        "longitude",
        "method",
        "quality",
        "source",
    )
    output: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping) or any(key not in record for key in point_keys):
            raise IstatCapoluogoResolutionError("resolution record is incomplete")
        output.append({key: record[key] for key in point_keys})
    return tuple(output)


def validate_resolution_document(document: Mapping[str, Any]) -> None:
    """Validate identity, ordering and every self-hash in a resolution document."""

    expected_keys = {
        "catalog_file_sha256",
        "catalog_sha256",
        "kind",
        "municipality_count",
        "records",
        "records_sha256",
        "resolution_policy",
        "resolution_policy_sha256",
        "resolution_sha256",
        "schema_version",
        "source_manifest",
        "source_manifest_sha256",
        "summary",
    }
    if not isinstance(document, Mapping) or set(document) != expected_keys:
        raise IstatCapoluogoResolutionError(
            "resolution document has missing or extra fields"
        )
    if (
        document.get("kind") != RESOLUTION_KIND
        or document.get("schema_version") != RESOLUTION_SCHEMA_VERSION
    ):
        raise IstatCapoluogoResolutionError("resolution document identity is invalid")
    for field in (
        "catalog_file_sha256",
        "catalog_sha256",
        "records_sha256",
        "resolution_policy_sha256",
        "resolution_sha256",
        "source_manifest_sha256",
    ):
        _required_sha256(document.get(field), field.replace("_", " "))
    count = document.get("municipality_count")
    records = document.get("records")
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or count < 1
        or not isinstance(records, list)
        or len(records) != count
    ):
        raise IstatCapoluogoResolutionError("resolution record count is invalid")
    codes: list[str] = []
    for record in records:
        if not isinstance(record, Mapping) or set(record) != {
            "evidence",
            "istat_code",
            "latitude",
            "longitude",
            "method",
            "name",
            "quality",
            "source",
        }:
            raise IstatCapoluogoResolutionError("resolution record schema is invalid")
        code = record.get("istat_code")
        if not isinstance(code, str) or _ISTAT_RE.fullmatch(code) is None:
            raise IstatCapoluogoResolutionError("resolution ISTAT code is invalid")
        if record.get("method") != POINT_METHOD or record.get("quality") != POINT_QUALITY:
            raise IstatCapoluogoResolutionError("resolution point classification is invalid")
        source = record.get("source")
        if not isinstance(source, Mapping) or set(source) != {
            "authority",
            "current_istat_code",
            "dataset",
            "dataset_sha256",
            "loc_id",
            "mapping_method",
            "reference_date",
            "source_istat_code",
            "source_crs",
            "url",
        }:
            raise IstatCapoluogoResolutionError("resolution source schema is invalid")
        if source.get("current_istat_code") != code:
            raise IstatCapoluogoResolutionError("resolution source binding is invalid")
        codes.append(code)
    if codes != sorted(set(codes)):
        raise IstatCapoluogoResolutionError(
            "resolution records must have unique sorted ISTAT codes"
        )
    if document["records_sha256"] != _sha256(canonical_json_bytes(records)):
        raise IstatCapoluogoResolutionError("resolution records SHA-256 mismatch")
    policy = document.get("resolution_policy")
    manifest = document.get("source_manifest")
    if not isinstance(policy, Mapping) or not isinstance(manifest, Mapping):
        raise IstatCapoluogoResolutionError(
            "resolution policy or source manifest is invalid"
        )
    if document["resolution_policy_sha256"] != _sha256(
        canonical_json_bytes(policy)
    ):
        raise IstatCapoluogoResolutionError("resolution policy SHA-256 mismatch")
    if document["source_manifest_sha256"] != _sha256(
        canonical_json_bytes(manifest)
    ):
        raise IstatCapoluogoResolutionError("source manifest SHA-256 mismatch")
    summary = document.get("summary")
    if (
        not isinstance(summary, Mapping)
        or summary.get("point_count") != count
        or summary.get("unique_loc_id_count") != count
        or summary.get("boundary_containment_checked_count") != count
    ):
        raise IstatCapoluogoResolutionError("resolution summary is inconsistent")
    content = dict(document)
    expected_resolution_sha256 = content.pop("resolution_sha256")
    if _sha256(canonical_json_bytes(content)) != expected_resolution_sha256:
        raise IstatCapoluogoResolutionError("resolution document SHA-256 mismatch")


def resolution_json_bytes(document: Mapping[str, Any]) -> bytes:
    validate_resolution_document(document)
    return canonical_json_bytes(document)


def load_resolution_document(path: str | Path) -> dict[str, Any]:
    try:
        with Path(path).open("rb") as stream:
            body = stream.read(_MAX_RESOLUTION_BYTES + 1)
    except OSError as error:
        raise IstatCapoluogoResolutionError(
            f"resolution document is unreadable: {path}"
        ) from error
    if len(body) > _MAX_RESOLUTION_BYTES:
        raise IstatCapoluogoResolutionError(
            "resolution document exceeds the safe size limit"
        )
    try:
        document = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IstatCapoluogoResolutionError(
            "resolution document JSON is unreadable"
        ) from error
    if not isinstance(document, dict) or canonical_json_bytes(document) != body:
        raise IstatCapoluogoResolutionError(
            "resolution document is not canonical JSON"
        )
    validate_resolution_document(document)
    return document


def write_resolution_create_only(
    path: str | Path, document: Mapping[str, Any]
) -> None:
    """Atomically create a canonical resolution document without overwriting."""

    body = resolution_json_bytes(document)
    output = Path(path)
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        created = True
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise IstatCapoluogoResolutionError(
            f"output already exists (create-only): {output}"
        ) from error
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            try:
                output.unlink()
            except OSError:
                pass
        raise


def _load_catalog_bytes(body: bytes) -> Mapping[str, Any]:
    canonical = body[:-1] if body.endswith(b"\n") else body
    if not canonical or canonical.endswith(b"\r"):
        raise IstatCapoluogoResolutionError("national catalog JSON framing is invalid")
    try:
        document = json.loads(canonical)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IstatCapoluogoResolutionError("national catalog JSON is unreadable") from error
    if not isinstance(document, Mapping) or canonical_json_bytes(document) != canonical:
        raise IstatCapoluogoResolutionError("national catalog JSON is not canonical")
    return document


def build_from_paths(
    catalog_path: str | Path,
    registry_path: str | Path,
    localities_path: str | Path,
    boundaries_path: str | Path,
    *,
    transformer: _PyprojTransformer | TransformerRuntime | None = None,
    pyproj_version: str | None = None,
    proj_version: str | None = None,
    expected_registry_sha256: str = REGISTRY_SOURCE_SHA256,
    expected_localities_sha256: str = LOCALITIES_SOURCE_SHA256,
    expected_boundaries_sha256: str = CONTAINMENT_BOUNDARIES_SOURCE_SHA256,
    expected_count: int = EXPECTED_MUNICIPALITY_COUNT,
    enforce_official_distribution: bool = True,
    expected_total_locality_rows: int = EXPECTED_LOCALITY_ROWS,
    expected_capoluogo_rows: int = EXPECTED_CAPOLUOGO_ROWS,
) -> dict[str, Any]:
    """Hash, parse and resolve immutable source snapshots without writing output."""

    catalog_body = _read_snapshot(catalog_path)
    registry_body = _read_snapshot(registry_path)
    localities_body = _read_snapshot(localities_path)
    boundaries_body = _read_snapshot(boundaries_path)
    observed_registry_sha256 = _sha256(registry_body)
    observed_localities_sha256 = _sha256(localities_body)
    observed_boundaries_sha256 = _sha256(boundaries_body)
    if observed_registry_sha256 != _required_sha256(
        expected_registry_sha256, "expected registry SHA-256"
    ):
        raise IstatCapoluogoResolutionError(
            "ISTAT registry SHA-256 differs from the reviewed source"
        )
    if observed_localities_sha256 != _required_sha256(
        expected_localities_sha256, "expected localities SHA-256"
    ):
        raise IstatCapoluogoResolutionError(
            "ISTAT locality ZIP SHA-256 differs from the reviewed source"
        )
    if observed_boundaries_sha256 != _required_sha256(
        expected_boundaries_sha256, "expected boundaries SHA-256"
    ):
        raise IstatCapoluogoResolutionError(
            "ISTAT boundary ZIP SHA-256 differs from the reviewed source"
        )
    catalog = _load_catalog_bytes(catalog_body)
    registry = parse_registry_xlsx_bytes(registry_body)
    localities = parse_coordinate_zip_bytes(
        localities_body,
        expected_total_rows=expected_total_locality_rows,
        expected_capoluogo_rows=expected_capoluogo_rows,
    )
    try:
        boundaries = read_boundary_geometry_zip(BytesIO(boundaries_body))
    except NationalCatalogError as error:
        raise IstatCapoluogoResolutionError(
            "ISTAT boundary ZIP is invalid"
        ) from error
    if len(registry) != expected_count:
        raise IstatCapoluogoResolutionError(
            f"ISTAT registry count is {len(registry)}, expected {expected_count}"
        )
    if expected_count == EXPECTED_MUNICIPALITY_COUNT and (
        localities.capoluogo_tipo_1_count != EXPECTED_CAPOLUOGO_TIPO_1_ROWS
        or localities.capoluogo_other_tipo_count
        != EXPECTED_CAPOLUOGO_OTHER_TIPO_ROWS
    ):
        raise IstatCapoluogoResolutionError(
            "ISTAT capoluogo type distribution differs from reviewed evidence"
        )
    return resolve_istat_capoluogo_points(
        catalog,
        registry,
        localities,
        boundary_geometries=boundaries,
        transformer=transformer,
        pyproj_version=pyproj_version,
        proj_version=proj_version,
        catalog_file_sha256=_sha256(catalog_body),
        registry_sha256=observed_registry_sha256,
        localities_sha256=observed_localities_sha256,
        boundaries_sha256=observed_boundaries_sha256,
        expected_count=expected_count,
        enforce_official_distribution=enforce_official_distribution,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--localities", type=Path, required=True)
    parser.add_argument("--boundaries", type=Path, required=True)
    parser.add_argument("--resolution-output", type=Path)
    parser.add_argument("--points-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if (args.resolution_output is None) != (args.points_output is None):
        parser.error("--resolution-output and --points-output must be supplied together")
    if (
        args.resolution_output is not None
        and args.resolution_output.resolve() == args.points_output.resolve()
    ):
        parser.error("resolution and forecast-point outputs must be different files")
    if args.resolution_output is not None:
        for output in (args.resolution_output, args.points_output):
            if output.exists():
                raise IstatCapoluogoResolutionError(
                    f"output already exists (create-only): {output}"
                )
    document = build_from_paths(
        args.catalog, args.registry, args.localities, args.boundaries
    )
    points_document: Mapping[str, Any] | None = None
    if args.resolution_output is not None:
        catalog = _load_catalog_bytes(_read_snapshot(args.catalog))
        points_document = build_approved_forecast_points_artifact(
            catalog=catalog,
            points=forecast_point_records(document),
            # The point artifact remains bound to the generalized boundary
            # source embedded in the national catalog.  The independent,
            # detailed boundary used for strict seat containment remains in
            # this resolution document's source manifest.
            boundary_sha256=(
                document["source_manifest"]["catalog"]["boundary_sha256"]
                or document["source_manifest"]["municipality_boundaries"][
                    "sha256"
                ]
            ),
            source_manifest_sha256=document["source_manifest_sha256"],
            resolution_policy_sha256=document["resolution_policy_sha256"],
        )
        write_resolution_create_only(args.resolution_output, document)
        try:
            write_forecast_points_create_only(
                args.points_output, points_document, catalog=catalog
            )
        except Exception:
            # This path was created by this invocation and the paired delivery
            # is incomplete, so remove only that exact new file.
            try:
                args.resolution_output.unlink()
            except OSError:
                pass
            raise
    print(
        json.dumps(
            {
                "catalog_sha256": document["catalog_sha256"],
                "point_count": document["municipality_count"],
                "records_sha256": document["records_sha256"],
                "resolution_policy_sha256": document[
                    "resolution_policy_sha256"
                ],
                "resolution_sha256": document["resolution_sha256"],
                "source_manifest_sha256": document["source_manifest_sha256"],
                "summary": document["summary"],
                "resolution_output": (
                    str(args.resolution_output)
                    if args.resolution_output is not None
                    else None
                ),
                "points_output": (
                    str(args.points_output) if args.points_output is not None else None
                ),
                "points_artifact_sha256": (
                    points_document["artifact_sha256"]
                    if points_document is not None
                    else None
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
