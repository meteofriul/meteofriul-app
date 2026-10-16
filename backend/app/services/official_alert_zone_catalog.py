"""Immutable, fail-closed Comune -> official alert-zone catalog.

This service only resolves an already verified municipality identity.  It does
not geocode names, choose a nearby Comune or interpret device coordinates.  A
multi-zone Comune intentionally returns every intersecting official zone.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from app.services.national_municipalities import (
    NATIONAL_MUNICIPALITY_CATALOG_SHA256,
    NationalMunicipalityCatalog,
    get_default_national_municipality_catalog,
)
from app.services.pilot_community_geography import (
    BOUNDARIES_SOURCE_SHA256,
    GEOGRAPHY_SCHEMA,
    PILOT_GEOGRAPHY_ARTIFACT_SHA256,
)
from app.weather.dpc_national_alerts import canonical_dpc_zone_id


ALERT_ZONE_CATALOG_CONTRACT = "meteofriul.official_alert_zone_catalog.v1"
ALERT_ZONE_CATALOG_SCHEMA_VERSION = 1
ALERT_ZONE_CATALOG_SHA256 = (
    "8de0daced916538b6ae229bd1e1953784e13ea1988b1ae86bc4a4a7d746717db"
)
ALERT_ZONE_CATALOG_MUNICIPALITY_COUNT = 7_894
ALERT_ZONE_CATALOG_ZONE_COUNT = 187
FVG_REGION_ISO = "IT-36"
FVG_ZONE_IDS = frozenset({"FVG-A", "FVG-B", "FVG-C", "FVG-D"})
REGION_ZONE_PREFIX = {
    "IT-21": "Piem",
    "IT-23": "VDAo",
    "IT-25": "Lomb",
    "IT-32": "Tren",
    "IT-34": "Vene",
    "IT-36": "Friu",
    "IT-42": "Ligu",
    "IT-45": "Emil",
    "IT-52": "Tosc",
    "IT-55": "Umbr",
    "IT-57": "Marc",
    "IT-62": "Lazi",
    "IT-65": "Abru",
    "IT-67": "Moli",
    "IT-72": "Camp",
    "IT-75": "Pugl",
    "IT-77": "Basi",
    "IT-78": "Cala",
    "IT-82": "Sici",
    "IT-88": "Sard",
}


class OfficialAlertZoneCatalogError(ValueError):
    """The checked-in alert-zone catalog is incomplete or untrusted."""


@dataclass(frozen=True, slots=True)
class OfficialAlertZone:
    zone_id: str
    source_zone_id: str
    name: str


@dataclass(frozen=True, slots=True)
class MunicipalityAlertZones:
    istat_code: str
    region_iso: str
    zone_ids: tuple[str, ...]
    representative_point_zone_id: str | None


@dataclass(frozen=True, slots=True)
class _CatalogSnapshot:
    catalog_sha256: str
    source_revision: str
    zones: Mapping[str, OfficialAlertZone]
    municipalities: Mapping[str, MunicipalityAlertZones]
    multi_zone_municipality_count: int


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
        raise OfficialAlertZoneCatalogError(
            "official alert-zone catalog is not canonical JSON data"
        ) from error


def _required_text(record: Mapping[str, Any], field: str) -> str:
    value = str(record.get(field) or "").strip()
    if not value:
        raise OfficialAlertZoneCatalogError(
            f"official alert-zone catalog has no {field}"
        )
    return value


class OfficialAlertZoneCatalog:
    """Lazy, immutable lookup for exact canonical ISTAT identities."""

    def __init__(
        self,
        data_path: Path | None = None,
        *,
        municipality_catalog: NationalMunicipalityCatalog | None = None,
        expected_count: int = ALERT_ZONE_CATALOG_MUNICIPALITY_COUNT,
        expected_zone_count: int = ALERT_ZONE_CATALOG_ZONE_COUNT,
        expected_sha256: str | None = None,
    ) -> None:
        uses_default = data_path is None
        self._data_path = data_path or (
            Path(__file__).resolve().parents[1]
            / "data"
            / "official_alert_zone_catalog.json"
        )
        self._municipality_catalog = (
            municipality_catalog or get_default_national_municipality_catalog()
        )
        self._expected_count = expected_count
        self._expected_zone_count = expected_zone_count
        self._expected_sha256 = (
            ALERT_ZONE_CATALOG_SHA256 if uses_default else expected_sha256
        )
        self._snapshot: _CatalogSnapshot | None = None
        self._load_lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._snapshot is not None

    @property
    def catalog_sha256(self) -> str:
        return self._load().catalog_sha256

    @property
    def source_revision(self) -> str:
        return self._load().source_revision

    @property
    def zones(self) -> tuple[OfficialAlertZone, ...]:
        return tuple(self._load().zones.values())

    @property
    def multi_zone_municipality_count(self) -> int:
        return self._load().multi_zone_municipality_count

    def match_istat(self, value: Any) -> MunicipalityAlertZones | None:
        istat_code = str(value or "").strip()
        if not re.fullmatch(r"\d{6}", istat_code):
            return None
        return self._load().municipalities.get(istat_code)

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
            raise OfficialAlertZoneCatalogError(
                "official alert-zone catalog cannot be loaded"
            ) from error
        if not isinstance(payload, dict):
            raise OfficialAlertZoneCatalogError(
                "official alert-zone catalog must be an object"
            )
        if (
            payload.get("contract") != ALERT_ZONE_CATALOG_CONTRACT
            or payload.get("schema_version")
            != ALERT_ZONE_CATALOG_SCHEMA_VERSION
        ):
            raise OfficialAlertZoneCatalogError(
                "official alert-zone catalog header is incompatible"
            )

        expected_hash = str(payload.get("catalog_sha256") or "")
        unhashed = dict(payload)
        unhashed.pop("catalog_sha256", None)
        observed_hash = hashlib.sha256(_canonical_json_bytes(unhashed)).hexdigest()
        if not expected_hash or observed_hash != expected_hash:
            raise OfficialAlertZoneCatalogError(
                "official alert-zone catalog hash is invalid"
            )
        if (
            self._expected_sha256 is not None
            and expected_hash != self._expected_sha256
        ):
            raise OfficialAlertZoneCatalogError(
                "official alert-zone catalog release is not approved"
            )

        source = payload.get("source")
        if not isinstance(source, Mapping):
            raise OfficialAlertZoneCatalogError(
                "official alert-zone catalog source is invalid"
            )
        if (
            source.get("authority")
            != "Dipartimento della Protezione Civile"
            or source.get("municipality_geography_schema") != GEOGRAPHY_SCHEMA
            or source.get("municipality_boundaries_sha256")
            != BOUNDARIES_SOURCE_SHA256
            or source.get("municipality_geometry_artifact_sha256")
            != PILOT_GEOGRAPHY_ARTIFACT_SHA256
            or source.get("municipality_catalog_sha256")
            != NATIONAL_MUNICIPALITY_CATALOG_SHA256
        ):
            raise OfficialAlertZoneCatalogError(
                "official alert-zone catalog provenance is not approved"
            )
        source_revision = _required_text(source, "bulletin_revision")
        if not re.fullmatch(r"\d{8}_\d{4}", source_revision):
            raise OfficialAlertZoneCatalogError(
                "official alert-zone catalog revision is invalid"
            )
        for field in ("zone_geometry_sha256", "zone_zip_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", _required_text(source, field)):
                raise OfficialAlertZoneCatalogError(
                    "official alert-zone source digest is invalid"
                )

        raw_zones = payload.get("zones")
        if (
            not isinstance(raw_zones, list)
            or payload.get("zone_count") != self._expected_zone_count
            or len(raw_zones) != self._expected_zone_count
        ):
            raise OfficialAlertZoneCatalogError(
                "official alert-zone count is invalid"
            )
        zones: dict[str, OfficialAlertZone] = {}
        source_prefix_by_zone: dict[str, str] = {}
        for raw_zone in raw_zones:
            if not isinstance(raw_zone, Mapping):
                raise OfficialAlertZoneCatalogError(
                    "official alert-zone record is invalid"
                )
            zone_id = _required_text(raw_zone, "zone_id")
            source_zone_id = _required_text(raw_zone, "source_zone_id")
            if (
                zone_id in zones
                or canonical_dpc_zone_id(source_zone_id) != zone_id
                or not re.fullmatch(r"[A-Za-z0-9]+-[A-Za-z0-9-]+", source_zone_id)
            ):
                raise OfficialAlertZoneCatalogError(
                    "official alert-zone identity is invalid"
                )
            zones[zone_id] = OfficialAlertZone(
                zone_id=zone_id,
                source_zone_id=source_zone_id,
                name=_required_text(raw_zone, "zone_name"),
            )
            source_prefix_by_zone[zone_id] = source_zone_id.split("-", 1)[0]
        if set(source_prefix_by_zone.values()) != set(REGION_ZONE_PREFIX.values()):
            raise OfficialAlertZoneCatalogError(
                "official alert-zone regional coverage is invalid"
            )

        raw_mappings = payload.get("mappings")
        if (
            not isinstance(raw_mappings, list)
            or payload.get("municipality_count") != self._expected_count
            or len(raw_mappings) != self._expected_count
        ):
            raise OfficialAlertZoneCatalogError(
                "official alert-zone municipality count is invalid"
            )
        municipalities: dict[str, MunicipalityAlertZones] = {}
        used_zones = set()
        multi_zone_count = 0
        for raw_mapping in raw_mappings:
            if not isinstance(raw_mapping, Mapping):
                raise OfficialAlertZoneCatalogError(
                    "official alert-zone municipality record is invalid"
                )
            istat_code = _required_text(raw_mapping, "istat")
            region_iso = _required_text(raw_mapping, "region_iso")
            identity = self._municipality_catalog.match_istat(istat_code)
            raw_zone_ids = raw_mapping.get("zone_ids")
            if (
                identity is None
                or identity.region_iso != region_iso
                or region_iso not in REGION_ZONE_PREFIX
                or istat_code in municipalities
                or not isinstance(raw_zone_ids, list)
                or not raw_zone_ids
                or raw_zone_ids != sorted(set(raw_zone_ids))
                or any(zone_id not in zones for zone_id in raw_zone_ids)
                or any(
                    source_prefix_by_zone[zone_id]
                    != REGION_ZONE_PREFIX[region_iso]
                    for zone_id in raw_zone_ids
                )
            ):
                raise OfficialAlertZoneCatalogError(
                    "official alert-zone municipality mapping is invalid"
                )
            point_zone_id = raw_mapping.get("point_zone_id")
            if point_zone_id is not None and point_zone_id not in raw_zone_ids:
                raise OfficialAlertZoneCatalogError(
                    "official alert-zone representative point is invalid"
                )
            zone_ids = tuple(raw_zone_ids)
            multi_zone_count += len(zone_ids) > 1
            used_zones.update(zone_ids)
            municipalities[istat_code] = MunicipalityAlertZones(
                istat_code=istat_code,
                region_iso=region_iso,
                zone_ids=zone_ids,
                representative_point_zone_id=point_zone_id,
            )

        expected_codes = {
            municipality.istat_code
            for municipality in self._municipality_catalog.municipalities
        }
        fvg_mappings = tuple(
            item
            for item in municipalities.values()
            if item.region_iso == FVG_REGION_ISO
        )
        if (
            set(municipalities) != expected_codes
            or used_zones != set(zones)
            or payload.get("multi_zone_municipality_count") != multi_zone_count
            or payload.get("fvg_municipality_count") != 215
            or len(fvg_mappings) != 215
            or {
                zone_id
                for item in fvg_mappings
                for zone_id in item.zone_ids
            }
            != FVG_ZONE_IDS
            or any(not set(item.zone_ids).issubset(FVG_ZONE_IDS) for item in fvg_mappings)
        ):
            raise OfficialAlertZoneCatalogError(
                "official alert-zone catalog coverage is invalid"
            )
        return _CatalogSnapshot(
            catalog_sha256=expected_hash,
            source_revision=source_revision,
            zones=MappingProxyType(zones),
            municipalities=MappingProxyType(municipalities),
            multi_zone_municipality_count=multi_zone_count,
        )


@lru_cache(maxsize=1)
def get_default_official_alert_zone_catalog() -> OfficialAlertZoneCatalog:
    return OfficialAlertZoneCatalog()


__all__ = [
    "ALERT_ZONE_CATALOG_CONTRACT",
    "ALERT_ZONE_CATALOG_SHA256",
    "FVG_REGION_ISO",
    "FVG_ZONE_IDS",
    "REGION_ZONE_PREFIX",
    "MunicipalityAlertZones",
    "OfficialAlertZone",
    "OfficialAlertZoneCatalog",
    "OfficialAlertZoneCatalogError",
    "get_default_official_alert_zone_catalog",
]
