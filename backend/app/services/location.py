from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from app.contracts.location import (
    LocationSearchItem,
    ReverseLocationDataPoint,
    ReverseLocationLocality,
    ReverseLocationMunicipality,
    ReverseLocationResolution,
    ReverseLocationResponse,
)
from app.services.fvg_geography import (
    FvgGeographyCatalog,
    FvgLocalityResolution,
    MUNICIPALITY_SOURCE_ID,
    get_default_fvg_geography_catalog,
)


FVG_REGION_LABEL = "Friuli Venezia Giulia"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "Meteo-Friul-App/3.0 (+https://meteofriul.it)"
LOCATION_SEARCH_CACHE_TTL_SECONDS = 24 * 60 * 60
LOCATION_SEARCH_CACHE_MAX_ITEMS = 512
LOCATION_SEARCH_DEFAULT_TIMEOUT_SECONDS = 6.0
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
NOMINATIM_CACHE_MAX_ITEMS = 2048
NOMINATIM_MIN_REQUEST_INTERVAL_SECONDS = 1.05
NOMINATIM_COORDINATE_DECIMALS = 3
MAX_EXTERNAL_CANONICAL_DISTANCE_KM = 80
MAX_LOCATION_RESULTS = 8
# Broad prefixes can fill the local catalog alone. Keep a small national lane
# while preserving the FVG-first ordering and the historical response bound.
NATIONAL_LOCATION_RESULT_RESERVE = 3
LOCATION_SEARCH_DEDUPLICATION_DISTANCE_KM = 10
LOCALITY_ADDRESS_FIELDS = (
    "city",
    "town",
    "village",
    "hamlet",
    "suburb",
    "quarter",
    "neighbourhood",
    "city_district",
    "borough",
    "locality",
    "isolated_dwelling",
)
SUPRALOCAL_ADDRESS_TYPES = frozenset({
    "continent",
    "country",
    "region",
    "state",
    "state_district",
    "province",
    "county",
})

MAIN_PLACE_PRIORITY = {
    "udine": 1000,
    "trieste": 980,
    "pordenone": 960,
    "gorizia": 940,
    "monfalcone": 860,
    "sacile": 820,
    "codroipo": 800,
    "cividale del friuli": 780,
    "gemona del friuli": 760,
    "tolmezzo": 740,
    "tarvisio": 720,
    "lignano sabbiadoro": 700,
    "grado": 680,
    "spilimbergo": 660,
    "palmanova": 640,
    "cordenons": 620,
    "san vito al tagliamento": 600,
}


class NominatimRequestGate:
    """Serialize all public Nominatim traffic and enforce its request cadence."""

    def __init__(self, minimum_interval_seconds: float) -> None:
        self.minimum_interval_seconds = minimum_interval_seconds
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def __enter__(self) -> None:
        self._lock.acquire()
        wait_seconds = self.minimum_interval_seconds - (
            time.monotonic() - self._last_request_at
        )
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self._last_request_at = time.monotonic()
        self._lock.release()


NOMINATIM_REQUEST_GATE = NominatimRequestGate(
    NOMINATIM_MIN_REQUEST_INTERVAL_SECONDS
)


class LocationSourceUnavailable(RuntimeError):
    """Raised when reverse geocoding cannot provide a trustworthy result."""


class LocationSearchSourceUnavailable(RuntimeError):
    """Raised when national locality search cannot be reached or decoded."""


@dataclass(frozen=True)
class Municipality:
    slug: str
    name: str
    admin1: str
    province: str
    province_name: str
    istat_code: str
    latitude: float
    longitude: float

    def to_search_item(self) -> LocationSearchItem:
        return LocationSearchItem(
            name=self.name,
            admin1=self.admin1,
            latitude=self.latitude,
            longitude=self.longitude,
            population=0,
            province=self.province,
            provinceName=self.province_name,
            istatCode=self.istat_code,
            country="Italia",
            countryCode="IT",
            provider="fvg_catalog",
            providerId=self.istat_code,
        )

def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    without_marks = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return " ".join(without_marks.strip().lower().split())


def is_fvg_region(value: Any) -> bool:
    normalized = normalize_text(value).replace("-", " ")
    return "friuli" in normalized and "giulia" in normalized


