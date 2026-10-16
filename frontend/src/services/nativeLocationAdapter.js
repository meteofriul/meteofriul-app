export const NATIVE_LOCATION_BRIDGE_NAME = "MeteoAndroid";
export const NATIVE_LOCATION_RESULT_EVENT = "meteo-native-location";
export const NATIVE_LOCATION_LEGACY_RESULT_EVENT = "meteo-fast-location";
export const NATIVE_LOCATION_RESULT_EVENTS = Object.freeze([
  NATIVE_LOCATION_RESULT_EVENT,
  NATIVE_LOCATION_LEGACY_RESULT_EVENT,
]);
export const NATIVE_LOCATION_DEFAULT_TIMEOUT_MS = 3000;
export const NATIVE_LOCATION_BALANCED_TIMEOUT_MS = 2800;

export const NATIVE_LOCATION_METHODS = Object.freeze({
  getStatus: "getLocationStatus",
  requestPermission: "requestLocationPermission",
  requestFastLocation: "requestFastLocation",
  requestBalancedLocation: "requestBalancedLocation",
});

function getDefaultBridge(windowLike = globalThis.window) {
  return windowLike?.[NATIVE_LOCATION_BRIDGE_NAME] || null;
}

function normalizeToken(value, fallback = "") {
  const token = String(value || "").trim().toLowerCase();
  return token || fallback;
}

function parseNativePayload(payload) {
  if (payload && typeof payload === "object") return payload;

  if (typeof payload !== "string") return {};

  try {
    const parsed = JSON.parse(payload);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function normalizeBoolean(value) {
  return value === true || normalizeToken(value) === "true";
}

function normalizeNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function normalizeNativeLocationStatus(payload) {
  const record = parseNativePayload(payload);
  const permission = normalizeToken(record.permission, "unknown");
  const servicesEnabled = normalizeBoolean(record.servicesEnabled ?? record.services_enabled);

  return {
    permission,
    servicesEnabled,
  };
}

export function getNativeLocationStatus({ bridge = getDefaultBridge() } = {}) {
  if (!bridge || typeof bridge[NATIVE_LOCATION_METHODS.getStatus] !== "function") {
    return {
      available: false,
      permission: "unsupported",
      servicesEnabled: false,
    };
  }

  try {
    return {
      available: true,
      ...normalizeNativeLocationStatus(bridge[NATIVE_LOCATION_METHODS.getStatus]()),
    };
  } catch (error) {
    return {
      available: false,
      error: error?.message || "native_location_status_failed",
      permission: "unknown",
      servicesEnabled: false,
    };
  }
}

export function normalizeNativeLocationPayload(payload = {}) {
  const record = parseNativePayload(payload);
  const lat = normalizeNumber(record.lat);
  const lon = normalizeNumber(record.lon);
  const accuracyM = normalizeNumber(record.accuracy_m ?? record.accuracyM);
  const ageMs = normalizeNumber(record.age_ms ?? record.ageMs);

  return {
    ...record,
    ok: record.ok === true,
    source: normalizeToken(record.source, "native_location"),
    reason: normalizeToken(record.reason),
    permission: normalizeToken(record.permission, "unknown"),
    services_enabled: normalizeBoolean(record.services_enabled ?? record.servicesEnabled),
    lat,
    lon,
    accuracy_m: accuracyM,
    age_ms: ageMs,
    requestId: String(record.requestId || ""),
  };
}

function createNativeLocationRequestId(methodName) {
  return [
    "native-location",
    methodName,
    Date.now(),
    Math.random().toString(16).slice(2),
  ].join(":");
}

function normalizeNativeLocationEventNames({ eventName, eventNames } = {}) {
  const names = Array.isArray(eventNames) && eventNames.length > 0
    ? eventNames
    : eventName
      ? [eventName]
      : NATIVE_LOCATION_RESULT_EVENTS;

  return Array.from(new Set(
    names
      .map((name) => String(name || "").trim())
      .filter(Boolean),
  ));
}

export function isNativeLocationBridgeAvailable({
  bridge = getDefaultBridge(),
  methodName,
} = {}) {
  if (!bridge) return false;
  if (!methodName) return true;

  return typeof bridge[methodName] === "function";
}

export function requestNativeLocationAction(
  methodName,
  {
    bridge = getDefaultBridge(),
    eventName,
    eventNames,
    eventTarget = globalThis.window,
    requestId = createNativeLocationRequestId(methodName),
    timeoutMs = NATIVE_LOCATION_DEFAULT_TIMEOUT_MS,
    setTimeoutImpl = globalThis.setTimeout,
    clearTimeoutImpl = globalThis.clearTimeout,
    args = [],
  } = {},
) {
  if (!isNativeLocationBridgeAvailable({ bridge, methodName })) {
    return Promise.resolve({
      ok: false,
      reason: "native_location_bridge_unavailable",
      source: methodName,
      requestId,
    });
  }

  if (
    !eventTarget ||
    typeof eventTarget.addEventListener !== "function" ||
    typeof eventTarget.removeEventListener !== "function"
  ) {
    return Promise.resolve({
      ok: false,
      reason: "native_location_event_target_unavailable",
      source: methodName,
      requestId,
    });
  }

  const resolvedEventNames = normalizeNativeLocationEventNames({ eventName, eventNames });
  if (!resolvedEventNames.length) {
    return Promise.resolve({
      ok: false,
      reason: "native_location_event_name_unavailable",
      source: methodName,
      requestId,
    });
  }

  return new Promise((resolve) => {
    let settled = false;

    function cleanup(result) {
      if (settled) return;
      settled = true;
      resolvedEventNames.forEach((name) => {
        eventTarget.removeEventListener(name, handleResult);
      });
      clearTimeoutImpl?.(timer);
      resolve(result);
    }

    function handleResult(event) {
      const detail = event?.detail || {};
      if (String(detail.requestId || "") !== requestId) return;

      cleanup(normalizeNativeLocationPayload(detail));
    }

    const timer = setTimeoutImpl?.(() => {
      cleanup({
        ok: false,
        reason: "native_location_timeout",
        source: methodName,
        requestId,
      });
    }, Math.max(Number(timeoutMs) || NATIVE_LOCATION_DEFAULT_TIMEOUT_MS, 1));

    resolvedEventNames.forEach((name) => {
      eventTarget.addEventListener(name, handleResult);
    });

    try {
      bridge[methodName](requestId, ...args);
    } catch (error) {
      cleanup({
        ok: false,
        error: error?.message || "native_location_bridge_failed",
        reason: "native_location_bridge_failed",
        source: methodName,
        requestId,
      });
    }
  });
}

export function requestNativeLocationPermission(options = {}) {
  return requestNativeLocationAction(NATIVE_LOCATION_METHODS.requestPermission, options);
}

export function requestNativeFastLocation(options = {}) {
  return requestNativeLocationAction(NATIVE_LOCATION_METHODS.requestFastLocation, options);
}

export function requestNativeBalancedLocation({
  timeoutMs = NATIVE_LOCATION_BALANCED_TIMEOUT_MS,
  ...options
} = {}) {
  return requestNativeLocationAction(NATIVE_LOCATION_METHODS.requestBalancedLocation, {
    ...options,
    timeoutMs,
    args: [timeoutMs],
  });
}
