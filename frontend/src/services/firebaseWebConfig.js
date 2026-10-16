function normalizeText(value) {
  return String(value || "").trim();
}

function readBoolean(value) {
  return String(value || "").trim().toLowerCase() === "true";
}

// Firebase Web identifiers and browser-facing keys are public configuration,
// not server credentials. Keeping the production values versioned makes the
// guarded Hosting build reproducible without accepting arbitrary VITE_* input.
export const FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG = Object.freeze({
  apiKey: "AIzaSyBwf2FHYpVAy0RmwNt1knp0QwOBjZBng70",
  appCheckSiteKey: "6Lf-QoctAAAAAHwIacD7sA2a166596cSXI7ijObk",
  appId: "1:49007668366:web:a848e70da40a12eb852ddf",
  authDomain: "meteo-friul.firebaseapp.com",
  messagingSenderId: "49007668366",
  projectId: "meteo-friul",
  storageBucket: "meteo-friul.firebasestorage.app",
  vapidKey: "BJMyuP76yQHJyT_kNFUBF8eVFy-DQotac3bHVoUwF88bCeNJVEfp8Gks11UEOgbJVk972o3AB6I9j7cPnkXmJ6Q",
  // Production enrollment is guarded by Firebase App Check and by the
  // backend's explicit allowlist for this Web app id.
  webPushEnrollmentEnabled: true,
});

function readPublicValue(env, key, productionValue) {
  const configured = normalizeText(env?.[key]);
  if (configured) return configured;
  return env?.PROD === true ? productionValue : "";
}

export function readFirebaseWebConfig(env = import.meta.env) {
  const firebaseConfig = {
    apiKey: readPublicValue(
      env,
      "VITE_FIREBASE_API_KEY",
      FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.apiKey,
    ),
    appId: readPublicValue(
      env,
      "VITE_FIREBASE_APP_ID",
      FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.appId,
    ),
    authDomain: readPublicValue(
      env,
      "VITE_FIREBASE_AUTH_DOMAIN",
      FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.authDomain,
    ),
    messagingSenderId: readPublicValue(
      env,
      "VITE_FIREBASE_MESSAGING_SENDER_ID",
      FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.messagingSenderId,
    ),
    projectId: readPublicValue(
      env,
      "VITE_FIREBASE_PROJECT_ID",
      FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.projectId,
    ),
    storageBucket: readPublicValue(
      env,
      "VITE_FIREBASE_STORAGE_BUCKET",
      FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.storageBucket,
    ),
  };
  const appConfigured = [
    firebaseConfig.apiKey,
    firebaseConfig.appId,
    firebaseConfig.messagingSenderId,
    firebaseConfig.projectId,
  ].every(Boolean);
  const appCheckSiteKey = readPublicValue(
    env,
    "VITE_FIREBASE_APP_CHECK_ENTERPRISE_SITE_KEY",
    FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.appCheckSiteKey,
  );
  const vapidKey = readPublicValue(
    env,
    "VITE_FIREBASE_VAPID_KEY",
    FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.vapidKey,
  );
  const debugRequested = readBoolean(env?.VITE_FIREBASE_APP_CHECK_DEBUG);
  const configuredDebugToken = normalizeText(env?.VITE_FIREBASE_APP_CHECK_DEBUG_TOKEN);
  const appCheckDebugEnabled = env?.DEV === true && debugRequested && Boolean(configuredDebugToken);
  const webPushEnrollmentEnabled = env?.PROD === true
    ? FIREBASE_WEB_PRODUCTION_PUBLIC_CONFIG.webPushEnrollmentEnabled
    : readBoolean(env?.VITE_WEB_PUSH_ENROLLMENT_ENABLED);

  return {
    appCheckDebugEnabled,
    appCheckDebugToken: appCheckDebugEnabled ? configuredDebugToken : "",
    appCheckSiteKey,
    appConfigured,
    firebaseConfig,
    messagingConfigured: appConfigured && Boolean(vapidKey) && webPushEnrollmentEnabled,
    appCheckConfigured: appConfigured && Boolean(appCheckSiteKey),
    vapidKey,
    webPushEnrollmentEnabled,
  };
}

export function isFirebaseWebAppCheckConfigured(options) {
  return readFirebaseWebConfig(options?.env).appCheckConfigured;
}

export function isFirebaseWebMessagingConfigured(options) {
  return readFirebaseWebConfig(options?.env).messagingConfigured;
}
