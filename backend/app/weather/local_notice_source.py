"""Verified ICON 2I adapter for conservative local weather notices."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests

from app.services.fvg_geography import FvgLocality
from app.services.location import LocationCatalog, Municipality
from app.services.national_municipalities import (
    NATIONAL_MUNICIPALITY_CATALOG_SHA256,
    NATIONAL_MUNICIPALITY_CATALOG_VERSION,
    NATIONAL_MUNICIPALITY_CODES_SHA256,
    NATIONAL_MUNICIPALITY_COUNT,
    NationalMunicipality,
)
from app.weather.local_notice_shadow import (
    EXPECTED_HOURLY_UNITS,
    FVG_TIMEZONE,
    REQUIRED_HOURLY_FIELDS,
    SOURCE_ID,
    canonical_weather_request,
)


ICON_LOCAL_NOTICE_BASE_URL_ENV = "LOCAL_NOTICE_ICON_BASE_URL"
ICON_LOCAL_NOTICE_BASE_URL = (
    "https://meteofriul-weather-49007668366.europe-west1.run.app/"
    "weather/v1/icon2i/"
)
LOCAL_NOTICE_FORECAST_HOURS = 8
MAX_LOCAL_NOTICE_FORECAST_HOURS = 48
DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS = 30.0
MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS = 45.0
LOCAL_NOTICE_SOURCE_REQUEST_ATTEMPTS = 2
LOCAL_NOTICE_USER_AGENT = "MeteoFriul/3.0 (+https://meteofriul.it)"
NATIONAL_ICON_LOCAL_NOTICE_BASE_URL_ENV = "LOCAL_NOTICE_NATIONAL_ICON_BASE_URL"
NATIONAL_ICON_LOCAL_NOTICE_BASE_URL = (
    "https://meteofriul-national-weather-49007668366.europe-west1.run.app/"
    "weather/v2/icon2i/"
)
NATIONAL_ICON_CONTRACT = "weather/v2/icon2i"
NATIONAL_ICON_RESOLUTION_KIND = (
    "meteofriul.weather.icon.national.local_pilot_resolution"
)
NATIONAL_ICON_BLOCK_KIND = "meteofriul.weather.icon.national.block"
NATIONAL_ICON_ACTIVE_STATUS = "experimental_local_pilot_only"
LOCAL_NOTICE_HOURLY_FIELDS = tuple(
    field for field in REQUIRED_HOURLY_FIELDS if field != "time"
)
_MANIFEST_PATH = re.compile(r"^runs/\d{8}T\d{6}Z/manifest\.json$")
_MUNICIPALITY_PATH = re.compile(
    r"^runs/(?P<run>\d{8}T\d{6}Z)/municipalities/(?P<istat>\d{6})\.json$"
)
_RUN_ID = re.compile(r"^\d{8}T\d{6}Z$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NATIONAL_BLOCK_PATH = re.compile(
    r"^runs/(?P<run>\d{8}T\d{6}Z)/blocks/(?P<block>[a-z0-9-]+)\.json$"
)
_NATIONAL_REQUIRED_VARIABLES = {
    "t_2m_k": "K",
    "u_10m_m_s": "m/s",
    "v_10m_m_s": "m/s",
    "total_precipitation_mm": "mm",
    "weather_code": "wmo_code",
    "wind_gust_max_m_s": "m/s",
    "convective_rain_mm": "mm",
    "grid_scale_rain_mm": "mm",
    "convective_snow_mm": "mm",
    "grid_scale_snow_mm": "mm",
    "grid_scale_graupel_mm": "mm",
}


class LocalNoticeSourceUnavailable(RuntimeError):
    """The ICON source did not return a usable verified-contract document."""

    def __init__(self, code: str) -> None:
        self.code = str(code or "source_unavailable")[:80]
        super().__init__(self.code)


def _bounded_source_timeout(timeout_seconds: float) -> float:
    return max(
        1.0,
        min(float(timeout_seconds), MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS),
    )


def _request_with_timeout_retry(
    session: requests.Session | Any,
    url: str,
    *,
    timeout_seconds: float,
    params: dict[str, str] | None = None,
) -> Any:
    """Retry one idempotent ICON GET after a timeout, then fail closed."""

    request_options: dict[str, Any] = {
        "headers": {"User-Agent": LOCAL_NOTICE_USER_AGENT},
        "timeout": timeout_seconds,
    }
    if params is not None:
        request_options["params"] = params

    for attempt in range(LOCAL_NOTICE_SOURCE_REQUEST_ATTEMPTS):
        try:
            response = session.get(url, **request_options)
            response.raise_for_status()
            return response
        except requests.Timeout as error:
            # The regional service can need one Cloud Run cold start. Retrying
            # immediately reuses the startup already in progress without
            # weakening validation or accepting stale/partial payloads.
            if attempt + 1 == LOCAL_NOTICE_SOURCE_REQUEST_ATTEMPTS:
                raise LocalNoticeSourceUnavailable("source_timeout") from error
        except requests.RequestException as error:
            raise LocalNoticeSourceUnavailable("source_request_failed") from error

    raise LocalNoticeSourceUnavailable("source_timeout")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _nonnegative(value: Any, *, default: float = 0.0) -> float:
    numeric = _number(value)
    if numeric is None:
        return default
    if numeric < 0:
        raise LocalNoticeSourceUnavailable("source_invalid_hourly_value")
    return numeric


def _weather_code(*, rain_mm: float, snow_cm: float, native_code: Any) -> int:
    # Preserve explicit hazardous ICON/WMO semantics before deriving a
    # conservative precipitation class from amounts.  Replacing 95/96 or the
    # freezing codes with generic rain would silently disable those notices.
    if native_code in {56, 57, 66, 67, 73, 75, 86, 95, 96, 99}:
        return int(native_code)
    if snow_cm >= 1.0:
        return 73
    # ICON interpolation can leave floating-point residues around 1e-16.
    # Treat only measurable amounts as precipitation; otherwise a warm,
    # dry hour could be mislabeled as snow or rain in user-facing copy.
    if snow_cm > 0.1:
        return 71
    if rain_mm >= 7.5:
        return 65
    if rain_mm >= 2.5:
        return 63
    if rain_mm > 0.1:
        return 61
    return int(native_code) if native_code in {0, 1, 2, 3} else 3


class IconLocalNoticeSource:
    """Read the immutable ICON latest/manifest/municipality contract."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout_seconds: float = DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        base_url: str | None = None,
        forecast_hours: int = LOCAL_NOTICE_FORECAST_HOURS,
    ) -> None:
        self._session = session or requests.Session()
        self._timeout_seconds = _bounded_source_timeout(timeout_seconds)
        self._now = now
        configured = base_url or os.getenv(
            ICON_LOCAL_NOTICE_BASE_URL_ENV,
            ICON_LOCAL_NOTICE_BASE_URL,
        )
        self._base_url = configured.rstrip("/") + "/"
        if not self._base_url.startswith("https://"):
            raise ValueError("local_notice_icon_base_url_invalid")
        self._forecast_hours = max(
            3,
            min(int(forecast_hours), MAX_LOCAL_NOTICE_FORECAST_HOURS),
        )
        # One Cloud Run Job execution can evaluate several municipalities. The
        # immutable latest pointer and manifest are shared by all of them, so
        # read and validate that index only once instead of paying two remote
        # round trips for every delivery group.
        self._run_index: tuple[str, dict[str, Any]] | None = None
        self._run_index_error_code: str | None = None

    def _get_json(self, path: str) -> dict[str, Any]:
        response = _request_with_timeout_retry(
            self._session,
            urljoin(self._base_url, path),
            timeout_seconds=self._timeout_seconds,
        )
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise LocalNoticeSourceUnavailable("source_invalid_json") from error
        if not isinstance(payload, dict):
            raise LocalNoticeSourceUnavailable("source_invalid_payload")
        return payload

    def _get_run_index(self) -> tuple[str, dict[str, Any]]:
        if self._run_index is not None:
            return self._run_index
        if self._run_index_error_code is not None:
            raise LocalNoticeSourceUnavailable(self._run_index_error_code)

        try:
            latest = self._get_json("latest.json")
            latest_ref = latest.get("latest")
            manifest_path = (
                latest_ref.get("manifest_path")
                if isinstance(latest_ref, dict)
                else None
            )
            source_run_id = (
                latest_ref.get("source_run_id")
                if isinstance(latest_ref, dict)
                else None
            )
            if (
                latest.get("provider") != SOURCE_ID
                or not isinstance(manifest_path, str)
                or not _MANIFEST_PATH.fullmatch(manifest_path)
                or not isinstance(source_run_id, str)
            ):
                raise LocalNoticeSourceUnavailable("source_invalid_latest")

            manifest = self._get_json(manifest_path)
            if (
                manifest.get("provider") != SOURCE_ID
                or manifest.get("source_run_id") != source_run_id
            ):
                raise LocalNoticeSourceUnavailable("source_invalid_manifest")
            objects = manifest.get("objects")
            if not isinstance(objects, dict):
                raise LocalNoticeSourceUnavailable("source_invalid_manifest")
        except LocalNoticeSourceUnavailable as error:
            # latest.json and its manifest are shared by every FVG group. Once
            # both bounded attempts fail (or the shared contract is invalid),
            # do not multiply the same outage by the number of subscribers.
            self._run_index_error_code = error.code
            raise
        self._run_index = (source_run_id, objects)
        return self._run_index

    def _adapt_hourly(
        self,
        payload: dict[str, Any],
        *,
        fetched_at: datetime,
    ) -> dict[str, list[Any]]:
        rows = payload.get("hourly")
        if not isinstance(rows, list):
            raise LocalNoticeSourceUnavailable("source_invalid_hourly")

        adapted: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise LocalNoticeSourceUnavailable("source_invalid_hourly")
            try:
                valid_at = datetime.fromisoformat(
                    str(row.get("valid_at", "")).replace("Z", "+00:00")
                ).astimezone(timezone.utc)
            except (TypeError, ValueError):
                raise LocalNoticeSourceUnavailable("source_invalid_hourly_time") from None
            if valid_at < fetched_at:
                continue

            temperature = _number(row.get("temperature_c"))
            apparent = _number(row.get("apparent_temperature_c"))
            gust_m_s = _number(row.get("wind_gust_max_m_s"))
            if temperature is None or apparent is None or gust_m_s is None or gust_m_s < 0:
                continue
            rain = _nonnegative(row.get("liquid_rain_mm"))
            snow_cm = _nonnegative(row.get("snow_water_equivalent_mm"))
            precipitation = _nonnegative(
                row.get("precipitation_mm"),
                default=rain + snow_cm,
            )
            condition = row.get("condition")
            native_code = condition.get("native_code") if isinstance(condition, dict) else None
            adapted.append(
                {
                    "time": valid_at.astimezone(ZoneInfo(FVG_TIMEZONE)).isoformat(
                        timespec="minutes"
                    ),
                    "temperature_2m": temperature,
                    "apparent_temperature": apparent,
                    # ICON 2I is deterministic. This binary compatibility field
                    # means predicted/not predicted; it is not an ensemble POP.
                    "precipitation_probability": 100.0 if precipitation > 0 else 0.0,
                    "precipitation": precipitation,
                    "rain": rain,
                    "showers": 0.0,
                    "snowfall": snow_cm,
                    "weather_code": _weather_code(
                        rain_mm=rain,
                        snow_cm=snow_cm,
                        native_code=native_code,
                    ),
                    "wind_gusts_10m": gust_m_s * 3.6,
                }
            )
            if len(adapted) >= self._forecast_hours:
                break
        if len(adapted) < 3:
            raise LocalNoticeSourceUnavailable("source_insufficient_future_hours")
        return {
            field: [row[field] for row in adapted]
            for field in REQUIRED_HOURLY_FIELDS
        }

    def fetch(
        self,
        municipality: Municipality,
        locality: FvgLocality | None = None,
    ) -> dict[str, Any]:
        requested_location = canonical_weather_request(
            municipality.istat_code,
            locality=locality,
        )
        fetched_at = self._now()
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        fetched_at = fetched_at.astimezone(timezone.utc)

        source_run_id, objects = self._get_run_index()
        descriptor = objects.get(municipality.istat_code)
        path = descriptor.get("path") if isinstance(descriptor, dict) else None
        match = _MUNICIPALITY_PATH.fullmatch(path or "")
        if (
            match is None
            or match.group("run") != source_run_id
            or match.group("istat") != municipality.istat_code
        ):
            raise LocalNoticeSourceUnavailable("source_invalid_manifest")

        payload = self._get_json(path)
        payload_municipality = payload.get("municipality")
        if (
            payload.get("provider") != SOURCE_ID
            or payload.get("source_run_id") != source_run_id
            or payload.get("timezone") != FVG_TIMEZONE
            or not isinstance(payload_municipality, dict)
            or payload_municipality.get("istat_code") != municipality.istat_code
        ):
            raise LocalNoticeSourceUnavailable("source_invalid_municipality")

        model_point = payload_municipality.get("model_point")
        return {
            "source": SOURCE_ID,
            "fetched_at": fetched_at.isoformat(timespec="seconds"),
            "timezone": FVG_TIMEZONE,
            "utc_offset_seconds": int(
                fetched_at.astimezone(ZoneInfo(FVG_TIMEZONE)).utcoffset().total_seconds()
            ),
            "hourly_units": dict(EXPECTED_HOURLY_UNITS),
            "hourly": self._adapt_hourly(payload, fetched_at=fetched_at),
            "requested_location": requested_location,
            "model_location": model_point if isinstance(model_point, dict) else {},
            "source_run_id": source_run_id,
            "precipitation_probability_basis": "icon2i_deterministic_binary",
        }


