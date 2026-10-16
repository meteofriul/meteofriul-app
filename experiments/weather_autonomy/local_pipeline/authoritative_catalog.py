"""Build authoritative representative points from the local ISTAT/IRDAT data.

This is an isolated audit product.  It deliberately consumes only municipal
identity fields from ``fvg_municipalities.json``; that file's legacy latitude
and longitude fields are neither read nor copied.  Coordinates come exclusively
from IRDAT localities or, as a final fallback, from ISTAT 2026 polygons.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from typing import Any


EXPECTED_MUNICIPALITIES = 215
SCHEMA_VERSION = 1
CATALOG_VERSION = "istat-2026-irdat-2006-representative-points-v1"
KIND = "meteofriul.authoritative_representative_points"

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GEOGRAPHY_PATH = ROOT / "backend" / "app" / "data" / "fvg_geography.json"
DEFAULT_MUNICIPALITY_PATH = ROOT / "backend" / "app" / "data" / "fvg_municipalities.json"

_ISTAT = re.compile(r"[0-9]{6}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_LOCALITY_KINDS = frozenset(("municipal_seat", "settlement"))
_EPSILON = 1e-12


class AuthoritativeCatalogError(ValueError):
    """Raised when local source data cannot produce an authoritative catalog."""


def canonical_json_bytes(value: Any) -> bytes:
    """Canonical UTF-8 used for the stable catalog and metadata digests."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise AuthoritativeCatalogError("Catalog contains a non-canonical JSON value") from None


def normalize_municipality_name(value: str) -> str:
    """Normalize case, Unicode compatibility forms and whitespace only."""
    if not isinstance(value, str):
        raise AuthoritativeCatalogError("Municipality or locality name must be text")
    normalized = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
    if not normalized:
        raise AuthoritativeCatalogError("Municipality or locality name must not be empty")
    return normalized


