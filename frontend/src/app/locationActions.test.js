import { describe, expect, it, vi } from "vitest";

import {
  changeAutomaticLocationMode,
  prepareManualLocationChange,
  refreshDeviceLocation,
  runManualLocationChange,
} from "./locationActions";

describe("location actions", () => {
  it("pilot commits immediately and never recommits after a late weather response", async () => {
    let finish;
    const loadWeather = vi.fn(() => new Promise(resolve => { finish = resolve; }));
    const commitLocation = vi.fn(location => location);
    const disableAutomaticLocation = vi.fn();
    const location = { city: 'Udine' };
    await expect(runManualLocationChange(location, {
      immediate: true, commitLocation, disableAutomaticLocation, loadWeather,
    })).resolves.toBe(location);
    expect(commitLocation).toHaveBeenCalledTimes(1);
    expect(disableAutomaticLocation).toHaveBeenCalledOnce();
    finish({ current: { temperature: 20 }, forecast: { hourly: [] } });
    await Promise.resolve();
    expect(commitLocation).toHaveBeenCalledTimes(1);
  });

  it("pilot weather failure does not undo the selected municipality", async () => {
    const commitLocation = vi.fn(location => location);
    await expect(runManualLocationChange({ city: 'Trieste' }, {
      immediate: true, commitLocation,
      loadWeather: vi.fn().mockRejectedValue(new Error('offline')),
    })).resolves.toEqual({ city: 'Trieste' });
    await Promise.resolve();
    expect(commitLocation).toHaveBeenCalledOnce();
  });
  it("refreshes the GPS fix without disabling automatic mode", async () => {
    const disableAutomaticLocation = vi.fn();
    const resolveDeviceLocation = vi.fn().mockResolvedValue({ ok: true });

    await refreshDeviceLocation(resolveDeviceLocation);

    expect(resolveDeviceLocation).toHaveBeenCalledWith({ markLoading: true });
    expect(disableAutomaticLocation).not.toHaveBeenCalled();
  });

  it("changes automatic mode only through its dedicated control", async () => {
    const disableAutomaticLocation = vi.fn();
    const resolveDeviceLocation = vi.fn().mockResolvedValue({ ok: true });

    await changeAutomaticLocationMode(false, {
      disableAutomaticLocation,
      resolveDeviceLocation,
    });
    expect(disableAutomaticLocation).toHaveBeenCalledTimes(1);
    expect(resolveDeviceLocation).not.toHaveBeenCalled();

    disableAutomaticLocation.mockClear();
    await changeAutomaticLocationMode(true, {
      disableAutomaticLocation,
      resolveDeviceLocation,
    });
    expect(disableAutomaticLocation).not.toHaveBeenCalled();
    expect(resolveDeviceLocation).toHaveBeenCalledWith({ markLoading: true });
  });

  it("prepares mandatory weather while leaving CAMS enrichment deferred", async () => {
    const location = { city: "Udine" };
    const weather = {
      current: { temperature: 22 },
      forecast: { hourly: [] },
      rawCurrent: { temperature: 22, data_quality: { cams_status: "pending" } },
    };
    const loadWeather = vi.fn().mockResolvedValue(weather);

    await expect(prepareManualLocationChange(location, {
      loadWeather,
      timeoutMs: 100,
    })).resolves.toBe(weather);
    expect(loadWeather).toHaveBeenCalledWith(location, { deferCams: true });
  });

  it("rejects a location whose required ICON weather is unavailable", async () => {
    const loadWeather = vi.fn().mockResolvedValue({
      current: null,
      forecast: null,
      rawCurrent: null,
      error: "ICON non disponibile",
    });

    await expect(prepareManualLocationChange({ city: "Udine" }, {
      loadWeather,
      timeoutMs: 100,
    })).rejects.toThrow("ICON non disponibile");
  });

  it("uses an already verified target bundle without another request", async () => {
    const location = { city: "Udine" };
    const cachedWeather = {
      current: { temperature: 22 },
      forecast: { hourly: [] },
    };
    const loadWeather = vi.fn();

    await expect(prepareManualLocationChange(location, {
      loadWeather,
      readWeather: vi.fn().mockReturnValue(cachedWeather),
      timeoutMs: 100,
    })).resolves.toBe(cachedWeather);
    expect(loadWeather).not.toHaveBeenCalled();
  });

  it("commits the manual location only after mandatory weather is ready", async () => {
    const order = [];
    const location = { city: "Udine" };
    const loadWeather = vi.fn(async (_location, options) => {
      order.push(`weather:${options.deferCams}`);
      return {
        current: { temperature: 22 },
        forecast: { hourly: [] },
      };
    });
    const disableAutomaticLocation = vi.fn(() => order.push("disable-auto"));
    const commitLocation = vi.fn((nextLocation) => {
      order.push("commit");
      return nextLocation;
    });

    await expect(runManualLocationChange(location, {
      commitLocation,
      disableAutomaticLocation,
      loadWeather,
      timeoutMs: 100,
    })).resolves.toBe(location);
    expect(order).toEqual(["weather:true", "disable-auto", "commit"]);
  });

  it("preserves the current location and automatic mode when preparation fails", async () => {
    const disableAutomaticLocation = vi.fn();
    const commitLocation = vi.fn();

    await expect(runManualLocationChange({ city: "Udine" }, {
      commitLocation,
      disableAutomaticLocation,
      loadWeather: vi.fn().mockResolvedValue({
        current: null,
        forecast: null,
        error: "ICON non disponibile",
      }),
      timeoutMs: 100,
    })).rejects.toThrow("ICON non disponibile");
    expect(disableAutomaticLocation).not.toHaveBeenCalled();
    expect(commitLocation).not.toHaveBeenCalled();
  });

  it("times out a stalled preload without accepting the target location", async () => {
    vi.useFakeTimers();
    try {
      const pending = prepareManualLocationChange({ city: "Udine" }, {
        loadWeather: vi.fn(() => new Promise(() => {})),
        timeoutMs: 50,
      });
      const rejected = expect(pending).rejects.toMatchObject({
        code: "LOCATION_WEATHER_TIMEOUT",
      });

      await vi.advanceTimersByTimeAsync(50);
      await rejected;
    } finally {
      vi.useRealTimers();
    }
  });
});
