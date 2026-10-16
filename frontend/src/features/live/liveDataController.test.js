import { describe, expect, it, vi } from "vitest";

import {
  createEmptyLiveDataState,
  LIVE_AUTO_REFRESH_INTERVAL_MS,
  loadLiveData,
  readInitialLiveData,
} from "./liveDataController";
import {
  LIVE_COMMUNITY_CACHE_KEY,
  LIVE_COMMUNITY_RECHECK_MS,
  LIVE_COMMUNITY_STORAGE_MAX_AGE_MS,
  LIVE_WEBCAM_CACHE_KEY,
  LIVE_WEBCAM_RECHECK_MS,
  LIVE_WEBCAM_STORAGE_MAX_AGE_MS,
} from "../../services/liveCache";

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => values.get(key) || null),
    removeItem: vi.fn((key) => values.delete(key)),
    setItem: vi.fn((key, value) => values.set(key, value)),
  };
}

const webcamPayload = {
  ok: true,
  webcams: [{ id: "sacile", imageUrl: "https://images.example.test/sacile.jpg" }],
};
const communityPayload = { reports: [], map_groups: [] };

function cacheEntry(data, savedAt = 1000) {
  return JSON.stringify({ data, savedAt });
}

describe("live data controller", () => {
  it("still waits for both sources when a progressive observer throws", async () => {
    let finishCommunity;
    const settled = vi.fn();
    const onUpdate = vi.fn(() => { throw new Error("observer failed"); });
    const request = loadLiveData({
      storage: createStorage(),
      onUpdate,
      webcamFetcher: async () => webcamPayload,
      communityFetcher: () => new Promise(resolve => { finishCommunity = resolve; }),
    });
    request.then(settled);
    await vi.waitFor(() => expect(onUpdate).toHaveBeenCalledTimes(1));
    expect(settled).not.toHaveBeenCalled();
    finishCommunity(communityPayload);
    await expect(request).resolves.toMatchObject({ status: "ready", items: webcamPayload.webcams });
  });

  it.each(["webcams", "community"])("shows %s before the other source completes", async (first) => {
    let finishWebcams;
    let finishCommunity;
    const onUpdate = vi.fn();
    const settled = vi.fn();
    const storage = createStorage();
    const request = loadLiveData({
      storage,
      onUpdate,
      webcamFetcher: () => new Promise((resolve) => { finishWebcams = resolve; }),
      communityFetcher: () => new Promise((resolve) => { finishCommunity = resolve; }),
    });
    request.then(settled);
    await Promise.resolve();
    if (first === "webcams") finishWebcams(webcamPayload);
    else finishCommunity(communityPayload);
    await vi.waitFor(() => expect(onUpdate).toHaveBeenCalledTimes(1));

    expect(onUpdate.mock.calls[0][0]).toMatchObject({
      [first]: { status: "fresh", payload: first === "webcams" ? webcamPayload : communityPayload },
      [first === "webcams" ? "community" : "webcams"]: { status: "loading" },
    });
    expect(settled).not.toHaveBeenCalled();
    expect(storage.getItem(first === "webcams" ? LIVE_WEBCAM_CACHE_KEY : LIVE_COMMUNITY_CACHE_KEY)).not.toBeNull();

    if (first === "webcams") finishCommunity(communityPayload);
    else finishWebcams(webcamPayload);
    await expect(request).resolves.toMatchObject({ status: "ready", items: webcamPayload.webcams });
    expect(onUpdate).toHaveBeenCalledTimes(2);
  });

  it("keeps the ready source usable when the slower source fails", async () => {
    let failCommunity;
    const onUpdate = vi.fn();
    const request = loadLiveData({
      storage: createStorage(),
      onUpdate,
      webcamFetcher: async () => webcamPayload,
      communityFetcher: () => new Promise((resolve, reject) => { failCommunity = reject; }),
    });
    await vi.waitFor(() => expect(onUpdate).toHaveBeenCalledTimes(1));
    expect(onUpdate.mock.calls[0][0].items).toEqual(webcamPayload.webcams);
    failCommunity(new Error("timeout"));
    await expect(request).resolves.toMatchObject({
      ok: true,
      items: webcamPayload.webcams,
      community: { status: "error", error: "timeout" },
      webcams: { status: "fresh" },
    });
  });

  it("limits automatic community polling to once every five minutes", () => {
    expect(LIVE_COMMUNITY_RECHECK_MS).toBe(5 * 60 * 1000);
    expect(LIVE_AUTO_REFRESH_INTERVAL_MS).toBe(LIVE_COMMUNITY_RECHECK_MS);
  });

  it("hydrates immediately from independent device caches", () => {
    const storage = createStorage({
      [LIVE_COMMUNITY_CACHE_KEY]: cacheEntry(communityPayload),
      [LIVE_WEBCAM_CACHE_KEY]: cacheEntry(webcamPayload),
    });

    expect(readInitialLiveData({ now: () => 1200, storage })).toMatchObject({
      community: { fromCache: true, status: "cache" },
      ok: true,
      status: "ready",
      webcams: { fromCache: true, status: "cache" },
    });
  });

  it("keeps interactive QA isolated from the real community cache", () => {
    const storage = createStorage({
      [LIVE_COMMUNITY_CACHE_KEY]: cacheEntry({
        reports: [{ id: "real-report" }],
        map_groups: [{ id: "real-group" }],
      }),
      [LIVE_WEBCAM_CACHE_KEY]: cacheEntry(webcamPayload),
    });

    expect(readInitialLiveData({
      communityEnabled: false,
      now: () => 1200,
      storage,
    })).toMatchObject({
      community: {
        payload: { map_groups: [], reports: [] },
        status: "fresh",
      },
      status: "ready",
      webcams: { fromCache: true, payload: webcamPayload },
    });
    expect(storage.getItem).not.toHaveBeenCalledWith(LIVE_COMMUNITY_CACHE_KEY);
    expect(storage.getItem).toHaveBeenCalledWith(LIVE_WEBCAM_CACHE_KEY);
  });

  it("does not read or fetch webcams or community when those sources are out of scope", async () => {
    const storage = createStorage({
      [LIVE_WEBCAM_CACHE_KEY]: cacheEntry(webcamPayload),
    });
    const webcamFetcher = vi.fn().mockResolvedValue(webcamPayload);
    const communityFetcher = vi.fn().mockResolvedValue(communityPayload);

    expect(readInitialLiveData({
      communityEnabled: false,
      webcamsEnabled: false,
      now: () => 1200,
      storage,
    })).toMatchObject({
      items: [],
      webcams: { payload: null, status: "unsupported" },
    });
    expect(storage.getItem).not.toHaveBeenCalledWith(LIVE_WEBCAM_CACHE_KEY);

    const result = await loadLiveData({
      communityEnabled: false,
      communityFetcher,
      force: true,
      forceWebcams: true,
      storage,
      webcamFetcher,
      webcamsEnabled: false,
    });

    expect(result).toMatchObject({
      items: [],
      ok: true,
      status: "ready",
      webcams: { payload: null, status: "unsupported" },
    });
    expect(webcamFetcher).not.toHaveBeenCalled();
    expect(communityFetcher).not.toHaveBeenCalled();
    expect(storage.setItem).not.toHaveBeenCalledWith(
      LIVE_WEBCAM_CACHE_KEY,
      expect.anything(),
    );
  });

  it("does not re-fetch or rewrite fresh cache entries", async () => {
    const storage = createStorage({
      [LIVE_COMMUNITY_CACHE_KEY]: cacheEntry(communityPayload),
      [LIVE_WEBCAM_CACHE_KEY]: cacheEntry(webcamPayload),
    });
    const webcamFetcher = vi.fn();
    const communityFetcher = vi.fn();

    const result = await loadLiveData({
      communityFetcher,
      now: () => 1200,
      storage,
      webcamFetcher,
    });

    expect(result).toMatchObject({ ok: true, status: "ready" });
    expect(webcamFetcher).not.toHaveBeenCalled();
    expect(communityFetcher).not.toHaveBeenCalled();
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("rechecks webcams only after the ten-minute cache window unless forced", async () => {
    const savedAt = 1000;
    const storage = createStorage({
      [LIVE_WEBCAM_CACHE_KEY]: cacheEntry(webcamPayload, savedAt),
    });
    const webcamFetcher = vi.fn().mockResolvedValue(webcamPayload);
    let currentTime = savedAt + LIVE_WEBCAM_RECHECK_MS;
    const options = {
      communityEnabled: false,
      now: () => currentTime,
      storage,
      webcamFetcher,
    };

    expect(LIVE_WEBCAM_RECHECK_MS).toBe(10 * 60 * 1000);
    const cached = await loadLiveData(options);

    expect(cached.webcams).toMatchObject({ fromCache: true, payload: webcamPayload });
    expect(webcamFetcher).not.toHaveBeenCalled();
    expect(storage.setItem).not.toHaveBeenCalled();

    currentTime += 1;
    const refreshed = await loadLiveData(options);

    expect(refreshed.webcams).toMatchObject({ fromCache: false, payload: webcamPayload });
    expect(webcamFetcher).toHaveBeenCalledTimes(1);
    expect(JSON.parse(storage.getItem(LIVE_WEBCAM_CACHE_KEY))).toEqual({
      data: webcamPayload,
      savedAt: currentTime,
    });
  });

  it.each(["remove-source", "disable-image"])(
    "persists a remote %s update without reviving the previous snapshot while offline",
    async (update) => {
      const sacile = {
        id: "sacile",
        imageUrl: "https://images.example.test/sacile.jpg",
        fallbackImageUrl: "/municipalities/photos/sacile.webp",
        sourcePage: "https://camera.example.test/webcam/sacile",
      };
      const other = {
        id: "other-webcam",
        imageUrl: "https://images.example.test/other.jpg",
      };
      const previousPayload = { ok: true, version: 1, webcams: [sacile, other] };
      const disabledSacile = {
        id: sacile.id,
        fallbackImageUrl: sacile.fallbackImageUrl,
        sourcePage: sacile.sourcePage,
      };
      const updatedPayload = {
        ok: true,
        version: 2,
        webcams: update === "remove-source" ? [other] : [disabledSacile, other],
      };
      const savedAt = 1000;
      let currentTime = savedAt + LIVE_WEBCAM_RECHECK_MS + 1;
      const refreshedAt = currentTime;
      const storage = createStorage({
        [LIVE_WEBCAM_CACHE_KEY]: cacheEntry(previousPayload, savedAt),
      });
      const webcamFetcher = vi.fn()
        .mockResolvedValueOnce(updatedPayload)
        .mockRejectedValueOnce(new Error("offline"));
      const options = {
        communityEnabled: false,
        now: () => currentTime,
        storage,
        webcamFetcher,
      };

      const refreshed = await loadLiveData(options);

      expect(refreshed.webcams).toMatchObject({
        fromCache: false,
        payload: updatedPayload,
        status: "fresh",
      });
      expect(refreshed.items).toEqual(updatedPayload.webcams);
      expect(JSON.parse(storage.getItem(LIVE_WEBCAM_CACHE_KEY))).toEqual({
        data: updatedPayload,
        savedAt: refreshedAt,
      });
      expect(readInitialLiveData(options).items).toEqual(updatedPayload.webcams);

      currentTime += LIVE_WEBCAM_RECHECK_MS + 1;
      const offline = await loadLiveData(options);

      expect(webcamFetcher).toHaveBeenCalledTimes(2);
      expect(offline.webcams).toMatchObject({
        error: "offline",
        fromCache: true,
        payload: updatedPayload,
        status: "stale",
      });
      expect(offline.items).toEqual(updatedPayload.webcams);
      expect(JSON.stringify(offline.items)).not.toContain(sacile.imageUrl);
      expect(JSON.parse(storage.getItem(LIVE_WEBCAM_CACHE_KEY))).toEqual({
        data: updatedPayload,
        savedAt: refreshedAt,
      });
      expect(storage.setItem).toHaveBeenCalledTimes(1);
    },
  );

  it("keeps cached webcams visible when a forced refresh is offline", async () => {
    const storage = createStorage({
      [LIVE_COMMUNITY_CACHE_KEY]: cacheEntry(communityPayload),
      [LIVE_WEBCAM_CACHE_KEY]: cacheEntry(webcamPayload),
    });

    const result = await loadLiveData({
      communityFetcher: vi.fn().mockRejectedValue(new Error("offline")),
      force: true,
      now: () => 1200,
      storage,
      webcamFetcher: vi.fn().mockRejectedValue(new Error("offline")),
    });

    expect(result).toMatchObject({
      ok: true,
      status: "stale",
      webcams: { error: "offline", fromCache: true, payload: webcamPayload },
    });
    expect(result.items).toHaveLength(1);
  });

  it("refreshes community reports without re-fetching fresh webcams", async () => {
    const storage = createStorage({
      [LIVE_COMMUNITY_CACHE_KEY]: cacheEntry(communityPayload),
      [LIVE_WEBCAM_CACHE_KEY]: cacheEntry(webcamPayload),
    });
    const webcamFetcher = vi.fn();
    const communityFetcher = vi.fn().mockResolvedValue(communityPayload);

    const result = await loadLiveData({
      communityFetcher,
      forceCommunity: true,
      now: () => 1200,
      storage,
      webcamFetcher,
    });

    expect(result).toMatchObject({ ok: true, status: "ready" });
    expect(communityFetcher).toHaveBeenCalledTimes(1);
    expect(webcamFetcher).not.toHaveBeenCalled();
  });

  it("shares one in-flight community request between simultaneous consumers", async () => {
    let resolveCommunity;
    const communityFetcher = vi.fn(() => new Promise((resolve) => {
      resolveCommunity = resolve;
    }));
    const firstStorage = createStorage();
    const secondStorage = createStorage();

    const first = loadLiveData({
      communityFetcher,
      storage: firstStorage,
      webcamsEnabled: false,
    });
    const second = loadLiveData({
      communityFetcher,
      forceCommunity: true,
      storage: secondStorage,
      webcamsEnabled: false,
    });

    await Promise.resolve();
    expect(communityFetcher).toHaveBeenCalledTimes(1);

    resolveCommunity(communityPayload);
    await expect(Promise.all([first, second])).resolves.toEqual([
      expect.objectContaining({ status: "ready" }),
      expect.objectContaining({ status: "ready" }),
    ]);
    expect(firstStorage.setItem).toHaveBeenCalledWith(
      LIVE_COMMUNITY_CACHE_KEY,
      expect.any(String),
    );
    expect(secondStorage.setItem).toHaveBeenCalledWith(
      LIVE_COMMUNITY_CACHE_KEY,
      expect.any(String),
    );
  });

  it("cannot re-enable community traffic with force flags in interactive QA", async () => {
    const storage = createStorage();
    const communityFetcher = vi.fn();
    const webcamFetcher = vi.fn().mockResolvedValue(webcamPayload);

    const result = await loadLiveData({
      communityEnabled: false,
      communityFetcher,
      force: true,
      forceCommunity: true,
      storage,
      webcamFetcher,
    });

    expect(result).toMatchObject({
      community: {
        payload: { map_groups: [], reports: [] },
        status: "fresh",
      },
      status: "ready",
      webcams: { payload: webcamPayload },
    });
    expect(communityFetcher).not.toHaveBeenCalled();
    expect(webcamFetcher).toHaveBeenCalledTimes(1);
    expect(storage.setItem).not.toHaveBeenCalledWith(
      LIVE_COMMUNITY_CACHE_KEY,
      expect.anything(),
    );
  });

  it("fails only when neither endpoint nor cache can keep content visible", async () => {
    const result = await loadLiveData({
      communityFetcher: vi.fn().mockRejectedValue(new Error("community offline")),
      force: true,
      storage: createStorage(),
      webcamFetcher: vi.fn().mockRejectedValue(new Error("webcam offline")),
    });

    expect(result).toMatchObject({ ok: false, status: "error" });
    expect(result.error).toContain("webcam offline");
    expect(result.error).toContain("community offline");
  });

  it("does not revive expired live caches when both endpoints are offline", async () => {
    const storage = createStorage({
      [LIVE_COMMUNITY_CACHE_KEY]: cacheEntry(communityPayload),
      [LIVE_WEBCAM_CACHE_KEY]: cacheEntry(webcamPayload),
    });
    const now = 1000 + Math.max(
      LIVE_COMMUNITY_STORAGE_MAX_AGE_MS,
      LIVE_WEBCAM_STORAGE_MAX_AGE_MS,
    ) + 1;

    const result = await loadLiveData({
      communityFetcher: vi.fn().mockRejectedValue(new Error("community offline")),
      force: true,
      now: () => now,
      storage,
      webcamFetcher: vi.fn().mockRejectedValue(new Error("webcam offline")),
    });

    expect(result).toMatchObject({
      items: [],
      ok: false,
      status: "error",
    });
  });

  it("starts with a non-blocking loading state when no cache exists", () => {
    expect(createEmptyLiveDataState()).toMatchObject({
      items: [],
      ok: true,
      status: "loading",
    });
  });
});
