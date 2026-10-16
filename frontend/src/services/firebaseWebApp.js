import { readFirebaseWebConfig } from "./firebaseWebConfig";

export const FIREBASE_WEB_APP_NAME = "meteo-friul-web";

let firebaseWebAppPromise = null;

export async function getFirebaseWebApp({
  config = readFirebaseWebConfig(),
  firebaseAppModule,
} = {}) {
  if (!config.appConfigured) {
    throw new Error("firebase_web_app_not_configured");
  }

  if (firebaseAppModule) {
    const existing = firebaseAppModule
      .getApps()
      .find((app) => app.name === FIREBASE_WEB_APP_NAME);
    return existing || firebaseAppModule.initializeApp(
      config.firebaseConfig,
      FIREBASE_WEB_APP_NAME,
    );
  }

  if (!firebaseWebAppPromise) {
    firebaseWebAppPromise = import("firebase/app").then((module) => {
      const existing = module
        .getApps()
        .find((app) => app.name === FIREBASE_WEB_APP_NAME);
      return existing || module.initializeApp(
        config.firebaseConfig,
        FIREBASE_WEB_APP_NAME,
      );
    });
  }

  return firebaseWebAppPromise;
}
