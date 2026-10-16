import { afterEach, describe, expect, it, vi } from "vitest";

import * as localWeatherPilot from "./localWeatherPilot";
import { getWeatherCacheKey } from "./weatherCache";
import {
  clearLocalConditionsDeviceCache,
  getLocalConditionsCacheKey,
  LOCAL_CONDITIONS_STORAGE_MAX_AGE_MS,
  readLocalConditionsDeviceCache,
  writeLocalConditionsDeviceCache,
} from "./localConditionsCache";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

function createStorage(initial = {}) {
  const items = new Map(Object.entries(initial));
  return {
    getItem: vi.fn((key) => items.get(key) ?? null),
    setItem: vi.fn((key, value) => items.set(key, value)),
    removeItem: vi.fn((key) => items.delete(key)),
    items,
  };
}

function entry(data) {
  return JSON.stringify({ savedAt: 1000, data });
}

describe("local conditions cache", () => {
  it("preserves ordinary reads, writes and expiry outside the pilot", () => {
    const storage = createStorage();
    const location = { city: "Udine" };
    const data = { current: { temperature: 23 } };
    expect(writeLocalConditionsDeviceCache(location, data, { storage, now: () => 1000 })).toBe(true);
    expect(readLocalConditionsDeviceCache(location, { storage, now: () => 1000 })).toEqual(data);
    expect(readLocalConditionsDeviceCache(location, {
      storage, now: () => 1001 + LOCAL_CONDITIONS_STORAGE_MAX_AGE_MS,
    })).toBeNull();
  });

  it("retains the ordinary shared-cache fallback and its opt-out", () => {
    const location = { city: "Udine" };
    const ordinary = { current: { temperature: 23 } };
    const storage = createStorage({ [getWeatherCacheKey(location)]: entry(ordinary) });
    const options = { storage, now: () => 1000 };
    expect(readLocalConditionsDeviceCache(location, options)).toEqual(ordinary);
    expect(readLocalConditionsDeviceCache(location, { ...options, allowLegacyWeatherCache: false })).toBeNull();
  });

  it("does not read, modify or erase either ordinary cache while piloting", () => {
    const location = { city: "Udine" };
    const local = { current: { temperature: 23 } };
    const shared = { current: { temperature: 24 } };
    const storage = createStorage({
      [getLocalConditionsCacheKey(location)]: entry(local),
      [getWeatherCacheKey(location)]: entry(shared),
    });
    const snapshot = new Map(storage.items);
    const pilot = vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const options = { storage, now: () => 1000, maxAgeMs: Infinity };

    expect(readLocalConditionsDeviceCache(location, options)).toBeNull();
    expect(writeLocalConditionsDeviceCache(location, { current: { temperature: 15 } }, options)).toBe(false);
    expect(clearLocalConditionsDeviceCache(location, options)).toBe(false);
    expect(storage.getItem).not.toHaveBeenCalled();
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.removeItem).not.toHaveBeenCalled();
    expect(storage.items).toEqual(snapshot);

    pilot.mockReturnValue(false);
    expect(readLocalConditionsDeviceCache(location, options)).toEqual(local);
  });

  it("does not expose a saved Open-Meteo local response in autonomous production", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    vi.stubEnv("VITE_WEATHER_PROVIDER_PRIMARY", "autonomous");
    const location = { city: "Udine" };
    const storage = createStorage({
      [getLocalConditionsCacheKey(location)]: entry({
        current: { primary_source: "open_meteo", temperature: 23 },
      }),
    });

    expect(readLocalConditionsDeviceCache(location, {
      maxAgeMs: Infinity,
      now: () => 1000,
      storage,
    })).toBeNull();
    expect(storage.getItem).toHaveBeenCalledWith(getLocalConditionsCacheKey(location));
  });

  it("fails closed as a cache miss for an explicitly foreign location", () => {
    const location = { city: "Nova Gorica", countryCode: "SI", region: "Gorizia" };
    const storage = createStorage();

    expect(() => readLocalConditionsDeviceCache(location, { storage })).not.toThrow();
    expect(readLocalConditionsDeviceCache(location, { storage })).toBeNull();
    expect(writeLocalConditionsDeviceCache(location, { current: {} }, { storage })).toBe(false);
    expect(clearLocalConditionsDeviceCache(location, { storage })).toBe(false);
    expect(storage.getItem).not.toHaveBeenCalled();
  });
});
