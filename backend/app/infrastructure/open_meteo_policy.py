"""Fail-closed compatibility guard for the retired Open-Meteo provider.

ICON/CAMS is the production weather stack. Open-Meteo stays disabled unless a
developer makes an explicit, isolated override; a missing environment variable
must never turn the retired provider back on.
"""

from __future__ import annotations

import ipaddress
import os


LOCAL_WEATHER_PILOT_ENV = "METEOFRIUL_LOCAL_WEATHER_PILOT"
OPEN_METEO_ENABLED_ENV = "METEOFRIUL_OPEN_METEO_ENABLED"
LOCAL_WEATHER_PILOT_HEADER = "X-Meteo-Friul-Local-Weather-Pilot"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


class ProviderPolicyConfigurationError(RuntimeError):
    """A provider switch has a value that cannot be interpreted safely."""


class OpenMeteoDisabled(RuntimeError):
    """An Open-Meteo adapter was invoked while the provider is disabled."""


def _read_boolean_switch(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    normalized = raw_value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ProviderPolicyConfigurationError(f"invalid_boolean_switch:{name}")


def local_weather_pilot_requested() -> bool:
    return _read_boolean_switch(LOCAL_WEATHER_PILOT_ENV, default=False)


def open_meteo_enabled() -> bool:
    return _read_boolean_switch(OPEN_METEO_ENABLED_ENV, default=False)


def local_weather_pilot_ready() -> bool:
    return local_weather_pilot_requested() and not open_meteo_enabled()


def require_open_meteo_enabled(operation: str) -> None:
    if not open_meteo_enabled():
        normalized_operation = str(operation or "request").strip() or "request"
        raise OpenMeteoDisabled(f"open_meteo_disabled:{normalized_operation}")


def is_loopback_hostname(hostname: str | None) -> bool:
    normalized = str(hostname or "").strip().lower().rstrip(".")
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def provider_policy_status() -> dict[str, bool | str | None]:
    """Return a health-safe, non-secret snapshot of the provider switches."""

    try:
        pilot_requested = local_weather_pilot_requested()
        provider_enabled = open_meteo_enabled()
    except ProviderPolicyConfigurationError as error:
        return {
            "valid": False,
            "error": str(error),
            "local_weather_pilot_requested": False,
            "open_meteo_enabled": False,
            "local_weather_pilot_ready": False,
        }

    return {
        "valid": True,
        "error": None,
        "local_weather_pilot_requested": pilot_requested,
        "open_meteo_enabled": provider_enabled,
        "local_weather_pilot_ready": pilot_requested and not provider_enabled,
    }


__all__ = [
    "LOCAL_WEATHER_PILOT_ENV",
    "LOCAL_WEATHER_PILOT_HEADER",
    "OPEN_METEO_ENABLED_ENV",
    "OpenMeteoDisabled",
    "ProviderPolicyConfigurationError",
    "is_loopback_hostname",
    "local_weather_pilot_ready",
    "local_weather_pilot_requested",
    "open_meteo_enabled",
    "provider_policy_status",
    "require_open_meteo_enabled",
]
