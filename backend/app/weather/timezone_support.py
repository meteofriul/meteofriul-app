"""Timezone helpers shared by weather pipelines.

Open-Meteo returns local wall-clock timestamps together with an IANA timezone.
Windows development hosts do not always bundle the IANA database, so the
territorial CET/CEST area keeps a standards-based fallback for deterministic
tests and safe operation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


FVG_TIMEZONE = "Europe/Rome"
CENTRAL_EUROPE_TIMEZONES = frozenset(
    {
        "Europe/Berlin",
        "Europe/Ljubljana",
        "Europe/Rome",
        "Europe/Vienna",
    }
)


class CentralEuropeanFallback(tzinfo):
    """Modern EU daylight-saving rules when IANA timezone data is absent."""

    _standard_offset = timedelta(hours=1)
    _daylight_delta = timedelta(hours=1)

    @staticmethod
    def _last_sunday(year: int, month: int) -> datetime:
        if month == 12:
            following_month = datetime(year + 1, 1, 1)
        else:
            following_month = datetime(year, month + 1, 1)
        last_day = following_month - timedelta(days=1)
        return last_day - timedelta(days=(last_day.weekday() + 1) % 7)

    @classmethod
    def _utc_transitions(cls, year: int) -> tuple[datetime, datetime]:
        start = cls._last_sunday(year, 3).replace(hour=1)
        end = cls._last_sunday(year, 10).replace(hour=1)
        return start, end

    @classmethod
    def _local_transitions(cls, year: int) -> tuple[datetime, datetime]:
        start_utc, end_utc = cls._utc_transitions(year)
        return (
            start_utc + cls._standard_offset,
            end_utc + cls._standard_offset + cls._daylight_delta,
        )

    def utcoffset(self, value: datetime | None) -> timedelta:
        return self._standard_offset + self.dst(value)

    def dst(self, value: datetime | None) -> timedelta:
        if value is None:
            return timedelta(0)
        local_value = value.replace(tzinfo=None)
        start, end = self._local_transitions(local_value.year)
        if start <= local_value < start + self._daylight_delta:
            return timedelta(0) if value.fold else self._daylight_delta
        if end - self._daylight_delta <= local_value < end:
            return timedelta(0) if value.fold else self._daylight_delta
        if start + self._daylight_delta <= local_value < end - self._daylight_delta:
            return self._daylight_delta
        return timedelta(0)

    def tzname(self, value: datetime | None) -> str:
        return "CEST" if self.dst(value) else "CET"

    def fromutc(self, value: datetime) -> datetime:
        if value.tzinfo is not self:
            raise ValueError("fromutc requires a datetime using this timezone")
        utc_value = value.replace(tzinfo=None)
        start, end = self._utc_transitions(utc_value.year)
        in_daylight_time = start <= utc_value < end
        offset = self._standard_offset + (
            self._daylight_delta if in_daylight_time else timedelta(0)
        )
        local_value = (utc_value + offset).replace(tzinfo=self)
        if end <= utc_value < end + self._daylight_delta:
            local_value = local_value.replace(fold=1)
        return local_value


def _fixed_offset(utc_offset_seconds) -> tzinfo:
    try:
        offset_seconds = int(utc_offset_seconds)
    except (TypeError, ValueError):
        offset_seconds = 0
    offset_seconds = max(-23 * 60 * 60, min(23 * 60 * 60, offset_seconds))
    return timezone(timedelta(seconds=offset_seconds))


def resolve_weather_timezone(
    timezone_name: str | None,
    utc_offset_seconds=None,
) -> tzinfo:
    """Resolve an Open-Meteo timezone with a deterministic safe fallback."""

    normalized_name = str(timezone_name or "").strip()
    if normalized_name:
        try:
            return ZoneInfo(normalized_name)
        except (ZoneInfoNotFoundError, ValueError):
            if normalized_name in CENTRAL_EUROPE_TIMEZONES:
                return CentralEuropeanFallback()

    if utc_offset_seconds is not None:
        return _fixed_offset(utc_offset_seconds)
    return CentralEuropeanFallback()


def get_fvg_timezone() -> tzinfo:
    return resolve_weather_timezone(FVG_TIMEZONE, 3600)
