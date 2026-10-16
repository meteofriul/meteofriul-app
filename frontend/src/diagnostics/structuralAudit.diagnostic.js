import { describe, expect, it, vi } from "vitest";

import {
  hydrateHomeWeatherFromBackgroundPrefetch,
  loadHomeEvents,
  readInitialHomeData,
} from "../features/home/homeDataController";
import { loadBulletinRadarData } from "../features/bulletin/bulletinRadarDataController";
import { loadLiveData } from "../features/live/liveDataController";
import { isVerifiedUvDocument } from "../features/weather/uvForecast";
import { LIVE_WEBCAM_CACHE_KEY } from "../services/liveCache";
import { getPushNavigationTarget } from "../services/pushDeepLink";

function createStorage() {
  const values = new Map();

  return {
    getItem: vi.fn((key) => values.get(key) ?? null),
    removeItem: vi.fn((key) => values.delete(key)),
    setItem: vi.fn((key, value) => values.set(key, value)),
  };
}

function createDeferred() {
  let resolve;
  const promise = new Promise((settle) => {
    resolve = settle;
  });

  return { promise, resolve };
}

function createWeatherPayload(city, temperature) {
  return {
    city,
    current: {
      city,
      condition: "Sereno",
      primary_source: "open_meteo",
      temperature,
      weathercode: 0,
    },
    forecast: { daily: [] },
  };
}

function createRadarPayload(time) {
  return {
    available: true,
    city: "Pordenone",
    products: [{ id: time, product_type: "SRI", time }],
    tiles: { base_url: "https://tiles.example.test" },
  };
}

function createWebcamPayload(version) {
  return {
    ok: true,
    version,
    webcams: [{ id: `webcam-${version}` }],
  };
}

function createStructurallyUntrustedUvDocument() {
  const runAt = Date.parse("2026-09-12T00:30:00.000Z");
  return {
    schema: "pilot-uv-v1",
    source: "NOT CAMS",
    unit: "1",
    run_at: new Date(runAt).toISOString(),
    grid: [[0, 0]],
    hours: Array.from({ length: 72 }, (_, index) => ({
      time: new Date(runAt + index * 3_600_000).toISOString(),
      values: [1],
    })),
    extra: "not allowed by the producer contract",
  };
}

describe("open structural contracts at revision 3f517a8", () => {
  it("routes the backend local-weather notification type to Bollettino", () => {
    expect(getPushNavigationTarget({
      notification: { data: { type: "local_weather_notice" } },
    })).toEqual({ tab: "bulletin" });
  });

  it("rejects UV documents that violate the producer identity and exact schema", () => {
    expect(isVerifiedUvDocument(createStructurallyUntrustedUvDocument())).toBe(false);
  });

  it("marks an arbitrarily old ordinary-weather startup snapshot as stale", () => {
    const staleWeather = createWeatherPayload("Pordenone", 21);
    const weatherCacheReader = vi.fn()
      .mockReturnValueOnce(null)
      .mockReturnValueOnce(staleWeather);

    expect(readInitialHomeData({ city: "Pordenone" }, {
      bootstrapCacheReader: vi.fn().mockReturnValue(null),
      eventsCacheReader: vi.fn().mockReturnValue(null),
      weatherCacheReader,
    })).toMatchObject({
      weather: {
        current: { temperature: 21 },
        isStale: true,
        status: "stale",
      },
    });
  });

  it("does not relabel a nearby municipality prefetch as the active municipality", async () => {
    const weatherCacheWriter = vi.fn();
    const result = await hydrateHomeWeatherFromBackgroundPrefetch({
      city: "Pordenone",
      lat: 45.9567,
      lon: 12.6605,
      municipality: { istatCode: "093033", name: "Pordenone" },
    }, {
      now: () => 20_000,
      prefetchReader: vi.fn().mockResolvedValue({
        available: true,
        city: "Porcia",
        lat: 45.963,
        lon: 12.614,
        payload: createWeatherPayload("Porcia", 19),
        savedAt: 10_000,
      }),
      weatherCacheEntryReader: vi.fn().mockReturnValue(null),
      weatherCacheWriter,
    });

    expect(result).toBeNull();
    expect(weatherCacheWriter).not.toHaveBeenCalled();
  });

  it("keeps cached Home events when the backend reports source_unavailable", async () => {
    const eventsCacheWriter = vi.fn();
    const state = await loadHomeEvents({ city: "Pordenone" }, {
      eventsCacheReader: vi.fn().mockReturnValue({
        data: {
          contractVersion: "canonical-events-v2",
          events: [{ id: "cached-event" }],
          total: 1,
        },
        limit: 100,
      }),
      eventsCacheWriter,
      eventsFetcher: vi.fn().mockResolvedValue({
        cacheStatus: "source_unavailable",
        contractVersion: "canonical-events-v2",
        events: [],
        isPartial: false,
        isRefreshing: false,
        shouldRetry: false,
        total: 0,
      }),
    });

    expect(state).toMatchObject({
      fromCache: true,
      items: [{ id: "cached-event" }],
      status: "stale",
    });
    expect(eventsCacheWriter).not.toHaveBeenCalled();
  });

  it("does not let an older radar request overwrite a newer completion", async () => {
    const older = createDeferred();
    const newer = createDeferred();
    const radarCacheWriter = vi.fn();
    const options = {
      force: true,
      radarCacheReader: vi.fn().mockReturnValue(null),
      radarCacheWriter,
    };
    const olderPayload = createRadarPayload("2026-09-12T08:00:00Z");
    const newerPayload = createRadarPayload("2026-09-12T08:05:00Z");

    const olderRequest = loadBulletinRadarData({ city: "Pordenone" }, {
      ...options,
      radarFetcher: vi.fn(() => older.promise),
    });
    const newerRequest = loadBulletinRadarData({ city: "Pordenone" }, {
      ...options,
      radarFetcher: vi.fn(() => newer.promise),
    });

    newer.resolve(newerPayload);
    await newerRequest;
    older.resolve(olderPayload);
    await olderRequest;

    expect(radarCacheWriter.mock.calls.at(-1)?.[1]).toEqual(newerPayload);
  });

  it("does not let a superseded Live request regress the persistent webcam cache", async () => {
    const storage = createStorage();
    const older = createDeferred();
    const newer = createDeferred();
    const olderPayload = createWebcamPayload("older");
    const newerPayload = createWebcamPayload("newer");
    const common = {
      communityEnabled: false,
      forceWebcams: true,
      now: () => 10_000,
      storage,
    };

    const olderRequest = loadLiveData({
      ...common,
      webcamFetcher: vi.fn(() => older.promise),
    });
    const newerRequest = loadLiveData({
      ...common,
      webcamFetcher: vi.fn(() => newer.promise),
    });

    newer.resolve(newerPayload);
    await newerRequest;
    older.resolve(olderPayload);
    await olderRequest;

    const cached = JSON.parse(storage.getItem(LIVE_WEBCAM_CACHE_KEY));
    expect(cached.data).toEqual(newerPayload);
  });
});
