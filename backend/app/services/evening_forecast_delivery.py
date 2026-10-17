"""Daily evening preview for the next local calendar day."""

from __future__ import annotations

import math
import os
import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from time import sleep
from typing import Any

from app.infrastructure.firebase import get_firestore_client
from app.push.fcm import FirebaseCloudMessagingSender
from app.repositories.push import PushDeviceRepository, PushRepositoryUnavailable
from app.services.fvg_geography import FvgLocality
from app.services.local_notice_delivery import (
    LocalNoticeDeliveryConfig,
    LocalNoticeDeliveryConfigurationError,
    LocalNoticeDeliveryTarget,
)
from app.services.location import Municipality
from app.services.morning_forecast_delivery import (
    ForecastNotificationContent,
    MorningForecastDeliveryResult,
    MorningForecastDeliveryService,
)
from app.services.notice_municipalities import NoticeMunicipalityCatalog
from app.weather.local_notice_shadow import FVG_ZONE, WIND_GUST_THRESHOLD_KMH
from app.weather.local_notice_source import RoutedIconLocalNoticeSource


EVENING_FORECAST_MODE_ENV = "EVENING_FORECAST_DELIVERY_MODE"
EVENING_FORECAST_REQUIRE_SINGLE_TARGET_ENV = (
    "EVENING_FORECAST_REQUIRE_SINGLE_TARGET"
)
EVENING_FORECAST_TEST_RUN_ID_ENV = "EVENING_FORECAST_TEST_RUN_ID"
EVENING_FORECAST_TEST_PLATFORM_ENV = "EVENING_FORECAST_TEST_PLATFORM"
EVENING_FORECAST_TEST_INSTALLATION_HASH_ENV = (
    "EVENING_FORECAST_TEST_INSTALLATION_HASH"
)
EVENING_FORECAST_KIND = "evening_forecast"
EVENING_FORECAST_HOURS = 36
EVENING_FORECAST_TTL_SECONDS = 3 * 60 * 60
EVENING_FORECAST_MINIMUM_DAY_ROWS = 20
EVENING_FORECAST_MAX_RUN_AGE_SECONDS = 10 * 60 * 60

_PRECIPITATION_CODES = frozenset(
    {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
)
_FREEZING_CODES = frozenset({56, 57, 66, 67})
_SNOW_CODES = frozenset({71, 73, 75, 77, 85, 86})
_STORM_CODES = frozenset({95, 96, 99})


class EveningForecastConfigurationError(RuntimeError):
    """The evening dispatcher is not configured safely."""


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _forecast_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=FVG_ZONE)
    return parsed.astimezone(FVG_ZONE)


