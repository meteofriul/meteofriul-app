import { Capacitor } from "@capacitor/core";

export const DEFAULT_WEB_API_BASE = "/api";

export function isAndroidCapacitorRuntime(capacitor = Capacitor) {
  try {
    return Boolean(
      capacitor?.isNativePlatform?.() &&
      String(capacitor?.getPlatform?.() || "").trim().toLowerCase() === "android"
    );
  } catch {
    return false;
  }
}

export function normalizeAndroidApiBase(value) {
  const candidate = String(value || "").trim();

  let url;
  try {
    url = new URL(candidate);
  } catch {
    throw new Error("android_api_base_must_be_absolute_https");
  }

  if (
    url.protocol !== "https:" ||
    !url.hostname ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  ) {
    throw new Error("android_api_base_must_be_absolute_https");
  }

  return url.href.replace(/\/$/, "");
}

export function resolveApiBase({
  androidApiBase,
  configuredApiBase,
  nativeAndroid = isAndroidCapacitorRuntime(),
} = {}) {
  if (nativeAndroid) {
    return normalizeAndroidApiBase(
      androidApiBase || configuredApiBase,
    );
  }

  return String(configuredApiBase || DEFAULT_WEB_API_BASE).trim() || DEFAULT_WEB_API_BASE;
}

export const API_BASE = resolveApiBase({
  androidApiBase: import.meta.env.VITE_ANDROID_API_BASE,
  configuredApiBase: import.meta.env.VITE_API_BASE,
});
