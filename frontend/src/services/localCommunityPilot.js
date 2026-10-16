import { isLocalWeatherPilot } from "./localWeatherPilot";
import { ANDROID_LOOPBACK_ONLY_BUILD } from "./localOnlyBuild";

const BROWSER_BASE = "/__local-community/api";
const ANDROID_BASE = "http://127.0.0.1:8783/api";
export const PRODUCTION_COMMUNITY_API_BASE = ANDROID_LOOPBACK_ONLY_BUILD ? "" : "https://meteofriul-community-49007668366.europe-west1.run.app/api";
// Kept as a compatibility export for protected local-pilot build tooling.
// Cloud Community now always uses the official public service.
export const CLOUD_COMMUNITY_PILOT_API_BASE = PRODUCTION_COMMUNITY_API_BASE;
export const LOCAL_COMMUNITY_PILOT_HEADER = "X-Meteo-Pilot-Community";

export function isLocalCommunityDevelopmentRuntime() {
  const base = import.meta.env.VITE_LOCAL_COMMUNITY_PILOT_API_BASE;
  return isLocalWeatherPilot()
    && import.meta.env.VITE_LOCAL_COMMUNITY_PILOT_ENABLED === "1"
    && (import.meta.env.MODE === "local-pilot" && base === BROWSER_BASE
      || import.meta.env.MODE === "android-local-pilot" && base === ANDROID_BASE);
}

// The v2 national contract has graduated to the official application. The
// historical function name remains as a compatibility seam for UI code.
export function isLocalCommunityPilot() {
  return isLocalCommunityDevelopmentRuntime()
    || import.meta.env.VITE_COMMUNITY_V2_ENABLED === "1"
    || import.meta.env.PROD === true;
}

export function getLocalCommunityPilotApiBase() {
  if (isLocalCommunityDevelopmentRuntime()) {
    return import.meta.env.VITE_LOCAL_COMMUNITY_PILOT_API_BASE;
  }
  if (ANDROID_LOOPBACK_ONLY_BUILD) throw new Error("local_community_runtime_required");
  return String(import.meta.env.VITE_COMMUNITY_API_BASE || PRODUCTION_COMMUNITY_API_BASE).replace(/\/+$/, "");
}

export function communityStorageKey(key) {
  if (isLocalCommunityDevelopmentRuntime()) return `localCommunityPilot:v1:${key}`;
  return `communityV2:v1:${key}`;
}

// The selected place determines what is read. Only fresh GPS determines where
// a report may be submitted; this scope is never used as submission evidence.
export function getLocalCommunityReadScope(location) {
  if (!isLocalCommunityPilot()) return "";
  const code = String(location?.istatCode || location?.municipality?.istatCode || "");
  if (/^\d{6}$/.test(code)) return `istat_code=${code}&radius_km=30`;
  const lat = location?.lat;
  const lon = location?.lon;
  if (typeof lat === "number" && typeof lon === "number"
    && Number.isFinite(lat) && Number.isFinite(lon)
    && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
    return `lat=${lat.toFixed(4)}&lon=${lon.toFixed(4)}&radius_km=30`;
  }
  if (!location) return "";
  throw new Error("Località non riconosciuta per le segnalazioni.");
}
