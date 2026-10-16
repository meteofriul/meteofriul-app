import {
  getLegacyLocationCacheKey,
  getLocationCacheKey,
} from "../domain/geo/locationCacheKey";
import { isFvgLocation } from "../domain/scope/productScope";
import { isLocalWeatherPilot } from "./localWeatherPilot";
import { FULL_EVENTS_LIMIT, getEventsRequestLimit, HOME_EVENTS_LIMIT } from "./eventsApi";
import { readJsonCacheEntry, removeJsonCache, writeJsonCache } from "./jsonCache";

export const EVENTS_CACHE_PREFIX = "eventsCache:v12";
export const EVENTS_CACHE_SCHEMA_VERSION = "canonical-events-v2";
export const EVENTS_DEVICE_CACHE_MAX_AGE_MS = 48 * 60 * 60 * 1000;

export function getEventsLocationKey(locationOrCity) {
  if (locationOrCity && typeof locationOrCity === "object") {
    return getLocationCacheKey(locationOrCity);
  }

  return getLocationCacheKey({ city: locationOrCity });
}

export function getEventsCacheKey(locationOrCity, limit) {
  return `${EVENTS_CACHE_PREFIX}${isLocalWeatherPilot() ? ":pilot-programmes-v2" : ""}:${getEventsLocationKey(locationOrCity)}:${limit}`;
}

function getLegacyEventsCacheKey(locationOrCity, limit) {
  if (
    !locationOrCity
    || typeof locationOrCity !== "object"
    || !isFvgLocation(locationOrCity)
  ) return "";

  const currentLocationKey = getEventsLocationKey(locationOrCity);
  const legacyLocationKey = getLegacyLocationCacheKey(locationOrCity);
  if (!legacyLocationKey || legacyLocationKey === currentLocationKey) return "";
  return `${EVENTS_CACHE_PREFIX}${isLocalWeatherPilot() ? ":pilot-programmes-v2" : ""}:${legacyLocationKey}:${limit}`;
}

export function isUsableEventsCache(value) {
  return value?.schemaVersion === EVENTS_CACHE_SCHEMA_VERSION && Array.isArray(value.events);
}

export function createEventsCachePayload(events, contractVersion = null) {
  const normalizedEvents = Array.isArray(events) ? events : [];

  return {
    schemaVersion: EVENTS_CACHE_SCHEMA_VERSION,
    contractVersion: String(contractVersion || "").trim() || null,
    events: normalizedEvents,
    total: normalizedEvents.length,
  };
}

function readEventsCacheEntryAtLimit(locationOrCity, limit, { storage, now } = {}) {
  const options = { removeExpired: true, storage, now };
  const currentKey = getEventsCacheKey(locationOrCity, limit);
  const current = readJsonCacheEntry(
    currentKey,
    EVENTS_DEVICE_CACHE_MAX_AGE_MS,
    options,
  );
  if (current && isUsableEventsCache(current.data)) return current;

  const legacyKey = getLegacyEventsCacheKey(locationOrCity, limit);
  if (!legacyKey) return null;
  const legacy = readJsonCacheEntry(
    legacyKey,
    EVENTS_DEVICE_CACHE_MAX_AGE_MS,
    options,
  );
  if (!legacy || !isUsableEventsCache(legacy.data)) return null;

  const promoted = writeJsonCache(currentKey, legacy.data, {
    storage,
    now: () => legacy.savedAt,
  });
  if (promoted) removeJsonCache(legacyKey, { storage });
  return legacy;
}

export function readEventsCache(locationOrCity, { storage, now } = {}) {
  const fullCached = readEventsCacheEntryAtLimit(
    locationOrCity,
    FULL_EVENTS_LIMIT,
    { storage, now },
  )?.data;

  if (isUsableEventsCache(fullCached)) return fullCached;

  const homeCached = readEventsCacheEntryAtLimit(
    locationOrCity,
    HOME_EVENTS_LIMIT,
    { storage, now },
  )?.data;

  return isUsableEventsCache(homeCached) ? homeCached : null;
}

export function getEventsCachedLimit(locationOrCity, { storage, now } = {}) {
  const fullCached = readEventsCacheEntryAtLimit(
    locationOrCity,
    FULL_EVENTS_LIMIT,
    { storage, now },
  )?.data;

  if (isUsableEventsCache(fullCached) && fullCached.events.length) return FULL_EVENTS_LIMIT;

  const homeCached = readEventsCacheEntryAtLimit(
    locationOrCity,
    HOME_EVENTS_LIMIT,
    { storage, now },
  )?.data;

  return isUsableEventsCache(homeCached) && homeCached.events.length ? HOME_EVENTS_LIMIT : 0;
}

export function readEventsCacheEntry(locationOrCity, limit, { storage, now } = {}) {
  const requestLimit = getEventsRequestLimit(limit);
  const fullEntry = readEventsCacheEntryAtLimit(
    locationOrCity,
    requestLimit,
    { storage, now },
  );

  if (fullEntry && isUsableEventsCache(fullEntry.data)) {
    return {
      ...fullEntry,
      limit: requestLimit,
    };
  }

  if (requestLimit !== FULL_EVENTS_LIMIT) return null;

  const homeEntry = readEventsCacheEntryAtLimit(
    locationOrCity,
    HOME_EVENTS_LIMIT,
    { storage, now },
  );

  return homeEntry && isUsableEventsCache(homeEntry.data)
    ? {
        ...homeEntry,
        limit: HOME_EVENTS_LIMIT,
      }
    : null;
}

export function writeEventsCache(
  locationOrCity,
  events,
  { contractVersion = null, limit = FULL_EVENTS_LIMIT, storage, now } = {},
) {
  const written = writeJsonCache(
    getEventsCacheKey(locationOrCity, limit),
    createEventsCachePayload(events, contractVersion),
    { storage, now },
  );
  const legacyKey = getLegacyEventsCacheKey(locationOrCity, limit);
  if (written && legacyKey) removeJsonCache(legacyKey, { storage });
  return written;
}

export function clearEventsCache(locationOrCity, { storage } = {}) {
  const removedFull = removeJsonCache(getEventsCacheKey(locationOrCity, FULL_EVENTS_LIMIT), { storage });
  const removedHome = removeJsonCache(getEventsCacheKey(locationOrCity, HOME_EVENTS_LIMIT), { storage });
  const legacyFullKey = getLegacyEventsCacheKey(locationOrCity, FULL_EVENTS_LIMIT);
  const legacyHomeKey = getLegacyEventsCacheKey(locationOrCity, HOME_EVENTS_LIMIT);
  const removedLegacyFull = legacyFullKey
    ? removeJsonCache(legacyFullKey, { storage })
    : false;
  const removedLegacyHome = legacyHomeKey
    ? removeJsonCache(legacyHomeKey, { storage })
    : false;

  return removedFull || removedHome || removedLegacyFull || removedLegacyHome;
}