def _text(value: Any, label: str, *, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise AuthoritativeCatalogError(f"{label} must be bounded non-empty text")
    if any(ord(character) < 0x20 and character not in "\t\r\n" for character in value):
        raise AuthoritativeCatalogError(f"{label} contains a control character")
    return value.strip()


def _coordinate(value: Any, *, latitude: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise AuthoritativeCatalogError("Geometry coordinate must be finite")
    result = float(value)
    limit = 90 if latitude else 180
    if not -limit <= result <= limit:
        raise AuthoritativeCatalogError("Geometry coordinate is outside geographic bounds")
    return result


def _validated_polygons(value: Any) -> tuple[tuple[tuple[tuple[float, float], ...], ...], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise AuthoritativeCatalogError("Municipality polygons must be a non-empty sequence")
    polygons = []
    for polygon in value:
        if isinstance(polygon, (str, bytes)) or not isinstance(polygon, Sequence) or not polygon:
            raise AuthoritativeCatalogError("Polygon must contain at least one ring")
        rings = []
        for ring in polygon:
            if isinstance(ring, (str, bytes)) or not isinstance(ring, Sequence) or len(ring) < 4:
                raise AuthoritativeCatalogError("Polygon ring must contain at least four positions")
            positions = []
            for position in ring:
                if (
                    isinstance(position, (str, bytes))
                    or not isinstance(position, Sequence)
                    or len(position) != 2
                ):
                    raise AuthoritativeCatalogError("Polygon position must be a longitude/latitude pair")
                positions.append(
                    (
                        _coordinate(position[0], latitude=False),
                        _coordinate(position[1], latitude=True),
                    )
                )
            if positions[0] != positions[-1] or len(set(positions[:-1])) < 3:
                raise AuthoritativeCatalogError("Polygon ring must be closed and non-degenerate")
            twice_area = sum(
                left[0] * right[1] - right[0] * left[1]
                for left, right in zip(positions, positions[1:])
            )
            if abs(twice_area) <= _EPSILON:
                raise AuthoritativeCatalogError("Polygon ring has zero area")
            rings.append(tuple(positions))
        polygons.append(tuple(rings))
    return tuple(polygons)


def _ring_location(longitude: float, latitude: float, ring: Sequence[Sequence[float]]) -> int:
    """Return -1 outside, 0 on boundary, or 1 inside one closed ring."""
    inside = False
    for left, right in zip(ring, ring[1:]):
        x1, y1 = left
        x2, y2 = right
        cross = (longitude - x1) * (y2 - y1) - (latitude - y1) * (x2 - x1)
        scale = max(1.0, abs(x2 - x1), abs(y2 - y1))
        if (
            abs(cross) <= _EPSILON * scale
            and min(x1, x2) - _EPSILON <= longitude <= max(x1, x2) + _EPSILON
            and min(y1, y2) - _EPSILON <= latitude <= max(y1, y2) + _EPSILON
        ):
            return 0
        if (y1 > latitude) != (y2 > latitude):
            intersection = x1 + (latitude - y1) * (x2 - x1) / (y2 - y1)
            if longitude < intersection:
                inside = not inside
    return 1 if inside else -1


def _polygon_location(
    longitude: float,
    latitude: float,
    polygon: Sequence[Sequence[Sequence[float]]],
) -> int:
    outer = _ring_location(longitude, latitude, polygon[0])
    if outer < 0:
        return -1
    if outer == 0:
        return 0
    for hole in polygon[1:]:
        location = _ring_location(longitude, latitude, hole)
        if location > 0:
            return -1
        if location == 0:
            return 0
    return 1


def point_in_polygons(
    longitude: float,
    latitude: float,
    polygons: Sequence[Sequence[Sequence[Sequence[float]]]],
    *,
    boundary_is_inside: bool = True,
) -> bool:
    """Test a point against the repository's MultiPolygon-like representation."""
    wanted = {0, 1} if boundary_is_inside else {1}
    return any(_polygon_location(longitude, latitude, polygon) in wanted for polygon in polygons)


def _scanline_intersections(
    ring: Sequence[Sequence[float]], latitude: float
) -> list[float]:
    intersections = []
    for left, right in zip(ring, ring[1:]):
        x1, y1 = left
        x2, y2 = right
        if y1 == y2:
            continue
        if y1 < y2:
            low_x, low_y, high_x, high_y = x1, y1, x2, y2
        else:
            low_x, low_y, high_x, high_y = x2, y2, x1, y1
        if low_y <= latitude < high_y:
            fraction = (latitude - low_y) / (high_y - low_y)
            intersections.append(low_x + fraction * (high_x - low_x))
    return sorted(intersections)


def deterministic_point_on_surface(
    polygons: Sequence[Sequence[Sequence[Sequence[float]]]],
) -> tuple[float, float]:
    """Choose the midpoint of a deterministic interior horizontal segment.

    Unlike a raw bbox centre, every candidate is tested against the outer ring
    and holes.  Candidate ranking contains no input-list index, so polygon and
    ring orientation changes cannot choose a different point.
    """
    candidates: list[tuple[float, float, float]] = []
    for polygon in polygons:
        outer = polygon[0]
        latitudes = [position[1] for position in outer[:-1]]
        minimum, maximum = min(latitudes), max(latitudes)
        if maximum - minimum <= _EPSILON:
            continue
        middle = (minimum + maximum) / 2
        scanlines = {
            middle,
            math.nextafter(middle, maximum),
            math.nextafter(middle, minimum),
            minimum + (maximum - minimum) / 4,
            minimum + 3 * (maximum - minimum) / 4,
        }
        for latitude in sorted(scanlines):
            intersections = sorted(
                longitude
                for ring in polygon
                for longitude in _scanline_intersections(ring, latitude)
            )
            for left, right in zip(intersections, intersections[1:]):
                width = right - left
                if width <= _EPSILON:
                    continue
                longitude = (left + right) / 2
                if _polygon_location(longitude, latitude, polygon) == 1:
                    candidates.append((width, longitude, latitude))
    if not candidates:
        raise AuthoritativeCatalogError("No deterministic interior polygon point could be found")

    # Widest interval first, then southernmost/westernmost as stable tie-breaks.
    width, longitude, latitude = min(
        candidates,
        key=lambda item: (-round(item[0], 14), round(item[2], 12), round(item[1], 12)),
    )
    del width
    rounded = (round(longitude, 7), round(latitude, 7))
    if point_in_polygons(*rounded, polygons, boundary_is_inside=False):
        return rounded
    precise = (round(longitude, 12), round(latitude, 12))
    if point_in_polygons(*precise, polygons, boundary_is_inside=False):
        return precise
    if point_in_polygons(longitude, latitude, polygons, boundary_is_inside=False):
        return longitude, latitude
    raise AuthoritativeCatalogError("Deterministic polygon point failed its containment check")


def _source(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise AuthoritativeCatalogError(f"{label} source metadata must be an object")
    source = {
        "authority": _text(value.get("authority"), f"{label} authority"),
        "dataset": _text(value.get("dataset"), f"{label} dataset"),
        "license": _text(value.get("license"), f"{label} license"),
    }
    digest = value.get("sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise AuthoritativeCatalogError(f"{label} source SHA-256 is invalid")
    source["source_sha256"] = digest
    return source


def _metadata_records(source: Mapping[str, Any]) -> tuple[list[dict[str, str]], str]:
    if source.get("schemaVersion") != 1:
        raise AuthoritativeCatalogError("Unsupported municipality metadata schema")
    records = source.get("municipalities")
    if not isinstance(records, list) or len(records) != EXPECTED_MUNICIPALITIES:
        raise AuthoritativeCatalogError("Municipality metadata must contain exactly 215 records")
    source_metadata = source.get("source")
    if not isinstance(source_metadata, Mapping) or source_metadata.get("count") != EXPECTED_MUNICIPALITIES:
        raise AuthoritativeCatalogError("Municipality metadata source count is inconsistent")

    selected = []
    seen_istat = set()
    for raw in records:
        if not isinstance(raw, Mapping):
            raise AuthoritativeCatalogError("Municipality metadata record must be an object")
        # Do not access raw['latitude'], raw['longitude'] or the coordinate source.
        record = {
            "istat_code": raw.get("istatCode"),
            "slug": raw.get("slug"),
            "name": raw.get("name"),
            "province": raw.get("province"),
            "province_name": raw.get("provinceName"),
        }
        istat = record["istat_code"]
        if not isinstance(istat, str) or not _ISTAT.fullmatch(istat) or istat in seen_istat:
            raise AuthoritativeCatalogError("Municipality metadata has an invalid or duplicate ISTAT code")
        # ISTAT is the identity key.  ``slug`` is descriptive registry metadata;
        # the checked-in source contains a legacy replacement character in one
        # value, so treating URL syntax as an authority constraint would reject
        # an otherwise valid official record.
        record["slug"] = _text(record["slug"], "municipality slug")
        record["name"] = _text(record["name"], "municipality name")
        record["province"] = _text(record["province"], "municipality province", maximum=2)
        record["province_name"] = _text(record["province_name"], "municipality province name")
        selected.append(record)
        seen_istat.add(istat)
    selected.sort(key=lambda item: item["istat_code"])
    digest = hashlib.sha256(canonical_json_bytes(selected)).hexdigest()
    return selected, digest


def _geography_records(source: Mapping[str, Any]):
    if source.get("schemaVersion") != "fvg-geography.v1":
        raise AuthoritativeCatalogError("Unsupported FVG geography schema")
    municipalities = source.get("municipalities")
    localities = source.get("localities")
    if (
        source.get("municipalityCount") != EXPECTED_MUNICIPALITIES
        or not isinstance(municipalities, list)
        or len(municipalities) != EXPECTED_MUNICIPALITIES
    ):
        raise AuthoritativeCatalogError("FVG geography must contain exactly 215 municipalities")
    if not isinstance(localities, list) or source.get("localityCount") != len(localities):
        raise AuthoritativeCatalogError("FVG geography locality count is inconsistent")
    sources = source.get("sources")
    if not isinstance(sources, Mapping):
        raise AuthoritativeCatalogError("FVG geography sources are missing")
    boundary_source = _source(sources.get("municipalities"), "ISTAT boundary")
    locality_source = _source(sources.get("localities"), "IRDAT locality")

    geometry_by_istat = {}
    for raw in municipalities:
        if not isinstance(raw, Mapping):
            raise AuthoritativeCatalogError("Geography municipality must be an object")
        istat = raw.get("istatCode")
        if not isinstance(istat, str) or not _ISTAT.fullmatch(istat) or istat in geometry_by_istat:
            raise AuthoritativeCatalogError("Geography has an invalid or duplicate ISTAT code")
        geometry_by_istat[istat] = {
            "name": _text(raw.get("name"), "geography municipality name"),
            "polygons": _validated_polygons(raw.get("polygons")),
        }

    localities_by_istat = defaultdict(list)
    locality_ids = set()
    for raw in localities:
        if not isinstance(raw, Mapping):
            raise AuthoritativeCatalogError("IRDAT locality must be an object")
        identifier = _text(raw.get("id"), "IRDAT locality identifier")
        if identifier in locality_ids:
            raise AuthoritativeCatalogError("IRDAT locality identifier is duplicated")
        istat = raw.get("municipalityIstat")
        if not isinstance(istat, str) or istat not in geometry_by_istat:
            raise AuthoritativeCatalogError("IRDAT locality has an unknown municipality ISTAT code")
        kind = raw.get("kind")
        if kind not in _LOCALITY_KINDS:
            raise AuthoritativeCatalogError("IRDAT locality kind is unsupported")
        localities_by_istat[istat].append(
            {
                "id": identifier,
                "name": _text(raw.get("name"), "IRDAT locality name"),
                "kind": kind,
                "latitude": _coordinate(raw.get("latitude"), latitude=True),
                "longitude": _coordinate(raw.get("longitude"), latitude=False),
            }
        )
        locality_ids.add(identifier)
    for values in localities_by_istat.values():
        values.sort(key=lambda item: (item["kind"], normalize_municipality_name(item["name"]), item["id"]))
    return geometry_by_istat, localities_by_istat, boundary_source, locality_source


def _representative_point(metadata, geometry, localities, boundary_source, locality_source):
    seats = [item for item in localities if item["kind"] == "municipal_seat"]
    exact_name = normalize_municipality_name(metadata["name"])
    exact = [item for item in localities if normalize_municipality_name(item["name"]) == exact_name]
    if len(seats) == 1:
        candidate = seats[0]
        method = "irdat_unique_municipal_seat"
    elif len(exact) == 1:
        candidate = exact[0]
        method = "irdat_unique_normalized_municipality_name"
    else:
        candidate = None
        method = "istat_deterministic_point_on_surface"

    if candidate is not None:
        longitude, latitude = candidate["longitude"], candidate["latitude"]
        if not point_in_polygons(longitude, latitude, geometry["polygons"]):
            raise AuthoritativeCatalogError("Selected IRDAT representative point lies outside its ISTAT polygon")
        source = dict(locality_source, feature_id=candidate["id"])
        locality_name = candidate["name"]
    else:
        longitude, latitude = deterministic_point_on_surface(geometry["polygons"])
        source = dict(boundary_source, feature_id=None)
        locality_name = None

    point = {
        "latitude": latitude,
        "longitude": longitude,
        "method": method,
        "source": source,
        "locality_name": locality_name,
    }
    if not point_in_polygons(point["longitude"], point["latitude"], geometry["polygons"]):
        raise AuthoritativeCatalogError("Representative point failed final polygon containment")
    return point


def build_authoritative_catalog(
    geography: Mapping[str, Any], municipality_metadata: Mapping[str, Any]
) -> dict[str, Any]:
    """Build and canonically hash all 215 authoritative representative points."""
    if not isinstance(geography, Mapping) or not isinstance(municipality_metadata, Mapping):
        raise AuthoritativeCatalogError("Catalog sources must be JSON objects")
    metadata, metadata_digest = _metadata_records(municipality_metadata)
    geometry, localities, boundary_source, locality_source = _geography_records(geography)
    metadata_codes = {item["istat_code"] for item in metadata}
    if metadata_codes != set(geometry):
        raise AuthoritativeCatalogError("ISTAT coverage differs between metadata and geography")

    records = []
    for item in metadata:
        istat = item["istat_code"]
        area = geometry[istat]
        if normalize_municipality_name(item["name"]) != normalize_municipality_name(area["name"]):
            raise AuthoritativeCatalogError("Municipality name differs between ISTAT source products")
        records.append(
            {
                **item,
                "representative_point": _representative_point(
                    item,
                    area,
                    localities.get(istat, ()),
                    boundary_source,
                    locality_source,
                ),
            }
        )

    counts = Counter(record["representative_point"]["method"] for record in records)
    document = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "catalog_version": CATALOG_VERSION,
        "municipality_count": len(records),
        "policy": {
            "priority": [
                "unique_irdat_municipal_seat",
                "unique_irdat_exact_normalized_municipality_name",
                "deterministic_istat_polygon_point_on_surface",
            ],
            "name_normalization": "unicode_nfkc_casefold_collapsed_whitespace_v1",
            "polygon_algorithm": "widest_valid_horizontal_interior_segment_v1",
            "legacy_coordinate_fields_consumed": False,
        },
        "source_fingerprints": {
            "istat_boundaries_sha256": boundary_source["source_sha256"],
            "irdat_localities_sha256": locality_source["source_sha256"],
            "municipality_identity_metadata_sha256": metadata_digest,
        },
        "method_counts": dict(sorted(counts.items())),
        "municipalities": records,
    }
    if len(records) != EXPECTED_MUNICIPALITIES or len(metadata_codes) != EXPECTED_MUNICIPALITIES:
        raise AuthoritativeCatalogError("Authoritative catalog does not contain 215 unique ISTAT codes")
    document["catalog_sha256"] = hashlib.sha256(canonical_json_bytes(document)).hexdigest()
    return document


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuthoritativeCatalogError("Source JSON contains a duplicate object key")
        result[key] = value
    return result


def _load_json(path: str | Path, maximum_bytes: int) -> Mapping[str, Any]:
    selected = Path(path)
    if not selected.is_file() or not 1 <= selected.stat().st_size <= maximum_bytes:
        raise AuthoritativeCatalogError("Source JSON path or size is invalid")
    try:
        value = json.loads(
            selected.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                AuthoritativeCatalogError("Source JSON contains a non-finite number")
            ),
        )
    except AuthoritativeCatalogError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise AuthoritativeCatalogError("Source JSON cannot be loaded") from None
    if not isinstance(value, Mapping):
        raise AuthoritativeCatalogError("Source JSON root must be an object")
    return value


def load_authoritative_catalog(
    geography_path: str | Path = DEFAULT_GEOGRAPHY_PATH,
    municipality_path: str | Path = DEFAULT_MUNICIPALITY_PATH,
) -> dict[str, Any]:
    """Load the two approved local files and return the derived audit product."""
    geography = _load_json(geography_path, 16 * 1024 * 1024)
    metadata = _load_json(municipality_path, 2 * 1024 * 1024)
    return build_authoritative_catalog(geography, metadata)


def verify_catalog_hash(document: Mapping[str, Any]) -> bool:
    """Verify the non-self-referential canonical SHA-256 on a built document."""
    if not isinstance(document, Mapping):
        return False
    expected = document.get("catalog_sha256")
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        return False
    content = deepcopy(dict(document))
    content.pop("catalog_sha256", None)
    return hashlib.sha256(canonical_json_bytes(content)).hexdigest() == expected
