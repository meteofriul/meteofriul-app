from __future__ import annotations

import json
import math
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence


FVG_GEOGRAPHY_SCHEMA_VERSION = "fvg-geography.v1"
DEFAULT_LOCALITY_MAX_DISTANCE_KM = 1.0
DEFAULT_LOCALITY_NEAREST_MAX_DISTANCE_KM = 0.35
DEFAULT_LOCALITY_NEAREST_SAFETY_MARGIN_M = 10.0
MUNICIPALITY_SOURCE_ID = "istat_boundaries"
LOCALITY_SOURCE_ID = "rafvg_irdat_5000"


def _normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    without_marks = "".join(
        character for character in text if unicodedata.category(character) != "Mn"
    )
    return " ".join(without_marks.casefold().strip().split())


def _haversine_km(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> float:
    radius_km = 6371.0088
    first_lat = math.radians(first_latitude)
    second_lat = math.radians(second_latitude)
    delta_lat = math.radians(second_latitude - first_latitude)
    delta_lon = math.radians(second_longitude - first_longitude)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(first_lat) * math.cos(second_lat) * math.sin(delta_lon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(
        math.sqrt(haversine),
        math.sqrt(max(0.0, 1 - haversine)),
    )


def _point_on_segment(
    longitude: float,
    latitude: float,
    first: Sequence[float],
    second: Sequence[float],
    tolerance: float = 1e-10,
) -> bool:
    first_lon, first_lat = float(first[0]), float(first[1])
    second_lon, second_lat = float(second[0]), float(second[1])
    cross = (
        (longitude - first_lon) * (second_lat - first_lat)
        - (latitude - first_lat) * (second_lon - first_lon)
    )
    if abs(cross) > tolerance:
        return False
    return (
        min(first_lon, second_lon) - tolerance
        <= longitude
        <= max(first_lon, second_lon) + tolerance
        and min(first_lat, second_lat) - tolerance
        <= latitude
        <= max(first_lat, second_lat) + tolerance
    )


def _point_in_ring(
    longitude: float,
    latitude: float,
    ring: Sequence[Sequence[float]],
) -> bool:
    if len(ring) < 4:
        return False
    inside = False
    previous = ring[-1]
    for current in ring:
        if _point_on_segment(longitude, latitude, previous, current):
            return True
        first_lon, first_lat = float(previous[0]), float(previous[1])
        second_lon, second_lat = float(current[0]), float(current[1])
        if (first_lat > latitude) != (second_lat > latitude):
            intersection = (
                (second_lon - first_lon)
                * (latitude - first_lat)
                / (second_lat - first_lat)
                + first_lon
            )
            if longitude < intersection:
                inside = not inside
        previous = current
    return inside


def _point_in_polygons(
    longitude: float,
    latitude: float,
    polygons: Sequence[Sequence[Sequence[Sequence[float]]]],
) -> bool:
    for polygon in polygons:
        if not polygon or not _point_in_ring(longitude, latitude, polygon[0]):
            continue
        if any(_point_in_ring(longitude, latitude, hole) for hole in polygon[1:]):
            continue
        return True
    return False


def _point_to_segment_distance_m(
    longitude: float,
    latitude: float,
    first: Sequence[float],
    second: Sequence[float],
) -> float:
    """Approximate a short WGS84 segment in a local metric plane."""

    earth_radius_m = 6_371_008.8
    latitude_radians = math.radians(latitude)

    def local_xy(point: Sequence[float]) -> tuple[float, float]:
        point_lon, point_lat = float(point[0]), float(point[1])
        return (
            math.radians(point_lon - longitude)
            * math.cos(latitude_radians)
            * earth_radius_m,
            math.radians(point_lat - latitude) * earth_radius_m,
        )

    first_x, first_y = local_xy(first)
    second_x, second_y = local_xy(second)
    delta_x = second_x - first_x
    delta_y = second_y - first_y
    squared_length = delta_x * delta_x + delta_y * delta_y
    if squared_length <= 0:
        return math.hypot(first_x, first_y)
    projection = max(
        0.0,
        min(1.0, -(first_x * delta_x + first_y * delta_y) / squared_length),
    )
    return math.hypot(
        first_x + projection * delta_x,
        first_y + projection * delta_y,
    )


@dataclass(frozen=True)
class FvgLocality:
    id: str
    name: str
    kind: str
    municipality_istat: str
    latitude: float
    longitude: float
    dataset_version: str

    def to_public_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "source": LOCALITY_SOURCE_ID,
            "datasetVersion": self.dataset_version,
        }


@dataclass(frozen=True)
class FvgLocalityResolution:
    """Auditable result of matching one IRDAT locality to a GPS point."""

    locality: FvgLocality | None
    match_method: Literal["name", "nearest"] | None = None
    distance_m: float | None = None
    runner_up_distance_m: float | None = None


@dataclass(frozen=True)
class MunicipalityBoundary:
    istat_code: str
    name: str
    bbox: tuple[float, float, float, float]
    polygons: tuple


class FvgGeographyCatalog:
    """Offline, fail-closed resolver for FVG municipalities and localities."""

    def __init__(self, data_path: Path | None = None) -> None:
        resolved_path = data_path or (
            Path(__file__).resolve().parents[1] / "data" / "fvg_geography.json"
        )
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != FVG_GEOGRAPHY_SCHEMA_VERSION:
            raise ValueError("fvg_geography_schema_invalid")

        self.sources = dict(payload.get("sources") or {})
        municipality_source = dict(self.sources.get("municipalities") or {})
        locality_source = dict(self.sources.get("localities") or {})
        self.municipality_dataset_version = str(
            municipality_source.get("validAt") or ""
        ).strip()
        self.locality_dataset_version = str(
            locality_source.get("edition") or ""
        ).strip()
        if not self.municipality_dataset_version or not self.locality_dataset_version:
            raise ValueError("fvg_geography_source_version_missing")

        boundaries = tuple(
            MunicipalityBoundary(
                istat_code=str(item["istatCode"]),
                name=str(item["name"]),
                bbox=tuple(float(value) for value in item["bbox"]),
                polygons=tuple(item["polygons"]),
            )
            for item in payload.get("municipalities") or []
        )
        localities = tuple(
            FvgLocality(
                id=str(item["id"]),
                name=str(item["name"]),
                kind=str(item["kind"]),
                municipality_istat=str(item["municipalityIstat"]),
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                dataset_version=self.locality_dataset_version,
            )
            for item in payload.get("localities") or []
        )
        if len(boundaries) != int(payload.get("municipalityCount") or 0):
            raise ValueError("fvg_geography_municipality_count_invalid")
        if len(localities) != int(payload.get("localityCount") or 0):
            raise ValueError("fvg_geography_locality_count_invalid")

        boundary_codes = {item.istat_code for item in boundaries}
        if (
            len(boundary_codes) != len(boundaries)
            or any(len(code) != 6 or not code.isdigit() for code in boundary_codes)
        ):
            raise ValueError("fvg_geography_municipality_identity_invalid")
        if any(
            locality.municipality_istat not in boundary_codes
            or not locality.id.strip()
            or not locality.name.strip()
            or not math.isfinite(locality.latitude)
            or not math.isfinite(locality.longitude)
            for locality in localities
        ):
            raise ValueError("fvg_geography_locality_identity_invalid")

        self.boundaries = boundaries
        self.localities = localities
        self._locality_by_id = {item.id: item for item in localities}
        if len(self._locality_by_id) != len(localities):
            raise ValueError("fvg_geography_duplicate_locality_id")
        self._localities_by_name: dict[tuple[str, str], list[FvgLocality]] = {}
        self._localities_by_municipality: dict[str, list[FvgLocality]] = {}
        for locality in localities:
            key = (locality.municipality_istat, _normalize_name(locality.name))
            self._localities_by_name.setdefault(key, []).append(locality)
            self._localities_by_municipality.setdefault(
                locality.municipality_istat,
                [],
            ).append(locality)

    def resolve_municipality_istat(self, latitude: float, longitude: float) -> str | None:
        if not math.isfinite(latitude) or not math.isfinite(longitude):
            return None
        matches = []
        for boundary in self.boundaries:
            min_lon, min_lat, max_lon, max_lat = boundary.bbox
            if not (
                min_lon <= longitude <= max_lon
                and min_lat <= latitude <= max_lat
            ):
                continue
            if _point_in_polygons(longitude, latitude, boundary.polygons):
                matches.append(boundary.istat_code)
        return matches[0] if len(matches) == 1 else None

    def match_locality_id(self, locality_id: Any) -> FvgLocality | None:
        return self._locality_by_id.get(str(locality_id or "").strip())

    def municipality_boundary_distance_m(
        self,
        *,
        municipality_istat: str,
        latitude: float,
        longitude: float,
    ) -> float | None:
        """Return the shortest distance to the matched municipality boundary."""

        if not math.isfinite(latitude) or not math.isfinite(longitude):
            return None
        boundary = next(
            (
                item
                for item in self.boundaries
                if item.istat_code == str(municipality_istat or "")
            ),
            None,
        )
        if boundary is None or not _point_in_polygons(
            longitude,
            latitude,
            boundary.polygons,
        ):
            return None
        distances = []
        for polygon in boundary.polygons:
            for ring in polygon:
                if len(ring) < 2:
                    continue
                previous = ring[-1]
                for current in ring:
                    distances.append(
                        _point_to_segment_distance_m(
                            longitude,
                            latitude,
                            previous,
                            current,
                        )
                    )
                    previous = current
        return min(distances) if distances else None

    def resolve_locality(
        self,
        *,
        municipality_istat: str,
        candidate_names: Iterable[Any],
        latitude: float,
        longitude: float,
        max_distance_km: float = DEFAULT_LOCALITY_MAX_DISTANCE_KM,
    ) -> FvgLocality | None:
        """Backward-compatible exact-name resolver.

        Callers that need to explain the match should use
        :meth:`resolve_locality_resolution`.
        """

        return self.resolve_locality_resolution(
            municipality_istat=municipality_istat,
            candidate_names=candidate_names,
            latitude=latitude,
            longitude=longitude,
            max_name_distance_km=max_distance_km,
            allow_nearest=False,
        ).locality

    def resolve_locality_resolution(
        self,
        *,
        municipality_istat: str,
        candidate_names: Iterable[Any],
        latitude: float,
        longitude: float,
        max_name_distance_km: float = DEFAULT_LOCALITY_MAX_DISTANCE_KM,
        max_nearest_distance_km: float = DEFAULT_LOCALITY_NEAREST_MAX_DISTANCE_KM,
        nearest_accuracy_m: float | None = None,
        allow_nearest: bool = False,
    ) -> FvgLocalityResolution:
        if (
            not math.isfinite(latitude)
            or not math.isfinite(longitude)
            or not math.isfinite(max_name_distance_km)
            or max_name_distance_km <= 0
            or not math.isfinite(max_nearest_distance_km)
            or max_nearest_distance_km <= 0
            or (
                nearest_accuracy_m is not None
                and (
                    not math.isfinite(nearest_accuracy_m)
                    or nearest_accuracy_m < 0
                )
            )
        ):
            return FvgLocalityResolution(locality=None)

        municipality_localities = self._localities_by_municipality.get(
            municipality_istat,
            (),
        )
        ranked_all = sorted(
            (
                _haversine_km(
                    latitude,
                    longitude,
                    locality.latitude,
                    locality.longitude,
                ),
                locality.id,
                locality,
            )
            for locality in municipality_localities
        )

        matches: dict[str, FvgLocality] = {}
        normalized_candidates: set[str] = set()
        for candidate_name in candidate_names:
            normalized = _normalize_name(candidate_name)
            if not normalized:
                continue
            normalized_candidates.add(normalized)
            for locality in self._localities_by_name.get(
                (municipality_istat, normalized),
                [],
            ):
                matches[locality.id] = locality

        match_method: Literal["name", "nearest"] | None = None
        selected: tuple[float, str, FvgLocality] | None = None
        if matches:
            ranked_matches = sorted(
                item for item in ranked_all if item[2].id in matches
            )
            if ranked_matches and ranked_matches[0][0] <= max_name_distance_km:
                selected = ranked_matches[0]
                match_method = "name"
        elif (
            not normalized_candidates
            and allow_nearest
            and nearest_accuracy_m is not None
            and ranked_all
        ):
            nearest = ranked_all[0]
            normalized_nearest_name = _normalize_name(nearest[2].name)
            nearest_runner_up = next(
                (
                    item
                    for item in ranked_all
                    if _normalize_name(item[2].name) != normalized_nearest_name
                ),
                None,
            )
            ambiguity_gap_m = (
                (nearest_runner_up[0] - nearest[0]) * 1000
                if nearest_runner_up is not None
                else None
            )
            minimum_gap_m = 2 * (
                nearest_accuracy_m + DEFAULT_LOCALITY_NEAREST_SAFETY_MARGIN_M
            )
            maximum_enveloped_distance_m = max_nearest_distance_km * 1000
            uncertainty_enveloped_distance_m = (
                nearest[0] * 1000
                + nearest_accuracy_m
                + DEFAULT_LOCALITY_NEAREST_SAFETY_MARGIN_M
            )
            within_distance_gate = (
                uncertainty_enveloped_distance_m <= maximum_enveloped_distance_m
            )
            if (
                ambiguity_gap_m is not None
                and within_distance_gate
                and ambiguity_gap_m > minimum_gap_m
            ):
                selected = nearest
                match_method = "nearest"

        # An explicit but uncorroborated Nominatim candidate must never fall
        # through to the spatial fallback.  It is safer to expose only the
        # municipality in that case.
        if selected is None or match_method is None:
            return FvgLocalityResolution(locality=None)

        distance_km, _, locality = selected
        normalized_selected_name = _normalize_name(locality.name)
        runner_up = next(
            (
                item
                for item in ranked_all
                if _normalize_name(item[2].name) != normalized_selected_name
            ),
            None,
        )
        return FvgLocalityResolution(
            locality=locality,
            match_method=match_method,
            distance_m=distance_km * 1000,
            runner_up_distance_m=(runner_up[0] * 1000 if runner_up else None),
        )


@lru_cache(maxsize=1)
def get_default_fvg_geography_catalog() -> FvgGeographyCatalog:
    return FvgGeographyCatalog()


__all__ = [
    "DEFAULT_LOCALITY_MAX_DISTANCE_KM",
    "DEFAULT_LOCALITY_NEAREST_MAX_DISTANCE_KM",
    "DEFAULT_LOCALITY_NEAREST_SAFETY_MARGIN_M",
    "FVG_GEOGRAPHY_SCHEMA_VERSION",
    "LOCALITY_SOURCE_ID",
    "MUNICIPALITY_SOURCE_ID",
    "FvgGeographyCatalog",
    "FvgLocality",
    "FvgLocalityResolution",
    "MunicipalityBoundary",
    "get_default_fvg_geography_catalog",
]
