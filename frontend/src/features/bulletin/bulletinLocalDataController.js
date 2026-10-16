import { normalizeWeatherData } from "../../domain/weather/normalizedWeather";
import {
  LOCAL_CONDITIONS_RECHECK_INTERVAL_MS,
  LOCAL_CONDITIONS_STORAGE_MAX_AGE_MS,
  readLocalConditionsDeviceCache,
  writeLocalConditionsDeviceCache,
} from "../../services/localConditionsCache";
import { fetchLocalConditions } from "../../services/localConditionsApi";

export const BULLETIN_LOCAL_INITIAL_STALE_MAX_AGE_MS = LOCAL_CONDITIONS_STORAGE_MAX_AGE_MS;
export const BULLETIN_LOCAL_REFRESH_FALLBACK_MAX_AGE_MS = BULLETIN_LOCAL_INITIAL_STALE_MAX_AGE_MS;
export const BULLETIN_LOCAL_AUTO_REFRESH_INTERVAL_MS = LOCAL_CONDITIONS_RECHECK_INTERVAL_MS;

function getLocationCity(location) {
  return typeof location === "string" ? location : location?.city;
}

function hasLocationCity(location) {
  return Boolean(String(getLocationCity(location) || "").trim());
}

function getErrorMessage(error) {
  return error instanceof Error ? error.message : String(error || "Errore sconosciuto");
}

function getNowValue(now) {
  return typeof now === "function" ? now() : now;
}

function getNowIso({ now = Date.now, nowIso } = {}) {
  if (typeof nowIso === "function") return nowIso();

  return new Date(getNowValue(now)).toISOString();
}

function hasUsefulPollen(current) {
  const values = current?.pollen_data?.values;

  return Boolean(
    current?.pollen_data &&
    (
      String(current.pollen_data?.level || "").trim() ||
      values && Object.values(values).some((value) => Number.isFinite(Number(value)))
    )
  );
}

export function isUsableLocalConditions(payload) {
  const current = payload?.current;
  if (!current || typeof current !== "object") return false;

  const normalized = normalizeWeatherData(current);

  return Boolean(
    [
      normalized.temperature,
      normalized.humidity,
      normalized.pressure,
      normalized.windSpeed,
      normalized.windGusts,
    ].some((value) => value !== null) ||
    normalized.hourlyForecast.length ||
    hasUsefulPollen(current)
  );
}

function toLocalConditionsCachePayload(payload, { updatedAt }) {
  return {
    city: payload?.city || payload?.current?.city || "",
    current: payload?.current || null,
    updatedAt,
  };
}

export function createBulletinLocalDataState(
  payload,
  { error = null, fromCache = false, isStale = false } = {},
) {
  if (!isUsableLocalConditions(payload)) {
    return {
      city: payload?.city || "",
      current: null,
      error: error ? getErrorMessage(error) : null,
      fromCache,
      isStale,
      rawCurrent: payload?.current || null,
      status: error ? "error" : "empty",
      updatedAt: payload?.updatedAt || null,
    };
  }

  return {
    city: payload.city || payload.current?.city || "",
    current: normalizeWeatherData(payload.current),
    error: error ? getErrorMessage(error) : null,
    fromCache,
    isStale,
    rawCurrent: payload.current,
    status: error ? "stale" : fromCache ? "cache" : "fresh",
    updatedAt: payload.updatedAt || null,
  };
}

export function createEmptyBulletinLocalDataState(error = null) {
  return createBulletinLocalDataState(null, { error });
}

export function readCachedBulletinLocalData(
  location,
  {
    cacheMaxAgeMs = Infinity,
    isStale = false,
    now = Date.now,
    storage,
    localCacheReader = readLocalConditionsDeviceCache,
  } = {},
) {
  if (!hasLocationCity(location)) return null;

  const cached = localCacheReader(location, {
    maxAgeMs: cacheMaxAgeMs,
    now,
    storage,
  });

  if (!isUsableLocalConditions(cached)) return null;

  return createBulletinLocalDataState(cached, {
    fromCache: true,
    isStale,
  });
}

export function readInitialBulletinLocalData(location, options = {}) {
  const {
    initialStaleMaxAgeMs = BULLETIN_LOCAL_INITIAL_STALE_MAX_AGE_MS,
    ...cacheOptions
  } = options;

  return (
    readCachedBulletinLocalData(location, {
      ...cacheOptions,
      cacheMaxAgeMs: LOCAL_CONDITIONS_RECHECK_INTERVAL_MS,
    }) ||
    readCachedBulletinLocalData(location, {
      ...cacheOptions,
      cacheMaxAgeMs: initialStaleMaxAgeMs,
      isStale: true,
    })
  );
}

export async function loadBulletinLocalData(
  location,
  {
    cacheMaxAgeMs = LOCAL_CONDITIONS_RECHECK_INTERVAL_MS,
    force = false,
    localCacheReader = readLocalConditionsDeviceCache,
    localCacheWriter = writeLocalConditionsDeviceCache,
    localFetcher = fetchLocalConditions,
    now = Date.now,
    nowIso,
    refreshFallbackMaxAgeMs = BULLETIN_LOCAL_REFRESH_FALLBACK_MAX_AGE_MS,
    storage,
  } = {},
) {
  if (!hasLocationCity(location)) {
    return createEmptyBulletinLocalDataState(new Error("Localita meteo mancante"));
  }

  const cacheOptions = { now, storage };
  const cached = localCacheReader(location, { ...cacheOptions, maxAgeMs: cacheMaxAgeMs });

  if (!force && isUsableLocalConditions(cached)) {
    return createBulletinLocalDataState(cached, { fromCache: true });
  }

  try {
    const payload = await localFetcher(location, { force, now, storage });
    const cachePayload = toLocalConditionsCachePayload(payload, {
      updatedAt: getNowIso({ now, nowIso }),
    });

    if (!isUsableLocalConditions(cachePayload)) {
      throw new Error("Dati meteo locali incompleti");
    }

    localCacheWriter(location, cachePayload, cacheOptions);

    return createBulletinLocalDataState(cachePayload);
  } catch (error) {
    const fallbackCache = cached || localCacheReader(location, {
      ...cacheOptions,
      maxAgeMs: refreshFallbackMaxAgeMs,
    });

    if (isUsableLocalConditions(fallbackCache)) {
      return createBulletinLocalDataState(fallbackCache, {
        error,
        fromCache: true,
        isStale: !cached,
      });
    }

    return createEmptyBulletinLocalDataState(error);
  }
}
