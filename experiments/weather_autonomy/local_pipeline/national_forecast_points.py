"""Strict national forecast-point artifact contract.

The artifact defined here is the reviewed bridge between municipality-source
resolution and an ICON grid mapping.  It is deliberately independent from the
resolver and benchmark runners so both sides validate exactly the same bytes.

Approved artifacts contain one WGS 84 point for every municipality in their
bound catalog.  Experimental generalized-boundary points use a separate status
and quality and are rejected unless a caller explicitly opts in.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit


FORECAST_POINTS_KIND = "meteofriul.weather.national_forecast_points"
FORECAST_POINTS_SCHEMA_VERSION = 2

APPROVED_POINTS_STATUS = "approved_for_icon_mapping"
EXPERIMENTAL_POINTS_STATUS = "experimental_proxy"

QUALITY_OFFICIAL_ISTAT_CAPOLUOGO = "official_istat_capoluogo"
QUALITY_OFFICIAL_DBGT = "official_dbgt"
QUALITY_EXACT_ACCESS = "exact_access"
QUALITY_SEAT_AREA_PROXY = "seat_area_proxy"
QUALITY_EXPERIMENTAL_BOUNDARY_PROXY = "experimental_boundary_interior_proxy"

APPROVED_POINT_QUALITIES = frozenset(
    {
        QUALITY_OFFICIAL_ISTAT_CAPOLUOGO,
        QUALITY_OFFICIAL_DBGT,
        QUALITY_EXACT_ACCESS,
        QUALITY_SEAT_AREA_PROXY,
    }
)
EXPERIMENTAL_POINT_QUALITIES = frozenset(
    {QUALITY_EXPERIMENTAL_BOUNDARY_PROXY}
)
ALL_POINT_QUALITIES = APPROVED_POINT_QUALITIES | EXPERIMENTAL_POINT_QUALITIES

METHOD_BY_QUALITY = {
    QUALITY_OFFICIAL_ISTAT_CAPOLUOGO: "official_istat_capoluogo_v1",
    QUALITY_OFFICIAL_DBGT: "official_dbgt_v1",
    QUALITY_EXACT_ACCESS: "anncsu_exact_access_v1",
    QUALITY_SEAT_AREA_PROXY: "reviewed_seat_area_proxy_v1",
    QUALITY_EXPERIMENTAL_BOUNDARY_PROXY: "istat_boundary_interior_point_v1",
}

OUTPUT_COORDINATE_REFERENCE_SYSTEM = {
    "axis_order": ["latitude", "longitude"],
    "id": "EPSG:4326",
}

_TOP_LEVEL_KEYS = frozenset(
    {
        "artifact_sha256",
        "boundary_sha256",
        "catalog_sha256",
        "coordinate_reference_system",
        "kind",
        "municipality_codes_sha256",
        "point_count",
        "points",
        "points_sha256",
        "quality_counts",
        "resolution_policy_sha256",
        "schema_version",
        "source_manifest_sha256",
        "status",
    }
)
_POINT_KEYS = frozenset(
    {"istat_code", "latitude", "longitude", "method", "quality", "source"}
)
_OFFICIAL_ISTAT_SOURCE_KEYS = frozenset(
    {
        "authority",
        "current_istat_code",
        "dataset",
        "dataset_sha256",
        "loc_id",
        "mapping_method",
        "reference_date",
        "source_istat_code",
        "source_crs",
        "url",
    }
)
_EXACT_ACCESS_SOURCE_KEYS = frozenset(
    {
        "address_match_method",
        "archive_sha256",
        "authority",
        "cadastral_code",
        "coordinate_method",
        "current_istat_code",
        "dataset",
        "progressivo_accesso",
        "progressivo_nazionale",
        "reconciliation_audit_sha256",
        "reference_date",
        "source_crs",
        "url",
    }
)
_OFFICIAL_DBGT_SOURCE_KEYS = frozenset(
    {
        "authority",
        "current_istat_code",
        "dataset",
        "dataset_sha256",
        "feature_id",
        "layer_name",
        "mapping_method",
        "reference_date",
        "source_crs",
        "url",
    }
)
_SEAT_AREA_PROXY_SOURCE_KEYS = frozenset(
    {
        "authority",
        "component_count",
        "current_istat_code",
        "dataset",
        "derivation_sha256",
        "input_records_sha256",
        "mapping_method",
        "max_radius_m",
        "reference_date",
        "review_decision_sha256",
        "source_crs",
        "url",
    }
)
_EXPERIMENTAL_PROXY_SOURCE_KEYS = frozenset(
    {
        "authority",
        "catalog_sha256",
        "current_istat_code",
        "dataset",
        "dataset_sha256",
        "reference_date",
        "source_crs",
        "source_field",
        "url",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ISTAT_RE = re.compile(r"^\d{6}$")
_CADASTRAL_RE = re.compile(r"^[A-Z]\d{3}$")
_POSITIVE_INTEGER_TEXT_RE = re.compile(r"^[1-9]\d*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

OFFICIAL_ISTAT_MAPPING_METHODS = frozenset(
    {
        "direct_current_istat_code_v1",
        "registry_2017_2025_code_v1",
        "reviewed_post_2021_seat_override_v1",
    }
)
OFFICIAL_DBGT_MAPPING_METHODS = frozenset(
    {
        "current_istat_code_exact_v1",
        "reviewed_feature_identity_v1",
        "reviewed_municipality_code_crosswalk_v1",
    }
)

_MIN_LATITUDE = 35.0
_MAX_LATITUDE = 48.8
_MIN_LONGITUDE = 5.8
_MAX_LONGITUDE = 19.8
_MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
_MAX_TEXT_CHARS = 2_048


class NationalForecastPointsError(ValueError):
    """A document violates the national forecast-point v2 contract."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the sole JSON encoding accepted and hashed by this contract."""

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise NationalForecastPointsError(
            "forecast-point document is not canonical JSON data"
        ) from error