def _national_interval(series: list[Any], index: int) -> float | None:
    """Convert one ICON accumulation into the corresponding hourly interval."""

    if index <= 0:
        return None
    current = _nonnegative(series[index])
    previous = _nonnegative(series[index - 1])
    delta = current - previous
    return max(0.0, delta) if delta >= -0.001 else current


class NationalIconLocalNoticeSource:
    """Read and verify the immutable nationwide ICON v2 block contract."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout_seconds: float = DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        base_url: str | None = None,
        forecast_hours: int = LOCAL_NOTICE_FORECAST_HOURS,
    ) -> None:
        self._session = session or requests.Session()
        self._timeout_seconds = _bounded_source_timeout(timeout_seconds)
        self._now = now
        configured = base_url or os.getenv(
            NATIONAL_ICON_LOCAL_NOTICE_BASE_URL_ENV,
            NATIONAL_ICON_LOCAL_NOTICE_BASE_URL,
        )
        self._base_url = configured.rstrip("/") + "/"
        if not self._base_url.startswith("https://"):
            raise ValueError("local_notice_national_icon_base_url_invalid")
        self._forecast_hours = max(
            3,
            min(int(forecast_hours), MAX_LOCAL_NOTICE_FORECAST_HOURS),
        )
        self._blocks: dict[tuple[str, str], dict[str, Any]] = {}
        self._availability_error_code: str | None = None

    def _request(self, path: str, *, params: dict[str, str] | None = None) -> Any:
        return _request_with_timeout_retry(
            self._session,
            urljoin(self._base_url, path),
            params=params,
            timeout_seconds=self._timeout_seconds,
        )

    @staticmethod
    def _response_bytes(response: Any) -> bytes:
        raw = getattr(response, "content", None)
        if isinstance(raw, bytes):
            return raw
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text.encode("utf-8")
        raise LocalNoticeSourceUnavailable("source_invalid_payload")

    @classmethod
    def _response_json(cls, response: Any) -> dict[str, Any]:
        try:
            payload = json.loads(cls._response_bytes(response).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LocalNoticeSourceUnavailable("source_invalid_json") from error
        if not isinstance(payload, dict):
            raise LocalNoticeSourceUnavailable("source_invalid_payload")
        return payload

    @staticmethod
    def _validate_resolution(
        payload: dict[str, Any],
        municipality: NationalMunicipality | Municipality,
    ) -> dict[str, Any]:
        resolved = payload.get("municipality")
        source_run_id = payload.get("source_run_id")
        block_path = payload.get("block_path")
        block_id = payload.get("block_id")
        block_match = _NATIONAL_BLOCK_PATH.fullmatch(str(block_path or ""))
        block_size = payload.get("block_json_bytes")
        if (
            payload.get("schema_version") != 1
            or payload.get("kind") != NATIONAL_ICON_RESOLUTION_KIND
            or payload.get("contract") != NATIONAL_ICON_CONTRACT
            or payload.get("status") != NATIONAL_ICON_ACTIVE_STATUS
            or not isinstance(source_run_id, str)
            or not _RUN_ID.fullmatch(source_run_id)
            or block_match is None
            or block_match.group("run") != source_run_id
            or block_match.group("block") != block_id
            or isinstance(block_size, bool)
            or not isinstance(block_size, int)
            or block_size < 1
            or not _SHA256.fullmatch(str(payload.get("block_sha256") or ""))
            or not isinstance(payload.get("cell_id"), str)
            or not isinstance(resolved, dict)
            or resolved.get("istat_code") != municipality.istat_code
            or resolved.get("name") != municipality.name
            or resolved.get("province") != municipality.province
        ):
            raise LocalNoticeSourceUnavailable("source_invalid_resolution")
        return payload

    @staticmethod
    def _validate_block(
        block: dict[str, Any],
        resolution: dict[str, Any],
    ) -> tuple[list[datetime], dict[str, Any]]:
        times = block.get("time_axis")
        municipality_cells = block.get("municipality_cells")
        cells = block.get("cells")
        metadata = block.get("metadata")
        catalog = metadata.get("catalog") if isinstance(metadata, dict) else None
        if (
            block.get("schema_version") != 2
            or block.get("kind") != NATIONAL_ICON_BLOCK_KIND
            or block.get("contract") != NATIONAL_ICON_CONTRACT
            or block.get("source_run_id") != resolution["source_run_id"]
            or block.get("block_id") != resolution["block_id"]
            or not isinstance(times, list)
            or len(times) < 13
            or not isinstance(municipality_cells, dict)
            or municipality_cells.get(resolution["municipality"]["istat_code"])
            != resolution["cell_id"]
            or not isinstance(cells, list)
            or not isinstance(catalog, dict)
            or catalog.get("municipality_count") != NATIONAL_MUNICIPALITY_COUNT
            or catalog.get("version") != NATIONAL_MUNICIPALITY_CATALOG_VERSION
            or catalog.get("sha256") != NATIONAL_MUNICIPALITY_CATALOG_SHA256
            or catalog.get("municipality_codes_sha256")
            != NATIONAL_MUNICIPALITY_CODES_SHA256
        ):
            raise LocalNoticeSourceUnavailable("source_invalid_block")

        parsed_times: list[datetime] = []
        for value in times:
            try:
                parsed = datetime.fromisoformat(
                    str(value).replace("Z", "+00:00")
                ).astimezone(timezone.utc)
            except (TypeError, ValueError):
                raise LocalNoticeSourceUnavailable("source_invalid_block_time") from None
            if parsed_times and parsed - parsed_times[-1] != timedelta(hours=1):
                raise LocalNoticeSourceUnavailable("source_invalid_block_time")
            parsed_times.append(parsed)

        variables = metadata.get("variables")
        declared_units = {
            str(item.get("id") or ""): str(item.get("unit") or "")
            for item in variables
            if isinstance(item, dict)
        } if isinstance(variables, list) else {}
        if any(
            declared_units.get(variable_id) != unit
            for variable_id, unit in _NATIONAL_REQUIRED_VARIABLES.items()
        ):
            raise LocalNoticeSourceUnavailable("source_invalid_block_variables")

        cell = next(
            (
                item
                for item in cells
                if isinstance(item, dict)
                and item.get("cell_id") == resolution["cell_id"]
            ),
            None,
        )
        values = cell.get("values") if isinstance(cell, dict) else None
        if not isinstance(values, dict):
            raise LocalNoticeSourceUnavailable("source_invalid_block_cell")
        for variable_id in _NATIONAL_REQUIRED_VARIABLES:
            series = values.get(variable_id)
            if (
                not isinstance(series, list)
                or len(series) != len(parsed_times)
                or any(_number(value) is None for value in series)
            ):
                raise LocalNoticeSourceUnavailable("source_invalid_block_series")
        if (
            _number(cell.get("latitude")) is None
            or _number(cell.get("longitude")) is None
        ):
            raise LocalNoticeSourceUnavailable("source_invalid_block_cell")
        return parsed_times, cell

    def _adapt_national_hourly(
        self,
        times: list[datetime],
        cell: dict[str, Any],
        *,
        fetched_at: datetime,
    ) -> dict[str, list[Any]]:
        values = cell["values"]
        adapted: list[dict[str, Any]] = []
        for index, valid_at in enumerate(times):
            if valid_at < fetched_at or index == 0:
                continue
            temperature_k = _number(values["t_2m_k"][index])
            gust_m_s = _number(values["wind_gust_max_m_s"][index])
            native_code = _number(values["weather_code"][index])
            if (
                temperature_k is None
                or gust_m_s is None
                or gust_m_s < 0
                or native_code is None
            ):
                raise LocalNoticeSourceUnavailable("source_invalid_block_series")
            rain_parts = [
                _national_interval(values[variable_id], index)
                for variable_id in ("convective_rain_mm", "grid_scale_rain_mm")
            ]
            snow_parts = [
                _national_interval(values[variable_id], index)
                for variable_id in (
                    "convective_snow_mm",
                    "grid_scale_snow_mm",
                    "grid_scale_graupel_mm",
                )
            ]
            precipitation = _national_interval(
                values["total_precipitation_mm"], index
            )
            if precipitation is None or any(
                value is None for value in (*rain_parts, *snow_parts)
            ):
                continue
            rain = sum(float(value) for value in rain_parts)
            snow = sum(float(value) for value in snow_parts)
            temperature = temperature_k - 273.15
            adapted.append(
                {
                    "time": valid_at.astimezone(ZoneInfo(FVG_TIMEZONE)).isoformat(
                        timespec="minutes"
                    ),
                    "temperature_2m": temperature,
                    "apparent_temperature": temperature,
                    "precipitation_probability": (
                        100.0 if precipitation > 0 else 0.0
                    ),
                    "precipitation": precipitation,
                    "rain": rain,
                    "showers": 0.0,
                    "snowfall": snow,
                    "weather_code": _weather_code(
                        rain_mm=rain,
                        snow_cm=snow,
                        native_code=int(native_code),
                    ),
                    "wind_gusts_10m": gust_m_s * 3.6,
                }
            )
            if len(adapted) >= self._forecast_hours:
                break
        if len(adapted) < 3:
            raise LocalNoticeSourceUnavailable("source_insufficient_future_hours")
        return {
            field: [row[field] for row in adapted]
            for field in REQUIRED_HOURLY_FIELDS
        }

    def fetch(
        self,
        municipality: NationalMunicipality | Municipality,
        locality: FvgLocality | None = None,
    ) -> dict[str, Any]:
        if locality is not None:
            raise LocalNoticeSourceUnavailable("source_national_locality_unsupported")
        if municipality.latitude is None or municipality.longitude is None:
            raise LocalNoticeSourceUnavailable("source_invalid_municipality")
        if self._availability_error_code is not None:
            raise LocalNoticeSourceUnavailable(self._availability_error_code)

        try:
            response = self._request(
                "resolve.json",
                params={
                    "city": municipality.name,
                    "province": municipality.province,
                },
            )
        except LocalNoticeSourceUnavailable as error:
            if error.code in {"source_timeout", "source_request_failed"}:
                # A failed resolver means the shared national service is not
                # reachable for this job execution. Avoid one full retry budget
                # per subscriber group while keeping contract errors scoped.
                self._availability_error_code = error.code
            raise
        resolution = self._validate_resolution(
            self._response_json(response), municipality
        )
        block_key = (resolution["block_path"], resolution["block_sha256"])
        block = self._blocks.get(block_key)
        if block is None:
            response = self._request(resolution["block_path"])
            raw = self._response_bytes(response)
            if (
                len(raw) != resolution["block_json_bytes"]
                or hashlib.sha256(raw).hexdigest() != resolution["block_sha256"]
            ):
                raise LocalNoticeSourceUnavailable("source_block_integrity_failed")
            block = self._response_json(response)
            self._blocks[block_key] = block
        times, cell = self._validate_block(block, resolution)

        fetched_at = self._now()
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        fetched_at = fetched_at.astimezone(timezone.utc)
        requested_location = {
            "city": municipality.name,
            "istat_code": municipality.istat_code,
            "locality_id": "",
            "locality_name": "",
            "latitude": municipality.latitude,
            "longitude": municipality.longitude,
        }
        return {
            "source": SOURCE_ID,
            "fetched_at": fetched_at.isoformat(timespec="seconds"),
            "timezone": FVG_TIMEZONE,
            "utc_offset_seconds": int(
                fetched_at.astimezone(ZoneInfo(FVG_TIMEZONE))
                .utcoffset()
                .total_seconds()
            ),
            "hourly_units": dict(EXPECTED_HOURLY_UNITS),
            "hourly": self._adapt_national_hourly(
                times, cell, fetched_at=fetched_at
            ),
            "requested_location": requested_location,
            "model_location": {
                "lat": float(cell["latitude"]),
                "lon": float(cell["longitude"]),
            },
            "source_run_id": resolution["source_run_id"],
            "precipitation_probability_basis": "icon2i_deterministic_binary",
        }


class RoutedIconLocalNoticeSource:
    """Keep the proven FVG v1 source and route other Italian towns to v2."""

    def __init__(
        self,
        *,
        fvg_source: IconLocalNoticeSource | None = None,
        national_source: NationalIconLocalNoticeSource | None = None,
        fvg_catalog: LocationCatalog | None = None,
        timeout_seconds: float = DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS,
        forecast_hours: int = LOCAL_NOTICE_FORECAST_HOURS,
    ) -> None:
        self._fvg_source = fvg_source or IconLocalNoticeSource(
            timeout_seconds=timeout_seconds,
            forecast_hours=forecast_hours,
        )
        self._national_source = national_source or NationalIconLocalNoticeSource(
            timeout_seconds=timeout_seconds,
            forecast_hours=forecast_hours,
        )
        self._fvg_catalog = fvg_catalog or LocationCatalog()

    def fetch(
        self,
        municipality: NationalMunicipality | Municipality,
        locality: FvgLocality | None = None,
    ) -> dict[str, Any]:
        fvg_municipality = self._fvg_catalog.match_istat(municipality.istat_code)
        if fvg_municipality is not None:
            return self._fvg_source.fetch(fvg_municipality, locality)
        return self._national_source.fetch(municipality, locality)


__all__ = [
    "DEFAULT_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS",
    "ICON_LOCAL_NOTICE_BASE_URL",
    "ICON_LOCAL_NOTICE_BASE_URL_ENV",
    "LOCAL_NOTICE_FORECAST_HOURS",
    "LOCAL_NOTICE_SOURCE_REQUEST_ATTEMPTS",
    "MAX_LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS",
    "MAX_LOCAL_NOTICE_FORECAST_HOURS",
    "LOCAL_NOTICE_HOURLY_FIELDS",
    "NATIONAL_ICON_ACTIVE_STATUS",
    "NATIONAL_ICON_LOCAL_NOTICE_BASE_URL",
    "NATIONAL_ICON_LOCAL_NOTICE_BASE_URL_ENV",
    "IconLocalNoticeSource",
    "LocalNoticeSourceUnavailable",
    "NationalIconLocalNoticeSource",
    "RoutedIconLocalNoticeSource",
]
