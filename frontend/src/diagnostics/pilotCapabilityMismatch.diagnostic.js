import { describe, expect, it, vi } from "vitest";

import {
  FIREBASE_APP_CHECK_PLUGIN_NAME,
  getFirebaseAppCheckToken,
  isPilotCommunityReportingAvailable,
} from "../services/firebaseAppCheckAdapter";
import { getNativePushNotificationsPlugin } from "../services/nativePushAdapter";

function localPilotCapacitorRuntime() {
  return {
    getPlatform: vi.fn(() => "android"),
    isNativePlatform: vi.fn(() => true),
    // MainActivity registers this bridge even in localPilot. The localPilot
    // source set installs no Firebase provider/identity, so bridge presence is
    // not proof that it can issue a token.
    isPluginAvailable: vi.fn(name => name === FIREBASE_APP_CHECK_PLUGIN_NAME),
  };
}

describe("open localPilot capability contract at revision 3f517a8", () => {
  it("does not advertise community submission when its required App Check token is unavailable", async () => {
    const capacitor = localPilotCapacitorRuntime();
    const pushNotifications = { register: vi.fn() };
    const appCheckPlugin = {
      getToken: vi.fn().mockRejectedValue(new Error("firebase_app_check_not_configured")),
    };

    // This is the real localPilot push policy, not a UI mock.
    expect(getNativePushNotificationsPlugin({
      capacitor,
      localPilot: true,
      pushNotifications,
    })).toBeNull();

    // This reproduces the real localPilot App Check bridge outcome: the bridge
    // exists, while its package has no configured Firebase Android identity.
    await expect(getFirebaseAppCheckToken({ appCheckPlugin, capacitor }))
      .rejects.toMatchObject({ code: "firebase_app_check_token_failed" });

    // LiveView uses this synchronous gate to expose the submission action.
    // It currently returns true for every native Android runtime, even after
    // the capability above has proved unavailable.
    expect(isPilotCommunityReportingAvailable({ capacitor })).toBe(false);
  });
});
