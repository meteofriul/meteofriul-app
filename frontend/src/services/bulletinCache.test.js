import { describe, expect, it, vi } from "vitest";

import {
  getBulletinCacheKey,
  readBulletinDeviceCache,
  writeBulletinDeviceCache,
} from "./bulletinCache";

function createStorage(initial = {}) {
  const items = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => (items.has(key) ? items.get(key) : null)),
    setItem: vi.fn((key, value) => items.set(key, value)),
    removeItem: vi.fn((key) => items.delete(key)),
    items,
  };
}

function cacheEntry(data, savedAt = 1000) {
  return JSON.stringify({ data, savedAt });
}

describe("bulletin device cache", () => {
  it("disables both weather migrations in pilot but preserves the independent official cache", () => {
    const location = { city: "Udine" };
    const storage = createStorage({
      "weatherBootstrapCache:v2:udine|city|city": cacheEntry({ id: "legacy" }),
      "weatherBootstrapCache:v3:udine|city|city": cacheEntry({ id: "ordinary" }),
    });
    const options = { localPilot: true, now: () => 1000, storage };
    expect(readBulletinDeviceCache(location, options)).toBeNull();
    expect(storage.getItem).toHaveBeenCalledTimes(1);
    expect(storage.getItem).toHaveBeenCalledWith(getBulletinCacheKey(location, { localPilot: true }));
    expect(storage.removeItem).not.toHaveBeenCalled();

    expect(writeBulletinDeviceCache(location, { id: "real-official" }, options)).toBe(true);
    expect(readBulletinDeviceCache(location, options)).toEqual({ id: "real-official" });
    expect(storage.items.has("officialBulletinCache:v1:udine|city|city")).toBe(false);
    expect(storage.items.has("officialBulletinCache:local-weather-pilot:v1:udine|city|city")).toBe(true);
    expect(storage.items.get("weatherBootstrapCache:v2:udine|city|city")).toBe(cacheEntry({ id: "legacy" }));
    expect(storage.items.get("weatherBootstrapCache:v3:udine|city|city")).toBe(cacheEntry({ id: "ordinary" }));
  });

  it("keeps ordinary and local-pilot bulletin snapshots in separate namespaces", () => {
    const location = { city: "Udine" };
    const storage = createStorage();
    const options = { now: () => 1000, storage };

    expect(writeBulletinDeviceCache(location, { id: "ordinary" }, options)).toBe(true);
    expect(writeBulletinDeviceCache(location, { id: "pilot" }, {
      ...options,
      localPilot: true,
    })).toBe(true);

    expect(readBulletinDeviceCache(location, options)).toEqual({ id: "ordinary" });
    expect(readBulletinDeviceCache(location, { ...options, localPilot: true })).toEqual({ id: "pilot" });
  });

  it("uses a dedicated key instead of overwriting the Home weather cache", () => {
    const location = { city: "Udine" };
    const storage = createStorage();

    writeBulletinDeviceCache(location, { forecast: { id: "official" } }, {
      now: () => 1000,
      storage,
    });

    expect(getBulletinCacheKey(location)).toBe("officialBulletinCache:v1:udine|city|city");
    expect(storage.setItem).toHaveBeenCalledWith(
      "officialBulletinCache:v1:udine|city|city",
      expect.any(String),
    );
    expect(storage.items.has("weatherBootstrapCache:v2:udine|city|city")).toBe(false);
  });

  it("reads the dedicated cache before the legacy weather cache", () => {
    const location = { city: "Udine" };
    const storage = createStorage({
      "officialBulletinCache:v1:udine|city|city": cacheEntry({ id: "dedicated" }),
      "weatherBootstrapCache:v2:udine|city|city": cacheEntry({ id: "legacy" }),
    });

    expect(readBulletinDeviceCache(location, {
      maxAgeMs: 1000,
      now: () => 1000,
      storage,
    })).toEqual({ id: "dedicated" });
  });

  it("migrates transparently from the previous shared cache", () => {
    const location = { city: "Udine" };
    const storage = createStorage({
      "weatherBootstrapCache:v2:udine|city|city": cacheEntry({ id: "legacy" }),
    });

    expect(readBulletinDeviceCache(location, {
      maxAgeMs: 1000,
      now: () => 1000,
      storage,
    })).toEqual({ id: "legacy" });
  });

  it("prefers the new shared cache and can disable both shared fallbacks", () => {
    const location = { city: "Udine" };
    const storage = createStorage({
      "weatherBootstrapCache:v2:udine|city|city": cacheEntry({ id: "old" }),
      "weatherBootstrapCache:v3:udine|city|city": cacheEntry({ id: "current" }),
    });
    const options = { now: () => 1000, storage };

    expect(readBulletinDeviceCache(location, options)).toEqual({ id: "current" });
    expect(readBulletinDeviceCache(location, { ...options, allowLegacyWeatherCache: false })).toBeNull();
    expect(storage.removeItem).not.toHaveBeenCalled();
  });
});
