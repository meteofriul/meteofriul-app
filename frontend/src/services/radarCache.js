import { getLocationCacheKey } from "../domain/geo/locationCacheKey";
import { readJsonCache, removeJsonCache, writeJsonCache } from "./jsonCache";

export const RADAR_CACHE_KEY = "bulletinRadarCache:v2";
export const RADAR_RECHECK_INTERVAL_MS = 2 * 60 * 1000;
export const RADAR_STORAGE_MAX_AGE_MS = 30 * 60 * 1000;

export function getRadarCacheKey(location) {
  return `${RADAR_CACHE_KEY}:${getLocationCacheKey(location)}`;
}

export function readRadarDeviceCache(
  location,
  { maxAgeMs = RADAR_STORAGE_MAX_AGE_MS, now, storage } = {},
) {
  return readJsonCache(getRadarCacheKey(location), maxAgeMs, { now, storage });
}

export function writeRadarDeviceCache(location, data, { now, storage } = {}) {
  return writeJsonCache(getRadarCacheKey(location), data, { now, storage });
}

export function clearRadarDeviceCache(location, { storage } = {}) {
  return removeJsonCache(getRadarCacheKey(location), { storage });
}
