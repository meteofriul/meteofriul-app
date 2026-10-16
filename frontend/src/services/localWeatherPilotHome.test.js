import { afterEach, describe, expect, it, vi } from "vitest";

import * as localWeatherPilot from "./localWeatherPilot";
import {
  hydrateHomeWeatherFromBackgroundPrefetch,
  loadHomeWeather,
} from "../features/home/homeDataController";

afterEach(() => vi.restoreAllMocks());

describe("local pilot Home isolation", () => {
  it("does not read or import ordinary background prefetch", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const prefetchReader = vi.fn();
    const weatherCacheEntryReader = vi.fn();
    const weatherCacheWriter = vi.fn();

    await expect(hydrateHomeWeatherFromBackgroundPrefetch({ city: "Udine" }, {
      prefetchReader, weatherCacheEntryReader, weatherCacheWriter,
    })).resolves.toBeNull();
    expect(prefetchReader).not.toHaveBeenCalled();
    expect(weatherCacheEntryReader).not.toHaveBeenCalled();
    expect(weatherCacheWriter).not.toHaveBeenCalled();
  });

  it("does not fall back to saved Open-Meteo weather when the pilot request fails", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const stored = JSON.stringify({ savedAt: 1000, data: {
      current: { temperature: 28 }, forecast: { days: [] },
    } });
    const items = new Map([["weatherBootstrapCache:v3:udine|city|city", stored]]);
    const storage = {
      getItem: vi.fn((key) => items.get(key) ?? null),
      setItem: vi.fn((key, value) => items.set(key, value)),
      removeItem: vi.fn((key) => items.delete(key)),
    };
    const weatherFetcher = vi.fn().mockRejectedValue(new Error("pilot snapshot unavailable"));

    const result = await loadHomeWeather({ city: "Udine" }, { storage, now: () => 1000, weatherFetcher });
    expect(result.status).toBe("empty");
    expect(result.current).toBeNull();
    expect(result.error).toBe("pilot snapshot unavailable");
    expect(weatherFetcher).toHaveBeenCalledTimes(1);
    expect(storage.getItem).not.toHaveBeenCalled();
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.removeItem).not.toHaveBeenCalled();
    expect(items.get("weatherBootstrapCache:v3:udine|city|city")).toBe(stored);
  });
});
