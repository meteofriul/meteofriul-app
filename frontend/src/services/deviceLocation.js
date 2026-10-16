import {
  NATIVE_LOCATION_BALANCED_TIMEOUT_MS,
  NATIVE_LOCATION_BRIDGE_NAME,
  NATIVE_LOCATION_METHODS,
  isNativeLocationBridgeAvailable,
  requestNativeBalancedLocation,
  requestNativeFastLocation,
} from "./nativeLocationAdapter";
import {
  CAPACITOR_GEOLOCATION_OPTIONS,
  requestCapacitorDeviceCoordinates,
} from "./capacitorLocationAdapter";

export const DEVICE_GEOLOCATION_OPTIONS = {
  enableHighAccuracy: true,
  timeout: 25000,
  maximumAge: 0,
};

export const DEVICE_NATIVE_FAST_TIMEOUT_MS = 1200;
export const DEVICE_LOCATION_MAX_AGE_MS = 2 * 60 * 1000;
export const DEVICE_LOCATION_MAX_ACCURACY_M = 250;
export const DEVICE_LOCATION_BOUNDARY_MARGIN_M = 10;
export const DEVICE_LOCATION_SIGNIFICANT_CHANGE_M = 500;
export const DEVICE_NATIVE_FAST_MAX_AGE_MS = DEVICE_LOCATION_MAX_AGE_MS;
export const DEVICE_NATIVE_FAST_MAX_ACCURACY_M = DEVICE_LOCATION_MAX_ACCURACY_M;
export const DEVICE_NATIVE_CONFIRM_MAX_AGE_MS = DEVICE_LOCATION_MAX_AGE_MS;
export const DEVICE_NATIVE_CONFIRM_MAX_ACCURACY_M = DEVICE_LOCATION_MAX_ACCURACY_M;

