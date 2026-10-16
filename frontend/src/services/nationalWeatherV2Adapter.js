import { getDateTimeFormatter } from "../domain/dateTimeFormatters.js";
import {
  getLocationMunicipality,
  getLocationMunicipalityName,
} from "../domain/geo/locationIdentity";
import { getHomeSolarState } from "../features/home/homeDayPhase";
import { ICON_FORECAST_WINDOW_POLICY, selectIconFutureRows } from "./iconForecastWindow";
import { fetchNationalWeatherV2Cell } from "./nationalWeatherV2Client";

const HOUR_MS = 3_600_000;
const TIME_ZONE = "Europe/Rome";
const PRIMARY_SOURCE = "icon2i_local_pilot";
const MODE = "national_contract_v2";
const STORAGE_PREFIX = "meteofriul:national-weather-v2:";
const CONDITION_LABELS = Object.freeze({
  0: "Sereno", 1: "Poco nuvoloso", 2: "Parzialmente nuvoloso", 3: "Coperto",
  45: "Nebbia", 48: "Nebbia", 51: "Pioviggine debole", 53: "Pioviggine",
  55: "Pioviggine intensa", 56: "Pioviggine gelata", 57: "Pioviggine gelata",
  61: "Pioggia debole", 63: "Pioggia", 65: "Pioggia intensa", 66: "Pioggia gelata",
  67: "Pioggia gelata", 71: "Neve debole", 73: "Neve", 75: "Neve intensa",
  77: "Neve", 80: "Rovesci deboli", 81: "Rovesci", 82: "Rovesci intensi",
  85: "Rovesci di neve", 86: "Rovesci di neve", 95: "Temporale", 96: "Temporale forte",
});

function clockMilliseconds(now) {
  const value = typeof now === "function" ? now() : now;
  const timestamp = value instanceof Date ? value.getTime() : Number(value);
  if (!Number.isFinite(timestamp)) throw new Error("Orologio nazionale v2 non valido");
  return timestamp;
}

