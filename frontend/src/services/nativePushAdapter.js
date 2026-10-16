import { Capacitor, registerPlugin } from "@capacitor/core";

import { isAndroidCapacitorRuntime } from "./apiConfig";
import { isLocalWeatherPilot } from "./localWeatherPilot";

export const NATIVE_PUSH_PLUGIN_NAME = "PushNotifications";
export const NATIVE_NOTIFICATION_SETTINGS_PLUGIN_NAME = "MeteoNotificationSettings";
export const NATIVE_PUSH_CHANNEL_ID = "mf_official_alerts_v1";
export const NATIVE_PUSH_CHANNEL_NAME = "Allerte ufficiali";
export const NATIVE_PUSH_NATIONAL_CHANNEL_ID = "mf_national_official_alerts_v1";
export const NATIVE_PUSH_LOCAL_CHANNEL_ID = "mf_weather_notices_v1";

const CapacitorPushNotifications = registerPlugin(NATIVE_PUSH_PLUGIN_NAME);
const CapacitorNotificationSettings = registerPlugin(NATIVE_NOTIFICATION_SETTINGS_PLUGIN_NAME);

export const NATIVE_PUSH_PERMISSION = Object.freeze({
  granted: "granted",
  denied: "denied",
  prompt: "prompt",
  unsupported: "unsupported",
  unknown: "unknown",
});

export const DEFAULT_NATIVE_PUSH_ANDROID_CHANNEL = Object.freeze({
  id: NATIVE_PUSH_CHANNEL_ID,
  name: NATIVE_PUSH_CHANNEL_NAME,
  description: "Allerte ufficiali valide per il Friuli Venezia Giulia",
  importance: 4,
  visibility: 1,
  lights: true,
  vibration: true,
});

export const DEFAULT_NATIVE_PUSH_LOCAL_ANDROID_CHANNEL = Object.freeze({
  id: NATIVE_PUSH_LOCAL_CHANNEL_ID,
  name: "Avvisi meteo locali",
  description: "Avvisi meteo per la località selezionata",
  importance: 3,
  visibility: 0,
  lights: true,
  vibration: false,
});

export const DEFAULT_NATIVE_PUSH_NATIONAL_ANDROID_CHANNEL = Object.freeze({
  id: NATIVE_PUSH_NATIONAL_CHANNEL_ID,
  name: "Allerte nazionali",
  description: "Allerte ufficiali per il Comune italiano selezionato manualmente",
  importance: 4,
  visibility: 1,
  lights: true,
  vibration: true,
});

export const DEFAULT_NATIVE_PUSH_ANDROID_CHANNELS = Object.freeze([
  DEFAULT_NATIVE_PUSH_ANDROID_CHANNEL,
  DEFAULT_NATIVE_PUSH_LOCAL_ANDROID_CHANNEL,
  DEFAULT_NATIVE_PUSH_NATIONAL_ANDROID_CHANNEL,
]);

export function createNativePushRuntime(pushNotifications = null) {
  return { pushNotifications };
}

function normalizeToken(value, fallback = "") {
  const token = String(value || "").trim().toLowerCase();
  return token || fallback;
}

function normalizePermissionValue(value) {
  const receive = normalizeToken(value);

  if (receive === "granted") return NATIVE_PUSH_PERMISSION.granted;
  if (receive === "denied") return NATIVE_PUSH_PERMISSION.denied;
  if (
    receive === "prompt" ||
    receive === "prompt-with-rationale" ||
    receive === "default"
  ) return NATIVE_PUSH_PERMISSION.prompt;
  if (receive === "unsupported") return NATIVE_PUSH_PERMISSION.unsupported;

  return NATIVE_PUSH_PERMISSION.unknown;
}

export function normalizeNativePushPermission(payload) {
  if (typeof payload === "string") {
    return { receive: normalizePermissionValue(payload) };
  }

  const record = payload && typeof payload === "object" ? payload : {};
  return {
    ...record,
    receive: normalizePermissionValue(record.receive ?? record.permission),
  };
}

export function isNativePushPluginAvailable({ pushNotifications } = {}) {
  return Boolean(
    pushNotifications &&
    typeof pushNotifications.checkPermissions === "function" &&
    typeof pushNotifications.requestPermissions === "function"
  );
}

export function getNativePushNotificationsPlugin({
  capacitor = Capacitor,
  localPilot = isLocalWeatherPilot(),
  pushNotifications = CapacitorPushNotifications,
} = {}) {
  if (localPilot) return null;
  if (!isAndroidCapacitorRuntime(capacitor)) return null;

  try {
    return capacitor?.isPluginAvailable?.(NATIVE_PUSH_PLUGIN_NAME)
      ? pushNotifications
      : null;
  } catch {
    return null;
  }
}

export async function openNativeNotificationSettings({
  capacitor = Capacitor,
  notificationSettings = CapacitorNotificationSettings,
} = {}) {
  if (!isAndroidCapacitorRuntime(capacitor)) {
    return { ok: false, reason: "not_android" };
  }

  try {
    if (
      !capacitor?.isPluginAvailable?.(NATIVE_NOTIFICATION_SETTINGS_PLUGIN_NAME)
      || typeof notificationSettings?.openSettings !== "function"
    ) {
      return { ok: false, reason: "notification_settings_unavailable" };
    }

    await notificationSettings.openSettings();
    return { ok: true };
  } catch (error) {
    return {
      error: error?.message || "notification_settings_open_failed",
      ok: false,
      reason: "notification_settings_open_failed",
    };
  }
}

