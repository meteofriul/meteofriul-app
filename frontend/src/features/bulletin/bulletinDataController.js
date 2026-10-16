import { isUsableOfficialBulletin } from "../../domain/weather/officialBulletin";
import {
  BULLETIN_CACHE_RECHECK_INTERVAL_MS,
  BULLETIN_CACHE_STORAGE_MAX_AGE_MS,
  readBulletinDeviceCache,
  writeBulletinDeviceCache,
} from "../../services/bulletinCache";
import { fetchBulletinPayload } from "../../services/bulletinApi";
import {
  hydrateOfficialAlertsFromRegionalCache,
  reconcileRegionalOfficialAlerts,
} from "../../services/officialAlertsCache";

export { resolveOfficialAlerts } from "../../services/officialAlertsCache";

export const BULLETIN_INITIAL_STALE_MAX_AGE_MS = BULLETIN_CACHE_STORAGE_MAX_AGE_MS;
export const BULLETIN_REFRESH_FALLBACK_MAX_AGE_MS = BULLETIN_INITIAL_STALE_MAX_AGE_MS;

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

function toBulletinCachePayload(payload, { updatedAt }) {
  return {
    city: payload?.city || "",
    forecast: payload?.forecast || null,
    officialAlerts: payload?.officialAlerts || null,
    osmerAudit: payload?.osmerAudit || null,
    updatedAt,
  };
}

function isUsableBulletinCache(payload, { now = Date.now } = {}) {
  return Boolean(payload?.forecast && isUsableOfficialBulletin(payload, { now }));
}

export function createBulletinDataState(payload, { error = null, fromCache = false, isStale = false } = {}) {
  if (!payload?.forecast) {
    return {
      city: payload?.city || "",
      error: error ? getErrorMessage(error) : null,
      fromCache,
      forecast: null,
      isStale,
      officialAlerts: payload?.officialAlerts || null,
      osmerAudit: payload?.osmerAudit || null,
      raw: payload?.raw || payload || null,
      status: error ? "error" : "empty",
      updatedAt: payload?.updatedAt || null,
    };
  }

  return {
    city: payload.city || "",
    error: error ? getErrorMessage(error) : null,
    fromCache,
    forecast: payload.forecast,
    isStale,
    officialAlerts: payload.officialAlerts || null,
    osmerAudit: payload.osmerAudit || null,
    raw: payload.raw || payload,
    status: error ? "stale" : fromCache ? "cache" : "fresh",
    updatedAt: payload.updatedAt || null,
  };
}

export function createEmptyBulletinDataState(error = null) {
  return createBulletinDataState(null, { error });
}

export function readCachedBulletinData(
  location,
  {
    cacheMaxAgeMs = Infinity,
    includeAlerts = true,
    isStale = false,
    now = Date.now,
    storage,
    bulletinCacheReader = readBulletinDeviceCache,
  } = {},
) {
  if (!hasLocationCity(location)) return null;

  const cached = bulletinCacheReader(location, {
    maxAgeMs: cacheMaxAgeMs,
    now,
    storage,
  });
  const hydrated = cached
    ? {
      ...cached,
      officialAlerts: includeAlerts === false
        ? null
        : hydrateOfficialAlertsFromRegionalCache(cached.officialAlerts, {
          storage,
          now,
        }),
    }
    : null;

  if (!isUsableBulletinCache(hydrated, { now })) return null;

  return createBulletinDataState(hydrated, {
    fromCache: true,
    isStale,
  });
}

export function readInitialBulletinData(location, options = {}) {
  const {
    initialStaleMaxAgeMs = BULLETIN_INITIAL_STALE_MAX_AGE_MS,
    ...cacheOptions
  } = options;

  return (
    readCachedBulletinData(location, {
      ...cacheOptions,
      cacheMaxAgeMs: BULLETIN_CACHE_RECHECK_INTERVAL_MS,
      isStale: false,
    }) ||
    readCachedBulletinData(location, {
      ...cacheOptions,
      cacheMaxAgeMs: initialStaleMaxAgeMs,
      isStale: true,
    })
  );
}

export async function loadBulletinData(
  location,
  {
    bulletinFetcher = fetchBulletinPayload,
    cacheMaxAgeMs = BULLETIN_CACHE_RECHECK_INTERVAL_MS,
    force = false,
    includeAlerts,
    now = Date.now,
    nowIso,
    refreshFallbackMaxAgeMs = BULLETIN_REFRESH_FALLBACK_MAX_AGE_MS,
    storage,
    bulletinCacheReader = readBulletinDeviceCache,
    bulletinCacheWriter = writeBulletinDeviceCache,
  } = {},
) {
  if (!hasLocationCity(location)) {
    return createEmptyBulletinDataState(new Error("Localita bollettino mancante"));
  }

  const cacheOptions = { storage, now };
  const cached = bulletinCacheReader(location, { ...cacheOptions, maxAgeMs: cacheMaxAgeMs });
  const fallbackCache = cached || bulletinCacheReader(location, {
    ...cacheOptions,
    maxAgeMs: refreshFallbackMaxAgeMs,
  });
  const hydrateCachedPayload = (payload) => (
    payload
      ? {
        ...payload,
        officialAlerts: includeAlerts === false
          ? null
          : hydrateOfficialAlertsFromRegionalCache(payload.officialAlerts, {
            storage,
            now,
          }),
      }
      : null
  );

  if (!force && isUsableBulletinCache(cached, { now })) {
    return createBulletinDataState(hydrateCachedPayload(cached), { fromCache: true });
  }

  try {
    const fetchOptions = {
      force,
      now,
    };
    if (typeof includeAlerts === "boolean") fetchOptions.includeAlerts = includeAlerts;

    const payload = await bulletinFetcher(location, fetchOptions);
    const updatedAt = getNowIso({ now, nowIso });
    const cachePayload = toBulletinCachePayload({
      ...payload,
      officialAlerts: includeAlerts === false
        ? null
        : reconcileRegionalOfficialAlerts(
            payload?.officialAlerts,
            fallbackCache?.officialAlerts,
            { storage, now },
          ),
      osmerAudit: payload?.osmerAudit || fallbackCache?.osmerAudit || null,
    }, { updatedAt });

    if (!isUsableBulletinCache(cachePayload, { now })) {
      throw new Error("Dati ufficiali OSMER mancanti o fuori validita");
    }

    bulletinCacheWriter(location, cachePayload, cacheOptions);

    return createBulletinDataState(cachePayload);
  } catch (error) {
    if (isUsableBulletinCache(fallbackCache, { now })) {
      return createBulletinDataState(hydrateCachedPayload(fallbackCache), {
        fromCache: true,
        isStale: !cached,
        error,
      });
    }

    return createEmptyBulletinDataState(error);
  }
}
