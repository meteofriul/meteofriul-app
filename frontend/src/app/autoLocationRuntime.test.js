import { describe, expect, it, vi } from "vitest";

import {
  AUTO_LOCATION_MAX_AGE_MS,
  createLatestLocationRequestGuard,
  getAutomaticLocationBootstrapState,
  getAutomaticLocationQualityDecision,
  getDisabledAutomaticLocationStatus,
  shouldRestoreAutomaticLocation,
  shouldRunAutomaticLocationCheck,
  startAutomaticLocationRuntime,
} from "./autoLocationRuntime";

function createEventTarget(initial = {}) {
  const listeners = new Map();

  return {
    ...initial,
    addEventListener: vi.fn((type, listener) => {
      const entries = listeners.get(type) || new Set();
      entries.add(listener);
      listeners.set(type, entries);
    }),
    dispatch(type) {
      listeners.get(type)?.forEach((listener) => listener({ type }));
    },
    removeEventListener: vi.fn((type, listener) => {
      listeners.get(type)?.delete(listener);
    }),
  };
}

function createWindowTarget() {
  const target = createEventTarget();
  let intervalCallback = null;

  return {
    ...target,
    clearInterval: vi.fn(),
    runInterval() {
      return intervalCallback?.();
    },
    setInterval: vi.fn((callback) => {
      intervalCallback = callback;
      return 17;
    }),
  };
}

function buildResult(overrides = {}) {
  return {
    ageMs: 500,
    coords: { accuracyM: 20, lat: 45.9567, lon: 12.6605 },
    ok: true,
    source: "browser_geolocation",
    ...overrides,
  };
}

