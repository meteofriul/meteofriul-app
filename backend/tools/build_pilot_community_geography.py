"""Create-only builder for the pilot national Community boundary index.

Requires pyproj only at build time. Example from the repository root::

    python backend/tools/build_pilot_community_geography.py \
        --boundaries-zip PATH/meteofriul-Limiti01012026.zip \
        --output .dev-logs/local-weather-pilot/community-geography.sqlite3

The 2026 ISTAT source is verified by SHA-256 before parsing. The generated
artifact is local pilot data, not a production or cloud configuration change.
"""

from __future__ import annotations

import argparse
from array import array
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile
from zipfile import ZipFile
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.services.national_municipalities import get_default_national_municipality_catalog
from app.services.pilot_community_geography import (
    BOUNDARIES_PROJECTION_SHA256,
    BOUNDARIES_SOURCE_SHA256,
    BOUNDARIES_SOURCE_URL,
    GEOGRAPHY_SCHEMA,
    _contains_point,
    _pack_rings,
)
from experiments.weather_autonomy.national_catalog import (
    BOUNDARY_COMPONENTS,
    _interior_point,
    _read_dbf_records,
    sha256_file,
)

BOUNDARIES_BASE = "Com01012026/Com01012026_WGS84"


def _shape_records(stream):
    header = stream.read(100)
    if len(header) != 100 or struct.unpack_from(">I", header)[0] != 9994:
        raise ValueError("invalid ISTAT shapefile header")
    while record_header := stream.read(8):
        if len(record_header) != 8:
            raise ValueError("truncated ISTAT shapefile record")
        _, length_words = struct.unpack(">II", record_header)
        body = stream.read(length_words * 2)
        if len(body) != length_words * 2 or len(body) < 44 or struct.unpack_from("<I", body)[0] != 5:
            raise ValueError("invalid ISTAT polygon record")
        parts, points = struct.unpack_from("<II", body, 36)
        if parts < 1 or points < 4 or len(body) != 44 + parts * 4 + points * 16:
            raise ValueError("invalid ISTAT polygon parts")
        offsets = struct.unpack_from(f"<{parts}I", body, 44) + (points,)
        if offsets[0] != 0 or any(b - a < 4 for a, b in zip(offsets, offsets[1:])):
            raise ValueError("invalid ISTAT ring offsets")
        coordinates = array("d")
        coordinates.frombytes(body[44 + parts * 4:])
        if sys.byteorder != "little":
            coordinates.byteswap()
        yield tuple(coordinates[start * 2:end * 2] for start, end in zip(offsets, offsets[1:]))


def _transform_rings(rings, transformer):
    transformed = []
    for ring in rings:
        longitudes, latitudes = transformer.transform(ring[::2], ring[1::2], errcheck=True)
        output = array("d")
        for longitude, latitude in zip(longitudes, latitudes):
            output.extend((longitude, latitude))
        transformed.append(output)
    return tuple(transformed)


