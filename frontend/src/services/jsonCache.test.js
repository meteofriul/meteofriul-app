import { describe, expect, it, vi } from "vitest";

import { readJsonCache, readJsonCacheEntry, removeJsonCache, writeJsonCache } from "./jsonCache";

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

describe("json cache", () => {
  it("reads fresh entries with age metadata", () => {
    const storage = createStorage({
      weather: JSON.stringify({ savedAt: 1000, data: { city: "Udine" } }),
    });

    expect(readJsonCacheEntry("weather", 5000, { storage, now: () => 1300 })).toEqual({
      data: { city: "Udine" },
      age: 300,
      savedAt: 1000,
    });
  });

  it("can retain stale entries for a wider offline fallback", () => {
    const storage = createStorage({
      weather: JSON.stringify({ savedAt: 1000, data: { city: "Udine" } }),
    });

    expect(readJsonCache("weather", 100, { storage, now: () => 1300 })).toBeNull();
    expect(storage.removeItem).not.toHaveBeenCalled();
    expect(storage.getItem("weather")).not.toBeNull();
  });

  it("removes entries at their definitive retention boundary", () => {
    const storage = createStorage({
      events: JSON.stringify({ savedAt: 1000, data: { events: [] } }),
    });

    expect(readJsonCache("events", 100, {
      removeExpired: true,
      storage,
      now: () => 1300,
    })).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith("events");
    expect(storage.getItem("events")).toBeNull();
  });

  it("removes invalid JSON and keeps storage failures non-fatal", () => {
    const storage = createStorage({ broken: "{" });

    expect(readJsonCache("broken", 1000, { storage, now: () => 1300 })).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith("broken");

    expect(
      writeJsonCache("key", { ok: true }, { storage: { setItem: () => undefined }, now: () => 1 }),
    ).toBe(true);
    expect(
      writeJsonCache(
        "key",
        { ok: true },
        {
          storage: {
            setItem: () => {
              throw new Error("full");
            },
          },
          now: () => 1,
        },
      ),
    ).toBe(false);
  });

  it("writes savedAt and data using the provided clock", () => {
    const storage = createStorage();

    expect(writeJsonCache("events", { events: [] }, { storage, now: () => 42 })).toBe(true);
    expect(storage.setItem).toHaveBeenCalledWith("events", JSON.stringify({ savedAt: 42, data: { events: [] } }));
  });

  it("removes a cache key without failing on missing storage", () => {
    const storage = createStorage({
      weather: JSON.stringify({ savedAt: 1000, data: { city: "Udine" } }),
    });

    expect(removeJsonCache("weather", { storage })).toBe(true);
    expect(storage.removeItem).toHaveBeenCalledWith("weather");
    expect(removeJsonCache("weather", { storage: null })).toBe(false);
  });
});
