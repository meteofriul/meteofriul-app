import { getLocationMunicipalityName } from "../../domain/geo/locationIdentity";
import { normalizeWeatherData } from "../../domain/weather/normalizedWeather";
import { readBackgroundWeatherPrefetch } from "../../services/backgroundLocationAdapter";
import { fetchLocalEvents, FULL_EVENTS_LIMIT, HOME_EVENTS_LIMIT } from "../../services/eventsApi";
import { readEventsCacheEntry, writeEventsCache } from "../../services/eventsCache";
import {
  fetchWeatherBootstrap,
  normalizeWeatherBootstrapPayload,
  readWeatherBootstrapCache,
} from "../../services/weatherApi";
import { isLocalWeatherPilot } from "../../services/localWeatherPilot";
import { usesAutonomousWeatherProvider } from "../../services/weatherProviderRuntime";
import {
  hydrateOfficialAlertsFromRegionalCache,
  reconcileRegionalOfficialAlerts,
} from "../../services/officialAlertsCache";
import {
  readWeatherDeviceCache,
  readWeatherDeviceCacheEntry,
  WEATHER_CACHE_MAX_AGE_MS,
  writeWeatherDeviceCache,
} from "../../services/weatherCache";

export const HOME_INITIAL_STALE_MAX_AGE_MS = Number.POSITIVE_INFINITY;
export const HOME_REFRESH_FALLBACK_MAX_AGE_MS = HOME_INITIAL_STALE_MAX_AGE_MS;
export const BACKGROUND_WEATHER_LOCATION_MATCH_MAX_DISTANCE_M = 5_000;

function getLocationCity(location) {
  return typeof location === "string" ? location : location?.city;
}

function hasLocationCity(location) {
  return Boolean(String(getLocationCity(location) || "").trim());
}

function getNowValue(now) {
  return typeof now === "function" ? now() : now;
}

function getNowIso({ now = Date.now, nowIso } = {}) {
  if (typeof nowIso === "function") return nowIso();

  return new Date(getNowValue(now)).toISOString();
}

function getErrorMessage(error) {
  const message = error instanceof Error ? error.message : String(error || "Errore sconosciuto");
  if (!isLocalWeatherPilot() || !(error instanceof Error)) return message;
  const cause = error.cause;
  const diagnostic = [
    error.code ? `codice=${error.code}` : "",
    cause?.name ? `causa=${cause.name}` : "",
    cause?.code ? `causa_codice=${cause.code}` : "",
    cause?.message ? `causa_messaggio=${cause.message}` : "",
  ].filter(Boolean).join(", ");
  return diagnostic ? `${message} (${diagnostic})` : message;
}

function reportLocalWeatherPilotLoadError(error) {
  if (!isLocalWeatherPilot()) return;
  const cause = error instanceof Error ? error.cause : null;
  const details = [
    error?.name,
    error?.code,
    getErrorMessage(error),
    cause?.name,
    cause?.code,
    cause?.message,
  ].filter(Boolean).join(" | ");
  console.error(`[local-weather-pilot] ${details}`);
}

function toRadians(value) {
  return Number(value) * Math.PI / 180;
}

function readCoordinate(record, key) {
  const value = record?.[key];
  if (value === null || value === undefined || value === "") return null;

  const coordinate = Number(value);
  return Number.isFinite(coordinate) ? coordinate : null;
}

function getDistanceMeters(first, second) {
  const firstLat = readCoordinate(first, "lat");
  const firstLon = readCoordinate(first, "lon");
  const secondLat = readCoordinate(second, "lat");
  const secondLon = readCoordinate(second, "lon");
  if ([firstLat, firstLon, secondLat, secondLon].some((value) => value === null)) return null;

  const deltaLat = toRadians(secondLat - firstLat);
  const deltaLon = toRadians(secondLon - firstLon);
  const lat1 = toRadians(firstLat);
  const lat2 = toRadians(secondLat);
  const haversine = Math.sin(deltaLat / 2) ** 2
    + Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) ** 2;

  return 2 * 6_371_000 * Math.asin(Math.min(1, Math.sqrt(haversine)));
}

