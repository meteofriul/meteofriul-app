"""Strict, provider-separated local weather data contract, version 1.

This module is deliberately independent from the current application adapters.
It performs no network or cloud I/O and does not import the existing weather
provider.  Builders return plain JSON-compatible dictionaries; validators fail
closed before a document can be presented to a client.

Integrity hashes are SHA-256 over ``canonical_json_bytes``: uncompressed UTF-8
JSON with sorted object keys, compact separators, and non-finite numbers
forbidden.  HTTP compression, when introduced later, is outside that digest.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = 1
CATALOG_VERSION = "istat-2026-irdat-2006-representative-points-v1"
LEGACY_FIXTURE_CATALOG_VERSION = "istat-codici-2026-02-21-open-meteo-coordinate-fixture"
SUPPORTED_CATALOG_VERSIONS = frozenset((CATALOG_VERSION, LEGACY_FIXTURE_CATALOG_VERSION))
EXPECTED_MUNICIPALITIES = 215

ICON_PROVIDER = "icon2i"
CAMS_PROVIDER = "cams_europe"
CAMS_POLLEN_PROVIDER = "cams_europe_pollen"
PROVIDERS = frozenset((ICON_PROVIDER, CAMS_PROVIDER, CAMS_POLLEN_PROVIDER))

LATEST_KIND = "meteofriul.weather.latest"
RUN_MANIFEST_KIND = "meteofriul.weather.run_manifest"
ICON_PAYLOAD_KIND = "meteofriul.weather.icon.municipality"
CAMS_PAYLOAD_KIND = "meteofriul.weather.cams.municipality"
CAMS_POLLEN_PAYLOAD_KIND = "meteofriul.weather.cams.pollen_municipality"

DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "backend"
    / "app"
    / "data"
    / "fvg_municipalities.json"
)

MAX_PAYLOAD_JSON_BYTES = 512 * 1024
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z$")
_ISTAT_RE = re.compile(r"^\d{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


ICON_MODEL = {
    "id": "icon-2i",
    "product": "surface_pressure_levels",
}
ICON_SOURCE = {
    "attribution": "Agenzia ItaliaMeteo / Arpae Emilia-Romagna Idro-Meteo-Clima",
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
}
ICON_UNITS = {
    "temperature_c": "degC",
    "apparent_temperature_c": "degC",
    "relative_humidity_pct": "percent",
    "pressure_msl_hpa": "hPa",
    "wind_speed_m_s": "m/s",
    "wind_from_degrees": "degree",
    "wind_gust_max_m_s": "m/s",
    "cloud_cover_pct": "percent",
    "precipitation_mm": "mm",
    "liquid_rain_mm": "mm",
    "snow_water_equivalent_mm": "mm",
}
APPARENT_TEMPERATURE_METHOD = "steadman_bom_shade_t2m_rh_magnus_wind10m_v1"

CAMS_MODEL = {
    "id": "cams-european-regional-ensemble",
    "dataset": "cams-europe-air-quality-forecasts",
    "forecast_type": "ensemble",
    "statistic": "median",
    "level": "surface",
}
CAMS_SOURCE = {
    "attribution": (
        "Copernicus Atmosphere Monitoring Service (CAMS), European regional "
        "ensemble providers, Atmosphere Data Store (ADS)"
    ),
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "doi": "10.24381/a4005cee",
}
# Exact identifiers exposed by the verified CAMS surface-ensemble request.  The
# local contract deliberately retains every decoded field.  A later UI policy
# may choose a smaller display subset without destroying source information.
# (id, UI key, category, unit, provider validation status)
CAMS_VARIABLE_SPECS = (
    ("alder_pollen", "ontano", "pollen", "grains/m3", "experimental_unvalidated_by_provider"),
    ("ammonia", "ammoniaca", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("birch_pollen", "betulla", "pollen", "grains/m3", "experimental_unvalidated_by_provider"),
    ("carbon_monoxide", "monossido_carbonio", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("formaldehyde", "formaldeide", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("glyoxal", "gliossale", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("grass_pollen", "graminacee", "pollen", "grains/m3", "experimental_unvalidated_by_provider"),
    ("mugwort_pollen", "artemisia", "pollen", "grains/m3", "experimental_unvalidated_by_provider"),
    ("nitrogen_dioxide", "biossido_azoto", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"),
    ("nitrogen_monoxide", "monossido_azoto", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"),
    ("non_methane_vocs", "cov_non_metanici", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("olive_pollen", "olivo", "pollen", "grains/m3", "experimental_unvalidated_by_provider"),
    ("ozone", "ozono", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"),
    ("particulate_matter_2.5um", "pm2_5", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"),
    ("pm2.5_ammonium", "pm2_5_ammonio", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("pm2.5_nitrate", "pm2_5_nitrato", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("residential_elementary_carbon", "carbonio_elementare_residenziale", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("secondary_inorganic_aerosol", "aerosol_inorganico_secondario", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("pm2.5_sulphate", "pm2_5_solfato", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("total_elementary_carbon", "carbonio_elementare_totale", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("pm2.5_total_organic_matter", "pm2_5_materia_organica", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("particulate_matter_10um", "pm10", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"),
    ("dust", "polvere_minerale_pm10", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"),
    ("pm10_sea_salt_dry", "pm10_sale_marino_secco", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("pm10_wildfires", "pm10_incendi", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("peroxyacyl_nitrates", "nitrati_perossiacile", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"),
    ("ragweed_pollen", "ambrosia", "pollen", "grains/m3", "experimental_unvalidated_by_provider"),
    ("sulphur_dioxide", "biossido_zolfo", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"),
)
CAMS_VARIABLE_IDS = tuple(item[0] for item in CAMS_VARIABLE_SPECS)
CAMS_POLLEN_IDS = tuple(item[0] for item in CAMS_VARIABLE_SPECS if item[2] == "pollen")
CAMS_POLLEN_SPECS = tuple((item[0], item[1]) for item in CAMS_VARIABLE_SPECS if item[2] == "pollen")
CAMS_VARIABLES = [
    {
        "id": source_id,
        "ui_key": ui_key,
        "category": category,
        "unit": unit,
        "validation_status": validation_status,
    }
    for source_id, ui_key, category, unit, validation_status in CAMS_VARIABLE_SPECS
]
CAMS_POLLEN_VARIABLES = [
    deepcopy(item) for item in CAMS_VARIABLES if item["category"] == "pollen"
]
CAMS_POLLEN_PROJECTION = {
    "id": "cams_pollen_hourly_v1",
    "source_provider": CAMS_PROVIDER,
    "source_kind": CAMS_PAYLOAD_KIND,
    "retained_variable_ids": list(CAMS_POLLEN_IDS),
}

# code -> native label, semantic key, localization key, icon key, scene key.
# WW 96 is intentionally a strong storm, not a hail assertion: the native
# meaning is ambiguous between hail and a heavy thunderstorm.
ICON_CONDITIONS: dict[int, tuple[str, str, str, str, str]] = {
    0: ("Sereno", "clear", "conditionSun", "Sun", "clear"),
    1: ("Poco nuvoloso", "mostly_sunny", "conditionMostlySunny", "MostlySunny", "partly"),
    2: ("Parzialmente nuvoloso", "partly_cloudy", "conditionPartlyCloudy", "PartlyCloudy", "partly"),
    3: ("Molto nuvoloso o coperto", "overcast", "conditionOvercast", "Overcast", "cloud"),
    45: ("Nebbia", "fog", "conditionFog", "Fog", "fog"),
    48: ("Nebbia con deposito di brina", "fog", "conditionFog", "Fog", "fog"),
    51: ("Pioviggine debole", "drizzle", "conditionLightRain", "LightRain", "rain"),
    53: ("Pioviggine moderata", "drizzle", "conditionLightRain", "LightRain", "rain"),
    55: ("Pioviggine intensa", "drizzle", "conditionLightRain", "LightRain", "rain"),
    56: ("Pioviggine gelata debole", "freezing_drizzle", "conditionFreezingDrizzle", "Sleet", "rain"),
    57: ("Pioviggine gelata moderata o intensa", "freezing_drizzle", "conditionFreezingDrizzle", "Sleet", "rain"),
    61: ("Pioggia debole", "rain", "conditionRain", "Rain", "rain"),
    63: ("Pioggia moderata", "rain", "conditionRain", "Rain", "rain"),
    65: ("Pioggia intensa", "heavy_rain", "conditionHeavyRain", "HeavyRain", "rain"),
    66: ("Pioggia gelata debole", "freezing_rain", "conditionFreezingRain", "Sleet", "rain"),
    67: ("Pioggia gelata moderata o intensa", "freezing_rain", "conditionFreezingRain", "Sleet", "rain"),
    71: ("Nevicata debole", "snow", "conditionSnow", "Snow", "snow"),
    73: ("Nevicata moderata", "snow", "conditionSnow", "Snow", "snow"),
    75: ("Nevicata intensa", "snow", "conditionSnow", "Snow", "snow"),
    77: ("Granuli di neve", "snow_grains", "conditionSnow", "Snow", "snow"),
    80: ("Rovesci di pioggia deboli", "showers", "conditionShowers", "Showers", "rain"),
    81: ("Rovesci di pioggia moderati o intensi", "showers", "conditionShowers", "Showers", "rain"),
    82: ("Rovesci di pioggia violenti", "showers", "conditionShowers", "Showers", "rain"),
    85: ("Rovesci di neve deboli", "snow_showers", "conditionSnow", "Snow", "snow"),
    86: ("Rovesci di neve moderati o intensi", "snow_showers", "conditionSnow", "Snow", "snow"),
    95: ("Temporale debole o moderato", "storm", "conditionStorm", "Storm", "storm"),
    96: (
        "Temporale con grandine o temporale forte",
        "strong_storm",
        "conditionStrongStorm",
        "StrongStorm",
        "storm",
    ),
}

_ICON_HOURLY_KEYS = frozenset(
    {
        "valid_at",
        "interval_start",
        "interval_end",
        "temperature_c",
        "apparent_temperature_c",
        "relative_humidity_pct",
        "pressure_msl_hpa",
        "wind_speed_m_s",
        "wind_from_degrees",
        "wind_gust_max_m_s",
        "cloud_cover_pct",
        "precipitation_mm",
        "liquid_rain_mm",
        "snow_water_equivalent_mm",
        "condition",
        "quality_flags",
    }
)
_TWO_HOURLY_KEYS = frozenset(
    {
        "start_at",
        "end_at",
        "source_hours",
        "precipitation_mm",
        "wind_gust_max_m_s",
        "temperature_min_c",
        "temperature_max_c",
        "temperature_end_c",
        "status",
        "quality_flags",
    }
)


class ContractError(ValueError):
    """The document does not conform to the local weather v1 contract."""


@dataclass(frozen=True)
class Municipality:
    istat_code: str
    slug: str
    name: str
    province: str
    province_name: str
    latitude: float
    longitude: float

    def canonical_record(self) -> dict[str, Any]:
        return {
            "istat_code": self.istat_code,
            "slug": self.slug,
            "name": self.name,
            "province": self.province,
            "province_name": self.province_name,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


@dataclass(frozen=True)
class Catalog:
    version: str
    sha256: str
    municipalities: tuple[Municipality, ...]

    @property
    def municipality_count(self) -> int:
        return len(self.municipalities)

    @property
    def istat_codes(self) -> tuple[str, ...]:
        return tuple(item.istat_code for item in self.municipalities)

    def municipality(self, istat_code: str) -> Municipality:
        for item in self.municipalities:
            if item.istat_code == istat_code:
                return item
        raise ContractError(f"unknown municipality ISTAT code: {istat_code!r}")

    def reference(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sha256": self.sha256,
            "municipality_count": self.municipality_count,
        }


def canonical_json_bytes(value: Any) -> bytes:
    """Return the sole byte representation hashed by this v1 contract."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ContractError("document is not canonical JSON data") from error


