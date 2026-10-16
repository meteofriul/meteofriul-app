"""Offline national geography for the isolated Community pilot only.

The optional SQLite artifact is built from the reviewed, non-generalized ISTAT
2026 boundaries by ``backend/tools/build_pilot_community_geography.py``. Runtime
lookups never call a geocoder, download a dataset, or guess a nearby Comune.
Only candidate geometries are decompressed; the entire country is not held in
memory. Public report coordinates are fixed municipal representative points,
not the submitting device's GPS coordinates.
"""

from __future__ import annotations

from array import array
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import math
import os
from pathlib import Path
import sqlite3
import struct
import sys
import threading
from typing import Any
import zlib

from app.services.national_municipalities import (
    NationalMunicipalityCatalog,
    get_default_national_municipality_catalog,
    normalize_municipality_identity,
)


GEOGRAPHY_SCHEMA = "meteofriul.pilot.community_geography.v1"
BOUNDARIES_SOURCE_URL = (
    "https://www.istat.it/storage/cartografia/confini_amministrativi/"
    "non_generalizzati/2026/Limiti01012026.zip"
)
BOUNDARIES_SOURCE_SHA256 = (
    "a9075f8d839dcb2b409099703da7bdd37cc214f8967fa7372b32305875ad046f"
)
BOUNDARIES_PROJECTION_SHA256 = (
    "10a2674d7bc43a70df19daf98d0b1deb3f5222f03659e1b4d82b395c20177cb9"
)
PILOT_GEOGRAPHY_ARTIFACT_SHA256 = (
    "1eb9e8dd66759b36a8d1dc59da824493e43c500428ce875127ed863691ce006e"
)
MAX_GEOMETRY_BYTES = 16 * 1024 * 1024


class PilotCommunityGeographyUnavailable(RuntimeError):
    """The pilot's reviewed national boundaries are missing or invalid."""


@dataclass(frozen=True, slots=True)
class PilotCommunityMunicipality:
    slug: str
    name: str
    admin1: str
    province: str
    province_name: str
    istat_code: str
    latitude: float
    longitude: float
    region_iso: str