function normalizeLocationName(value) {
  return String(value || "").trim().toLocaleLowerCase("it");
}

function matchesBackgroundWeatherLocation(location, prefetch) {
  const distanceMeters = getDistanceMeters(location, prefetch);
  if (distanceMeters !== null) {
    return distanceMeters <= BACKGROUND_WEATHER_LOCATION_MATCH_MAX_DISTANCE_M;
  }

  const activeNames = [
    getLocationMunicipalityName(location),
    location?.displayName,
    location?.locality?.name,
  ].map(normalizeLocationName).filter(Boolean);
  const prefetchCity = normalizeLocationName(prefetch?.city);

  return Boolean(prefetchCity && activeNames.includes(prefetchCity));
}

function toWeatherCachePayload(payload, { updatedAt }) {
  return {
    city: payload?.city || "",
    current: payload?.current || null,
    forecast: payload?.forecast || null,
    officialAlerts: payload?.officialAlerts || null,
    osmerAudit: payload?.osmerAudit || null,
    updatedAt,
  };
}

function hydrateWeatherAlerts(
  payload,
  { manageOfficialAlerts = true, storage, now = Date.now } = {},
) {
  if (!payload) return payload;

  if (!manageOfficialAlerts) {
    return {
      ...payload,
      officialAlerts: null,
    };
  }

  return {
    ...payload,
    officialAlerts: hydrateOfficialAlertsFromRegionalCache(payload.officialAlerts, {
      storage,
      now,
    }),
  };
}

export async function hydrateHomeWeatherFromBackgroundPrefetch(
  location,
  {
    now = Date.now,
    manageOfficialAlerts = true,
    prefetchReader = readBackgroundWeatherPrefetch,
    storage,
    weatherCacheEntryReader = readWeatherDeviceCacheEntry,
    weatherCacheWriter = writeWeatherDeviceCache,
  } = {},
) {
  try {
    if (usesAutonomousWeatherProvider({ location }) || !hasLocationCity(location)) return null;
  } catch {
    return null;
  }

  const prefetch = await prefetchReader();
  const prefetchedCurrentSource = prefetch?.payload?.current?.primary_source
    || prefetch?.payload?.current?.source?.active;
  if (
    !prefetch?.available
    || !prefetch.savedAt
    || !matchesBackgroundWeatherLocation(location, prefetch)
    || (prefetchedCurrentSource && prefetchedCurrentSource !== "open_meteo")
  ) return null;

  const currentEntry = weatherCacheEntryReader(location, {
    maxAgeMs: Number.POSITIVE_INFINITY,
    now,
    storage,
  });
  if (Number(currentEntry?.savedAt || 0) >= prefetch.savedAt) return null;

  let weatherPayload;
  try {
    weatherPayload = normalizeWeatherBootstrapPayload(prefetch.payload, {
      fallbackCity: getLocationMunicipalityName(location),
    });
  } catch {
    return null;
  }

  const updatedAt = new Date(prefetch.savedAt).toISOString();
  const cachePayload = toWeatherCachePayload({
    ...weatherPayload,
    city: getLocationMunicipalityName(location) || weatherPayload.city,
    officialAlerts: manageOfficialAlerts
      ? reconcileRegionalOfficialAlerts(
          weatherPayload.officialAlerts,
          currentEntry?.data?.officialAlerts,
          { storage, now },
        )
      : null,
  }, { updatedAt });

  weatherCacheWriter(location, cachePayload, {
    now: () => prefetch.savedAt,
    storage,
  });

  return createHomeWeatherState(cachePayload, { fromCache: true });
}