def sha256_hex(value: bytes) -> str:
    if not isinstance(value, bytes):
        raise ContractError("SHA-256 input must be bytes")
    return hashlib.sha256(value).hexdigest()


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ContractError(f"{label} must be a finite number")
    return float(value)


def _number_or_null(
    value: Any,
    label: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> None:
    if value is None:
        return
    numeric = _finite_number(value, label)
    if minimum is not None and numeric < minimum:
        raise ContractError(f"{label} is below its minimum")
    if maximum is not None and numeric > maximum:
        raise ContractError(f"{label} is above its maximum")


def _exact_keys(value: Any, expected: set[str] | frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise ContractError(f"{label} has missing or extra fields")
    return value


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ContractError(f"{label} must be a trimmed non-empty string")
    return value


def _parse_utc(value: Any, label: str, *, on_hour: bool = False) -> datetime:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        raise ContractError(f"{label} must use canonical UTC seconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ContractError(f"{label} is not a valid UTC timestamp") from error
    if on_hour and (parsed.minute or parsed.second):
        raise ContractError(f"{label} must fall on an exact UTC hour")
    return parsed


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_run_id(run_at: str) -> str:
    run = _parse_utc(run_at, "run_at", on_hour=True)
    return run.strftime("%Y%m%dT%H%M%SZ")


def validate_run_id(source_run_id: Any, run_at: Any) -> None:
    if not isinstance(source_run_id, str) or not _RUN_ID_RE.fullmatch(source_run_id):
        raise ContractError("source_run_id is not canonical")
    if source_run_id != canonical_run_id(run_at):
        raise ContractError("source_run_id does not identify run_at")


def _validate_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ContractError(f"{label} must be 64 lowercase hexadecimal characters")
    return value


def _validate_flags(value: Any, label: str) -> None:
    if (
        not isinstance(value, list)
        or any(not isinstance(flag, str) or not flag or flag != flag.strip() for flag in value)
        or value != sorted(set(value))
    ):
        raise ContractError(f"{label} must be a sorted unique string array")


def _normalize_flags(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ContractError("quality flags must be an array")
    result = list(value)
    if any(not isinstance(flag, str) or not flag or flag != flag.strip() for flag in result):
        raise ContractError("quality flags contain an invalid value")
    return sorted(set(result))


def _catalog_from_authoritative_sources() -> Catalog:
    from .authoritative_catalog import load_authoritative_catalog, verify_catalog_hash

    source = load_authoritative_catalog()
    if not verify_catalog_hash(source):
        raise ContractError("authoritative municipality catalog hash is invalid")
    if (
        source.get("catalog_version") != CATALOG_VERSION
        or source.get("municipality_count") != EXPECTED_MUNICIPALITIES
        or not isinstance(source.get("municipalities"), list)
    ):
        raise ContractError("authoritative municipality catalog is incompatible")
    municipalities: list[Municipality] = []
    seen_istat: set[str] = set()
    seen_slugs: set[str] = set()
    for record in source["municipalities"]:
        point = record.get("representative_point") if isinstance(record, Mapping) else None
        if not isinstance(point, Mapping):
            raise ContractError("authoritative municipality point is missing")
        istat = record.get("istat_code")
        slug = record.get("slug")
        if not isinstance(istat, str) or not _ISTAT_RE.fullmatch(istat) or istat in seen_istat:
            raise ContractError("authoritative catalog has an invalid or duplicate ISTAT code")
        if not isinstance(slug, str) or not slug or slug != slug.strip() or slug in seen_slugs:
            raise ContractError("authoritative catalog has an invalid or duplicate slug")
        latitude = _finite_number(point.get("latitude"), f"municipality {istat} latitude")
        longitude = _finite_number(point.get("longitude"), f"municipality {istat} longitude")
        if not 45 <= latitude <= 47 or not 12 <= longitude <= 14.5:
            raise ContractError(f"municipality {istat} lies outside the FVG contract bounds")
        municipality = Municipality(
            istat_code=istat,
            slug=slug,
            name=_nonempty_string(record.get("name"), f"municipality {istat} name"),
            province=_nonempty_string(record.get("province"), f"municipality {istat} province").upper(),
            province_name=_nonempty_string(
                record.get("province_name"), f"municipality {istat} province_name"
            ),
            latitude=latitude,
            longitude=longitude,
        )
        if municipality.province not in {"GO", "PN", "TS", "UD"}:
            raise ContractError(f"municipality {istat} has an invalid province")
        municipalities.append(municipality)
        seen_istat.add(istat)
        seen_slugs.add(slug)
    municipalities.sort(key=lambda item: item.istat_code)
    if len(municipalities) != EXPECTED_MUNICIPALITIES:
        raise ContractError("authoritative catalog must contain exactly 215 municipalities")
    return Catalog(
        version=CATALOG_VERSION,
        sha256=source["catalog_sha256"],
        municipalities=tuple(municipalities),
    )


def load_catalog(path: str | Path | None = None) -> Catalog:
    """Load the authoritative catalog, or an explicit legacy test fixture.

    New ingestion calls this with no path and therefore never consumes the
    Open-Meteo-derived latitude/longitude fields in the historical JSON file.
    """
    if path is None:
        return _catalog_from_authoritative_sources()
    catalog_path = Path(path)
    try:
        raw = catalog_path.read_bytes()
        source = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError("municipality catalog cannot be loaded") from error
    _exact_keys(source, {"schemaVersion", "generatedFrom", "source", "municipalities"}, "catalog")
    if source["schemaVersion"] != 1:
        raise ContractError("unsupported municipality catalog schema")
    if not isinstance(source["municipalities"], list) or len(source["municipalities"]) != EXPECTED_MUNICIPALITIES:
        raise ContractError("catalog must contain exactly 215 municipalities")
    if not isinstance(source["source"], Mapping) or source["source"].get("count") != EXPECTED_MUNICIPALITIES:
        raise ContractError("catalog source count is inconsistent")

    municipalities: list[Municipality] = []
    seen_istat: set[str] = set()
    seen_slugs: set[str] = set()
    for position, record in enumerate(source["municipalities"]):
        if not isinstance(record, Mapping):
            raise ContractError(f"catalog municipality {position} is not an object")
        istat = record.get("istatCode")
        slug = record.get("slug")
        if not isinstance(istat, str) or not _ISTAT_RE.fullmatch(istat) or istat in seen_istat:
            raise ContractError("catalog contains an invalid or duplicate ISTAT code")
        if not isinstance(slug, str) or not slug or slug != slug.strip() or slug in seen_slugs:
            raise ContractError("catalog contains an invalid or duplicate slug")
        latitude = _finite_number(record.get("latitude"), f"municipality {istat} latitude")
        longitude = _finite_number(record.get("longitude"), f"municipality {istat} longitude")
        if not 45 <= latitude <= 47 or not 12 <= longitude <= 14.5:
            raise ContractError(f"municipality {istat} lies outside the FVG contract bounds")
        municipality = Municipality(
            istat_code=istat,
            slug=slug,
            name=_nonempty_string(record.get("name"), f"municipality {istat} name"),
            province=_nonempty_string(record.get("province"), f"municipality {istat} province").upper(),
            province_name=_nonempty_string(
                record.get("provinceName"), f"municipality {istat} provinceName"
            ),
            latitude=latitude,
            longitude=longitude,
        )
        if municipality.province not in {"GO", "PN", "TS", "UD"}:
            raise ContractError(f"municipality {istat} has an invalid province")
        municipalities.append(municipality)
        seen_istat.add(istat)
        seen_slugs.add(slug)

    municipalities.sort(key=lambda item: item.istat_code)
    canonical = {
        "schema_version": SCHEMA_VERSION,
        "version": LEGACY_FIXTURE_CATALOG_VERSION,
        "municipalities": [item.canonical_record() for item in municipalities],
    }
    return Catalog(
        version=LEGACY_FIXTURE_CATALOG_VERSION,
        sha256=sha256_hex(canonical_json_bytes(canonical)),
        municipalities=tuple(municipalities),
    )


def _validate_catalog_reference(value: Any, catalog: Catalog) -> None:
    _validate_catalog_reference_shape(value)
    if dict(value) != catalog.reference():
        raise ContractError("catalog reference does not match the loaded catalog")


def _validate_catalog_reference_shape(value: Any) -> None:
    _exact_keys(value, {"version", "sha256", "municipality_count"}, "catalog reference")
    if value["version"] not in SUPPORTED_CATALOG_VERSIONS:
        raise ContractError("catalog reference has an unsupported version")
    _validate_sha256(value["sha256"], "catalog sha256")
    if value["municipality_count"] != EXPECTED_MUNICIPALITIES:
        raise ContractError("catalog reference must identify exactly 215 municipalities")


def _provider_contract(provider: str) -> tuple[dict[str, str], dict[str, str], int]:
    if provider == ICON_PROVIDER:
        return ICON_MODEL, ICON_SOURCE, 72
    if provider in {CAMS_PROVIDER, CAMS_POLLEN_PROVIDER}:
        return CAMS_MODEL, CAMS_SOURCE, 96
    raise ContractError(f"unknown weather provider: {provider!r}")


def build_freshness(provider: str, run_at: str, valid_to: str) -> dict[str, Any]:
    run = _parse_utc(run_at, "run_at", on_hour=True)
    end = _parse_utc(valid_to, "valid_to", on_hour=True)
    if provider == ICON_PROVIDER:
        required_hours = 48
        policy_id = "icon2i_48h_v1"
        fresh = min(run + timedelta(hours=18), end - timedelta(hours=required_hours))
        usable = min(run + timedelta(hours=30), end - timedelta(hours=required_hours))
    elif provider in {CAMS_PROVIDER, CAMS_POLLEN_PROVIDER}:
        required_hours = 0
        policy_id = (
            "cams_current_v1"
            if provider == CAMS_PROVIDER
            else "cams_pollen_current_v1"
        )
        fresh = min(run + timedelta(hours=24), end)
        usable = min(run + timedelta(hours=30), end)
    else:
        raise ContractError("freshness provider is unknown")
    if fresh < run or usable < fresh:
        raise ContractError("source coverage cannot satisfy the freshness policy")
    return {
        "policy_id": policy_id,
        "fresh_until": _iso(fresh),
        "usable_until": _iso(usable),
        "required_future_hours": required_hours,
        "current_sample_max_lag_minutes": 60,
    }


def _validate_freshness(value: Any, provider: str, run_at: str, valid_to: str) -> None:
    _exact_keys(
        value,
        {
            "policy_id",
            "fresh_until",
            "usable_until",
            "required_future_hours",
            "current_sample_max_lag_minutes",
        },
        "freshness",
    )
    if dict(value) != build_freshness(provider, run_at, valid_to):
        raise ContractError("freshness metadata is inconsistent with provider coverage")


def classify_freshness(freshness: Mapping[str, Any], now: str) -> str:
    _exact_keys(
        freshness,
        {
            "policy_id",
            "fresh_until",
            "usable_until",
            "required_future_hours",
            "current_sample_max_lag_minutes",
        },
        "freshness",
    )
    current = _parse_utc(now, "now")
    fresh_until = _parse_utc(freshness["fresh_until"], "fresh_until")
    usable_until = _parse_utc(freshness["usable_until"], "usable_until")
    if current <= fresh_until:
        return "fresh"
    if current <= usable_until:
        return "stale"
    return "expired"


def build_icon_condition(native_code: int | None) -> dict[str, Any]:
    if native_code is None:
        return {
            "native_code": None,
            "native_status": "invalid",
            "native_label_it": "Condizione meteo non disponibile",
            "semantic_key": None,
            "text_key": None,
            "icon_key": None,
            "scene_key": None,
        }
    if isinstance(native_code, bool) or not isinstance(native_code, int):
        raise ContractError("ICON native weather code must be an integer or null")
    presentation = ICON_CONDITIONS.get(native_code)
    if presentation is None:
        return {
            "native_code": native_code,
            "native_status": "unknown",
            "native_label_it": "Codice meteo ICON-2I non riconosciuto",
            "semantic_key": None,
            "text_key": None,
            "icon_key": None,
            "scene_key": None,
        }
    label, semantic, text_key, icon_key, scene_key = presentation
    return {
        "native_code": native_code,
        "native_status": "valid",
        "native_label_it": label,
        "semantic_key": semantic,
        "text_key": text_key,
        "icon_key": icon_key,
        "scene_key": scene_key,
    }


def _validate_icon_condition(value: Any) -> None:
    keys = {
        "native_code",
        "native_status",
        "native_label_it",
        "semantic_key",
        "text_key",
        "icon_key",
        "scene_key",
    }
    _exact_keys(value, keys, "ICON condition")
    code = value["native_code"]
    if code is not None and (isinstance(code, bool) or not isinstance(code, int)):
        raise ContractError("ICON condition native_code must be integer or null")
    if dict(value) != build_icon_condition(code):
        raise ContractError("ICON condition does not match the v1 native/presentation taxonomy")
    if code == 96 and (
        value["semantic_key"] != "strong_storm"
        or value["icon_key"] != "StrongStorm"
        or value["scene_key"] != "storm"
    ):
        raise ContractError("ICON WW 96 must not assert hail")


def _build_municipality_identity(
    catalog: Catalog,
    istat_code: str,
    model_point: Mapping[str, Any],
) -> dict[str, Any]:
    municipality = catalog.municipality(istat_code)
    _validate_model_point(model_point)
    return {
        "istat_code": municipality.istat_code,
        "name": municipality.name,
        "slug": municipality.slug,
        "province": municipality.province,
        "representative_point": {
            "lat": municipality.latitude,
            "lon": municipality.longitude,
        },
        "model_point": deepcopy(dict(model_point)),
    }


def _validate_model_point(value: Any) -> None:
    _exact_keys(value, {"lat", "lon", "distance_km", "grid_index"}, "model point")
    latitude = _finite_number(value["lat"], "model point latitude")
    longitude = _finite_number(value["lon"], "model point longitude")
    distance = _finite_number(value["distance_km"], "model point distance")
    index = value["grid_index"]
    if not 45 <= latitude <= 47.2 or not 11.8 <= longitude <= 14.5 or distance < 0:
        raise ContractError("model point lies outside its supported domain")
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise ContractError("model point grid_index must be a non-negative integer")


def _validate_municipality_identity(value: Any, catalog: Catalog, expected_istat: str | None) -> str:
    keys = {
        "istat_code",
        "name",
        "slug",
        "province",
        "representative_point",
        "model_point",
    }
    _exact_keys(value, keys, "municipality identity")
    istat = value["istat_code"]
    if not isinstance(istat, str) or not _ISTAT_RE.fullmatch(istat):
        raise ContractError("municipality ISTAT code is invalid")
    if expected_istat is not None and istat != expected_istat:
        raise ContractError("payload municipality differs from the requested ISTAT code")
    municipality = catalog.municipality(istat)
    expected = {
        "istat_code": municipality.istat_code,
        "name": municipality.name,
        "slug": municipality.slug,
        "province": municipality.province,
        "representative_point": {
            "lat": municipality.latitude,
            "lon": municipality.longitude,
        },
    }
    if {key: value[key] for key in expected} != expected:
        raise ContractError("payload municipality identity differs from the catalog")
    _validate_model_point(value["model_point"])
    return istat


def _validate_common_payload(
    value: Any,
    *,
    provider: str,
    kind: str,
    catalog: Catalog,
    expected_istat_code: str | None,
    expected_extra_keys: set[str],
) -> tuple[datetime, str]:
    common = {
        "schema_version",
        "kind",
        "provider",
        "model",
        "source",
        "source_run_id",
        "run_at",
        "generated_at",
        "valid_from",
        "valid_to",
        "timezone",
        "freshness",
        "catalog",
        "municipality",
    }
    _exact_keys(value, common | expected_extra_keys, "provider payload")
    if value["schema_version"] != SCHEMA_VERSION or value["kind"] != kind or value["provider"] != provider:
        raise ContractError("provider payload envelope is incompatible with v1")
    model, source, horizon = _provider_contract(provider)
    if value["model"] != model or value["source"] != source:
        raise ContractError("provider model or source attribution is inconsistent")
    run = _parse_utc(value["run_at"], "run_at", on_hour=True)
    validate_run_id(value["source_run_id"], value["run_at"])
    generated = _parse_utc(value["generated_at"], "generated_at")
    if generated < run:
        raise ContractError("generated_at cannot precede the source run")
    if value["valid_from"] != value["run_at"]:
        raise ContractError("valid_from must equal run_at")
    valid_to = _parse_utc(value["valid_to"], "valid_to", on_hour=True)
    if valid_to != run + timedelta(hours=horizon):
        raise ContractError("provider payload has the wrong native horizon")
    if value["timezone"] != "Europe/Rome":
        raise ContractError("payload timezone must be Europe/Rome")
    _validate_freshness(value["freshness"], provider, value["run_at"], value["valid_to"])
    _validate_catalog_reference(value["catalog"], catalog)
    istat = _validate_municipality_identity(value["municipality"], catalog, expected_istat_code)
    return run, istat


def _validate_icon_hour(row: Any, expected_time: datetime, run: datetime) -> None:
    _exact_keys(row, _ICON_HOURLY_KEYS, "ICON hourly row")
    valid = _parse_utc(row["valid_at"], "ICON valid_at", on_hour=True)
    if valid != expected_time:
        raise ContractError("ICON hourly timeline is not consecutive")
    if valid == run:
        if row["interval_start"] is not None or row["interval_end"] is not None:
            raise ContractError("ICON lead zero cannot claim a previous-hour interval")
        for key in (
            "wind_gust_max_m_s",
            "precipitation_mm",
            "liquid_rain_mm",
            "snow_water_equivalent_mm",
        ):
            if row[key] is not None:
                raise ContractError(f"ICON lead zero {key} must be null")
    else:
        if row["interval_start"] != _iso(valid - timedelta(hours=1)) or row["interval_end"] != row["valid_at"]:
            raise ContractError("ICON interval does not represent the previous hour")

    for key in ("temperature_c", "apparent_temperature_c"):
        _number_or_null(row[key], f"ICON {key}")
    _number_or_null(row["relative_humidity_pct"], "ICON humidity", minimum=0, maximum=100)
    _number_or_null(row["pressure_msl_hpa"], "ICON pressure", minimum=0)
    _number_or_null(row["wind_speed_m_s"], "ICON wind speed", minimum=0)
    _number_or_null(row["wind_from_degrees"], "ICON wind direction", minimum=0)
    if row["wind_from_degrees"] is not None and row["wind_from_degrees"] >= 360:
        raise ContractError("ICON wind direction must be below 360 degrees")
    _number_or_null(row["wind_gust_max_m_s"], "ICON wind gust", minimum=0)
    _number_or_null(row["cloud_cover_pct"], "ICON cloud cover", minimum=0, maximum=100)
    for key in ("precipitation_mm", "liquid_rain_mm", "snow_water_equivalent_mm"):
        _number_or_null(row[key], f"ICON {key}", minimum=0)
    _validate_icon_condition(row["condition"])
    _validate_flags(row["quality_flags"], "ICON hourly quality_flags")


def _aggregate_two_hour(hourly: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for offset in range(1, len(hourly), 2):
        pair = hourly[offset : offset + 2]
        if len(pair) != 2:
            raise ContractError("ICON native horizon produced an unpaired two-hour interval")
        flags = set(pair[0]["quality_flags"]) | set(pair[1]["quality_flags"])
        missing: list[str] = []
        for key in ("precipitation_mm", "wind_gust_max_m_s", "temperature_c"):
            if any(row[key] is None for row in pair):
                missing.append(key)
                flags.add(f"missing_{key}")
        temperatures = [row["temperature_c"] for row in pair]
        precipitation = [row["precipitation_mm"] for row in pair]
        gusts = [row["wind_gust_max_m_s"] for row in pair]
        result.append(
            {
                "start_at": pair[0]["interval_start"],
                "end_at": pair[1]["interval_end"],
                "source_hours": 2,
                "precipitation_mm": sum(precipitation) if all(v is not None for v in precipitation) else None,
                "wind_gust_max_m_s": max(gusts) if all(v is not None for v in gusts) else None,
                "temperature_min_c": min(temperatures) if all(v is not None for v in temperatures) else None,
                "temperature_max_c": max(temperatures) if all(v is not None for v in temperatures) else None,
                "temperature_end_c": temperatures[-1],
                "status": "incomplete" if missing else "valid",
                "quality_flags": sorted(flags),
            }
        )
    return result


def build_icon_payload(
    *,
    catalog: Catalog,
    istat_code: str,
    run_at: str,
    generated_at: str,
    model_point: Mapping[str, Any],
    hourly: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    valid_to = _iso(_parse_utc(run_at, "run_at", on_hour=True) + timedelta(hours=72))
    normalized_hourly = []
    for row in hourly:
        copy = deepcopy(dict(row))
        copy["quality_flags"] = _normalize_flags(copy.get("quality_flags"))
        normalized_hourly.append(copy)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": ICON_PAYLOAD_KIND,
        "provider": ICON_PROVIDER,
        "model": deepcopy(ICON_MODEL),
        "source": deepcopy(ICON_SOURCE),
        "source_run_id": canonical_run_id(run_at),
        "run_at": run_at,
        "generated_at": generated_at,
        "valid_from": run_at,
        "valid_to": valid_to,
        "timezone": "Europe/Rome",
        "freshness": build_freshness(ICON_PROVIDER, run_at, valid_to),
        "catalog": catalog.reference(),
        "municipality": _build_municipality_identity(catalog, istat_code, model_point),
        "units": deepcopy(ICON_UNITS),
        "apparent_temperature_method": APPARENT_TEMPERATURE_METHOD,
        "hourly": normalized_hourly,
        "two_hourly": _aggregate_two_hour(normalized_hourly),
    }
    validate_icon_payload(payload, catalog, expected_istat_code=istat_code)
    return payload


def validate_icon_payload(
    value: Any,
    catalog: Catalog,
    *,
    expected_istat_code: str | None = None,
) -> Mapping[str, Any]:
    run, _ = _validate_common_payload(
        value,
        provider=ICON_PROVIDER,
        kind=ICON_PAYLOAD_KIND,
        catalog=catalog,
        expected_istat_code=expected_istat_code,
        expected_extra_keys={"units", "apparent_temperature_method", "hourly", "two_hourly"},
    )
    if value["units"] != ICON_UNITS:
        raise ContractError("ICON units differ from contract v1")
    if value["apparent_temperature_method"] != APPARENT_TEMPERATURE_METHOD:
        raise ContractError("ICON apparent-temperature provenance is unknown")
    hourly = value["hourly"]
    if not isinstance(hourly, list) or len(hourly) != 73:
        raise ContractError("ICON payload must contain exactly 73 native hourly samples")
    for lead, row in enumerate(hourly):
        _validate_icon_hour(row, run + timedelta(hours=lead), run)
    expected_two_hourly = _aggregate_two_hour(hourly)
    if not isinstance(value["two_hourly"], list) or len(value["two_hourly"]) != 36:
        raise ContractError("ICON payload must contain exactly 36 two-hour aggregates")
    for row in value["two_hourly"]:
        _exact_keys(row, _TWO_HOURLY_KEYS, "ICON two-hour row")
        _validate_flags(row["quality_flags"], "ICON two-hour quality_flags")
    if value["two_hourly"] != expected_two_hourly:
        raise ContractError("ICON two-hour aggregates do not match the hourly source")
    canonical_json_bytes(value)
    return value


def build_cams_payload(
    *,
    catalog: Catalog,
    istat_code: str,
    run_at: str,
    generated_at: str,
    model_point: Mapping[str, Any],
    hourly: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    valid_to = _iso(_parse_utc(run_at, "run_at", on_hour=True) + timedelta(hours=96))
    normalized_hourly = []
    for row in hourly:
        copy = deepcopy(dict(row))
        raw_flags = copy.get("quality_flags", {})
        if not isinstance(raw_flags, Mapping):
            raise ContractError("CAMS quality_flags must be an object")
        copy["quality_flags"] = {
            variable: _normalize_flags(raw_flags.get(variable)) for variable in CAMS_VARIABLE_IDS
        }
        normalized_hourly.append(copy)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": CAMS_PAYLOAD_KIND,
        "provider": CAMS_PROVIDER,
        "model": deepcopy(CAMS_MODEL),
        "source": deepcopy(CAMS_SOURCE),
        "source_run_id": canonical_run_id(run_at),
        "run_at": run_at,
        "generated_at": generated_at,
        "valid_from": run_at,
        "valid_to": valid_to,
        "timezone": "Europe/Rome",
        "freshness": build_freshness(CAMS_PROVIDER, run_at, valid_to),
        "catalog": catalog.reference(),
        "municipality": _build_municipality_identity(catalog, istat_code, model_point),
        "variables": deepcopy(CAMS_VARIABLES),
        "hourly": normalized_hourly,
        "health_classification": None,
    }
    validate_cams_payload(payload, catalog, expected_istat_code=istat_code)
    return payload


def validate_cams_payload(
    value: Any,
    catalog: Catalog,
    *,
    expected_istat_code: str | None = None,
) -> Mapping[str, Any]:
    run, _ = _validate_common_payload(
        value,
        provider=CAMS_PROVIDER,
        kind=CAMS_PAYLOAD_KIND,
        catalog=catalog,
        expected_istat_code=expected_istat_code,
        expected_extra_keys={"variables", "hourly", "health_classification"},
    )
    if value["variables"] != CAMS_VARIABLES:
        raise ContractError("CAMS v1 variables, units, or validation metadata differ from the 28-field contract")
    if value["health_classification"] is not None:
        raise ContractError("CAMS v1 cannot introduce an unvalidated health classification")
    hourly = value["hourly"]
    if not isinstance(hourly, list) or len(hourly) != 97:
        raise ContractError("CAMS payload must contain exactly 97 native hourly samples")
    for lead, row in enumerate(hourly):
        _exact_keys(row, {"valid_at", "values", "quality_flags"}, "CAMS hourly row")
        if _parse_utc(row["valid_at"], "CAMS valid_at", on_hour=True) != run + timedelta(hours=lead):
            raise ContractError("CAMS hourly timeline is not consecutive")
        _exact_keys(row["values"], set(CAMS_VARIABLE_IDS), "CAMS values")
        _exact_keys(row["quality_flags"], set(CAMS_VARIABLE_IDS), "CAMS quality flags")
        for variable in CAMS_VARIABLE_IDS:
            _number_or_null(row["values"][variable], f"CAMS {variable}", minimum=0)
            _validate_flags(row["quality_flags"][variable], f"CAMS {variable} quality_flags")
    canonical_json_bytes(value)
    return value


def build_cams_pollen_payload(
    *,
    catalog: Catalog,
    istat_code: str,
    run_at: str,
    generated_at: str,
    model_point: Mapping[str, Any],
    hourly: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the small public pollen view without discarding the full archive."""

    valid_to = _iso(_parse_utc(run_at, "run_at", on_hour=True) + timedelta(hours=96))
    normalized_hourly = []
    for row in hourly:
        if not isinstance(row, Mapping):
            raise ContractError("CAMS pollen hourly row must be an object")
        raw_values = row.get("values")
        raw_flags = row.get("quality_flags")
        if not isinstance(raw_values, Mapping) or not isinstance(raw_flags, Mapping):
            raise ContractError("CAMS pollen row values and flags must be objects")
        normalized_hourly.append(
            {
                "valid_at": row.get("valid_at"),
                "values": {
                    variable: raw_values.get(variable)
                    for variable in CAMS_POLLEN_IDS
                },
                "quality_flags": {
                    variable: _normalize_flags(raw_flags.get(variable))
                    for variable in CAMS_POLLEN_IDS
                },
            }
        )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": CAMS_POLLEN_PAYLOAD_KIND,
        "provider": CAMS_POLLEN_PROVIDER,
        "model": deepcopy(CAMS_MODEL),
        "source": deepcopy(CAMS_SOURCE),
        "source_run_id": canonical_run_id(run_at),
        "run_at": run_at,
        "generated_at": generated_at,
        "valid_from": run_at,
        "valid_to": valid_to,
        "timezone": "Europe/Rome",
        "freshness": build_freshness(CAMS_POLLEN_PROVIDER, run_at, valid_to),
        "catalog": catalog.reference(),
        "municipality": _build_municipality_identity(catalog, istat_code, model_point),
        "variables": deepcopy(CAMS_POLLEN_VARIABLES),
        "hourly": normalized_hourly,
        "health_classification": None,
        "projection": deepcopy(CAMS_POLLEN_PROJECTION),
    }
    validate_cams_pollen_payload(payload, catalog, expected_istat_code=istat_code)
    return payload


def validate_cams_pollen_payload(
    value: Any,
    catalog: Catalog,
    *,
    expected_istat_code: str | None = None,
) -> Mapping[str, Any]:
    run, _ = _validate_common_payload(
        value,
        provider=CAMS_POLLEN_PROVIDER,
        kind=CAMS_POLLEN_PAYLOAD_KIND,
        catalog=catalog,
        expected_istat_code=expected_istat_code,
        expected_extra_keys={
            "variables", "hourly", "health_classification", "projection"
        },
    )
    if value["variables"] != CAMS_POLLEN_VARIABLES:
        raise ContractError("CAMS pollen view must contain exactly the six pollen variables")
    if value["projection"] != CAMS_POLLEN_PROJECTION:
        raise ContractError("CAMS pollen projection provenance is invalid")
    if value["health_classification"] is not None:
        raise ContractError("CAMS pollen view cannot introduce a health classification")
    hourly = value["hourly"]
    if not isinstance(hourly, list) or len(hourly) != 97:
        raise ContractError("CAMS pollen view must contain exactly 97 hourly samples")
    expected_ids = set(CAMS_POLLEN_IDS)
    for lead, row in enumerate(hourly):
        _exact_keys(row, {"valid_at", "values", "quality_flags"}, "CAMS pollen hourly row")
        if _parse_utc(row["valid_at"], "CAMS pollen valid_at", on_hour=True) != run + timedelta(hours=lead):
            raise ContractError("CAMS pollen timeline is not consecutive")
        _exact_keys(row["values"], expected_ids, "CAMS pollen values")
        _exact_keys(row["quality_flags"], expected_ids, "CAMS pollen quality flags")
        for variable in CAMS_POLLEN_IDS:
            _number_or_null(row["values"][variable], f"CAMS pollen {variable}", minimum=0)
            _validate_flags(
                row["quality_flags"][variable],
                f"CAMS pollen {variable} quality_flags",
            )
    canonical_json_bytes(value)
    return value


def _payload_validator(provider: str):
    if provider == ICON_PROVIDER:
        return validate_icon_payload
    if provider == CAMS_PROVIDER:
        return validate_cams_payload
    if provider == CAMS_POLLEN_PROVIDER:
        return validate_cams_pollen_payload
    raise ContractError("unknown provider")


def _object_path(source_run_id: str, istat_code: str) -> str:
    return f"runs/{source_run_id}/municipalities/{istat_code}.json"


def build_object_descriptor(
    *,
    provider: str,
    source_run_id: str,
    istat_code: str,
    payload: Mapping[str, Any] | bytes,
    catalog: Catalog,
) -> dict[str, Any]:
    if not _RUN_ID_RE.fullmatch(source_run_id) or not _ISTAT_RE.fullmatch(istat_code):
        raise ContractError("object descriptor run or ISTAT identity is invalid")
    if isinstance(payload, bytes):
        try:
            parsed = json.loads(payload)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ContractError("object payload bytes are not JSON") from error
        if canonical_json_bytes(parsed) != payload:
            raise ContractError("object payload bytes are not canonical v1 JSON")
        encoded = payload
    elif isinstance(payload, Mapping):
        parsed = payload
        encoded = canonical_json_bytes(payload)
    else:
        raise ContractError("object payload must be a mapping or canonical JSON bytes")
    _payload_validator(provider)(parsed, catalog, expected_istat_code=istat_code)
    if parsed["source_run_id"] != source_run_id:
        raise ContractError("object payload run differs from its path")
    if not 1 <= len(encoded) <= MAX_PAYLOAD_JSON_BYTES:
        raise ContractError("object payload exceeds the v1 public JSON size cap")
    return {
        "path": _object_path(source_run_id, istat_code),
        "json_bytes": len(encoded),
        "sha256": sha256_hex(encoded),
    }


def _validate_object_descriptor(
    value: Any,
    *,
    source_run_id: str,
    istat_code: str,
) -> None:
    _exact_keys(value, {"path", "json_bytes", "sha256"}, "run object descriptor")
    if value["path"] != _object_path(source_run_id, istat_code):
        raise ContractError("run object path is not canonical")
    size = value["json_bytes"]
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= MAX_PAYLOAD_JSON_BYTES:
        raise ContractError("run object JSON size is invalid")
    _validate_sha256(value["sha256"], "run object sha256")


def build_run_manifest(
    *,
    provider: str,
    run_at: str,
    generated_at: str,
    catalog: Catalog,
    objects: Mapping[str, Mapping[str, Any] | bytes],
) -> dict[str, Any]:
    model, source, horizon = _provider_contract(provider)
    source_run_id = canonical_run_id(run_at)
    valid_to = _iso(_parse_utc(run_at, "run_at", on_hour=True) + timedelta(hours=horizon))
    descriptors: dict[str, Any] = {}
    if not isinstance(objects, Mapping):
        raise ContractError("run objects must be keyed by ISTAT code")
    for istat_code, item in objects.items():
        if isinstance(item, Mapping) and set(item) == {"path", "json_bytes", "sha256"}:
            descriptor = deepcopy(dict(item))
        else:
            descriptor = build_object_descriptor(
                provider=provider,
                source_run_id=source_run_id,
                istat_code=istat_code,
                payload=item,
                catalog=catalog,
            )
        descriptors[istat_code] = descriptor
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": RUN_MANIFEST_KIND,
        "provider": provider,
        "model": deepcopy(model),
        "source": deepcopy(source),
        "source_run_id": source_run_id,
        "run_at": run_at,
        "generated_at": generated_at,
        "valid_from": run_at,
        "valid_to": valid_to,
        "freshness": build_freshness(provider, run_at, valid_to),
        "catalog": catalog.reference(),
        "objects": descriptors,
    }
    validate_run_manifest(manifest, catalog, expected_provider=provider)
    return manifest


def validate_run_manifest(
    value: Any,
    catalog: Catalog,
    *,
    expected_provider: str | None = None,
    object_bodies: Mapping[str, Mapping[str, Any] | bytes] | None = None,
) -> Mapping[str, Any]:
    keys = {
        "schema_version",
        "kind",
        "provider",
        "model",
        "source",
        "source_run_id",
        "run_at",
        "generated_at",
        "valid_from",
        "valid_to",
        "freshness",
        "catalog",
        "objects",
    }
    _exact_keys(value, keys, "run manifest")
    provider = value["provider"]
    if value["schema_version"] != SCHEMA_VERSION or value["kind"] != RUN_MANIFEST_KIND:
        raise ContractError("run manifest envelope is incompatible with v1")
    if expected_provider is not None and provider != expected_provider:
        raise ContractError("run manifest provider differs from the expected provider")
    model, source, horizon = _provider_contract(provider)
    if value["model"] != model or value["source"] != source:
        raise ContractError("run manifest provider metadata is inconsistent")
    run = _parse_utc(value["run_at"], "run_at", on_hour=True)
    validate_run_id(value["source_run_id"], value["run_at"])
    if _parse_utc(value["generated_at"], "generated_at") < run:
        raise ContractError("run manifest generated_at precedes run_at")
    if value["valid_from"] != value["run_at"]:
        raise ContractError("run manifest valid_from must equal run_at")
    if _parse_utc(value["valid_to"], "valid_to", on_hour=True) != run + timedelta(hours=horizon):
        raise ContractError("run manifest native horizon is invalid")
    _validate_freshness(value["freshness"], provider, value["run_at"], value["valid_to"])
    _validate_catalog_reference(value["catalog"], catalog)
    objects = value["objects"]
    if not isinstance(objects, Mapping) or set(objects) != set(catalog.istat_codes):
        raise ContractError("run manifest must contain exactly the catalog's 215 ISTAT objects")
    for istat_code, descriptor in objects.items():
        _validate_object_descriptor(
            descriptor,
            source_run_id=value["source_run_id"],
            istat_code=istat_code,
        )
    if object_bodies is not None:
        if not isinstance(object_bodies, Mapping) or set(object_bodies) != set(catalog.istat_codes):
            raise ContractError("object bodies must cover exactly the catalog")
        for istat_code, body in object_bodies.items():
            expected = build_object_descriptor(
                provider=provider,
                source_run_id=value["source_run_id"],
                istat_code=istat_code,
                payload=body,
                catalog=catalog,
            )
            if objects[istat_code] != expected:
                raise ContractError(f"run object integrity mismatch for ISTAT {istat_code}")
    canonical_json_bytes(value)
    return value


def _manifest_descriptor(manifest: Mapping[str, Any], catalog: Catalog) -> dict[str, Any]:
    validate_run_manifest(manifest, catalog)
    encoded = canonical_json_bytes(manifest)
    return {
        "source_run_id": manifest["source_run_id"],
        "run_at": manifest["run_at"],
        "manifest_path": f"runs/{manifest['source_run_id']}/manifest.json",
        "manifest_json_bytes": len(encoded),
        "manifest_sha256": sha256_hex(encoded),
    }


def _validate_manifest_descriptor(value: Any) -> None:
    keys = {
        "source_run_id",
        "run_at",
        "manifest_path",
        "manifest_json_bytes",
        "manifest_sha256",
    }
    _exact_keys(value, keys, "latest manifest descriptor")
    validate_run_id(value["source_run_id"], value["run_at"])
    if value["manifest_path"] != f"runs/{value['source_run_id']}/manifest.json":
        raise ContractError("latest manifest path is not canonical")
    size = value["manifest_json_bytes"]
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ContractError("latest manifest size is invalid")
    _validate_sha256(value["manifest_sha256"], "latest manifest sha256")


def build_latest_document(
    *,
    provider: str,
    revision: int,
    published_at: str,
    run_manifest: Mapping[str, Any],
    catalog: Catalog,
    previous_manifest: Mapping[str, Any] | None = None,
    disabled_run_ids: Sequence[str] = (),
) -> dict[str, Any]:
    validate_run_manifest(run_manifest, catalog, expected_provider=provider)
    if previous_manifest is not None:
        validate_run_manifest(previous_manifest, catalog, expected_provider=provider)
    latest = {
        "schema_version": SCHEMA_VERSION,
        "kind": LATEST_KIND,
        "provider": provider,
        "revision": revision,
        "published_at": published_at,
        "catalog": catalog.reference(),
        "latest": _manifest_descriptor(run_manifest, catalog),
        "previous": _manifest_descriptor(previous_manifest, catalog) if previous_manifest else None,
        "disabled_run_ids": sorted(set(disabled_run_ids)),
    }
    validate_latest_document(
        latest,
        expected_provider=provider,
        catalog=catalog,
        run_manifest=run_manifest,
        previous_manifest=previous_manifest,
    )
    return latest


def validate_latest_document(
    value: Any,
    *,
    expected_provider: str | None = None,
    catalog: Catalog | None = None,
    run_manifest: Mapping[str, Any] | None = None,
    previous_manifest: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    keys = {
        "schema_version",
        "kind",
        "provider",
        "revision",
        "published_at",
        "catalog",
        "latest",
        "previous",
        "disabled_run_ids",
    }
    _exact_keys(value, keys, "latest document")
    if value["schema_version"] != SCHEMA_VERSION or value["kind"] != LATEST_KIND:
        raise ContractError("latest document envelope is incompatible with v1")
    provider = value["provider"]
    _provider_contract(provider)
    if expected_provider is not None and provider != expected_provider:
        raise ContractError("latest document provider differs from the expected provider")
    _validate_catalog_reference_shape(value["catalog"])
    if catalog is not None:
        _validate_catalog_reference(value["catalog"], catalog)
    revision = value["revision"]
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ContractError("latest revision must be a positive integer")
    _parse_utc(value["published_at"], "published_at")
    _validate_manifest_descriptor(value["latest"])
    if value["previous"] is not None:
        _validate_manifest_descriptor(value["previous"])
        if value["previous"]["source_run_id"] == value["latest"]["source_run_id"]:
            raise ContractError("latest and previous cannot identify the same run")
    disabled = value["disabled_run_ids"]
    if not isinstance(disabled, list) or disabled != sorted(set(disabled)):
        raise ContractError("disabled_run_ids must be a sorted unique array")
    for run_id in disabled:
        if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
            raise ContractError("disabled_run_ids contains a non-canonical run")
    if value["latest"]["source_run_id"] in disabled:
        raise ContractError("latest run is disabled")
    if run_manifest is not None:
        if catalog is None:
            raise ContractError("catalog is required to verify an immutable run manifest")
        validate_run_manifest(run_manifest, catalog, expected_provider=provider)
        if value["latest"] != _manifest_descriptor(run_manifest, catalog):
            raise ContractError("latest pointer does not match the immutable run manifest")
    if previous_manifest is not None:
        if catalog is None:
            raise ContractError("catalog is required to verify the previous run manifest")
        validate_run_manifest(previous_manifest, catalog, expected_provider=provider)
        if value["previous"] != _manifest_descriptor(previous_manifest, catalog):
            raise ContractError("previous pointer does not match the immutable run manifest")
    canonical_json_bytes(value)
    return value


# Short aliases for callers that prefer the artifact names.
build_latest = build_latest_document
validate_latest = validate_latest_document