function numberAt(series, index) {
  const raw = series?.[index];
  if (raw === null || raw === undefined || raw === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function round(value, digits = 1) {
  if (!Number.isFinite(value)) return null;
  const power = 10 ** digits;
  return Math.round(value * power) / power;
}

function relativeHumidity(temperatureC, dewPointC) {
  if (!Number.isFinite(temperatureC) || !Number.isFinite(dewPointC)) return null;
  const vapor = Math.exp((17.625 * dewPointC) / (243.04 + dewPointC));
  const saturation = Math.exp((17.625 * temperatureC) / (243.04 + temperatureC));
  return Math.max(0, Math.min(100, round(100 * vapor / saturation, 0)));
}

function solarState(time, latitude, longitude) {
  return getHomeSolarState({ now: time, latitude, longitude, timeZone: TIME_ZONE });
}

function clockLabel(minutes) {
  if (!Number.isFinite(minutes)) return null;
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(Math.round(minutes % 60)).padStart(2, "0")}`;
}

export function deriveNationalAccumulatedInterval(series, index) {
  const current = numberAt(series, index);
  if (current === null) return null;
  if (index === 0) return null;
  const previous = numberAt(series, index - 1);
  if (previous === null) return null;
  const delta = current - previous;
  if (delta >= -0.001) return Math.max(0, round(delta));
  return Math.max(0, round(current));
}

function sumAccumulatedIntervals(values, variableIds, index) {
  const intervals = variableIds.map(id => deriveNationalAccumulatedInterval(values[id], index));
  if (intervals.some(value => value === null)) return null;
  return round(intervals.reduce((total, value) => total + value, 0));
}

function buildRows(block, cell) {
  const values = cell.values;
  return block.time_axis.map((validAt, index) => {
    const temperature = numberAt(values.t_2m_k, index);
    const dewPoint = numberAt(values.td_2m_k, index);
    const u = numberAt(values.u_10m_m_s, index);
    const v = numberAt(values.v_10m_m_s, index);
    const code = numberAt(values.weather_code, index);
    const windMs = u === null || v === null ? null : Math.hypot(u, v);
    const windFrom = u === null || v === null
      ? null
      : (Math.atan2(-u, -v) * 180 / Math.PI + 360) % 360;
    const temperatureC = temperature === null ? null : round(temperature - 273.15);
    const dewPointC = dewPoint === null ? null : dewPoint - 273.15;
    const solar = solarState(validAt, cell.latitude, cell.longitude);
    const precipitation = deriveNationalAccumulatedInterval(values.total_precipitation_mm, index);
    const rain = sumAccumulatedIntervals(
      values,
      ["convective_rain_mm", "grid_scale_rain_mm"],
      index,
    );
    const snowWaterEquivalent = sumAccumulatedIntervals(
      values,
      ["convective_snow_mm", "grid_scale_snow_mm", "grid_scale_graupel_mm"],
      index,
    );
    return {
      valid_at: validAt,
      time: validAt,
      interval_start: new Date(Date.parse(validAt) - HOUR_MS).toISOString(),
      interval_end: validAt,
      temperature: temperatureC,
      condition: CONDITION_LABELS[code] || "Condizione meteo non disponibile",
      weathercode: null,
      primary_source: PRIMARY_SOURCE,
      feels_like: temperatureC,
      humidity: relativeHumidity(temperatureC, dewPointC),
      pressure: round((numberAt(values.pressure_msl_pa, index) ?? NaN) / 100),
      cloud_cover: round(numberAt(values.cloud_cover_pct, index), 0),
      wind_speed: round((windMs ?? NaN) * 3.6),
      wind_direction: round(windFrom, 0),
      wind_gusts: round((numberAt(values.wind_gust_max_m_s, index) ?? NaN) * 3.6),
      precipitation,
      rain,
      showers: null,
      snowfall: null,
      snowfall_water_equivalent_mm: snowWaterEquivalent,
      precipitation_probability: null,
      visibility: null,
      is_day: solar.isNight ? 0 : 1,
      data_quality: { mode: MODE, native_weather_code: code, valid_at_utc: validAt },
    };
  });
}

function zonedDateAndHour(timestamp) {
  const values = Object.fromEntries(getDateTimeFormatter("en-CA", {
    day: "2-digit", hour: "2-digit", hourCycle: "h23", month: "2-digit",
    timeZone: TIME_ZONE, year: "numeric",
  }).formatToParts(new Date(timestamp)).map(({ type, value }) => [type, value]));
  return { date: `${values.year}-${values.month}-${values.day}`, hour: Number(values.hour) };
}

function buildDaily(rows) {
  const groups = new Map();
  for (const row of rows) {
    const local = zonedDateAndHour(row.valid_at);
    if (!groups.has(local.date)) groups.set(local.date, []);
    groups.get(local.date).push({ row, hour: local.hour });
  }
  const forecast = [...groups.entries()].map(([date, entries]) => {
    const temperatures = entries.map(({ row }) => row.temperature).filter(Number.isFinite);
    const representative = entries.reduce((best, entry) => (
      Math.abs(entry.hour - 12) < Math.abs(best.hour - 12) ? entry : best
    ));
    const complete = entries[0]?.hour === 0 && entries.at(-1)?.hour === 23
      && [23, 24, 25].includes(entries.length) && temperatures.length === entries.length;
    return {
      date,
      condition: representative.row.condition,
      weathercode: null,
      min_temp: complete ? Math.min(...temperatures) : null,
      max_temp: complete ? Math.max(...temperatures) : null,
      sampled_min_temp: temperatures.length ? Math.min(...temperatures) : null,
      sampled_max_temp: temperatures.length ? Math.max(...temperatures) : null,
      source_hours: entries.length,
      partial_day: !complete,
      primary_source: PRIMARY_SOURCE,
      official_text: "",
      emission: "",
    };
  });
  return {
    forecast,
    daily: {
      time: forecast.map(day => day.date),
      temperature_2m_min: forecast.map(day => day.min_temp),
      temperature_2m_max: forecast.map(day => day.max_temp),
      weathercode: forecast.map(() => null),
      weather_code: forecast.map(() => null),
    },
  };
}

function cacheKey(baseUrl, location) {
  const municipality = getLocationMunicipality(location);
  const identity = municipality?.istatCode
    || `${getLocationMunicipalityName(location).toLocaleLowerCase("it")}|${municipality?.province || ""}`;
  return `${STORAGE_PREFIX}${String(baseUrl)}:${encodeURIComponent(identity)}`;
}

function optionalStorage(storage) {
  try { return storage ?? null; } catch { return null; }
}

function persist(storage, key, bundle) {
  try { storage?.setItem(key, JSON.stringify(bundle)); } catch { /* optional cache */ }
}

export function readNationalWeatherV2PersistedBundle(
  location,
  { baseUrl, storage, now = Date.now } = {},
) {
  const target = optionalStorage(storage);
  const key = cacheKey(baseUrl, location);
  const discard = () => {
    try { target?.removeItem?.(key); } catch { /* optional cache */ }
  };
  try {
    const raw = target?.getItem(key);
    const value = raw ? JSON.parse(raw) : null;
    if (raw && (value?.current?.data_quality?.mode !== MODE || !value?.forecast)) discard();
    if (value?.current?.data_quality?.mode !== MODE || !value?.forecast) return null;
    const nowMilliseconds = clockMilliseconds(now);
    const currentAt = Date.parse(value.current.data_quality.valid_at_utc);
    if (
      !Number.isFinite(currentAt)
      || currentAt > nowMilliseconds
      || nowMilliseconds - currentAt >= HOUR_MS
    ) {
      discard();
      return null;
    }
    const future = selectIconFutureRows(value.current.hourly_forecast, nowMilliseconds, "time");
    if (future.length < ICON_FORECAST_WINDOW_POLICY.minimumFutureHours) {
      discard();
      return null;
    }
    return {
      ...value,
      current: {
        ...value.current,
        hourly_forecast: future,
        hourly_next_12h: future.slice(0, 12),
      },
    };
  } catch {
    discard();
    return null;
  }
}

export function adaptNationalWeatherV2Cell({ resolution, block, cell }, { now = Date.now } = {}) {
  const nowMilliseconds = clockMilliseconds(now);
  const rows = buildRows(block, cell);
  let currentIndex = -1;
  for (let index = 0; index < rows.length; index += 1) {
    if (Date.parse(rows[index].valid_at) <= nowMilliseconds) currentIndex = index;
  }
  if (currentIndex < 0 || nowMilliseconds - Date.parse(rows[currentIndex].valid_at) >= HOUR_MS) {
    throw new Error("Campione corrente nazionale v2 non disponibile");
  }
  const future = selectIconFutureRows(rows, nowMilliseconds);
  if (future.length < ICON_FORECAST_WINDOW_POLICY.minimumFutureHours) {
    throw new Error("Copertura futura nazionale v2 insufficiente");
  }
  const sample = rows[currentIndex];
  const municipality = resolution.municipality;
  const solar = solarState(sample.valid_at, cell.latitude, cell.longitude);
  const source = {
    active: PRIMARY_SOURCE,
    primary_source: PRIMARY_SOURCE,
    provider: "ItaliaMeteo",
    model: "ICON-2I",
    contract: "weather/v2/icon2i",
    municipality_istat: municipality.istat_code,
    run_id: resolution.source_run_id,
  };
  const dataQuality = {
    mode: MODE,
    status: "experimental_local_pilot_only",
    certainty: "experimental_model",
    source: PRIMARY_SOURCE,
    run_utc: resolution.run_at,
    generated_at_utc: resolution.generated_at,
    valid_at_utc: sample.valid_at,
    coverage_hours: future.length,
    run_age_hours: (nowMilliseconds - Date.parse(resolution.run_at)) / HOUR_MS,
    native_weather_code: sample.data_quality.native_weather_code,
    cams_status: "unavailable",
    municipality_istat: municipality.istat_code,
    catalog_version: block.metadata?.catalog?.version || "national-v2",
    catalog_sha256: block.metadata?.catalog?.sha256 || null,
    grid_point: { latitude: cell.latitude, longitude: cell.longitude },
    capability_gaps: ["visibility", "precipitation_probability", "cams_pollen", "station_observations"],
    flags: ["experimental_national_v2"],
  };
  const modelSupport = { icon2i: true, cams: false, open_meteo: false, hourly: true, daily: true };
  const current = {
    ...sample,
    city: municipality.name,
    phrase: "",
    is_bora: false,
    pop: null,
    sunrise: clockLabel(solar.sunriseMinutes),
    sunset: clockLabel(solar.sunsetMinutes),
    hourly_next_12h: future.slice(0, 12),
    hourly_forecast: future,
    pollen: null,
    pollen_data: { status: "unavailable" },
    air_quality_data: null,
    source,
    station: null,
    official: null,
    fallback_used: null,
    model_support: modelSupport,
    cache: { status: "fresh", mode: MODE, generated_at: resolution.generated_at, ttl_seconds: 0 },
    data_quality: dataQuality,
  };
  const daily = buildDaily(rows);
  const forecast = {
    city: municipality.name,
    daily_extrema_version: 2,
    ...daily,
    source,
    fallback_used: null,
    primary_source: PRIMARY_SOURCE,
    model_support: modelSupport,
    cache: { ...current.cache },
    data_quality: { ...dataQuality },
  };
  return { city: municipality.name, current, forecast };
}

export async function fetchNationalWeatherV2Bootstrap(
  location,
  {
    baseUrl,
    fetchImpl = globalThis.fetch,
    force = false,
    now = Date.now,
    storage = globalThis.localStorage,
    cellFetcher = fetchNationalWeatherV2Cell,
  } = {},
) {
  const key = cacheKey(baseUrl, location);
  try {
    const source = await cellFetcher(location, { baseUrl, fetchImpl, force });
    const bundle = adaptNationalWeatherV2Cell(source, { now });
    persist(optionalStorage(storage), key, bundle);
    return bundle;
  } catch (error) {
    if (!force) {
      const retained = readNationalWeatherV2PersistedBundle(location, { baseUrl, storage, now });
      if (retained) return retained;
    }
    throw error;
  }
}