export async function checkNativePushPermission({ pushNotifications } = {}) {
  if (!isNativePushPluginAvailable({ pushNotifications })) {
    return {
      available: false,
      receive: NATIVE_PUSH_PERMISSION.unsupported,
    };
  }

  try {
    return {
      available: true,
      ...normalizeNativePushPermission(await pushNotifications.checkPermissions()),
    };
  } catch (error) {
    return {
      available: false,
      error: error?.message || "native_push_check_failed",
      receive: NATIVE_PUSH_PERMISSION.unknown,
    };
  }
}

export async function requestNativePushPermission({
  pushNotifications,
  checkFirst = true,
} = {}) {
  if (!isNativePushPluginAvailable({ pushNotifications })) {
    return {
      available: false,
      receive: NATIVE_PUSH_PERMISSION.unsupported,
      requested: false,
    };
  }

  const current = checkFirst
    ? await checkNativePushPermission({ pushNotifications })
    : { available: true, receive: NATIVE_PUSH_PERMISSION.prompt };

  if (!current.available || current.receive !== NATIVE_PUSH_PERMISSION.prompt) {
    return {
      ...current,
      requested: false,
    };
  }

  try {
    return {
      available: true,
      requested: true,
      ...normalizeNativePushPermission(await pushNotifications.requestPermissions()),
    };
  } catch (error) {
    return {
      available: false,
      error: error?.message || "native_push_request_failed",
      receive: NATIVE_PUSH_PERMISSION.unknown,
      requested: true,
    };
  }
}

export async function ensureNativePushAndroidChannel({
  pushNotifications,
  platform = "android",
  channel = DEFAULT_NATIVE_PUSH_ANDROID_CHANNEL,
} = {}) {
  if (normalizeToken(platform) !== "android") {
    return { ok: true, skipped: true, reason: "not_android" };
  }

  if (!pushNotifications || typeof pushNotifications.createChannel !== "function") {
    return { ok: false, reason: "native_push_channel_unavailable" };
  }

  try {
    await pushNotifications.createChannel(channel);
    return { ok: true, channelId: channel.id };
  } catch (error) {
    return {
      ok: false,
      error: error?.message || "native_push_channel_failed",
      reason: "native_push_channel_failed",
    };
  }
}

export async function ensureNativePushAndroidChannels({
  channels = DEFAULT_NATIVE_PUSH_ANDROID_CHANNELS,
  platform = "android",
  pushNotifications,
} = {}) {
  const results = [];

  for (const channel of channels) {
    results.push(await ensureNativePushAndroidChannel({
      channel,
      platform,
      pushNotifications,
    }));
  }

  const failed = results.find((result) => result?.ok === false);
  return failed || {
    channelIds: results.map((result) => result.channelId).filter(Boolean),
    ok: true,
  };
}

export async function registerNativePush({ pushNotifications } = {}) {
  if (!pushNotifications || typeof pushNotifications.register !== "function") {
    return { ok: false, reason: "native_push_register_unavailable" };
  }

  try {
    await pushNotifications.register();
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error?.message || "native_push_register_failed",
      reason: "native_push_register_failed",
    };
  }
}

export async function unregisterNativePush({ pushNotifications } = {}) {
  if (!pushNotifications || typeof pushNotifications.unregister !== "function") {
    return { ok: false, reason: "native_push_unregister_unavailable" };
  }

  try {
    await pushNotifications.unregister();
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error?.message || "native_push_unregister_failed",
      reason: "native_push_unregister_failed",
    };
  }
}

export async function addNativePushListeners({
  onNotificationAction,
  onNotificationReceived,
  onRegistration,
  onRegistrationError,
  pushNotifications,
} = {}) {
  if (!pushNotifications || typeof pushNotifications.addListener !== "function") {
    return { ok: false, reason: "native_push_listener_unavailable" };
  }

  const listeners = [];

  try {

    if (typeof onRegistration === "function") {
      listeners.push(await pushNotifications.addListener("registration", (token) => {
        onRegistration({
          token: String(token?.value || ""),
        });
      }));
    }

    if (typeof onNotificationReceived === "function") {
      listeners.push(await pushNotifications.addListener("pushNotificationReceived", (notification) => {
        onNotificationReceived(notification);
      }));
    }

    if (typeof onNotificationAction === "function") {
      listeners.push(await pushNotifications.addListener("pushNotificationActionPerformed", (action) => {
        onNotificationAction(action);
      }));
    }

    if (typeof onRegistrationError === "function") {
      listeners.push(await pushNotifications.addListener("registrationError", (error) => {
        onRegistrationError(error);
      }));
    }
  } catch (error) {
    await Promise.all(
      listeners
        .filter((listener) => listener && typeof listener.remove === "function")
        .map((listener) => listener.remove()),
    );
    return {
      error: error?.message || "native_push_listener_failed",
      ok: false,
      reason: "native_push_listener_failed",
    };
  }

  return {
    ok: true,
    remove: async () => {
      await Promise.all(
        listeners
          .filter((listener) => listener && typeof listener.remove === "function")
          .map((listener) => listener.remove()),
      );
    },
  };
}
