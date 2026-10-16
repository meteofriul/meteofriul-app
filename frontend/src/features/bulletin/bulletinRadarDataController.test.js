import { describe, expect, it, vi } from "vitest";

import {
  createBulletinRadarDataState,
  loadBulletinRadarData,
  readInitialBulletinRadarData,
} from "./bulletinRadarDataController";
import {
  getRadarCacheKey,
  RADAR_STORAGE_MAX_AGE_MS,
} from "../../services/radarCache";

const NOW = 2_000_000_000;

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => values.get(key) || null),
    removeItem: vi.fn((key) => values.delete(key)),
    setItem: vi.fn((key, value) => values.set(key, value)),
  };
}

function buildPayload(overrides = {}) {
  return {
    available: true,
    city: "Pordenone",
    products: [
      {
        id: "rain",
        layer: "radar:sri",
        product_type: "SRI",
        time: "2026-08-03T07:10:00Z",
      },
    ],
    tiles: { base_url: "https://tiles.example.test" },
    ...overrides,
  };
}

describe("bulletin radar data controller", () => {
  it("keeps device radar snapshots for at most thirty minutes", () => {
    expect(RADAR_STORAGE_MAX_AGE_MS).toBe(30 * 60 * 1000);
  });

  it("uses a fresh device cache before calling the radar endpoint", async () => {
    const payload = buildPayload();
    const radarFetcher = vi.fn();

    const result = await loadBulletinRadarData({ city: "Pordenone" }, {
      radarCacheReader: vi.fn().mockReturnValue(payload),
      radarFetcher,
    });

    expect(result).toMatchObject({ fromCache: true, status: "cache" });
    expect(radarFetcher).not.toHaveBeenCalled();
  });

  it("does not read cache or fetch Italian radar when the selected territory is unsupported", async () => {
    const radarCacheReader = vi.fn();
    const radarFetcher = vi.fn();

    expect(readInitialBulletinRadarData({ city: "Lubiana" }, {
      enabled: false,
      radarCacheReader,
    })).toMatchObject({ payload: null, status: "empty" });
    await expect(loadBulletinRadarData({ city: "Lubiana" }, {
      enabled: false,
      radarCacheReader,
      radarFetcher,
    })).resolves.toMatchObject({ payload: null, status: "empty" });

    expect(radarCacheReader).not.toHaveBeenCalled();
    expect(radarFetcher).not.toHaveBeenCalled();
  });

  it("rejects an obsolete WMS-only snapshot", async () => {
    const oldPayload = buildPayload({
      tiles: undefined,
      wms: { url: "https://radar.example.test/wms" },
    });

    const result = await loadBulletinRadarData({ city: "Pordenone" }, {
      radarCacheReader: vi.fn().mockReturnValue(oldPayload),
      radarFetcher: vi.fn().mockRejectedValue(new Error("offline")),
    });

    expect(result).toMatchObject({ fromCache: false, status: "error" });
  });

  it("keeps a recent cached radar when refresh fails", async () => {
    const payload = buildPayload();
    const radarCacheReader = vi.fn()
      .mockReturnValueOnce(null)
      .mockReturnValueOnce(payload);

    const result = await loadBulletinRadarData({ city: "Pordenone" }, {
      force: true,
      radarCacheReader,
      radarFetcher: vi.fn().mockRejectedValue(new Error("offline")),
    });

    expect(result).toMatchObject({
      error: "offline",
      fromCache: true,
      isStale: true,
      status: "stale",
    });
    expect(result.payload).toEqual(payload);
  });

  it("does not revive an expired radar snapshot when the endpoint is offline", async () => {
    const location = { city: "Pordenone" };
    const storage = createStorage({
      [getRadarCacheKey(location)]: JSON.stringify({
        data: buildPayload(),
        savedAt: NOW - RADAR_STORAGE_MAX_AGE_MS - 1,
      }),
    });

    const result = await loadBulletinRadarData(location, {
      force: true,
      now: () => NOW,
      radarFetcher: vi.fn().mockRejectedValue(new Error("offline")),
      storage,
    });

    expect(result).toEqual({
      error: "offline",
      fromCache: false,
      isStale: false,
      payload: null,
      status: "error",
    });
  });

  it("does not turn a radar failure into a bulletin failure", () => {
    expect(createBulletinRadarDataState(null, { error: new Error("offline") })).toEqual({
      error: "offline",
      fromCache: false,
      isStale: false,
      payload: null,
      status: "error",
    });
  });

  it("reads stale startup data explicitly", () => {
    const payload = buildPayload();
    const radarCacheReader = vi.fn()
      .mockReturnValueOnce(null)
      .mockReturnValueOnce(payload);

    expect(readInitialBulletinRadarData({ city: "Pordenone" }, {
      radarCacheReader,
    })).toMatchObject({ fromCache: true, isStale: true, status: "stale" });
  });
});
