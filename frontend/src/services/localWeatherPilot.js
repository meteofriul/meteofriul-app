import { isAndroidCapacitorRuntime } from "./apiConfig";

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]", "::1"]);
const DEV_LOCAL_WEATHER_PILOT_MODE = "local-pilot";
const DEV_CLOUD_WEATHER_PILOT_MODE = "local-pilot-cloud";
const DEV_LOCAL_WEATHER_PILOT_MODES = new Set([
  DEV_LOCAL_WEATHER_PILOT_MODE,
  DEV_CLOUD_WEATHER_PILOT_MODE,
]);
const ANDROID_LOCAL_WEATHER_PILOT_MODE = "android-local-pilot";
const CANONICAL_UTC_SECONDS = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/u;
export const PRODUCTION_NATIONAL_WEATHER_API_BASE = "https://meteofriul-national-weather-49007668366.europe-west1.run.app";

export function resolveLocalWeatherPilot({
  androidBuildFlag,
  dev,
  flag,
  hostname,
  mode,
  nativeAndroid,
} = {}) {
  const loopback = LOOPBACK_HOSTS.has(String(hostname || "").toLowerCase());
  const devPilot = dev === true
    && DEV_LOCAL_WEATHER_PILOT_MODES.has(mode)
    && flag === "1"
    && androidBuildFlag === "0"
    && nativeAndroid === false;
  const androidPilot = dev === false
    && mode === ANDROID_LOCAL_WEATHER_PILOT_MODE
    && flag === "1"
    && androidBuildFlag === "1"
    && nativeAndroid === true;

  return loopback && (devPilot || androidPilot);
}

export function isLocalWeatherPilot() {
  return resolveLocalWeatherPilot({
    androidBuildFlag: import.meta.env.VITE_ANDROID_LOCAL_WEATHER_PILOT,
    dev: import.meta.env.DEV,
    mode: import.meta.env.MODE,
    flag: import.meta.env.VITE_LOCAL_WEATHER_PILOT,
    hostname: globalThis.location?.hostname,
    nativeAndroid: isAndroidCapacitorRuntime(),
  });
}

export function isDefinitiveAppExperience() {
  return import.meta.env.VITE_DEFINITIVE_APP_EXPERIENCE === "1"
    || isLocalWeatherPilot();
}

export function isOfficialAppRelease() {
  return import.meta.env.VITE_OFFICIAL_APP_RELEASE === "1";
}

export function getLocalWeatherPilotApiBase() {
  return String(
    import.meta.env.VITE_LOCAL_WEATHER_PILOT_API_BASE || "/__local-weather-pilot",
  ).replace(/\/+$/, "");
}

export function isLocalWeatherNationalPilot() {
  return isLocalWeatherPilot()
    && import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_ENABLED === "1"
    && Boolean(String(import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_API_BASE || "").trim());
}

export function getLocalWeatherNationalApiBase() {
  if (isLocalWeatherNationalPilot()) {
    return String(import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_API_BASE).replace(/\/+$/, "");
  }
  return String(
    import.meta.env.VITE_NATIONAL_WEATHER_V2_BASE_URL || PRODUCTION_NATIONAL_WEATHER_API_BASE,
  ).replace(/\/+$/, "");
}

export function getLocalWeatherPilotTestNow() {
  if (!isLocalWeatherPilot()) return null;
  const candidate = String(import.meta.env.VITE_LOCAL_WEATHER_PILOT_NOW || "").trim();
  if (!CANONICAL_UTC_SECONDS.test(candidate)) return null;
  const milliseconds = Date.parse(candidate);
  if (
    !Number.isFinite(milliseconds)
    || new Date(milliseconds).toISOString().replace(".000Z", "Z") !== candidate
  ) return null;
  return candidate;
}

export function getLocalWeatherPilotNow() {
  const fixed = getLocalWeatherPilotTestNow();
  return fixed ? Date.parse(fixed) : Date.now();
}
