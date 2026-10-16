import { describe, expect, it, vi } from "vitest";

import {
  FIREBASE_APP_CHECK_PLUGIN_NAME,
  FirebaseAppCheckTokenError,
  getFirebaseAppCheckToken,
  isPilotCommunityReportingAvailable,
} from "./firebaseAppCheckAdapter";

function capacitorRuntime({ available = true, native = true, platform = "android" } = {}) {
  return {
    getPlatform: vi.fn(() => platform),
    isNativePlatform: vi.fn(() => native),
    isPluginAvailable: vi.fn((name) => available && name === FIREBASE_APP_CHECK_PLUGIN_NAME),
  };
}

describe("Firebase App Check adapter", () => {
  it("enables reporting in native Android and a configured web runtime", () => {
    const webEnv = {
      VITE_FIREBASE_API_KEY: "api-key",
      VITE_FIREBASE_APP_ID: "app-id",
      VITE_FIREBASE_APP_CHECK_ENTERPRISE_SITE_KEY: "site-key",
      VITE_FIREBASE_MESSAGING_SENDER_ID: "sender-id",
      VITE_FIREBASE_PROJECT_ID: "project-id",
    };
    expect(isPilotCommunityReportingAvailable({ capacitor: capacitorRuntime() })).toBe(true);
    expect(isPilotCommunityReportingAvailable({
      capacitor: capacitorRuntime({ native: false, platform: "web" }),
    })).toBe(false);
    expect(isPilotCommunityReportingAvailable({
      capacitor: capacitorRuntime({ native: false, platform: "web" }),
      env: webEnv,
    })).toBe(true);
    expect(isPilotCommunityReportingAvailable({
      capacitor: capacitorRuntime({ platform: "ios" }),
    })).toBe(false);
  });

  it("does not request a token on web", async () => {
    const appCheckPlugin = { getToken: vi.fn() };

    await expect(getFirebaseAppCheckToken({
      appCheckPlugin,
      capacitor: capacitorRuntime({ native: false, platform: "web" }),
    })).resolves.toBe("");
    expect(appCheckPlugin.getToken).not.toHaveBeenCalled();
  });

  it("returns App Check from the configured web provider", async () => {
    const webTokenProvider = vi.fn(async () => " web-app-check-token ");

    await expect(getFirebaseAppCheckToken({
      capacitor: capacitorRuntime({ native: false, platform: "web" }),
      env: {
        VITE_FIREBASE_API_KEY: "api-key",
        VITE_FIREBASE_APP_ID: "app-id",
        VITE_FIREBASE_APP_CHECK_ENTERPRISE_SITE_KEY: "site-key",
        VITE_FIREBASE_MESSAGING_SENDER_ID: "sender-id",
        VITE_FIREBASE_PROJECT_ID: "project-id",
      },
      forceRefresh: true,
      webTokenProvider,
    })).resolves.toBe("web-app-check-token");
    expect(webTokenProvider).toHaveBeenCalledWith({ forceRefresh: true });
  });

  it("returns the trimmed native token on Android", async () => {
    const appCheckPlugin = {
      getToken: vi.fn().mockResolvedValue({ token: " pilot-app-check-token " }),
    };

    await expect(getFirebaseAppCheckToken({
      appCheckPlugin,
      capacitor: capacitorRuntime(),
    })).resolves.toBe("pilot-app-check-token");
    expect(appCheckPlugin.getToken).toHaveBeenCalledWith({ forceRefresh: false });
  });

  it("fails closed on Android when the native plugin is unavailable", async () => {
    const appCheckPlugin = { getToken: vi.fn() };

    await expect(getFirebaseAppCheckToken({
      appCheckPlugin,
      capacitor: capacitorRuntime({ available: false }),
    })).rejects.toMatchObject({
      code: "firebase_app_check_plugin_unavailable",
      name: "FirebaseAppCheckTokenError",
    });
    expect(appCheckPlugin.getToken).not.toHaveBeenCalled();
  });

  it("fails closed on Android when the plugin returns no token", async () => {
    await expect(getFirebaseAppCheckToken({
      appCheckPlugin: { getToken: vi.fn().mockResolvedValue({ token: " " }) },
      capacitor: capacitorRuntime(),
    })).rejects.toEqual(expect.any(FirebaseAppCheckTokenError));
  });
});
