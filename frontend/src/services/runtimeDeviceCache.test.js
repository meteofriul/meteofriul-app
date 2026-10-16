import { describe, expect, it, vi } from "vitest";

import { FULL_EVENTS_LIMIT, HOME_EVENTS_LIMIT } from "./eventsApi";
import { getEventsCacheKey } from "./eventsCache";
import { LIVE_COMMUNITY_CACHE_KEY, LIVE_WEBCAM_CACHE_KEY } from "./liveCache";
import { REGIONAL_OFFICIAL_ALERTS_CACHE_KEY } from "./officialAlertsCache";
import { clearRuntimeDeviceCaches } from "./runtimeDeviceCache";
import { getWeatherCacheKey } from "./weatherCache";
import * as pilotPrefetch from "./pilotWeatherPrefetch";

function createStorage(initial = {}) {
  const items = new Map(Object.entries(initial));

  return {
    get length() { return items.size; },
    items,
    getItem: vi.fn(key => items.get(key) ?? null),
    key: vi.fn(index => [...items.keys()][index] ?? null),
    removeItem: vi.fn((key) => {
      items.delete(key);
    }),
    setItem: vi.fn((key, value) => {
      items.set(key, value);
    }),
  };
}

describe("runtime device cache", () => {
  it("waits for native staging cleanup before reporting completion", async () => {
    let release;
    const clear = vi.spyOn(pilotPrefetch, "clearPilotWeatherPrefetch")
      .mockReturnValue(new Promise(resolve => { release = resolve; }));
    try {
      let settled = false;
      const pending = clearRuntimeDeviceCaches(
        { city: "Pordenone" },
        { storage: createStorage() },
      ).then(result => {
        settled = true;
        return result;
      });
      await Promise.resolve();
      expect(settled).toBe(false);
      expect(clear).toHaveBeenCalledOnce();
      release(true);
      const result = await pending;
      expect(result.ok).toBe(true);
      expect(result.nativePrefetch).toBe(true);
    } finally { clear.mockRestore(); }
  });

  it("clears every runtime section and locality without touching alerts, preferences or promotion counters", async () => {
    const location = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };
    const storage = createStorage({
      [getWeatherCacheKey(location)]: "{}",
      "weatherBootstrapCache:v3:roma|istat|058091": "{}",
      [getEventsCacheKey(location, FULL_EVENTS_LIMIT)]: "{}",
      [getEventsCacheKey(location, HOME_EVENTS_LIMIT)]: "{}",
      "eventsCache:v12:roma|istat|058091:100": "{}",
      [getEventsCacheKey({ city: "Tolmezzo" }, FULL_EVENTS_LIMIT)]: "{}",
      "eventsCache:v13:pilot-programmes-v2:udine|city|city:100": "{}",
      [LIVE_COMMUNITY_CACHE_KEY]: "{}",
      [LIVE_WEBCAM_CACHE_KEY]: "{}",
      "bulletinLocalConditionsCache:v1:pordenone|city|city": "{}",
      "bulletinRadarCache:v2:pordenone|city|city": "{}",
      "communityV2:v1:liveCommunityReports:v1:45.95|12.66": "{}",
      "locationReverseCache:v3:45.956700:12.660500": "{}",
      "meteofriul:national-weather-v2:https://example.test:058091": "{}",
      "meteofriul:uv:v1": "{}",
      "meteofriul:uv:v1:candidate": "{}",
      "meteofriul:weather-v1:bundle:v4:lru": "{}",
      "meteofriul:weather-v1:v4:0123456789abcdef:icon2i:latest:0": "{}",
      "officialBulletinCache:local-weather-pilot:v1:pordenone|city|city": "{}",
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: "{}",
      "meteofriul.home-promotions.v1": "{}",
      "meteofriul:language": "fur",
    });

    const result = await clearRuntimeDeviceCaches(location, { storage });

    expect(result.ok).toBe(true);
    expect(result.storage.removed).toBe(19);
    expect(storage.removeItem).toHaveBeenCalledWith(getWeatherCacheKey(location));
    expect(storage.removeItem).toHaveBeenCalledWith(getEventsCacheKey(location, FULL_EVENTS_LIMIT));
    expect(storage.removeItem).toHaveBeenCalledWith(getEventsCacheKey(location, HOME_EVENTS_LIMIT));
    expect(storage.removeItem).toHaveBeenCalledWith(LIVE_WEBCAM_CACHE_KEY);
    expect(storage.removeItem).toHaveBeenCalledWith(LIVE_COMMUNITY_CACHE_KEY);
    expect(storage.removeItem).not.toHaveBeenCalledWith(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY);
    expect([...storage.items.keys()].sort()).toEqual([
      REGIONAL_OFFICIAL_ALERTS_CACHE_KEY,
      "meteofriul.home-promotions.v1",
      "meteofriul:language",
    ].sort());
  });

  it("clears weather and editorial events with their independent locations", async () => {
    const weatherLocation = { city: "Roma", region: "Lazio", countryCode: "IT" };
    const eventsLocation = { city: "Pordenone", region: "Friuli Venezia Giulia" };
    const storage = createStorage();

    await clearRuntimeDeviceCaches(weatherLocation, { eventsLocation, storage });

    expect(storage.removeItem).toHaveBeenCalledWith(getWeatherCacheKey(weatherLocation));
    expect(storage.removeItem).toHaveBeenCalledWith(getEventsCacheKey(eventsLocation, FULL_EVENTS_LIMIT));
    expect(storage.removeItem).not.toHaveBeenCalledWith(getEventsCacheKey(weatherLocation, FULL_EVENTS_LIMIT));
  });

  it("reports an incomplete reset when storage cannot be enumerated", async () => {
    const storage = {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
      setItem: vi.fn(),
    };

    const result = await clearRuntimeDeviceCaches({ city: "Pordenone" }, { storage });

    expect(result.ok).toBe(false);
    expect(result.storage).toEqual({ ok: false, removed: 0 });
  });
});
