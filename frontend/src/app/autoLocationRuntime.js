import { requestDeviceCoordinates } from "../services/deviceLocation";
import { AUTO_LOCATION_FOREGROUND_RECHECK_MS } from "../domain/geo/autoLocationPolicy";

export const AUTO_LOCATION_RECHECK_MS = AUTO_LOCATION_FOREGROUND_RECHECK_MS;
export const AUTO_LOCATION_TICK_MS = 60 * 1000;
export const AUTO_LOCATION_MAX_ACCURACY_M = 250;
export const AUTO_LOCATION_MAX_AGE_MS = 2 * 60 * 1000;

export function createLatestLocationRequestGuard() {
  let sequence = 0;

  return {
    begin() {
      sequence += 1;
      return sequence;
    },
    invalidate() {
      sequence += 1;
    },
    isCurrent(token) {
      return token === sequence;
    },
  };
}

export function getDisabledAutomaticLocationStatus(status, { preserveLastResult = true } = {}) {
  if (!preserveLastResult) return { status: "idle" };
  if (status?.status === "success") {
    const lastKnown = {
      status: "last_known",
      city: status.city,
    };

    if (status.displayName) lastKnown.displayName = status.displayName;
    if (status.locality) lastKnown.locality = status.locality;

    return lastKnown;
  }
  if (status?.status === "loading") return { status: "idle" };

  return status || { status: "idle" };
}

export function shouldRestoreAutomaticLocation({ enabled, location } = {}) {
  if (!enabled || !location?.city) return false;

  const source = String(location.source || "").trim().toLowerCase();

  return Boolean(source && source !== "manual");
}

export function getAutomaticLocationBootstrapState({ enabled, location } = {}) {
  const shouldRestore = shouldRestoreAutomaticLocation({ enabled, location });

  return {
    autoLocationEnabled: shouldRestore,
    requiresStorageRepair: Boolean(enabled && !shouldRestore),
  };
}

function toFiniteNumber(value) {
  if (value == null || value === "") return null;

  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function getAutomaticLocationQualityDecision(
  result,
  {
    maxAccuracyM = AUTO_LOCATION_MAX_ACCURACY_M,
    maxAgeMs = AUTO_LOCATION_MAX_AGE_MS,
  } = {},
) {
  if (!result?.ok) {
    return { ok: false, reason: result?.reason || "unavailable" };
  }

  const lat = toFiniteNumber(result.coords?.lat);
  const lon = toFiniteNumber(result.coords?.lon);
  const accuracyM = toFiniteNumber(result.coords?.accuracyM);
  const ageMs = toFiniteNumber(result.ageMs);

  if (lat == null || lon == null || accuracyM == null || accuracyM < 0 || ageMs == null || ageMs < 0) {
    return { ok: false, reason: "missing_quality" };
  }
  if (accuracyM > maxAccuracyM || ageMs > maxAgeMs) {
    return { ok: false, reason: "stale_or_imprecise" };
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
    ok: true,
  };
}

export function shouldRunAutomaticLocationCheck({
  enabled = true,
  inFlight = false,
  lastCheckedAt = 0,
  minIntervalMs = AUTO_LOCATION_RECHECK_MS,
  now = Date.now(),
  visibilityState = "visible",
} = {}) {
  if (!enabled || inFlight || visibilityState === "hidden" || !Number.isFinite(now)) {
    return false;
  }
  if (!Number.isFinite(lastCheckedAt) || lastCheckedAt <= 0) return true;

  return now - lastCheckedAt >= minIntervalMs;
}

export function startAutomaticLocationRuntime({
  documentTarget = globalThis.document,
  enabled = true,
  intervalMs = AUTO_LOCATION_TICK_MS,
  initialLastCheckedAt = 0,
  now = Date.now,
  onResult,
  requestCoordinates = requestDeviceCoordinates,
  windowTarget = globalThis.window,
} = {}) {
  let disposed = false;
  let inFlight = false;
  let lastCheckedAt = Number.isFinite(initialLastCheckedAt) ? initialLastCheckedAt : 0;

  const check = async ({ force = false } = {}) => {
    if (disposed || !enabled || inFlight || documentTarget?.visibilityState === "hidden") {
      return { status: "skipped" };
    }

    const checkedAt = Number(now());
    if (!force && !shouldRunAutomaticLocationCheck({
      enabled,
      inFlight,
      lastCheckedAt,
      now: checkedAt,
      visibilityState: documentTarget?.visibilityState,
    })) {
      return { status: "skipped" };
    }

    inFlight = true;
    lastCheckedAt = checkedAt;

    let result;

    try {
      const rawResult = await requestCoordinates({
        maxAccuracyM: AUTO_LOCATION_MAX_ACCURACY_M,
        maxAgeMs: AUTO_LOCATION_MAX_AGE_MS,
      });
      result = getAutomaticLocationQualityDecision(rawResult);
    } catch (error) {
      result = { ok: false, reason: error?.message || "unavailable" };
    }

    try {
      if (!disposed) {
        await onResult?.(result);
      }
    } catch {
      // Runtime callbacks must never break the next scheduled location check.
    } finally {
      inFlight = false;
    }

    return { result, status: disposed ? "cancelled" : "settled" };
  };

  const handleForeground = () => {
    if (documentTarget?.visibilityState !== "hidden") {
      check();
    }
  };
  const handleVisibilityChange = () => {
    if (documentTarget?.visibilityState === "visible") {
      check();
    }
  };
  const handleOnline = () => {
    if (documentTarget?.visibilityState !== "hidden") {
      check({ force: true });
    }
  };
  const intervalId = windowTarget?.setInterval?.(() => check(), intervalMs);

  documentTarget?.addEventListener?.("visibilitychange", handleVisibilityChange);
  windowTarget?.addEventListener?.("focus", handleForeground);
  windowTarget?.addEventListener?.("online", handleOnline);
  check();

  return {
    check,
    stop() {
      if (disposed) return;

      disposed = true;
      if (intervalId != null) windowTarget?.clearInterval?.(intervalId);
      documentTarget?.removeEventListener?.("visibilitychange", handleVisibilityChange);
      windowTarget?.removeEventListener?.("focus", handleForeground);
      windowTarget?.removeEventListener?.("online", handleOnline);
    },
  };
}
