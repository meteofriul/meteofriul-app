from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.contracts.weather import (
    OfficialAlertsResponse,
    WeatherBootstrapResponse,
    WeatherCurrentResponse,
    WeatherForecastResponse,
    WeatherRadarResponse,
)
from app.services import official_alerts
from app.weather import alerts_engine, current_engine, forecast_engine, radar_engine


class WeatherSourceUnavailable(RuntimeError):
    pass


class WeatherService:
    def __init__(
        self,
        *,
        current_loader: Callable[..., dict | None] = current_engine.get_real_current_weather,
        forecast_loader: Callable[..., dict | None] = forecast_engine.get_real_forecast,
        local_pilot_forecast_loader: Callable[..., dict | None] = (
            forecast_engine.get_osmer_only_forecast
        ),
        alerts_loader: Callable[..., dict] = official_alerts.get_official_alerts_state,
        radar_loader: Callable[..., dict] = radar_engine.get_weather_radar,
    ) -> None:
        self._current_loader = current_loader
        self._forecast_loader = forecast_loader
        self._local_pilot_forecast_loader = local_pilot_forecast_loader
        self._alerts_loader = alerts_loader
        self._radar_loader = radar_loader

    def get_current(
        self,
        *,
        city: str,
        lat: float | None,
        lon: float | None,
        force: bool = False,
    ) -> WeatherCurrentResponse:
        if force:
            current_engine.clear_current_weather_caches()

        try:
            payload = self._current_loader(city, lat, lon)
            if not payload:
                raise WeatherSourceUnavailable("current_weather_unavailable")
            return WeatherCurrentResponse.model_validate(payload)
        except WeatherSourceUnavailable:
            raise
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError) as error:
            raise WeatherSourceUnavailable("current_weather_unavailable") from error

    def get_forecast(
        self,
        *,
        city: str,
        lat: float | None,
        lon: float | None,
        force: bool = False,
    ) -> WeatherForecastResponse:
        if force:
            forecast_engine.clear_weather_caches()

        try:
            payload = self._forecast_loader(city, lat, lon)
            if not payload:
                raise WeatherSourceUnavailable("official_forecast_unavailable")
            return WeatherForecastResponse.model_validate(payload)
        except WeatherSourceUnavailable:
            raise
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError) as error:
            raise WeatherSourceUnavailable("official_forecast_unavailable") from error

    def get_local_pilot_forecast(
        self,
        *,
        city: str,
        lat: float | None,
        lon: float | None,
        force: bool = False,
    ) -> WeatherForecastResponse:
        """Serve the official bulletin without consulting Open-Meteo."""

        if force:
            forecast_engine.clear_weather_caches()

        try:
            payload = self._local_pilot_forecast_loader(city, lat, lon)
            if not payload:
                raise WeatherSourceUnavailable("official_forecast_unavailable")
            return WeatherForecastResponse.model_validate(payload)
        except WeatherSourceUnavailable:
            raise
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError) as error:
            raise WeatherSourceUnavailable("official_forecast_unavailable") from error

    def get_official_alerts(self, *, force: bool = False) -> OfficialAlertsResponse:
        payload: dict[str, Any] = self._alerts_loader(force=force)
        return OfficialAlertsResponse.model_validate(payload)

    def get_radar(
        self,
        *,
        city: str,
        lat: float | None,
        lon: float | None,
        force: bool = False,
    ) -> WeatherRadarResponse:
        try:
            payload = self._radar_loader(city, lat, lon, force=force)
            return WeatherRadarResponse.model_validate(payload)
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError) as error:
            raise WeatherSourceUnavailable("radar_unavailable") from error

    def get_bootstrap(
        self,
        *,
        city: str,
        lat: float | None,
        lon: float | None,
        force: bool = False,
    ) -> WeatherBootstrapResponse:
        if force:
            current_engine.clear_current_weather_caches()
            alerts_engine.clear_official_alerts_cache()

        try:
            with ThreadPoolExecutor(max_workers=3) as executor:
                current_future = executor.submit(self._current_loader, city, lat, lon)
                forecast_future = executor.submit(self._forecast_loader, city, lat, lon)
                alerts_future = executor.submit(self._alerts_loader, force=force)
                current_payload = current_future.result()
                forecast_payload = forecast_future.result()
                alerts_payload = alerts_future.result()

            if not current_payload:
                raise WeatherSourceUnavailable("current_weather_unavailable")
            if not forecast_payload:
                raise WeatherSourceUnavailable("official_forecast_unavailable")

            return WeatherBootstrapResponse.model_validate(
                {
                    "city": city,
                    "current": current_payload,
                    "forecast": forecast_payload,
                    "official_alerts": alerts_payload,
                    "cache": {
                        "status": "fresh",
                        "generated_at": datetime.now().isoformat(),
                    },
                }
            )
        except WeatherSourceUnavailable:
            raise
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError) as error:
            raise WeatherSourceUnavailable("weather_bootstrap_unavailable") from error
