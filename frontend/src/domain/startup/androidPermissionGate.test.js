import { describe, expect, it } from "vitest";

import {
  ANDROID_STARTUP_GATE_ACTION,
  ANDROID_STARTUP_GATE_STATE,
  getAndroidStartupGateDecision,
  getGpsFailureState,
  hasStartupLocation,
  readAndroidStartupAutoLocationEnabled,
  shouldPromptStartupNotifications,
} from "./androidPermissionGate";

describe("androidPermissionGate", () => {
  it("keeps automatic device location enabled by default on a clean Android launch", () => {
    expect(readAndroidStartupAutoLocationEnabled(null)).toBe(true);
    expect(readAndroidStartupAutoLocationEnabled("true")).toBe(true);
    expect(readAndroidStartupAutoLocationEnabled("false")).toBe(false);
  });

  it("skips the Android gate outside native Android", () => {
    expect(getAndroidStartupGateDecision({
      isNativeAndroid: false,
    })).toEqual({
      action: ANDROID_STARTUP_GATE_ACTION.none,
      state: ANDROID_STARTUP_GATE_STATE.skipped,
    });
  });

  it("requests native device location first on Android when no startup location exists", () => {
    expect(getAndroidStartupGateDecision({
      isNativeAndroid: true,
    })).toEqual({
      action: ANDROID_STARTUP_GATE_ACTION.requestNativeGps,
      state: ANDROID_STARTUP_GATE_STATE.gpsPromptPending,
    });
  });

  it("requests native device location before notifications even when a previous manual city exists", () => {
    expect(getAndroidStartupGateDecision({
      isNativeAndroid: true,
      selectedLocation: { city: "Trieste", source: "manual" },
      startupNotificationsAsked: false,
    })).toEqual({
      action: ANDROID_STARTUP_GATE_ACTION.requestNativeGps,
      state: ANDROID_STARTUP_GATE_STATE.gpsPromptPending,
    });
  });

  it("resolves the device location after Android permission is granted", () => {
    expect(getAndroidStartupGateDecision({
      gpsStep: "granted",
      isNativeAndroid: true,
    })).toEqual({
      action: ANDROID_STARTUP_GATE_ACTION.resolveGpsLocation,
      state: ANDROID_STARTUP_GATE_STATE.gpsGrantedResolving,
    });
  });

  it("requires a manual location when GPS is denied and no location is selected yet", () => {
    expect(getAndroidStartupGateDecision({
      gpsFailureReason: "permission_denied",
      gpsStep: "failed",
      isNativeAndroid: true,
    })).toEqual({
      action: ANDROID_STARTUP_GATE_ACTION.requestManualLocation,
      state: ANDROID_STARTUP_GATE_STATE.gpsDenied,
    });
  });

  it("keeps temporary GPS failures separate from user denial", () => {
    expect(getGpsFailureState("native_location_timeout")).toBe(ANDROID_STARTUP_GATE_STATE.gpsTemporaryFailure);
    expect(getAndroidStartupGateDecision({
      gpsFailureReason: "native_location_timeout",
      gpsStep: "failed",
      isNativeAndroid: true,
    })).toEqual({
      action: ANDROID_STARTUP_GATE_ACTION.resolveGpsLocation,
      state: ANDROID_STARTUP_GATE_STATE.gpsTemporaryFailure,
    });
  });

  it("asks native notifications only after a GPS or manual location exists", () => {
    expect(shouldPromptStartupNotifications({
      hasResolvedOrSelectedLocation: false,
      isNativeAndroid: true,
      startupNotificationsAsked: false,
      weatherAlertsEnabled: false,
    })).toBe(false);

    expect(shouldPromptStartupNotifications({
      hasResolvedOrSelectedLocation: true,
      isNativeAndroid: true,
      startupNotificationsAsked: false,
      weatherAlertsEnabled: false,
    })).toBe(true);
  });

  it("requests notifications after a resolved device location", () => {
    expect(getAndroidStartupGateDecision({
      isNativeAndroid: true,
      resolvedLocation: { city: "Pordenone", source: "android_current_location" },
      startupNotificationsAsked: false,
      weatherAlertsEnabled: false,
    })).toEqual({
      action: ANDROID_STARTUP_GATE_ACTION.requestNativeNotifications,
      state: ANDROID_STARTUP_GATE_STATE.notificationsPromptPending,
    });
  });

  it("requests notifications after a manual location is selected", () => {
    expect(getAndroidStartupGateDecision({
      gpsFailureReason: "permission_denied",
      gpsStep: "failed",
      isNativeAndroid: true,
      selectedLocation: { city: "Trieste", source: "manual" },
      startupNotificationsAsked: false,
      weatherAlertsEnabled: false,
    })).toEqual({
      action: ANDROID_STARTUP_GATE_ACTION.requestNativeNotifications,
      state: ANDROID_STARTUP_GATE_STATE.notificationsPromptPending,
    });
  });

  it("does not re-prompt notifications when already asked or enabled", () => {
    expect(getAndroidStartupGateDecision({
      isNativeAndroid: true,
      resolvedLocation: { city: "Udine" },
      startupNotificationsAsked: "true",
    })).toEqual({
      action: ANDROID_STARTUP_GATE_ACTION.none,
      state: ANDROID_STARTUP_GATE_STATE.ready,
    });

    expect(getAndroidStartupGateDecision({
      isNativeAndroid: true,
      resolvedLocation: { city: "Udine" },
      weatherAlertsEnabled: true,
    })).toEqual({
      action: ANDROID_STARTUP_GATE_ACTION.none,
      state: ANDROID_STARTUP_GATE_STATE.ready,
    });
  });

  it("does not treat the fallback app city as selected unless it is passed explicitly", () => {
    expect(hasStartupLocation(null)).toBe(false);
    expect(hasStartupLocation({ city: "" })).toBe(false);
    expect(hasStartupLocation({ city: "Udine", source: "manual" })).toBe(true);
  });
});
