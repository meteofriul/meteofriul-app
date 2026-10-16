import { getLocationMunicipalityName } from "../domain/geo/locationIdentity";
import {
  getLocalWeatherPilotNow,
  getLocalWeatherPilotTestNow,
} from "./localWeatherPilot";
import { fetchLocalWeatherV1Bootstrap } from "./localWeatherV1Adapter";
import { fetchLocalWeatherV1RuntimeBundle } from "./localWeatherV1Runtime";
import { WEATHER_PROVIDERS } from "./weatherProviderPolicy";
import {
  isLocalWeatherPilotLocation,
  resolveWeatherHttpApiBase,
  resolveWeatherRequestPolicy,
  resolveWeatherV1RequestBaseUrl,
} from "./weatherProviderRuntime";

function optionalLocalStorage(storage) {
  if (storage !== undefined) return storage;
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function getLocationCity(location) {
  return getLocationMunicipalityName(location);
}

function buildLocationQuery(location) {
  const city = String(getLocationCity(location) || "").trim();

  if (!city) {
    throw new Error("Localita meteo mancante");
  }

  const params = new URLSearchParams({ city });
  const lat = typeof location === "object" ? Number(location?.lat) : NaN;
  const lon = typeof location === "object" ? Number(location?.lon) : NaN;

  if (Number.isFinite(lat) && Number.isFinite(lon)) {
    params.set("lat", String(lat));
    params.set("lon", String(lon));
  }

  return params;
}

export function buildLocalConditionsUrl(
  location,
  {
    apiBase,
    force = false,
    now = Date.now,
  } = {},
) {
  const base = String(resolveWeatherHttpApiBase(location, { apiBase })).replace(/\/$/, "");
  const params = buildLocationQuery(location);

  if (force) {
    const timestamp = typeof now === "function" ? now() : now;
    params.set("_", String(timestamp));
  }

  return `${base}/weather/current?${params.toString()}`;
}

export function normalizeLocalConditionsPayload(payload, { fallbackCity = "" } = {}) {
  const current = payload?.current || payload;

  if (!current || typeof current !== "object" || Array.isArray(current)) {
    throw new Error("Dati meteo locali mancanti");
  }

  const hasCurrentValue = [
    current.temperature,
    current.humidity,
    current.pressure,
    current.wind_speed,
    current.precipitation,
  ].some((value) => value !== null && value !== undefined && value !== "");
  const hasHourly = [current.hourly_forecast, current.hourly_next_12h]
    .some((slots) => Array.isArray(slots) && slots.length > 0);
  const hasPollen = Boolean(current.pollen_data && typeof current.pollen_data === "object");

  if (!hasCurrentValue && !hasHourly && !hasPollen) {
    throw new Error("Dati meteo locali incompleti");
  }

  return {
    city: String(payload?.city || current.city || fallbackCity || "").trim(),
    current,
    raw: payload,
  };
}

export async function fetchLocalConditions(
  location,
  {
    apiBase,
    fetchImpl = globalThis.fetch,
    force = false,
    now = Date.now,
    storage,
    weatherV1Fetcher = fetchLocalWeatherV1Bootstrap,
    providerConfig,
    verificationNow,
    verifyWindowMs,
    weatherV1BaseUrl,
  } = {},
) {
  if (typeof fetchImpl !== "function") {
    throw new Error("Fetch non disponibile");
  }

  const fallbackCity = getLocationCity(location);
  const providerPolicy = resolveWeatherRequestPolicy({ location, providerConfig });
  if (providerPolicy.primary === WEATHER_PROVIDERS.AUTONOMOUS) {
    const weatherModelNow = getLocalWeatherPilotTestNow()
      ? getLocalWeatherPilotNow
      : now;
    const payload = await fetchLocalWeatherV1RuntimeBundle(location, {
      baseUrl: resolveWeatherV1RequestBaseUrl(providerPolicy, {
        configuredBaseUrl: weatherV1BaseUrl,
      }),
      bundleFetcher: weatherV1Fetcher,
      fetchImpl,
      force,
      now: weatherModelNow,
      storage: optionalLocalStorage(storage),
      ...(verificationNow === undefined ? {} : { verificationNow }),
      ...(verifyWindowMs === undefined ? {} : { verifyWindowMs }),
    });
    return normalizeLocalConditionsPayload(payload, { fallbackCity });
  }

  const url = buildLocalConditionsUrl(location, { apiBase, force, now });
  const response = await fetchImpl(url, {
    cache: force || isLocalWeatherPilotLocation(location) ? "no-store" : "default",
  });

  if (!response?.ok) {
    throw new Error("Risposta meteo locale non valida");
  }

  const payload = await response.json();
  return normalizeLocalConditionsPayload(payload, { fallbackCity });
}
