import { afterEach, describe, expect, it, vi } from "vitest";

import * as localWeatherPilot from "./localWeatherPilot";

import {
  clearWeatherDeviceCache,
  getWeatherCacheKey,
  hasOfficialOsmerForecasts,
  readWeatherDeviceCache,
  readWeatherDeviceCacheEntry,
  WEATHER_CACHE_MAX_AGE_MS,
  writeWeatherDeviceCache,
} from "./weatherCache";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

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

describe("weather cache", () => {
  it("bypasses reads, writes and clears during the pilot without touching saved ordinary weather", () => {
    const location = { city: "Udine" };
    const ordinary = { current: { temperature: 28 }, forecast: { days: [] } };
    const stored = JSON.stringify({ savedAt: 1000, data: ordinary });
    const storage = createStorage({ [getWeatherCacheKey(location)]: stored });
    const pilot = vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const options = { now: () => 1000, storage, maxAgeMs: Infinity };

    expect(readWeatherDeviceCache(location, options)).toBeNull();
    expect(readWeatherDeviceCacheEntry(location, options)).toBeNull();
    expect(writeWeatherDeviceCache(location, { current: { temperature: 15 } }, options)).toBe(false);
    expect(clearWeatherDeviceCache(location, options)).toBe(false);
    expect(storage.getItem).not.toHaveBeenCalled();
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.removeItem).not.toHaveBeenCalled();

    pilot.mockReturnValue(false);
    expect(readWeatherDeviceCache(location, options)).toEqual(ordinary);
    expect(storage.getItem(getWeatherCacheKey(location))).toBe(stored);
  });

  it("does not read or write an Open-Meteo cache for a national location during the FVG pilot", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const roma = {
      city: "Roma",
      countryCode: "IT",
      region: "Lazio",
      regionCode: "IT-62",
    };
    const storage = createStorage();
    const data = { current: { temperature: 27 }, forecast: { daily: [] } };
    const options = { storage, now: () => 1000 };

    expect(writeWeatherDeviceCache(roma, data, options)).toBe(false);
    expect(readWeatherDeviceCache(roma, options)).toBeNull();
    expect(storage.getItem).not.toHaveBeenCalled();
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("promotes a safely identified FVG cache from the pre-national location key without refreshing its age", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
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
    const legacyKey = getWeatherCacheKey(legacyLocation);
    const currentKey = getWeatherCacheKey(location);
    const data = { current: { temperature: 21 }, forecast: { daily: [] } };
    const storage = createStorage({
      [legacyKey]: JSON.stringify({ savedAt: 1000, data }),
    });

    expect(currentKey).not.toBe(legacyKey);
    expect(readWeatherDeviceCacheEntry(location, {
      maxAgeMs: 1000,
      now: () => 1500,
      storage,
    })).toEqual({ age: 500, data, savedAt: 1000 });
    expect(storage.setItem).toHaveBeenCalledWith(
      currentKey,
      JSON.stringify({ savedAt: 1000, data }),
    );
    expect(storage.removeItem).toHaveBeenCalledWith(legacyKey);
  });

  it("never treats a pre-national key as a fallback for a non-FVG location", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    const location = {
      city: "Roma",
      countryCode: "IT",
      region: "Lazio",
      regionCode: "IT-62",
      lat: 41.9028,
      lon: 12.4964,
    };
    const legacyKey = getWeatherCacheKey({
      city: location.city,
      lat: location.lat,
      lon: location.lon,
    });
    const storage = createStorage({
      [legacyKey]: JSON.stringify({
        savedAt: 1000,
        data: { current: { temperature: 99 } },
      }),
    });

    expect(readWeatherDeviceCache(location, {
      maxAgeMs: Infinity,
      now: () => 1000,
      storage,
    })).toBeNull();
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

  it("treats an explicitly unsupported foreign territory as a cache miss", () => {
    const location = {
      city: "Nova Gorica",
      countryCode: "SI",
      region: "Gorizia",
      lat: 45.956,
      lon: 13.648,
    };
    const storage = createStorage();

    expect(() => readWeatherDeviceCache(location, { storage })).not.toThrow();
    expect(readWeatherDeviceCache(location, { storage })).toBeNull();
    expect(readWeatherDeviceCacheEntry(location, { storage })).toBeNull();
    expect(writeWeatherDeviceCache(location, { current: {} }, { storage })).toBe(false);
    expect(clearWeatherDeviceCache(location, { storage })).toBe(false);
    expect(storage.getItem).not.toHaveBeenCalled();
  });

  it("does not rehydrate an Open-Meteo bootstrap cache in autonomous production", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    vi.stubEnv("VITE_WEATHER_PROVIDER_PRIMARY", "autonomous");
    const location = { city: "Udine" };
    const storage = createStorage({
      [getWeatherCacheKey(location)]: JSON.stringify({
        savedAt: 1000,
        data: { current: { primary_source: "open_meteo", temperature: 28 } },
      }),
    });

    expect(readWeatherDeviceCache(location, {
      maxAgeMs: Infinity,
      now: () => 1000,
      storage,
    })).toBeNull();
    expect(storage.getItem).toHaveBeenCalledWith(getWeatherCacheKey(location));
  });

  it("does not rehydrate the old mixed cache or erase independent official data", () => {
    const oldCache = JSON.stringify({ savedAt: 1000, data: { current: { temperature: 30 } } });
    const storage = createStorage({
      "weatherBootstrapCache:v2:udine|city|city": oldCache,
      "independent-official-data": "preserved",
    });

    expect(readWeatherDeviceCache({ city: "Udine" }, { storage, now: () => 1000 })).toBeNull();
    expect(storage.removeItem).not.toHaveBeenCalled();
    expect(storage.getItem("independent-official-data")).toBe("preserved");
  });

  it("uses a new cache namespace for coherent Open-Meteo current conditions", () => {
    expect(getWeatherCacheKey({ city: "Udine" })).toBe("weatherBootstrapCache:v3:udine|city|city");
  });

  it("reads and writes weather cache through injected storage", () => {
    const storage = createStorage();
    const location = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };
    const data = { current: { temperature: 20 }, forecast: { daily: [] } };

    expect(writeWeatherDeviceCache(location, data, { storage, now: () => 1000 })).toBe(true);
    expect(readWeatherDeviceCache(location, { storage, now: () => 1000 + WEATHER_CACHE_MAX_AGE_MS })).toEqual(data);
    expect(readWeatherDeviceCache(location, { storage, now: () => 1001 + WEATHER_CACHE_MAX_AGE_MS })).toBeNull();
  });

  it("clears the weather cache for the selected location", () => {
    const location = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };
    const storage = createStorage({
      [getWeatherCacheKey(location)]: JSON.stringify({ savedAt: 1000, data: { current: {} } }),
    });

    expect(clearWeatherDeviceCache(location, { storage })).toBe(true);
    expect(storage.removeItem).toHaveBeenCalledWith(getWeatherCacheKey(location));
  });

  it("detects official OSMER text in current or forecast cache data", () => {
    expect(hasOfficialOsmerForecasts({ current: { official: { it: { forecasts: [{ text: "  " }] } } } })).toBe(
      false,
    );
    expect(hasOfficialOsmerForecasts({ forecast: { official: { it: { forecasts: [{ text: "Sole" }] } } } })).toBe(
      true,
    );
  });
});
