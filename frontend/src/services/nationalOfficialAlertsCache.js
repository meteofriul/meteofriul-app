import { readJsonCache, removeJsonCache, writeJsonCache } from "./jsonCache";
import { getNationalOfficialAlertsIstat } from "./nationalOfficialAlertsApi";

export const NATIONAL_OFFICIAL_ALERTS_CACHE_KEY = "nationalOfficialAlertsCache:v1";
export const NATIONAL_OFFICIAL_ALERTS_RECHECK_INTERVAL_MS = 5 * 60 * 1000;
export const NATIONAL_OFFICIAL_ALERTS_STORAGE_MAX_AGE_MS = 36 * 60 * 60 * 1000;

export function getNationalOfficialAlertsCacheKey(location) {
  const istatCode = getNationalOfficialAlertsIstat(location);
  return istatCode ? `${NATIONAL_OFFICIAL_ALERTS_CACHE_KEY}:${istatCode}` : "";
}

export function readNationalOfficialAlertsCache(
  location,
  { maxAgeMs = NATIONAL_OFFICIAL_ALERTS_STORAGE_MAX_AGE_MS, now, storage } = {},
) {
  const key = getNationalOfficialAlertsCacheKey(location);
  return key ? readJsonCache(key, maxAgeMs, { now, storage }) : null;
}

export function writeNationalOfficialAlertsCache(location, data, { now, storage } = {}) {
  const key = getNationalOfficialAlertsCacheKey(location);
  return key ? writeJsonCache(key, data, { now, storage }) : false;
}

export function clearNationalOfficialAlertsCache(location, { storage } = {}) {
  const key = getNationalOfficialAlertsCacheKey(location);
  return key ? removeJsonCache(key, { storage }) : false;
}
