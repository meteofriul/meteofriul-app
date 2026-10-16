import {
  ANDROID_STARTUP_GATE_ACTION,
  ANDROID_STARTUP_GATE_STATE,
  getAndroidStartupGateDecision,
  getGpsFailureState,
} from "./androidPermissionGate";

export const ANDROID_STARTUP_PROMPT_STEP = Object.freeze({
  skipped: "skipped",
  disclosureRequested: "disclosure_requested",
  disclosureAccepted: "disclosure_accepted",
  disclosureDeclined: "disclosure_declined",
  gpsRequested: "gps_requested",
  gpsResolved: "gps_resolved",
  gpsFailed: "gps_failed",
  manualLocationRequired: "manual_location_required",
  notificationsRequested: "notifications_requested",
  notificationsSkipped: "notifications_skipped",
  ready: "ready",
});

function normalizeToken(value, fallback = "") {
  const token = String(value || "").trim().toLowerCase();
  return token || fallback;
}

function hasLocation(location) {
  return Boolean(String(location?.city || "").trim());
}

function normalizeGpsResult(result) {
  const record = result && typeof result === "object" ? result : {};
  const location = record.location || record.resolvedLocation || null;

  if (record.ok && hasLocation(location)) {
    return {
      ok: true,
      location,
      source: normalizeToken(record.source || location.source, "gps"),
    };
  }

  return {
    ok: false,
    reason: normalizeToken(record.reason || record.error, "gps_failed"),
  };
}

function normalizeNotificationResult(result) {
  const record = result && typeof result === "object" ? result : {};
  const receive = normalizeToken(record.receive || record.permission, "unknown");

  return {
    ...record,
    receive,
    requested: record.requested !== false,
  };
}

function hasAcceptedDisclosure(result) {
  return result === true || result?.accepted === true;
}

function getNotificationStoragePatch(notificationResult) {
  const receive = normalizeToken(notificationResult?.receive);

  return {
    startupNotificationsAsked:
      notificationResult?.requested !== false || receive === "granted" || receive === "denied",
    weatherAlertsEnabled: receive === "granted",
  };
}

async function requestNotifications({ decision, requestNativeNotifications, resolvedLocation, steps }) {
  steps.push({
    action: ANDROID_STARTUP_GATE_ACTION.requestNativeNotifications,
    state: ANDROID_STARTUP_GATE_STATE.notificationsPromptPending,
    step: ANDROID_STARTUP_PROMPT_STEP.notificationsRequested,
  });

  if (typeof requestNativeNotifications !== "function") {
    return {
      errorResult: {
        completed: false,
        decision,
        reason: "startup_notifications_handler_missing",
        resolvedLocation,
        steps,
      },
    };
  }

  const notificationResult = normalizeNotificationResult(await requestNativeNotifications());
  return {
    notificationResult,
    storagePatch: getNotificationStoragePatch(notificationResult),
  };
}

function createReadyResult({ decision, notificationResult = null, resolvedLocation = null, steps }) {
  return {
    completed: true,
    decision: {
      action: ANDROID_STARTUP_GATE_ACTION.none,
      state: ANDROID_STARTUP_GATE_STATE.ready,
    },
    notificationResult,
    previousDecision: decision,
    resolvedLocation,
    steps: [
      ...steps,
      {
        action: ANDROID_STARTUP_GATE_ACTION.none,
        state: ANDROID_STARTUP_GATE_STATE.ready,
        step: ANDROID_STARTUP_PROMPT_STEP.ready,
      },
    ],
  };
}

