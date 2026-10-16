import { fetchLocalEvents, FULL_EVENTS_LIMIT, HOME_EVENTS_LIMIT } from "../../services/eventsApi";
import { readEventsCacheEntry, writeEventsCache } from "../../services/eventsCache";
import { isLocalWeatherPilot } from "../../services/localWeatherPilot";

function getLocationCity(location) {
  return typeof location === "string" ? location : location?.city;
}

function hasLocationCity(location) {
  return Boolean(String(getLocationCity(location) || "").trim());
}

function getErrorMessage(error) {
  return error instanceof Error ? error.message : String(error || "Errore sconosciuto");
}

function readBestEventsCache(location, options = {}) {
  return (
    readEventsCacheEntry(location, FULL_EVENTS_LIMIT, options) ||
    readEventsCacheEntry(location, HOME_EVENTS_LIMIT, options)
  );
}

export function createEventsDataState(
  payload,
  {
    cacheStatus = null,
    contractVersion = null,
    error = null,
    fromCache = false,
    isPartial = false,
    isRefreshing = false,
    loadedLimit = FULL_EVENTS_LIMIT,
    retry = 0,
    shouldRetry = false,
  } = {},
) {
  const events = Array.isArray(payload?.events) ? payload.events : [];

  return {
    cacheStatus,
    contractVersion,
    error: error ? getErrorMessage(error) : null,
    fromCache,
    isPartial,
    isRefreshing,
    items: events,
    loadedLimit,
    retry,
    shouldRetry,
    status: error
      ? fromCache
        ? "stale"
        : "error"
      : isRefreshing
        ? "refreshing"
        : isPartial
          ? "partial"
          : fromCache
            ? "cache"
            : "fresh",
    total: Number(payload?.total || events.length),
  };
}

export function createEmptyEventsDataState(error = null) {
  return createEventsDataState(null, {
    error,
    loadedLimit: 0,
  });
}

export function createLoadingEventsDataState() {
  return createEventsDataState(null, {
    isRefreshing: true,
    loadedLimit: 0,
    shouldRetry: false,
  });
}

export function readInitialEventsData(
  location,
  {
    eventsCacheReader = readBestEventsCache,
    now = Date.now,
    storage,
  } = {},
) {
  if (!hasLocationCity(location)) return null;

  const cachedEntry = eventsCacheReader(location, { now, storage });
  if (!cachedEntry?.data) return null;

  return createEventsDataState(cachedEntry.data, {
    contractVersion: cachedEntry.data.contractVersion,
    fromCache: true,
    loadedLimit: cachedEntry.limit || FULL_EVENTS_LIMIT,
  });
}

export async function loadEventsData(
  location,
  {
    eventsCacheReader = readBestEventsCache,
    eventsCacheWriter = writeEventsCache,
    eventsFetcher = fetchLocalEvents,
    pilot = isLocalWeatherPilot(),
    now = Date.now,
    retry = 0,
    storage,
  } = {},
) {
  if (!hasLocationCity(location)) {
    return createEmptyEventsDataState(new Error("Localita eventi mancante"));
  }

  const cacheOptions = { now, storage };
  const cachedEntry = eventsCacheReader(location, cacheOptions);
  const cached = cachedEntry?.data || null;

  try {
    const payload = await eventsFetcher(location, {
      limit: FULL_EVENTS_LIMIT,
      retry,
    });
    const isPending = payload.isRefreshing || payload.isPartial;
    const contractChanged = Boolean(payload.contractVersion)
      && payload.contractVersion !== (cached?.contractVersion || null);

    if (pilot && cached?.events?.length && payload.cacheStatus === "source_unavailable") {
      return createEventsDataState(cached, {
        cacheStatus: payload.cacheStatus,
        contractVersion: cached.contractVersion,
        error: new Error("Fonti temporaneamente non disponibili; mostro i dati salvati."),
        fromCache: true,
        loadedLimit: cachedEntry.limit || FULL_EVENTS_LIMIT,
      });
    }
    // Partial responses can grow as sources complete. Do not freeze the
    // pilot forever on its first small cached batch, or blank it on failure.
    const improvedPartial = pilot && payload.isPartial && !contractChanged
      && payload.events.length > (cached?.events?.length || 0);

    if (isPending && cached && !improvedPartial && (!contractChanged || !payload.events.length)) {
      return createEventsDataState(cached, {
        cacheStatus: payload.cacheStatus,
        contractVersion: cached.contractVersion,
        fromCache: true,
        isPartial: payload.isPartial,
        isRefreshing: payload.isRefreshing,
        loadedLimit: cachedEntry.limit || FULL_EVENTS_LIMIT,
        retry,
        shouldRetry: payload.shouldRetry,
      });
    }

    if (isPending && (contractChanged || improvedPartial) && payload.events.length) {
      eventsCacheWriter(location, payload.events, {
        ...cacheOptions,
        contractVersion: payload.contractVersion,
        limit: FULL_EVENTS_LIMIT,
      });
    }

    if (!isPending) {
      eventsCacheWriter(location, payload.events, {
        ...cacheOptions,
        contractVersion: payload.contractVersion,
        limit: FULL_EVENTS_LIMIT,
      });
    }

    return createEventsDataState(payload, {
      cacheStatus: payload.cacheStatus,
      contractVersion: payload.contractVersion,
      isPartial: payload.isPartial,
      isRefreshing: payload.isRefreshing,
      loadedLimit: FULL_EVENTS_LIMIT,
      retry,
      shouldRetry: payload.shouldRetry,
    });
  } catch (error) {
    if (cached) {
      return createEventsDataState(cached, {
        error,
        fromCache: true,
        loadedLimit: cachedEntry.limit || FULL_EVENTS_LIMIT,
      });
    }

    return createEmptyEventsDataState(error);
  }
}
