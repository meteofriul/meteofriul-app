"""Build the reviewed Comune -> DPC alert-zone catalog.

The builder overlays the canonical, non-generalized ISTAT 2026 municipality
boundaries with the alert-zone polygons shipped in one complete DPC bulletin
ZIP.  It is deliberately offline and create-only: source artifacts are passed
explicitly and the destination is never overwritten.

No representative-point shortcut is used to decide municipality coverage.
The point is retained only as a separately labelled, optional zone hint; every
zone with a positive-area intersection is preserved for multi-zone Comuni.
"""

from __future__ import annotations

import argparse
from array import array
from collections import defaultdict
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.services.national_municipalities import (
    get_default_national_municipality_catalog,
)
from app.services.official_alert_zone_catalog import (
    ALERT_ZONE_CATALOG_CONTRACT,
    FVG_REGION_ISO,
    FVG_ZONE_IDS,
    REGION_ZONE_PREFIX,
)
from app.services.pilot_community_geography import (
    BOUNDARIES_SOURCE_SHA256,
    GEOGRAPHY_SCHEMA,
    PILOT_GEOGRAPHY_ARTIFACT_SHA256,
    PilotCommunityGeographyCatalog,
)
from app.weather.dpc_national_alerts import canonical_dpc_zone_id
from app.weather.dpc_national_zone_snapshot import _read_dbf, _read_members
from tools.build_pilot_community_geography import _shape_records, sha256_file


GRID_DEGREES = 0.05
_EPSILON = 1e-12


class OfficialAlertZoneCatalogBuildError(ValueError):
    """The geographic inputs cannot produce a safe complete catalog."""


def _bbox(rings: Iterable[array]) -> tuple[float, float, float, float]:
    materialized = tuple(rings)
    return (
        min(min(ring[::2]) for ring in materialized),
        min(min(ring[1::2]) for ring in materialized),
        max(max(ring[::2]) for ring in materialized),
        max(max(ring[1::2]) for ring in materialized),
    )


