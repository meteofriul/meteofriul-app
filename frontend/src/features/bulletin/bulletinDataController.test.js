import { describe, expect, it, vi } from "vitest";

import {
  createBulletinDataState,
  loadBulletinData,
  readCachedBulletinData,
  readInitialBulletinData,
  resolveOfficialAlerts,
} from "./bulletinDataController";
import { REGIONAL_OFFICIAL_ALERTS_CACHE_KEY } from "../../services/officialAlertsCache";

const NOW = new Date("2026-08-02T10:00:00.000Z").getTime();
const CACHE_KEY = "officialBulletinCache:v1:udine|city|city";
const LEGACY_CACHE_KEY = "weatherBootstrapCache:v2:udine|city|city";

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

function cacheEntry(data, savedAt = NOW) {
  return JSON.stringify({ savedAt, data });
}

function buildOfficialPayload(overrides = {}) {
  return {
    city: "Udine",
    forecast: {
      official: {
        it: {
          forecasts: [
            { date: "2026-08-02", text: "Sole" },
            { date: "2026-08-03", text: "Poco nuvoloso" },
          ],
        },
      },
    },
    officialAlerts: {
      active: false,
      alerts: [],
      source_mode: "github_actions_official_page",
    },
    osmerAudit: { storage_active: "firestore" },
    ...overrides,
  };
}

function buildOpenMeteoOnlyPayload() {
  return {
    city: "Udine",
    forecast: {
      forecast: [{ date: "2026-08-02", condition: "Sole", min_temp: 20, max_temp: 31 }],
      primary_source: "open_meteo",
    },
    officialAlerts: null,
  };
}

function buildStructuredOnlyPayload() {
  const areas9 = Object.fromEntries(
    Array.from({ length: 9 }, (_, index) => [
      `A${index + 1}`,
      { source_kind: "structured_xml" },
    ]),
  );

  return {
    city: "Udine",
    forecast: {
      osmer_structured: {
        days: [{ areas9, source_kind: "structured_xml", valid_date: "2026-08-02" }],
        source_kind: "structured_xml",
        source_status: "reachable_xml",
      },
    },
  };
}

function buildActiveAlert() {
  return {
    active: true,
    alerts: [{ id: "yellow", level: "gialla", valid_to: "2026-08-03T12:00:00+02:00" }],
    source_mode: "github_actions_official_page",
  };
}

