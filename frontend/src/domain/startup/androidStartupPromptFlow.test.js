import { describe, expect, it, vi } from "vitest";

import {
  ANDROID_STARTUP_GATE_STATE,
} from "./androidPermissionGate";
import {
  ANDROID_STARTUP_PROMPT_STEP,
  runAndroidStartupPromptFlow,
} from "./androidStartupPromptFlow";

describe("androidStartupPromptFlow", () => {
  it("skips native prompts outside Android", async () => {
    const requestBackgroundLocationDisclosure = vi.fn();
    const resolveDeviceLocation = vi.fn();
    const requestNativeNotifications = vi.fn();

    await expect(runAndroidStartupPromptFlow({
      isNativeAndroid: false,
      requestBackgroundLocationDisclosure,
      requestNativeNotifications,
      resolveDeviceLocation,
    })).resolves.toMatchObject({
      completed: true,
      decision: { state: ANDROID_STARTUP_GATE_STATE.skipped },
      steps: [{ step: ANDROID_STARTUP_PROMPT_STEP.skipped }],
    });

    expect(requestBackgroundLocationDisclosure).not.toHaveBeenCalled();
    expect(resolveDeviceLocation).not.toHaveBeenCalled();
    expect(requestNativeNotifications).not.toHaveBeenCalled();
  });

  it("awaits disclosure, then requests GPS, then notifications", async () => {
    const order = [];
    const requestBackgroundLocationDisclosure = vi.fn(async () => {
      order.push("disclosure");
      return true;
    });
    const resolveDeviceLocation = vi.fn(async () => {
      order.push("gps");
      return {
        ok: true,
        location: {
          city: "Pordenone",
          region: "Friuli Venezia Giulia",
          source: "android_current_location",
        },
      };
    });
    const requestNativeNotifications = vi.fn(async () => {
      order.push("notifications");
      return { receive: "granted", requested: true };
    });

    const result = await runAndroidStartupPromptFlow({
      isNativeAndroid: true,
      requestBackgroundLocationDisclosure,
      requestNativeNotifications,
      resolveDeviceLocation,
      startupNotificationsAsked: false,
      weatherAlertsEnabled: false,
    });

    expect(order).toEqual(["disclosure", "gps", "notifications"]);
    expect(result.completed).toBe(true);
    expect(result.resolvedLocation.city).toBe("Pordenone");
    expect(result.storagePatch).toEqual({
      startupNotificationsAsked: true,
      weatherAlertsEnabled: true,
    });
    expect(result.steps.map((step) => step.step)).toEqual([
      ANDROID_STARTUP_PROMPT_STEP.disclosureRequested,
      ANDROID_STARTUP_PROMPT_STEP.disclosureAccepted,
      ANDROID_STARTUP_PROMPT_STEP.gpsRequested,
      ANDROID_STARTUP_PROMPT_STEP.gpsResolved,
      ANDROID_STARTUP_PROMPT_STEP.notificationsRequested,
      ANDROID_STARTUP_PROMPT_STEP.ready,
    ]);
  });

  it("blocks GPS but still requests notification permission when disclosure is declined", async () => {
    const order = [];
    const requestBackgroundLocationDisclosure = vi.fn(async () => {
      order.push("disclosure");
      return false;
    });
    const resolveDeviceLocation = vi.fn(async () => {
      order.push("gps");
      return { ok: true, location: { city: "Udine" } };
    });
    const requestNativeNotifications = vi.fn(async () => {
      order.push("notifications");
      return { receive: "granted", requested: true };
    });

    const result = await runAndroidStartupPromptFlow({
      isNativeAndroid: true,
      requestBackgroundLocationDisclosure,
      requestNativeNotifications,
      resolveDeviceLocation,
    });

    expect(order).toEqual(["disclosure", "notifications"]);
    expect(resolveDeviceLocation).not.toHaveBeenCalled();
    expect(requestNativeNotifications).toHaveBeenCalledTimes(1);
    expect(result).toMatchObject({
      completed: false,
      disclosureAccepted: false,
      needsManualLocation: true,
      notificationResult: {
        receive: "granted",
        requested: true,
      },
      reason: "background_location_disclosure_declined",
      storagePatch: {
        startupNotificationsAsked: true,
        weatherAlertsEnabled: true,
      },
    });
    expect(result.steps.map((step) => step.step)).toEqual([
      ANDROID_STARTUP_PROMPT_STEP.disclosureRequested,
      ANDROID_STARTUP_PROMPT_STEP.disclosureDeclined,
      ANDROID_STARTUP_PROMPT_STEP.notificationsRequested,
      ANDROID_STARTUP_PROMPT_STEP.manualLocationRequired,
    ]);
  });

  it("asks notifications after GPS denial before requiring a manual location", async () => {
    const order = [];
    const requestNativeNotifications = vi.fn(async () => {
      order.push("notifications");
      return { receive: "granted", requested: true };
    });

    const result = await runAndroidStartupPromptFlow({
      backgroundLocationDisclosureAccepted: true,
      isNativeAndroid: true,
      requestNativeNotifications,
      resolveDeviceLocation: async () => {
        order.push("gps");
        return { ok: false, reason: "permission_denied" };
      },
    });

    expect(result.completed).toBe(false);
    expect(result.needsManualLocation).toBe(true);
    expect(result.decision.state).toBe(ANDROID_STARTUP_GATE_STATE.gpsDenied);
    expect(order).toEqual(["gps", "notifications"]);
    expect(result.storagePatch).toEqual({
      startupNotificationsAsked: true,
      weatherAlertsEnabled: true,
    });
    expect(result.steps.map((step) => step.step)).toEqual([
      ANDROID_STARTUP_PROMPT_STEP.gpsRequested,
      ANDROID_STARTUP_PROMPT_STEP.gpsFailed,
      ANDROID_STARTUP_PROMPT_STEP.notificationsRequested,
      ANDROID_STARTUP_PROMPT_STEP.manualLocationRequired,
    ]);
  });

  it("asks notifications even when the native GPS handler is unavailable", async () => {
    const requestNativeNotifications = vi.fn(async () => ({
      receive: "granted",
      requested: true,
    }));

    const result = await runAndroidStartupPromptFlow({
      backgroundLocationDisclosureAccepted: true,
      isNativeAndroid: true,
      requestNativeNotifications,
    });

    expect(requestNativeNotifications).toHaveBeenCalledTimes(1);
    expect(result.needsManualLocation).toBe(true);
    expect(result.steps.map((step) => step.step)).toEqual([
      ANDROID_STARTUP_PROMPT_STEP.gpsRequested,
      ANDROID_STARTUP_PROMPT_STEP.gpsFailed,
      ANDROID_STARTUP_PROMPT_STEP.notificationsRequested,
      ANDROID_STARTUP_PROMPT_STEP.manualLocationRequired,
    ]);
    expect(result.steps[1]).toMatchObject({
      reason: "native_unavailable",
      state: ANDROID_STARTUP_GATE_STATE.gpsUnavailable,
    });
  });

  it("asks notifications after GPS denial when a manual location is already selected", async () => {
    const order = [];
    const requestNativeNotifications = vi.fn(async () => {
      order.push("notifications");
      return { receive: "denied", requested: true };
    });

    const result = await runAndroidStartupPromptFlow({
      backgroundLocationDisclosureAccepted: true,
      isNativeAndroid: true,
      requestNativeNotifications,
      resolveDeviceLocation: async () => {
        order.push("gps");
        return { ok: false, reason: "permission_denied" };
      },
      selectedLocation: { city: "Gorizia", source: "manual" },
    });

    expect(order).toEqual(["gps", "notifications"]);
    expect(result.completed).toBe(true);
    expect(result.storagePatch).toEqual({
      startupNotificationsAsked: true,
      weatherAlertsEnabled: false,
    });
    expect(result.steps.map((step) => step.step)).toEqual([
      ANDROID_STARTUP_PROMPT_STEP.gpsRequested,
      ANDROID_STARTUP_PROMPT_STEP.gpsFailed,
      ANDROID_STARTUP_PROMPT_STEP.notificationsRequested,
      ANDROID_STARTUP_PROMPT_STEP.ready,
    ]);
    expect(result.steps[1]).toMatchObject({
      state: ANDROID_STARTUP_GATE_STATE.gpsDenied,
      reason: "permission_denied",
    });
  });

  it("rechecks the OS permission when a stale marker says it was already asked", async () => {
    const requestNativeNotifications = vi.fn(async () => ({
      receive: "granted",
      requested: true,
    }));

    const result = await runAndroidStartupPromptFlow({
      backgroundLocationDisclosureAccepted: true,
      isNativeAndroid: true,
      requestNativeNotifications,
      resolveDeviceLocation: async () => ({
        ok: true,
        location: { city: "Udine", source: "android_last_location" },
      }),
      startupNotificationsAsked: true,
    });

    expect(result.completed).toBe(true);
    expect(requestNativeNotifications).toHaveBeenCalledTimes(1);
    expect(result.storagePatch).toEqual({
      startupNotificationsAsked: true,
      weatherAlertsEnabled: true,
    });
  });

  it("asks notifications after one temporary GPS failure and leaves GPS retryable", async () => {
    const requestNativeNotifications = vi.fn(async () => ({
      receive: "denied",
      requested: true,
    }));

    const result = await runAndroidStartupPromptFlow({
      backgroundLocationDisclosureAccepted: true,
      isNativeAndroid: true,
      requestNativeNotifications,
      resolveDeviceLocation: async () => ({ ok: false, reason: "native_location_timeout" }),
    });

    expect(result.completed).toBe(false);
    expect(result.retryableGps).toBe(true);
    expect(result.decision.state).toBe(ANDROID_STARTUP_GATE_STATE.gpsTemporaryFailure);
    expect(requestNativeNotifications).toHaveBeenCalledTimes(1);
    expect(result.storagePatch).toEqual({
      startupNotificationsAsked: true,
      weatherAlertsEnabled: false,
    });
  });

  it("can start from an existing manual location when automatic location is disabled", async () => {
    const resolveDeviceLocation = vi.fn();
    const requestNativeNotifications = vi.fn(async () => ({ receive: "granted", requested: true }));

    const result = await runAndroidStartupPromptFlow({
      autoLocationEnabled: false,
      isNativeAndroid: true,
      requestNativeNotifications,
      resolveDeviceLocation,
      selectedLocation: { city: "Trieste", source: "manual" },
    });

    expect(resolveDeviceLocation).not.toHaveBeenCalled();
    expect(requestNativeNotifications).toHaveBeenCalledTimes(1);
    expect(result.completed).toBe(true);
  });
});
