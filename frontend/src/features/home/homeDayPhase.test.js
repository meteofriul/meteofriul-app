import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getHomeSolarState,
  getMillisecondsUntilNextMinute,
  subscribeToHomeSolarClock,
} from "./homeDayPhase";

const SERVER_SOLAR_CONTEXT = {
  sunrise: "2026-08-12T06:00",
  sunset: "2026-08-12T18:00",
};

describe("getHomeSolarState", () => {
  it.each([
    ["2026-08-12T05:14", "night", true],
    ["2026-08-12T05:15", "night", true],
    ["2026-08-12T05:59", "night", true],
    ["2026-08-12T06:00", "dawn", false],
    ["2026-08-12T06:44", "dawn", false],
    ["2026-08-12T06:45", "morning", false],
    ["2026-08-12T10:29", "morning", false],
    ["2026-08-12T10:30", "midday", false],
    ["2026-08-12T13:29", "midday", false],
    ["2026-08-12T13:30", "afternoon", false],
    ["2026-08-12T17:14", "afternoon", false],
    ["2026-08-12T17:15", "sunset", false],
    ["2026-08-12T17:59", "sunset", false],
    ["2026-08-12T18:00", "night", true],
    ["2026-08-12T18:44", "night", true],
    ["2026-08-12T18:45", "night", true],
  ])("classifies the exact phase boundary at %s", (now, expectedPhase, expectedIsNight) => {
    const state = getHomeSolarState({ now, ...SERVER_SOLAR_CONTEXT });

    expect(state).toMatchObject({
      phase: expectedPhase,
      isNight: expectedIsNight,
      source: "server",
      sunriseMinutes: 6 * 60,
      sunsetMinutes: 18 * 60,
    });
  });

  it("accepts clock-only values and offset-aware timestamps", () => {
    const clockState = getHomeSolarState({
      now: new Date("2026-08-12T10:00:00Z"),
      sunrise: "06:00",
      sunset: "18:00",
    });
    const offsetState = getHomeSolarState({
      now: new Date("2026-08-12T10:00:00Z"),
      sunrise: "2026-08-12T04:00:00Z",
      sunset: "2026-08-12T16:00:00Z",
    });

    expect(clockState).toMatchObject({ phase: "midday", source: "server" });
    expect(offsetState).toMatchObject({
      phase: "midday",
      source: "server",
      sunriseMinutes: 6 * 60,
      sunsetMinutes: 18 * 60,
    });
  });

  it("rejects stale server dates and computes the current FVG solar state", () => {
    const daytimeFallback = getHomeSolarState({
      now: "2026-08-12T12:00",
      sunrise: "2026-08-11T06:00",
      sunset: "2026-08-11T18:00",
    });
    const nighttimeFallback = getHomeSolarState({
      now: "2026-08-12T12:00",
      sunrise: "2026-08-11T06:00",
      sunset: "2026-08-11T18:00",
      fallbackIsNight: true,
    });

    expect(daytimeFallback).toMatchObject({
      phase: "midday",
      isNight: false,
      source: "sun-cycle",
    });
    expect(nighttimeFallback).toMatchObject({
      phase: "midday",
      isNight: false,
      source: "sun-cycle",
    });
  });

  it("computes the local summer solar cycle when server values are unavailable", () => {
    const state = getHomeSolarState({
      now: new Date("2026-06-24T10:00:00Z"),
      latitude: 46.0711,
      longitude: 13.2346,
    });

    expect(state.source).toBe("sun-cycle");
    expect(state.phase).toBe("midday");
    expect(state.sunriseMinutes).toBeGreaterThanOrEqual(5 * 60);
    expect(state.sunriseMinutes).toBeLessThan(5 * 60 + 30);
    expect(state.sunsetMinutes).toBeGreaterThan(21 * 60);
    expect(state.sunsetMinutes).toBeLessThan(21 * 60 + 20);
  });

  it("computes the local winter solar cycle and night state", () => {
    const midday = getHomeSolarState({
      now: new Date("2026-12-21T11:00:00Z"),
      latitude: 46.0711,
      longitude: 13.2346,
    });
    const earlyMorning = getHomeSolarState({
      now: new Date("2026-12-21T05:00:00Z"),
      latitude: 46.0711,
      longitude: 13.2346,
    });

    expect(midday).toMatchObject({ phase: "midday", isNight: false, source: "sun-cycle" });
    expect(midday.sunriseMinutes).toBeGreaterThan(7 * 60 + 30);
    expect(midday.sunsetMinutes).toBeLessThan(16 * 60 + 45);
    expect(earlyMorning).toMatchObject({ phase: "night", isNight: true, source: "sun-cycle" });
  });

  it("uses the Europe/Rome calendar date across the spring DST boundary", () => {
    const state = getHomeSolarState({
      // 23:30 UTC on Saturday is already Sunday, 29 March, in Europe/Rome.
      now: new Date("2026-03-28T23:30:00Z"),
      sunrise: "2026-03-29T06:00",
      sunset: "2026-03-29T19:00",
    });

    expect(state).toMatchObject({ phase: "night", source: "server" });
  });

  it("falls back safely for an invalid timezone", () => {
    const state = getHomeSolarState({
      now: new Date("2026-08-12T10:00:00Z"),
      latitude: Number.NaN,
      longitude: 13.2346,
      timeZone: "Invalid/Zone",
      fallbackIsNight: true,
    });

    expect(state).toEqual({
      phase: "night",
      isNight: true,
      source: "fallback",
      sunriseMinutes: null,
      sunsetMinutes: null,
    });
  });

  it("uses central FVG coordinates when a location has no coordinates", () => {
    const state = getHomeSolarState({
      now: new Date("2026-08-12T15:00:00Z"),
    });

    expect(state).toMatchObject({
      phase: "afternoon",
      isNight: false,
      source: "sun-cycle",
    });
  });
});

describe("getMillisecondsUntilNextMinute", () => {
  it("aligns the next update to the minute boundary", () => {
    expect(getMillisecondsUntilNextMinute(new Date("2026-08-12T12:34:45.250Z"))).toBe(14_750);
    expect(getMillisecondsUntilNextMinute(new Date("2026-08-12T12:35:00.000Z"))).toBe(60_000);
  });

  it("uses a full minute for an invalid timestamp", () => {
    expect(getMillisecondsUntilNextMinute("not-a-date")).toBe(60_000);
  });
});

describe("subscribeToHomeSolarClock", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("ticks on the next minute, resyncs on visibility changes and cleans up", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-12T12:34:45.250Z"));
    const listeners = new Map();
    const documentRef = {
      addEventListener: vi.fn((eventName, handler) => listeners.set(eventName, handler)),
      removeEventListener: vi.fn((eventName, handler) => {
        if (listeners.get(eventName) === handler) listeners.delete(eventName);
      }),
    };
    const onTick = vi.fn();
    const cleanup = subscribeToHomeSolarClock(onTick, { documentRef });

    vi.advanceTimersByTime(14_749);
    expect(onTick).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onTick).toHaveBeenCalledTimes(1);

    listeners.get("visibilitychange")();
    expect(onTick).toHaveBeenCalledTimes(2);

    cleanup();
    expect(documentRef.removeEventListener).toHaveBeenCalledWith(
      "visibilitychange",
      expect.any(Function),
    );
    expect(listeners.has("visibilitychange")).toBe(false);
    vi.advanceTimersByTime(120_000);
    expect(onTick).toHaveBeenCalledTimes(2);
  });
});
