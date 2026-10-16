import {
  ANDROID_PERMISSION_STORAGE_KEYS,
  readAndroidStartupAutoLocationEnabled,
  readStoredBoolean,
} from "../domain/startup/androidPermissionGate";

function getStorage(storage = globalThis.window?.localStorage) {
  return storage || null;
}

function normalizeToken(value) {
  return String(value || "").trim().toLowerCase();
}

export function isNativeAndroidRuntime({ windowLike = globalThis.window } = {}) {
  const capacitor = windowLike?.Capacitor;

  try {
    if (
      typeof capacitor?.isNativePlatform === "function" &&
      capacitor.isNativePlatform() &&
      normalizeToken(capacitor.getPlatform?.()) === "android"
    ) {
      return true;
    }
  } catch {
    return false;
  }

  return Boolean(windowLike?.MeteoAndroid);
}

export function readAndroidStartupPromptStorage({ storage } = {}) {
  const localStorage = getStorage(storage);

  if (!localStorage) {
    return {
      autoLocationEnabled: true,
      startupNotificationsAsked: false,
      weatherAlertsEnabled: false,
    };
  }

  return {
    autoLocationEnabled: readAndroidStartupAutoLocationEnabled(
      localStorage.getItem(ANDROID_PERMISSION_STORAGE_KEYS.autoLocationEnabled),
    ),
    startupNotificationsAsked: readStoredBoolean(
      localStorage.getItem(ANDROID_PERMISSION_STORAGE_KEYS.startupNotificationsAsked),
    ),
    weatherAlertsEnabled: readStoredBoolean(
      localStorage.getItem(ANDROID_PERMISSION_STORAGE_KEYS.weatherAlertsEnabled),
    ),
  };
}

export function shouldPersistAndroidStartupNotificationPatch(result) {
  const receive = normalizeToken(result?.notificationResult?.receive);

  return Boolean(
    result?.storagePatch &&
    receive &&
    receive !== "unknown" &&
    receive !== "unsupported"
  );
}

export function writeAndroidStartupNotificationStoragePatch(patch, { storage } = {}) {
  const localStorage = getStorage(storage);
  if (!localStorage || !patch) return false;

  try {
    localStorage.setItem(
      ANDROID_PERMISSION_STORAGE_KEYS.startupNotificationsAsked,
      patch.startupNotificationsAsked ? "true" : "false",
    );
    localStorage.setItem(
      ANDROID_PERMISSION_STORAGE_KEYS.weatherAlertsEnabled,
      patch.weatherAlertsEnabled ? "true" : "false",
    );
    return true;
  } catch {
    return false;
  }
}
