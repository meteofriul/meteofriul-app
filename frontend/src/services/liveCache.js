import { readJsonCacheEntry, removeJsonCache, writeJsonCache } from "./jsonCache";
import { communityStorageKey, getLocalCommunityReadScope, isLocalCommunityPilot } from "./localCommunityPilot";

export const LIVE_WEBCAM_CACHE_KEY = "liveWebcamManifest:v1";
export const LIVE_COMMUNITY_CACHE_KEY = "liveCommunityReports:v1";
export const LIVE_WEBCAM_RECHECK_MS = 10 * 60 * 1000;
export const LIVE_WEBCAM_STALE_MS = 36 * 60 * 60 * 1000;
export const LIVE_WEBCAM_STORAGE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
export const LIVE_COMMUNITY_RECHECK_MS = 5 * 60 * 1000;
export const LIVE_COMMUNITY_STORAGE_MAX_AGE_MS = 65 * 60 * 1000;

function communityCacheKey(location) {
  if (!isLocalCommunityPilot()) return LIVE_COMMUNITY_CACHE_KEY;
  return `${communityStorageKey(LIVE_COMMUNITY_CACHE_KEY)}:${getLocalCommunityReadScope(location)}`;
}

export function readLiveWebcamCacheEntry({
  maxAgeMs = LIVE_WEBCAM_STORAGE_MAX_AGE_MS,
  now,
  storage,
} = {}) {
  return readJsonCacheEntry(LIVE_WEBCAM_CACHE_KEY, maxAgeMs, { now, storage });
}

export function writeLiveWebcamCache(data, { now, storage } = {}) {
  return writeJsonCache(LIVE_WEBCAM_CACHE_KEY, data, { now, storage });
}

export function readLiveCommunityCacheEntry({
  communityLocation,
  maxAgeMs = LIVE_COMMUNITY_STORAGE_MAX_AGE_MS,
  now,
  storage,
} = {}) {
  try {
    return readJsonCacheEntry(communityCacheKey(communityLocation), maxAgeMs, { now, storage });
  } catch { return null; }
}

export function writeLiveCommunityCache(data, { communityLocation, now, storage } = {}) {
  try {
    if (storage === undefined) storage = globalThis.localStorage;
    const key = communityCacheKey(communityLocation);
    // Bounded pilot cache: retain at most twelve locality scopes.
    if (isLocalCommunityPilot() && storage) {
      const prefix = `${communityStorageKey(LIVE_COMMUNITY_CACHE_KEY)}:`;
      const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index))
        .filter((item) => item?.startsWith(prefix) && item !== key);
      for (const old of keys.slice(0, Math.max(0, keys.length - 11))) storage.removeItem(old);
    }
    return writeJsonCache(key, data, { now, storage });
  } catch { return false; }
}

export function clearLiveDeviceCache({ storage } = {}) {
  const webcams = removeJsonCache(LIVE_WEBCAM_CACHE_KEY, { storage });
  const community = removeJsonCache(LIVE_COMMUNITY_CACHE_KEY, { storage });
  try {
    const resolvedStorage = storage === undefined ? globalThis.localStorage : storage;
    if (isLocalCommunityPilot() && resolvedStorage) {
      const prefix = `${communityStorageKey(LIVE_COMMUNITY_CACHE_KEY)}:`;
      const keys = Array.from({ length: resolvedStorage.length }, (_, index) => resolvedStorage.key(index));
      keys.filter((key) => key?.startsWith(prefix)).forEach((key) => removeJsonCache(key, { storage: resolvedStorage }));
    }
  } catch { /* Storage may be denied without preventing the app from working. */ }

  return {
    community,
    ok: webcams || community,
    webcams,
  };
}
