import { describe, expect, it } from "vitest";

import {
  FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG,
  readFirebaseWebConfig,
} from "./firebaseWebConfig";

const PUBLIC_CONFIG = {
  VITE_FIREBASE_API_KEY: "public-api-key",
  VITE_FIREBASE_APP_ID: "app-id",
  VITE_FIREBASE_APP_CHECK_ENTERPRISE_SITE_KEY: "enterprise-site-key",
  VITE_FIREBASE_MESSAGING_SENDER_ID: "sender-id",
  VITE_FIREBASE_PROJECT_ID: "project-id",
  VITE_FIREBASE_VAPID_KEY: "public-vapid-key",
  VITE_WEB_PUSH_ENROLLMENT_ENABLED: "true",
};

describe("Firebase web configuration", () => {
  it("requires complete public app, App Check and messaging configuration", () => {
    const config = readFirebaseWebConfig(PUBLIC_CONFIG);

    expect(config.appConfigured).toBe(true);
    expect(config.appCheckConfigured).toBe(true);
    expect(config.messagingConfigured).toBe(true);
    expect(config.firebaseConfig).toMatchObject({
      apiKey: "public-api-key",
      appId: "app-id",
      messagingSenderId: "sender-id",
      projectId: "project-id",
    });
  });

  it("keeps messaging disabled until the public VAPID key is supplied", () => {
    const config = readFirebaseWebConfig({ ...PUBLIC_CONFIG, VITE_FIREBASE_VAPID_KEY: "" });

    expect(config.appCheckConfigured).toBe(true);
    expect(config.messagingConfigured).toBe(false);
  });

  it("enables the guarded Web Push enrollment in production", () => {
    const config = readFirebaseWebConfig({ PROD: true });

    expect(config.appConfigured).toBe(true);
    expect(config.appCheckConfigured).toBe(true);
    expect(config.messagingConfigured).toBe(true);
    expect(config.webPushEnrollmentEnabled).toBe(true);
    expect(config.vapidKey).toBe(FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.vapidKey);
    expect(config.firebaseConfig).toMatchObject({
      apiKey: FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.apiKey,
      appId: FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.appId,
      messagingSenderId: FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.messagingSenderId,
      projectId: FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.projectId,
    });
  });

  it("can enable Web Push in development only through the dedicated enrollment flag", () => {
    const config = readFirebaseWebConfig({
      PROD: false,
      VITE_WEB_PUSH_ENROLLMENT_ENABLED: "true",
      ...PUBLIC_CONFIG,
    });

    expect(config.messagingConfigured).toBe(true);
    expect(config.webPushEnrollmentEnabled).toBe(true);
  });

  it("does not silently enable Firebase public defaults in development", () => {
    const config = readFirebaseWebConfig({ DEV: true, PROD: false });

    expect(config.appConfigured).toBe(false);
    expect(config.appCheckConfigured).toBe(false);
    expect(config.messagingConfigured).toBe(false);
  });

  it("honors App Check debug only with an explicit development flag", () => {
    expect(readFirebaseWebConfig({
      ...PUBLIC_CONFIG,
      DEV: true,
      VITE_FIREBASE_APP_CHECK_DEBUG: "true",
      VITE_FIREBASE_APP_CHECK_DEBUG_TOKEN: "local-debug-token",
    })).toMatchObject({
      appCheckDebugEnabled: true,
      appCheckDebugToken: "local-debug-token",
    });
    expect(readFirebaseWebConfig({
      ...PUBLIC_CONFIG,
      DEV: false,
      VITE_FIREBASE_APP_CHECK_DEBUG: "true",
      VITE_FIREBASE_APP_CHECK_DEBUG_TOKEN: "must-not-be-used",
    })).toMatchObject({
      appCheckDebugEnabled: false,
      appCheckDebugToken: "",
    });
    expect(readFirebaseWebConfig({
      ...PUBLIC_CONFIG,
      DEV: true,
      VITE_FIREBASE_APP_CHECK_DEBUG: "true",
      VITE_FIREBASE_APP_CHECK_DEBUG_TOKEN: "",
    }).appCheckDebugEnabled).toBe(false);
  });
});