describe("automatic location runtime", () => {
  it("invalidates late requests and keeps only the latest result authoritative", () => {
    const guard = createLatestLocationRequestGuard();
    const first = guard.begin();
    const second = guard.begin();

    expect(guard.isCurrent(first)).toBe(false);
    expect(guard.isCurrent(second)).toBe(true);
    guard.invalidate();
    expect(guard.isCurrent(second)).toBe(false);
  });

  it("keeps the last detected city separate when automatic mode is disabled", () => {
    expect(getDisabledAutomaticLocationStatus({ status: "success", city: "Pordenone" })).toEqual({
      status: "last_known",
      city: "Pordenone",
    });
    expect(getDisabledAutomaticLocationStatus({ status: "loading" })).toEqual({ status: "idle" });
  });

  it("keeps the last visible locality when automatic mode is disabled", () => {
    expect(getDisabledAutomaticLocationStatus({
      status: "success",
      city: "Fontanafredda",
      displayName: "Vigonovo",
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
    })).toEqual({
      status: "last_known",
      city: "Fontanafredda",
      displayName: "Vigonovo",
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
    });
  });

  it("does not restore a legacy automatic flag over a manual municipality", () => {
    expect(shouldRestoreAutomaticLocation({
      enabled: true,
      location: { city: "Trieste", source: "manual" },
    })).toBe(false);
    expect(shouldRestoreAutomaticLocation({
      enabled: true,
      location: { city: "Pordenone", source: "browser_geolocation" },
    })).toBe(true);
    expect(getAutomaticLocationBootstrapState({
      enabled: true,
      location: { city: "Trieste", source: "manual" },
    })).toEqual({
      autoLocationEnabled: false,
      requiresStorageRepair: true,
    });
  });

  it("requires a fresh and precise fix before changing municipality", () => {
    expect(getAutomaticLocationQualityDecision(buildResult())).toMatchObject({ ok: true });
    expect(getAutomaticLocationQualityDecision(buildResult({
      coords: { accuracyM: 250, lat: 45.9567, lon: 12.6605 },
    }))).toMatchObject({ ok: true });
    expect(getAutomaticLocationQualityDecision(buildResult({
      coords: { accuracyM: 250.01, lat: 45.9567, lon: 12.6605 },
    }))).toEqual({ ok: false, reason: "stale_or_imprecise" });
    expect(getAutomaticLocationQualityDecision(buildResult({
      ageMs: AUTO_LOCATION_MAX_AGE_MS + 1,
    }))).toEqual({ ok: false, reason: "stale_or_imprecise" });
    expect(getAutomaticLocationQualityDecision(buildResult({
      coords: { accuracyM: null, lat: 45.9567, lon: 12.6605 },
    }))).toEqual({ ok: false, reason: "missing_quality" });
    expect(getAutomaticLocationQualityDecision(buildResult({
      coords: { accuracyM: -1, lat: 45.9567, lon: 12.6605 },
    }))).toEqual({ ok: false, reason: "missing_quality" });
  });

  it("checks only when visible, enabled, due and idle", () => {
    expect(shouldRunAutomaticLocationCheck({ enabled: false, now: 1000 })).toBe(false);
    expect(shouldRunAutomaticLocationCheck({ enabled: true, now: 1000 })).toBe(true);
    expect(shouldRunAutomaticLocationCheck({
      enabled: true,
      lastCheckedAt: 1000,
      now: 2000,
    })).toBe(false);
    expect(shouldRunAutomaticLocationCheck({
      enabled: true,
      inFlight: true,
      now: Number.MAX_SAFE_INTEGER,
    })).toBe(false);
    expect(shouldRunAutomaticLocationCheck({
      enabled: true,
      now: Number.MAX_SAFE_INTEGER,
      visibilityState: "hidden",
    })).toBe(false);
  });

  it("runs one-shot on start, deduplicates while in flight and respects the foreground cadence", async () => {
    let resolveRequest;
    const requestCoordinates = vi.fn(() => new Promise((resolve) => {
      resolveRequest = resolve;
    }));
    const documentTarget = createEventTarget({ visibilityState: "visible" });
    const windowTarget = createWindowTarget();
    const onResult = vi.fn();
    const runtime = startAutomaticLocationRuntime({
      documentTarget,
      now: () => 1000,
      onResult,
      requestCoordinates,
      windowTarget,
    });

    expect(requestCoordinates).toHaveBeenCalledTimes(1);
    documentTarget.dispatch("visibilitychange");
    expect(requestCoordinates).toHaveBeenCalledTimes(1);
    resolveRequest(buildResult());
    await Promise.resolve();
    await Promise.resolve();
    expect(onResult).toHaveBeenCalledWith(expect.objectContaining({ ok: true }));

    documentTarget.visibilityState = "hidden";
    documentTarget.dispatch("visibilitychange");
    expect(requestCoordinates).toHaveBeenCalledTimes(1);
    documentTarget.visibilityState = "visible";
    documentTarget.dispatch("visibilitychange");
    expect(requestCoordinates).toHaveBeenCalledTimes(1);

    windowTarget.dispatch("online");
    expect(requestCoordinates).toHaveBeenCalledTimes(2);

    runtime.stop();
    expect(windowTarget.clearInterval).toHaveBeenCalledWith(17);
    expect(documentTarget.removeEventListener).toHaveBeenCalledWith(
      "visibilitychange",
      expect.any(Function),
    );
  });

  it("does not duplicate the explicit GPS check that just enabled automatic mode", () => {
    const requestCoordinates = vi.fn();
    const runtime = startAutomaticLocationRuntime({
      documentTarget: createEventTarget({ visibilityState: "visible" }),
      initialLastCheckedAt: 1000,
      now: () => 1001,
      requestCoordinates,
      windowTarget: createWindowTarget(),
    });

    expect(requestCoordinates).not.toHaveBeenCalled();
    runtime.stop();
  });

  it("ignores late results after cleanup", async () => {
    let resolveRequest;
    const onResult = vi.fn();
    const runtime = startAutomaticLocationRuntime({
      documentTarget: createEventTarget({ visibilityState: "visible" }),
      onResult,
      requestCoordinates: () => new Promise((resolve) => {
        resolveRequest = resolve;
      }),
      windowTarget: createWindowTarget(),
    });

    runtime.stop();
    resolveRequest(buildResult());
    await Promise.resolve();
    await Promise.resolve();
    expect(onResult).not.toHaveBeenCalled();
  });

  it("does not invoke the result callback twice when its consumer fails", async () => {
    const onResult = vi.fn().mockRejectedValue(new Error("consumer failed"));
    const runtime = startAutomaticLocationRuntime({
      documentTarget: createEventTarget({ visibilityState: "visible" }),
      onResult,
      requestCoordinates: vi.fn().mockResolvedValue(buildResult()),
      windowTarget: createWindowTarget(),
    });

    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(onResult).toHaveBeenCalledTimes(1);
    runtime.stop();
  });
});
