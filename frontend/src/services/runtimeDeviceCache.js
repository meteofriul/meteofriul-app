import { clearBulletinDeviceCache } from "./bulletinCache";
import { clearEventsCache, EVENTS_CACHE_PREFIX } from "./eventsCache";
import { clearLiveDeviceCache } from "./liveCache";
import { clearLocalConditionsDeviceCache } from "./localConditionsCache";
import { clearLocalWeatherV1MemoryCache } from "./localWeatherV1Runtime";
import { clearPilotWeatherPrefetch } from "./pilotWeatherPrefetch";
import { clearRadarDeviceCache } from "./radarCache";
import { clearWeatherDeviceCache } from "./weatherCache";
import { clearWeatherV1ClientMemoryCache } from "./weatherV1Client";

export const RUNTIME_DEVICE_CACHE_EXACT_KEYS = Object.freeze([
  "liveCommunityReports:v1",
  "liveWebcamManifest:v1",
  "meteofriul:uv:v1",
  "meteofriul:uv:v1:candidate",
]);

export const RUNTIME_DEVICE_CACHE_PREFIXES = Object.freeze([
  "bulletinLocalConditionsCache:v1:",
  "bulletinRadarCache:v2:",
  "communityV2:v1:liveCommunityReports:v1:",
  "eventsCache:v12:",
  "eventsCache:v12:pilot-programmes-v2:",
  "eventsCache:v13:",
  `${EVENTS_CACHE_PREFIX}:`,
  "localCommunityPilot:v1:liveCommunityReports:v1:",
  "locationReverseCache:v3:",
  "meteofriul:national-weather-v2:",
  "meteofriul:weather-v1:bundle:v2:",
  "meteofriul:weather-v1:bundle:v3:",
  "meteofriul:weather-v1:bundle:v4:",
  "meteofriul:weather-v1:cams-family-decision:v1:",
  "meteofriul:weather-v1:v2:",
  "meteofriul:weather-v1:v3:",
  "meteofriul:weather-v1:v4:",
  "officialBulletinCache:local-weather-pilot:v1:",
  "officialBulletinCache:v1:",
  "weatherBootstrapCache:v2:",
  "weatherBootstrapCache:v3:",
]);

function getDefaultStorage() {
  try { return globalThis?.localStorage || null; }
  catch { return null; }
}

function isRuntimeCacheKey(key) {
  return RUNTIME_DEVICE_CACHE_EXACT_KEYS.includes(key)
    || RUNTIME_DEVICE_CACHE_PREFIXES.some(prefix => key.startsWith(prefix));
}

export function clearAllRuntimeStorageCaches({ storage = getDefaultStorage() } = {}) {
  if (!storage || typeof storage.removeItem !== "function"
    || typeof storage.key !== "function" || !Number.isSafeInteger(storage.length)) {
    return { ok: false, removed: 0 };
  }

  try {
    const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index))
      .filter(key => typeof key === "string" && isRuntimeCacheKey(key));
    let ok = true;
    let removed = 0;
    for (const key of keys) {
      try {
        storage.removeItem(key);
        removed += 1;
      } catch {
        ok = false;
      }
    }
    return { ok, removed };
  } catch {
    return { ok: false, removed: 0 };
  }
}

export async function clearRuntimeDeviceCaches(
  location,
  { eventsLocation = location, storage = getDefaultStorage() } = {},
) {
  const nativePrefetch = await clearPilotWeatherPrefetch();
  const storageCaches = clearAllRuntimeStorageCaches({ storage });
  const memory = {
    localWeather: clearLocalWeatherV1MemoryCache(),
    rawWeather: clearWeatherV1ClientMemoryCache({ storage }),
  };

  // Targeted removals also cover the active location on partial Storage
  // implementations. A non-enumerable store still reports an incomplete reset.
  const weather = clearWeatherDeviceCache(location, { storage });
  const events = clearEventsCache(eventsLocation, { storage });
  const bulletin = clearBulletinDeviceCache(location, { storage });
  const localConditions = clearLocalConditionsDeviceCache(location, { storage });
  const radar = clearRadarDeviceCache(location, { storage });
  const live = clearLiveDeviceCache({ storage });
  const ok = storageCaches.ok
    && memory.localWeather
    && memory.rawWeather
    && nativePrefetch !== false;

  return {
    bulletin,
    events,
    live,
    localConditions,
    memory,
    nativePrefetch,
    ok,
    radar,
    storage: storageCaches,
    weather,
  };
}
