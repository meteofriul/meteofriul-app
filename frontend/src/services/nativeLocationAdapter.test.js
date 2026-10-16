import { afterEach, describe, expect, it, vi } from "vitest";

import {
  NATIVE_LOCATION_LEGACY_RESULT_EVENT,
  NATIVE_LOCATION_METHODS,
  NATIVE_LOCATION_RESULT_EVENT,
  getNativeLocationStatus,
  isNativeLocationBridgeAvailable,
  normalizeNativeLocationPayload,
  requestNativeBalancedLocation,
  requestNativeFastLocation,
  requestNativeLocationPermission,
} from "./nativeLocationAdapter";

function dispatchNativeLocation(target, detail, eventName = NATIVE_LOCATION_RESULT_EVENT) {
  const event = new Event(eventName);
  event.detail = detail;
  target.dispatchEvent(event);
}

afterEach(() => {
  vi.useRealTimers();
});

describe("nativeLocationAdapter", () => {
  it("reports unavailable when the Android bridge is missing", async () => {
    expect(isNativeLocationBridgeAvailable({ bridge: null })).toBe(false);
    expect(getNativeLocationStatus({ bridge: null })).toEqual({
      available: false,
      permission: "unsupported",
      servicesEnabled: false,
    });

    await expect(requestNativeFastLocation({
      bridge: null,
      requestId: "missing-bridge",
    })).resolves.toEqual({
      ok: false,
      reason: "native_location_bridge_unavailable",
      source: NATIVE_LOCATION_METHODS.requestFastLocation,
      requestId: "missing-bridge",
    });
  });

  it("normalizes the explicit native location status", () => {
    const bridge = {
      getLocationStatus: () => "{\"permission\":\"granted\",\"servicesEnabled\":true}",
    };

    expect(getNativeLocationStatus({ bridge })).toEqual({
      available: true,
      permission: "granted",
      servicesEnabled: true,
    });
  });

  it("requests native device-location permission through an explicit bridge method", async () => {
    const eventTarget = new EventTarget();
    const bridge = {
      requestLocationPermission: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(eventTarget, {
            ok: true,
            permission: "granted",
            requestId,
            source: "android_permission",
          });
        });
      }),
    };

    await expect(requestNativeLocationPermission({
      bridge,
      eventTarget,
      requestId: "permission-1",
    })).resolves.toMatchObject({
      ok: true,
      permission: "granted",
      requestId: "permission-1",
      source: "android_permission",
    });

    expect(bridge.requestLocationPermission).toHaveBeenCalledWith("permission-1");
  });

  it("waits for the matching request id and ignores stale native events", async () => {
    const eventTarget = new EventTarget();
    const bridge = {
      requestFastLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(eventTarget, {
            ok: true,
            lat: 45,
            lon: 12,
            requestId: "other-request",
          });
          dispatchNativeLocation(eventTarget, {
            ok: true,
            lat: 46.0711,
            lon: 13.2346,
            accuracy_m: 25,
            age_ms: 1000,
            permission: "fine",
            requestId,
            services_enabled: true,
            source: "android_last_location",
          });
        });
      }),
    };

    await expect(requestNativeFastLocation({
      bridge,
      eventTarget,
      requestId: "fast-1",
    })).resolves.toMatchObject({
      ok: true,
      lat: 46.0711,
      lon: 13.2346,
      accuracy_m: 25,
      age_ms: 1000,
      permission: "fine",
      requestId: "fast-1",
      services_enabled: true,
      source: "android_last_location",
    });
  });

  it("accepts the legacy Android fast-location event emitted by the old app bridge", async () => {
    const eventTarget = new EventTarget();
    const bridge = {
      requestFastLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(eventTarget, {
            ok: true,
            lat: 45.9567,
            lon: 12.6605,
            accuracyM: 35,
            permission: "fine",
            requestId,
            servicesEnabled: true,
            source: "android_last_location",
          }, NATIVE_LOCATION_LEGACY_RESULT_EVENT);
        });
      }),
    };

    await expect(requestNativeFastLocation({
      bridge,
      eventTarget,
      requestId: "legacy-fast-1",
    })).resolves.toMatchObject({
      ok: true,
      lat: 45.9567,
      lon: 12.6605,
      accuracy_m: 35,
      permission: "fine",
      requestId: "legacy-fast-1",
      services_enabled: true,
      source: "android_last_location",
    });
  });

  it("passes the balanced timeout to the native bridge", async () => {
    const eventTarget = new EventTarget();
    const bridge = {
      requestBalancedLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(eventTarget, {
            ok: false,
            reason: "null_location",
            requestId,
            source: "android_current_location",
          });
        });
      }),
    };

    await expect(requestNativeBalancedLocation({
      bridge,
      eventTarget,
      requestId: "balanced-1",
      timeoutMs: 2400,
    })).resolves.toMatchObject({
      ok: false,
      reason: "null_location",
      requestId: "balanced-1",
      source: "android_current_location",
    });

    expect(bridge.requestBalancedLocation).toHaveBeenCalledWith("balanced-1", 2400);
  });

  it("returns a controlled timeout when native Android does not answer", async () => {
    vi.useFakeTimers();
    const eventTarget = new EventTarget();
    const bridge = {
      requestFastLocation: vi.fn(),
    };
    const resultPromise = requestNativeFastLocation({
      bridge,
      eventTarget,
      requestId: "timeout-1",
      timeoutMs: 25,
    });

    vi.advanceTimersByTime(26);

    await expect(resultPromise).resolves.toEqual({
      ok: false,
      reason: "native_location_timeout",
      source: NATIVE_LOCATION_METHODS.requestFastLocation,
      requestId: "timeout-1",
    });
  });

  it("normalizes numeric quality fields for downstream GPS policy", () => {
    expect(normalizeNativeLocationPayload({
      ok: true,
      lat: "46.1",
      lon: "13.2",
      accuracyM: "30",
      ageMs: "900",
      requestId: "normalize-1",
    })).toMatchObject({
      ok: true,
      lat: 46.1,
      lon: 13.2,
      accuracy_m: 30,
      age_ms: 900,
      requestId: "normalize-1",
    });
  });
});
