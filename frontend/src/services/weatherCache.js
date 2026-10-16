import {
  getLegacyLocationCacheKey,
  getLocationCacheKey,
} from "../domain/geo/locationCacheKey";
import { isFvgLocation } from "../domain/scope/productScope";
import { readJsonCacheEntry, removeJsonCache, writeJsonCache } from "./jsonCache";
import { isLocalWeatherPilot } from "./localWeatherPilot";
import { resolveWeatherRequestPolicy } from "./weatherProviderRuntime";

// Do not rehydrate the previous OSMER/Open-Meteo mixed current conditions.
export const WEATHER_BOOTSTRAP_CACHE_KEY = "weatherBootstrapCache:v3";
export const WEATHER_VERIFY_INTERVAL_MS = 5 * 60 * 1000;
export const WEATHER_CACHE_MAX_AGE_MS = WEATHER_VERIFY_INTERVAL_MS;

export function getWeatherCacheKey(location) {
  return `${WEATHER_BOOTSTRAP_CACHE_KEY}:${getLocationCacheKey(location)}`;
}

function getLegacyWeatherCacheKey(location) {
  if (!isFvgLocation(location)) return "";
  const currentLocationKey = getLocationCacheKey(location);
  const legacyLocationKey = getLegacyLocationCacheKey(location);
  if (!legacyLocationKey || legacyLocationKey === currentLocationKey) return "";
  return `${WEATHER_BOOTSTRAP_CACHE_KEY}:${legacyLocationKey}`;
}

function canUseWeatherDeviceCache(location) {
  try {
    resolveWeatherRequestPolicy({ location });
    return !isLocalWeatherPilot() && Boolean(location);
  } catch {
    // Unsupported/unknown explicit territories must fail closed without
    // making synchronous React cache hydration throw during render.
    return false;
  }
}

function isRetiredOpenMeteoPayload(payload) {
  const current = payload?.current || payload;
  return current?.primary_source === "open_meteo"
    || current?.source?.active === "open_meteo";
}

function readWeatherCacheEntryWithMigration(
  location,
  { maxAgeMs = WEATHER_CACHE_MAX_AGE_MS, storage, now } = {},
) {
  const options = { storage, now };
  const currentKey = getWeatherCacheKey(location);
  const current = readJsonCacheEntry(currentKey, maxAgeMs, options);
  if (current) return current;

  const legacyKey = getLegacyWeatherCacheKey(location);
  if (!legacyKey) return null;
  const legacy = readJsonCacheEntry(legacyKey, maxAgeMs, options);
  if (!legacy) return null;

  const promoted = writeJsonCache(currentKey, legacy.data, {
    storage,
    now: () => legacy.savedAt,
  });
  if (promoted) removeJsonCache(legacyKey, { storage });
  return legacy;
}

export function readWeatherDeviceCache(location, { maxAgeMs = WEATHER_CACHE_MAX_AGE_MS, storage, now } = {}) {
  if (!canUseWeatherDeviceCache(location)) return null;
  const entry = readWeatherCacheEntryWithMigration(location, { maxAgeMs, storage, now });
  return entry && !isRetiredOpenMeteoPayload(entry.data) ? entry.data : null;
}

export function readWeatherDeviceCacheEntry(
  location,
  { maxAgeMs = WEATHER_CACHE_MAX_AGE_MS, storage, now } = {},
) {
  if (!canUseWeatherDeviceCache(location)) return null;
  const entry = readWeatherCacheEntryWithMigration(location, { maxAgeMs, storage, now });
  return entry && !isRetiredOpenMeteoPayload(entry.data) ? entry : null;
}

export function writeWeatherDeviceCache(location, data, { storage, now } = {}) {
  if (!canUseWeatherDeviceCache(location)) return false;
  const written = writeJsonCache(getWeatherCacheKey(location), data, { storage, now });
  const legacyKey = getLegacyWeatherCacheKey(location);
  if (written && legacyKey) removeJsonCache(legacyKey, { storage });
  return written;
}

export function clearWeatherDeviceCache(location, { storage } = {}) {
  if (!canUseWeatherDeviceCache(location)) return false;
  const removedCurrent = removeJsonCache(getWeatherCacheKey(location), { storage });
  const legacyKey = getLegacyWeatherCacheKey(location);
  const removedLegacy = legacyKey ? removeJsonCache(legacyKey, { storage }) : false;
  return removedCurrent || removedLegacy;
}

export function hasOfficialOsmerForecasts(cacheData) {
  const forecasts =
    cacheData?.current?.official?.it?.forecasts ||
    cacheData?.forecast?.official?.it?.forecasts ||
    [];

  return Array.isArray(forecasts) && forecasts.some((item) => String(item?.text || "").trim());
}
