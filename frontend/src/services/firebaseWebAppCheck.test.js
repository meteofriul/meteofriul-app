import { describe, expect, it, vi } from "vitest";

import {
  getFirebaseWebAppCheck,
  getFirebaseWebAppCheckToken,
} from "./firebaseWebAppCheck";

function configuredWebAppCheck(overrides = {}) {
  return {
    appCheckConfigured: true,
    appCheckDebugEnabled: false,
    appCheckDebugToken: "",
    appCheckSiteKey: "enterprise-site-key",
    ...overrides,
  };
}

describe("Firebase Web App Check", () => {
  it("initializes the Enterprise provider lazily without Analytics", async () => {
    const provider = { type: "enterprise" };
    const appCheckModule = {
      initializeAppCheck: vi.fn(() => ({ type: "app-check" })),
      ReCaptchaEnterpriseProvider: vi.fn(function EnterpriseProvider() { return provider; }),
    };
    const firebaseApp = { name: "web-app" };

    await expect(getFirebaseWebAppCheck({
      appCheckModule,
      config: configuredWebAppCheck(),
      firebaseApp,
    })).resolves.toEqual({ type: "app-check" });
    expect(appCheckModule.ReCaptchaEnterpriseProvider).toHaveBeenCalledWith(
      "enterprise-site-key",
    );
    expect(appCheckModule.initializeAppCheck).toHaveBeenCalledWith(firebaseApp, {
      isTokenAutoRefreshEnabled: true,
      provider,
    });
  });

  it("enables debug only when the already-gated config explicitly requests it", async () => {
    const globalObject = {};
    const appCheckModule = {
      initializeAppCheck: vi.fn(() => ({})),
      ReCaptchaEnterpriseProvider: vi.fn(function EnterpriseProvider() {}),
    };

    await getFirebaseWebAppCheck({
      appCheckModule,
      config: configuredWebAppCheck({
        appCheckDebugEnabled: true,
        appCheckDebugToken: "local-debug-token",
      }),
      firebaseApp: {},
      globalObject,
    });

    expect(globalObject.FIREBASE_APPCHECK_DEBUG_TOKEN).toBe("local-debug-token");
  });

  it("returns a trimmed App Check token", async () => {
    const appCheckModule = {
      getToken: vi.fn(async () => ({ token: " web-app-check-token " })),
      initializeAppCheck: vi.fn(() => ({ type: "app-check" })),
      ReCaptchaEnterpriseProvider: vi.fn(function EnterpriseProvider() {}),
    };

    await expect(getFirebaseWebAppCheckToken({
      appCheckModule,
      config: configuredWebAppCheck(),
      firebaseApp: {},
      tokenProvider: appCheckModule.getToken,
    })).resolves.toBe("web-app-check-token");
  });
});