def locality_candidate_names(address: dict[str, Any]) -> tuple[str, ...]:
    candidates: list[str] = []
    seen: set[str] = set()
    for field in LOCALITY_ADDRESS_FIELDS:
        value = str(address.get(field) or "").strip()
        # Nominatim commonly returns the Italian and Friulian names in one
        # field (for example ``Vigonovo / Vinuf``).  Keep the full label for
        # diagnostics, but also expose each language variant to the official
        # IRDAT-name corroborator.  The municipality and distance gates still
        # decide whether a variant is safe to use.
        for candidate in (value, *(part.strip() for part in value.split("/"))):
            normalized = normalize_text(candidate)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(candidate)
    return tuple(candidates)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    first_lat = math.radians(lat1)
    second_lat = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(first_lat) * math.cos(second_lat) * math.sin(delta_lon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def search_results_match(
    first: LocationSearchItem,
    second: LocationSearchItem,
) -> bool:
    if normalize_text(first.name) != normalize_text(second.name):
        return False
    if first.istatCode and second.istatCode:
        return first.istatCode == second.istatCode
    if (
        first.province and second.province
        and normalize_text(first.province) != normalize_text(second.province)
    ):
        return False

    first_region = normalize_text(first.admin1).replace("-", " ")
    second_region = normalize_text(second.admin1).replace("-", " ")
    if is_fvg_region(first.admin1):
        first_region = normalize_text(FVG_REGION_LABEL)
    if is_fvg_region(second.admin1):
        second_region = normalize_text(FVG_REGION_LABEL)
    if first_region and second_region and first_region != second_region:
        return False

    return haversine_km(
        first.latitude,
        first.longitude,
        second.latitude,
        second.longitude,
    ) <= LOCATION_SEARCH_DEDUPLICATION_DISTANCE_KM


class LocationCatalog:
    def __init__(self, data_path: Path | None = None) -> None:
        resolved_path = data_path or Path(__file__).resolve().parents[1] / "data" / "fvg_municipalities.json"
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        records = payload.get("municipalities") or []
        expected_count = int((payload.get("source") or {}).get("count") or 0)

        self.municipalities = tuple(
            Municipality(
                slug=str(record["slug"]),
                name=str(record["name"]),
                admin1=str(record.get("admin1") or FVG_REGION_LABEL),
                province=str(record["province"]),
                province_name=str(record["provinceName"]),
                istat_code=str(record["istatCode"]),
                latitude=float(record["latitude"]),
                longitude=float(record["longitude"]),
            )
            for record in records
        )

        if not self.municipalities or len(self.municipalities) != expected_count:
            raise ValueError(
                f"Catalogo Comuni incoerente: attesi {expected_count}, trovati {len(self.municipalities)}"
            )

        self._by_name = {
            normalize_text(municipality.name): municipality
            for municipality in self.municipalities
        }
        self._by_slug = {
            normalize_text(municipality.slug.replace("-", " ")): municipality
            for municipality in self.municipalities
        }
        self._by_istat = {
            municipality.istat_code: municipality
            for municipality in self.municipalities
        }

    @staticmethod
    def _matches(municipality: Municipality, clean_query: str) -> bool:
        name = normalize_text(municipality.name)
        slug = normalize_text(municipality.slug.replace("-", " "))
        province = normalize_text(municipality.province)
        compact_name = name.replace(" ", "")
        compact_query = clean_query.replace(" ", "")

        return (
            clean_query in slug
            or clean_query in name
            or compact_query in compact_name
            or slug in clean_query
            or province == clean_query
        )

    @staticmethod
    def _score(municipality: Municipality, clean_query: str) -> float:
        name = normalize_text(municipality.name)
        slug = normalize_text(municipality.slug.replace("-", " "))
        province = normalize_text(municipality.province)
        compact_name = name.replace(" ", "")
        compact_query = clean_query.replace(" ", "")
        word_starts = any(part.startswith(clean_query) for part in name.split(" "))
        match_priority = 0

        if name == clean_query or compact_name == compact_query:
            match_priority = 10000
        elif name.startswith(clean_query) or compact_name.startswith(compact_query):
            match_priority = 9000
        elif word_starts:
            match_priority = 8400
        elif slug.startswith(clean_query):
            match_priority = 8200
        elif clean_query in name:
            match_priority = 7000
        elif compact_query in compact_name:
            match_priority = 6600
        elif province == clean_query:
            match_priority = 8000
        elif slug in clean_query:
            match_priority = 2600

        return match_priority + MAIN_PLACE_PRIORITY.get(name, 0)

    def search(self, query: str, limit: int = MAX_LOCATION_RESULTS) -> list[LocationSearchItem]:
        clean_query = normalize_text(query)
        if len(clean_query) < 2:
            return []

        matches = [
            municipality
            for municipality in self.municipalities
            if self._matches(municipality, clean_query)
        ]
        matches.sort(
            key=lambda municipality: (
                -self._score(municipality, clean_query),
                normalize_text(municipality.name),
            )
        )
        return [municipality.to_search_item() for municipality in matches[:limit]]

    def match_names(self, *values: Any) -> Municipality | None:
        for value in values:
            normalized = normalize_text(value)
            if not normalized:
                continue
            municipality = self._by_name.get(normalized) or self._by_slug.get(normalized)
            if municipality:
                return municipality
        return None

    def match_istat(self, value: Any) -> Municipality | None:
        return self._by_istat.get(str(value or "").strip())

    def nearest(self, lat: float, lon: float) -> tuple[Municipality, float]:
        municipality = min(
            self.municipalities,
            key=lambda item: haversine_km(lat, lon, item.latitude, item.longitude),
        )
        return municipality, haversine_km(lat, lon, municipality.latitude, municipality.longitude)


class NominatimLocationSearchSource:
    def __init__(
        self,
        session: requests.Session | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout_seconds = self._resolve_timeout(timeout_seconds)
        self._cache: dict[
            tuple[str, int],
            tuple[float, tuple[LocationSearchItem, ...]],
        ] = {}
        self._cache_lock = threading.Lock()

    @staticmethod
    def _resolve_timeout(timeout_seconds: float | None) -> float:
        raw_timeout: Any = (
            timeout_seconds
            if timeout_seconds is not None
            else os.getenv(
                "LOCATION_SEARCH_TIMEOUT_SECONDS",
                str(LOCATION_SEARCH_DEFAULT_TIMEOUT_SECONDS),
            )
        )
        try:
            parsed_timeout = float(raw_timeout)
        except (TypeError, ValueError):
            parsed_timeout = LOCATION_SEARCH_DEFAULT_TIMEOUT_SECONDS
        if not math.isfinite(parsed_timeout):
            parsed_timeout = LOCATION_SEARCH_DEFAULT_TIMEOUT_SECONDS
        return min(max(parsed_timeout, 1.0), 15.0)

    @staticmethod
    def _copy_results(
        results: tuple[LocationSearchItem, ...],
    ) -> list[LocationSearchItem]:
        return [item.model_copy(deep=True) for item in results]

    def _read_cache(
        self,
        key: tuple[str, int],
    ) -> list[LocationSearchItem] | None:
        now = time.monotonic()
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached is None:
                return None
            stored_at, results = cached
            if now - stored_at > LOCATION_SEARCH_CACHE_TTL_SECONDS:
                self._cache.pop(key, None)
                return None
            return self._copy_results(results)

    def _write_cache(
        self,
        key: tuple[str, int],
        results: list[LocationSearchItem],
    ) -> None:
        with self._cache_lock:
            if (
                key not in self._cache
                and len(self._cache) >= LOCATION_SEARCH_CACHE_MAX_ITEMS
            ):
                oldest_key = min(self._cache, key=lambda item: self._cache[item][0])
                self._cache.pop(oldest_key, None)
            self._cache[key] = (
                time.monotonic(),
                tuple(item.model_copy(deep=True) for item in results),
            )

    @staticmethod
    def _is_supralocal_result(payload: dict[str, Any]) -> bool:
        address_type = normalize_text(payload.get("addresstype"))
        place_type = normalize_text(payload.get("type"))
        if (
            address_type in SUPRALOCAL_ADDRESS_TYPES
            or place_type in SUPRALOCAL_ADDRESS_TYPES
        ):
            return True
        if address_type in (*LOCALITY_ADDRESS_FIELDS, "municipality"):
            return False

        category = normalize_text(payload.get("category") or payload.get("class"))
        if category != "boundary" or place_type != "administrative":
            return False
        # Nominatim search ranks 1-12 cover countries/regions/counties;
        # municipalities start at 13. Use this only for typed boundaries,
        # never infer that a result is a province from its name/address.
        # https://nominatim.org/release-docs/latest/customize/Ranking/
        try:
            rank = float(payload.get("place_rank"))
        except (TypeError, ValueError):
            return False
        return not isinstance(payload.get("place_rank"), bool) and 1 <= rank <= 12

    @classmethod
    def _parse_result(cls, payload: Any) -> LocationSearchItem | None:
        if not isinstance(payload, dict) or not isinstance(payload.get("address"), dict):
            return None
        address = payload["address"]
        country_code = str(address.get("country_code") or "").strip().upper()
        country = str(address.get("country") or "").strip()
        if country_code != "IT" or not country:
            return None
        if cls._is_supralocal_result(payload):
            return None

        name = str(payload.get("name") or "").strip()
        if not name:
            name = next(
                (
                    str(address.get(field) or "").strip()
                    for field in LOCALITY_ADDRESS_FIELDS
                    if str(address.get(field) or "").strip()
                ),
                "",
            )
        admin1 = str(address.get("state") or address.get("region") or "").strip()
        province_name = str(
            address.get("province") or address.get("county") or ""
        ).strip()
        province_iso = str(address.get("ISO3166-2-lvl6") or "").strip().upper()
        province = province_iso[3:] if re.fullmatch(r"IT-[A-Z]{2}", province_iso) else ""
        try:
            latitude = float(payload.get("lat"))
            longitude = float(payload.get("lon"))
        except (TypeError, ValueError):
            return None
        if (
            not name
            or not admin1
            or not math.isfinite(latitude)
            or not math.isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            return None

        return LocationSearchItem(
            name=name,
            admin1=admin1,
            latitude=latitude,
            longitude=longitude,
            population=0,
            province=province,
            provinceName=province_name,
            istatCode="",
            country=country,
            countryCode="IT",
            provider="nominatim_search",
            providerId=str(payload.get("place_id") or payload.get("osm_id") or "").strip(),
        )

    def search(
        self,
        query: str,
        limit: int = MAX_LOCATION_RESULTS,
    ) -> list[LocationSearchItem]:
        clean_query = normalize_text(query)
        if len(clean_query) < 2:
            return []
        effective_limit = min(max(int(limit), 1), MAX_LOCATION_RESULTS)
        cache_key = (clean_query, effective_limit)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        # The public Nominatim service requires an identifying User-Agent and
        # asks clients to stay below one request per second. Cache hits bypass
        # this lane; misses are serialized and rate-limited.
        with NOMINATIM_REQUEST_GATE:
            cached = self._read_cache(cache_key)
            if cached is not None:
                return cached

            try:
                response = self.session.get(
                    NOMINATIM_SEARCH_URL,
                    params={
                        "q": " ".join(str(query).strip().split()),
                        "format": "jsonv2",
                        "addressdetails": 1,
                        "accept-language": "it",
                        "countrycodes": "it",
                        "dedupe": 1,
                        "limit": effective_limit,
                    },
                    headers={"User-Agent": NOMINATIM_USER_AGENT},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                raw_results = response.json()
            except (requests.RequestException, ValueError, TypeError) as error:
                raise LocationSearchSourceUnavailable(
                    "location_search_source_failed"
                ) from error

        if not isinstance(raw_results, list):
            raise LocationSearchSourceUnavailable("location_search_payload_invalid")

        results: list[LocationSearchItem] = []
        for raw_result in raw_results:
            result = self._parse_result(raw_result)
            if result is not None:
                results.append(result)
            if len(results) >= effective_limit:
                break

        self._write_cache(cache_key, results)
        return self._copy_results(tuple(results))


class ReverseLocationSource:
    def __init__(self, session: requests.Session | None = None, timeout_seconds: float | None = None) -> None:
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds or float(os.getenv("LOCATION_SOURCE_TIMEOUT_SECONDS", "6"))
        self._cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
        self._cache_lock = threading.Lock()

    def _read_cache(self, key: tuple[float, float]) -> dict[str, Any] | None:
        now = time.monotonic()
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached is None:
                return None
            stored_at, payload = cached
            if now - stored_at > NOMINATIM_CACHE_TTL_SECONDS:
                self._cache.pop(key, None)
                return None
            return payload

    def _write_cache(self, key: tuple[float, float], payload: dict[str, Any]) -> None:
        with self._cache_lock:
            if len(self._cache) >= NOMINATIM_CACHE_MAX_ITEMS:
                oldest_key = min(self._cache, key=lambda item: self._cache[item][0])
                self._cache.pop(oldest_key, None)
            self._cache[key] = (time.monotonic(), payload)

    def fetch(self, lat: float, lon: float) -> dict[str, Any]:
        key = (
            round(float(lat), NOMINATIM_COORDINATE_DECIMALS),
            round(float(lon), NOMINATIM_COORDINATE_DECIMALS),
        )
        cached = self._read_cache(key)
        if cached is not None:
            return cached

        # The public endpoint asks clients to stay below one request per
        # second. Serializing misses and caching coarse coordinate cells keeps
        # foreground refreshes respectful without persisting precise GPS data.
        with NOMINATIM_REQUEST_GATE:
            cached = self._read_cache(key)
            if cached is not None:
                return cached

            try:
                response = self.session.get(
                    NOMINATIM_REVERSE_URL,
                    params={
                        "lat": key[0],
                        "lon": key[1],
                        "format": "jsonv2",
                        "addressdetails": 1,
                        "accept-language": "it",
                        # City-level detail returns the named administrative
                        # place and its public representative point, not the
                        # exact road, building or shop under the GPS fix.
                        "zoom": 10,
                    },
                    headers={"User-Agent": NOMINATIM_USER_AGENT},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError, TypeError) as error:
                raise LocationSourceUnavailable("reverse_location_source_failed") from error

        if not isinstance(payload, dict) or not isinstance(payload.get("address"), dict):
            raise LocationSourceUnavailable("reverse_location_payload_invalid")

        self._write_cache(key, payload)
        return payload


class LocationService:
    def __init__(
        self,
        catalog: LocationCatalog | None = None,
        geography: FvgGeographyCatalog | None = None,
        reverse_source: ReverseLocationSource | None = None,
        search_source: NominatimLocationSearchSource | None = None,
    ) -> None:
        self.catalog = catalog or LocationCatalog()
        self.geography = geography or get_default_fvg_geography_catalog()
        self.reverse_source = reverse_source or ReverseLocationSource()
        self.search_source = search_source or NominatimLocationSearchSource()

    def search(self, query: str) -> list[LocationSearchItem]:
        local_results = self.catalog.search(query, limit=MAX_LOCATION_RESULTS)
        try:
            national_results = self.search_source.search(
                query,
                limit=MAX_LOCATION_RESULTS,
            )
        except LocationSearchSourceUnavailable:
            if not local_results:
                raise
            national_results = []

        unique_national_results: list[LocationSearchItem] = []
        for result in national_results:
            if any(search_results_match(result, local) for local in local_results):
                continue
            if any(
                search_results_match(result, existing)
                for existing in unique_national_results
            ):
                continue
            unique_national_results.append(result)

        reserved_national_count = min(
            len(unique_national_results),
            NATIONAL_LOCATION_RESULT_RESERVE,
        )
        local_count = min(
            len(local_results),
            MAX_LOCATION_RESULTS - reserved_national_count,
        )
        merged_results = local_results[:local_count]
        merged_results.extend(
            unique_national_results[:MAX_LOCATION_RESULTS - local_count]
        )
        return merged_results

    def reverse(
        self,
        lat: float,
        lon: float,
        *,
        accuracy_m: float | None = None,
    ) -> ReverseLocationResponse:
        if accuracy_m is not None and (
            not math.isfinite(accuracy_m) or accuracy_m < 0 or accuracy_m > 10_000
        ):
            raise ValueError("location_accuracy_invalid")

        municipality_istat = self.geography.resolve_municipality_istat(lat, lon)
        municipality = (
            self.catalog.match_istat(municipality_istat)
            if municipality_istat is not None
            else None
        )
        if municipality_istat is not None and municipality is None:
            raise LocationSourceUnavailable("fvg_municipality_catalog_mismatch")

        if municipality is None:
            return self._build_external_response(
                payload=self.reverse_source.fetch(lat, lon),
                lat=lat,
                lon=lon,
            )

        locality_resolution = FvgLocalityResolution(locality=None)
        if accuracy_m is not None:
            # Native GPS polling stays entirely within the versioned offline
            # ISTAT/IRDAT snapshot.  A locality is exposed only when distance,
            # runner-up separation and reported GPS accuracy make the nearest
            # official toponym unambiguous.
            locality_resolution = self.geography.resolve_locality_resolution(
                municipality_istat=municipality.istat_code,
                candidate_names=(),
                latitude=lat,
                longitude=lon,
                allow_nearest=True,
                nearest_accuracy_m=accuracy_m,
            )
        return self._build_fvg_response(
            municipality=municipality,
            locality_resolution=locality_resolution,
            lat=lat,
            lon=lon,
        )

    def _build_external_response(
        self,
        *,
        payload: dict[str, Any],
        lat: float,
        lon: float,
    ) -> ReverseLocationResponse:
        address = payload.get("address")
        if not isinstance(address, dict):
            raise LocationSourceUnavailable("reverse_location_payload_invalid")

        place_name = next(
            (
                str(address.get(field) or "").strip()
                for field in (
                    "city",
                    "town",
                    "village",
                    "municipality",
                    "hamlet",
                    "isolated_dwelling",
                    "suburb",
                    "county",
                )
                if str(address.get(field) or "").strip()
            ),
            str(payload.get("name") or "").strip(),
        )
        region = next(
            (
                str(address.get(field) or "").strip()
                for field in ("state", "region", "state_district", "country")
                if str(address.get(field) or "").strip()
            ),
            "",
        )
        country = str(address.get("country") or "").strip()
        country_code = str(address.get("country_code") or "").strip().upper()
        try:
            canonical_lat = float(payload.get("lat"))
            canonical_lon = float(payload.get("lon"))
        except (TypeError, ValueError) as error:
            raise LocationSourceUnavailable("reverse_location_payload_invalid") from error

        if (
            not place_name
            or not region
            or not country
            or len(country_code) != 2
            or not country_code.isalpha()
            or not math.isfinite(canonical_lat)
            or not math.isfinite(canonical_lon)
            or not -90 <= canonical_lat <= 90
            or not -180 <= canonical_lon <= 180
        ):
            raise LocationSourceUnavailable("reverse_location_payload_invalid")

        canonical_distance_km = haversine_km(
            lat,
            lon,
            canonical_lat,
            canonical_lon,
        )
        if canonical_distance_km > MAX_EXTERNAL_CANONICAL_DISTANCE_KM:
            raise LocationSourceUnavailable("reverse_location_place_too_far")

        return ReverseLocationResponse(
            city=place_name,
            displayName=place_name,
            region=region,
            country=country,
            countryCode=country_code,
            lat=lat,
            lon=lon,
            locality=None,
            municipality=None,
            dataPoint=ReverseLocationDataPoint(
                lat=canonical_lat,
                lon=canonical_lon,
                source="nominatim_place",
            ),
            resolution=ReverseLocationResolution(
                status="external_place",
                municipalityResolved=False,
                localityCorroborated=False,
                matchMethod="nearest",
                distanceM=round(canonical_distance_km * 1000, 3),
            ),
        )

    def _build_fvg_response(
        self,
        *,
        municipality: Municipality,
        locality_resolution: FvgLocalityResolution,
        lat: float,
        lon: float,
    ) -> ReverseLocationResponse:
        locality = locality_resolution.locality
        locality_contract = (
            ReverseLocationLocality.model_validate(locality.to_public_dict())
            if locality is not None
            else None
        )
        municipality_contract = ReverseLocationMunicipality(
            name=municipality.name,
            istatCode=municipality.istat_code,
            province=municipality.province,
            provinceName=municipality.province_name,
            source=MUNICIPALITY_SOURCE_ID,
            datasetVersion=self.geography.municipality_dataset_version,
        )
        data_point_contract = ReverseLocationDataPoint(
            lat=locality.latitude if locality is not None else municipality.latitude,
            lon=locality.longitude if locality is not None else municipality.longitude,
            source=(
                "rafvg_irdat_5000"
                if locality is not None
                else "municipality_catalog"
            ),
        )
        boundary_distance_m = self.geography.municipality_boundary_distance_m(
            municipality_istat=municipality.istat_code,
            latitude=lat,
            longitude=lon,
        )
        if boundary_distance_m is None:
            raise LocationSourceUnavailable("fvg_municipality_boundary_distance_unavailable")
        return ReverseLocationResponse(
            city=municipality.name,
            displayName=locality.name if locality is not None else municipality.name,
            region=municipality.admin1,
            country="Italia",
            countryCode="IT",
            lat=lat,
            lon=lon,
            province=municipality.province,
            provinceName=municipality.province_name,
            istatCode=municipality.istat_code,
            locality=locality_contract,
            municipality=municipality_contract,
            dataPoint=data_point_contract,
            resolution=ReverseLocationResolution(
                status="resolved" if locality is not None else "municipality_only",
                municipalityResolved=True,
                localityCorroborated=locality is not None,
                matchMethod=locality_resolution.match_method,
                distanceM=(
                    round(locality_resolution.distance_m, 3)
                    if locality_resolution.distance_m is not None
                    else None
                ),
                runnerUpDistanceM=(
                    round(locality_resolution.runner_up_distance_m, 3)
                    if locality_resolution.runner_up_distance_m is not None
                    else None
                ),
                boundaryDistanceM=round(boundary_distance_m, 3),
            ),
        )
