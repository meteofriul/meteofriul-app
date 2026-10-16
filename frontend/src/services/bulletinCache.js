import { getLocationCacheKey } from "../domain/geo/locationCacheKey";
import { readJsonCache, removeJsonCache, writeJsonCache } from "./jsonCache";
import { readWeatherDeviceCache } from "./weatherCache";
import { isLocalWeatherPilot } from "./localWeatherPilot";

export const BULLETIN_DEVICE_CACHE_KEY = "officialBulletinCache:v1";
export const BULLETIN_LOCAL_WEATHER_PILOT_CACHE_KEY = "officialBulletinCache:local-weather-pilot:v1";
export const BULLETIN_CACHE_RECHECK_INTERVAL_MS = 5 * 60 * 1000;
export const BULLETIN_CACHE_STORAGE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

export function getBulletinCacheKey(
  location,
  { localPilot = isLocalWeatherPilot() } = {},
) {
  const namespace = localPilot
    ? BULLETIN_LOCAL_WEATHER_PILOT_CACHE_KEY
    : BULLETIN_DEVICE_CACHE_KEY;
  return `${namespace}:${getLocationCacheKey(location)}`;
}

export function readBulletinDeviceCache(
  location,
  {
    allowLegacyWeatherCache = true,
    localPilot = isLocalWeatherPilot(),
    maxAgeMs = BULLETIN_CACHE_STORAGE_MAX_AGE_MS,
    now,
    storage,
  } = {},
) {
  const options = { now, storage };
  const cached = readJsonCache(getBulletinCacheKey(location, { localPilot }), maxAgeMs, options);

  if (cached || !allowLegacyWeatherCache || localPilot) return cached;

  // The bulletin may still migrate official text from v2; the hero never reads it.
  return readWeatherDeviceCache(location, { ...options, maxAgeMs })
    || readJsonCache(`weatherBootstrapCache:v2:${getLocationCacheKey(location)}`, maxAgeMs, options);
}

export function writeBulletinDeviceCache(
  location,
  data,
  { localPilot = isLocalWeatherPilot(), now, storage } = {},
) {
  return writeJsonCache(getBulletinCacheKey(location, { localPilot }), data, { now, storage });
}

export function clearBulletinDeviceCache(
  location,
  { localPilot = isLocalWeatherPilot(), storage } = {},
) {
  return removeJsonCache(getBulletinCacheKey(location, { localPilot }), { storage });
}
