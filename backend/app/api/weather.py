from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.contracts.weather import (
    NationalOfficialAlertsResponse,
    OfficialAlertsResponse,
    WeatherBootstrapResponse,
    WeatherCurrentResponse,
    WeatherForecastResponse,
    WeatherRadarResponse,
)
from app.services.national_official_alerts_state import (
    NationalOfficialAlertsStateService,
    NationalOfficialAlertsUnavailable,
    get_national_official_alerts_state_service,
)
from app.infrastructure.open_meteo_policy import (
    LOCAL_WEATHER_PILOT_HEADER,
    is_loopback_hostname,
    provider_policy_status,
)
from app.services.weather import WeatherService, WeatherSourceUnavailable


router = APIRouter(prefix="/api/weather", tags=["weather"])


@lru_cache(maxsize=1)
def get_weather_service() -> WeatherService:
    return WeatherService()


def get_national_official_alerts_service() -> NationalOfficialAlertsStateService:
    return get_national_official_alerts_state_service()


def _weather_unavailable(error: WeatherSourceUnavailable) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"error": str(error)},
    )


def _pilot_http_error(status_code: int, error: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": error})


def _is_local_weather_pilot_request(request: Request) -> bool:
    raw_signal = request.headers.get(LOCAL_WEATHER_PILOT_HEADER)
    if raw_signal is None:
        return False
    if raw_signal.strip() != "1":
        raise _pilot_http_error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_local_weather_pilot_signal",
        )

    policy = provider_policy_status()
    if not policy["valid"] or not policy["local_weather_pilot_ready"]:
        raise _pilot_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "local_weather_pilot_backend_not_ready",
        )
    if not is_loopback_hostname(request.url.hostname):
        raise _pilot_http_error(
            status.HTTP_403_FORBIDDEN,
            "local_weather_pilot_requires_loopback_host",
        )
    return True


@router.get(
    "/current",
    response_model=WeatherCurrentResponse,
    response_model_exclude_none=True,
)
def get_current(
    request: Request,
    city: Annotated[str, Query(min_length=1, max_length=120)],
    service: Annotated[WeatherService, Depends(get_weather_service)],
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    refresh_token: Annotated[int | None, Query(alias="_")] = None,
) -> WeatherCurrentResponse:
    if _is_local_weather_pilot_request(request):
        raise _pilot_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "legacy_current_disabled_for_local_weather_pilot",
        )
    try:
        return service.get_current(
            city=city.strip(),
            lat=lat,
            lon=lon,
            force=refresh_token is not None,
        )
    except WeatherSourceUnavailable as error:
        raise _weather_unavailable(error) from error


@router.get(
    "/forecast",
    response_model=WeatherForecastResponse,
    response_model_exclude_none=True,
)
def get_forecast(
    request: Request,
    city: Annotated[str, Query(min_length=1, max_length=120)],
    service: Annotated[WeatherService, Depends(get_weather_service)],
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    refresh_token: Annotated[int | None, Query(alias="_")] = None,
) -> WeatherForecastResponse:
    try:
        if _is_local_weather_pilot_request(request):
            return service.get_local_pilot_forecast(
                city=city.strip(),
                lat=lat,
                lon=lon,
                force=refresh_token is not None,
            )
        return service.get_forecast(
            city=city.strip(),
            lat=lat,
            lon=lon,
            force=refresh_token is not None,
        )
    except WeatherSourceUnavailable as error:
        raise _weather_unavailable(error) from error


@router.get(
    "/bootstrap",
    response_model=WeatherBootstrapResponse,
    response_model_exclude_none=True,
)
def get_bootstrap(
    request: Request,
    city: Annotated[str, Query(min_length=1, max_length=120)],
    service: Annotated[WeatherService, Depends(get_weather_service)],
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    refresh_token: Annotated[int | None, Query(alias="_")] = None,
) -> WeatherBootstrapResponse:
    if _is_local_weather_pilot_request(request):
        raise _pilot_http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "legacy_bootstrap_disabled_for_local_weather_pilot",
        )
    try:
        return service.get_bootstrap(
            city=city.strip(),
            lat=lat,
            lon=lon,
            force=refresh_token is not None,
        )
    except WeatherSourceUnavailable as error:
        raise _weather_unavailable(error) from error


@router.get(
    "/official-alerts",
    response_model=OfficialAlertsResponse,
    response_model_exclude_none=True,
)
def get_official_alerts(
    service: Annotated[WeatherService, Depends(get_weather_service)],
    refresh_token: Annotated[int | None, Query(alias="_")] = None,
) -> OfficialAlertsResponse:
    return service.get_official_alerts(force=refresh_token is not None)


@router.get(
    "/official-alerts/national",
    response_model=NationalOfficialAlertsResponse,
    response_model_exclude_none=True,
)
def get_national_official_alerts(
    municipality_istat: Annotated[
        str,
        Query(pattern=r"^\d{6}$"),
    ],
    service: Annotated[
        NationalOfficialAlertsStateService,
        Depends(get_national_official_alerts_service),
    ],
) -> NationalOfficialAlertsResponse:
    try:
        payload = service.get_for_municipality(municipality_istat)
    except NationalOfficialAlertsUnavailable as error:
        message = str(error)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "municipality_unresolved" in message
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        raise HTTPException(
            status_code=status_code,
            detail={"error": message},
        ) from error
    return NationalOfficialAlertsResponse.model_validate(payload)


@router.get(
    "/radar",
    response_model=WeatherRadarResponse,
    response_model_exclude_none=True,
)
def get_radar(
    city: Annotated[str, Query(min_length=1, max_length=120)],
    service: Annotated[WeatherService, Depends(get_weather_service)],
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    refresh_token: Annotated[int | None, Query(alias="_")] = None,
) -> WeatherRadarResponse:
    try:
        return service.get_radar(
            city=city.strip(),
            lat=lat,
            lon=lon,
            force=refresh_token is not None,
        )
    except WeatherSourceUnavailable as error:
        raise _weather_unavailable(error) from error
