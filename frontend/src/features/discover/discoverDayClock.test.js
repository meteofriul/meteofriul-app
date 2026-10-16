import { describe, expect, it, vi } from "vitest";

import {
  getLocalDayKey,
  getMillisecondsUntilNextLocalDay,
  subscribeToDiscoverDayClock,
} from "./discoverDayClock";

describe("discover day clock", () => {
  it("uses the device local calendar day", () => {
    expect(getLocalDayKey(new Date(2026, 7, 21, 23, 59))).toBe("2026-08-21");
  });

  it("schedules the next tick at local midnight", () => {
    const now = new Date(2026, 7, 21, 23, 59, 30, 250);

    expect(getMillisecondsUntilNextLocalDay(now)).toBe(29_750);
  });

  it("notifies once when the local day changes and schedules the following midnight", () => {
    const times = [
      new Date(2026, 7, 21, 23, 59, 30),
      new Date(2026, 7, 21, 23, 59, 30),
      new Date(2026, 7, 22, 0, 0, 0),
      new Date(2026, 7, 22, 0, 0, 0),
    ];
    const now = vi.fn(() => times.shift() || new Date(2026, 7, 22, 0, 0, 0));
    const callbacks = [];
    const timerApi = {
      clearTimeout: vi.fn(),
      setTimeout: vi.fn((callback) => {
        callbacks.push(callback);
        return callbacks.length;
      }),
    };
    const onDayChange = vi.fn();

    const unsubscribe = subscribeToDiscoverDayClock(onDayChange, {
      documentRef: null,
      now,
      timerApi,
    });

    callbacks[0]();

    expect(onDayChange).toHaveBeenCalledTimes(1);
    expect(getLocalDayKey(onDayChange.mock.calls[0][0])).toBe("2026-08-22");
    expect(timerApi.setTimeout).toHaveBeenCalledTimes(2);

    unsubscribe();
    expect(timerApi.clearTimeout).toHaveBeenCalled();
  });

  it("catches a missed midnight when the app becomes visible again", () => {
    let visibilityHandler;
    const documentRef = {
      addEventListener: vi.fn((eventName, handler) => {
        if (eventName === "visibilitychange") visibilityHandler = handler;
      }),
      removeEventListener: vi.fn(),
    };
    const times = [
      new Date(2026, 7, 21, 18, 0),
      new Date(2026, 7, 21, 18, 0),
      new Date(2026, 7, 22, 8, 0),
      new Date(2026, 7, 22, 8, 0),
    ];
    const now = vi.fn(() => times.shift() || new Date(2026, 7, 22, 8, 0));
    const timerApi = {
      clearTimeout: vi.fn(),
      setTimeout: vi.fn(() => 1),
    };
    const onDayChange = vi.fn();

    const unsubscribe = subscribeToDiscoverDayClock(onDayChange, {
      documentRef,
      now,
      timerApi,
    });

    visibilityHandler();

    expect(onDayChange).toHaveBeenCalledTimes(1);
    expect(getLocalDayKey(onDayChange.mock.calls[0][0])).toBe("2026-08-22");

    unsubscribe();
    expect(documentRef.removeEventListener).toHaveBeenCalledWith(
      "visibilitychange",
      visibilityHandler,
    );
  });
});
