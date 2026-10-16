import { describe, expect, it, vi } from "vitest";

import {
  LIVE_COMMUNITY_CACHE_KEY,
  LIVE_WEBCAM_CACHE_KEY,
  clearLiveDeviceCache,
  readLiveCommunityCacheEntry,
  readLiveWebcamCacheEntry,
  writeLiveCommunityCache,
  writeLiveWebcamCache,
} from "./liveCache";

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => values.get(key) || null),
    removeItem: vi.fn((key) => values.delete(key)),
    setItem: vi.fn((key, value) => values.set(key, value)),
  };
}

describe("live cache", () => {
  it("stores webcam and community data independently", () => {
    const storage = createStorage();
    const now = () => 1000;

    expect(writeLiveWebcamCache({ ok: true, webcams: [{ id: "one" }] }, { now, storage })).toBe(true);
    expect(writeLiveCommunityCache({ reports: [], map_groups: [] }, { now, storage })).toBe(true);
    expect(readLiveWebcamCacheEntry({ now: () => 1300, storage })).toMatchObject({ age: 300 });
    expect(readLiveCommunityCacheEntry({ now: () => 1300, storage })).toMatchObject({ age: 300 });
  });

  it("clears both live caches from the settings cache action", () => {
    const storage = createStorage({
      [LIVE_COMMUNITY_CACHE_KEY]: "{}",
      [LIVE_WEBCAM_CACHE_KEY]: "{}",
    });

    expect(clearLiveDeviceCache({ storage })).toEqual({
      community: true,
      ok: true,
      webcams: true,
    });
    expect(storage.removeItem).toHaveBeenCalledWith(LIVE_WEBCAM_CACHE_KEY);
    expect(storage.removeItem).toHaveBeenCalledWith(LIVE_COMMUNITY_CACHE_KEY);
  });
});
