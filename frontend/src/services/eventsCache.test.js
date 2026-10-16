import { describe, expect, it, vi } from "vitest";

import { FULL_EVENTS_LIMIT, HOME_EVENTS_LIMIT } from "./eventsApi";
import {
  clearEventsCache,
  createEventsCachePayload,
  EVENTS_CACHE_SCHEMA_VERSION,
  getEventsCachedLimit,
  getEventsCacheKey,
  getEventsLocationKey,
  isUsableEventsCache,
  readEventsCache,
  readEventsCacheEntry,
  writeEventsCache,
} from "./eventsCache";

function createStorage(initial = {}) {
  const items = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => (items.has(key) ? items.get(key) : null)),
    setItem: vi.fn((key, value) => {
      items.set(key, value);
    }),
    removeItem: vi.fn((key) => {
      items.delete(key);
    }),
  };
}

function cacheEntry(data, savedAt = 1000) {
  return JSON.stringify({ savedAt, data });
}

describe("events cache", () => {
  it("builds location and cache keys from city or location objects", () => {
    expect(getEventsLocationKey("Pordenone")).toBe("pordenone|city|city");
    expect(getEventsCacheKey({ city: "Cordenons", lat: 45.98361, lon: 12.70038 }, FULL_EVENTS_LIMIT)).toBe(
      "eventsCache:v12:cordenons|45.9836|12.7004:100",
    );
  });

  it("marks usable caches with the single source schema", () => {
    const payload = createEventsCachePayload([{ id: "e1" }]);

    expect(payload).toEqual({
      schemaVersion: EVENTS_CACHE_SCHEMA_VERSION,
      contractVersion: null,
      events: [{ id: "e1" }],
      total: 1,
    });
    expect(isUsableEventsCache(payload)).toBe(true);
    expect(isUsableEventsCache({ events: [] })).toBe(false);
  });

  it("prefers the full canonical events cache over the home cache", () => {
    const storage = createStorage({
      [getEventsCacheKey("Udine", HOME_EVENTS_LIMIT)]: cacheEntry(createEventsCachePayload([{ id: "home" }])),
      [getEventsCacheKey("Udine", FULL_EVENTS_LIMIT)]: cacheEntry(createEventsCachePayload([{ id: "full" }])),
    });

    expect(readEventsCache("Udine", { storage, now: () => 1000 }).events).toEqual([{ id: "full" }]);
    expect(getEventsCachedLimit("Udine", { storage, now: () => 1000 })).toBe(FULL_EVENTS_LIMIT);
  });

  it("falls back to the home cache when full cache is missing", () => {
    const storage = createStorage({
      [getEventsCacheKey("Udine", HOME_EVENTS_LIMIT)]: cacheEntry(createEventsCachePayload([{ id: "home" }])),
    });

    expect(readEventsCache("Udine", { storage, now: () => 1000 }).events).toEqual([{ id: "home" }]);
    expect(getEventsCachedLimit("Udine", { storage, now: () => 1000 })).toBe(HOME_EVENTS_LIMIT);
  });

  it("promotes a safely identified FVG cache from the pre-national key and preserves savedAt", () => {
    const location = {
      city: "Pordenone",
      countryCode: "IT",
      region: "Friuli Venezia Giulia",
      province: "PN",
      lat: 45.9567,
      lon: 12.6605,
    };
    const legacyLocation = {
      city: location.city,
      lat: location.lat,
      lon: location.lon,
    };
    const legacyKey = getEventsCacheKey(legacyLocation, FULL_EVENTS_LIMIT);
    const currentKey = getEventsCacheKey(location, FULL_EVENTS_LIMIT);
    const data = createEventsCachePayload([{ id: "legacy-fvg" }]);
    const storage = createStorage({ [legacyKey]: cacheEntry(data, 1000) });

    expect(currentKey).not.toBe(legacyKey);
    expect(readEventsCacheEntry(location, FULL_EVENTS_LIMIT, {
      storage,
      now: () => 1500,
    })).toEqual({
      age: 500,
      data,
      limit: FULL_EVENTS_LIMIT,
      savedAt: 1000,
    });
    expect(storage.setItem).toHaveBeenCalledWith(currentKey, cacheEntry(data, 1000));
    expect(storage.removeItem).toHaveBeenCalledWith(legacyKey);
  });

  it("does not fall back to an ambiguous pre-national key for a national non-FVG location", () => {
    const location = {
      city: "Roma",
      countryCode: "IT",
      region: "Lazio",
      regionCode: "IT-62",
      lat: 41.9028,
      lon: 12.4964,
    };
    const legacyKey = getEventsCacheKey({
      city: location.city,
      lat: location.lat,
      lon: location.lon,
    }, FULL_EVENTS_LIMIT);
    const storage = createStorage({
      [legacyKey]: cacheEntry(createEventsCachePayload([{ id: "wrong-region" }])),
    });

    expect(readEventsCache(location, { storage, now: () => 1000 })).toBeNull();
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

  it("promotes home reads to full cache entries but can fall back to legacy home entries", () => {
    const fullStorage = createStorage({
      [getEventsCacheKey("Udine", FULL_EVENTS_LIMIT)]: cacheEntry(createEventsCachePayload([{ id: "full" }])),
    });
    const homeStorage = createStorage({
      [getEventsCacheKey("Udine", HOME_EVENTS_LIMIT)]: cacheEntry(createEventsCachePayload([{ id: "home" }])),
    });

    expect(readEventsCacheEntry("Udine", HOME_EVENTS_LIMIT, { storage: fullStorage, now: () => 1000 })).toMatchObject({
      data: createEventsCachePayload([{ id: "full" }]),
      limit: FULL_EVENTS_LIMIT,
    });
    expect(readEventsCacheEntry("Udine", HOME_EVENTS_LIMIT, { storage: homeStorage, now: () => 1000 })).toMatchObject({
      data: createEventsCachePayload([{ id: "home" }]),
      limit: HOME_EVENTS_LIMIT,
    });
  });

  it("writes schema-marked events cache payloads", () => {
    const storage = createStorage();

    expect(writeEventsCache("Udine", [{ id: "e1" }], {
      contractVersion: "canonical-events-v2",
      storage,
      now: () => 2000,
    })).toBe(true);
    expect(storage.setItem).toHaveBeenCalledWith(
      getEventsCacheKey("Udine", FULL_EVENTS_LIMIT),
      cacheEntry(createEventsCachePayload([{ id: "e1" }], "canonical-events-v2"), 2000),
    );
  });

  it("clears full and home event caches for the selected location", () => {
    const storage = createStorage({
      [getEventsCacheKey("Udine", FULL_EVENTS_LIMIT)]: cacheEntry(createEventsCachePayload([{ id: "full" }])),
      [getEventsCacheKey("Udine", HOME_EVENTS_LIMIT)]: cacheEntry(createEventsCachePayload([{ id: "home" }])),
    });

    expect(clearEventsCache("Udine", { storage })).toBe(true);
    expect(storage.removeItem).toHaveBeenCalledWith(getEventsCacheKey("Udine", FULL_EVENTS_LIMIT));
    expect(storage.removeItem).toHaveBeenCalledWith(getEventsCacheKey("Udine", HOME_EVENTS_LIMIT));
  });
});