def _source_run_is_fresh(snapshot: Mapping[str, Any], *, now: datetime) -> bool:
    try:
        source_run_at = datetime.strptime(
            str(snapshot.get("source_run_id") or ""),
            "%Y%m%dT%H%M%SZ",
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    current = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    age_seconds = (current.astimezone(timezone.utc) - source_run_at).total_seconds()
    return -30 * 60 <= age_seconds <= EVENING_FORECAST_MAX_RUN_AGE_SECONDS


def _period_key(hour: int) -> str:
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def _event_copy(kind: str, period: str, *, language: str) -> str:
    if language == "fur":
        event = {
            "fog": "Niblis",
            "freezing": "Ploie glaçade",
            "rain": "Ploie",
            "snow": "Nêf",
            "storm": "Temporâi",
            "wind": "Aiar fuart",
        }[kind]
        timing = {
            "morning": "di matine",
            "afternoon": "dal dopomisdì",
            "evening": "in serade",
        }[period]
        return f"{event} {timing}. Vierç e cjale."

    event = {
        "fog": "Nebbia",
        "freezing": "Pioggia gelata",
        "rain": "Pioggia",
        "snow": "Neve",
        "storm": "Temporali",
        "wind": "Vento forte",
    }[kind]
    timing = {
        "morning": "in mattinata",
        "afternoon": "dal pomeriggio",
        "evening": "in serata",
    }[period]
    return f"{event} {timing}. Apri e guarda."


def _base_condition_copy(rows: list[dict[str, Any]], *, language: str) -> str:
    daylight = [row for row in rows if 7 <= row["time"].hour < 20] or rows
    codes = [int(row["weather_code"]) for row in daylight]
    clear = sum(code in {0, 1} for code in codes)
    cloudy = sum(code in {2, 3} for code in codes)
    fog = sum(code in {45, 48} for code in codes)

    if fog >= max(3, math.ceil(len(codes) * 0.25)):
        first_fog = next(row for row in daylight if row["weather_code"] in {45, 48})
        return _event_copy(
            "fog",
            _period_key(first_fog["time"].hour),
            language=language,
        )
    if clear >= math.ceil(len(codes) * 0.6):
        if language == "fur":
            return "Zornade di soreli. Vierç e cjale."
        return "Giornata soleggiata. Apri e guarda."
    if cloudy >= math.ceil(len(codes) * 0.6):
        if clear:
            if language == "fur":
                return "Nulât, pussibilis sclaridis. Vierç e cjale."
            return "Nuvoloso, possibili schiarite. Apri e guarda."
        if language == "fur":
            return "Zornade nulade. Vierç e cjale."
        return "Giornata nuvolosa. Apri e guarda."
    if language == "fur":
        return "Timp variabil. Vierç e cjale."
    return "Tempo variabile. Apri e guarda."


def _tomorrow_rows(
    snapshot: Mapping[str, Any],
    *,
    forecast_date: date,
) -> list[dict[str, Any]]:
    hourly = snapshot.get("hourly")
    if not isinstance(hourly, Mapping):
        return []
    required = (
        "time",
        "precipitation",
        "rain",
        "showers",
        "snowfall",
        "weather_code",
        "wind_gusts_10m",
    )
    series = {name: hourly.get(name) for name in required}
    if any(not isinstance(values, list) for values in series.values()):
        return []
    lengths = {len(values) for values in series.values()}
    if len(lengths) != 1 or not lengths:
        return []

    rows: list[dict[str, Any]] = []
    for index, value in enumerate(series["time"]):
        forecast_at = _forecast_time(value)
        precipitation = _finite_number(series["precipitation"][index])
        rain = _finite_number(series["rain"][index])
        showers = _finite_number(series["showers"][index])
        snowfall = _finite_number(series["snowfall"][index])
        weather_code = _finite_number(series["weather_code"][index])
        wind_gust = _finite_number(series["wind_gusts_10m"][index])
        if (
            forecast_at is None
            or forecast_at.date() != forecast_date
            or precipitation is None
            or rain is None
            or showers is None
            or snowfall is None
            or weather_code is None
            or wind_gust is None
            or min(precipitation, rain, showers, snowfall, wind_gust) < 0
            or not weather_code.is_integer()
            or not 0 <= weather_code <= 99
        ):
            continue
        rows.append(
            {
                "time": forecast_at,
                "precipitation": precipitation,
                "rain": rain,
                "showers": showers,
                "snowfall": snowfall,
                "weather_code": int(weather_code),
                "wind_gusts_10m": wind_gust,
            }
        )

    rows.sort(key=lambda row: row["time"])
    if (
        len(rows) < EVENING_FORECAST_MINIMUM_DAY_ROWS
        or rows[0]["time"].hour > 2
        or rows[-1]["time"].hour < 21
    ):
        return []
    return rows


def _headline_body(rows: list[dict[str, Any]], *, language: str) -> str:
    first_storm = next(
        (row for row in rows if row["weather_code"] in _STORM_CODES),
        None,
    )
    if first_storm is not None:
        return _event_copy(
            "storm", _period_key(first_storm["time"].hour), language=language
        )

    first_freezing = next(
        (row for row in rows if row["weather_code"] in _FREEZING_CODES),
        None,
    )
    if first_freezing is not None:
        return _event_copy(
            "freezing",
            _period_key(first_freezing["time"].hour),
            language=language,
        )

    first_snow = next(
        (
            row
            for row in rows
            if row["weather_code"] in _SNOW_CODES or row["snowfall"] > 0.1
        ),
        None,
    )
    if first_snow is not None:
        return _event_copy(
            "snow", _period_key(first_snow["time"].hour), language=language
        )

    peak_wind = max(rows, key=lambda row: row["wind_gusts_10m"])
    if peak_wind["wind_gusts_10m"] >= WIND_GUST_THRESHOLD_KMH:
        return _event_copy(
            "wind", _period_key(peak_wind["time"].hour), language=language
        )

    first_rain = next(
        (
            row
            for row in rows
            if row["weather_code"] in _PRECIPITATION_CODES
            or max(row["precipitation"], row["rain"], row["showers"]) > 0.1
        ),
        None,
    )
    if first_rain is not None:
        return _event_copy(
            "rain", _period_key(first_rain["time"].hour), language=language
        )
    return _base_condition_copy(rows, language=language)


def build_evening_forecast_contents(
    snapshot: Mapping[str, Any],
    municipality: Municipality,
    locality: FvgLocality | None = None,
    *,
    now: datetime,
) -> Mapping[str, ForecastNotificationContent]:
    """Build compact IT/FUR copy for tomorrow from one verified ICON snapshot."""

    if not _source_run_is_fresh(snapshot, now=now):
        return {}
    forecast_date = now.astimezone(FVG_ZONE).date() + timedelta(days=1)
    rows = _tomorrow_rows(snapshot, forecast_date=forecast_date)
    if not rows:
        return {}
    place = locality.name if locality is not None else municipality.name
    return {
        "it": ForecastNotificationContent(
            title=f"Domani a {place}",
            body=_headline_body(rows, language="it"),
        ),
        "fur": ForecastNotificationContent(
            title=f"Doman a {place}",
            body=_headline_body(rows, language="fur"),
        ),
    }


def _read_mode() -> str:
    mode = os.getenv(EVENING_FORECAST_MODE_ENV, "off").strip().lower() or "off"
    if mode not in {"off", "dry_run", "send"}:
        raise EveningForecastConfigurationError("evening_forecast_mode_invalid")
    return mode


def _read_require_single_target() -> bool:
    value = os.getenv(
        EVENING_FORECAST_REQUIRE_SINGLE_TARGET_ENV,
        "true",
    ).strip().lower()
    if value not in {"true", "false"}:
        raise EveningForecastConfigurationError(
            "evening_forecast_single_target_invalid"
        )
    return value == "true"


def _read_test_run_id(*, require_single_target: bool) -> str:
    value = os.getenv(EVENING_FORECAST_TEST_RUN_ID_ENV, "").strip().lower()
    if not value:
        return ""
    if not require_single_target:
        raise EveningForecastConfigurationError(
            "evening_forecast_test_run_requires_single_target"
        )
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", value) is None:
        raise EveningForecastConfigurationError(
            "evening_forecast_test_run_id_invalid"
        )
    return value


def _read_test_platform(*, require_single_target: bool) -> str:
    value = os.getenv(EVENING_FORECAST_TEST_PLATFORM_ENV, "").strip().lower()
    if not value:
        return ""
    if not require_single_target:
        raise EveningForecastConfigurationError(
            "evening_forecast_test_platform_requires_single_target"
        )
    if value not in {"android", "web"}:
        raise EveningForecastConfigurationError(
            "evening_forecast_test_platform_invalid"
        )
    return value


def _read_test_installation_hash(*, require_single_target: bool) -> str:
    value = os.getenv(
        EVENING_FORECAST_TEST_INSTALLATION_HASH_ENV,
        "",
    ).strip().lower()
    if not value:
        return ""
    if not require_single_target:
        raise EveningForecastConfigurationError(
            "evening_forecast_test_installation_hash_requires_single_target"
        )
    if re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise EveningForecastConfigurationError(
            "evening_forecast_test_installation_hash_invalid"
        )
    return value


class EveningForecastDeliveryService(MorningForecastDeliveryService):
    configuration_error_type = EveningForecastConfigurationError
    error_prefix = "evening_forecast"
    forecast_kind = EVENING_FORECAST_KIND
    signature_namespace = "meteofriul-evening-forecast-v1"
    notification_ttl_seconds = EVENING_FORECAST_TTL_SECONDS
    collapse_key = "mf-evening-forecast"
    notification_tag = "mf-evening-forecast"
    invalid_target_is_retirement = True

    def _claim(
        self,
        target: LocalNoticeDeliveryTarget,
        *,
        signature: str,
        now: datetime,
    ) -> Any:
        try:
            return super()._claim(target, signature=signature, now=now)
        except PushRepositoryUnavailable as error:
            # Retry only typed transient storage errors, never permission or
            # validation failures. This happens before any FCM send.
            from google.api_core.exceptions import (
                Aborted,
                DeadlineExceeded,
                ServiceUnavailable,
            )

            cause = error.__cause__
            if not isinstance(cause, (Aborted, DeadlineExceeded, ServiceUnavailable)):
                raise
        sleep(0.2)
        claim = super()._claim(target, signature=signature, now=self._current_time())
        if not claim.claimed and claim.state in {"sending", "delivery_in_progress"}:
            # An earlier commit may have succeeded despite losing its reply.
            # Without ownership proof, neither send again nor report recovery.
            raise PushRepositoryUnavailable("evening_claim_confirmation_uncertain")
        return claim

    def _forecast_date(self, current: datetime) -> date:
        return current.astimezone(FVG_ZONE).date() + timedelta(days=1)

    def _notification_contents(
        self,
        snapshot: Mapping[str, Any],
        municipality: Municipality,
        locality: FvgLocality | None,
        *,
        now: datetime,
    ) -> Mapping[str, ForecastNotificationContent]:
        return build_evening_forecast_contents(
            snapshot,
            municipality,
            locality,
            now=now,
        )


EveningForecastDeliveryResult = MorningForecastDeliveryResult


@lru_cache(maxsize=1)
def get_evening_forecast_delivery_service() -> EveningForecastDeliveryService:
    mode = _read_mode()
    require_single_target = _read_require_single_target()
    try:
        base_config = LocalNoticeDeliveryConfig.from_environment()
    except LocalNoticeDeliveryConfigurationError as error:
        raise EveningForecastConfigurationError(
            "evening_forecast_base_config_invalid"
        ) from error
    if mode != "off" and base_config.mode == "off":
        raise EveningForecastConfigurationError(
            "evening_forecast_base_delivery_mode_required"
        )
    config = replace(base_config, mode=mode)
    return EveningForecastDeliveryService(
        device_repository=PushDeviceRepository(get_firestore_client),
        source=RoutedIconLocalNoticeSource(
            timeout_seconds=config.source_timeout_seconds,
            forecast_hours=EVENING_FORECAST_HOURS,
        ),
        sender=FirebaseCloudMessagingSender(),
        config=config,
        require_single_target=require_single_target,
        test_run_id=_read_test_run_id(
            require_single_target=require_single_target,
        ),
        test_platform=_read_test_platform(
            require_single_target=require_single_target,
        ),
        test_installation_hash=_read_test_installation_hash(
            require_single_target=require_single_target,
        ),
        location_catalog=NoticeMunicipalityCatalog(),
    )


def reset_evening_forecast_delivery_service_for_tests() -> None:
    get_evening_forecast_delivery_service.cache_clear()


__all__ = [
    "EVENING_FORECAST_HOURS",
    "EVENING_FORECAST_KIND",
    "EVENING_FORECAST_MAX_RUN_AGE_SECONDS",
    "EVENING_FORECAST_MODE_ENV",
    "EVENING_FORECAST_REQUIRE_SINGLE_TARGET_ENV",
    "EVENING_FORECAST_TEST_INSTALLATION_HASH_ENV",
    "EVENING_FORECAST_TEST_PLATFORM_ENV",
    "EVENING_FORECAST_TEST_RUN_ID_ENV",
    "EveningForecastConfigurationError",
    "EveningForecastDeliveryResult",
    "EveningForecastDeliveryService",
    "build_evening_forecast_contents",
    "get_evening_forecast_delivery_service",
    "reset_evening_forecast_delivery_service_for_tests",
]