export function createHomeWeatherState(cacheData, { fromCache = false, isStale = false, error = null } = {}) {
  if (!cacheData?.current || !cacheData?.forecast) {
    return {
      status: "empty",
      city: cacheData?.city || "",
      current: null,
      rawCurrent: cacheData?.current || null,
      forecast: cacheData?.forecast || null,
      officialAlerts: cacheData?.officialAlerts || null,
      osmerAudit: cacheData?.osmerAudit || null,
      updatedAt: cacheData?.updatedAt || null,
      fromCache,
      isStale,
      error: error ? getErrorMessage(error) : null,
    };
  }

  const sourceIsStale = cacheData.current.data_quality?.status === "stale"
    || cacheData.current.cache?.status === "stale";
  return {
    status: error || sourceIsStale ? "stale" : fromCache ? "cache" : "fresh",
    city: cacheData.city || cacheData.current?.city || "",
    current: normalizeWeatherData(cacheData.current),
    rawCurrent: cacheData.current,
    forecast: cacheData.forecast,
    officialAlerts: cacheData.officialAlerts || null,
    osmerAudit: cacheData.osmerAudit || null,
    updatedAt: cacheData.updatedAt || null,
    fromCache,
    isStale: isStale || sourceIsStale,
    error: error ? getErrorMessage(error) : null,
  };
}

export function createEmptyHomeWeatherState(error = null) {
  return createHomeWeatherState(null, { error });
}

export function createHomeEventsState(
  payload,
  {
    fromCache = false,
    loadedLimit = HOME_EVENTS_LIMIT,
    catalogHealth = payload?.catalogHealth || null,
    cacheStatus = catalogHealth?.status === "degraded" ? "degraded" : null,
    contractVersion = payload?.contractVersion || null,
    isRefreshing = false,
    isPartial = false,
    retry = 0,
    shouldRetry = false,
    error = null,
  } = {},
) {
  const events = Array.isArray(payload?.events) ? payload.events : [];

  return {
    status: error ? fromCache ? "stale" : "error"
      : catalogHealth?.status === "degraded" ? "degraded" : fromCache ? "cache" : "fresh",
    items: events,
    total: Number(payload?.total || events.length),
    loadedLimit,
    cacheStatus,
    contractVersion,
    catalogHealth,
    isDegraded: catalogHealth?.status === "degraded",
    isRefreshing,
    isPartial,
    retry,
    shouldRetry,
    fromCache,
    error: error ? getErrorMessage(error) : null,
  };
}

export function createEmptyHomeEventsState(error = null) {
  return createHomeEventsState(null, {
    loadedLimit: 0,
    error,
  });
}

export function readInitialHomeData(
  location,
  {
    now = Date.now,
    initialStaleMaxAgeMs = HOME_INITIAL_STALE_MAX_AGE_MS,
    manageOfficialAlerts = true,
    eventsLocation = location,
    storage,
    bootstrapCacheReader = readWeatherBootstrapCache,
    weatherCacheReader = readWeatherDeviceCache,
    eventsCacheReader = readEventsCacheEntry,
  } = {},
) {
  if (!hasLocationCity(location)) return null;

  const cacheOptions = { storage, now };
  const autonomousWeather = bootstrapCacheReader(location, cacheOptions);
  const freshWeather = weatherCacheReader(location, { ...cacheOptions, maxAgeMs: WEATHER_CACHE_MAX_AGE_MS });
  const staleWeather = freshWeather
    ? null
    : weatherCacheReader(location, { ...cacheOptions, maxAgeMs: initialStaleMaxAgeMs });
  const weather = autonomousWeather || freshWeather || staleWeather;
  const hydratedWeather = hydrateWeatherAlerts(weather, {
    ...cacheOptions,
    manageOfficialAlerts,
  });
  const eventsEntry = eventsCacheReader(eventsLocation, HOME_EVENTS_LIMIT, cacheOptions);

  if (!hydratedWeather && !eventsEntry?.data) return null;

  return {
    editorialLocation: eventsLocation,
    location,
    weather: hydratedWeather
      ? createHomeWeatherState(hydratedWeather, {
          fromCache: true,
          isStale: false,
        })
      : createEmptyHomeWeatherState(),
    events: eventsEntry?.data
      ? createHomeEventsState(eventsEntry.data, {
          contractVersion: eventsEntry.data.contractVersion,
          fromCache: true,
          loadedLimit: eventsEntry.limit,
        })
      : createEmptyHomeEventsState(),
    ok: true,
  };
}

