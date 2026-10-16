import { API_BASE } from "./apiConfig";
import {
  FIREBASE_APP_CHECK_HEADER,
  getFirebaseAppCheckToken,
} from "./firebaseAppCheckAdapter";
import {
  getLocationLocality,
  getLocationMunicipality,
} from "../domain/geo/locationIdentity";
import { getTerritoryKind, isFvgLocation } from "../domain/scope/productScope";
import { isLocalWeatherPilot } from "./localWeatherPilot";

export const PUSH_INSTALLATION_ID_STORAGE_KEY = "mfPushInstallationId:v1";
export const PUSH_DEVICE_REQUEST_TIMEOUT_MS = 12_000;
export const PUSH_LOCATION_EVIDENCE_MAX_ACCURACY_M = 250;
export const PUSH_LOCATION_EVIDENCE_MAX_AGE_MS = 10 * 60 * 1000;
export const PUSH_LOCATION_EVIDENCE_FUTURE_SKEW_MS = 2 * 60 * 1000;

export class PushDeviceRegistrationError extends Error {
  constructor(code, options = {}) {
    super(code, options);
    this.name = "PushDeviceRegistrationError";
    this.code = code;
    this.serverCode = normalizeText(options.serverCode).toLowerCase() || null;
    this.status = Number.isFinite(Number(options.status)) ? Number(options.status) : null;
  }
}

function normalizeText(value) {
  return String(value || "").trim();
}

function normalizeLanguage(value) {
  return String(value || "").trim().toLowerCase() === "fur" ? "fur" : "it";
}

export function isValidPushInstallationId(value) {
  return /^[a-f0-9]{32}$/.test(normalizeText(value).toLowerCase());
}

export function isValidFirebaseInstallationId(value) {
  return /^[cdef][A-Za-z0-9_-]{21}$/.test(normalizeText(value));
}

