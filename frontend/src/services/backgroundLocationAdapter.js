import { Capacitor, registerPlugin } from "@capacitor/core";

import { isAndroidCapacitorRuntime } from "./apiConfig";
import { isValidPushInstallationId } from "./pushDeviceRegistration";

export const BACKGROUND_LOCATION_PLUGIN_NAME = "MeteoBackgroundLocation";

const MeteoBackgroundLocation = registerPlugin(BACKGROUND_LOCATION_PLUGIN_NAME);

export const DEFAULT_BACKGROUND_LOCATION_STATUS = Object.freeze({
  available: false,
  backgroundPermission: false,
  configured: false,
  lastAttemptAt: 0,
  lastDisplayName: "",
  lastStatus: "",
  lastSuccessAt: 0,
  lastTrigger: "",
  localTargetEligible: false,
  precisePermission: false,
  trackingActive: false,
});

export const DEFAULT_BACKGROUND_WEATHER_PREFETCH = Object.freeze({
  available: false,
  city: "",
  lat: null,
  lon: null,
  payload: null,
  savedAt: 0,
  trigger: "",
});

export class BackgroundLocationError extends Error {
  constructor(code, options = {}) {
    super(code, options);
    this.name = "BackgroundLocationError";
    this.code = code;
  }
}

function normalizeTimestamp(value) {
  const timestamp = Number(value);
  return Number.isFinite(timestamp) && timestamp > 0 ? Math.trunc(timestamp) : 0;
}

function normalizeText(value, maxLength = 160) {
  return String(value || "").trim().slice(0, maxLength);
}

export function normalizeBackgroundLocationStatus(payload = {}) {
  return {
    available: payload?.available === true,
    backgroundPermission: payload?.backgroundPermission === true,
    configured: payload?.configured === true,
    lastAttemptAt: normalizeTimestamp(payload?.lastAttemptAt),
    lastDisplayName: normalizeText(payload?.lastDisplayName),
    lastStatus: normalizeText(payload?.lastStatus, 80),
    lastSuccessAt: normalizeTimestamp(payload?.lastSuccessAt),
    lastTrigger: normalizeText(payload?.lastTrigger, 40),
    localTargetEligible: payload?.localTargetEligible === true,
    precisePermission: payload?.precisePermission === true,
    trackingActive: payload?.trackingActive === true,
  };
}

function normalizeCoordinate(value, min, max) {
  const coordinate = Number(value);
  return Number.isFinite(coordinate) && coordinate >= min && coordinate <= max
    ? coordinate
    : null;
}

export function normalizeBackgroundWeatherPrefetch(payload = {}) {
  const weatherPayload = payload?.payload;
  const hasWeather = Boolean(weatherPayload?.current && weatherPayload?.forecast);

  return {
    available: payload?.available === true && hasWeather,
    city: normalizeText(payload?.city),
    lat: normalizeCoordinate(payload?.lat, -90, 90),
    lon: normalizeCoordinate(payload?.lon, -180, 180),
    payload: hasWeather ? weatherPayload : null,
    savedAt: normalizeTimestamp(payload?.savedAt),
    trigger: normalizeText(payload?.trigger, 40),
  };
}

function getAvailablePlugin({ capacitor = Capacitor, plugin = MeteoBackgroundLocation } = {}) {
  if (!isAndroidCapacitorRuntime(capacitor)) return null;
  if (!capacitor?.isPluginAvailable?.(BACKGROUND_LOCATION_PLUGIN_NAME)) return null;
  return plugin;
}

export async function configureBackgroundLocation({
  capacitor = Capacitor,
  disclosureAccepted = false,
  enabled,
  installationId,
  plugin = MeteoBackgroundLocation,
} = {}) {
  const nativePlugin = getAvailablePlugin({ capacitor, plugin });
  if (!nativePlugin?.configure) return DEFAULT_BACKGROUND_LOCATION_STATUS;
  const configurationEnabled = Boolean(enabled && disclosureAccepted);
  if (configurationEnabled && !isValidPushInstallationId(installationId)) {
    throw new BackgroundLocationError("background_location_installation_id_invalid");
  }

  try {
    return normalizeBackgroundLocationStatus(await nativePlugin.configure({
      disclosureAccepted: Boolean(disclosureAccepted),
      enabled: configurationEnabled,
      installationId: configurationEnabled ? String(installationId).trim().toLowerCase() : "",
    }));
  } catch (error) {
    throw new BackgroundLocationError("background_location_configure_failed", { cause: error });
  }
}

export async function readBackgroundLocationStatus({
  capacitor = Capacitor,
  plugin = MeteoBackgroundLocation,
} = {}) {
  const nativePlugin = getAvailablePlugin({ capacitor, plugin });
  if (!nativePlugin?.getStatus) return DEFAULT_BACKGROUND_LOCATION_STATUS;

  try {
    return normalizeBackgroundLocationStatus(await nativePlugin.getStatus());
  } catch (error) {
    throw new BackgroundLocationError("background_location_status_failed", { cause: error });
  }
}

export async function readBackgroundWeatherPrefetch({
  capacitor = Capacitor,
  plugin = MeteoBackgroundLocation,
} = {}) {
  const nativePlugin = getAvailablePlugin({ capacitor, plugin });
  if (!nativePlugin?.getWeatherPrefetch) return DEFAULT_BACKGROUND_WEATHER_PREFETCH;

  try {
    return normalizeBackgroundWeatherPrefetch(await nativePlugin.getWeatherPrefetch());
  } catch {
    return DEFAULT_BACKGROUND_WEATHER_PREFETCH;
  }
}

export async function openBackgroundLocationSettings({
  capacitor = Capacitor,
  plugin = MeteoBackgroundLocation,
} = {}) {
  const nativePlugin = getAvailablePlugin({ capacitor, plugin });
  if (!nativePlugin?.openSettings) {
    throw new BackgroundLocationError("background_location_settings_unavailable");
  }

  try {
    await nativePlugin.openSettings();
  } catch (error) {
    throw new BackgroundLocationError("background_location_settings_failed", { cause: error });
  }
}

export async function refreshBackgroundLocation({
  capacitor = Capacitor,
  plugin = MeteoBackgroundLocation,
} = {}) {
  const nativePlugin = getAvailablePlugin({ capacitor, plugin });
  if (!nativePlugin?.refreshNow) {
    throw new BackgroundLocationError("background_location_refresh_unavailable");
  }

  try {
    return normalizeBackgroundLocationStatus(await nativePlugin.refreshNow());
  } catch (error) {
    throw new BackgroundLocationError("background_location_refresh_failed", { cause: error });
  }
}
