"""Current local weather engine for the UI3 API boundary.

Open-Meteo supplies the current conditions shown in the hero and its details.
OSMER observations and bulletins stay separate; CAMS supplies pollen estimates.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

import requests

from app.infrastructure.open_meteo_policy import require_open_meteo_enabled

from . import forecast_engine
from .timezone_support import resolve_weather_timezone


OPEN_METEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_CURRENT_CACHE_TTL = 5 * 60
CURRENT_WEATHER_POLICY = "open-meteo-current-v1"
WEATHER_SECONDARY_TIMEOUT = 4

weather_cache: dict = {}
pollen_cache: dict = {}

FRIULIAN_PHRASES = {
    "Soleggiato": "Il soreli al sclaris dut",
    "Poco nuvoloso": "Il c\u00eel al reste un p\u00f4c n\u00fbl",
    "Parzialmente nuvoloso": "Il c\u00eel al reste cuviert a tocs",
    "Coperto": "Il c\u00eel al reste cuviert",
    "Nebbia": "Niblis basse, va cun calme",
    "Pioggia leggera": "Al pl\u00fbf plan plan",
    "Pioggia": "Al pl\u00fbf, puarte il lambrel",
    "Rovesci": "Rovescis in zone",
    "Temporale": "Timp di burasce, mi\u00f4r st\u00e2 cuiets",
    "Neve": "Al n\u00eaf, copriti ben",
    "Vento": "A sofe la buere, ten dur",
}


def normalize_current_condition(
    condition: str,
    *,
    weather_code=None,
    precipitation=None,
    rain=None,
    showers=None,
    snowfall=None,
    wind_speed=None,
    city: str = "",
) -> str:
    normalized_condition = str(condition or "").strip() or "Coperto"
    lowered = forecast_engine.normalize_for_search(normalized_condition)

    if re.search(r"\bpoco\s+nuv", lowered):
        normalized_condition = "Poco nuvoloso"
        lowered = forecast_engine.normalize_for_search(normalized_condition)
    elif re.search(r"\bparz(?:ialmente)?\.?\s+nuv\b", lowered) or "parzial" in lowered:
        normalized_condition = "Parzialmente nuvoloso"
        lowered = forecast_engine.normalize_for_search(normalized_condition)
    elif re.search(r"\bnuv\.?\b", lowered) or "nuvol" in lowered:
        normalized_condition = "Coperto"
        lowered = forecast_engine.normalize_for_search(normalized_condition)

    def numeric(value) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    try:
        numeric_weather_code = int(weather_code)
    except (TypeError, ValueError):
        numeric_weather_code = None

    no_precipitation = all(
        numeric(value) <= 0
        for value in (precipitation, rain, showers, snowfall)
    )
    if numeric_weather_code == 0 and no_precipitation and (
        "temporal" in lowered or "burasce" in lowered
    ):
        return forecast_engine.map_weather_code(numeric_weather_code, wind_speed)

    return normalized_condition


def is_bora_wind_direction(direction) -> bool:
    if direction is None:
        return True

    return 20 <= float(direction) % 360 <= 110


def is_bora_exposed_area(city: str) -> bool:
    name = forecast_engine.normalize_place_name(city)
    return any(
        place in name
        for place in (
            "trieste",
            "muggia",
            "duino",
            "aurisina",
            "sistiana",
            "monfalcone",
            "ronchi",
            "staranzano",
            "grado",
            "gorizia",
            "savogna",
            "doberdo",
            "san dorligo",
            "carso",
            "lignano",
            "lignano sabbiadoro",
        )
    )


def pollen_level(value):
    if value is None:
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    if numeric_value <= 0:
        return "Assenti"
    if numeric_value < 10:
        return "Bassi"
    if numeric_value < 50:
        return "Medi"
    return "Alti"


def get_pollen_data(lat: float, lon: float) -> dict:
    require_open_meteo_enabled("air_quality")
    cache_key = forecast_engine.make_cache_key("pollen", round(lat, 4), round(lon, 4))
    cached = forecast_engine.get_from_cache(pollen_cache, cache_key)
    if cached:
        return cached

    try:
        response = requests.get(
            OPEN_METEO_AIR_QUALITY_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": ",".join(
                    (
                        "alder_pollen",
                        "birch_pollen",
                        "grass_pollen",
                        "mugwort_pollen",
                        "olive_pollen",
                        "ragweed_pollen",
                    )
                ),
                "timezone": "auto",
            },
            headers={"User-Agent": forecast_engine.HTTP_USER_AGENT},
            timeout=WEATHER_SECONDARY_TIMEOUT,
        )
        response.raise_for_status()
        current = (response.json() or {}).get("current") or {}
        pollens = {
            "ontano": current.get("alder_pollen"),
            "betulla": current.get("birch_pollen"),
            "graminacee": current.get("grass_pollen"),
            "artemisia": current.get("mugwort_pollen"),
            "olivo": current.get("olive_pollen"),
            "ambrosia": current.get("ragweed_pollen"),
        }
        valid_values = {name: value for name, value in pollens.items() if value is not None}
        if not valid_values:
            result = {"summary": "Non disponibili", "level": None, "main": None, "values": pollens}
        else:
            main_name, main_value = max(valid_values.items(), key=lambda item: item[1])
            level = pollen_level(main_value)
            result = {
                "summary": f"{level} ({main_name})" if level else "Non disponibili",
                "level": level,
                "main": main_name,
                "values": pollens,
            }
        forecast_engine.set_cache(pollen_cache, cache_key, result)
        return result
    except (OSError, requests.RequestException, TypeError, ValueError):
        return {"summary": "Non disponibili", "level": None, "main": None, "values": {}}


HOURLY_FORECAST_RESERVOIR_HOURS = 48


def build_hourly_forecast(
    hourly: dict,
    *,
    limit: int = 12,
    timezone_name: str | None = None,
    utc_offset_seconds=None,
    now: datetime | None = None,
) -> list[dict]:
    times = hourly.get("time") or []
    if not times:
        return []

    local_timezone = resolve_weather_timezone(timezone_name, utc_offset_seconds)
    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=local_timezone)
    current_local_hour = reference_time.astimezone(local_timezone).replace(
        minute=0,
        second=0,
        microsecond=0,
    )

    localized_times: list[tuple[int, datetime]] = []
    previous_utc: datetime | None = None
    for index, value in enumerate(times):
        try:
            item_time = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            continue
        if item_time.tzinfo is None:
            item_time = item_time.replace(tzinfo=local_timezone)
            item_utc = item_time.astimezone(timezone.utc)
            if previous_utc is not None and item_utc <= previous_utc:
                folded_time = item_time.replace(fold=1)
                folded_utc = folded_time.astimezone(timezone.utc)
                if folded_utc > previous_utc:
                    item_time = folded_time
                    item_utc = folded_utc
        else:
            item_time = item_time.astimezone(local_timezone)
            item_utc = item_time.astimezone(timezone.utc)
        localized_times.append((index, item_time))
        previous_utc = item_utc

    selected_times = [
        (index, item_time)
        for index, item_time in localized_times
        if item_time.astimezone(timezone.utc)
        >= current_local_hour.astimezone(timezone.utc)
    ][:max(0, int(limit))]

    def read(name: str, index: int):
        values = hourly.get(name) or []
        return values[index] if index < len(values) else None

    return [
        {
            "time": item_time.isoformat(timespec="minutes"),
            "temperature": read("temperature_2m", index),
            "precipitation_probability": read("precipitation_probability", index),
            "precipitation": read("precipitation", index),
            "rain": read("rain", index),
            "showers": read("showers", index),
            "snowfall": read("snowfall", index),
            "weathercode": read("weather_code", index),
            "wind_speed": read("wind_speed_10m", index),
            "wind_direction": read("wind_direction_10m", index),
            "wind_gusts": read("wind_gusts_10m", index),
        }
        for index, item_time in selected_times
    ]


def build_hourly_next_12h(
    hourly: dict,
    *,
    timezone_name: str | None = None,
    utc_offset_seconds=None,
    now: datetime | None = None,
) -> list[dict]:
    return build_hourly_forecast(
        hourly,
        limit=12,
        timezone_name=timezone_name,
        utc_offset_seconds=utc_offset_seconds,
        now=now,
    )


def calculate_sun_time(lat: float, lon: float, target_date, *, sunrise: bool) -> str | None:
    try:
        latitude = float(lat)
        longitude = float(lon)
    except (TypeError, ValueError):
        return None

    day_of_year = target_date.timetuple().tm_yday
    lng_hour = longitude / 15
    approx_time = day_of_year + ((6 if sunrise else 18) - lng_hour) / 24
    mean_anomaly = (0.9856 * approx_time) - 3.289
    true_longitude = (
        mean_anomaly
        + (1.916 * math.sin(math.radians(mean_anomaly)))
        + (0.020 * math.sin(math.radians(2 * mean_anomaly)))
        + 282.634
    ) % 360
    right_ascension = math.degrees(
        math.atan(0.91764 * math.tan(math.radians(true_longitude)))
    ) % 360
    right_ascension = (
        right_ascension
        + math.floor(true_longitude / 90) * 90
        - math.floor(right_ascension / 90) * 90
    ) / 15
    sin_declination = 0.39782 * math.sin(math.radians(true_longitude))
    cos_declination = math.cos(math.asin(sin_declination))
    cos_hour_angle = (
        math.cos(math.radians(90.833))
        - sin_declination * math.sin(math.radians(latitude))
    ) / (cos_declination * math.cos(math.radians(latitude)))
    if not -1 <= cos_hour_angle <= 1:
        return None

    hour_angle = math.degrees(math.acos(cos_hour_angle))
    if sunrise:
        hour_angle = 360 - hour_angle
    local_mean_time = hour_angle / 15 + right_ascension - 0.06571 * approx_time - 6.622
    utc_hour = (local_mean_time - lng_hour) % 24

    def last_sunday(year: int, month: int):
        end = (
            datetime(year, month + 1, 1).date() - timedelta(days=1)
            if month < 12
            else datetime(year, 12, 31).date()
        )
        return end - timedelta(days=(end.weekday() + 1) % 7)

    offset_hours = 2 if last_sunday(target_date.year, 3) <= target_date < last_sunday(target_date.year, 10) else 1
    local_hour = (utc_hour + offset_hours) % 24
    hour = int(local_hour)
    minute = int(round((local_hour - hour) * 60))
    if minute >= 60:
        hour = (hour + 1) % 24
        minute = 0
    return f"{target_date.isoformat()}T{hour:02d}:{minute:02d}:00+{offset_hours:02d}:00"


def get_astronomical_sun_times(lat: float, lon: float, target_date=None) -> dict:
    target = target_date or datetime.now().date()
    return {
        "sunrise": calculate_sun_time(lat, lon, target, sunrise=True),
        "sunset": calculate_sun_time(lat, lon, target, sunrise=False),
    }


def has_core_current_weather_values(**values) -> bool:
    observed = (
        values.get("temperature"),
        values.get("humidity"),
        values.get("pressure"),
        values.get("wind_speed"),
        values.get("wind_gusts"),
        values.get("precipitation"),
    )
    return any(value is not None for value in observed) or (
        values.get("weather_code") is not None and values.get("cloud_cover") is not None
    )


def get_real_current_weather(city: str, lat: float | None = None, lon: float | None = None) -> dict | None:
    require_open_meteo_enabled("current")
    lat = forecast_engine.normalize_optional_float(lat)
    lon = forecast_engine.normalize_optional_float(lon)
    cache_key = forecast_engine.make_cache_key(
        forecast_engine.WEATHER_PIPELINE_VERSION,
        "current",
        CURRENT_WEATHER_POLICY,
        city,
        lat,
        lon,
    )
    # Keep expired entries available for the verified Open-Meteo stale fallback.
    cached = forecast_engine.get_stale_from_cache(weather_cache, cache_key, WEATHER_CURRENT_CACHE_TTL)
    if cached:
        return cached

    if lat is None or lon is None:
        lat, lon = forecast_engine.geocode_city(city)
    if lat is None or lon is None:
        return None

    osmer_official = forecast_engine.get_osmer_official_weather(city, lat, lon)
    osmer_station = (osmer_official or {}).get("station") or {}

    data = {}
    try:
        data = forecast_engine.open_meteo_forecast(
            lat,
            lon,
            forecast_engine.WEATHER_REQUEST_TIMEOUT,
        )
        current = data.get("current") or {}
        daily = data.get("daily") or {}
        hourly = data.get("hourly") or {}
    except (OSError, requests.RequestException, TypeError, ValueError):
        current, daily, hourly = {}, {}, {}

    has_open_meteo = bool(current)
    if not has_open_meteo:
        stale = forecast_engine.get_stale_from_cache(
            weather_cache,
            cache_key,
            forecast_engine.WEATHER_STALE_TTL,
        )
        return (
            forecast_engine.add_data_quality(
                {**stale, "cache": {**stale.get("cache", {}), "status": "stale"}},
                "cached_verified", "stale", "open_meteo",
            )
            if stale
            else None
        )

    pollen_data = get_pollen_data(lat, lon)
    temperature = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    feels_like = current.get("apparent_temperature")
    pressure = current.get("pressure_msl")
    cloud_cover = current.get("cloud_cover")
    wind_speed = current.get("wind_speed_10m")
    wind_direction = current.get("wind_direction_10m")
    wind_gusts = current.get("wind_gusts_10m")
    precipitation = current.get("precipitation")
    rain = current.get("rain")
    showers = current.get("showers")
    snowfall = current.get("snowfall")
    visibility = current.get("visibility")
    weather_code = current.get("weather_code")
    is_day = current.get("is_day", 1)

    wind_speed_kmh = int(round(wind_speed)) if wind_speed is not None else None
    wind_direction_deg = int(round(wind_direction)) if wind_direction is not None else None
    wind_gusts_kmh = int(round(wind_gusts)) if wind_gusts is not None else None
    condition = (
        forecast_engine.map_weather_code(weather_code, wind_speed_kmh)
        if weather_code is not None
        else "Coperto"
    )

    if not has_core_current_weather_values(
        temperature=temperature,
        humidity=humidity,
        pressure=pressure,
        wind_speed=wind_speed_kmh,
        wind_gusts=wind_gusts_kmh,
        precipitation=precipitation,
        weather_code=weather_code,
        cloud_cover=cloud_cover,
    ):
        stale = forecast_engine.get_stale_from_cache(
            weather_cache,
            cache_key,
            forecast_engine.WEATHER_STALE_TTL,
        )
        return (
            forecast_engine.add_data_quality(
                {**stale, "cache": {**stale.get("cache", {}), "status": "stale"}},
                "cached_verified", "stale", "open_meteo",
            )
            if stale
            else None
        )

    is_bora = (
        is_bora_exposed_area(city)
        and wind_speed_kmh is not None
        and max(wind_speed_kmh, wind_gusts_kmh or 0) >= 45
        and is_bora_wind_direction(wind_direction_deg)
    )
    if is_bora:
        condition = "Vento"
    condition = normalize_current_condition(
        condition,
        weather_code=weather_code,
        precipitation=precipitation,
        rain=rain,
        showers=showers,
        snowfall=snowfall,
        wind_speed=wind_speed_kmh,
        city=city,
    )

    pop_values = daily.get("precipitation_probability_max") or []
    pop_value = f"{int(round(pop_values[0]))}%" if pop_values and pop_values[0] is not None else None
    sun_times = get_astronomical_sun_times(lat, lon)
    sunrise = (daily.get("sunrise") or [None])[0] or sun_times.get("sunrise")
    sunset = (daily.get("sunset") or [None])[0] or sun_times.get("sunset")
    model_support = {
        "open_meteo": has_open_meteo,
        "hourly": bool(hourly),
        "daily": bool(daily),
    }
    primary_source = "open_meteo"
    fallback_used = None
    source = forecast_engine.build_weather_sources(city, lat, lon, primary_source)
    source.update(
        {
            "fallback_used": fallback_used,
            "primary_source": primary_source,
            "current_policy": CURRENT_WEATHER_POLICY,
            "model_support": model_support,
            "station": osmer_station.get("station") if osmer_station else None,
            "station_scope": osmer_station.get("station_scope") if osmer_station else None,
            "station_distance_km": osmer_station.get("station_distance_km") if osmer_station else None,
            "official_scope": (
                "osmer_station_and_bulletin"
                if osmer_station
                else ("osmer_bulletin" if osmer_official else "none")
            ),
        }
    )

    hourly_forecast = build_hourly_forecast(
        hourly,
        limit=HOURLY_FORECAST_RESERVOIR_HOURS,
        timezone_name=data.get("timezone"),
        utc_offset_seconds=data.get("utc_offset_seconds"),
    )
    result = {
        "city": city,
        "temperature": int(round(temperature)) if temperature is not None else None,
        "condition": condition,
        "weathercode": weather_code,
        "wind_speed": wind_speed_kmh,
        "wind_direction": wind_direction_deg,
        "wind_gusts": wind_gusts_kmh,
        "cloud_cover": int(round(cloud_cover)) if cloud_cover is not None else None,
        "precipitation": round(float(precipitation), 1) if precipitation is not None else None,
        "rain": round(float(rain), 1) if rain is not None else None,
        "showers": round(float(showers), 1) if showers is not None else None,
        "snowfall": round(float(snowfall), 1) if snowfall is not None else None,
        "phrase": FRIULIAN_PHRASES.get(condition, ""),
        "is_bora": is_bora,
        "humidity": int(round(humidity)) if humidity is not None else None,
        "pressure": int(round(pressure)) if pressure is not None else None,
        "feels_like": int(round(feels_like)) if feels_like is not None else None,
        "visibility": visibility,
        "pop": pop_value,
        "sunrise": sunrise,
        "sunset": sunset,
        "hourly_next_12h": hourly_forecast[:12],
        "hourly_forecast": hourly_forecast,
        "pollen": pollen_data["summary"],
        "pollen_data": pollen_data,
        "is_day": is_day,
        "source": source,
        "station": osmer_station or None,
        "official": osmer_official,
        "fallback_used": fallback_used,
        "primary_source": primary_source,
        "model_support": model_support,
        "cache": {
            "status": "fresh",
            "ttl_seconds": WEATHER_CURRENT_CACHE_TTL,
            "generated_at": datetime.now().isoformat(),
        },
    }
    result = forecast_engine.add_data_quality(
        result,
        "model",
        "fresh",
        primary_source,
    )
    forecast_engine.set_cache(weather_cache, cache_key, result)
    return result


def clear_current_weather_caches(*, include_shared: bool = True) -> None:
    weather_cache.clear()
    pollen_cache.clear()
    if include_shared:
        forecast_engine.clear_weather_caches()