export function createPushInstallationId({ cryptoLike = globalThis.crypto } = {}) {
  if (typeof cryptoLike?.getRandomValues !== "function") {
    throw new PushDeviceRegistrationError("push_installation_random_unavailable");
  }

  const bytes = cryptoLike.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function readOrCreatePushInstallationId({
  cryptoLike = globalThis.crypto,
  storage = globalThis.window?.localStorage,
} = {}) {
  if (typeof storage?.getItem !== "function" || typeof storage?.setItem !== "function") {
    throw new PushDeviceRegistrationError("push_installation_storage_unavailable");
  }

  let stored;
  try {
    stored = normalizeText(storage?.getItem?.(PUSH_INSTALLATION_ID_STORAGE_KEY)).toLowerCase();
  } catch {
    stored = null;
  }
  if (isValidPushInstallationId(stored)) return stored;

  const installationId = createPushInstallationId({ cryptoLike });
  try {
    storage?.setItem?.(PUSH_INSTALLATION_ID_STORAGE_KEY, installationId);
  } catch {
    throw new PushDeviceRegistrationError("push_installation_storage_failed");
  }
  return installationId;
}

export function readPushInstallationId({
  storage = globalThis.window?.localStorage,
} = {}) {
  if (typeof storage?.getItem !== "function") return "";

  try {
    const stored = normalizeText(storage.getItem(PUSH_INSTALLATION_ID_STORAGE_KEY)).toLowerCase();
    return isValidPushInstallationId(stored) ? stored : "";
  } catch {
    return "";
  }
}

export function toPushRegistrationMunicipality(location) {
  if (normalizeText(location?.source).toLowerCase() === "placeholder") return null;
  if (!isFvgLocation(location)) return null;

  const municipality = getLocationMunicipality(location);
  const istat = normalizeText(municipality?.istatCode || location?.istatCode || location?.istat);
  const name = normalizeText(municipality?.name || location?.city || location?.name);

  return istat && name ? { istat, name } : null;
}

export function toPushRegistrationNationalManualMunicipality(location) {
  const source = normalizeText(location?.source).toLowerCase();
  if (
    !["manual", "manual_recent"].includes(source)
    || isFvgLocation(location)
    || getTerritoryKind(location) !== "italy"
  ) return null;

  const municipality = getLocationMunicipality(location);
  const istat = normalizeText(municipality?.istatCode);
  const name = normalizeText(municipality?.name);
  // The server checks the exact ISTAT/name pair against its versioned catalog.
  // A city-only or GPS-derived guess must never become a push subscription.
  return /^\d{6}$/u.test(istat) && name && name === normalizeText(location?.city)
    ? { istat, name }
    : null;
}

export function toPushRegistrationLocality(location) {
  if (normalizeText(location?.source).toLowerCase() === "placeholder") return null;
  if (!isFvgLocation(location)) return null;
  if (location?.resolution?.localityCorroborated !== true) return null;

  const locality = getLocationLocality(location);
  const id = normalizeText(locality?.id);
  const name = normalizeText(locality?.name);

  return id && name ? { id, name } : null;
}

export function toPushRegistrationLocationEvidence(
  location,
  { now = Date.now } = {},
) {
  const source = normalizeText(location?.source).toLowerCase();
  const isGpsSource = source === "browser_geolocation"
    || source === "capacitor_geolocation"
    || source.startsWith("android_");
  const hasCoordinates = location?.lat != null
    && location?.lat !== ""
    && location?.lon != null
    && location?.lon !== "";
  const hasAccuracy = location?.positionAccuracyM != null
    && location?.positionAccuracyM !== "";
  const lat = Number(location?.lat);
  const lon = Number(location?.lon);
  const accuracyM = Number(location?.positionAccuracyM);
  const capturedAt = new Date(location?.positionCapturedAt || "");
  const currentTime = Number(typeof now === "function" ? now() : now);
  const evidenceAgeMs = currentTime - capturedAt.getTime();

  if (
    !isGpsSource
    || !hasCoordinates
    || !Number.isFinite(lat)
    || lat < -90
    || lat > 90
    || !Number.isFinite(lon)
    || lon < -180
    || lon > 180
    || !hasAccuracy
    || !Number.isFinite(accuracyM)
    || accuracyM < 0
    || accuracyM > PUSH_LOCATION_EVIDENCE_MAX_ACCURACY_M
    || Number.isNaN(capturedAt.getTime())
    || !Number.isFinite(currentTime)
    || evidenceAgeMs > PUSH_LOCATION_EVIDENCE_MAX_AGE_MS
    || evidenceAgeMs < -PUSH_LOCATION_EVIDENCE_FUTURE_SKEW_MS
  ) {
    return null;
  }

  return {
    captured_at: capturedAt.toISOString(),
    accuracy_m: accuracyM,
  };
}

export function toPushRegistrationLocationMode(location, options = {}) {
  if (
    toPushRegistrationLocationEvidence(location, options)
    && toPushRegistrationMunicipality(location)
  ) return "automatic_gps";

  const source = normalizeText(location?.source).toLowerCase();
  const isManualSelection = source === "manual" || source === "manual_recent";

  return isManualSelection
    && toPushRegistrationMunicipality(location)
    ? "manual_selection"
    : null;
}

export function resolvePushRegistrationPreferences(
  preferences,
  {
    localPilot = isLocalWeatherPilot(),
    officialAlertsEligible = true,
  } = {},
) {
  return {
    official_alerts: officialAlertsEligible && preferences?.officialAlerts !== false,
    // The deterministic ICON pilot has no calibrated precipitation
    // probability. Keep official alerts independent, but never enroll this
    // side-by-side test app in the predictive local-notice channel.
    weather_notices: localPilot ? false : preferences?.weatherNotices !== false,
  };
}

function buildApiUrl(apiBase, path) {
  return `${String(apiBase || API_BASE).replace(/\/$/, "")}${path}`;
}

async function readResponsePayload(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function readResponseErrorCode(payload) {
  return normalizeText(payload?.detail?.code || payload?.code).toLowerCase();
}

async function postPushDevice({
  apiBase = API_BASE,
  body,
  fetchImpl = globalThis.fetch,
  path,
  tokenProvider = getFirebaseAppCheckToken,
  timeoutMs = PUSH_DEVICE_REQUEST_TIMEOUT_MS,
}) {
  if (typeof fetchImpl !== "function") {
    throw new PushDeviceRegistrationError("push_fetch_unavailable");
  }

  for (let attempt = 0; attempt < 2; attempt += 1) {
    const appCheckToken = normalizeText(await tokenProvider({ forceRefresh: attempt > 0 }));
    if (!appCheckToken) {
      throw new PushDeviceRegistrationError("push_app_check_token_missing");
    }

    let response;
    const abortController = new AbortController();
    const timeoutId = globalThis.setTimeout?.(
      () => abortController.abort(),
      Math.max(1, Number(timeoutMs) || PUSH_DEVICE_REQUEST_TIMEOUT_MS),
    );
    try {
      response = await fetchImpl(buildApiUrl(apiBase, path), {
        body: JSON.stringify(body),
        headers: {
          "Content-Type": "application/json",
          [FIREBASE_APP_CHECK_HEADER]: appCheckToken,
        },
        method: "POST",
        signal: abortController.signal,
      });
    } catch (error) {
      throw new PushDeviceRegistrationError("push_device_network_failed", { cause: error });
    } finally {
      if (timeoutId != null) globalThis.clearTimeout?.(timeoutId);
    }

    const payload = await readResponsePayload(response);
    const serverCode = readResponseErrorCode(payload);
    // A stale App Check token is refreshable; a 403 is an authorization or
    // enrollment-policy decision and retrying it cannot change the outcome.
    if (response.status === 401 && attempt === 0) continue;

    if (!response.ok) {
      throw new PushDeviceRegistrationError(`push_device_http_${response.status}`, {
        serverCode,
        status: response.status,
      });
    }

    return payload || {};
  }

  throw new PushDeviceRegistrationError("push_device_registration_failed");
}

export async function registerPushDevice({
  activeLocation,
  apiBase = API_BASE,
  appVersion,
  fetchImpl = globalThis.fetch,
  installationId,
  language,
  localPilot = isLocalWeatherPilot(),
  notificationPreferences,
  now = Date.now,
  platform = "android",
  registration,
  token,
  tokenProvider = getFirebaseAppCheckToken,
} = {}) {
  const normalizedInstallationId = normalizeText(installationId).toLowerCase();
  const normalizedPlatform = normalizeText(platform).toLowerCase() === "web" ? "web" : "android";
  const normalizedToken = normalizeText(token);

  if (!isValidPushInstallationId(normalizedInstallationId)) {
    throw new PushDeviceRegistrationError("push_installation_id_invalid");
  }
  if (normalizedPlatform === "android" && !normalizedToken) {
    throw new PushDeviceRegistrationError("push_token_missing");
  }

  const normalizedRegistration = normalizedPlatform === "web"
    ? {
        kind: normalizeText(registration?.kind).toLowerCase(),
        value: normalizeText(registration?.value),
      }
    : null;
  if (
    normalizedPlatform === "web" &&
    (
      normalizedRegistration.kind !== "firebase_installation_id" ||
      !isValidFirebaseInstallationId(normalizedRegistration.value)
    )
  ) {
    throw new PushDeviceRegistrationError("push_registration_invalid");
  }

  const fvgMunicipality = toPushRegistrationMunicipality(activeLocation);
  const nationalManualMunicipality = normalizedPlatform === "android"
    ? toPushRegistrationNationalManualMunicipality(activeLocation)
    : null;
  const selectedOfficialAlerts = nationalManualMunicipality
    ? notificationPreferences?.nationalOfficialAlerts === true
    : notificationPreferences?.officialAlerts !== false;
  const commonBody = {
    installation_id: normalizedInstallationId,
    platform: normalizedPlatform,
    app_version: normalizeText(appVersion) || "unknown",
    language: normalizeLanguage(language),
    municipality: fvgMunicipality || nationalManualMunicipality,
    locality: toPushRegistrationLocality(activeLocation),
    ...(() => {
      const nativeLocationMode = nationalManualMunicipality
        ? "manual_selection"
        : toPushRegistrationLocationMode(activeLocation, { now });
      // A PWA has no reliable native background-location lease. Persist its
      // canonical active municipality as an explicit selection instead of
      // claiming that a browser GPS fix will still be fresh when the job runs.
      const locationMode = normalizedPlatform === "web"
        ? (fvgMunicipality ? "manual_selection" : null)
        : nativeLocationMode;
      return {
        location_evidence: locationMode === "automatic_gps"
          ? toPushRegistrationLocationEvidence(activeLocation, { now })
          : null,
        location_mode: locationMode,
      };
    })(),
    preferences: resolvePushRegistrationPreferences({
      ...notificationPreferences,
      officialAlerts: selectedOfficialAlerts,
    }, {
      localPilot,
      officialAlertsEligible: Boolean(fvgMunicipality || nationalManualMunicipality),
    }),
  };

  return postPushDevice({
    apiBase,
    body: normalizedPlatform === "web"
      ? { ...commonBody, registration: normalizedRegistration }
      : { ...commonBody, token: normalizedToken },
    fetchImpl,
    path: "/push/devices/register",
    tokenProvider,
  });
}

export async function unregisterPushDevice({
  apiBase = API_BASE,
  fetchImpl = globalThis.fetch,
  installationId,
  tokenProvider = getFirebaseAppCheckToken,
} = {}) {
  const normalizedInstallationId = normalizeText(installationId).toLowerCase();
  if (!isValidPushInstallationId(normalizedInstallationId)) {
    throw new PushDeviceRegistrationError("push_installation_id_invalid");
  }

  return postPushDevice({
    apiBase,
    body: { installation_id: normalizedInstallationId },
    fetchImpl,
    path: "/push/devices/unregister",
    tokenProvider,
  });
}
