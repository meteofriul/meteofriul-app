"""Read-only identity lookup for the canonical Italian municipality catalog.

This service is deliberately separate from :mod:`app.services.location`.
The existing ``LocationCatalog`` remains the authoritative, polygon-backed FVG
runtime catalog; this module exposes exact national identities for weather
bundles and municipality-selected local notices.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


NATIONAL_MUNICIPALITY_CATALOG_KIND = (
    "meteofriul.weather.national_municipality_catalog"
)
NATIONAL_MUNICIPALITY_CATALOG_SCHEMA_VERSION = 1
NATIONAL_MUNICIPALITY_COUNT = 7_894
NATIONAL_MUNICIPALITY_CATALOG_VERSION = (
    "istat-2026-02-21-boundaries-2026-01-01-v1"
)
NATIONAL_MUNICIPALITY_CATALOG_SHA256 = (
    "ee856c27ec135be45c4c7eaaf946158fdfc61bc83135cf9b6fbbce892ce3cf0d"
)
NATIONAL_MUNICIPALITY_CODES_SHA256 = (
    "f4bf3155646e837e8c622c4bf1ce5af2eff47dd7c7d3fecf02dd44cf4d410f16"
)


class NationalMunicipalityCatalogError(ValueError):
    """Raised when the checked-in national identity catalog is not trustworthy."""


@dataclass(frozen=True, slots=True)
class NationalMunicipality:
    """One immutable, canonical ISTAT municipality identity."""

    istat_code: str
    name: str
    province_code: str
    province_name: str
    region_name: str
    region_iso: str
    latitude: float | None
    longitude: float | None

    @property
    def province(self) -> str:
        """Compatibility name used by the notice detector."""

        return self.province_code

    @property
    def admin1(self) -> str:
        """Compatibility name used by the canonical weather request."""

        return self.region_name

    @property
    def slug(self) -> str:
        """Stable non-fuzzy identifier for catalog-compatible call sites."""

        return self.istat_code

    @property
    def representative_coordinates(self) -> tuple[float, float] | None:
        if self.latitude is None or self.longitude is None:
            return None
        return self.latitude, self.longitude


@dataclass(frozen=True, slots=True)
class _CatalogSnapshot:
    catalog_version: str
    catalog_sha256: str
    municipality_codes_sha256: str
    effective_at: str
    municipalities: tuple[NationalMunicipality, ...]
    by_istat: Mapping[str, NationalMunicipality]
    by_name: Mapping[str, tuple[NationalMunicipality, ...]]


def normalize_municipality_identity(value: Any) -> str:
    """Normalize an administrative label without introducing fuzzy matching."""

    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^0-9a-z]+", " ", without_marks).split())


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise NationalMunicipalityCatalogError(
            "national municipality catalog is not canonical JSON data"
        ) from error


def _required_text(record: Mapping[str, Any], field: str) -> str:
    value = str(record.get(field) or "").strip()
    if not value:
        raise NationalMunicipalityCatalogError(
            f"national municipality record has no {field}"
        )
    return value


def _optional_point(record: Mapping[str, Any]) -> tuple[float | None, float | None]:
    raw_point = record.get("representative_point")
    if raw_point is None:
        return None, None
    if not isinstance(raw_point, Mapping):
        raise NationalMunicipalityCatalogError(
            "national municipality representative_point is invalid"
        )
    try:
        latitude = float(raw_point["latitude"])
        longitude = float(raw_point["longitude"])
    except (KeyError, TypeError, ValueError) as error:
        raise NationalMunicipalityCatalogError(
            "national municipality representative coordinates are invalid"
        ) from error
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise NationalMunicipalityCatalogError(
            "national municipality representative coordinates are out of range"
        )
    return latitude, longitude


class NationalMunicipalityCatalog:
    """Lazy, immutable national lookup keyed only by exact canonical identity."""

    def __init__(
        self,
        data_path: Path | None = None,
        *,
        expected_count: int = NATIONAL_MUNICIPALITY_COUNT,
        expected_version: str | None = None,
        expected_sha256: str | None = None,
        expected_codes_sha256: str | None = None,
    ) -> None:
        uses_default_catalog = data_path is None
        self._data_path = data_path or (
            Path(__file__).resolve().parents[1]
            / "data"
            / "italy_municipalities_2026.json"
        )
        self._expected_count = expected_count
        self._expected_version = (
            NATIONAL_MUNICIPALITY_CATALOG_VERSION
            if uses_default_catalog
            else expected_version
        )
        self._expected_sha256 = (
            NATIONAL_MUNICIPALITY_CATALOG_SHA256
            if uses_default_catalog
            else expected_sha256
        )
        self._expected_codes_sha256 = (
            NATIONAL_MUNICIPALITY_CODES_SHA256
            if uses_default_catalog
            else expected_codes_sha256
        )
        self._snapshot: _CatalogSnapshot | None = None
        self._load_lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._snapshot is not None

    @property
    def municipalities(self) -> tuple[NationalMunicipality, ...]:
        return self._load().municipalities

    @property
    def catalog_version(self) -> str:
        return self._load().catalog_version

    @property
    def catalog_sha256(self) -> str:
        return self._load().catalog_sha256

    @property
    def municipality_codes_sha256(self) -> str:
        return self._load().municipality_codes_sha256

    @property
    def effective_at(self) -> str:
        return self._load().effective_at

    def match_istat(self, value: Any) -> NationalMunicipality | None:
        """Return one exact six-digit ISTAT identity, never a padded guess."""

        istat_code = str(value or "").strip()
        if not re.fullmatch(r"\d{6}", istat_code):
            return None
        return self._load().by_istat.get(istat_code)

    def match_name(
        self,
        name: Any,
        *,
        province: Any | None = None,
    ) -> NationalMunicipality | None:
        """Resolve an exact normalized name and optional province code/name.

        A name shared by more than one municipality returns ``None`` unless the
        supplied province selector leaves exactly one candidate.  Province
        matching is exact after normalization and accepts either the official
        abbreviation or the full official province name.
        """

        normalized_name = normalize_municipality_identity(name)
        if not normalized_name:
            return None
        candidates = self._load().by_name.get(normalized_name, ())
        normalized_province = normalize_municipality_identity(province)
        if province is not None:
            if not normalized_province:
                return None
            candidates = tuple(
                municipality
                for municipality in candidates
                if normalized_province
                in {
                    normalize_municipality_identity(municipality.province_code),
                    normalize_municipality_identity(municipality.province_name),
                }
            )
        return candidates[0] if len(candidates) == 1 else None

    def match_names(self, *values: Any) -> NationalMunicipality | None:
        """Compatibility exact-name lookup; ambiguous national names fail closed."""

        for value in values:
            municipality = self.match_name(value)
            if municipality is not None:
                return municipality
        return None

    def _load(self) -> _CatalogSnapshot:
        snapshot = self._snapshot
        if snapshot is not None:
            return snapshot
        with self._load_lock:
            if self._snapshot is None:
                self._snapshot = self._read_snapshot()
            return self._snapshot

    def _read_snapshot(self) -> _CatalogSnapshot:
        try:
            payload = json.loads(self._data_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise NationalMunicipalityCatalogError(
                "national municipality catalog cannot be loaded"
            ) from error
        if not isinstance(payload, dict):
            raise NationalMunicipalityCatalogError(
                "national municipality catalog must be an object"
            )
        if (
            payload.get("kind") != NATIONAL_MUNICIPALITY_CATALOG_KIND
            or payload.get("schema_version")
            != NATIONAL_MUNICIPALITY_CATALOG_SCHEMA_VERSION
        ):
            raise NationalMunicipalityCatalogError(
                "national municipality catalog header is incompatible"
            )

        expected_hash = str(payload.get("catalog_sha256") or "")
        unhashed_payload = dict(payload)
        unhashed_payload.pop("catalog_sha256", None)
        observed_hash = hashlib.sha256(
            _canonical_json_bytes(unhashed_payload)
        ).hexdigest()
        if not expected_hash or observed_hash != expected_hash:
            raise NationalMunicipalityCatalogError(
                "national municipality catalog hash is invalid"
            )
        catalog_version = str(payload.get("catalog_version") or "")
        codes_sha256 = str(payload.get("municipality_codes_sha256") or "")
        if (
            self._expected_version is not None
            and catalog_version != self._expected_version
        ):
            raise NationalMunicipalityCatalogError(
                "national municipality catalog version is not approved"
            )
        if (
            self._expected_sha256 is not None
            and expected_hash != self._expected_sha256
        ):
            raise NationalMunicipalityCatalogError(
                "national municipality catalog release hash is not approved"
            )
        if (
            self._expected_codes_sha256 is not None
            and codes_sha256 != self._expected_codes_sha256
        ):
            raise NationalMunicipalityCatalogError(
                "national municipality identity set is not approved"
            )

        raw_records = payload.get("municipalities")
        declared_count = payload.get("municipality_count")
        if (
            not isinstance(raw_records, list)
            or declared_count != self._expected_count
            or len(raw_records) != self._expected_count
        ):
            raise NationalMunicipalityCatalogError(
                "national municipality catalog count is invalid"
            )

        municipalities: list[NationalMunicipality] = []
        by_istat: dict[str, NationalMunicipality] = {}
        names: dict[str, dict[str, NationalMunicipality]] = {}
        for raw_record in raw_records:
            if not isinstance(raw_record, Mapping):
                raise NationalMunicipalityCatalogError(
                    "national municipality record must be an object"
                )
            istat_code = _required_text(raw_record, "istat_code")
            if not re.fullmatch(r"\d{6}", istat_code) or istat_code in by_istat:
                raise NationalMunicipalityCatalogError(
                    "national municipality ISTAT identities are invalid"
                )
            latitude, longitude = _optional_point(raw_record)
            municipality = NationalMunicipality(
                istat_code=istat_code,
                name=_required_text(raw_record, "name"),
                province_code=_required_text(raw_record, "province_abbreviation"),
                province_name=_required_text(raw_record, "uts_name"),
                region_name=_required_text(raw_record, "region_name"),
                region_iso=_required_text(raw_record, "region_iso"),
                latitude=latitude,
                longitude=longitude,
            )
            municipalities.append(municipality)
            by_istat[istat_code] = municipality

            aliases = {
                municipality.name,
                str(raw_record.get("italian_name") or ""),
                str(raw_record.get("alternate_name") or ""),
            }
            for alias in aliases:
                normalized_alias = normalize_municipality_identity(alias)
                if normalized_alias:
                    names.setdefault(normalized_alias, {})[istat_code] = municipality

        observed_codes_sha256 = hashlib.sha256(
            _canonical_json_bytes(sorted(by_istat))
        ).hexdigest()
        if codes_sha256 != observed_codes_sha256:
            raise NationalMunicipalityCatalogError(
                "national municipality identity hash is invalid"
            )

        immutable_names = {
            name: tuple(sorted(matches.values(), key=lambda item: item.istat_code))
            for name, matches in names.items()
        }
        return _CatalogSnapshot(
            catalog_version=catalog_version,
            catalog_sha256=expected_hash,
            municipality_codes_sha256=codes_sha256,
            effective_at=_required_text(payload, "effective_at"),
            municipalities=tuple(municipalities),
            by_istat=MappingProxyType(by_istat),
            by_name=MappingProxyType(immutable_names),
        )


@lru_cache(maxsize=1)
def get_default_national_municipality_catalog() -> NationalMunicipalityCatalog:
    """Return the process-wide lazy, immutable national catalog."""

    return NationalMunicipalityCatalog()
