import { describe, expect, it, vi } from "vitest";

import {
  DEVICE_GEOLOCATION_OPTIONS,
  DEVICE_LOCATION_MAX_ACCURACY_M,
  buildReliableDeviceAppLocation,
  getDeviceAppLocationUpdatePlan,
  getDeviceCoordinateQualityDecision,
  getGeolocationErrorReason,
  getNativeDeviceCoordinateDecision,
  requestDeviceCoordinates,
} from "./deviceLocation";
import { CAPACITOR_GEOLOCATION_OPTIONS } from "./capacitorLocationAdapter";
import { NATIVE_LOCATION_LEGACY_RESULT_EVENT } from "./nativeLocationAdapter";

function dispatchNativeLocation(target, detail, eventName = NATIVE_LOCATION_LEGACY_RESULT_EVENT) {
  const event = new Event(eventName);
  event.detail = detail;
  target.dispatchEvent(event);
}

describe("device location service", () => {
  it("allows a 25-second high-accuracy cold fix without accepting cached positions", () => {
    expect(DEVICE_GEOLOCATION_OPTIONS).toEqual({
      enableHighAccuracy: true,
      maximumAge: 0,
      timeout: 25000,
    });
  });

  it("maps geolocation errors to stable reasons", () => {
    expect(getGeolocationErrorReason({ code: 1, PERMISSION_DENIED: 1 })).toBe("permission_denied");
    expect(getGeolocationErrorReason({ code: 3, TIMEOUT: 3 })).toBe("timeout");
    expect(getGeolocationErrorReason({ code: 2 })).toBe("unavailable");
  });

  it("fails closed above 250 metres for automatic identity updates", () => {
    const buildFix = (accuracyM) => ({
      ageMs: 1000,
      coords: { accuracyM, lat: 45.9567, lon: 12.6605 },
      ok: true,
      source: "test",
    });

    expect(DEVICE_LOCATION_MAX_ACCURACY_M).toBe(250);
    expect(getDeviceCoordinateQualityDecision(buildFix(250))).toMatchObject({ ok: true });
    expect(getDeviceCoordinateQualityDecision(buildFix(250.01))).toEqual({
      ok: false,
      reason: "stale_or_imprecise",
      source: "test",
    });
  });

  it("builds a canonical stored location from every reliable fix", () => {
    const decision = buildReliableDeviceAppLocation({
      city: "Montereale Valcellina",
      displayName: "Malnisio",
      dataPoint: {
        lat: 46.1601,
        lon: 12.6551,
        source: "rafvg_irdat_5000",
      },
      lat: 46,
      locality: {
        datasetVersion: "2006",
        id: "irdat:malnisio",
        name: "Malnisio",
      },
      lon: 12,
      resolution: {
        boundaryDistanceM: 500,
        localityCorroborated: true,
        municipalityResolved: true,
        status: "resolved",
      },
    }, {
      ageMs: 1500,
      coords: { accuracyM: 24, lat: 46.1623, lon: 12.6578 },
      source: "capacitor_geolocation",
    }, { now: () => 100_000 });

    expect(decision).toMatchObject({
      ok: true,
      location: {
        displayName: "Malnisio",
        lat: 46.1601,
        locality: {
          datasetVersion: "2006",
          id: "irdat:malnisio",
        },
        lon: 12.6551,
        positionAccuracyM: 24,
        positionCapturedAt: "1970-01-01T00:01:38.500Z",
        resolution: {
          boundaryDistanceM: 500,
          localityCorroborated: true,
          status: "resolved",
        },
        source: "capacitor_geolocation",
      },
    });
    const location = decision.location;
    expect(location.lat).not.toBe(46.1623);
    expect(location.lon).not.toBe(12.6578);
    expect(getDeviceAppLocationUpdatePlan({
      lat: 46.16008,
      lon: 12.65508,
    }, location, { placeChanged: false })).toEqual({
      coordsChanged: false,
      placeChanged: false,
      shouldRefreshPushEvidence: true,
      shouldRefreshRuntime: false,
      shouldUpdateVisibleLocation: false,
    });
    expect(getDeviceAppLocationUpdatePlan({
      lat: 46.1,
      lon: 12.6,
    }, location, { placeChanged: false })).toEqual({
      coordsChanged: true,
      placeChanged: false,
      shouldRefreshPushEvidence: false,
      shouldRefreshRuntime: true,
      shouldUpdateVisibleLocation: true,
    });
    expect(getDeviceAppLocationUpdatePlan(location, location, {
      placeChanged: true,
    })).toMatchObject({
      coordsChanged: false,
      placeChanged: true,
      shouldRefreshRuntime: true,
      shouldUpdateVisibleLocation: true,
    });
  });

  it("rejects an otherwise precise fix whose uncertainty crosses a boundary", () => {
    const buildDecision = (boundaryDistanceM) => buildReliableDeviceAppLocation({
      city: "Fontanafredda",
      dataPoint: {
        lat: 45.9901,
        lon: 12.5481,
        source: "municipality_catalog",
      },
      resolution: { boundaryDistanceM, status: "resolved" },
    }, {
      ageMs: 1000,
      coords: { accuracyM: 100, lat: 45.9892, lon: 12.5473 },
      source: "capacitor_geolocation",
    }, { now: () => 100_000 });

    expect(buildDecision(80)).toEqual({
      ok: false,
      reason: "ambiguous_boundary",
    });
    expect(buildDecision(undefined)).toEqual({
      ok: false,
      reason: "ambiguous_boundary",
    });
    expect(buildDecision(500)).toMatchObject({
      ok: true,
      location: {
        lat: 45.9901,
        lon: 12.5481,
        positionAccuracyM: 100,
      },
    });
  });

  it("accepts a named external place only through its canonical public point", () => {
    const decision = buildReliableDeviceAppLocation({
      city: "Bologna",
      displayName: "Bologna",
      region: "Emilia-Romagna",
      dataPoint: {
        lat: 44.4938203,
        lon: 11.3426327,
        source: "nominatim_place",
      },
      resolution: {
        status: "external_place",
        municipalityResolved: false,
        localityCorroborated: false,
      },
    }, {
      ageMs: 1000,
      coords: { accuracyM: 20, lat: 44.4949188, lon: 11.3429472 },
      source: "capacitor_geolocation",
    }, { now: () => 100_000 });

    expect(decision).toMatchObject({
      ok: true,
      location: {
        city: "Bologna",
        lat: 44.4938203,
        lon: 11.3426327,
        positionAccuracyM: 20,
        resolution: { status: "external_place" },
      },
    });
    expect(decision.location.lat).not.toBe(44.4949188);
    expect(decision.location.lon).not.toBe(11.3429472);
  });

  it("fails closed when the backend omits the canonical weather data point", () => {
    expect(buildReliableDeviceAppLocation({
      city: "Fontanafredda",
      lat: 45.9892,
      lon: 12.5473,
      resolution: { boundaryDistanceM: 500, status: "municipality_only" },
    }, {
      ageMs: 1000,
      coords: { accuracyM: 20, lat: 45.9892, lon: 12.5473 },
      source: "capacitor_geolocation",
    }, { now: () => 100_000 })).toEqual({
      ok: false,
      reason: "missing_quality",
    });
  });

  it("returns unsupported when the browser API is missing", async () => {
    await expect(requestDeviceCoordinates({ geolocation: null })).resolves.toEqual({
      ok: false,
      reason: "unsupported",
    });
  });

  it("uses Capacitor Geolocation first on native Android without starting background tracking", async () => {
    const capacitorGeolocation = {
      checkPermissions: vi.fn().mockResolvedValue({ location: "granted" }),
      getCurrentPosition: vi.fn().mockResolvedValue({
        coords: { accuracy: 18, latitude: 45.9567, longitude: 12.6605 },
        timestamp: 99_000,
      }),
      requestPermissions: vi.fn(),
      watchPosition: vi.fn(),
    };
    const geolocation = { getCurrentPosition: vi.fn() };
    const nativeBridge = { requestFastLocation: vi.fn() };

    await expect(requestDeviceCoordinates({
      capacitorGeolocation,
      capacitorRuntime: {
        getPlatform: () => "android",
        isNativePlatform: () => true,
      },
      geolocation,
      nativeBridge,
      now: () => 100_000,
    })).resolves.toEqual({
      acquisitionStage: "fast",
      ageMs: 1000,
      coords: { accuracyM: 18, lat: 45.9567, lon: 12.6605 },
      ok: true,
      precision: "precise",
      source: "capacitor_geolocation",
    });

    expect(capacitorGeolocation.watchPosition).not.toHaveBeenCalled();
    expect(nativeBridge.requestFastLocation).not.toHaveBeenCalled();
    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled();
  });

  it("does not expose an Android approximate fix for municipality or push resolution", async () => {
    const capacitorGeolocation = {
      checkPermissions: vi.fn().mockResolvedValue({
        coarseLocation: "granted",
        location: "denied",
      }),
      getCurrentPosition: vi.fn().mockResolvedValue({
        coords: { accuracy: 150, latitude: 45.9567, longitude: 12.6605 },
        timestamp: 99_000,
      }),
      requestPermissions: vi.fn(),
    };

    await expect(requestDeviceCoordinates({
      capacitorGeolocation,
      capacitorRuntime: {
        getPlatform: () => "android",
        isNativePlatform: () => true,
      },
      geolocation: { getCurrentPosition: vi.fn() },
      now: () => 100_000,
    })).resolves.toEqual({
      ok: false,
      precision: "approximate",
      reason: "approximate_location",
      source: "capacitor_geolocation",
    });
  });

  it("rejects stale and imprecise Capacitor fixes before reverse geocoding", async () => {
    const runtime = {
      getPlatform: () => "android",
      isNativePlatform: () => true,
    };
    const geolocation = {
      checkPermissions: vi.fn().mockResolvedValue({ location: "granted" }),
      getCurrentPosition: vi.fn()
        .mockResolvedValueOnce({
          coords: { accuracy: 20, latitude: 45.9567, longitude: 12.6605 },
          timestamp: 1000,
        })
        .mockResolvedValueOnce({
          coords: { accuracy: 250.01, latitude: 45.9567, longitude: 12.6605 },
          timestamp: 100_000,
        })
        .mockResolvedValue({
          coords: { accuracy: 250.01, latitude: 45.9567, longitude: 12.6605 },
          timestamp: 100_000,
        }),
      requestPermissions: vi.fn(),
    };

    await expect(requestDeviceCoordinates({
      capacitorGeolocation: geolocation,
      capacitorRuntime: runtime,
      now: () => 200_000,
    })).resolves.toMatchObject({
      ok: false,
      reason: "stale_or_imprecise",
    });
    await expect(requestDeviceCoordinates({
      capacitorGeolocation: geolocation,
      capacitorRuntime: runtime,
      now: () => 100_000,
    })).resolves.toMatchObject({
      ok: false,
      reason: "stale_or_imprecise",
    });
  });

  it("forces a non-cached precise Capacitor request for submit verification", async () => {
    const runtime = {
      getPlatform: () => "android",
      isNativePlatform: () => true,
    };
    const geolocation = {
      checkPermissions: vi.fn().mockResolvedValue({ location: "granted" }),
      getCurrentPosition: vi.fn().mockResolvedValue({
        coords: { accuracy: 20, latitude: 45.9567, longitude: 12.6605 },
        timestamp: 100_000,
      }),
      requestPermissions: vi.fn(),
    };

    await expect(requestDeviceCoordinates({
      capacitorGeolocation: geolocation,
      capacitorRuntime: runtime,
      maxAgeMs: 30_000,
      now: () => 100_000,
      requireCurrent: true,
    })).resolves.toMatchObject({ ok: true, ageMs: 0 });
    expect(geolocation.getCurrentPosition).toHaveBeenCalledExactlyOnceWith(
      CAPACITOR_GEOLOCATION_OPTIONS,
    );
  });

  it("resolves finite coordinates without deciding the city", async () => {
    const geolocation = {
      getCurrentPosition: vi.fn((onSuccess) => {
        onSuccess({
          timestamp: 99_500,
          coords: {
            latitude: "46.0693",
            longitude: "13.2372",
            accuracy: "35",
          },
        });
      }),
    };

    await expect(requestDeviceCoordinates({
      geolocation,
      now: () => 100_000,
    })).resolves.toEqual({
      ok: true,
      source: "browser_geolocation",
      ageMs: 500,
      coords: {
        lat: 46.0693,
        lon: 13.2372,
        accuracyM: 35,
      },
    });
    expect(geolocation.getCurrentPosition).toHaveBeenCalledWith(
      expect.any(Function),
      expect.any(Function),
      DEVICE_GEOLOCATION_OPTIONS,
    );
  });

  it("does not return success for missing coordinates", async () => {
    const geolocation = {
      getCurrentPosition: vi.fn((onSuccess) => {
        onSuccess({ coords: { latitude: "", longitude: "" } });
      }),
    };

    await expect(requestDeviceCoordinates({ geolocation })).resolves.toEqual({
      ok: false,
      reason: "missing_coordinates",
    });
  });

  it("stops waiting when browser geolocation never calls back", async () => {
    vi.useFakeTimers();
    try {
      const getCurrentPosition = vi.fn();
      const result = requestDeviceCoordinates({
        geolocation: { getCurrentPosition },
        preferNative: false,
        options: { ...DEVICE_GEOLOCATION_OPTIONS, timeout: 1000 },
      });

      await vi.advanceTimersByTimeAsync(2000);
      await expect(result).resolves.toEqual({ ok: false, reason: "timeout" });
      expect(getCurrentPosition).toHaveBeenCalledOnce();
    } finally {
      vi.useRealTimers();
    }
  });

  it("uses Android fast location before browser geolocation when the native bridge is available", async () => {
    const nativeEventTarget = new EventTarget();
    const geolocation = {
      getCurrentPosition: vi.fn(),
    };
    const nativeBridge = {
      requestFastLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(nativeEventTarget, {
            ok: true,
            lat: 45.9567,
            lon: 12.6605,
            accuracy_m: 35,
            age_ms: 1000,
            requestId,
          });
        });
      }),
    };

    await expect(requestDeviceCoordinates({ geolocation, nativeBridge, nativeEventTarget })).resolves.toEqual({
      ok: true,
      confidence: "fast",
      source: "android_last_location",
      coords: {
        lat: 45.9567,
        lon: 12.6605,
        accuracyM: 35,
      },
      ageMs: 1000,
    });
    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled();
  });

  it("tries Android balanced location when the fast location is stale", async () => {
    const nativeEventTarget = new EventTarget();
    const nativeBridge = {
      requestFastLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(nativeEventTarget, {
            ok: true,
            lat: 45.9567,
            lon: 12.6605,
            accuracy_m: 35,
            age_ms: 2 * 60 * 60 * 1000,
            requestId,
          });
        });
      }),
      requestBalancedLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(nativeEventTarget, {
            ok: true,
            lat: 46.0711,
            lon: 13.2346,
            accuracy_m: 20,
            age_ms: 500,
            requestId,
          });
        });
      }),
    };

    await expect(requestDeviceCoordinates({ geolocation: null, nativeBridge, nativeEventTarget })).resolves.toMatchObject({
      ok: true,
      confidence: "current",
      source: "android_current_location",
      coords: {
        lat: 46.0711,
        lon: 13.2346,
        accuracyM: 20,
      },
    });
    expect(nativeBridge.requestBalancedLocation).toHaveBeenCalledWith(expect.any(String), 2800);
  });

  it("bypasses the cached native fast path for submit verification", async () => {
    const nativeEventTarget = new EventTarget();
    const nativeBridge = {
      requestFastLocation: vi.fn(),
      requestBalancedLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(nativeEventTarget, {
            ok: true,
            lat: 45.9568,
            lon: 12.6606,
            accuracy_m: 20,
            age_ms: 500,
            requestId,
          });
        });
      }),
    };

    await expect(requestDeviceCoordinates({
      geolocation: null,
      maxAgeMs: 30_000,
      nativeBridge,
      nativeEventTarget,
      requireCurrent: true,
    })).resolves.toMatchObject({
      ageMs: 500,
      confidence: "current",
      ok: true,
      source: "android_current_location",
    });
    expect(nativeBridge.requestFastLocation).not.toHaveBeenCalled();
    expect(nativeBridge.requestBalancedLocation).toHaveBeenCalledTimes(1);
  });

  it("uses per-call report quality so a five-minute native cache requests balanced", async () => {
    const nativeEventTarget = new EventTarget();
    const geolocation = { getCurrentPosition: vi.fn() };
    const nativeBridge = {
      requestFastLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(nativeEventTarget, {
            ok: true,
            lat: 45.9567,
            lon: 12.6605,
            accuracy_m: 25,
            age_ms: 5 * 60 * 1000,
            requestId,
          });
        });
      }),
      requestBalancedLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(nativeEventTarget, {
            ok: true,
            lat: 45.9568,
            lon: 12.6606,
            accuracy_m: 30,
            age_ms: 500,
            requestId,
          });
        });
      }),
    };

    await expect(requestDeviceCoordinates({
      geolocation,
      maxAccuracyM: 1000,
      maxAgeMs: 2 * 60 * 1000,
      nativeBridge,
      nativeEventTarget,
    })).resolves.toMatchObject({
      ageMs: 500,
      confidence: "current",
      ok: true,
      source: "android_current_location",
    });
    expect(nativeBridge.requestBalancedLocation).toHaveBeenCalledTimes(1);
    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled();
  });

  it("keeps the fast path when native report coordinates are fresh and precise", async () => {
    const nativeEventTarget = new EventTarget();
    const nativeBridge = {
      requestFastLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(nativeEventTarget, {
            ok: true,
            lat: 45.9567,
            lon: 12.6605,
            accuracy_m: 25,
            age_ms: 30_000,
            requestId,
          });
        });
      }),
      requestBalancedLocation: vi.fn(),
    };

    await expect(requestDeviceCoordinates({
      geolocation: null,
      maxAccuracyM: 1000,
      maxAgeMs: 2 * 60 * 1000,
      nativeBridge,
      nativeEventTarget,
    })).resolves.toMatchObject({
      ageMs: 30_000,
      confidence: "fast",
      ok: true,
      source: "android_last_location",
    });
    expect(nativeBridge.requestBalancedLocation).not.toHaveBeenCalled();
  });

  it("does not fall back to browser geolocation after a native permission denial", async () => {
    const nativeEventTarget = new EventTarget();
    const geolocation = {
      getCurrentPosition: vi.fn(),
    };
    const nativeBridge = {
      requestFastLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(nativeEventTarget, {
            ok: false,
            reason: "permission_denied",
            requestId,
            source: "android_last_location",
          });
        });
      }),
    };

    await expect(requestDeviceCoordinates({ geolocation, nativeBridge, nativeEventTarget })).resolves.toMatchObject({
      ok: false,
      reason: "permission_denied",
      source: "android_last_location",
    });
    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled();
  });

  it("does not expose an explicitly coarse legacy native fix", async () => {
    const nativeEventTarget = new EventTarget();
    const nativeBridge = {
      requestFastLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(nativeEventTarget, {
            accuracy_m: 30,
            age_ms: 1000,
            lat: 45.9567,
            lon: 12.6605,
            ok: true,
            permission: "coarse",
            requestId,
          });
        });
      }),
    };

    await expect(requestDeviceCoordinates({
      geolocation: null,
      nativeBridge,
      nativeEventTarget,
    })).resolves.toEqual({
      ok: false,
      precision: "approximate",
      reason: "approximate_location",
      source: "android_last_location",
    });
  });

  it("falls back to browser geolocation when Android has no usable position", async () => {
    const nativeEventTarget = new EventTarget();
    const nativeBridge = {
      requestFastLocation: vi.fn((requestId) => {
        queueMicrotask(() => {
          dispatchNativeLocation(nativeEventTarget, {
            ok: false,
            reason: "null_location",
            requestId,
            source: "android_last_location",
          });
        });
      }),
    };
    const geolocation = {
      getCurrentPosition: vi.fn((onSuccess) => {
        onSuccess({
          timestamp: 99_800,
          coords: {
            latitude: 45.6495,
            longitude: 13.7768,
            accuracy: 50,
          },
        });
      }),
    };

    await expect(requestDeviceCoordinates({
      geolocation,
      nativeBridge,
      nativeEventTarget,
      now: () => 100_000,
    })).resolves.toEqual({
      ok: true,
      source: "browser_geolocation",
      ageMs: 200,
      coords: {
        lat: 45.6495,
        lon: 13.7768,
        accuracyM: 50,
      },
    });
  });

  it("rejects stale or imprecise native coordinates before the UI sees them", () => {
    expect(getNativeDeviceCoordinateDecision({
      ok: true,
      lat: 45.9567,
      lon: 12.6605,
      accuracy_m: 12000,
      age_ms: 1000,
    })).toMatchObject({
      ok: false,
      reason: "stale_or_imprecise",
    });
  });

  it("clamps a future browser timestamp to zero age", async () => {
    const geolocation = {
      getCurrentPosition: vi.fn((onSuccess) => {
        onSuccess({
          timestamp: 100_500,
          coords: {
            latitude: 45.9567,
            longitude: 12.6605,
            accuracy: 30,
          },
        });
      }),
    };

    await expect(requestDeviceCoordinates({
      geolocation,
      now: () => 100_000,
    })).resolves.toMatchObject({ ageMs: 0, ok: true });
  });
});