def build(boundaries_zip: Path, output: Path) -> dict:
    from pyproj import Transformer, __version__ as pyproj_version

    if output.exists():
        raise ValueError("output already exists; builder never overwrites pilot geography")
    if sha256_file(boundaries_zip) != BOUNDARIES_SOURCE_SHA256:
        raise ValueError("ISTAT boundary archive differs from reviewed source")
    catalog = get_default_national_municipality_catalog()
    code_map = {
        component: item.istat_code
        for item in catalog.municipalities
        for component in BOUNDARY_COMPONENTS.get(item.istat_code, (item.istat_code,))
    }
    transformer = Transformer.from_crs(32632, 4326, always_xy=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(prefix="community-geography-", suffix=".sqlite3", dir=output.parent, delete=False)
    temporary.close()
    temporary_path = Path(temporary.name)
    seen = set()
    merged = {}
    total_vertices = 0
    corrected_points = []
    try:
        with closing(sqlite3.connect(temporary_path)) as connection, ZipFile(boundaries_zip) as archive:
            if hashlib.sha256(archive.read(BOUNDARIES_BASE + ".prj")).hexdigest() != BOUNDARIES_PROJECTION_SHA256:
                raise ValueError("ISTAT boundary CRS differs from reviewed EPSG:32632")
            identities = _read_dbf_records(archive.read(BOUNDARIES_BASE + ".dbf"))
            if {identity["PRO_COM_T"] for identity in identities} != set(code_map):
                raise ValueError("boundary and canonical registry identities differ")
            connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute(
                "CREATE TABLE municipalities (istat_code TEXT PRIMARY KEY, "
                "min_lon REAL NOT NULL, min_lat REAL NOT NULL, max_lon REAL NOT NULL, max_lat REAL NOT NULL, "
                "public_latitude REAL NOT NULL, public_longitude REAL NOT NULL, "
                "geometry BLOB NOT NULL, geometry_sha256 TEXT NOT NULL)"
            )

            def insert(code, source_rings):
                nonlocal total_vertices
                identity = catalog.match_istat(code)
                rings = _transform_rings(source_rings, transformer)
                total_vertices += sum(len(ring) // 2 for ring in rings)
                latitude, longitude = identity.representative_coordinates
                if not _contains_point(rings, latitude, longitude):
                    # The generalized catalog point can fall just outside a
                    # narrow original boundary. Derive a fixed interior point
                    # from that same official polygon, never from device GPS.
                    source_pairs = tuple(tuple(zip(ring[::2], ring[1::2])) for ring in source_rings)
                    easting, northing, _ = _interior_point(source_pairs)
                    longitude, latitude = transformer.transform(easting, northing, errcheck=True)
                    if not _contains_point(rings, latitude, longitude):
                        raise ValueError(f"cannot verify public representative point for {code}")
                    corrected_points.append(code)
                geometry = _pack_rings(rings)
                connection.execute(
                    "INSERT INTO municipalities VALUES (?,?,?,?,?,?,?,?,?)",
                    (code, min(min(ring[::2]) for ring in rings), min(min(ring[1::2]) for ring in rings),
                     max(max(ring[::2]) for ring in rings), max(max(ring[1::2]) for ring in rings),
                     latitude, longitude, zlib.compress(geometry, 6), hashlib.sha256(geometry).hexdigest()),
                )

            with archive.open(BOUNDARIES_BASE + ".shp") as stream:
                count = 0
                for index, rings in enumerate(_shape_records(stream)):
                    if index >= len(identities):
                        raise ValueError("ISTAT shapefile has excess records")
                    source_code = identities[index]["PRO_COM_T"]
                    if source_code in seen:
                        raise ValueError("duplicate ISTAT geometry")
                    seen.add(source_code)
                    code = code_map[source_code]
                    if code in BOUNDARY_COMPONENTS:
                        merged.setdefault(code, []).extend(rings)
                    else:
                        insert(code, rings)
                    count += 1
                if count != len(identities):
                    raise ValueError("ISTAT shapefile and DBF counts differ")
            for code, rings in merged.items():
                insert(code, tuple(rings))
            count = connection.execute("SELECT count(*) FROM municipalities").fetchone()[0]
            if count != len(catalog.municipalities):
                raise ValueError("incomplete national Community boundary coverage")
            connection.execute("CREATE INDEX municipality_bbox ON municipalities (min_lon, max_lon, min_lat, max_lat)")
            metadata = {
                "schema": GEOGRAPHY_SCHEMA,
                "source_sha256": BOUNDARIES_SOURCE_SHA256,
                "source_url": BOUNDARIES_SOURCE_URL,
                "source_date": "2026-01-01",
                "license": "CC BY 4.0",
                "catalog_sha256": catalog.catalog_sha256,
                "crs": "EPSG:4326",
                "geometry_policy": "non_generalized_no_simplification",
                "pyproj_version": pyproj_version,
                "public_point_policy": "canonical_representative_point_verified_inside_non_generalized_boundary",
                "public_points_rederived_from_non_generalized_boundary": json.dumps(corrected_points),
                "boundary_components": json.dumps(BOUNDARY_COMPONENTS, sort_keys=True),
            }
            connection.executemany("INSERT INTO metadata VALUES (?, ?)", sorted(metadata.items()))
            connection.commit()
        # Windows rename is create-only; explicitly check also for POSIX.
        if output.exists():
            raise ValueError("output appeared while building pilot geography")
        os.link(temporary_path, output)
        return {"output": str(output), "municipalities": count, "vertices": total_vertices,
                "bytes": output.stat().st_size, "sha256": sha256_file(output),
                "public_points_rederived": corrected_points}
    finally:
        temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundaries-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.boundaries_zip, arguments.output), ensure_ascii=False))
