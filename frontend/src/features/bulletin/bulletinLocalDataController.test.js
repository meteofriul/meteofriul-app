import { describe, expect, it, vi } from "vitest";

import {
  BULLETIN_LOCAL_AUTO_REFRESH_INTERVAL_MS,
  loadBulletinLocalData,
  readInitialBulletinLocalData,
} from "./bulletinLocalDataController";
import { LOCAL_CONDITIONS_STORAGE_MAX_AGE_MS } from "../../services/localConditionsCache";

const NOW = new Date("2026-08-02T21:00:00.000Z").getTime();
const LOCAL_CACHE_KEY = "bulletinLocalConditionsCache:v1:pordenone|city|city";
const WEATHER_CACHE_KEY = "weatherBootstrapCache:v3:pordenone|city|city";

function createStorage(initial = {}) {
  const items = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => (items.has(key) ? items.get(key) : null)),
    setItem: vi.fn((key, value) => items.set(key, value)),
    removeItem: vi.fn((key) => items.delete(key)),
    items,
  };
}

function cacheEntry(data, savedAt = NOW) {
  return JSON.stringify({ savedAt, data });
}

function buildPayload(overrides = {}) {
  return {
    city: "Pordenone",
    current: {
      city: "Pordenone",
      humidity: 64,
      pressure: 1009,
      wind_speed: 2,
      ...overrides,
    },
    updatedAt: "2026-08-02T21:00:00.000Z",
  };
}

describe("bulletin local data controller", () => {
  it("uses a ten minute cadence for silent local updates", () => {
    expect(BULLETIN_LOCAL_AUTO_REFRESH_INTERVAL_MS).toBe(10 * 60 * 1000);
  });

  it("hydrates from its dedicated fresh cache", async () => {
    const storage = createStorage({
      [LOCAL_CACHE_KEY]: cacheEntry(buildPayload()),
    });
    const localFetcher = vi.fn();

    const state = await loadBulletinLocalData({ city: "Pordenone" }, {
      localFetcher,
      now: () => NOW,
      storage,
    });

    expect(localFetcher).not.toHaveBeenCalled();
    expect(state).toMatchObject({
      city: "Pordenone",
      fromCache: true,
      isStale: false,
      status: "cache",
    });
    expect(state.current.humidity).toBe(64);
  });

  it("hydrates once from the shared Home weather cache", () => {
    const storage = createStorage({
      [WEATHER_CACHE_KEY]: cacheEntry(buildPayload()),
    });

    expect(readInitialBulletinLocalData({ city: "Pordenone" }, {
      now: () => NOW,
      storage,
    })).toMatchObject({
      city: "Pordenone",
      fromCache: true,
      status: "cache",
    });
  });

  it("writes a dedicated cache after a successful refresh", async () => {
    const storage = createStorage();
    const current = buildPayload().current;

    const state = await loadBulletinLocalData({ city: "Pordenone" }, {
      force: true,
      localFetcher: vi.fn().mockResolvedValue({ city: "Pordenone", current }),
      now: () => NOW,
      nowIso: () => "2026-08-02T21:00:00.000Z",
      storage,
    });

    expect(state).toMatchObject({
      city: "Pordenone",
      fromCache: false,
      status: "fresh",
      updatedAt: "2026-08-02T21:00:00.000Z",
    });
    expect(storage.setItem).toHaveBeenCalledWith(LOCAL_CACHE_KEY, expect.any(String));
  });

  it("keeps a recent saved snapshot when the local source is unreachable", async () => {
    const storage = createStorage({
      [LOCAL_CACHE_KEY]: cacheEntry(buildPayload(), NOW - 30 * 60 * 1000),
    });

    const state = await loadBulletinLocalData({ city: "Pordenone" }, {
      force: true,
      localFetcher: vi.fn().mockRejectedValue(new Error("network_error")),
      now: () => NOW,
      storage,
    });

    expect(state).toMatchObject({
      error: "network_error",
      fromCache: true,
      isStale: true,
      status: "stale",
    });
    expect(state.current.pressure).toBe(1009);
  });

  it("does not revive expired local conditions when the source is unreachable", async () => {
    const storage = createStorage({
      [LOCAL_CACHE_KEY]: cacheEntry(
        buildPayload(),
        NOW - LOCAL_CONDITIONS_STORAGE_MAX_AGE_MS - 1,
      ),
    });

    const state = await loadBulletinLocalData({ city: "Pordenone" }, {
      force: true,
      localFetcher: vi.fn().mockRejectedValue(new Error("network_error")),
      now: () => NOW,
      storage,
    });

    expect(state).toMatchObject({
      current: null,
      error: "network_error",
      fromCache: false,
      status: "error",
    });
  });

  it("returns an empty error state without affecting official bulletin data", async () => {
    const state = await loadBulletinLocalData({ city: "Pordenone" }, {
      force: true,
      localCacheReader: vi.fn().mockReturnValue(null),
      localFetcher: vi.fn().mockRejectedValue(new Error("network_error")),
    });

    expect(state).toMatchObject({
      current: null,
      error: "network_error",
      status: "error",
    });
  });
});