def sha256_hex(value: bytes) -> str:
    if not isinstance(value, bytes):
        raise NationalForecastPointsError("SHA-256 input must be bytes")
    return hashlib.sha256(value).hexdigest()


def _require_exact_keys(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    if frozenset(value) != expected:
        raise NationalForecastPointsError(f"{label} has missing or extra fields")


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise NationalForecastPointsError(f"{label} is not a SHA-256 digest")
    return value


def _strict_text(value: Any, label: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 for character in value)
    ):
        raise NationalForecastPointsError(f"{label} is invalid")
    return value


def _reference_date(value: Any, label: str) -> str:
    value = _strict_text(value, label, maximum=10)
    if _DATE_RE.fullmatch(value) is None:
        raise NationalForecastPointsError(f"{label} must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise NationalForecastPointsError(f"{label} is not a valid date") from error
    if parsed.isoformat() != value:
        raise NationalForecastPointsError(f"{label} is not canonical")
    return value


def _https_url(value: Any, label: str) -> str:
    value = _strict_text(value, label, maximum=_MAX_TEXT_CHARS)
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise NationalForecastPointsError(f"{label} must be a canonical HTTPS URL")
    return value


def _official_source_url(
    value: Any, label: str, *, allowed_domains: Sequence[str]
) -> str:
    value = _https_url(value, label)
    hostname = (urlsplit(value).hostname or "").casefold()
    if not any(
        hostname == domain or hostname.endswith("." + domain)
        for domain in allowed_domains
    ):
        raise NationalForecastPointsError(
            f"{label} is not hosted by the required institutional source"
        )
    return value


def _coordinate(value: Any, label: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NationalForecastPointsError(f"{label} is not numeric")
    number = float(value)
    if (
        not math.isfinite(number)
        or not minimum <= number <= maximum
        or number != round(number, 7)
    ):
        raise NationalForecastPointsError(
            f"{label} is outside the contract bounds or precision"
        )
    return number


def _source_common(
    value: Mapping[str, Any], *, istat_code: str
) -> dict[str, Any]:
    current_istat_code = value.get("current_istat_code")
    if current_istat_code != istat_code:
        raise NationalForecastPointsError(
            f"forecast point {istat_code} source municipality binding is invalid"
        )
    return {
        "authority": _strict_text(
            value["authority"], f"forecast point {istat_code} source authority"
        ),
        "current_istat_code": istat_code,
        "dataset": _strict_text(
            value["dataset"], f"forecast point {istat_code} source dataset"
        ),
        "reference_date": _reference_date(
            value["reference_date"],
            f"forecast point {istat_code} source reference date",
        ),
        "source_crs": _strict_text(
            value["source_crs"],
            f"forecast point {istat_code} source CRS",
            maximum=128,
        ),
    }


def _positive_integer_text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 32
        or _POSITIVE_INTEGER_TEXT_RE.fullmatch(value) is None
    ):
        raise NationalForecastPointsError(f"{label} must be a positive integer string")
    return value


def _normalize_official_istat_source(
    value: Mapping[str, Any], *, istat_code: str
) -> dict[str, Any]:
    _require_exact_keys(
        value,
        _OFFICIAL_ISTAT_SOURCE_KEYS,
        f"forecast point {istat_code} official ISTAT source",
    )
    common = _source_common(value, istat_code=istat_code)
    if common["authority"] != "Istituto nazionale di statistica (Istat)":
        raise NationalForecastPointsError(
            f"forecast point {istat_code} official ISTAT authority is invalid"
        )
    if (
        common["source_crs"] != "EPSG:32632"
        or common["reference_date"] != "2021-12-31"
    ):
        raise NationalForecastPointsError(
            f"forecast point {istat_code} official ISTAT release identity is invalid"
        )
    source_istat_code = value["source_istat_code"]
    if (
        not isinstance(source_istat_code, str)
        or _ISTAT_RE.fullmatch(source_istat_code) is None
    ):
        raise NationalForecastPointsError(
            f"forecast point {istat_code} source ISTAT code is invalid"
        )
    mapping_method = value["mapping_method"]
    if mapping_method not in OFFICIAL_ISTAT_MAPPING_METHODS:
        raise NationalForecastPointsError(
            f"forecast point {istat_code} ISTAT mapping method is invalid"
        )
    codes_match = source_istat_code == istat_code
    mapping_is_direct = mapping_method == "direct_current_istat_code_v1"
    if mapping_is_direct != codes_match:
        raise NationalForecastPointsError(
            f"forecast point {istat_code} ISTAT mapping method conflicts with source identity"
        )
    return {
        **common,
        "dataset_sha256": _sha256(
            value["dataset_sha256"],
            f"forecast point {istat_code} ISTAT dataset SHA-256",
        ),
        "loc_id": _positive_integer_text(
            value["loc_id"], f"forecast point {istat_code} ISTAT LOC_ID"
        ),
        "mapping_method": mapping_method,
        "source_istat_code": source_istat_code,
        "url": _official_source_url(
            value["url"],
            f"forecast point {istat_code} ISTAT source URL",
            allowed_domains=("istat.it",),
        ),
    }


def _normalize_exact_access_source(
    value: Mapping[str, Any], *, istat_code: str
) -> dict[str, Any]:
    _require_exact_keys(
        value,
        _EXACT_ACCESS_SOURCE_KEYS,
        f"forecast point {istat_code} ANNCSU exact-access source",
    )
    common = _source_common(value, istat_code=istat_code)
    cadastral_code = value["cadastral_code"]
    if not isinstance(cadastral_code, str) or _CADASTRAL_RE.fullmatch(cadastral_code) is None:
        raise NationalForecastPointsError(
            f"forecast point {istat_code} cadastral code is invalid"
        )
    coordinate_method = value["coordinate_method"]
    if coordinate_method not in {"1", "2", "3", "4", "5"}:
        raise NationalForecastPointsError(
            f"forecast point {istat_code} ANNCSU coordinate method is invalid"
        )
    if value["address_match_method"] != "indicepa_anncsu_exact_v1":
        raise NationalForecastPointsError(
            f"forecast point {istat_code} ANNCSU address-match method is invalid"
        )
    return {
        "address_match_method": "indicepa_anncsu_exact_v1",
        "archive_sha256": _sha256(
            value["archive_sha256"],
            f"forecast point {istat_code} ANNCSU archive SHA-256",
        ),
        **common,
        "cadastral_code": cadastral_code,
        "coordinate_method": coordinate_method,
        "progressivo_accesso": _positive_integer_text(
            value["progressivo_accesso"],
            f"forecast point {istat_code} ANNCSU access progressive",
        ),
        "progressivo_nazionale": _positive_integer_text(
            value["progressivo_nazionale"],
            f"forecast point {istat_code} ANNCSU street progressive",
        ),
        "reconciliation_audit_sha256": _sha256(
            value["reconciliation_audit_sha256"],
            f"forecast point {istat_code} reconciliation audit SHA-256",
        ),
        "url": _official_source_url(
            value["url"],
            f"forecast point {istat_code} ANNCSU source URL",
            allowed_domains=("anncsu.gov.it", "agenziaentrate.gov.it"),
        ),
    }


def _normalize_official_dbgt_source(
    value: Mapping[str, Any], *, istat_code: str
) -> dict[str, Any]:
    _require_exact_keys(
        value,
        _OFFICIAL_DBGT_SOURCE_KEYS,
        f"forecast point {istat_code} official DBGT source",
    )
    common = _source_common(value, istat_code=istat_code)
    mapping_method = value["mapping_method"]
    if mapping_method not in OFFICIAL_DBGT_MAPPING_METHODS:
        raise NationalForecastPointsError(
            f"forecast point {istat_code} DBGT mapping method is invalid"
        )
    return {
        **common,
        "dataset_sha256": _sha256(
            value["dataset_sha256"],
            f"forecast point {istat_code} DBGT dataset SHA-256",
        ),
        "feature_id": _strict_text(
            value["feature_id"], f"forecast point {istat_code} DBGT feature ID"
        ),
        "layer_name": _strict_text(
            value["layer_name"], f"forecast point {istat_code} DBGT layer name"
        ),
        "mapping_method": mapping_method,
        "url": _https_url(
            value["url"], f"forecast point {istat_code} DBGT source URL"
        ),
    }


def _normalize_seat_area_proxy_source(
    value: Mapping[str, Any], *, istat_code: str
) -> dict[str, Any]:
    _require_exact_keys(
        value,
        _SEAT_AREA_PROXY_SOURCE_KEYS,
        f"forecast point {istat_code} seat-area proxy source",
    )
    common = _source_common(value, istat_code=istat_code)
    component_count = value["component_count"]
    if (
        isinstance(component_count, bool)
        or not isinstance(component_count, int)
        or not 1 <= component_count <= 10_000
    ):
        raise NationalForecastPointsError(
            f"forecast point {istat_code} proxy component count is invalid"
        )
    max_radius_m = value["max_radius_m"]
    if isinstance(max_radius_m, bool) or not isinstance(max_radius_m, (int, float)):
        raise NationalForecastPointsError(
            f"forecast point {istat_code} proxy radius is invalid"
        )
    max_radius_m = float(max_radius_m)
    if not math.isfinite(max_radius_m) or not 0 <= max_radius_m <= 5_000:
        raise NationalForecastPointsError(
            f"forecast point {istat_code} proxy radius is invalid"
        )
    if value["mapping_method"] != "reviewed_seat_area_proxy_v1":
        raise NationalForecastPointsError(
            f"forecast point {istat_code} proxy mapping method is invalid"
        )
    return {
        **common,
        "component_count": component_count,
        "derivation_sha256": _sha256(
            value["derivation_sha256"],
            f"forecast point {istat_code} proxy derivation SHA-256",
        ),
        "input_records_sha256": _sha256(
            value["input_records_sha256"],
            f"forecast point {istat_code} proxy input-record SHA-256",
        ),
        "mapping_method": "reviewed_seat_area_proxy_v1",
        "max_radius_m": max_radius_m,
        "review_decision_sha256": _sha256(
            value["review_decision_sha256"],
            f"forecast point {istat_code} proxy review-decision SHA-256",
        ),
        "url": _https_url(
            value["url"], f"forecast point {istat_code} proxy source URL"
        ),
    }


def _normalize_experimental_proxy_source(
    value: Mapping[str, Any], *, istat_code: str
) -> dict[str, Any]:
    _require_exact_keys(
        value,
        _EXPERIMENTAL_PROXY_SOURCE_KEYS,
        f"forecast point {istat_code} experimental proxy source",
    )
    common = _source_common(value, istat_code=istat_code)
    if common["authority"] != "Istituto nazionale di statistica (Istat)":
        raise NationalForecastPointsError(
            f"forecast point {istat_code} experimental proxy authority is invalid"
        )
    if common["source_crs"] != "EPSG:4326":
        raise NationalForecastPointsError(
            f"forecast point {istat_code} experimental proxy source CRS is invalid"
        )
    if value["source_field"] != "representative_point":
        raise NationalForecastPointsError(
            f"forecast point {istat_code} experimental proxy source field is invalid"
        )
    return {
        **common,
        "catalog_sha256": _sha256(
            value["catalog_sha256"],
            f"forecast point {istat_code} proxy catalog SHA-256",
        ),
        "dataset_sha256": _sha256(
            value["dataset_sha256"],
            f"forecast point {istat_code} proxy dataset SHA-256",
        ),
        "source_field": "representative_point",
        "url": _official_source_url(
            value["url"],
            f"forecast point {istat_code} experimental proxy source URL",
            allowed_domains=("istat.it",),
        ),
    }


def _normalize_source(
    value: Any, *, istat_code: str, quality: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise NationalForecastPointsError(
            f"forecast point {istat_code} source is invalid"
        )
    normalizer = {
        QUALITY_OFFICIAL_ISTAT_CAPOLUOGO: _normalize_official_istat_source,
        QUALITY_OFFICIAL_DBGT: _normalize_official_dbgt_source,
        QUALITY_EXACT_ACCESS: _normalize_exact_access_source,
        QUALITY_SEAT_AREA_PROXY: _normalize_seat_area_proxy_source,
        QUALITY_EXPERIMENTAL_BOUNDARY_PROXY: _normalize_experimental_proxy_source,
    }[quality]
    return normalizer(value, istat_code=istat_code)


def _normalize_point(value: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise NationalForecastPointsError(f"forecast point {index} is invalid")
    _require_exact_keys(value, _POINT_KEYS, f"forecast point {index}")
    istat_code = value["istat_code"]
    if not isinstance(istat_code, str) or _ISTAT_RE.fullmatch(istat_code) is None:
        raise NationalForecastPointsError(f"forecast point {index} ISTAT code is invalid")
    quality = value["quality"]
    if not isinstance(quality, str) or quality not in ALL_POINT_QUALITIES:
        raise NationalForecastPointsError(
            f"forecast point {istat_code} quality is invalid"
        )
    expected_method = METHOD_BY_QUALITY[quality]
    if value["method"] != expected_method:
        raise NationalForecastPointsError(
            f"forecast point {istat_code} method does not match quality"
        )
    return {
        "istat_code": istat_code,
        "latitude": _coordinate(
            value["latitude"],
            f"forecast point {istat_code} latitude",
            _MIN_LATITUDE,
            _MAX_LATITUDE,
        ),
        "longitude": _coordinate(
            value["longitude"],
            f"forecast point {istat_code} longitude",
            _MIN_LONGITUDE,
            _MAX_LONGITUDE,
        ),
        "method": expected_method,
        "quality": quality,
        "source": _normalize_source(
            value["source"], istat_code=istat_code, quality=quality
        ),
    }


def _catalog_reference(catalog: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(catalog, Mapping):
        raise NationalForecastPointsError("national catalog must be an object")
    catalog_sha256 = _sha256(catalog.get("catalog_sha256"), "catalog SHA-256")
    municipalities = catalog.get("municipalities")
    municipality_count = catalog.get("municipality_count")
    if (
        isinstance(municipality_count, bool)
        or not isinstance(municipality_count, int)
        or municipality_count < 1
        or not isinstance(municipalities, list)
        or len(municipalities) != municipality_count
    ):
        raise NationalForecastPointsError("national catalog municipality count is invalid")

    content = dict(catalog)
    content.pop("catalog_sha256", None)
    if sha256_hex(canonical_json_bytes(content)) != catalog_sha256:
        raise NationalForecastPointsError("national catalog SHA-256 mismatch")

    codes: list[str] = []
    for index, municipality in enumerate(municipalities):
        if not isinstance(municipality, Mapping):
            raise NationalForecastPointsError(
                f"catalog municipality {index} is invalid"
            )
        code = municipality.get("istat_code")
        if not isinstance(code, str) or _ISTAT_RE.fullmatch(code) is None:
            raise NationalForecastPointsError(
                f"catalog municipality {index} ISTAT code is invalid"
            )
        codes.append(code)
    codes = sorted(codes)
    if len(set(codes)) != municipality_count:
        raise NationalForecastPointsError("national catalog ISTAT codes are duplicated")
    codes_sha256 = sha256_hex(canonical_json_bytes(codes))
    if catalog.get("municipality_codes_sha256") != codes_sha256:
        raise NationalForecastPointsError(
            "national catalog municipality-code SHA-256 mismatch"
        )
    return {
        "catalog_sha256": catalog_sha256,
        "municipality_codes_sha256": codes_sha256,
        "municipality_count": municipality_count,
        "codes": codes,
    }


def _boundary_sha256_from_catalog(catalog: Mapping[str, Any]) -> str | None:
    sources = catalog.get("sources")
    if not isinstance(sources, Mapping):
        return None
    boundaries = sources.get("boundaries")
    if not isinstance(boundaries, Mapping):
        return None
    value = boundaries.get("sha256")
    return value if isinstance(value, str) and _SHA256_RE.fullmatch(value) else None


def _quality_counts(points: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    observed = Counter(point["quality"] for point in points)
    return {quality: observed[quality] for quality in sorted(ALL_POINT_QUALITIES)}


def _validate_status_qualities(status: str, points: Sequence[Mapping[str, Any]]) -> None:
    qualities = {point["quality"] for point in points}
    if status == APPROVED_POINTS_STATUS:
        if not qualities <= APPROVED_POINT_QUALITIES:
            raise NationalForecastPointsError(
                "approved artifact contains an experimental point quality"
            )
    elif status == EXPERIMENTAL_POINTS_STATUS:
        if not qualities or not qualities <= EXPERIMENTAL_POINT_QUALITIES:
            raise NationalForecastPointsError(
                "experimental artifact contains a non-experimental point quality"
            )
    else:
        raise NationalForecastPointsError("forecast-point artifact status is invalid")


def build_forecast_points_artifact(
    *,
    catalog: Mapping[str, Any],
    points: Iterable[Mapping[str, Any]],
    status: str,
    boundary_sha256: str,
    source_manifest_sha256: str,
    resolution_policy_sha256: str,
) -> dict[str, Any]:
    """Build and validate one immutable v2 forecast-point artifact."""

    catalog_reference = _catalog_reference(catalog)
    boundary_sha256 = _sha256(boundary_sha256, "boundary source SHA-256")
    catalog_boundary_sha256 = _boundary_sha256_from_catalog(catalog)
    if (
        catalog_boundary_sha256 is not None
        and boundary_sha256 != catalog_boundary_sha256
    ):
        raise NationalForecastPointsError(
            "boundary source differs from the bound national catalog"
        )
    source_manifest_sha256 = _sha256(
        source_manifest_sha256, "source manifest SHA-256"
    )
    resolution_policy_sha256 = _sha256(
        resolution_policy_sha256, "resolution policy SHA-256"
    )
    normalized = [
        _normalize_point(point, index=index) for index, point in enumerate(points)
    ]
    normalized.sort(key=lambda point: point["istat_code"])
    _validate_status_qualities(status, normalized)
    codes = [point["istat_code"] for point in normalized]
    if (
        codes != catalog_reference["codes"]
        or len(normalized) != catalog_reference["municipality_count"]
    ):
        raise NationalForecastPointsError(
            "forecast points do not exactly cover the bound national catalog"
        )

    document: dict[str, Any] = {
        "boundary_sha256": boundary_sha256,
        "catalog_sha256": catalog_reference["catalog_sha256"],
        "coordinate_reference_system": dict(
            OUTPUT_COORDINATE_REFERENCE_SYSTEM
        ),
        "kind": FORECAST_POINTS_KIND,
        "municipality_codes_sha256": catalog_reference[
            "municipality_codes_sha256"
        ],
        "point_count": len(normalized),
        "points": normalized,
        "points_sha256": sha256_hex(canonical_json_bytes(normalized)),
        "quality_counts": _quality_counts(normalized),
        "resolution_policy_sha256": resolution_policy_sha256,
        "schema_version": FORECAST_POINTS_SCHEMA_VERSION,
        "source_manifest_sha256": source_manifest_sha256,
        "status": status,
    }
    document["artifact_sha256"] = sha256_hex(canonical_json_bytes(document))
    validate_forecast_points_artifact(
        document,
        catalog=catalog,
        allow_experimental=status == EXPERIMENTAL_POINTS_STATUS,
    )
    return document


def build_approved_forecast_points_artifact(
    *,
    catalog: Mapping[str, Any],
    points: Iterable[Mapping[str, Any]],
    boundary_sha256: str,
    source_manifest_sha256: str,
    resolution_policy_sha256: str,
) -> dict[str, Any]:
    """Build a complete artifact that is eligible for ICON mapping."""

    return build_forecast_points_artifact(
        catalog=catalog,
        points=points,
        status=APPROVED_POINTS_STATUS,
        boundary_sha256=boundary_sha256,
        source_manifest_sha256=source_manifest_sha256,
        resolution_policy_sha256=resolution_policy_sha256,
    )


def build_experimental_proxy_artifact(
    catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Build explicitly non-production points from catalog interior proxies."""

    catalog_reference = _catalog_reference(catalog)
    sources = catalog.get("sources")
    boundaries = sources.get("boundaries") if isinstance(sources, Mapping) else None
    if not isinstance(boundaries, Mapping):
        raise NationalForecastPointsError(
            "catalog boundary provenance is required for experimental proxies"
        )
    boundary_sha256 = _sha256(
        boundaries.get("sha256"), "catalog boundary SHA-256"
    )
    dataset = _strict_text(
        boundaries.get("dataset"), "catalog boundary dataset"
    )
    reference_date = _reference_date(
        boundaries.get("reference_date"), "catalog boundary reference date"
    )
    url = _https_url(boundaries.get("url"), "catalog boundary URL")

    points: list[dict[str, Any]] = []
    for municipality in catalog["municipalities"]:
        code = municipality["istat_code"]
        proxy = municipality.get("representative_point")
        if not isinstance(proxy, Mapping):
            raise NationalForecastPointsError(
                f"municipality {code} has no representative-point proxy"
            )
        if proxy.get("method") != METHOD_BY_QUALITY[
            QUALITY_EXPERIMENTAL_BOUNDARY_PROXY
        ]:
            raise NationalForecastPointsError(
                f"municipality {code} representative-point method is incompatible"
            )
        points.append(
            {
                "istat_code": code,
                "latitude": proxy.get("latitude"),
                "longitude": proxy.get("longitude"),
                "method": METHOD_BY_QUALITY[
                    QUALITY_EXPERIMENTAL_BOUNDARY_PROXY
                ],
                "quality": QUALITY_EXPERIMENTAL_BOUNDARY_PROXY,
                "source": {
                    "authority": "Istituto nazionale di statistica (Istat)",
                    "catalog_sha256": catalog_reference["catalog_sha256"],
                    "current_istat_code": code,
                    "dataset": dataset,
                    "dataset_sha256": boundary_sha256,
                    "reference_date": reference_date,
                    "source_crs": "EPSG:4326",
                    "source_field": "representative_point",
                    "url": url,
                },
            }
        )

    source_manifest = {
        "catalog_sha256": catalog_reference["catalog_sha256"],
        "source": dict(boundaries),
    }
    policy = {
        "id": "experimental_catalog_boundary_proxy_v1",
        "not_for_production": True,
    }
    return build_forecast_points_artifact(
        catalog=catalog,
        points=points,
        status=EXPERIMENTAL_POINTS_STATUS,
        boundary_sha256=boundary_sha256,
        source_manifest_sha256=sha256_hex(canonical_json_bytes(source_manifest)),
        resolution_policy_sha256=sha256_hex(canonical_json_bytes(policy)),
    )


def validate_forecast_points_artifact(
    document: Mapping[str, Any],
    *,
    catalog: Mapping[str, Any] | None = None,
    allow_experimental: bool = False,
) -> None:
    """Validate shape, semantics, hashes, ordering and optional catalog binding."""

    if not isinstance(document, Mapping):
        raise NationalForecastPointsError("forecast-point artifact must be an object")
    _require_exact_keys(document, _TOP_LEVEL_KEYS, "forecast-point artifact")
    if (
        document.get("kind") != FORECAST_POINTS_KIND
        or document.get("schema_version") != FORECAST_POINTS_SCHEMA_VERSION
    ):
        raise NationalForecastPointsError("forecast-point artifact identity is invalid")
    status = document.get("status")
    if status == EXPERIMENTAL_POINTS_STATUS and not allow_experimental:
        raise NationalForecastPointsError(
            "experimental forecast points require explicit opt-in"
        )
    if status not in {APPROVED_POINTS_STATUS, EXPERIMENTAL_POINTS_STATUS}:
        raise NationalForecastPointsError("forecast-point artifact status is invalid")
    for field in (
        "artifact_sha256",
        "boundary_sha256",
        "catalog_sha256",
        "municipality_codes_sha256",
        "points_sha256",
        "resolution_policy_sha256",
        "source_manifest_sha256",
    ):
        _sha256(document.get(field), field.replace("_", " "))
    if document.get("coordinate_reference_system") != OUTPUT_COORDINATE_REFERENCE_SYSTEM:
        raise NationalForecastPointsError(
            "forecast-point output coordinate reference system is invalid"
        )
    point_count = document.get("point_count")
    points = document.get("points")
    if (
        isinstance(point_count, bool)
        or not isinstance(point_count, int)
        or point_count < 1
        or not isinstance(points, list)
        or len(points) != point_count
    ):
        raise NationalForecastPointsError("forecast-point count is inconsistent")
    normalized = [
        _normalize_point(point, index=index) for index, point in enumerate(points)
    ]
    if normalized != points:
        raise NationalForecastPointsError("forecast points are not canonical")
    codes = [point["istat_code"] for point in normalized]
    if codes != sorted(set(codes)):
        raise NationalForecastPointsError(
            "forecast points must be uniquely sorted by ISTAT code"
        )
    observed_codes_sha256 = sha256_hex(canonical_json_bytes(codes))
    if document["municipality_codes_sha256"] != observed_codes_sha256:
        raise NationalForecastPointsError("municipality-code SHA-256 mismatch")
    _validate_status_qualities(status, normalized)
    if document.get("quality_counts") != _quality_counts(normalized):
        raise NationalForecastPointsError("forecast-point quality counts are invalid")
    if document["points_sha256"] != sha256_hex(canonical_json_bytes(normalized)):
        raise NationalForecastPointsError("forecast points SHA-256 mismatch")

    if catalog is not None:
        reference = _catalog_reference(catalog)
        if (
            document["catalog_sha256"] != reference["catalog_sha256"]
            or document["municipality_codes_sha256"]
            != reference["municipality_codes_sha256"]
            or point_count != reference["municipality_count"]
            or codes != reference["codes"]
        ):
            raise NationalForecastPointsError(
                "forecast-point artifact targets another national catalog"
            )
        catalog_boundary_sha256 = _boundary_sha256_from_catalog(catalog)
        if (
            catalog_boundary_sha256 is not None
            and document["boundary_sha256"] != catalog_boundary_sha256
        ):
            raise NationalForecastPointsError(
                "forecast-point boundary source differs from the national catalog"
            )

    content = dict(document)
    expected_artifact_sha256 = content.pop("artifact_sha256")
    if sha256_hex(canonical_json_bytes(content)) != expected_artifact_sha256:
        raise NationalForecastPointsError("forecast-point artifact SHA-256 mismatch")


def artifact_json_bytes(
    document: Mapping[str, Any],
    *,
    catalog: Mapping[str, Any] | None = None,
    allow_experimental: bool = False,
) -> bytes:
    """Validate and encode a complete artifact in canonical form."""

    validate_forecast_points_artifact(
        document, catalog=catalog, allow_experimental=allow_experimental
    )
    return canonical_json_bytes(document)


def load_forecast_points_artifact(
    path: str | Path,
    *,
    catalog: Mapping[str, Any] | None = None,
    allow_experimental: bool = False,
) -> dict[str, Any]:
    """Read one bounded, canonical and self-verifying artifact."""

    source = Path(path)
    with source.open("rb") as stream:
        raw = stream.read(_MAX_ARTIFACT_BYTES + 1)
    if len(raw) > _MAX_ARTIFACT_BYTES:
        raise NationalForecastPointsError("forecast-point artifact exceeds size limit")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NationalForecastPointsError(
            "forecast-point artifact JSON is unreadable"
        ) from error
    if not isinstance(document, dict) or canonical_json_bytes(document) != raw:
        raise NationalForecastPointsError(
            "forecast-point artifact is not canonical JSON"
        )
    validate_forecast_points_artifact(
        document, catalog=catalog, allow_experimental=allow_experimental
    )
    return document


def write_forecast_points_create_only(
    path: str | Path,
    document: Mapping[str, Any],
    *,
    catalog: Mapping[str, Any] | None = None,
    allow_experimental: bool = False,
) -> None:
    """Validate and atomically create a new artifact without overwriting."""

    payload = artifact_json_bytes(
        document, catalog=catalog, allow_experimental=allow_experimental
    )
    output = Path(path)
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        created = True
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise NationalForecastPointsError(
            f"output already exists (create-only): {output}"
        ) from error
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            try:
                output.unlink()
            except OSError:
                pass
        raise
