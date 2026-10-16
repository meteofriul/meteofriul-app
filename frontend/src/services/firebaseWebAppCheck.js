import { getFirebaseWebApp } from "./firebaseWebApp";
import { readFirebaseWebConfig } from "./firebaseWebConfig";

let firebaseWebAppCheckPromise = null;

function enableExplicitLocalDebug(config, globalObject) {
  if (!config.appCheckDebugEnabled) return;

  globalObject.FIREBASE_APPCHECK_DEBUG_TOKEN = config.appCheckDebugToken;
}

export async function getFirebaseWebAppCheck({
  appCheckModule,
  config = readFirebaseWebConfig(),
  firebaseApp,
  globalObject = globalThis,
} = {}) {
  if (!config.appCheckConfigured) {
    throw new Error("firebase_web_app_check_not_configured");
  }

  const initialize = async (module) => {
    enableExplicitLocalDebug(config, globalObject);
    const app = firebaseApp || await getFirebaseWebApp({ config });
    return module.initializeAppCheck(app, {
      isTokenAutoRefreshEnabled: true,
      provider: new module.ReCaptchaEnterpriseProvider(config.appCheckSiteKey),
    });
  };

  if (appCheckModule) return initialize(appCheckModule);

  if (!firebaseWebAppCheckPromise) {
    firebaseWebAppCheckPromise = import("firebase/app-check").then(initialize);
  }
  return firebaseWebAppCheckPromise;
}

export async function getFirebaseWebAppCheckToken({
  appCheckModule,
  config = readFirebaseWebConfig(),
  firebaseApp,
  forceRefresh = false,
  globalObject = globalThis,
  tokenProvider,
} = {}) {
  const module = appCheckModule || await import("firebase/app-check");
  const appCheck = appCheckModule
    ? await getFirebaseWebAppCheck({
        appCheckModule: module,
        config,
        firebaseApp,
        globalObject,
      })
    : await getFirebaseWebAppCheck({ config });
  const payload = tokenProvider
    ? await tokenProvider(appCheck, Boolean(forceRefresh))
    : await module.getToken(appCheck, Boolean(forceRefresh));
  return String(payload?.token || "").trim();
}
