export const ANDROID_PERMISSION_STORAGE_KEYS = Object.freeze({
  autoLocationEnabled: "autoLocationEnabled",
  startupNotificationsAsked: "startupNotificationsAsked:v1",
  weatherAlertsEnabled: "weatherAlertsEnabled",
});

export const ANDROID_STARTUP_GATE_STATE = Object.freeze({
  skipped: "skipped",
  gpsPromptPending: "gps_prompt_pending",
  gpsGrantedResolving: "gps_granted_resolving",
  gpsDenied: "gps_denied",
  gpsUnavailable: "gps_unavailable",
  gpsTemporaryFailure: "gps_temporary_failure",
  manualLocationRequired: "manual_location_required",
  notificationsPromptPending: "notifications_prompt_pending",
  ready: "ready",
});

export const ANDROID_STARTUP_GATE_ACTION = Object.freeze({
  none: "none",
  requestNativeGps: "request_native_gps",
  resolveGpsLocation: "resolve_gps_location",
  requestManualLocation: "request_manual_location",
  requestNativeNotifications: "request_native_notifications",
});

const GPS_DENIED_REASONS = new Set(["denied", "permission_denied"]);
const GPS_UNAVAILABLE_REASONS = new Set([
  "unsupported",
  "native_unavailable",
  "services_disabled",
  "location_services_disabled",
]);

function normalizeToken(value) {
  return String(value || "").trim().toLowerCase();
}

export function readAndroidStartupAutoLocationEnabled(storedValue) {
  return normalizeToken(storedValue) !== "false";
}

export function readStoredBoolean(value) {
  return value === true || normalizeToken(value) === "true";
}

export function hasStartupLocation(location) {
  return Boolean(String(location?.city || "").trim());
}

export function getGpsFailureState(reason) {
  const normalizedReason = normalizeToken(reason);

  if (GPS_DENIED_REASONS.has(normalizedReason)) {
    return ANDROID_STARTUP_GATE_STATE.gpsDenied;
  }

  if (GPS_UNAVAILABLE_REASONS.has(normalizedReason)) {
    return ANDROID_STARTUP_GATE_STATE.gpsUnavailable;
  }

  return ANDROID_STARTUP_GATE_STATE.gpsTemporaryFailure;
}

export function shouldPromptStartupNotifications({
  hasResolvedOrSelectedLocation,
  isNativeAndroid,
  startupNotificationsAsked,
  weatherAlertsEnabled,
} = {}) {
  return Boolean(
    isNativeAndroid &&
    hasResolvedOrSelectedLocation &&
    !readStoredBoolean(startupNotificationsAsked) &&
    !readStoredBoolean(weatherAlertsEnabled)
  );
}

function notificationOrReadyDecision({
  hasResolvedOrSelectedLocation,
  isNativeAndroid,
  startupNotificationsAsked,
  weatherAlertsEnabled,
}) {
  if (shouldPromptStartupNotifications({
    hasResolvedOrSelectedLocation,
    isNativeAndroid,
    startupNotificationsAsked,
    weatherAlertsEnabled,
  })) {
    return {
      action: ANDROID_STARTUP_GATE_ACTION.requestNativeNotifications,
      state: ANDROID_STARTUP_GATE_STATE.notificationsPromptPending,
    };
  }

  return {
    action: ANDROID_STARTUP_GATE_ACTION.none,
    state: ANDROID_STARTUP_GATE_STATE.ready,
  };
}

export function getAndroidStartupGateDecision({
  autoLocationEnabled = true,
  gpsFailureReason = "",
  gpsStep = "not_requested",
  isNativeAndroid = false,
  resolvedLocation = null,
  selectedLocation = null,
  startupNotificationsAsked = false,
  weatherAlertsEnabled = false,
} = {}) {
  if (!isNativeAndroid) {
    return {
      action: ANDROID_STARTUP_GATE_ACTION.none,
      state: ANDROID_STARTUP_GATE_STATE.skipped,
    };
  }

  const hasResolvedLocation = hasStartupLocation(resolvedLocation);
  const hasSelectedLocation = hasStartupLocation(selectedLocation);
  const hasResolvedOrSelectedLocation = hasResolvedLocation || hasSelectedLocation;

  if (hasResolvedLocation) {
    return notificationOrReadyDecision({
      hasResolvedOrSelectedLocation,
      isNativeAndroid,
      startupNotificationsAsked,
      weatherAlertsEnabled,
    });
  }

  const normalizedStep = normalizeToken(gpsStep) || "not_requested";

  if (autoLocationEnabled && (normalizedStep === "denied" || normalizedStep === "failed")) {
    const failureState = getGpsFailureState(gpsFailureReason || normalizedStep);

    if (
      failureState !== ANDROID_STARTUP_GATE_STATE.gpsTemporaryFailure &&
      hasSelectedLocation
    ) {
      return notificationOrReadyDecision({
        hasResolvedOrSelectedLocation,
        isNativeAndroid,
        startupNotificationsAsked,
        weatherAlertsEnabled,
      });
    }

    return {
      action: failureState === ANDROID_STARTUP_GATE_STATE.gpsTemporaryFailure
        ? ANDROID_STARTUP_GATE_ACTION.resolveGpsLocation
        : ANDROID_STARTUP_GATE_ACTION.requestManualLocation,
      state: failureState,
    };
  }

  if (autoLocationEnabled && (normalizedStep === "granted" || normalizedStep === "resolving")) {
    return {
      action: ANDROID_STARTUP_GATE_ACTION.resolveGpsLocation,
      state: ANDROID_STARTUP_GATE_STATE.gpsGrantedResolving,
    };
  }

  if (autoLocationEnabled && normalizedStep === "prompting") {
    return {
      action: ANDROID_STARTUP_GATE_ACTION.none,
      state: ANDROID_STARTUP_GATE_STATE.gpsPromptPending,
    };
  }

  if (!autoLocationEnabled) {
    if (hasSelectedLocation) {
      return notificationOrReadyDecision({
        hasResolvedOrSelectedLocation,
        isNativeAndroid,
        startupNotificationsAsked,
        weatherAlertsEnabled,
      });
    }

    return {
      action: ANDROID_STARTUP_GATE_ACTION.requestManualLocation,
      state: ANDROID_STARTUP_GATE_STATE.manualLocationRequired,
    };
  }

  return {
    action: ANDROID_STARTUP_GATE_ACTION.requestNativeGps,
    state: ANDROID_STARTUP_GATE_STATE.gpsPromptPending,
  };
}