export async function loadHomeWeather(
  location,
  {
    force = false,
    manageOfficialAlerts = true,
    storage,
    now = Date.now,
    nowIso,
    cacheMaxAgeMs = WEATHER_CACHE_MAX_AGE_MS,
    refreshFallbackMaxAgeMs = HOME_REFRESH_FALLBACK_MAX_AGE_MS,
    weatherCacheReader = readWeatherDeviceCache,
    weatherCacheWriter = writeWeatherDeviceCache,
    weatherFetcher = fetchWeatherBootstrap,
    deferCams = false,
    retryUnavailableCams = false,
    onCamsUpdate,
    onCamsFailure,
  } = {},
) {
  if (!hasLocationCity(location)) {
    return createEmptyHomeWeatherState(new Error("Localita meteo mancante"));
  }

  const cacheOptions = { storage, now };
  const cached = weatherCacheReader(location, { ...cacheOptions, maxAgeMs: cacheMaxAgeMs });
  const fallbackCache = cached || weatherCacheReader(location, {
    ...cacheOptions,
    maxAgeMs: refreshFallbackMaxAgeMs,
  });

  const cachedCamsPending = cached?.current?.data_quality?.cams_status === "pending";
  const legacyAirCache = cached?.current?.primary_source === "icon2i_local_pilot"
    && !Object.hasOwn(cached.current, "air_quality_data");
  if (!force && cached && !legacyAirCache && !(deferCams && cachedCamsPending)) {
    return createHomeWeatherState(hydrateWeatherAlerts(cached, {
      ...cacheOptions,
      manageOfficialAlerts,
    }), {
      fromCache: true,
    });
  }

  const commitWeatherPayload = (weatherPayload) => {
    const updatedAt = getNowIso({ now, nowIso });
    const cachePayload = toWeatherCachePayload({
      ...weatherPayload,
      officialAlerts: manageOfficialAlerts
        ? reconcileRegionalOfficialAlerts(
            weatherPayload.officialAlerts,
            fallbackCache?.officialAlerts,
            cacheOptions,
          )
        : null,
    }, { updatedAt });

    weatherCacheWriter(location, cachePayload, cacheOptions);
    return createHomeWeatherState(cachePayload);
  };
  let latestCamsPayload = null;
  let latestCamsWeather = null;

  try {
    const fetchOptions = { force, now, storage };
    if (retryUnavailableCams) fetchOptions.retryUnavailableCams = true;
    if (deferCams) {
      fetchOptions.deferCams = true;
      fetchOptions.onCamsFailure = (error) => {
        reportLocalWeatherPilotLoadError(error);
        return typeof onCamsFailure === "function" ? onCamsFailure(error) : undefined;
      };
      fetchOptions.onCamsUpdate = (weatherPayload, lifecycle) => {
        try {
          const weather = commitWeatherPayload(weatherPayload);
          latestCamsPayload = weatherPayload;
          latestCamsWeather = weather;
          return typeof onCamsUpdate === "function"
            ? onCamsUpdate(weather, lifecycle)
            : undefined;
        } catch {
          return undefined;
        }
      };
    }
    const weatherPayload = await weatherFetcher(location, fetchOptions);
    const weather = commitWeatherPayload(weatherPayload);
    if (latestCamsPayload) {
      commitWeatherPayload(latestCamsPayload);
      return latestCamsWeather;
    }
    return weather;
  } catch (error) {
    reportLocalWeatherPilotLoadError(error);
    if (fallbackCache) {
      return createHomeWeatherState(hydrateWeatherAlerts(fallbackCache, {
        ...cacheOptions,
        manageOfficialAlerts,
      }), {
        fromCache: true,
        isStale: !cached,
        error,
      });
    }

    return createEmptyHomeWeatherState(error);
  }
}

