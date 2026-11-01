import { describe, expect, it, vi } from "vitest";
import { EVENTS_RADIUS_STORAGE_KEY, normalizeEventsRadius, readEventsRadiusPreference, writeEventsRadiusPreference } from "./eventsRadiusPreference";

describe("shared Eventi and Mercati radius preference", () => {
  it("defaults to 20 and persists a validated radius independently of location", () => {
    const values = new Map();
    const storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) };
    expect(readEventsRadiusPreference(storage)).toBe(20);
    expect(writeEventsRadiusPreference("50", storage)).toBe(50);
    expect(readEventsRadiusPreference(storage)).toBe(50);
    expect([...values]).toEqual([[EVENTS_RADIUS_STORAGE_KEY, "50"]]);
  });
  it.each([null, undefined, true, false, "", 0, 1, 7, 55, {}, [], NaN, Infinity])("rejects invalid persisted value %s", value => {
    expect(normalizeEventsRadius(value)).toBeNull();
    expect(readEventsRadiusPreference({ getItem: () => value })).toBe(20);
  });
  it("keeps working when browser storage is unavailable", () => {
    const storage = { getItem: vi.fn(() => { throw Error("blocked"); }), setItem: vi.fn(() => { throw Error("blocked"); }) };
    expect(readEventsRadiusPreference(storage)).toBe(20);
    expect(writeEventsRadiusPreference(5, storage)).toBe(5);
  });
});
