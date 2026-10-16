import { Capacitor } from "@capacitor/core";
import { Geolocation } from "@capacitor/geolocation";

import { isAndroidCapacitorRuntime } from "./apiConfig";

export const CAPACITOR_GEOLOCATION_OPTIONS = Object.freeze({
  enableHighAccuracy: true,
  maximumAge: 0,
  timeout: 18500,
});
export const CAPACITOR_GEOLOCATION_STAGES = Object.freeze([
  Object.freeze({
    maxAcceptedAgeMs: 30 * 1000,
    name: "fast",
    options: Object.freeze({
      enableHighAccuracy: false,
      maximumAge: 30 * 1000,
      timeout: 1500,
    }),
    source: "capacitor_geolocation",
  }),
  Object.freeze({
    maxAcceptedAgeMs: 2 * 60 * 1000,
    name: "balanced",
    options: Object.freeze({
      enableHighAccuracy: false,
      maximumAge: 0,
      timeout: 5000,
    }),
    source: "capacitor_geolocation",
  }),
  Object.freeze({
    maxAcceptedAgeMs: 2 * 60 * 1000,
    name: "precise",
    options: CAPACITOR_GEOLOCATION_OPTIONS,
    source: "capacitor_geolocation",
  }),
]);

export const CAPACITOR_LOCATION_PRECISION = Object.freeze({
  approximate: "approximate",
  precise: "precise",
  unknown: "unknown",
});
export const CAPACITOR_LOCATION_MAX_FUTURE_SKEW_MS = 5000;

