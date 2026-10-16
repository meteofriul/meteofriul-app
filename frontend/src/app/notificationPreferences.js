export const NOTIFICATION_PREFERENCES_STORAGE_KEY = "mfNotificationPreferences:v1";

export const DEFAULT_NOTIFICATION_PREFERENCES = Object.freeze({
  officialAlerts: true,
  // FVG consent does not silently authorize a new national subscription.
  nationalOfficialAlerts: false,
  weatherNotices: true,
});

function getBrowserStorage() {
  return globalThis.window?.localStorage;
}

export function normalizeNotificationPreferences(value) {
  const preferences = value && typeof value === "object" ? value : {};

  return {
    officialAlerts: preferences.officialAlerts !== false,
    nationalOfficialAlerts: preferences.nationalOfficialAlerts === true,
    weatherNotices: preferences.weatherNotices !== false,
  };
}

export function readNotificationPreferences(storage = getBrowserStorage()) {
  try {
    const stored = storage?.getItem(NOTIFICATION_PREFERENCES_STORAGE_KEY);
    if (!stored) return { ...DEFAULT_NOTIFICATION_PREFERENCES };

    return normalizeNotificationPreferences(JSON.parse(stored));
  } catch {
    return { ...DEFAULT_NOTIFICATION_PREFERENCES };
  }
}

export function writeNotificationPreferences(preferences, storage = getBrowserStorage()) {
  const normalized = normalizeNotificationPreferences(preferences);

  try {
    storage?.setItem(NOTIFICATION_PREFERENCES_STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    // Keep the in-memory preference usable when persistent storage is unavailable.
  }

  return normalized;
}

export function toPushNotificationPreferences(preferences) {
  const normalized = normalizeNotificationPreferences(preferences);

  return {
    official_alerts: normalized.officialAlerts,
    rain: normalized.weatherNotices,
    storms: normalized.weatherNotices,
    wind: normalized.weatherNotices,
    snow: normalized.weatherNotices,
    heat: normalized.weatherNotices,
  };
}
