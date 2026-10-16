import { getLocationCacheKey } from "../domain/geo/locationCacheKey";
import { readJsonCache, removeJsonCache, writeJsonCache } from "./jsonCache";
import { readWeatherDeviceCache } from "./weatherCache";
import { isLocalWeatherPilot } from "./localWeatherPilot";
import { resolveWeatherRequestPolicy } from "./weatherProviderRuntime";

export const LOCAL_CONDITIONS_CACHE_KEY = "bulletinLocalConditionsCache:v1";
export const LOCAL_CONDITIONS_RECHECK_INTERVAL_MS = 10 * 60 * 1000;
export const LOCAL_CONDITIONS_STORAGE_MAX_AGE_MS = 3 * 60 * 60 * 1000;

export function getLocalConditionsCacheKey(location) {
  return `${LOCAL_CONDITIONS_CACHE_KEY}:${getLocationCacheKey(location)}`;
}

function canUseLocalConditionsCache(location) {
  try {
    resolveWeatherRequestPolicy({ location });
    return !isLocalWeatherPilot() && Boolean(location);
  } catch {
    return false;
  }
}

function isRetiredOpenMeteoPayload(payload) {
  const current = payload?.current || payload;
  return current?.primary_source === "open_meteo"
    || current?.source?.active === "open_meteo";
}

export function readLocalConditionsDeviceCache(
  location,
  {
    allowLegacyWeatherCache = true,
    maxAgeMs = LOCAL_CONDITIONS_STORAGE_MAX_AGE_MS,
    now,
    storage,
  } = {},
) {
  if (!canUseLocalConditionsCache(location)) return null;
  const options = { now, storage };
  const cached = readJsonCache(getLocalConditionsCacheKey(location), maxAgeMs, options);

  if (cached) return isRetiredOpenMeteoPayload(cached) ? null : cached;
  if (!allowLegacyWeatherCache) return null;

  return readWeatherDeviceCache(location, { ...options, maxAgeMs });
}

export function writeLocalConditionsDeviceCache(location, data, { now, storage } = {}) {
  if (!canUseLocalConditionsCache(location)) return false;
  return writeJsonCache(getLocalConditionsCacheKey(location), data, { now, storage });
}

export function clearLocalConditionsDeviceCache(location, { storage } = {}) {
  if (!canUseLocalConditionsCache(location)) return false;
  return removeJsonCache(getLocalConditionsCacheKey(location), { storage });
}