def _bbox_overlaps(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> bool:
    return not (
        first[2] < second[0]
        or second[2] < first[0]
        or first[3] < second[1]
        or second[3] < first[1]
    )


def _point_location(rings: tuple[array, ...], x: float, y: float) -> int:
    """Return 1 inside, 0 on a boundary and -1 outside using even/odd fill."""

    inside = False
    for ring in rings:
        x1, y1 = ring[-2:]
        for index in range(0, len(ring), 2):
            x2, y2 = ring[index], ring[index + 1]
            dx, dy = x2 - x1, y2 - y1
            tolerance = _EPSILON * max(1.0, abs(dx), abs(dy))
            if (
                min(x1, x2) - tolerance <= x <= max(x1, x2) + tolerance
                and min(y1, y2) - tolerance <= y <= max(y1, y2) + tolerance
                and abs((x - x1) * dy - (y - y1) * dx) <= tolerance
            ):
                return 0
            if (y1 > y) != (y2 > y) and x < dx * (y - y1) / dy + x1:
                inside = not inside
            x1, y1 = x2, y2
    return 1 if inside else -1


def _ring_segments(rings: tuple[array, ...]):
    for ring in rings:
        x1, y1 = ring[-2:]
        for index in range(0, len(ring), 2):
            x2, y2 = ring[index], ring[index + 1]
            yield (x1, y1, x2, y2)
            x1, y1 = x2, y2


def _orientation(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _proper_intersection(first, second) -> bool:
    ax, ay, bx, by = first
    cx, cy, dx, dy = second
    if not _bbox_overlaps(
        (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)),
        (min(cx, dx), min(cy, dy), max(cx, dx), max(cy, dy)),
    ):
        return False
    values = (
        _orientation(ax, ay, bx, by, cx, cy),
        _orientation(ax, ay, bx, by, dx, dy),
        _orientation(cx, cy, dx, dy, ax, ay),
        _orientation(cx, cy, dx, dy, bx, by),
    )
    scale = max(
        1.0,
        abs(bx - ax),
        abs(by - ay),
        abs(dx - cx),
        abs(dy - cy),
    )
    tolerance = _EPSILON * scale * scale
    return (
        (values[0] > tolerance and values[1] < -tolerance)
        or (values[0] < -tolerance and values[1] > tolerance)
    ) and (
        (values[2] > tolerance and values[3] < -tolerance)
        or (values[2] < -tolerance and values[3] > tolerance)
    )


def _grid_range(low: float, high: float) -> range:
    return range(
        math.floor(low / GRID_DEGREES),
        math.floor(high / GRID_DEGREES) + 1,
    )


class _PreparedGeometry:
    def __init__(self, rings: tuple[array, ...]) -> None:
        self.rings = rings
        self.bbox = _bbox(rings)
        self.segments = tuple(_ring_segments(rings))
        self.grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        self.y_grid: dict[int, list[int]] = defaultdict(list)
        for index, (x1, y1, x2, y2) in enumerate(self.segments):
            for gy in _grid_range(min(y1, y2), max(y1, y2)):
                self.y_grid[gy].append(index)
            for gx in _grid_range(min(x1, x2), max(x1, x2)):
                for gy in _grid_range(min(y1, y2), max(y1, y2)):
                    self.grid[(gx, gy)].append(index)

    def segment_candidates(self, bbox) -> tuple[tuple[float, ...], ...]:
        indexes = set()
        for gx in _grid_range(bbox[0], bbox[2]):
            for gy in _grid_range(bbox[1], bbox[3]):
                indexes.update(self.grid.get((gx, gy), ()))
        return tuple(self.segments[index] for index in sorted(indexes))

    def point_location(self, x: float, y: float) -> int:
        if not (
            self.bbox[0] - _EPSILON <= x <= self.bbox[2] + _EPSILON
            and self.bbox[1] - _EPSILON <= y <= self.bbox[3] + _EPSILON
        ):
            return -1
        inside = False
        for index in self.y_grid.get(math.floor(y / GRID_DEGREES), ()):
            x1, y1, x2, y2 = self.segments[index]
            dx, dy = x2 - x1, y2 - y1
            tolerance = _EPSILON * max(1.0, abs(dx), abs(dy))
            if (
                min(x1, x2) - tolerance <= x <= max(x1, x2) + tolerance
                and min(y1, y2) - tolerance <= y <= max(y1, y2) + tolerance
                and abs((x - x1) * dy - (y - y1) * dx) <= tolerance
            ):
                return 0
            if (y1 > y) != (y2 > y) and x < dx * (y - y1) / dy + x1:
                inside = not inside
        return 1 if inside else -1


def _positive_overlap(
    municipality: _PreparedGeometry,
    zone: _PreparedGeometry,
    *,
    public_point: tuple[float, float],
) -> bool:
    """Reject boundary-only contact while retaining every positive overlap."""

    if not _bbox_overlaps(municipality.bbox, zone.bbox):
        return False
    if zone.point_location(public_point[0], public_point[1]) == 1:
        return True

    for municipal_segment in municipality.segments:
        x1, y1, x2, y2 = municipal_segment
        candidates = zone.segment_candidates(
            (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        )
        if any(
            _proper_intersection(municipal_segment, zone_segment)
            for zone_segment in candidates
        ):
            return True

    # Covers a zone wholly enclosed by a Comune and boundaries which enter and
    # leave exactly through municipality vertices. A mere shared outer border
    # has its midpoint on, not inside, the municipal boundary.
    for x1, y1, x2, y2 in zone.segment_candidates(municipality.bbox):
        if municipality.point_location((x1 + x2) / 2, (y1 + y2) / 2) == 1:
            return True
    return False


def _zone_geometries(payload: bytes):
    revision, members = _read_members(payload)
    prefix = f"{revision}_today"
    rows = _read_dbf(members[f"{prefix}.dbf"])
    rings_by_record = tuple(
        _shape_records(BytesIO(members[f"{prefix}.shp"]))
    )
    if len(rows) != len(rings_by_record):
        raise OfficialAlertZoneCatalogBuildError("zone_shape_identity_mismatch")

    zones = []
    digest = hashlib.sha256()
    seen = set()
    for row, rings in zip(rows, rings_by_record):
        source_zone_id = row["Zona_all"].strip()
        zone_id = canonical_dpc_zone_id(source_zone_id)
        if zone_id in seen:
            raise OfficialAlertZoneCatalogBuildError("duplicate_canonical_zone")
        seen.add(zone_id)
        digest.update(zone_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source_zone_id.encode("utf-8"))
        digest.update(b"\0")
        for ring in rings:
            digest.update(ring.tobytes())
        zones.append(
            {
                "zone_id": zone_id,
                "source_zone_id": source_zone_id,
                "zone_name": row["Nome_zona"].strip(),
                "geometry": _PreparedGeometry(rings),
            }
        )
    zones.sort(key=lambda item: item["zone_id"])
    return revision, digest.hexdigest(), tuple(zones)


def _canonical_digest(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("catalog_sha256", None)
    encoded = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build(zone_zip: Path, municipality_geography: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise OfficialAlertZoneCatalogBuildError("output_exists")
    raw_zones = zone_zip.read_bytes()
    revision, zone_geometry_sha256, zones = _zone_geometries(raw_zones)
    national_catalog = get_default_national_municipality_catalog()
    geography = PilotCommunityGeographyCatalog(municipality_geography)
    municipalities = geography.municipalities
    if {item.region_iso for item in municipalities} != set(REGION_ZONE_PREFIX):
        raise OfficialAlertZoneCatalogBuildError("region_catalog_changed")
    observed_prefixes = {
        zone["source_zone_id"].split("-", 1)[0] for zone in zones
    }
    if observed_prefixes != set(REGION_ZONE_PREFIX.values()):
        raise OfficialAlertZoneCatalogBuildError("zone_region_prefixes_changed")

    mappings = []
    unresolved = []
    for municipality in sorted(municipalities, key=lambda item: item.istat_code):
        rings = geography._geometry(municipality.istat_code)
        prepared = _PreparedGeometry(rings)
        point = (municipality.longitude, municipality.latitude)
        expected_prefix = REGION_ZONE_PREFIX[municipality.region_iso] + "-"
        regional_zones = tuple(
            zone
            for zone in zones
            if zone["source_zone_id"].startswith(expected_prefix)
        )
        zone_ids = [
            zone["zone_id"]
            for zone in regional_zones
            if _positive_overlap(prepared, zone["geometry"], public_point=point)
        ]
        if not zone_ids:
            unresolved.append(municipality.istat_code)
            continue
        point_zone_ids = [
            zone["zone_id"]
            for zone in regional_zones
            if zone["geometry"].point_location(point[0], point[1]) == 1
        ]
        if municipality.region_iso == FVG_REGION_ISO and (
            not set(zone_ids).issubset(FVG_ZONE_IDS)
            or not zone_ids
        ):
            raise OfficialAlertZoneCatalogBuildError(
                f"fvg_zone_contract_changed:{municipality.istat_code}:{zone_ids}"
            )
        mappings.append(
            {
                "istat": municipality.istat_code,
                "region_iso": municipality.region_iso,
                "zone_ids": sorted(zone_ids),
                "point_zone_id": (
                    point_zone_ids[0] if len(point_zone_ids) == 1 else None
                ),
            }
        )
    if unresolved:
        raise OfficialAlertZoneCatalogBuildError(
            "unresolved_municipalities:" + ",".join(unresolved[:20])
        )
    expected_codes = {item.istat_code for item in national_catalog.municipalities}
    if {item["istat"] for item in mappings} != expected_codes:
        raise OfficialAlertZoneCatalogBuildError("municipality_coverage_mismatch")
    fvg_mappings = [item for item in mappings if item["region_iso"] == FVG_REGION_ISO]
    if len(fvg_mappings) != 215 or {
        zone_id for item in fvg_mappings for zone_id in item["zone_ids"]
    } != FVG_ZONE_IDS:
        raise OfficialAlertZoneCatalogBuildError("fvg_coverage_mismatch")

    payload = {
        "contract": ALERT_ZONE_CATALOG_CONTRACT,
        "schema_version": 1,
        "source": {
            "authority": "Dipartimento della Protezione Civile",
            "bulletin_revision": revision,
            "zone_geometry_sha256": zone_geometry_sha256,
            "zone_zip_sha256": hashlib.sha256(raw_zones).hexdigest(),
            "municipality_geography_schema": GEOGRAPHY_SCHEMA,
            "municipality_boundaries_sha256": BOUNDARIES_SOURCE_SHA256,
            "municipality_geometry_artifact_sha256": sha256_file(
                municipality_geography
            ),
            "municipality_catalog_sha256": national_catalog.catalog_sha256,
        },
        "zone_count": len(zones),
        "municipality_count": len(mappings),
        "multi_zone_municipality_count": sum(
            len(item["zone_ids"]) > 1 for item in mappings
        ),
        "fvg_municipality_count": len(fvg_mappings),
        "zones": [
            {
                "zone_id": zone["zone_id"],
                "source_zone_id": zone["source_zone_id"],
                "zone_name": zone["zone_name"],
            }
            for zone in zones
        ],
        "mappings": mappings,
    }
    if payload["source"]["municipality_geometry_artifact_sha256"] != (
        PILOT_GEOGRAPHY_ARTIFACT_SHA256
    ):
        raise OfficialAlertZoneCatalogBuildError(
            "municipality_geometry_artifact_changed"
        )
    payload["catalog_sha256"] = _canonical_digest(payload)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(
        prefix="official-alert-zone-catalog-",
        suffix=".json",
        dir=output.parent,
        delete=False,
    )
    temporary_path = Path(temporary.name)
    temporary.close()
    try:
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if output.exists():
            raise OfficialAlertZoneCatalogBuildError("output_appeared")
        os.link(temporary_path, output)
    finally:
        temporary_path.unlink(missing_ok=True)
    return {
        "output": str(output),
        "zones": payload["zone_count"],
        "municipalities": payload["municipality_count"],
        "multi_zone_municipalities": payload["multi_zone_municipality_count"],
        "fvg_municipalities": payload["fvg_municipality_count"],
        "catalog_sha256": payload["catalog_sha256"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zone-zip", type=Path, required=True)
    parser.add_argument("--municipality-geography", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(
        json.dumps(
            build(
                arguments.zone_zip,
                arguments.municipality_geography,
                arguments.output,
            ),
            ensure_ascii=False,
        )
    )