def _valid_point(latitude: Any, longitude: Any) -> bool:
    return (
        isinstance(latitude, (int, float))
        and not isinstance(latitude, bool)
        and isinstance(longitude, (int, float))
        and not isinstance(longitude, bool)
        and math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def _distance_km(latitude: float, longitude: float, other_lat: float, other_lon: float) -> float:
    lat1, lat2 = math.radians(latitude), math.radians(other_lat)
    haversine = (
        math.sin(math.radians(other_lat - latitude) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(math.radians(other_lon - longitude) / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, haversine)))


def _pack_rings(rings: tuple[array, ...]) -> bytes:
    """Stable little-endian geometry encoding, shared with the offline builder."""
    output = bytearray(struct.pack("<I", len(rings)))
    for ring in rings:
        output.extend(struct.pack("<I", len(ring) // 2))
        coordinates = array("d", ring)
        if sys.byteorder != "little":
            coordinates.byteswap()
        output.extend(coordinates.tobytes())
    return bytes(output)


def _unpack_rings(payload: bytes) -> tuple[array, ...]:
    if len(payload) < 4 or len(payload) > MAX_GEOMETRY_BYTES:
        raise PilotCommunityGeographyUnavailable("pilot municipality geometry size is invalid")
    count = struct.unpack_from("<I", payload)[0]
    offset = 4
    rings = []
    for _ in range(count):
        if offset + 4 > len(payload):
            raise PilotCommunityGeographyUnavailable("pilot municipality geometry is truncated")
        points = struct.unpack_from("<I", payload, offset)[0]
        offset += 4
        end = offset + points * 16
        if points < 4 or end > len(payload):
            raise PilotCommunityGeographyUnavailable("pilot municipality ring is invalid")
        ring = array("d")
        ring.frombytes(payload[offset:end])
        if sys.byteorder != "little":
            ring.byteswap()
        if (
            not all(math.isfinite(value) for value in ring)
            or ring[:2] != ring[-2:]
            or any(not -180 <= value <= 180 for value in ring[::2])
            or any(not -90 <= value <= 90 for value in ring[1::2])
        ):
            raise PilotCommunityGeographyUnavailable("pilot municipality ring coordinates are invalid")
        rings.append(ring)
        offset = end
    if not rings or offset != len(payload):
        raise PilotCommunityGeographyUnavailable("pilot municipality geometry encoding is invalid")
    return tuple(rings)


def _contains_point(rings: tuple[array, ...], latitude: float, longitude: float) -> bool:
    """Even/odd containment supports exterior rings, holes and multipart shapes.

    Boundary points are candidates too. If two municipalities share that point,
    the public resolver rejects the ambiguous result instead of choosing one.
    """
    inside = False
    tolerance = 1e-11
    for ring in rings:
        x1, y1 = ring[-2:]
        for index in range(0, len(ring), 2):
            x2, y2 = ring[index], ring[index + 1]
            dx, dy = x2 - x1, y2 - y1
            if (
                min(x1, x2) - tolerance <= longitude <= max(x1, x2) + tolerance
                and min(y1, y2) - tolerance <= latitude <= max(y1, y2) + tolerance
                and abs((longitude - x1) * dy - (latitude - y1) * dx)
                <= tolerance * max(math.hypot(dx, dy), tolerance)
            ):
                return True
            if (y1 > latitude) != (y2 > latitude):
                if longitude < dx * (latitude - y1) / dy + x1:
                    inside = not inside
            x1, y1 = x2, y2
    return inside


class PilotCommunityGeographyCatalog:
    """Immutable national identities and fail-closed polygon containment."""

    def __init__(
        self,
        data_path: Path | str | None = None,
        *,
        catalog: NationalMunicipalityCatalog | None = None,
    ) -> None:
        default_path = (
            Path(__file__).resolve().parents[3]
            / ".dev-logs" / "local-weather-pilot" / "community-geography.sqlite3"
        )
        self.data_path = Path(
            data_path or os.environ.get("PILOT_COMMUNITY_GEOGRAPHY_PATH") or default_path
        ).resolve()
        self.catalog = catalog or get_default_national_municipality_catalog()
        self._expected_artifact_sha256 = PILOT_GEOGRAPHY_ARTIFACT_SHA256 if catalog is None else None
        self._by_istat: dict[str, PilotCommunityMunicipality] | None = None
        self._load_lock = threading.Lock()

    @contextmanager
    def _connect(self):
        connection = None
        try:
            connection = sqlite3.connect(self.data_path.as_uri() + "?mode=ro&immutable=1", uri=True)
            connection.execute("PRAGMA query_only = ON")
            yield connection
        except sqlite3.Error as error:
            raise PilotCommunityGeographyUnavailable(
                "pilot national municipality boundaries are unavailable"
            ) from error
        finally:
            if connection is not None:
                connection.close()

    def _load(self) -> dict[str, PilotCommunityMunicipality]:
        if self._by_istat is not None:
            return self._by_istat
        with self._load_lock:
            if self._by_istat is not None:
                return self._by_istat
            try:
                if self._expected_artifact_sha256 is not None:
                    with self.data_path.open("rb") as stream:
                        observed_digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    if observed_digest != self._expected_artifact_sha256:
                        raise PilotCommunityGeographyUnavailable("pilot boundary artifact checksum is invalid")
                with self._connect() as connection:
                    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
                    rows = connection.execute(
                        "SELECT istat_code, public_latitude, public_longitude FROM municipalities"
                    ).fetchall()
                if (
                    metadata.get("schema") != GEOGRAPHY_SCHEMA
                    or metadata.get("source_sha256") != BOUNDARIES_SOURCE_SHA256
                    or metadata.get("catalog_sha256") != self.catalog.catalog_sha256
                    or metadata.get("crs") != "EPSG:4326"
                    or metadata.get("geometry_policy") != "non_generalized_no_simplification"
                ):
                    raise PilotCommunityGeographyUnavailable("pilot boundary provenance is invalid")
                expected_codes = {item.istat_code for item in self.catalog.municipalities}
                if {row[0] for row in rows} != expected_codes or len(rows) != len(expected_codes):
                    raise PilotCommunityGeographyUnavailable("pilot boundary municipality coverage is incomplete")
                municipalities = {}
                for code, latitude, longitude in rows:
                    identity = self.catalog.match_istat(code)
                    if identity is None or not _valid_point(latitude, longitude):
                        raise PilotCommunityGeographyUnavailable("pilot municipality identity is invalid")
                    municipalities[code] = PilotCommunityMunicipality(
                        slug="-".join(normalize_municipality_identity(identity.name).split()),
                        name=identity.name,
                        admin1=identity.region_name,
                        province=identity.province_code,
                        province_name=identity.province_name,
                        istat_code=code,
                        latitude=latitude,
                        longitude=longitude,
                        region_iso=identity.region_iso,
                    )
            except (sqlite3.Error, OSError, ValueError) as error:
                raise PilotCommunityGeographyUnavailable("pilot national geography cannot be loaded") from error
            self._by_istat = municipalities
            return municipalities

    @property
    def municipalities(self) -> tuple[PilotCommunityMunicipality, ...]:
        return tuple(self._load().values())

    def match_istat(self, value: Any) -> PilotCommunityMunicipality | None:
        identity = self.catalog.match_istat(value)
        return self._load().get(identity.istat_code) if identity is not None else None

    def match_name(self, name: Any, province: Any = None) -> PilotCommunityMunicipality | None:
        identity = self.catalog.match_name(name, province=province)
        return self._load().get(identity.istat_code) if identity is not None else None

    @lru_cache(maxsize=128)
    def _geometry(self, istat_code: str) -> tuple[array, ...]:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT geometry, geometry_sha256 FROM municipalities WHERE istat_code = ?",
                    (istat_code,),
                ).fetchone()
            if row is None:
                raise PilotCommunityGeographyUnavailable("pilot municipality geometry is absent")
            decoder = zlib.decompressobj()
            payload = decoder.decompress(row[0], MAX_GEOMETRY_BYTES + 1)
            if not decoder.eof or decoder.unused_data or hashlib.sha256(payload).hexdigest() != row[1]:
                raise PilotCommunityGeographyUnavailable("pilot municipality geometry checksum is invalid")
            return _unpack_rings(payload)
        except (sqlite3.Error, zlib.error) as error:
            raise PilotCommunityGeographyUnavailable("pilot municipality geometry cannot be read") from error

    def resolve_municipality(self, latitude: float, longitude: float) -> PilotCommunityMunicipality | None:
        if not _valid_point(latitude, longitude):
            return None
        municipalities = self._load()
        try:
            with self._connect() as connection:
                candidates = connection.execute(
                    "SELECT istat_code FROM municipalities "
                    "WHERE min_lon <= ? AND max_lon >= ? AND min_lat <= ? AND max_lat >= ?",
                    (longitude, longitude, latitude, latitude),
                ).fetchall()
        except sqlite3.Error as error:
            raise PilotCommunityGeographyUnavailable("pilot boundary index cannot be read") from error
        matches = [code for (code,) in candidates if _contains_point(self._geometry(code), latitude, longitude)]
        return municipalities[matches[0]] if len(matches) == 1 else None

    def resolve_municipality_istat(self, latitude: float, longitude: float) -> str | None:
        municipality = self.resolve_municipality(latitude, longitude)
        return municipality.istat_code if municipality else None

    def nearby_municipalities(
        self, latitude: float, longitude: float, radius_km: float = 30, limit: int = 8
    ) -> tuple[PilotCommunityMunicipality, ...]:
        """Explicit suggestions only; never used as a containment fallback."""
        if (
            not _valid_point(latitude, longitude)
            or not isinstance(radius_km, (int, float))
            or not math.isfinite(radius_km)
            or not 0 < radius_km <= 100
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            return ()
        nearby = []
        for municipality in self.municipalities:
            distance = _distance_km(latitude, longitude, municipality.latitude, municipality.longitude)
            if distance <= radius_km:
                nearby.append((distance, municipality.istat_code, municipality))
        nearby.sort(key=lambda value: (value[0], value[1]))
        return tuple(item[2] for item in nearby[:limit])


@lru_cache(maxsize=1)
def get_default_pilot_community_geography_catalog() -> PilotCommunityGeographyCatalog:
    return PilotCommunityGeographyCatalog()
