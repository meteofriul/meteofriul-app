import {
  RADAR_RECHECK_INTERVAL_MS,
  RADAR_STORAGE_MAX_AGE_MS,
  readRadarDeviceCache,
  writeRadarDeviceCache,
} from "../../services/radarCache";
import { fetchRadarPayload } from "../../services/radarApi";

export const BULLETIN_RADAR_AUTO_REFRESH_INTERVAL_MS = 5 * 60 * 1000;
export const BULLETIN_RADAR_INITIAL_STALE_MAX_AGE_MS = RADAR_STORAGE_MAX_AGE_MS;

function hasLocationCity(location) {
  const city = typeof location === "string" ? location : location?.city;
  return Boolean(String(city || "").trim());
}

function getErrorMessage(error) {
  return error instanceof Error ? error.message : String(error || "Errore sconosciuto");
}

export function isUsableRadarPayload(payload) {
  return Boolean(
    payload?.available &&
    String(payload?.tiles?.base_url || "").trim() &&
    Array.isArray(payload?.products) &&
    payload.products.some((product) => (
      String(product?.product_type || "").trim() &&
      String(product?.time || product?.updated_at || "").trim()
    )),
  );
}

export function createBulletinRadarDataState(
  payload,
  { error = null, fromCache = false, isStale = false } = {},
) {
  if (!isUsableRadarPayload(payload)) {
    return {
      error: error ? getErrorMessage(error) : null,
      fromCache,
      isStale,
      payload: null,
      status: error ? "error" : "empty",
    };
  }

  return {
    error: error ? getErrorMessage(error) : null,
    fromCache,
    isStale,
    payload,
    status: error || isStale ? "stale" : fromCache ? "cache" : "fresh",
  };
}

export function createEmptyBulletinRadarDataState(error = null) {
  return createBulletinRadarDataState(null, { error });
}

export function readInitialBulletinRadarData(
  location,
  {
    enabled = true,
    initialStaleMaxAgeMs = BULLETIN_RADAR_INITIAL_STALE_MAX_AGE_MS,
    now = Date.now,
    radarCacheReader = readRadarDeviceCache,
    storage,
  } = {},
) {
  if (!enabled) return createEmptyBulletinRadarDataState();
  if (!hasLocationCity(location)) return null;

  const fresh = radarCacheReader(location, {
    maxAgeMs: RADAR_RECHECK_INTERVAL_MS,
    now,
    storage,
  });
  if (isUsableRadarPayload(fresh)) {
    return createBulletinRadarDataState(fresh, { fromCache: true });
  }

  const stale = radarCacheReader(location, {
    maxAgeMs: initialStaleMaxAgeMs,
    now,
    storage,
  });

  return isUsableRadarPayload(stale)
    ? createBulletinRadarDataState(stale, { fromCache: true, isStale: true })
    : null;
}

export async function loadBulletinRadarData(
  location,
  {
    cacheMaxAgeMs = RADAR_RECHECK_INTERVAL_MS,
    enabled = true,
    force = false,
    now = Date.now,
    radarCacheReader = readRadarDeviceCache,
    radarCacheWriter = writeRadarDeviceCache,
    radarFetcher = fetchRadarPayload,
    staleMaxAgeMs = BULLETIN_RADAR_INITIAL_STALE_MAX_AGE_MS,
    storage,
  } = {},
) {
  if (!enabled) return createEmptyBulletinRadarDataState();
  if (!hasLocationCity(location)) {
    return createEmptyBulletinRadarDataState(new Error("Localita radar mancante"));
  }

  const cacheOptions = { now, storage };
  const cached = radarCacheReader(location, {
    ...cacheOptions,
    maxAgeMs: cacheMaxAgeMs,
  });

  if (!force && isUsableRadarPayload(cached)) {
    return createBulletinRadarDataState(cached, { fromCache: true });
  }

  try {
    const payload = await radarFetcher(location, { force, now });
    if (!isUsableRadarPayload(payload)) {
      throw new Error("Dati radar incompleti");
    }

    radarCacheWriter(location, payload, cacheOptions);
    return createBulletinRadarDataState(payload);
  } catch (error) {
    const fallback = cached || radarCacheReader(location, {
      ...cacheOptions,
      maxAgeMs: staleMaxAgeMs,
    });

    if (isUsableRadarPayload(fallback)) {
      return createBulletinRadarDataState(fallback, {
        error,
        fromCache: true,
        isStale: !cached,
      });
    }

    return createEmptyBulletinRadarDataState(error);
  }
}