function toFiniteNumber(value) {
  if (value == null || value === "") return null;

  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function normalizePermissionToken(value) {
  return String(value || "").trim().toLowerCase();
}

export function getCapacitorLocationPermissionDetails(status = {}) {
  const fine = normalizePermissionToken(status.location);
  const coarse = normalizePermissionToken(status.coarseLocation);

  if (fine === "granted") {
    return {
      decision: "granted",
      precision: CAPACITOR_LOCATION_PRECISION.precise,
    };
  }
  if (coarse === "granted") {
    return {
      decision: "granted",
      precision: CAPACITOR_LOCATION_PRECISION.approximate,
    };
  }

  const tokens = [fine, coarse].filter(Boolean);
  if (tokens.includes("prompt") || tokens.includes("prompt-with-rationale")) {
    return {
      decision: "prompt",
      precision: CAPACITOR_LOCATION_PRECISION.unknown,
    };
  }
  if (tokens.includes("denied")) {
    return {
      decision: "denied",
      precision: CAPACITOR_LOCATION_PRECISION.unknown,
    };
  }

  return {
    decision: "unknown",
    precision: CAPACITOR_LOCATION_PRECISION.unknown,
  };
}

export function getCapacitorLocationPermissionDecision(status = {}) {
  return getCapacitorLocationPermissionDetails(status).decision;
}

export function normalizeCapacitorPosition(
  position,
  {
    now = Date.now,
    precision = CAPACITOR_LOCATION_PRECISION.unknown,
  } = {},
) {
  const lat = toFiniteNumber(position?.coords?.latitude);
  const lon = toFiniteNumber(position?.coords?.longitude);

  if (lat == null || lon == null) {
    return {
      ok: false,
      reason: "missing_coordinates",
      source: "capacitor_geolocation",
    };
  }

  const accuracyM = toFiniteNumber(position?.coords?.accuracy);
  const timestamp = toFiniteNumber(position?.timestamp);
  const currentTime = toFiniteNumber(now?.());
  if (
    accuracyM == null ||
    accuracyM < 0 ||
    timestamp == null ||
    currentTime == null ||
    timestamp - currentTime > CAPACITOR_LOCATION_MAX_FUTURE_SKEW_MS
  ) {
    return {
      ok: false,
      reason: "missing_quality",
      source: "capacitor_geolocation",
    };
  }
  const ageMs = Math.max(0, currentTime - timestamp);

  return {
    ok: true,
    source: "capacitor_geolocation",
    ageMs,
    precision,
    coords: {
      accuracyM,
      lat,
      lon,
    },
  };
}

function getCapacitorLocationFailureReason(error) {
  const token = `${error?.code || ""} ${error?.message || ""}`.toLowerCase();

  if (token.includes("permission") || token.includes("denied")) return "permission_denied";
  if (token.includes("timeout")) return "timeout";
  if (token.includes("location services") || token.includes("disabled")) {
    return "location_services_disabled";
  }

  return "unavailable";
}

function preferCapacitorLocationFailure(current, candidate) {
  const priority = {
    permission_denied: 5,
    location_services_disabled: 4,
    stale_or_imprecise: 3,
    missing_quality: 2,
    missing_coordinates: 1,
    timeout: 0,
    unavailable: 0,
  };
  const currentPriority = priority[current?.reason] ?? 0;
  const candidatePriority = priority[candidate?.reason] ?? 0;
  return candidatePriority >= currentPriority ? candidate : current;
}

export function isCapacitorGeolocationAvailable({
  capacitor = Capacitor,
  geolocation = Geolocation,
} = {}) {
  return Boolean(
    isAndroidCapacitorRuntime(capacitor) &&
    typeof geolocation?.checkPermissions === "function" &&
    typeof geolocation?.requestPermissions === "function" &&
    typeof geolocation?.getCurrentPosition === "function"
  );
}

export async function requestCapacitorDeviceCoordinates({
  capacitor = Capacitor,
  geolocation = Geolocation,
  maxAccuracyM = 250,
  maxAgeMs = 2 * 60 * 1000,
  now = Date.now,
  options,
  stages = CAPACITOR_GEOLOCATION_STAGES,
} = {}) {
  if (!isCapacitorGeolocationAvailable({ capacitor, geolocation })) {
    return {
      ok: false,
      reason: "capacitor_geolocation_unavailable",
      source: "capacitor_geolocation",
    };
  }

  try {
    let permission = getCapacitorLocationPermissionDetails(
      await geolocation.checkPermissions(),
    );

    if (permission.decision !== "granted") {
      if (permission.decision === "denied") {
        return {
          ok: false,
          reason: "permission_denied",
          source: "capacitor_geolocation",
        };
      }

      permission = getCapacitorLocationPermissionDetails(
        await geolocation.requestPermissions({ permissions: ["location"] }),
      );
    }

    if (permission.decision !== "granted") {
      return {
        ok: false,
        reason: "permission_denied",
        source: "capacitor_geolocation",
      };
    }

    const requestedStages = options
      ? [{ name: "custom", options, source: "capacitor_geolocation" }]
      : stages;
    let lastFailure = {
      ok: false,
      reason: "unavailable",
      source: "capacitor_geolocation",
    };

    for (const stage of requestedStages) {
      try {
        const position = await geolocation.getCurrentPosition(stage.options);
        const result = normalizeCapacitorPosition(position, {
          now,
          precision: permission.precision,
        });
        if (!result.ok) {
          lastFailure = preferCapacitorLocationFailure(lastFailure, result);
          continue;
        }

        const stageMaxAgeMs = Math.min(
          maxAgeMs,
          Number.isFinite(stage.maxAcceptedAgeMs) ? stage.maxAcceptedAgeMs : maxAgeMs,
        );
        const qualityAccepted = result.ageMs <= stageMaxAgeMs
          && result.coords.accuracyM <= maxAccuracyM;
        if (!qualityAccepted) {
          lastFailure = preferCapacitorLocationFailure(lastFailure, {
            ok: false,
            reason: "stale_or_imprecise",
            source: stage.source,
          });
          continue;
        }

        return {
          ...result,
          acquisitionStage: stage.name,
          source: stage.source,
        };
      } catch (error) {
        const reason = getCapacitorLocationFailureReason(error);
        lastFailure = preferCapacitorLocationFailure(lastFailure, {
          ok: false,
          error: error?.message || "capacitor_geolocation_failed",
          reason,
          source: stage.source,
        });
        if (["permission_denied", "location_services_disabled"].includes(reason)) {
          return lastFailure;
        }
      }
    }

    return lastFailure;
  } catch (error) {
    return {
      ok: false,
      error: error?.message || "capacitor_geolocation_failed",
      reason: getCapacitorLocationFailureReason(error),
      source: "capacitor_geolocation",
    };
  }
}
