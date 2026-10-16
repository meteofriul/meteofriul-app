import { describe, expect, it, vi } from "vitest";

import { FULL_EVENTS_LIMIT, HOME_EVENTS_LIMIT } from "../../services/eventsApi";
import { createEventsCachePayload, getEventsCacheKey, writeEventsCache } from "../../services/eventsCache";
import { writeWeatherDeviceCache } from "../../services/weatherCache";
import { REGIONAL_OFFICIAL_ALERTS_CACHE_KEY } from "../../services/officialAlertsCache";
import {
  createHomeWeatherState,
  loadHomeData,
  loadHomeEvents,
  loadHomeWeather,
  hydrateHomeWeatherFromBackgroundPrefetch,
  mergeHomeDataState,
  readInitialHomeData,
} from "./homeDataController";

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
    items,
  };
}

function cacheEntry(data, savedAt = 1000) {
  return JSON.stringify({ savedAt, data });
}

describe("home data controller", () => {
  it("does not throw while hydrating an unsupported foreign weather location", () => {
    const location = {
      city: "Nova Gorica",
      countryCode: "SI",
      region: "Gorizia",
      lat: 45.956,
      lon: 13.648,
    };

    expect(() => readInitialHomeData(location, {
      eventsCacheReader: () => null,
      storage: createStorage(),
    })).not.toThrow();
    expect(readInitialHomeData(location, {
      eventsCacheReader: () => null,
      storage: createStorage(),
    })).toBeNull();
  });

  it("keeps weather and editorial event locations independent", async () => {
    const weatherLocation = { city: "Roma", region: "Lazio", countryCode: "IT" };
    const eventsLocation = { city: "Pordenone", region: "Friuli Venezia Giulia" };
    const weatherFetcher = vi.fn().mockResolvedValue({
      city: "Roma",
      current: { condition: "Sereno", temperature: 20, weathercode: 0 },
      forecast: { daily: [] },
    });
    const eventsFetcher = vi.fn().mockResolvedValue({
      events: [],
      total: 0,
      cacheStatus: "fresh",
      isRefreshing: false,
      isPartial: false,
      shouldRetry: false,
    });

    const data = await loadHomeData(weatherLocation, {
      eventsLocation,
      weatherFetcher,
      eventsFetcher,
    });

    expect(weatherFetcher).toHaveBeenCalledWith(weatherLocation, expect.any(Object));
    expect(eventsFetcher).toHaveBeenCalledWith(eventsLocation, { limit: HOME_EVENTS_LIMIT, retry: 0 });
    expect(data).toMatchObject({ location: weatherLocation, editorialLocation: eventsLocation });
  });

  it("uses fresh weather cache immediately while refreshing events", async () => {
    const storage = createStorage();
    const location = { city: "Udine" };
    const weatherFetcher = vi.fn();
    const eventsFetcher = vi.fn().mockResolvedValue({
      events: [{ id: "fresh-event" }],
      total: 1,
      cacheStatus: "fresh",
      isRefreshing: false,
      isPartial: false,
      shouldRetry: false,
    });

    writeWeatherDeviceCache(
      location,
      {
        city: "Udine",
        current: { condition: "Sereno", weathercode: 0, temperature: 18, is_day: 1 },
        forecast: { daily: [] },
        officialAlerts: null,
        osmerAudit: null,
        updatedAt: "2026-06-21T10:00:00.000Z",
      },
      { storage, now: () => 1000 },
    );
    writeEventsCache(location, [{ id: "event-1" }], { storage, now: () => 1000 });

    const data = await loadHomeData(location, {
      storage,
      now: () => 1000,
      weatherFetcher,
      eventsFetcher,
    });

    expect(weatherFetcher).not.toHaveBeenCalled();
    expect(eventsFetcher).toHaveBeenCalledWith(location, { limit: HOME_EVENTS_LIMIT, retry: 0 });
    expect(data.weather).toMatchObject({
      status: "cache",
      fromCache: true,
      updatedAt: "2026-06-21T10:00:00.000Z",
    });
    expect(data.weather.current.temperature).toBe(18);
    expect(data.events).toMatchObject({
      status: "fresh",
      fromCache: false,
      loadedLimit: FULL_EVENTS_LIMIT,
      total: 1,
      items: [{ id: "fresh-event" }],
    });
    expect(data.ok).toBe(true);
  });

  it("fetches weather and events when cache is missing, then writes cache payloads", async () => {
    const storage = createStorage();
    const location = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };
    const weatherFetcher = vi.fn().mockResolvedValue({
      city: "Pordenone",
      current: { condition: "Pioggia debole", weathercode: 61, temperature: 11, is_day: 1 },
      forecast: { daily: [{ date: "2026-06-21" }] },
      officialAlerts: [{ id: "alert-1" }],
      osmerAudit: { storage_active: "firestore" },
    });
    const eventsFetcher = vi.fn().mockResolvedValue({
      events: [{ id: "event-1" }],
      total: 1,
      cacheStatus: "fresh",
      isRefreshing: false,
      isPartial: false,
      shouldRetry: false,
    });

    const data = await loadHomeData(location, {
      storage,
      now: () => 2000,
      nowIso: () => "2026-06-21T11:00:00.000Z",
      weatherFetcher,
      eventsFetcher,
    });

    expect(weatherFetcher).toHaveBeenCalledWith(location, {
      force: false,
      now: expect.any(Function),
      storage,
    });
    expect(eventsFetcher).toHaveBeenCalledWith(location, { limit: HOME_EVENTS_LIMIT, retry: 0 });
    expect(data.weather).toMatchObject({
      status: "fresh",
      city: "Pordenone",
      updatedAt: "2026-06-21T11:00:00.000Z",
      officialAlerts: [{ id: "alert-1" }],
      osmerAudit: { storage_active: "firestore" },
    });
    expect(data.weather.current.semantic.key).toBe("drizzle");
    expect(data.events).toMatchObject({
      status: "fresh",
      loadedLimit: FULL_EVENTS_LIMIT,
      cacheStatus: "fresh",
      items: [{ id: "event-1" }],
    });
    expect(storage.setItem).toHaveBeenCalled();
  });

  it("salva e inoltra l'arricchimento CAMS senza ricaricare il meteo ICON", async () => {
    const location = { city: "Pordenone" };
    const weatherCacheReader = vi.fn(() => null);
    const weatherCacheWriter = vi.fn();
    let publishCams;
    let publishCamsFailure;
    const weatherFetcher = vi.fn((_location, options) => {
      publishCams = options.onCamsUpdate;
      publishCamsFailure = options.onCamsFailure;
      return {
        city: "Pordenone",
        current: {
          condition: "Sereno",
          temperature: 17,
          data_quality: { cams_status: "pending" },
        },
        forecast: { daily: [] },
        officialAlerts: null,
        osmerAudit: null,
      };
    });
    const onCamsUpdate = vi.fn();
    const onCamsFailure = vi.fn();

    const initial = await loadHomeWeather(location, {
      deferCams: true,
      now: () => 2_000,
      nowIso: () => "2026-09-03T10:00:00.000Z",
      onCamsUpdate,
      onCamsFailure,
      storage: createStorage(),
      weatherCacheReader,
      weatherCacheWriter,
      weatherFetcher,
    });

    expect(initial.rawCurrent.data_quality.cams_status).toBe("pending");
    expect(weatherFetcher).toHaveBeenCalledOnce();
    expect(weatherFetcher).toHaveBeenCalledWith(location, expect.objectContaining({
      deferCams: true,
      onCamsFailure: expect.any(Function),
      onCamsUpdate: expect.any(Function),
    }));
    const lifecycle = { lifecycle: "intermediate", reason: "revocation" };
    publishCams({
      city: "Pordenone",
      current: {
        condition: "Sereno",
        temperature: 17,
        data_quality: { cams_status: "fresh" },
      },
      forecast: { daily: [] },
      officialAlerts: null,
      osmerAudit: null,
    }, lifecycle);

    expect(onCamsUpdate).toHaveBeenCalledOnce();
    expect(onCamsUpdate.mock.calls[0][0].rawCurrent.data_quality.cams_status).toBe("fresh");
    expect(onCamsUpdate.mock.calls[0][1]).toBe(lifecycle);
    expect(weatherCacheWriter).toHaveBeenCalledTimes(2);
    expect(weatherCacheWriter.mock.calls[1][1]).toMatchObject({
      current: { data_quality: { cams_status: "fresh" } },
      updatedAt: "2026-09-03T10:00:00.000Z",
    });
    const durabilityError = Object.assign(new Error("journal non persistito"), {
      code: "CAMS_REVOCATION_PERSIST_FAILED",
    });
    publishCamsFailure(durabilityError);
    expect(onCamsFailure).toHaveBeenCalledWith(durabilityError);
  });

  it("non lascia che un risultato pending tardivo sovrascriva un CAMS gia completato", async () => {
    const location = { city: "Pordenone" };
    const weatherCacheWriter = vi.fn();
    const enrichedPayload = {
      city: "Pordenone",
      current: {
        condition: "Sereno",
        temperature: 17,
        data_quality: { cams_status: "fresh" },
      },
      forecast: { daily: [] },
    };
    const weatherFetcher = vi.fn(async (_location, options) => {
      options.onCamsUpdate(enrichedPayload);
      return {
        ...enrichedPayload,
        current: {
          ...enrichedPayload.current,
          data_quality: { cams_status: "pending" },
        },
      };
    });

    const result = await loadHomeWeather(location, {
      deferCams: true,
      weatherCacheReader: vi.fn(() => null),
      weatherCacheWriter,
      weatherFetcher,
    });

    expect(result.rawCurrent.data_quality.cams_status).toBe("fresh");
    expect(weatherCacheWriter.mock.calls.at(-1)[1].current.data_quality.cams_status).toBe("fresh");
  });

  it("propaga al controller Home il candidato meteo non committato mantenendo i dati visibili", async () => {
    const payload = {
      city: "Pordenone",
      current: {
        condition: "Sereno",
        temperature: 17,
        cache: {
          status: "fresh",
          runtime_fallback: true,
          runtime_fallback_source: "candidate_not_committed",
          runtime_fallback_code: "CACHE_PERSIST_FAILED",
        },
        data_quality: {
          flags: [
            "runtime_candidate_not_committed",
            "runtime_refresh_failed_bundle_retained",
          ],
        },
      },
      forecast: { daily: [] },
    };
    const weather = await loadHomeWeather({ city: "Pordenone" }, {
      force: true,
      weatherCacheReader: vi.fn(() => null),
      weatherCacheWriter: vi.fn(),
      weatherFetcher: vi.fn().mockResolvedValue(payload),
    });

    expect(weather.current.temperature).toBe(17);
    expect(weather.rawCurrent.cache).toMatchObject({
      runtime_fallback_source: "candidate_not_committed",
      runtime_fallback_code: "CACHE_PERSIST_FAILED",
    });
    expect(weather.rawCurrent.data_quality.flags)
      .toContain("runtime_candidate_not_committed");
  });

  it("falls back to stale weather cache when refresh fails", async () => {
    const location = { city: "Udine" };
    const staleWeather = {
      city: "Udine",
      current: { condition: "Sereno", weathercode: 0, temperature: 20 },
      forecast: { daily: [] },
      updatedAt: "old",
    };
    const storage = createStorage({
      "weatherBootstrapCache:v3:udine|city|city": cacheEntry(staleWeather, 1000),
    });

    const weather = await loadHomeWeather(location, {
      storage,
      now: () => 1000 + 10 * 60 * 1000,
      weatherFetcher: vi.fn().mockRejectedValue(new Error("Risposta meteo non valida")),
    });

    expect(weather).toMatchObject({
      status: "stale",
      fromCache: true,
      isStale: true,
      error: "Risposta meteo non valida",
    });
    expect(weather.current.temperature).toBe(20);
  });

  it("keeps the last known Home weather visible when refresh fails after a long time", async () => {
    const location = { city: "Udine" };
    const oldWeather = {
      city: "Udine",
      current: { condition: "Sereno", weathercode: 0, temperature: 20 },
      forecast: { daily: [] },
      updatedAt: "too-old",
    };
    const storage = createStorage({
      "weatherBootstrapCache:v3:udine|city|city": cacheEntry(oldWeather, 1000),
    });

    const weather = await loadHomeWeather(location, {
      storage,
      now: () => 1000 + 24 * 60 * 60 * 1000,
      weatherFetcher: vi.fn().mockRejectedValue(new Error("Risposta meteo non valida")),
    });

    expect(weather).toMatchObject({
      status: "stale",
      current: { temperature: 20 },
      fromCache: true,
      isStale: true,
      error: "Risposta meteo non valida",
    });
  });

  it("keeps events visible from cache when a forced refresh fails", async () => {
    const location = { city: "Udine" };
    const storage = createStorage();
    writeEventsCache(location, [{ id: "cached" }], { storage, now: () => 1000 });

    const events = await loadHomeEvents(location, {
      force: true,
      storage,
      now: () => 1000,
      eventsFetcher: vi.fn().mockRejectedValue(new Error("Risposta eventi non valida")),
    });

    expect(events).toMatchObject({
      status: "stale",
      fromCache: true,
      loadedLimit: FULL_EVENTS_LIMIT,
      error: "Risposta eventi non valida",
      items: [{ id: "cached" }],
    });
  });

  it("does not cache refreshing or partial event payloads", async () => {
    const storage = createStorage();
    const location = { city: "Udine" };
    const events = await loadHomeEvents(location, {
      storage,
      now: () => 1000,
      eventsFetcher: vi.fn().mockResolvedValue({
        events: [],
        total: 0,
        cacheStatus: "refreshing",
        isRefreshing: true,
        isPartial: false,
        shouldRetry: true,
      }),
    });

    expect(events).toMatchObject({
      status: "fresh",
      cacheStatus: "refreshing",
      isRefreshing: true,
      shouldRetry: true,
    });
    expect(storage.items.has(getEventsCacheKey(location, FULL_EVENTS_LIMIT))).toBe(false);
  });

  it("forwards and preserves the retry count for pending Home events", async () => {
    const storage = createStorage();
    const location = { city: "Udine" };
    const eventsFetcher = vi.fn().mockResolvedValue({
      events: [],
      total: 0,
      cacheStatus: "refreshing",
      isRefreshing: true,
      isPartial: false,
      shouldRetry: true,
    });

    const events = await loadHomeEvents(location, {
      eventsFetcher,
      retry: 3,
      storage,
    });

    expect(eventsFetcher).toHaveBeenCalledWith(location, {
      limit: HOME_EVENTS_LIMIT,
      retry: 3,
    });
    expect(events).toMatchObject({ retry: 3, shouldRetry: true });
  });

  it("merges independently loaded Home slices without inventing missing content", () => {
    const location = { city: "Udine" };
    const events = createEventsCachePayload([{ id: "event-1" }]);
    const merged = mergeHomeDataState(null, location, { events });

    expect(merged).toMatchObject({ location, events, ok: true });
    expect(merged.weather).toBeUndefined();
  });

  it("keeps cached Home events visible when the backend is still refreshing", async () => {
    const storage = createStorage();
    const location = { city: "Udine" };
    writeEventsCache(location, [{ id: "cached-event" }], { storage, now: () => 1000 });

    const events = await loadHomeEvents(location, {
      storage,
      now: () => 1000,
      eventsFetcher: vi.fn().mockResolvedValue({
        events: [],
        total: 0,
        cacheStatus: "refreshing",
        isRefreshing: true,
        isPartial: false,
        shouldRetry: true,
      }),
    });

    expect(events).toMatchObject({
      cacheStatus: "refreshing",
      fromCache: true,
      isRefreshing: true,
      items: [{ id: "cached-event" }],
      loadedLimit: FULL_EVENTS_LIMIT,
      shouldRetry: true,
    });
  });

  it("uses a canonical partial Home response instead of an older event contract", async () => {
    const storage = createStorage();
    const location = { city: "Udine" };
    writeEventsCache(location, [{ id: "old-duplicate" }], {
      contractVersion: "canonical-events-v1",
      storage,
      now: () => 1000,
    });

    const events = await loadHomeEvents(location, {
      storage,
      now: () => 1000,
      eventsFetcher: vi.fn().mockResolvedValue({
        events: [{ id: "canonical-event" }],
        total: 1,
        cacheStatus: "partial",
        contractVersion: "canonical-events-v2",
        isRefreshing: false,
        isPartial: true,
        shouldRetry: true,
      }),
    });

    expect(events).toMatchObject({
      contractVersion: "canonical-events-v2",
      fromCache: false,
      isPartial: true,
      items: [{ id: "canonical-event" }],
    });
  });

  it("keeps a legacy home events cache visible if refresh fails", async () => {
    const storage = createStorage({
      [getEventsCacheKey("Udine", HOME_EVENTS_LIMIT)]: cacheEntry(createEventsCachePayload([{ id: "legacy-home" }])),
    });

    const events = await loadHomeEvents("Udine", {
      storage,
      now: () => 1000,
      eventsFetcher: vi.fn().mockRejectedValue(new Error("Risposta eventi non valida")),
    });

    expect(events).toMatchObject({
      error: "Risposta eventi non valida",
      fromCache: true,
      loadedLimit: HOME_EVENTS_LIMIT,
      status: "stale",
      items: [{ id: "legacy-home" }],
    });
  });

  it("hydrates initial Home data from device caches without network calls", () => {
    const location = { city: "Pordenone" };
    const storage = createStorage();

    writeWeatherDeviceCache(
      location,
      {
        city: "Pordenone",
        current: { condition: "Sereno", weathercode: 0, temperature: 21 },
        forecast: { daily: [] },
        updatedAt: "2026-06-28T10:00:00.000Z",
      },
      { storage, now: () => 1000 },
    );
    writeEventsCache(location, [{ id: "event-1" }], { storage, now: () => 1000 });

    const data = readInitialHomeData(location, { storage, now: () => 1000 });

    expect(data).toMatchObject({
      location,
      weather: {
        city: "Pordenone",
        fromCache: true,
        status: "cache",
      },
      events: {
        fromCache: true,
        loadedLimit: FULL_EVENTS_LIMIT,
        items: [{ id: "event-1" }],
      },
      ok: true,
    });
  });

  it("hydrates the verified autonomous bundle synchronously before the network refresh", () => {
    const location = {
      city: "Pordenone",
      municipality: { istatCode: "093033", name: "Pordenone" },
    };
    const storage = createStorage();
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const bootstrapCacheReader = vi.fn().mockReturnValue({
      city: "Pordenone",
      current: {
        condition: "Sereno",
        primary_source: "icon2i_local_pilot",
        temperature: 17,
        weathercode: 0,
      },
      forecast: { daily: [] },
      officialAlerts: null,
      osmerAudit: null,
    });
    const weatherCacheReader = vi.fn().mockReturnValue({
      city: "Pordenone",
      current: { condition: "Pioggia", temperature: 99, weathercode: 61 },
      forecast: { daily: [] },
    });

    const data = readInitialHomeData(location, {
      bootstrapCacheReader,
      eventsCacheReader: vi.fn().mockReturnValue(null),
      now,
      storage,
      weatherCacheReader,
    });

    expect(bootstrapCacheReader).toHaveBeenCalledWith(location, { now, storage });
    expect(data).toMatchObject({
      location,
      weather: {
        city: "Pordenone",
        current: { temperature: 17 },
        fromCache: true,
        status: "cache",
      },
      ok: true,
    });
  });

  it("hydrates initial Home weather from the last snapshot regardless of its age", () => {
    const location = { city: "Pordenone" };
    const oldWeather = {
      city: "Pordenone",
      current: { condition: "Sereno", weathercode: 0, temperature: 21 },
      forecast: { daily: [] },
      updatedAt: "old",
    };
    const storage = createStorage({
      "weatherBootstrapCache:v3:pordenone|city|city": cacheEntry(oldWeather, 1000),
    });

    expect(readInitialHomeData(location, {
      storage,
      now: () => 1000 + 24 * 60 * 60 * 1000,
    })).toMatchObject({
      weather: {
        current: { temperature: 21 },
        fromCache: true,
        isStale: false,
        status: "cache",
      },
    });
  });

  it("hydrates a cold Home start with the FVG regional alert even when the municipal weather cache lacks it", () => {
    const location = { city: "Barcis" };
    const regionalAlert = {
      active: true,
      alerts: [{
        id: "allerta-regionale-24-del-2026",
        level: "arancione",
        valid_to: "2026-08-21T23:59:00+02:00",
      }],
      source_mode: "official_widget",
    };
    const storage = createStorage({
      "weatherBootstrapCache:v3:barcis|city|city": cacheEntry({
        city: "Barcis",
        current: { condition: "Sereno", weathercode: 0, temperature: 21 },
        forecast: { daily: [] },
        officialAlerts: null,
        updatedAt: "old",
      }, 1000),
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(regionalAlert, 1000),
    });
    const now = new Date("2026-08-20T18:00:00.000Z").getTime();

    expect(readInitialHomeData(location, {
      storage,
      now: () => now,
    })).toMatchObject({
      weather: {
        city: "Barcis",
        fromCache: true,
        officialAlerts: regionalAlert,
        status: "cache",
      },
    });
  });

  it("ignores the retired Open-Meteo native background prefetch by default", async () => {
    const storage = createStorage();
    const location = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };
    const weather = await hydrateHomeWeatherFromBackgroundPrefetch(location, {
      now: () => 20_000,
      prefetchReader: vi.fn().mockResolvedValue({
        available: true,
        city: "Pordenone",
        lat: 45.957,
        lon: 12.661,
        savedAt: 10_000,
        trigger: "geofence_exit",
        payload: {
          city: "Pordenone",
          current: { condition: "Sereno", weathercode: 0, temperature: 22 },
          forecast: { daily: [] },
          official_alerts: [{ id: "alert-1" }],
        },
      }),
      storage,
    });

    expect(weather).toBeNull();
    expect(readInitialHomeData(location, { storage, now: () => 20_000 })).toBeNull();
  });

  it("ignores the native Open-Meteo prefetch when the app is configured autonomous", async () => {
    vi.stubEnv("VITE_WEATHER_PROVIDER_PRIMARY", "autonomous");
    const prefetchReader = vi.fn();
    const weatherCacheWriter = vi.fn();
    try {
      await expect(hydrateHomeWeatherFromBackgroundPrefetch({ city: "Pordenone" }, {
        prefetchReader,
        weatherCacheWriter,
      })).resolves.toBeNull();
      expect(prefetchReader).not.toHaveBeenCalled();
      expect(weatherCacheWriter).not.toHaveBeenCalled();
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it("does not import alerts from the retired Android prefetch", async () => {
    const location = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };
    const regionalAlert = {
      active: true,
      alerts: [{
        id: "allerta-regionale-24-del-2026",
        level: "arancione",
        valid_to: "2026-08-21T23:59:00+02:00",
      }],
      source_mode: "official_widget",
    };
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(regionalAlert, 1000),
    });
    const now = new Date("2026-08-20T18:00:00.000Z").getTime();

    const weather = await hydrateHomeWeatherFromBackgroundPrefetch(location, {
      now: () => now,
      prefetchReader: vi.fn().mockResolvedValue({
        available: true,
        city: "Pordenone",
        lat: 45.957,
        lon: 12.661,
        savedAt: now - 1000,
        trigger: "periodic",
        payload: {
          city: "Pordenone",
          current: { condition: "Sereno", weathercode: 0, temperature: 22 },
          forecast: { daily: [] },
          official_alerts: {
            active: false,
            alerts: [],
            cache: { status: "unavailable" },
            error: "official_alerts_unavailable",
            source_mode: "official_alerts_unavailable_fast_fallback",
          },
        },
      }),
      storage,
    });

    expect(weather).toBeNull();
    expect(storage.getItem(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY)).toBe(cacheEntry(regionalAlert, 1000));
  });

  it("retains the backend stale flag without replacing official alerts", () => {
    const officialAlerts = { active: true, alerts: [{ id: "official-yellow", level: "gialla" }] };
    const state = createHomeWeatherState({
      current: { temperature: 24, primary_source: "open_meteo", data_quality: { status: "stale" } },
      forecast: { daily: [] },
      officialAlerts,
    });

    expect(state).toMatchObject({ status: "stale", isStale: true, current: { temperature: 24 } });
    expect(state.officialAlerts).toBe(officialAlerts);
  });

  it.each([
    { primary_source: "arpa_fvg_osmer" },
    { source: { active: "arpa_fvg_osmer" } },
  ])("ignores a pre-upgrade mixed Android prefetch: %j", async (source) => {
    const weatherCacheWriter = vi.fn();
    const weather = await hydrateHomeWeatherFromBackgroundPrefetch({ city: "Udine" }, {
      prefetchReader: vi.fn().mockResolvedValue({
        available: true, city: "Udine", savedAt: 10_000,
        payload: { current: { temperature: 30, ...source }, forecast: { daily: [] } },
      }),
      weatherCacheWriter,
    });

    expect(weather).toBeNull();
    expect(weatherCacheWriter).not.toHaveBeenCalled();
  });

  it("ignores a background weather prefetch from a different area", async () => {
    const weatherCacheWriter = vi.fn();
    const weather = await hydrateHomeWeatherFromBackgroundPrefetch(
      { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      {
        prefetchReader: vi.fn().mockResolvedValue({
          available: true,
          city: "Udine",
          lat: 46.0619,
          lon: 13.2378,
          savedAt: 10_000,
          payload: { current: {}, forecast: {} },
        }),
        weatherCacheWriter,
      },
    );

    expect(weather).toBeNull();
    expect(weatherCacheWriter).not.toHaveBeenCalled();
  });

  it("does not import a retired native prefetch matched only by city", async () => {
    const weatherCacheWriter = vi.fn();
    const weather = await hydrateHomeWeatherFromBackgroundPrefetch(
      { city: "Pordenone" },
      {
        prefetchReader: vi.fn().mockResolvedValue({
          available: true,
          city: "Pordenone",
          lat: 45.9567,
          lon: 12.6605,
          savedAt: 10_000,
          payload: {
            city: "Pordenone",
            current: { temperature: 22 },
            forecast: { daily: [] },
          },
        }),
        weatherCacheEntryReader: vi.fn().mockReturnValue(null),
        weatherCacheWriter,
      },
    );

    expect(weather).toBeNull();
    expect(weatherCacheWriter).not.toHaveBeenCalled();
  });

  it("strips alerts from cached Home weather when the alert runtime owns them", async () => {
    const location = { city: "Pordenone" };
    const regionalAlert = {
      active: true,
      alerts: [{ id: "regional-orange", level: "arancione" }],
      source_mode: "official_widget",
    };
    const cachedWeather = {
      city: "Pordenone",
      current: { condition: "Sereno", temperature: 22, weathercode: 0 },
      forecast: { daily: [] },
      officialAlerts: { active: true, alerts: [{ id: "embedded-yellow", level: "gialla" }] },
    };
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(regionalAlert),
    });
    const regionalCacheBefore = storage.items.get(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY);
    const weatherFetcher = vi.fn();
    const weatherCacheWriter = vi.fn();

    const weather = await loadHomeWeather(location, {
      manageOfficialAlerts: false,
      now: () => 2_000,
      storage,
      weatherCacheReader: vi.fn().mockReturnValue(cachedWeather),
      weatherCacheWriter,
      weatherFetcher,
    });

    expect(weather).toMatchObject({ status: "cache", officialAlerts: null });
    expect(weatherFetcher).not.toHaveBeenCalled();
    expect(weatherCacheWriter).not.toHaveBeenCalled();
    expect(storage.items.get(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY)).toBe(regionalCacheBefore);
    expect(
      storage.setItem.mock.calls.filter(([key]) => key === REGIONAL_OFFICIAL_ALERTS_CACHE_KEY),
    ).toHaveLength(0);
  });

  it("strips alerts from fresh Home weather without changing the regional alert cache", async () => {
    const location = { city: "Pordenone" };
    const regionalAlert = {
      active: true,
      alerts: [{ id: "regional-orange", level: "arancione" }],
      source_mode: "official_widget",
    };
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(regionalAlert),
    });
    const regionalCacheBefore = storage.items.get(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY);
    const weatherCacheWriter = vi.fn();
    const weatherFetcher = vi.fn().mockResolvedValue({
      city: "Pordenone",
      current: { condition: "Sereno", temperature: 23, weathercode: 0 },
      forecast: { daily: [] },
      officialAlerts: { active: true, alerts: [{ id: "incoming-red", level: "rossa" }] },
    });

    const weather = await loadHomeWeather(location, {
      force: true,
      manageOfficialAlerts: false,
      now: () => 2_000,
      nowIso: () => "2026-09-06T10:00:00.000Z",
      storage,
      weatherCacheReader: vi.fn().mockReturnValue(null),
      weatherCacheWriter,
      weatherFetcher,
    });

    expect(weather).toMatchObject({ status: "fresh", officialAlerts: null });
    expect(weatherCacheWriter).toHaveBeenCalledWith(
      location,
      expect.objectContaining({ officialAlerts: null }),
      { storage, now: expect.any(Function) },
    );
    expect(storage.items.get(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY)).toBe(regionalCacheBefore);
    expect(
      storage.setItem.mock.calls.filter(([key]) => key === REGIONAL_OFFICIAL_ALERTS_CACHE_KEY),
    ).toHaveLength(0);
  });
});