describe("bulletin data controller", () => {
  it("uses fresh official bulletin cache before calling services", async () => {
    const location = { city: "Udine" };
    const cachedPayload = buildOfficialPayload({ updatedAt: "2026-08-02T09:59:00.000Z" });
    const storage = createStorage({
      [CACHE_KEY]: cacheEntry(cachedPayload),
    });
    const bulletinFetcher = vi.fn();

    const state = await loadBulletinData(location, {
      bulletinFetcher,
      now: () => NOW,
      storage,
    });

    expect(bulletinFetcher).not.toHaveBeenCalled();
    expect(state).toMatchObject({
      city: "Udine",
      error: null,
      fromCache: true,
      isStale: false,
      status: "cache",
      updatedAt: "2026-08-02T09:59:00.000Z",
    });
  });

  it("loads the dedicated bulletin service without current-weather requirements", async () => {
    const location = { city: "Udine" };
    const storage = createStorage();
    const bulletinFetcher = vi.fn().mockResolvedValue(buildOfficialPayload());

    const state = await loadBulletinData(location, {
      bulletinFetcher,
      force: true,
      now: () => NOW,
      nowIso: () => "2026-08-02T10:00:00.000Z",
      storage,
    });

    expect(bulletinFetcher).toHaveBeenCalledWith(location, {
      force: true,
      now: expect.any(Function),
    });
    expect(state).toMatchObject({
      city: "Udine",
      error: null,
      status: "fresh",
      officialAlerts: buildOfficialPayload().officialAlerts,
      osmerAudit: { storage_active: "firestore" },
      updatedAt: "2026-08-02T10:00:00.000Z",
    });
    expect(storage.setItem).toHaveBeenCalledWith(CACHE_KEY, expect.any(String));
  });

  it("returns an empty error state when location is missing", async () => {
    const state = await loadBulletinData("", {
      bulletinFetcher: vi.fn(),
    });

    expect(state).toMatchObject({
      error: "Localita bollettino mancante",
      forecast: null,
      status: "error",
    });
  });

  it("falls back to a still-valid official bulletin when refresh fails", async () => {
    const location = { city: "Udine" };
    const cachedPayload = buildOfficialPayload({ updatedAt: "old" });
    const storage = createStorage({
      [CACHE_KEY]: cacheEntry(cachedPayload, NOW - 10 * 60 * 1000),
    });

    const state = await loadBulletinData(location, {
      bulletinFetcher: vi.fn().mockRejectedValue(new Error("Risposta bollettino non valida")),
      now: () => NOW,
      storage,
    });

    expect(state).toMatchObject({
      error: "Risposta bollettino non valida",
      fromCache: true,
      isStale: true,
      status: "stale",
      updatedAt: "old",
    });
    expect(state.forecast).toEqual(cachedPayload.forecast);
  });

  it("keeps an older snapshot while at least one official forecast day is still current", () => {
    const location = { city: "Udine" };
    const cachedPayload = buildOfficialPayload({ updatedAt: "three-days-old" });
    const storage = createStorage({
      [CACHE_KEY]: cacheEntry(cachedPayload, NOW - 72 * 60 * 60 * 1000),
    });

    expect(readInitialBulletinData(location, {
      now: () => NOW,
      storage,
    })).toMatchObject({
      fromCache: true,
      isStale: true,
      updatedAt: "three-days-old",
    });
  });

  it("adds the regional FVG alert to a cold-start bulletin cache for another municipality", () => {
    const location = { city: "Udine" };
    const regionalAlert = buildActiveAlert();
    const cachedPayload = buildOfficialPayload({
      officialAlerts: null,
      updatedAt: "municipal-cache-without-alert",
    });
    const storage = createStorage({
      [CACHE_KEY]: cacheEntry(cachedPayload, NOW - 10 * 60 * 1000),
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(regionalAlert),
    });

    expect(readInitialBulletinData(location, {
      now: () => NOW,
      storage,
    })).toMatchObject({
      fromCache: true,
      officialAlerts: regionalAlert,
      updatedAt: "municipal-cache-without-alert",
    });
  });

  it("rejects a recent snapshot when every official forecast day has passed", () => {
    const location = { city: "Udine" };
    const cachedPayload = buildOfficialPayload({
      forecast: {
        official: {
          it: {
            forecasts: [{ date: "2026-08-01", text: "Sole" }],
          },
        },
      },
    });
    const storage = createStorage({
      [CACHE_KEY]: cacheEntry(cachedPayload),
    });

    expect(readInitialBulletinData(location, {
      now: () => NOW,
      storage,
    })).toBeNull();
  });

  it("hydrates once from the previous shared weather cache during migration", () => {
    const location = { city: "Udine" };
    const cachedPayload = buildOfficialPayload({ updatedAt: "legacy" });
    const storage = createStorage({
      [LEGACY_CACHE_KEY]: cacheEntry(cachedPayload),
    });

    expect(readCachedBulletinData(location, {
      now: () => NOW,
      storage,
    })).toMatchObject({
      fromCache: true,
      updatedAt: "legacy",
    });
  });

  it("accepts complete structured OSMER data when official text is temporarily absent", () => {
    const location = { city: "Udine" };
    const payload = buildStructuredOnlyPayload();
    const storage = createStorage({
      [CACHE_KEY]: cacheEntry(payload),
    });

    expect(readCachedBulletinData(location, {
      now: () => NOW,
      storage,
    })).toMatchObject({
      forecast: payload.forecast,
      fromCache: true,
    });
  });

  it("does not cache or display an Open-Meteo-only response as an official bulletin", async () => {
    const bulletinCacheWriter = vi.fn();
    const state = await loadBulletinData({ city: "Udine" }, {
      bulletinCacheReader: vi.fn().mockReturnValue(null),
      bulletinCacheWriter,
      bulletinFetcher: vi.fn().mockResolvedValue(buildOpenMeteoOnlyPayload()),
      force: true,
      now: () => NOW,
    });

    expect(state).toMatchObject({
      error: "Dati ufficiali OSMER mancanti o fuori validita",
      forecast: null,
      status: "error",
    });
    expect(bulletinCacheWriter).not.toHaveBeenCalled();
  });

  it("keeps the previous official cache when a refresh returns only Open-Meteo", async () => {
    const location = { city: "Udine" };
    const cachedPayload = buildOfficialPayload({ updatedAt: "official-cache" });
    const storage = createStorage({
      [CACHE_KEY]: cacheEntry(cachedPayload, NOW - 10 * 60 * 1000),
    });

    const state = await loadBulletinData(location, {
      bulletinFetcher: vi.fn().mockResolvedValue(buildOpenMeteoOnlyPayload()),
      force: true,
      now: () => NOW,
      storage,
    });

    expect(state).toMatchObject({
      fromCache: true,
      isStale: true,
      status: "stale",
      updatedAt: "official-cache",
    });
    expect(state.forecast).toEqual(cachedPayload.forecast);
  });

  it("keeps a previous active FVG alert when the new alert source is diagnostic", () => {
    const previous = buildActiveAlert();
    const diagnostic = {
      active: false,
      alerts: [],
      cache: { status: "stale" },
      source_mode: "github_actions_dpc_national_criticity_diagnostic",
    };

    expect(resolveOfficialAlerts(diagnostic, previous, { now: () => NOW })).toBe(previous);
  });

  it("keeps an unavailable observation when no active alert can be retained", () => {
    const unavailable = {
      active: false,
      alerts: [],
      cache: { status: "unavailable" },
      error: "official_alerts_unavailable",
      source_mode: "official_alerts_unavailable_fast_fallback",
    };
    const previousInactive = {
      active: false,
      alerts: [],
      source_mode: "github_actions_official_page",
    };

    expect(resolveOfficialAlerts(unavailable, null, { now: () => NOW })).toBe(unavailable);
    expect(resolveOfficialAlerts(unavailable, previousInactive, { now: () => NOW })).toBe(unavailable);
  });

  it("accepts a confirmed FVG no-alert state and clears the previous alert", () => {
    const confirmedInactive = {
      active: false,
      alerts: [],
      source_mode: "github_actions_official_page",
    };

    expect(resolveOfficialAlerts(confirmedInactive, buildActiveAlert(), {
      now: () => NOW,
    })).toBe(confirmedInactive);
  });

  it("keeps the data controller free from bulletin presentation copy", () => {
    const payload = buildOfficialPayload({
      city: "Pordenone",
      officialAlerts: { alerts: [{ id: "yellow", level: "gialla" }] },
    });

    expect(createBulletinDataState(payload)).toEqual({
      city: "Pordenone",
      error: null,
      forecast: payload.forecast,
      fromCache: false,
      isStale: false,
      officialAlerts: payload.officialAlerts,
      osmerAudit: payload.osmerAudit,
      raw: payload,
      status: "fresh",
      updatedAt: null,
    });
  });

  it("keeps alert reconciliation out of an OSMER-only refresh", async () => {
    const location = { city: "Udine" };
    const retainedRegionalAlert = buildActiveAlert();
    const incomingAlert = {
      active: true,
      alerts: [{ id: "orange", level: "arancione" }],
      source_mode: "official_widget",
    };
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(retainedRegionalAlert),
    });
    const regionalCacheBefore = storage.items.get(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY);
    const bulletinFetcher = vi.fn().mockResolvedValue(buildOfficialPayload({
      officialAlerts: incomingAlert,
    }));
    const bulletinCacheWriter = vi.fn();

    const state = await loadBulletinData(location, {
      bulletinCacheReader: vi.fn().mockReturnValue(null),
      bulletinCacheWriter,
      bulletinFetcher,
      force: true,
      includeAlerts: false,
      now: () => NOW,
      nowIso: () => "2026-08-02T10:00:00.000Z",
      storage,
    });

    expect(bulletinFetcher).toHaveBeenCalledWith(location, {
      force: true,
      includeAlerts: false,
      now: expect.any(Function),
    });
    expect(state).toMatchObject({ status: "fresh", officialAlerts: null });
    expect(bulletinCacheWriter).toHaveBeenCalledWith(
      location,
      expect.objectContaining({ officialAlerts: null }),
      { storage, now: expect.any(Function) },
    );
    expect(storage.items.get(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY)).toBe(regionalCacheBefore);
    expect(
      storage.setItem.mock.calls.filter(([key]) => key === REGIONAL_OFFICIAL_ALERTS_CACHE_KEY),
    ).toHaveLength(0);
  });

  it("keeps embedded alerts out of an OSMER-only cold-start cache", () => {
    const location = { city: "Udine" };
    const storage = createStorage({
      [CACHE_KEY]: cacheEntry(buildOfficialPayload({
        officialAlerts: buildActiveAlert(),
        updatedAt: "cached-osmer",
      })),
    });

    const state = readInitialBulletinData(location, {
      includeAlerts: false,
      now: () => NOW,
      storage,
    });

    expect(state).toMatchObject({
      fromCache: true,
      officialAlerts: null,
      updatedAt: "cached-osmer",
    });
    expect(storage.items.has(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY)).toBe(false);
    expect(
      storage.setItem.mock.calls.filter(([key]) => key === REGIONAL_OFFICIAL_ALERTS_CACHE_KEY),
    ).toHaveLength(0);
  });

  it("keeps embedded alerts out of fresh and fallback OSMER-only cache reads", async () => {
    const location = { city: "Udine" };
    const storage = createStorage({
      [CACHE_KEY]: cacheEntry(buildOfficialPayload({
        officialAlerts: buildActiveAlert(),
        updatedAt: "cached-osmer",
      })),
    });

    const freshState = await loadBulletinData(location, {
      bulletinFetcher: vi.fn(),
      includeAlerts: false,
      now: () => NOW,
      storage,
    });
    const fallbackState = await loadBulletinData(location, {
      bulletinFetcher: vi.fn().mockRejectedValue(new Error("offline")),
      force: true,
      includeAlerts: false,
      now: () => NOW,
      storage,
    });

    expect(freshState).toMatchObject({ fromCache: true, officialAlerts: null });
    expect(fallbackState).toMatchObject({
      error: "offline",
      fromCache: true,
      officialAlerts: null,
      status: "stale",
    });
    expect(storage.items.has(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY)).toBe(false);
    expect(
      storage.setItem.mock.calls.filter(([key]) => key === REGIONAL_OFFICIAL_ALERTS_CACHE_KEY),
    ).toHaveLength(0);
  });
});
