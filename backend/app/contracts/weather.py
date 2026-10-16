from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ForecastDay(BaseModel):
    model_config = ConfigDict(extra="allow")

    date: str
    condition: str
    weathercode: int | float | None = None
    min_temp: int | float | None = None
    max_temp: int | float | None = None
    official_text: str = ""
    emission: str = ""


class ForecastDaily(BaseModel):
    model_config = ConfigDict(extra="allow")

    time: list[str]
    temperature_2m_max: list[int | float | None]
    temperature_2m_min: list[int | float | None]
    weathercode: list[int | float | None]
    weather_code: list[int | float | None]


class WeatherForecastResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str
    forecast: list[ForecastDay] = Field(min_length=1)
    daily: ForecastDaily
    official: dict[str, Any] | None = None
    osmer_structured: dict[str, Any] | None = None
    source: dict[str, Any]
    fallback_used: str | None = None
    primary_source: str
    model_support: dict[str, bool]
    cache: dict[str, Any]
    data_quality: dict[str, Any]


class OfficialAlertRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    level: str
    valid_from: str = ""
    valid_to: str = ""
    official_text: str = ""


class OfficialAlertsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool
    count: int = Field(ge=0)
    alerts: list[OfficialAlertRecord]
    source: dict[str, Any]
    source_mode: str
    fetched_at: str | None = None
    expires_at: str = ""
    cache: dict[str, Any]
    warning: str | None = None
    error: str | None = None


class NationalOfficialAlertsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract: str
    schema_version: int
    status: str
    active: bool
    complete: bool
    highest_level: str | None = None
    highest_level_rank: int | None = None
    municipality: dict[str, Any]
    zones: list[str] = Field(min_length=1)
    conservative_multi_zone_display: bool
    regional_detail: dict[str, Any]
    standalone_display_allowed: bool
    source: dict[str, Any]
    revision: dict[str, Any]
    records: list[dict[str, Any]] = Field(min_length=1)
    zone_day_summaries: list[dict[str, Any]] = Field(min_length=1)
    expires_at: str
    generated_at: str
    cache: dict[str, Any]


class WeatherCurrentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str
    temperature: int | float | None = None
    condition: str = ""
    weathercode: int | float | None = None
    wind_speed: int | float | None = None
    wind_direction: int | float | None = None
    wind_gusts: int | float | None = None
    cloud_cover: int | float | None = None
    precipitation: int | float | None = None
    rain: int | float | None = None
    showers: int | float | None = None
    snowfall: int | float | None = None
    phrase: str = ""
    is_bora: bool = False
    humidity: int | float | None = None
    pressure: int | float | None = None
    feels_like: int | float | None = None
    visibility: int | float | None = None
    pop: str | None = None
    sunrise: str | None = None
    sunset: str | None = None
    hourly_next_12h: list[dict[str, Any]] = Field(default_factory=list)
    hourly_forecast: list[dict[str, Any]] = Field(default_factory=list)
    pollen: str = "Non disponibili"
    pollen_data: dict[str, Any] = Field(default_factory=dict)
    is_day: int | bool | None = None
    source: dict[str, Any]
    station: dict[str, Any] | None = None
    official: dict[str, Any] | None = None
    fallback_used: str | None = None
    primary_source: str
    model_support: dict[str, bool]
    cache: dict[str, Any]
    data_quality: dict[str, Any]


class WeatherBootstrapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str
    current: WeatherCurrentResponse
    forecast: WeatherForecastResponse
    official_alerts: OfficialAlertsResponse
    cache: dict[str, Any]


class RadarProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    product_type: str
    layer: str
    style: str = ""
    unit: str = ""
    period: str
    period_minutes: int = Field(ge=1)
    time: str
    updated_at: str


class WeatherRadarResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str
    available: bool
    mode: str
    status: str
    source: dict[str, Any]
    location: dict[str, float] | None = None
    products: list[RadarProduct] = Field(default_factory=list)
    frames: list[dict[str, Any]] | None = None
    tiles: dict[str, Any] | None = None
    wms: dict[str, Any] | None = None
    links: dict[str, str] | None = None
    certainty: str | None = None
    generated_at: str | None = None
    updated_at: str | None = None
    message: str
    warning: str | None = None