function coerceFiniteCoordinate(value) {
  if (value == null || value === "") return null;

  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function coerceFiniteNumber(value) {
  if (value == null || value === "") return null;

  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function coerceNonNegativeThreshold(value) {
  const number = coerceFiniteNumber(value);
  return number != null && number >= 0 ? number : null;
}

function getNativeLocationPrecision(permission) {
  const token = String(permission || "").trim().toLowerCase();

  if (["approximate", "coarse"].includes(token)) return "approximate";
  if (["fine", "precise"].includes(token)) return "precise";
  return null;
}

export function getDeviceCoordinateQualityDecision(
  result,
  {
    allowApproximate = false,
    maxAccuracyM = DEVICE_LOCATION_MAX_ACCURACY_M,
    maxAgeMs = DEVICE_LOCATION_MAX_AGE_MS,
  } = {},
) {
  if (!result?.ok) return result;

  if (!allowApproximate && result.precision === "approximate") {
    return {
      ok: false,
      precision: "approximate",
      reason: "approximate_location",
      source: result.source,
    };
  }

  const lat = coerceFiniteCoordinate(result.coords?.lat);
  const lon = coerceFiniteCoordinate(result.coords?.lon);
  const accuracyM = coerceFiniteNumber(result.coords?.accuracyM);
  const ageMs = coerceFiniteNumber(result.ageMs);

  if (
    lat == null ||
    lon == null ||
    accuracyM == null ||
    accuracyM < 0 ||
    ageMs == null ||
    ageMs < 0
  ) {
    return {
      ok: false,
      reason: "missing_quality",
      source: result.source,
    };
  }

  const requestedMaxAccuracyM = coerceNonNegativeThreshold(maxAccuracyM);
  const requestedMaxAgeMs = coerceNonNegativeThreshold(maxAgeMs);
  if (
    (requestedMaxAccuracyM != null && accuracyM > requestedMaxAccuracyM) ||
    (requestedMaxAgeMs != null && ageMs > requestedMaxAgeMs)
  ) {
    return {
      ok: false,
      reason: "stale_or_imprecise",
      source: result.source,
    };
  }

  return {
    ...result,
    ageMs,
    coords: {
      ...result.coords,
      accuracyM,
      lat,
      lon,
    },
  };
}

export function buildReliableDeviceAppLocation(
  reverseLocation,
  deviceLocation,
  {
    boundaryMarginM = DEVICE_LOCATION_BOUNDARY_MARGIN_M,
    now = Date.now,
  } = {},
) {
  const lat = coerceFiniteCoordinate(deviceLocation?.coords?.lat);
  const lon = coerceFiniteCoordinate(deviceLocation?.coords?.lon);
  const accuracyM = coerceFiniteNumber(deviceLocation?.coords?.accuracyM);
  const ageMs = coerceFiniteNumber(deviceLocation?.ageMs);
  const dataLat = coerceFiniteCoordinate(reverseLocation?.dataPoint?.lat);
  const dataLon = coerceFiniteCoordinate(reverseLocation?.dataPoint?.lon);
  const dataPointSource = String(reverseLocation?.dataPoint?.source || "").trim();
  const isExternalCanonicalPlace = dataPointSource === "nominatim_place"
    && reverseLocation?.resolution?.status === "external_place";
  const currentTime = coerceFiniteNumber(
    typeof now === "function" ? now() : now,
  );

  if (
    !reverseLocation ||
    lat == null ||
    lon == null ||
    dataLat == null ||
    dataLon == null ||
    dataLat < -90 ||
    dataLat > 90 ||
    dataLon < -180 ||
    dataLon > 180 ||
    ![
      "rafvg_irdat_5000",
      "municipality_catalog",
      "nominatim_place",
    ].includes(dataPointSource) ||
    accuracyM == null ||
    accuracyM < 0 ||
    ageMs == null ||
    ageMs < 0 ||
    currentTime == null
  ) return { ok: false, reason: "missing_quality" };

  const boundaryDistanceM = coerceFiniteNumber(
    reverseLocation.resolution?.boundaryDistanceM,
  );
  const requestedBoundaryMarginM = coerceNonNegativeThreshold(boundaryMarginM);
  if (!isExternalCanonicalPlace && (
    boundaryDistanceM == null ||
    boundaryDistanceM < 0 ||
    requestedBoundaryMarginM == null ||
    accuracyM + requestedBoundaryMarginM >= boundaryDistanceM
  )) {
    return { ok: false, reason: "ambiguous_boundary" };
  }

  const capturedAt = new Date(currentTime - ageMs);
  if (!Number.isFinite(capturedAt.getTime())) {
    return { ok: false, reason: "missing_quality" };
  }

  return {
    location: {
      ...reverseLocation,
      lat: dataLat,
      lon: dataLon,
      positionAccuracyM: accuracyM,
      positionCapturedAt: capturedAt.toISOString(),
      source: deviceLocation.source || reverseLocation.source || "gps",
    },
    ok: true,
  };
}

export function haveDeviceCoordinatesChanged(currentLocation, nextLocation) {
  const currentLat = coerceFiniteCoordinate(currentLocation?.lat);
  const currentLon = coerceFiniteCoordinate(currentLocation?.lon);
  const nextLat = coerceFiniteCoordinate(nextLocation?.lat);
  const nextLon = coerceFiniteCoordinate(nextLocation?.lon);

  if (
    nextLat == null ||
    nextLon == null ||
    nextLat < -90 ||
    nextLat > 90 ||
    nextLon < -180 ||
    nextLon > 180
  ) return false;
  if (currentLat == null || currentLon == null) return true;
  if (
    currentLat < -90 ||
    currentLat > 90 ||
    currentLon < -180 ||
    currentLon > 180
  ) return true;

  const toRadians = (degrees) => degrees * (Math.PI / 180);
  const deltaLat = toRadians(nextLat - currentLat);
  const deltaLon = toRadians(nextLon - currentLon);
  const firstLat = toRadians(currentLat);
  const secondLat = toRadians(nextLat);
  const haversine = Math.sin(deltaLat / 2) ** 2 +
    Math.cos(firstLat) * Math.cos(secondLat) * Math.sin(deltaLon / 2) ** 2;
  const distanceM = 2 * 6_371_000 * Math.asin(Math.min(1, Math.sqrt(haversine)));

  return distanceM >= DEVICE_LOCATION_SIGNIFICANT_CHANGE_M;
}

export function getDeviceAppLocationUpdatePlan(
  currentLocation,
  nextLocation,
  { placeChanged = false } = {},
) {
  const coordsChanged = haveDeviceCoordinatesChanged(currentLocation, nextLocation);
  const shouldUpdateVisibleLocation = Boolean(placeChanged || coordsChanged);

  return {
    coordsChanged,
    placeChanged: Boolean(placeChanged),
    shouldRefreshPushEvidence: !shouldUpdateVisibleLocation,
    shouldRefreshRuntime: shouldUpdateVisibleLocation,
    shouldUpdateVisibleLocation,
  };
}

export function getGeolocationErrorReason(error) {
  if (error?.code === error?.PERMISSION_DENIED || error?.code === 1) {
    return "permission_denied";
  }

  if (error?.code === error?.TIMEOUT || error?.code === 3) {
    return "timeout";
  }

  return "unavailable";
}

function normalizeBrowserPosition(position, now) {
  const lat = coerceFiniteCoordinate(position?.coords?.latitude);
  const lon = coerceFiniteCoordinate(position?.coords?.longitude);

  if (lat == null || lon == null) {
    return { ok: false, reason: "missing_coordinates" };
  }

  const timestamp = coerceFiniteNumber(position?.timestamp);
  const currentTime = Number(now?.());
  const ageMs = timestamp == null || !Number.isFinite(currentTime)
    ? null
    : Math.max(0, currentTime - timestamp);

  return {
    ok: true,
    source: "browser_geolocation",
    ageMs,
    coords: {
      lat,
      lon,
      accuracyM: coerceFiniteNumber(position.coords.accuracy),
    },
  };
}

export function getNativeDeviceCoordinateDecision(
  payload,
  {
    confirmMaxAccuracyM = DEVICE_NATIVE_CONFIRM_MAX_ACCURACY_M,
    confirmMaxAgeMs = DEVICE_NATIVE_CONFIRM_MAX_AGE_MS,
    fastMaxAccuracyM = DEVICE_NATIVE_FAST_MAX_ACCURACY_M,
    fastMaxAgeMs = DEVICE_NATIVE_FAST_MAX_AGE_MS,
  } = {},
) {
  if (!payload?.ok) {
    return {
      ok: false,
      reason: payload?.reason || "native_location_unavailable",
      source: payload?.source || "native_location",
    };
  }

  const lat = coerceFiniteCoordinate(payload.lat);
  const lon = coerceFiniteCoordinate(payload.lon);
  const ageMs = coerceFiniteNumber(payload.age_ms);
  const accuracyM = coerceFiniteNumber(payload.accuracy_m);
  const precision = getNativeLocationPrecision(payload.permission);

  if (lat == null || lon == null) {
    return { ok: false, reason: "missing_coordinates", source: payload.source };
  }

  if (ageMs == null || ageMs < 0 || accuracyM == null) {
    return { ok: false, reason: "missing_quality", source: payload.source };
  }

  if (ageMs <= fastMaxAgeMs && accuracyM <= fastMaxAccuracyM) {
    return {
      ok: true,
      confidence: "fast",
      source: payload.source || "android_last_location",
      coords: { lat, lon, accuracyM },
      ageMs,
      ...(precision ? { precision } : {}),
    };
  }

  if (ageMs <= confirmMaxAgeMs && accuracyM <= confirmMaxAccuracyM) {
    return {
      ok: true,
      confidence: "confirm",
      source: payload.source || "android_last_location_confirmed",
      coords: { lat, lon, accuracyM },
      ageMs,
      ...(precision ? { precision } : {}),
    };
  }

  return { ok: false, reason: "stale_or_imprecise", source: payload.source };
}

function shouldStopAfterNativeFailure(result) {
  return ["location_services_disabled", "permission_denied"].includes(result?.reason);
}

export async function requestNativeDeviceCoordinates({
  bridge,
  eventTarget = globalThis.window,
  fastTimeoutMs = DEVICE_NATIVE_FAST_TIMEOUT_MS,
  balancedTimeoutMs = NATIVE_LOCATION_BALANCED_TIMEOUT_MS,
  setTimeoutImpl,
  clearTimeoutImpl,
  maxAccuracyM,
  maxAgeMs,
  requireCurrent = false,
} = {}) {
  const requiredMethod = requireCurrent
    ? NATIVE_LOCATION_METHODS.requestBalancedLocation
    : NATIVE_LOCATION_METHODS.requestFastLocation;
  if (!isNativeLocationBridgeAvailable({ bridge, methodName: requiredMethod })) {
    return {
      ok: false,
      reason: "native_location_bridge_unavailable",
      source: "native_location",
    };
  }

  const requestedMaxAccuracyM = coerceNonNegativeThreshold(maxAccuracyM);
  const requestedMaxAgeMs = coerceNonNegativeThreshold(maxAgeMs);
  const strictQuality = {
    ...(requestedMaxAccuracyM != null
      ? {
          confirmMaxAccuracyM: requestedMaxAccuracyM,
          fastMaxAccuracyM: requestedMaxAccuracyM,
        }
      : {}),
    ...(requestedMaxAgeMs != null
      ? {
          confirmMaxAgeMs: requestedMaxAgeMs,
          fastMaxAgeMs: requestedMaxAgeMs,
        }
      : {}),
  };

  if (requireCurrent) {
    const balancedPayload = await requestNativeBalancedLocation({
      bridge,
      eventTarget,
      timeoutMs: balancedTimeoutMs,
      setTimeoutImpl,
      clearTimeoutImpl,
    });
    const balancedDecision = getNativeDeviceCoordinateDecision(
      balancedPayload,
      strictQuality,
    );

    if (!balancedDecision.ok) return balancedDecision;
    return {
      ...balancedDecision,
      confidence: "current",
      source: "android_current_location",
    };
  }

  const fastPayload = await requestNativeFastLocation({
    bridge,
    eventTarget,
    timeoutMs: fastTimeoutMs,
    setTimeoutImpl,
    clearTimeoutImpl,
  });
  const fastDecision = getNativeDeviceCoordinateDecision(fastPayload, strictQuality);

  if (fastDecision.ok) {
    return {
      ...fastDecision,
      source: fastDecision.confidence === "fast"
        ? "android_last_location"
        : "android_last_location_confirmed",
    };
  }

  if (shouldStopAfterNativeFailure(fastDecision)) return fastDecision;

  if (isNativeLocationBridgeAvailable({ bridge, methodName: NATIVE_LOCATION_METHODS.requestBalancedLocation })) {
    const balancedPayload = await requestNativeBalancedLocation({
      bridge,
      eventTarget,
      timeoutMs: balancedTimeoutMs,
      setTimeoutImpl,
      clearTimeoutImpl,
    });
    const balancedDecision = getNativeDeviceCoordinateDecision(
      balancedPayload,
      strictQuality,
    );

    if (balancedDecision.ok) {
      return {
        ...balancedDecision,
        confidence: "current",
        source: "android_current_location",
      };
    }

    if (shouldStopAfterNativeFailure(balancedDecision)) return balancedDecision;
  }

  return fastDecision;
}

function requestBrowserCoordinates({
  geolocation = globalThis.navigator?.geolocation,
  now = Date.now,
  options = DEVICE_GEOLOCATION_OPTIONS,
} = {}) {
  if (!geolocation || typeof geolocation.getCurrentPosition !== "function") {
    return Promise.resolve({ ok: false, reason: "unsupported" });
  }

  return new Promise((resolve) => {
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      globalThis.clearTimeout?.(fallbackTimeoutId);
      resolve(result);
    };
    // Some browsers leave the native timeout suspended while a location
    // permission prompt is unavailable. Keep the report form recoverable.
    const fallbackTimeoutId = globalThis.setTimeout?.(
      () => finish({ ok: false, reason: "timeout" }),
      Math.max(1_000, Number(options?.timeout) || 25_000) + 1_000,
    );
    try {
      geolocation.getCurrentPosition(
        (position) => finish(normalizeBrowserPosition(position, now)),
        (error) => finish({ ok: false, reason: getGeolocationErrorReason(error) }),
        options,
      );
    } catch {
      finish({ ok: false, reason: "unavailable" });
    }
  });
}

export async function requestDeviceCoordinates({
  allowApproximate = false,
  capacitorGeolocation,
  capacitorRuntime,
  geolocation = globalThis.navigator?.geolocation,
  nativeBridge = globalThis.window?.[NATIVE_LOCATION_BRIDGE_NAME],
  nativeEventTarget = globalThis.window,
  now = Date.now,
  options,
  preferCapacitor = true,
  preferNative = true,
  requireCurrent = false,
  maxAccuracyM,
  maxAgeMs,
} = {}) {
  const qualityOptions = {
    allowApproximate,
    maxAccuracyM: coerceNonNegativeThreshold(maxAccuracyM) ?? DEVICE_LOCATION_MAX_ACCURACY_M,
    maxAgeMs: coerceNonNegativeThreshold(maxAgeMs) ?? DEVICE_LOCATION_MAX_AGE_MS,
  };

  if (preferNative && preferCapacitor) {
    const capacitorResult = await requestCapacitorDeviceCoordinates({
      capacitor: capacitorRuntime,
      geolocation: capacitorGeolocation,
      maxAccuracyM: qualityOptions.maxAccuracyM,
      maxAgeMs: qualityOptions.maxAgeMs,
      now,
      options: requireCurrent ? options || CAPACITOR_GEOLOCATION_OPTIONS : options,
    });

    if (capacitorResult.ok) {
      return getDeviceCoordinateQualityDecision(capacitorResult, qualityOptions);
    }
    if (capacitorResult.reason !== "capacitor_geolocation_unavailable") {
      return capacitorResult;
    }
  }

  if (preferNative) {
    const nativeResult = await requestNativeDeviceCoordinates({
      bridge: nativeBridge,
      eventTarget: nativeEventTarget,
      maxAccuracyM: qualityOptions.maxAccuracyM,
      maxAgeMs: qualityOptions.maxAgeMs,
      requireCurrent,
    });

    if (nativeResult.ok) {
      return getDeviceCoordinateQualityDecision(nativeResult, qualityOptions);
    }
    if (shouldStopAfterNativeFailure(nativeResult)) return nativeResult;
  }

  const browserResult = await requestBrowserCoordinates({
    geolocation,
    now,
    options: options || DEVICE_GEOLOCATION_OPTIONS,
  });
  return getDeviceCoordinateQualityDecision(browserResult, qualityOptions);
}
