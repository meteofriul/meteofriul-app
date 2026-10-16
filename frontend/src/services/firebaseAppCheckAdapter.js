import { Capacitor, registerPlugin } from "@capacitor/core";

import { isAndroidCapacitorRuntime } from "./apiConfig";
import { isFirebaseWebAppCheckConfigured } from "./firebaseWebConfig";
import { getFirebaseWebAppCheckToken } from "./firebaseWebAppCheck";
import { isLocalCommunityPilot } from "./localCommunityPilot";

export const FIREBASE_APP_CHECK_HEADER = "X-Firebase-AppCheck";
export const FIREBASE_APP_CHECK_PLUGIN_NAME = "MeteoFirebaseAppCheck";

const MeteoFirebaseAppCheck = registerPlugin(FIREBASE_APP_CHECK_PLUGIN_NAME);

export class FirebaseAppCheckTokenError extends Error {
  constructor(code, options = {}) {
    super(code, options);
    this.name = "FirebaseAppCheckTokenError";
    this.code = code;
  }
}

function isWebRuntime(capacitor) {
  return !capacitor?.isNativePlatform?.();
}

export function isPilotCommunityReportingAvailable({ capacitor = Capacitor, env } = {}) {
  if (isLocalCommunityPilot()) return true;
  if (isAndroidCapacitorRuntime(capacitor)) return true;
  return isWebRuntime(capacitor) && isFirebaseWebAppCheckConfigured({ env });
}

export async function getFirebaseAppCheckToken({
  appCheckPlugin = MeteoFirebaseAppCheck,
  capacitor = Capacitor,
  env,
  forceRefresh = false,
  webTokenProvider = getFirebaseWebAppCheckToken,
} = {}) {
  const isAndroid = isAndroidCapacitorRuntime(capacitor);
  if (!isAndroid) {
    if (!isWebRuntime(capacitor) || !isFirebaseWebAppCheckConfigured({ env })) return "";

    let token;
    try {
      token = await webTokenProvider({ forceRefresh: Boolean(forceRefresh) });
    } catch (error) {
      throw new FirebaseAppCheckTokenError("firebase_app_check_token_failed", { cause: error });
    }
    const normalizedToken = String(token || "").trim();
    if (!normalizedToken) {
      throw new FirebaseAppCheckTokenError("firebase_app_check_token_missing");
    }
    return normalizedToken;
  }

  if (!capacitor?.isPluginAvailable?.(FIREBASE_APP_CHECK_PLUGIN_NAME)) {
    throw new FirebaseAppCheckTokenError("firebase_app_check_plugin_unavailable");
  }

  if (typeof appCheckPlugin?.getToken !== "function") {
    throw new FirebaseAppCheckTokenError("firebase_app_check_get_token_unavailable");
  }

  let payload;
  try {
    payload = await appCheckPlugin.getToken({ forceRefresh: Boolean(forceRefresh) });
  } catch (error) {
    throw new FirebaseAppCheckTokenError("firebase_app_check_token_failed", { cause: error });
  }

  const token = String(payload?.token || "").trim();
  if (!token) {
    throw new FirebaseAppCheckTokenError("firebase_app_check_token_missing");
  }

  return token;
}
