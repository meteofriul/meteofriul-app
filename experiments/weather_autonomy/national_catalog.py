"""Build the authoritative municipality catalog for the national ICON pilot.

The builder intentionally uses only Python's standard library.  Its two inputs
are the current ISTAT municipality registry (XLSX) and the annual generalized
administrative boundaries (ESRI Shapefile ZIP).  The source files are not
silently downloaded: callers must supply the exact reviewed artifacts.

The 2026 boundary release predates municipality mergers made later in the
year.  ``build_catalog`` therefore accepts explicit, reviewable boundary
aliases for current municipalities.  It never guesses an association from a
similar name or a nearby coordinate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from typing import Any, Iterable, Mapping, Sequence
from xml.etree import ElementTree
from zipfile import ZipFile


EXPECTED_MUNICIPALITY_COUNT = 7_894
CATALOG_KIND = "meteofriul.weather.national_municipality_catalog"
CATALOG_SCHEMA_VERSION = 1
CATALOG_VERSION = "istat-2026-02-21-boundaries-2026-01-01-v1"
REGISTRY_REFERENCE_DATE = "2026-02-21"
BOUNDARIES_REFERENCE_DATE = "2026-01-01"
REGISTRY_SOURCE_URL = (
    "https://www.istat.it/storage/codici-unita-amministrative/"
    "Elenco-comuni-italiani.xlsx"
)
BOUNDARIES_SOURCE_URL = (
    "https://www.istat.it/storage/cartografia/confini_amministrativi/"
    "generalizzati/2026/Limiti01012026_g.zip"
)
REGISTRY_SOURCE_SHA256 = (
    "83842076860450f7e482daecea6b7a769f5f93d0bf5b0d48802b44896d7a26d5"
)
BOUNDARIES_SOURCE_SHA256 = (
    "b011a590656c3a3ebc297fba80726a376aa843b6f164641cf6a4a990021a81d6"
)
BOUNDARIES_PROJECTION_SHA256 = (
    "10a2674d7bc43a70df19daf98d0b1deb3f5222f03659e1b4d82b395c20177cb9"
)

# The annual 1 January boundary release contains three municipalities which no
# longer exist in the 21 February registry.  The current geometry is composed
# only through these reviewed administrative changes; no fuzzy name matching is
# permitted.  Montalto Pavese keeps its ISTAT identity and absorbs Lirio, while
# Castegnero Nanto receives a new identity and combines both former polygons.
BOUNDARY_COMPONENTS = {
    "018094": ("018094", "018082"),
    "024129": ("024027", "024071"),
}
EXPECTED_RETIRED_BOUNDARY_CODES = frozenset({"018082", "024027", "024071"})
EXPECTED_MISSING_BOUNDARY_CODES = frozenset({"024129"})

_ISTAT_RE = re.compile(r"^\d{6}$")
_XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# ISTAT region code -> ISO 3166-2 subdivision used by the application policy.
REGION_ISO_CODES = {
    "01": "IT-21",
    "02": "IT-23",
    "03": "IT-25",
    "04": "IT-32",
    "05": "IT-34",
    "06": "IT-36",
    "07": "IT-42",
    "08": "IT-45",
    "09": "IT-52",
    "10": "IT-55",
    "11": "IT-57",
    "12": "IT-62",
    "13": "IT-65",
    "14": "IT-67",
    "15": "IT-72",
    "16": "IT-75",
    "17": "IT-77",
    "18": "IT-78",
    "19": "IT-82",
    "20": "IT-88",
}


class NationalCatalogError(ValueError):
    """The reviewed ISTAT sources cannot produce a safe national catalog."""


@dataclass(frozen=True)
class RegistryMunicipality:
    istat_code: str
    name: str
    italian_name: str
    alternate_name: str
    region_istat: str
    region_iso: str
    region_name: str
    uts_istat: str
    province_historical_istat: str
    uts_name: str
    province_abbreviation: str
    cadastral_code: str


@dataclass(frozen=True)
class _BoundaryGeometry:
    identity: Mapping[str, str]
    rings: tuple[tuple[tuple[float, float], ...], ...]


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise NationalCatalogError("catalog is not canonical JSON data") from error


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_reviewed_source_hash(observed: str, expected: str, label: str) -> None:
    if observed != expected:
        raise NationalCatalogError(
            f"{label} SHA-256 differs from the reviewed {CATALOG_VERSION} source"
        )


def _verify_boundary_projection(archive: ZipFile) -> None:
    member = "Com01012026_g/Com01012026_g_WGS84.prj"
    try:
        projection = archive.read(member)
    except KeyError as error:
        raise NationalCatalogError("ISTAT boundary projection is missing") from error
    _require_reviewed_source_hash(
        hashlib.sha256(projection).hexdigest(),
        BOUNDARIES_PROJECTION_SHA256,
        "ISTAT boundary projection",
    )


def _xlsx_column(cell_reference: str) -> str:
    match = re.match(r"^[A-Z]+", cell_reference)
    if match is None:
        raise NationalCatalogError("XLSX cell has no column reference")
    return match.group(0)


def _xlsx_shared_strings(archive: ZipFile) -> list[str]:
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    namespace = {"m": _XLSX_MAIN_NS}
    return [
        "".join(node.text or "" for node in item.findall(".//m:t", namespace))
        for item in root.findall("m:si", namespace)
    ]


def _xlsx_cell_value(
    cell: ElementTree.Element,
    shared_strings: Sequence[str],
) -> str:
    namespace = {"m": _XLSX_MAIN_NS}
    cell_type = cell.get("t", "")
    if cell_type == "inlineStr":
        return "".join(
            node.text or "" for node in cell.findall(".//m:is/m:t", namespace)
        ).strip()
    value_node = cell.find("m:v", namespace)
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text
    if cell_type == "s":
        try:
            return shared_strings[int(value)].strip()
        except (IndexError, ValueError) as error:
            raise NationalCatalogError("XLSX shared string index is invalid") from error
    return value.strip()


def read_registry_xlsx(path: str | Path) -> tuple[RegistryMunicipality, ...]:
    """Read the first ISTAT registry worksheet without an Excel dependency."""

    try:
        with ZipFile(path) as archive:
            shared_strings = _xlsx_shared_strings(archive)
            root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    except (KeyError, OSError) as error:
        raise NationalCatalogError("ISTAT registry XLSX is unreadable") from error

    namespace = {"m": _XLSX_MAIN_NS}
    rows = root.findall(".//m:sheetData/m:row", namespace)
    if not rows:
        raise NationalCatalogError("ISTAT registry worksheet is empty")

    records: list[RegistryMunicipality] = []
    seen: set[str] = set()
    for row in rows[1:]:
        values = {
            _xlsx_column(cell.get("r", "")): _xlsx_cell_value(cell, shared_strings)
            for cell in row.findall("m:c", namespace)
        }
        istat_code = values.get("E", "")
        if not istat_code:
            continue
        if not _ISTAT_RE.fullmatch(istat_code) or istat_code in seen:
            raise NationalCatalogError("ISTAT registry contains an invalid or duplicate code")
        region_istat = values.get("A", "")
        if region_istat not in REGION_ISO_CODES:
            raise NationalCatalogError(f"unknown ISTAT region code: {region_istat!r}")
        name = values.get("F", "")
        italian_name = values.get("G", "") or name
        uts_istat = values.get("B", "")
        province_historical_istat = values.get("C", "")
        if (
            not name
            or not italian_name
            or not re.fullmatch(r"\d{3}", uts_istat)
            or not re.fullmatch(r"\d{3}", province_historical_istat)
        ):
            raise NationalCatalogError(f"municipality {istat_code} has incomplete identity")
        records.append(
            RegistryMunicipality(
                istat_code=istat_code,
                name=name,
                italian_name=italian_name,
                alternate_name=values.get("H", ""),
                region_istat=region_istat,
                region_iso=REGION_ISO_CODES[region_istat],
                region_name=values.get("K", ""),
                uts_istat=uts_istat,
                province_historical_istat=province_historical_istat,
                uts_name=values.get("L", ""),
                province_abbreviation=values.get("O", ""),
                cadastral_code=values.get("U", ""),
            )
        )
        seen.add(istat_code)

    if len(records) != EXPECTED_MUNICIPALITY_COUNT:
        raise NationalCatalogError(
            f"ISTAT registry must contain {EXPECTED_MUNICIPALITY_COUNT} municipalities, "
            f"found {len(records)}"
        )
    return tuple(records)


def _read_dbf_records(body: bytes) -> list[dict[str, str]]:
    if len(body) < 33:
        raise NationalCatalogError("DBF boundary table is truncated")
    record_count = struct.unpack_from("<I", body, 4)[0]
    header_length, record_length = struct.unpack_from("<HH", body, 8)
    if header_length < 33 or record_length < 2 or len(body) < header_length:
        raise NationalCatalogError("DBF boundary table header is invalid")

    fields: list[tuple[str, int]] = []
    offset = 32
    while offset + 32 <= header_length and body[offset] != 0x0D:
        descriptor = body[offset : offset + 32]
        name = descriptor[:11].rstrip(b"\x00 ").decode("ascii", errors="strict")
        length = descriptor[16]
        if not name or length < 1:
            raise NationalCatalogError("DBF boundary field is invalid")
        fields.append((name, length))
        offset += 32

    expected_length = header_length + record_count * record_length
    if len(body) < expected_length:
        raise NationalCatalogError("DBF boundary records are truncated")

    result: list[dict[str, str]] = []
    for index in range(record_count):
        start = header_length + index * record_length
        record = body[start : start + record_length]
        if record[:1] == b"*":
            continue
        if record[:1] != b" ":
            raise NationalCatalogError("DBF boundary deletion flag is invalid")
        values: dict[str, str] = {}
        cursor = 1
        for name, length in fields:
            raw = record[cursor : cursor + length]
            cursor += length
            try:
                values[name] = raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                values[name] = raw.decode("latin-1").strip()
        result.append(values)
    return result


def read_boundary_identity_zip(path: str | Path) -> tuple[dict[str, str], ...]:
    """Read boundary identities without decoding their geometry.

    This small audit helper is also used to expose source-version mismatches
    before the more expensive geometry materialization starts.
    """

    member = "Com01012026_g/Com01012026_g_WGS84.dbf"
    try:
        with ZipFile(path) as archive:
            _verify_boundary_projection(archive)
            records = _read_dbf_records(archive.read(member))
    except (KeyError, OSError) as error:
        raise NationalCatalogError("ISTAT municipality boundary archive is unreadable") from error

    identities: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in records:
        istat_code = record.get("PRO_COM_T", "")
        if not _ISTAT_RE.fullmatch(istat_code) or istat_code in seen:
            raise NationalCatalogError("boundary table contains an invalid or duplicate code")
        identities.append(
            {
                "istat_code": istat_code,
                "name": record.get("COMUNE", ""),
                "region_istat": record.get("COD_REG", "").zfill(2),
                "uts_istat": record.get("COD_UTS", "").zfill(3),
            }
        )
        seen.add(istat_code)
    return tuple(identities)


def _read_shapefile_polygons(body: bytes) -> list[tuple[tuple[tuple[float, float], ...], ...]]:
    if len(body) < 100 or struct.unpack_from(">I", body, 0)[0] != 9994:
        raise NationalCatalogError("municipality shapefile header is invalid")
    if struct.unpack_from("<I", body, 28)[0] != 1000:
        raise NationalCatalogError("municipality shapefile version is unsupported")
    if struct.unpack_from("<I", body, 32)[0] != 5:
        raise NationalCatalogError("municipality shapefile must contain 2D polygons")

    result: list[tuple[tuple[tuple[float, float], ...], ...]] = []
    cursor = 100
    expected_record_number = 1
    while cursor < len(body):
        if cursor + 8 > len(body):
            raise NationalCatalogError("municipality shapefile record header is truncated")
        record_number, content_words = struct.unpack_from(">II", body, cursor)
        cursor += 8
        content_length = content_words * 2
        end = cursor + content_length
        if record_number != expected_record_number or content_length < 4 or end > len(body):
            raise NationalCatalogError("municipality shapefile record is invalid")
        expected_record_number += 1
        shape_type = struct.unpack_from("<I", body, cursor)[0]
        if shape_type == 0:
            result.append(())
            cursor = end
            continue
        if shape_type != 5 or content_length < 44:
            raise NationalCatalogError("municipality shapefile contains a non-polygon record")
        part_count, point_count = struct.unpack_from("<II", body, cursor + 36)
        parts_offset = cursor + 44
        points_offset = parts_offset + part_count * 4
        if (
            part_count < 1
            or point_count < 4
            or points_offset + point_count * 16 > end
        ):
            raise NationalCatalogError("municipality polygon dimensions are invalid")
        starts = list(struct.unpack_from(f"<{part_count}I", body, parts_offset))
        if starts[0] != 0 or starts != sorted(set(starts)) or starts[-1] >= point_count:
            raise NationalCatalogError("municipality polygon parts are invalid")
        points = [
            struct.unpack_from("<dd", body, points_offset + index * 16)
            for index in range(point_count)
        ]
        rings: list[tuple[tuple[float, float], ...]] = []
        for index, start in enumerate(starts):
            stop = starts[index + 1] if index + 1 < len(starts) else point_count
            ring = tuple(points[start:stop])
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise NationalCatalogError("municipality polygon ring is not closed")
            if any(not math.isfinite(value) for point in ring for value in point):
                raise NationalCatalogError("municipality polygon contains a nonfinite point")
            rings.append(ring)
        result.append(tuple(rings))
        cursor = end
    return result


def _polygon_centroid(
    rings: Sequence[Sequence[tuple[float, float]]],
) -> tuple[float, float, float]:
    weighted_x = 0.0
    weighted_y = 0.0
    signed_area_total = 0.0
    absolute_area_total = 0.0
    for ring in rings:
        cross_sum = 0.0
        centroid_x_sum = 0.0
        centroid_y_sum = 0.0
        for left, right in zip(ring, ring[1:]):
            cross = left[0] * right[1] - right[0] * left[1]
            cross_sum += cross
            centroid_x_sum += (left[0] + right[0]) * cross
            centroid_y_sum += (left[1] + right[1]) * cross
        signed_area = cross_sum / 2.0
        if abs(signed_area) < 1e-6:
            continue
        centroid_x = centroid_x_sum / (6.0 * signed_area)
        centroid_y = centroid_y_sum / (6.0 * signed_area)
        weighted_x += centroid_x * signed_area
        weighted_y += centroid_y * signed_area
        signed_area_total += signed_area
        absolute_area_total += abs(signed_area)
    if abs(signed_area_total) < 1e-6:
        points = [point for ring in rings for point in ring[:-1]]
        if not points:
            raise NationalCatalogError("municipality polygon has no usable area")
        return (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
            absolute_area_total,
        )
    return (
        weighted_x / signed_area_total,
        weighted_y / signed_area_total,
        abs(signed_area_total),
    )


def _point_in_polygon(
    x: float,
    y: float,
    rings: Sequence[Sequence[tuple[float, float]]],
) -> bool:
    inside = False
    for ring in rings:
        previous = ring[-1]
        for current in ring:
            if (current[1] > y) != (previous[1] > y):
                intersection = (
                    (previous[0] - current[0])
                    * (y - current[1])
                    / (previous[1] - current[1])
                    + current[0]
                )
                if x < intersection:
                    inside = not inside
            previous = current
    return inside


def _interior_point(
    rings: Sequence[Sequence[tuple[float, float]]],
) -> tuple[float, float, float]:
    centroid_x, centroid_y, area = _polygon_centroid(rings)
    if _point_in_polygon(centroid_x, centroid_y, rings):
        return centroid_x, centroid_y, area

    all_points = [point for ring in rings for point in ring]
    minimum_y = min(point[1] for point in all_points)
    maximum_y = max(point[1] for point in all_points)
    if maximum_y <= minimum_y:
        raise NationalCatalogError("municipality polygon has no vertical extent")
    candidates = [centroid_y]
    candidates.extend(
        minimum_y + (maximum_y - minimum_y) * step / 65.0
        for step in range(1, 65)
    )
    best: tuple[float, float, float] | None = None
    for y in candidates:
        intersections: list[float] = []
        for ring in rings:
            for left, right in zip(ring, ring[1:]):
                if (left[1] > y) == (right[1] > y):
                    continue
                intersections.append(
                    left[0]
                    + (y - left[1]) * (right[0] - left[0]) / (right[1] - left[1])
                )
        intersections.sort()
        if len(intersections) % 2:
            continue
        for left, right in zip(intersections[0::2], intersections[1::2]):
            width = right - left
            x = (left + right) / 2.0
            if width > 0 and _point_in_polygon(x, y, rings):
                candidate = (width, x, y)
                if best is None or candidate[0] > best[0]:
                    best = candidate
    if best is None:
        raise NationalCatalogError("could not derive an interior municipality point")
    return best[1], best[2], area


def _utm32n_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """Convert EPSG:32632 coordinates to latitude/longitude (WGS84)."""

    semi_major = 6_378_137.0
    eccentricity_squared = 0.0066943799901413165
    scale = 0.9996
    x = easting - 500_000.0
    y = northing
    meridional_arc = y / scale
    mu = meridional_arc / (
        semi_major
        * (
            1
            - eccentricity_squared / 4
            - 3 * eccentricity_squared**2 / 64
            - 5 * eccentricity_squared**3 / 256
        )
    )
    e1 = (1 - math.sqrt(1 - eccentricity_squared)) / (
        1 + math.sqrt(1 - eccentricity_squared)
    )
    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + 151 * e1**3 / 96 * math.sin(6 * mu)
        + 1097 * e1**4 / 512 * math.sin(8 * mu)
    )
    eccentricity_prime_squared = eccentricity_squared / (1 - eccentricity_squared)
    sin_phi1 = math.sin(phi1)
    cos_phi1 = math.cos(phi1)
    tan_phi1 = math.tan(phi1)
    n1 = semi_major / math.sqrt(1 - eccentricity_squared * sin_phi1**2)
    r1 = (
        semi_major
        * (1 - eccentricity_squared)
        / (1 - eccentricity_squared * sin_phi1**2) ** 1.5
    )
    t1 = tan_phi1**2
    c1 = eccentricity_prime_squared * cos_phi1**2
    d = x / (n1 * scale)
    latitude = phi1 - (n1 * tan_phi1 / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * eccentricity_prime_squared)
        * d**4
        / 24
        + (
            61
            + 90 * t1
            + 298 * c1
            + 45 * t1**2
            - 252 * eccentricity_prime_squared
            - 3 * c1**2
        )
        * d**6
        / 720
    )
    longitude = math.radians(9.0) + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (
            5
            - 2 * c1
            + 28 * t1
            - 3 * c1**2
            + 8 * eccentricity_prime_squared
            + 24 * t1**2
        )
        * d**5
        / 120
    ) / cos_phi1
    return math.degrees(latitude), math.degrees(longitude)


def read_boundary_geometry_zip(path: str | Path) -> dict[str, _BoundaryGeometry]:
    base = "Com01012026_g/Com01012026_g_WGS84"
    try:
        with ZipFile(path) as archive:
            _verify_boundary_projection(archive)
            identities = _read_dbf_records(archive.read(base + ".dbf"))
            geometries = _read_shapefile_polygons(archive.read(base + ".shp"))
    except (KeyError, OSError) as error:
        raise NationalCatalogError("ISTAT municipality boundaries are unreadable") from error
    if len(identities) != len(geometries):
        raise NationalCatalogError("boundary geometry and identity record counts differ")

    result: dict[str, _BoundaryGeometry] = {}
    for identity, rings in zip(identities, geometries):
        istat_code = identity.get("PRO_COM_T", "")
        if not _ISTAT_RE.fullmatch(istat_code) or istat_code in result or not rings:
            raise NationalCatalogError("boundary geometry identity is invalid")
        result[istat_code] = _BoundaryGeometry(identity=identity, rings=rings)
    return result


def audit_source_alignment(
    registry: Iterable[RegistryMunicipality],
    boundaries: Iterable[Mapping[str, str]],
) -> dict[str, Any]:
    registry_by_code = {item.istat_code: item for item in registry}
    boundary_by_code = {str(item["istat_code"]): item for item in boundaries}
    registry_codes = set(registry_by_code)
    boundary_codes = set(boundary_by_code)
    return {
        "registry_count": len(registry_codes),
        "boundary_count": len(boundary_codes),
        "missing_boundaries": [
            asdict(registry_by_code[code])
            for code in sorted(registry_codes - boundary_codes)
        ],
        "retired_boundaries": [
            dict(boundary_by_code[code])
            for code in sorted(boundary_codes - registry_codes)
        ],
        "name_mismatches": [
            {
                "istat_code": code,
                "registry_name": registry_by_code[code].name,
                "boundary_name": boundary_by_code[code].get("name", ""),
            }
            for code in sorted(registry_codes & boundary_codes)
            if registry_by_code[code].name != boundary_by_code[code].get("name", "")
        ],
    }


def build_catalog(
    registry: Sequence[RegistryMunicipality],
    boundaries: Mapping[str, _BoundaryGeometry],
    *,
    registry_sha256: str,
    boundaries_sha256: str,
) -> dict[str, Any]:
    _require_reviewed_source_hash(
        registry_sha256,
        REGISTRY_SOURCE_SHA256,
        "ISTAT municipality registry",
    )
    _require_reviewed_source_hash(
        boundaries_sha256,
        BOUNDARIES_SOURCE_SHA256,
        "ISTAT municipality boundaries",
    )
    registry_codes = {item.istat_code for item in registry}
    boundary_codes = set(boundaries)
    missing = registry_codes - boundary_codes
    retired = boundary_codes - registry_codes
    if missing != EXPECTED_MISSING_BOUNDARY_CODES:
        raise NationalCatalogError(
            f"unreviewed current municipalities missing from boundaries: {sorted(missing)}"
        )
    if retired != EXPECTED_RETIRED_BOUNDARY_CODES:
        raise NationalCatalogError(
            f"unreviewed retired municipality boundaries: {sorted(retired)}"
        )

    municipalities: list[dict[str, Any]] = []
    seen_points: set[tuple[float, float]] = set()
    for municipality in registry:
        component_codes = BOUNDARY_COMPONENTS.get(
            municipality.istat_code,
            (municipality.istat_code,),
        )
        if any(code not in boundaries for code in component_codes):
            raise NationalCatalogError(
                f"municipality {municipality.istat_code} has a missing boundary component"
            )
        rings = tuple(
            ring
            for code in component_codes
            for ring in boundaries[code].rings
        )
        easting, northing, area_square_m = _interior_point(rings)
        latitude, longitude = _utm32n_to_wgs84(easting, northing)
        if not (35 <= latitude <= 48.8 and 5.8 <= longitude <= 19.8):
            raise NationalCatalogError(
                f"municipality {municipality.istat_code} point lies outside Italy"
            )
        latitude = round(latitude, 7)
        longitude = round(longitude, 7)
        point_key = (latitude, longitude)
        if point_key in seen_points:
            raise NationalCatalogError("duplicate municipality representative point")
        seen_points.add(point_key)
        municipalities.append(
            {
                **asdict(municipality),
                "representative_point": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "method": "istat_boundary_interior_point_v1",
                    "source_boundary_codes": list(component_codes),
                    "source_area_square_m": round(area_square_m, 3),
                },
            }
        )

    if len(municipalities) != EXPECTED_MUNICIPALITY_COUNT:
        raise NationalCatalogError("national catalog municipality count changed")
    municipality_codes_sha256 = hashlib.sha256(
        canonical_json_bytes(sorted(item["istat_code"] for item in municipalities))
    ).hexdigest()
    document: dict[str, Any] = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "kind": CATALOG_KIND,
        "catalog_version": CATALOG_VERSION,
        "effective_at": REGISTRY_REFERENCE_DATE,
        "municipality_count": len(municipalities),
        "municipality_codes_sha256": municipality_codes_sha256,
        "attribution": {
            "authority": "Istituto nazionale di statistica (Istat)",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "terms_url": "https://www.istat.it/dati/open-data/",
            "transformation": (
                "Representative points are derived from generalized municipal "
                "boundaries; they are interior geometry points, not municipal seats."
            ),
        },
        "sources": {
            "registry": {
                "dataset": "Elenco dei comuni italiani",
                "reference_date": REGISTRY_REFERENCE_DATE,
                "sha256": registry_sha256,
                "url": REGISTRY_SOURCE_URL,
            },
            "boundaries": {
                "dataset": (
                    "Confini delle unità amministrative a fini statistici — "
                    "Comuni generalizzati"
                ),
                "reference_date": BOUNDARIES_REFERENCE_DATE,
                "sha256": boundaries_sha256,
                "url": BOUNDARIES_SOURCE_URL,
            },
        },
        "administrative_reconciliation": {
            "boundary_components": {
                code: list(components)
                for code, components in sorted(BOUNDARY_COMPONENTS.items())
            },
            "retired_boundary_codes": sorted(EXPECTED_RETIRED_BOUNDARY_CODES),
        },
        "municipalities": municipalities,
    }
    document["catalog_sha256"] = hashlib.sha256(canonical_json_bytes(document)).hexdigest()
    return document


def validate_catalog(document: Mapping[str, Any]) -> None:
    if not isinstance(document, Mapping):
        raise NationalCatalogError("national catalog must be an object")
    expected_keys = {
        "administrative_reconciliation",
        "attribution",
        "catalog_sha256",
        "catalog_version",
        "effective_at",
        "kind",
        "municipalities",
        "municipality_count",
        "municipality_codes_sha256",
        "schema_version",
        "sources",
    }
    if set(document) != expected_keys:
        raise NationalCatalogError("national catalog has missing or extra fields")
    if (
        document.get("schema_version") != CATALOG_SCHEMA_VERSION
        or document.get("kind") != CATALOG_KIND
        or document.get("catalog_version") != CATALOG_VERSION
        or document.get("effective_at") != REGISTRY_REFERENCE_DATE
        or document.get("municipality_count") != EXPECTED_MUNICIPALITY_COUNT
    ):
        raise NationalCatalogError("national catalog header is incompatible")
    attribution = document.get("attribution")
    if (
        not isinstance(attribution, Mapping)
        or set(attribution)
        != {
            "authority",
            "license",
            "license_url",
            "terms_url",
            "transformation",
        }
        or attribution.get("authority")
        != "Istituto nazionale di statistica (Istat)"
        or attribution.get("license") != "CC BY 4.0"
        or attribution.get("license_url")
        != "https://creativecommons.org/licenses/by/4.0/"
        or attribution.get("terms_url") != "https://www.istat.it/dati/open-data/"
        or not isinstance(attribution.get("transformation"), str)
        or not attribution.get("transformation")
    ):
        raise NationalCatalogError("national catalog attribution is invalid")
    sources = document.get("sources")
    if not isinstance(sources, Mapping) or set(sources) != {"registry", "boundaries"}:
        raise NationalCatalogError("national catalog sources are invalid")
    expected_sources = {
        "registry": {
            "dataset": "Elenco dei comuni italiani",
            "reference_date": REGISTRY_REFERENCE_DATE,
            "sha256": REGISTRY_SOURCE_SHA256,
            "url": REGISTRY_SOURCE_URL,
        },
        "boundaries": {
            "dataset": (
                "Confini delle unità amministrative a fini statistici — "
                "Comuni generalizzati"
            ),
            "reference_date": BOUNDARIES_REFERENCE_DATE,
            "sha256": BOUNDARIES_SOURCE_SHA256,
            "url": BOUNDARIES_SOURCE_URL,
        },
    }
    if dict(sources) != expected_sources:
        raise NationalCatalogError("national catalog source identity is invalid")
    reconciliation = document.get("administrative_reconciliation")
    expected_reconciliation = {
        "boundary_components": {
            code: list(components)
            for code, components in sorted(BOUNDARY_COMPONENTS.items())
        },
        "retired_boundary_codes": sorted(EXPECTED_RETIRED_BOUNDARY_CODES),
    }
    if reconciliation != expected_reconciliation:
        raise NationalCatalogError(
            "national catalog administrative reconciliation is invalid"
        )
    municipalities = document.get("municipalities")
    if not isinstance(municipalities, list) or len(municipalities) != EXPECTED_MUNICIPALITY_COUNT:
        raise NationalCatalogError("national catalog municipality array is incomplete")
    municipality_keys = {
        "alternate_name",
        "cadastral_code",
        "istat_code",
        "italian_name",
        "name",
        "province_abbreviation",
        "province_historical_istat",
        "region_iso",
        "region_istat",
        "region_name",
        "representative_point",
        "uts_istat",
        "uts_name",
    }
    point_keys = {
        "latitude",
        "longitude",
        "method",
        "source_area_square_m",
        "source_boundary_codes",
    }
    codes: list[str] = []
    for item in municipalities:
        if not isinstance(item, Mapping) or set(item) != municipality_keys:
            raise NationalCatalogError("national catalog municipality record is invalid")
        code = item.get("istat_code")
        region_istat = item.get("region_istat")
        historical_province = item.get("province_historical_istat")
        if (
            not isinstance(code, str)
            or not _ISTAT_RE.fullmatch(code)
            or not isinstance(region_istat, str)
            or region_istat not in REGION_ISO_CODES
            or item.get("region_iso") != REGION_ISO_CODES[region_istat]
            or not isinstance(item.get("uts_istat"), str)
            or not re.fullmatch(r"\d{3}", item["uts_istat"])
            or not isinstance(historical_province, str)
            or not re.fullmatch(r"\d{3}", historical_province)
            or code[:3] != historical_province
            or not isinstance(item.get("province_abbreviation"), str)
            or not re.fullmatch(r"[A-Z]{2}", item["province_abbreviation"])
            or not isinstance(item.get("cadastral_code"), str)
            or not re.fullmatch(r"[A-Z]\d{3}", item["cadastral_code"])
        ):
            raise NationalCatalogError("national catalog municipality identity is invalid")
        for field in ("name", "italian_name", "region_name", "uts_name"):
            value = item.get(field)
            if not isinstance(value, str) or not value or value != value.strip():
                raise NationalCatalogError(
                    "national catalog municipality label is invalid"
                )
        if not isinstance(item.get("alternate_name"), str):
            raise NationalCatalogError(
                "national catalog alternate municipality label is invalid"
            )
        point = item.get("representative_point")
        if not isinstance(point, Mapping) or set(point) != point_keys:
            raise NationalCatalogError(
                "national catalog representative point is invalid"
            )
        latitude = point.get("latitude")
        longitude = point.get("longitude")
        area = point.get("source_area_square_m")
        source_codes = point.get("source_boundary_codes")
        if (
            isinstance(latitude, bool)
            or not isinstance(latitude, (int, float))
            or not math.isfinite(float(latitude))
            or not 35 <= float(latitude) <= 48.8
            or isinstance(longitude, bool)
            or not isinstance(longitude, (int, float))
            or not math.isfinite(float(longitude))
            or not 5.8 <= float(longitude) <= 19.8
            or point.get("method") != "istat_boundary_interior_point_v1"
            or isinstance(area, bool)
            or not isinstance(area, (int, float))
            or not math.isfinite(float(area))
            or float(area) <= 0
            or source_codes
            != list(BOUNDARY_COMPONENTS.get(code, (code,)))
        ):
            raise NationalCatalogError(
                "national catalog representative point semantics are invalid"
            )
        codes.append(code)
    if codes != sorted(codes) or len(set(codes)) != EXPECTED_MUNICIPALITY_COUNT:
        raise NationalCatalogError("national catalog municipality identities are invalid")
    observed_codes_hash = hashlib.sha256(
        canonical_json_bytes(sorted(codes))
    ).hexdigest()
    if document.get("municipality_codes_sha256") != observed_codes_hash:
        raise NationalCatalogError("national catalog municipality code hash is invalid")
    expected_hash = document.get("catalog_sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise NationalCatalogError("national catalog hash field is invalid")
    content = dict(document)
    content.pop("catalog_sha256", None)
    observed_hash = hashlib.sha256(canonical_json_bytes(content)).hexdigest()
    if expected_hash != observed_hash:
        raise NationalCatalogError("national catalog hash is invalid")


def _build_command(args: argparse.Namespace) -> int:
    registry_sha256 = sha256_file(args.registry)
    boundaries_sha256 = sha256_file(args.boundaries)
    registry = read_registry_xlsx(args.registry)
    boundaries = read_boundary_geometry_zip(args.boundaries)
    document = build_catalog(
        registry,
        boundaries,
        registry_sha256=registry_sha256,
        boundaries_sha256=boundaries_sha256,
    )
    validate_catalog(document)
    body = canonical_json_bytes(document)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(body + b"\n")
    print(
        json.dumps(
            {
                "catalog_sha256": document["catalog_sha256"],
                "municipality_count": document["municipality_count"],
                "output": str(args.output),
                "output_bytes": len(body) + 1,
                "status": "built",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _audit_command(args: argparse.Namespace) -> int:
    registry_sha256 = sha256_file(args.registry)
    boundaries_sha256 = sha256_file(args.boundaries)
    _require_reviewed_source_hash(
        registry_sha256,
        REGISTRY_SOURCE_SHA256,
        "ISTAT municipality registry",
    )
    _require_reviewed_source_hash(
        boundaries_sha256,
        BOUNDARIES_SOURCE_SHA256,
        "ISTAT municipality boundaries",
    )
    registry = read_registry_xlsx(args.registry)
    boundaries = read_boundary_identity_zip(args.boundaries)
    audit = {
        "schema_version": 1,
        "kind": "meteofriul.weather.national_catalog_source_audit",
        "registry": {
            "reference_date": REGISTRY_REFERENCE_DATE,
            "sha256": registry_sha256,
            "url": REGISTRY_SOURCE_URL,
        },
        "boundaries": {
            "reference_date": BOUNDARIES_REFERENCE_DATE,
            "sha256": boundaries_sha256,
            "url": BOUNDARIES_SOURCE_URL,
        },
        **audit_source_alignment(registry, boundaries),
    }
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit", help="compare registry and boundary identities")
    audit.add_argument("--registry", type=Path, required=True)
    audit.add_argument("--boundaries", type=Path, required=True)
    audit.set_defaults(handler=_audit_command)
    build = subparsers.add_parser("build", help="materialize the reviewed national catalog")
    build.add_argument("--registry", type=Path, required=True)
    build.add_argument("--boundaries", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.set_defaults(handler=_build_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