export async function runAndroidStartupPromptFlow({
  autoLocationEnabled = true,
  backgroundLocationDisclosureAccepted = false,
  isNativeAndroid = false,
  requestBackgroundLocationDisclosure,
  requestNativeNotifications,
  resolveDeviceLocation,
  selectedLocation = null,
  startupNotificationsAsked = false,
  weatherAlertsEnabled = false,
} = {}) {
  const steps = [];
  let resolvedLocation = null;
  let decision = getAndroidStartupGateDecision({
    autoLocationEnabled,
    isNativeAndroid,
    selectedLocation,
    startupNotificationsAsked,
    weatherAlertsEnabled,
  });

  if (decision.state === ANDROID_STARTUP_GATE_STATE.skipped) {
    return {
      completed: true,
      decision,
      steps: [{
        action: decision.action,
        state: decision.state,
        step: ANDROID_STARTUP_PROMPT_STEP.skipped,
      }],
    };
  }

  if (decision.action === ANDROID_STARTUP_GATE_ACTION.requestNativeGps) {
    if (!backgroundLocationDisclosureAccepted) {
      steps.push({
        action: ANDROID_STARTUP_GATE_ACTION.requestNativeGps,
        state: ANDROID_STARTUP_GATE_STATE.gpsPromptPending,
        step: ANDROID_STARTUP_PROMPT_STEP.disclosureRequested,
      });

      let disclosureAccepted;
      try {
        disclosureAccepted = hasAcceptedDisclosure(
          await requestBackgroundLocationDisclosure?.(),
        );
      } catch {
        disclosureAccepted = false;
      }

      if (!disclosureAccepted) {
        const manualDecision = {
          action: ANDROID_STARTUP_GATE_ACTION.requestManualLocation,
          state: ANDROID_STARTUP_GATE_STATE.manualLocationRequired,
        };
        steps.push({
          action: ANDROID_STARTUP_GATE_ACTION.none,
          state: ANDROID_STARTUP_GATE_STATE.gpsPromptPending,
          step: ANDROID_STARTUP_PROMPT_STEP.disclosureDeclined,
        });
        const notificationOutcome = await requestNotifications({
          decision: manualDecision,
          requestNativeNotifications,
          resolvedLocation: null,
          steps,
        });
        if (notificationOutcome.errorResult) {
          return {
            ...notificationOutcome.errorResult,
            disclosureAccepted: false,
            needsManualLocation: !hasLocation(selectedLocation),
            reason: "background_location_disclosure_declined",
          };
        }

        return {
          completed: false,
          decision: manualDecision,
          disclosureAccepted: false,
          needsManualLocation: !hasLocation(selectedLocation),
          notificationResult: notificationOutcome.notificationResult,
          reason: "background_location_disclosure_declined",
          resolvedLocation: null,
          storagePatch: notificationOutcome.storagePatch,
          steps: [
            ...steps,
            {
              action: manualDecision.action,
              state: manualDecision.state,
              step: ANDROID_STARTUP_PROMPT_STEP.manualLocationRequired,
            },
          ],
        };
      }

      steps.push({
        action: ANDROID_STARTUP_GATE_ACTION.requestNativeGps,
        state: ANDROID_STARTUP_GATE_STATE.gpsPromptPending,
        step: ANDROID_STARTUP_PROMPT_STEP.disclosureAccepted,
      });
    }

    steps.push({
      action: decision.action,
      state: decision.state,
      step: ANDROID_STARTUP_PROMPT_STEP.gpsRequested,
    });

    let rawGpsResult;
    try {
      rawGpsResult = typeof resolveDeviceLocation === "function"
        ? await resolveDeviceLocation()
        : { ok: false, reason: "native_unavailable" };
    } catch (error) {
      rawGpsResult = { ok: false, reason: error?.message || "gps_failed" };
    }
    const gpsResult = normalizeGpsResult(rawGpsResult);

    if (gpsResult.ok) {
      resolvedLocation = gpsResult.location;
      steps.push({
        action: ANDROID_STARTUP_GATE_ACTION.resolveGpsLocation,
        state: ANDROID_STARTUP_GATE_STATE.gpsGrantedResolving,
        step: ANDROID_STARTUP_PROMPT_STEP.gpsResolved,
      });
      decision = getAndroidStartupGateDecision({
        autoLocationEnabled,
        gpsStep: "granted",
        isNativeAndroid,
        resolvedLocation,
        selectedLocation,
        startupNotificationsAsked,
        weatherAlertsEnabled,
      });
    } else {
      const gpsFailureState = getGpsFailureState(gpsResult.reason);
      decision = getAndroidStartupGateDecision({
        autoLocationEnabled,
        gpsFailureReason: gpsResult.reason,
        gpsStep: "failed",
        isNativeAndroid,
        selectedLocation,
        startupNotificationsAsked,
        weatherAlertsEnabled,
      });
      steps.push({
        action: ANDROID_STARTUP_GATE_ACTION.none,
        reason: gpsResult.reason,
        state: gpsFailureState,
        step: ANDROID_STARTUP_PROMPT_STEP.gpsFailed,
      });
    }
  }

  let earlyNotificationOutcome = null;
  if (
    decision.action !== ANDROID_STARTUP_GATE_ACTION.requestNativeNotifications &&
    isNativeAndroid
  ) {
    earlyNotificationOutcome = await requestNotifications({
      decision,
      requestNativeNotifications,
      resolvedLocation,
      steps,
    });
    if (earlyNotificationOutcome.errorResult) return earlyNotificationOutcome.errorResult;
  }

  if (decision.action === ANDROID_STARTUP_GATE_ACTION.requestManualLocation) {
    return {
      completed: false,
      decision,
      needsManualLocation: true,
      notificationResult: earlyNotificationOutcome?.notificationResult || null,
      resolvedLocation,
      storagePatch: earlyNotificationOutcome?.storagePatch,
      steps: [
        ...steps,
        {
          action: decision.action,
          state: decision.state,
          step: ANDROID_STARTUP_PROMPT_STEP.manualLocationRequired,
        },
      ],
    };
  }

  if (
    decision.state === ANDROID_STARTUP_GATE_STATE.gpsTemporaryFailure ||
    decision.state === ANDROID_STARTUP_GATE_STATE.gpsUnavailable
  ) {
    return {
      completed: false,
      decision,
      notificationResult: earlyNotificationOutcome?.notificationResult || null,
      resolvedLocation,
      retryableGps: decision.state === ANDROID_STARTUP_GATE_STATE.gpsTemporaryFailure,
      storagePatch: earlyNotificationOutcome?.storagePatch,
      steps,
    };
  }

  if (decision.action === ANDROID_STARTUP_GATE_ACTION.requestNativeNotifications) {
    const notificationOutcome = await requestNotifications({
      decision,
      requestNativeNotifications,
      resolvedLocation,
      steps,
    });
    if (notificationOutcome.errorResult) return notificationOutcome.errorResult;

    return {
      ...createReadyResult({
        decision,
        notificationResult: notificationOutcome.notificationResult,
        resolvedLocation,
        steps,
      }),
      storagePatch: notificationOutcome.storagePatch,
    };
  }

  if (decision.action === ANDROID_STARTUP_GATE_ACTION.none) {
    return {
      ...createReadyResult({
        decision,
        notificationResult: earlyNotificationOutcome?.notificationResult || null,
        resolvedLocation,
        steps,
      }),
      storagePatch: earlyNotificationOutcome?.storagePatch,
    };
  }

  return {
    completed: false,
    decision,
    resolvedLocation,
    steps,
  };
}
