import { describe, expect, it, vi } from "vitest";

import {
  CAPACITOR_GEOLOCATION_OPTIONS,
  CAPACITOR_GEOLOCATION_STAGES,
  CAPACITOR_LOCATION_MAX_FUTURE_SKEW_MS,
  getCapacitorLocationPermissionDecision,
  getCapacitorLocationPermissionDetails,
  normalizeCapacitorPosition,
  requestCapacitorDeviceCoordinates,
} from "./capacitorLocationAdapter";

const ANDROID_RUNTIME = {
  getPlatform: () => "android",
  isNativePlatform: () => true,
};

describe("Capacitor location adapter", () => {
  it("normalizes the plugin permission states", () => {
    expect(getCapacitorLocationPermissionDecision({ location: "granted" })).toBe("granted");
    expect(getCapacitorLocationPermissionDecision({ coarseLocation: "granted" })).toBe("granted");
    expect(getCapacitorLocationPermissionDecision({ location: "prompt-with-rationale" })).toBe("prompt");
    expect(getCapacitorLocationPermissionDecision({ location: "denied" })).toBe("denied");
    expect(getCapacitorLocationPermissionDetails({
      coarseLocation: "granted",
      location: "denied",
    })).toEqual({
      decision: "granted",
      precision: "approximate",
    });
    expect(getCapacitorLocationPermissionDetails({
      coarseLocation: "granted",
      location: "granted",
    })).toEqual({
      decision: "granted",
      precision: "precise",
    });
  });

  it("uses a strict cached fix immediately and never starts a watcher", async () => {
    expect(CAPACITOR_GEOLOCATION_OPTIONS).toEqual({
      enableHighAccuracy: true,
      maximumAge: 0,
      timeout: 18500,
    });
    const geolocation = {
      checkPermissions: vi.fn().mockResolvedValue({ location: "granted" }),
      getCurrentPosition: vi.fn().mockResolvedValue({
        coords: { accuracy: 14, latitude: 45.9567, longitude: 12.6605 },
        timestamp: 9000,
      }),
      requestPermissions: vi.fn(),
      watchPosition: vi.fn(),
    };

    await expect(requestCapacitorDeviceCoordinates({
      capacitor: ANDROID_RUNTIME,
      geolocation,
      now: () => 10000,
    })).resolves.toEqual({
      ageMs: 1000,
      acquisitionStage: "fast",
      coords: { accuracyM: 14, lat: 45.9567, lon: 12.6605 },
      ok: true,
      precision: "precise",
      source: "capacitor_geolocation",
    });

    expect(geolocation.getCurrentPosition).toHaveBeenCalledWith(
      CAPACITOR_GEOLOCATION_STAGES[0].options,
    );
    expect(geolocation.requestPermissions).not.toHaveBeenCalled();
    expect(geolocation.watchPosition).not.toHaveBeenCalled();
  });

  it("escalates from a stale cache to balanced and then precise only as needed", async () => {
    const geolocation = {
      checkPermissions: vi.fn().mockResolvedValue({ location: "granted" }),
      getCurrentPosition: vi.fn()
        .mockResolvedValueOnce({
          coords: { accuracy: 20, latitude: 45.9567, longitude: 12.6605 },
          timestamp: 1,
        })
        .mockResolvedValueOnce({
          coords: { accuracy: 600, latitude: 45.9567, longitude: 12.6605 },
          timestamp: 100_000,
        })
        .mockResolvedValueOnce({
          coords: { accuracy: 18, latitude: 45.9568, longitude: 12.6606 },
          timestamp: 100_000,
        }),
      requestPermissions: vi.fn(),
      watchPosition: vi.fn(),
    };

    await expect(requestCapacitorDeviceCoordinates({
      capacitor: ANDROID_RUNTIME,
      geolocation,
      now: () => 200_000,
    })).resolves.toMatchObject({
      acquisitionStage: "precise",
      ok: true,
      source: "capacitor_geolocation",
    });
    expect(geolocation.getCurrentPosition.mock.calls.map(([value]) => value)).toEqual(
      CAPACITOR_GEOLOCATION_STAGES.map((stage) => stage.options),
    );
    expect(geolocation.watchPosition).not.toHaveBeenCalled();
  });

  it("keeps a balanced fix without paying the high-accuracy timeout", async () => {
    const geolocation = {
      checkPermissions: vi.fn().mockResolvedValue({ location: "granted" }),
      getCurrentPosition: vi.fn()
        .mockRejectedValueOnce(Object.assign(new Error("timeout"), { code: "OS-PLUG-GLOC-0010" }))
        .mockResolvedValueOnce({
          coords: { accuracy: 90, latitude: 46.1, longitude: 13.1 },
          timestamp: 50_000,
        }),
      requestPermissions: vi.fn(),
    };

    await expect(requestCapacitorDeviceCoordinates({
      capacitor: ANDROID_RUNTIME,
      geolocation,
      now: () => 50_000,
    })).resolves.toMatchObject({
      acquisitionStage: "balanced",
      ok: true,
      source: "capacitor_geolocation",
    });
    expect(geolocation.getCurrentPosition).toHaveBeenCalledTimes(2);
  });

  it("preserves Android approximate permission on the returned one-shot fix", async () => {
    const geolocation = {
      checkPermissions: vi.fn().mockResolvedValue({
        coarseLocation: "granted",
        location: "denied",
      }),
      getCurrentPosition: vi.fn().mockResolvedValue({
        coords: { accuracy: 200, latitude: 45.9567, longitude: 12.6605 },
        timestamp: 9000,
      }),
      requestPermissions: vi.fn(),
      watchPosition: vi.fn(),
    };

    await expect(requestCapacitorDeviceCoordinates({
      capacitor: ANDROID_RUNTIME,
      geolocation,
      options: CAPACITOR_GEOLOCATION_OPTIONS,
      now: () => 10000,
    })).resolves.toMatchObject({
      ok: true,
      precision: "approximate",
      source: "capacitor_geolocation",
    });
    expect(geolocation.requestPermissions).not.toHaveBeenCalled();
    expect(geolocation.watchPosition).not.toHaveBeenCalled();
  });

  it("requests the Android location permission only when it is still promptable", async () => {
    const geolocation = {
      checkPermissions: vi.fn().mockResolvedValue({ location: "prompt" }),
      getCurrentPosition: vi.fn().mockResolvedValue({
        coords: { accuracy: 10, latitude: 46.1, longitude: 13.1 },
        timestamp: 1000,
      }),
      requestPermissions: vi.fn().mockResolvedValue({ location: "granted" }),
    };

    const result = await requestCapacitorDeviceCoordinates({
      capacitor: ANDROID_RUNTIME,
      geolocation,
      options: CAPACITOR_GEOLOCATION_OPTIONS,
      now: () => 1000,
    });

    expect(result.ok).toBe(true);
    expect(geolocation.requestPermissions).toHaveBeenCalledWith({ permissions: ["location"] });
  });

  it("stops on a denied permission instead of falling through to another provider", async () => {
    const geolocation = {
      checkPermissions: vi.fn().mockResolvedValue({ location: "denied" }),
      getCurrentPosition: vi.fn(),
      requestPermissions: vi.fn(),
    };

    await expect(requestCapacitorDeviceCoordinates({
      capacitor: ANDROID_RUNTIME,
      geolocation,
    })).resolves.toEqual({
      ok: false,
      reason: "permission_denied",
      source: "capacitor_geolocation",
    });
    expect(geolocation.requestPermissions).not.toHaveBeenCalled();
    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled();
  });

  it("is unavailable outside native Android", async () => {
    await expect(requestCapacitorDeviceCoordinates({
      capacitor: { getPlatform: () => "web", isNativePlatform: () => false },
      geolocation: {},
    })).resolves.toMatchObject({
      ok: false,
      reason: "capacitor_geolocation_unavailable",
    });
  });

  it("rejects malformed fixes", () => {
    expect(normalizeCapacitorPosition({ coords: {} })).toEqual({
      ok: false,
      reason: "missing_coordinates",
      source: "capacitor_geolocation",
    });
  });

  it("fails closed when Android omits fix quality or returns a far-future timestamp", () => {
    expect(normalizeCapacitorPosition({
      coords: { accuracy: 20, latitude: 45.9567, longitude: 12.6605 },
    }, { now: () => 100_000 })).toEqual({
      ok: false,
      reason: "missing_quality",
      source: "capacitor_geolocation",
    });
    expect(normalizeCapacitorPosition({
      coords: { accuracy: 20, latitude: 45.9567, longitude: 12.6605 },
      timestamp: 100_000 + CAPACITOR_LOCATION_MAX_FUTURE_SKEW_MS + 1,
    }, { now: () => 100_000 })).toEqual({
      ok: false,
      reason: "missing_quality",
      source: "capacitor_geolocation",
    });
    expect(normalizeCapacitorPosition({
      coords: { accuracy: 20, latitude: 45.9567, longitude: 12.6605 },
      timestamp: 100_000 + CAPACITOR_LOCATION_MAX_FUTURE_SKEW_MS,
    }, { now: () => 100_000 })).toMatchObject({
      ageMs: 0,
      ok: true,
    });
  });
});
