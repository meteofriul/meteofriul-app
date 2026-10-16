import { fetchCommunityReports, fetchLiveWebcams } from "../../services/liveApi";
import { getLocalCommunityReadScope, isLocalCommunityPilot } from "../../services/localCommunityPilot";
import {
  LIVE_COMMUNITY_RECHECK_MS,
  LIVE_WEBCAM_RECHECK_MS,
  LIVE_WEBCAM_STALE_MS,
  readLiveCommunityCacheEntry,
  readLiveWebcamCacheEntry,
  writeLiveCommunityCache,
  writeLiveWebcamCache,
} from "../../services/liveCache";

export const LIVE_AUTO_REFRESH_INTERVAL_MS = LIVE_COMMUNITY_RECHECK_MS;

const inFlightCommunityLoads = new WeakMap();

function loadCommunityPayload(fetcher, communityLocation) {
  const scope = getLocalCommunityReadScope(communityLocation);
  const requests = inFlightCommunityLoads.get(fetcher) || new Map();
  inFlightCommunityLoads.set(fetcher, requests);
  const pending = requests.get(scope);
  if (pending) return pending;

  const request = Promise.resolve().then(() => scope ? fetcher({ communityLocation }) : fetcher());
  requests.set(scope, request);
  const clear = () => {
    if (requests.get(scope) === request) {
      requests.delete(scope);
    }
  };
  request.then(clear, clear);
  return request;
}

function getErrorMessage(error) {
  return error instanceof Error ? error.message : String(error || "Errore sconosciuto");
}

export function isUsableLiveWebcamPayload(payload) {
  return Boolean(payload?.ok && Array.isArray(payload?.webcams) && payload.webcams.length > 0);
}

export function isUsableCommunityPayload(payload) {
  return Boolean(payload && Array.isArray(payload.reports) && Array.isArray(payload.map_groups));
}

function createSectionState(
  payload,
  {
    ageMs = 0,
    error = null,
    fromCache = false,
    isStale = false,
    status = null,
  } = {},
) {
  return {
    ageMs,
    error: error ? getErrorMessage(error) : null,
    fromCache,
    isStale,
    payload: payload || null,
    status: status || (
      error
        ? payload
          ? "stale"
          : "error"
        : isStale
          ? "stale"
          : fromCache
            ? "cache"
            : payload
              ? "fresh"
              : "loading"
    ),
  };
}

export function createEmptyLiveDataState() {
  return {
    community: createSectionState(null),
    error: null,
    items: [],
    ok: true,
    status: "loading",
    webcams: createSectionState(null),
  };
}

function createLiveDataState({ community, webcams }) {
  const items = webcams?.payload?.webcams || [];
  const hasData = items.length > 0 || Boolean(community?.payload);
  const hasFatalError = !hasData && webcams?.status === "error" && community?.status === "error";

  return {
    community,
    error: hasFatalError
      ? [webcams.error, community.error].filter(Boolean).join(" | ") || "Dati del territorio non disponibili"
      : null,
    items,
    ok: !hasFatalError,
    status: hasFatalError
      ? "error"
      : webcams?.status === "loading" || community?.status === "loading"
        ? "loading"
        : webcams?.status === "stale" || community?.status === "stale"
          ? "stale"
          : "ready",
    webcams,
  };
}

function readCachedSections({
  communityLocation,
  communityEnabled = true,
  webcamsEnabled = true,
  now = Date.now,
  storage,
} = {}) {
  const webcamEntry = webcamsEnabled
    ? readLiveWebcamCacheEntry({ now, storage })
    : null;
  const communityEntry = communityEnabled
    ? readLiveCommunityCacheEntry({ communityLocation, now, storage })
    : null;

  return {
    community: !communityEnabled
      ? createSectionState(
          { map_groups: [], reports: [] },
          { status: "fresh" },
        )
      : communityEntry && isUsableCommunityPayload(communityEntry.data)
        ? createSectionState(communityEntry.data, {
            ageMs: communityEntry.age,
            fromCache: true,
          })
        : createSectionState(null),
    webcamEntry,
    webcams: !webcamsEnabled
      ? createSectionState(null, { status: "unsupported" })
      : webcamEntry && isUsableLiveWebcamPayload(webcamEntry.data)
        ? createSectionState(webcamEntry.data, {
            ageMs: webcamEntry.age,
            fromCache: true,
            isStale: webcamEntry.age > LIVE_WEBCAM_STALE_MS,
          })
        : createSectionState(null),
    communityEntry,
  };
}

export function readInitialLiveData(options = {}) {
  const cached = readCachedSections(options);
  if (!cached.webcams.payload && !cached.community.payload) return null;

  return createLiveDataState(cached);
}

function resolveLoadedSection({
  cached,
  error,
  payload,
  staleAfterMs = Number.POSITIVE_INFINITY,
  validator,
  writer,
  writerOptions,
}) {
  if (validator(payload)) {
    writer(payload, writerOptions);
    return createSectionState(payload);
  }

  const failure = error || new Error("Payload live incompleto");
  if (cached?.payload) {
    return createSectionState(cached.payload, {
      ageMs: cached.ageMs,
      error: failure,
      fromCache: true,
      isStale: cached.isStale || cached.ageMs > staleAfterMs,
    });
  }

  return createSectionState(null, { error: failure });
}

export async function loadLiveData({
  communityLocation,
  communityEnabled = true,
  communityFetcher = fetchCommunityReports,
  force = false,
  forceCommunity = false,
  forceWebcams = false,
  now = Date.now,
  onUpdate,
  storage,
  webcamFetcher = fetchLiveWebcams,
  webcamsEnabled = true,
} = {}) {
  const cached = readCachedSections({ communityLocation, communityEnabled, webcamsEnabled, now, storage });
  const hasFreshWebcams = cached.webcams.payload && cached.webcams.ageMs <= LIVE_WEBCAM_RECHECK_MS;
  const hasFreshCommunity = cached.community.payload && cached.community.ageMs <= LIVE_COMMUNITY_RECHECK_MS;
  const shouldFetchWebcams = webcamsEnabled
    && (force || forceWebcams || !hasFreshWebcams);
  const shouldFetchCommunity = communityEnabled
    && (force || forceCommunity || !hasFreshCommunity);

  if (!shouldFetchWebcams && !shouldFetchCommunity) {
    return createLiveDataState(cached);
  }

  const writerOptions = { now, storage, ...(isLocalCommunityPilot() ? { communityLocation } : {}) };
  const sections = { community: cached.community, webcams: cached.webcams };
  const loadSection = async (key, fetcher, options) => {
    let payload;
    let error;
    try {
      payload = await fetcher();
    } catch (failure) {
      error = failure;
    }
    sections[key] = resolveLoadedSection({
      cached: cached[key],
      error,
      payload,
      ...options,
      writerOptions,
    });
    // Each source can become usable independently. The returned promise still
    // settles only after both sources, preserving manual-refresh completion.
    try {
      onUpdate?.(createLiveDataState(sections));
    } catch {
      // A UI observer must not end the refresh while another source is loading.
    }
  };
  await Promise.all([
    shouldFetchWebcams ? loadSection("webcams", webcamFetcher, {
      staleAfterMs: LIVE_WEBCAM_STALE_MS,
      validator: isUsableLiveWebcamPayload,
      writer: writeLiveWebcamCache,
    }) : null,
    shouldFetchCommunity ? loadSection("community", () => loadCommunityPayload(communityFetcher, communityLocation), {
      validator: isUsableCommunityPayload,
      writer: writeLiveCommunityCache,
    }) : null,
  ]);

  return createLiveDataState(sections);
}
