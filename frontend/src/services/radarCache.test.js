import { describe, expect, it, vi } from "vitest";

import {
  clearRadarDeviceCache,
  getRadarCacheKey,
  readRadarDeviceCache,
  writeRadarDeviceCache,
} from "./radarCache";

function createStorage() {
  const items = new Map();
  return {
    getItem: vi.fn(key => items.get(key) ?? null),
    setItem: vi.fn((key, value) => items.set(key, value)),
    removeItem: vi.fn(key => items.delete(key)),
  };
}

describe("radar cache", () => {
  const location = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };

  it("keeps radar entries isolated by location", () => {
    const storage = createStorage();
    const other = { city: "Udine", lat: 46.0635, lon: 13.2358 };

    expect(writeRadarDeviceCache(location, { frame: "pn" }, { storage, now: () => 1000 })).toBe(true);
    expect(writeRadarDeviceCache(other, { frame: "ud" }, { storage, now: () => 1000 })).toBe(true);
    expect(readRadarDeviceCache(location, { storage, now: () => 1100 })).toEqual({ frame: "pn" });
    expect(readRadarDeviceCache(other, { storage, now: () => 1100 })).toEqual({ frame: "ud" });
    expect(getRadarCacheKey(location)).not.toBe(getRadarCacheKey(other));
  });

  it("removes the selected radar entry", () => {
    const storage = createStorage();
    writeRadarDeviceCache(location, { frame: "pn" }, { storage, now: () => 1000 });

    expect(clearRadarDeviceCache(location, { storage })).toBe(true);
    expect(storage.removeItem).toHaveBeenCalledWith(getRadarCacheKey(location));
    expect(readRadarDeviceCache(location, { storage, now: () => 1100 })).toBeNull();
  });
});