export async function loadHomeEvents(
  location,
  {
    storage,
    now = Date.now,
    limit = HOME_EVENTS_LIMIT,
    retry = 0,
    eventsCacheReader = readEventsCacheEntry,
    eventsCacheWriter = writeEventsCache,
    eventsFetcher = fetchLocalEvents,
  } = {},
) {
  if (!hasLocationCity(location)) {
    return createEmptyHomeEventsState(new Error("Localita eventi mancante"));
  }

  const cacheOptions = { storage, now };
  const cachedEntry = eventsCacheReader(location, limit, cacheOptions);

  try {
    const eventsPayload = await eventsFetcher(location, { limit, retry });
    const cached = cachedEntry?.data || null;
    const contractChanged = Boolean(eventsPayload.contractVersion)
      && eventsPayload.contractVersion !== (cached?.contractVersion || null);

    if (
      (eventsPayload.isRefreshing || eventsPayload.isPartial)
      && cached
      && (!contractChanged || !eventsPayload.events.length)
    ) {
      return createHomeEventsState(cached, {
        cacheStatus: eventsPayload.cacheStatus,
        contractVersion: cached.contractVersion,
        fromCache: true,
        isPartial: eventsPayload.isPartial,
        isRefreshing: eventsPayload.isRefreshing,
        loadedLimit: cachedEntry.limit,
        retry,
        shouldRetry: eventsPayload.shouldRetry,
      });
    }

    if (
      (eventsPayload.isRefreshing || eventsPayload.isPartial)
      && contractChanged
      && eventsPayload.events.length
    ) {
      eventsCacheWriter(location, eventsPayload.events, {
        ...cacheOptions,
        contractVersion: eventsPayload.contractVersion,
        catalogHealth: eventsPayload.catalogHealth,
        limit: FULL_EVENTS_LIMIT,
      });
    }

    if (!eventsPayload.isRefreshing && !eventsPayload.isPartial) {
      eventsCacheWriter(location, eventsPayload.events, {
        ...cacheOptions,
        contractVersion: eventsPayload.contractVersion,
        catalogHealth: eventsPayload.catalogHealth,
        limit: FULL_EVENTS_LIMIT,
      });
    }

    return createHomeEventsState(eventsPayload, {
      loadedLimit: FULL_EVENTS_LIMIT,
      cacheStatus: eventsPayload.cacheStatus,
      contractVersion: eventsPayload.contractVersion,
      isRefreshing: eventsPayload.isRefreshing,
      isPartial: eventsPayload.isPartial,
      retry,
      shouldRetry: eventsPayload.shouldRetry,
    });
  } catch (error) {
    if (cachedEntry?.data) {
      return createHomeEventsState(cachedEntry.data, {
        fromCache: true,
        loadedLimit: cachedEntry.limit,
        error,
      });
    }

    return createEmptyHomeEventsState(error);
  }
}

export function mergeHomeDataState(current, location, patch = {}) {
  const nextState = {
    ...(current || {}),
    ...patch,
    location,
  };

  return {
    ...nextState,
    ok: !nextState.weather?.error && !nextState.events?.error,
  };
}

export async function loadHomeData(location, options = {}) {
  const eventsLocation = options.eventsLocation || location;
  const [weather, events] = await Promise.all([
    loadHomeWeather(location, options.weather || options),
    loadHomeEvents(eventsLocation, options.events || options),
  ]);

  return {
    editorialLocation: eventsLocation,
    location,
    weather,
    events,
    ok: !weather.error && !events.error,
  };
}
