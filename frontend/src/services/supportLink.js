import { AppLauncher } from "@capacitor/app-launcher";
import { Capacitor } from "@capacitor/core";

import { isAndroidCapacitorRuntime } from "./apiConfig";

export const DEFAULT_SUPPORT_URL = "https://ko-fi.com/meteofriul";

export function getConfiguredSupportUrl(
  configuredValue = import.meta.env.VITE_SUPPORT_URL,
) {
  return normalizeSupportUrl(configuredValue || DEFAULT_SUPPORT_URL);
}

export function normalizeSupportUrl(value) {
  try {
    const url = new URL(String(value || "").trim());
    const hostname = url.hostname.toLowerCase();
    const isKoFiHost = hostname === "ko-fi.com" || hostname === "www.ko-fi.com";

    return url.protocol === "https:" && isKoFiHost ? url.href : null;
  } catch {
    return null;
  }
}

export async function openSupportUrl(
  value,
  {
    appLauncher = AppLauncher,
    capacitor = Capacitor,
    windowLike = globalThis.window,
  } = {},
) {
  const url = normalizeSupportUrl(value);
  if (!url) return { ok: false, reason: "invalid_support_url" };

  if (isAndroidCapacitorRuntime(capacitor)) {
    if (typeof appLauncher?.openUrl !== "function") {
      return { ok: false, reason: "external_launcher_unavailable" };
    }

    try {
      const result = await appLauncher.openUrl({ url });
      return {
        ok: result?.completed !== false,
        mode: "android_external",
        reason: result?.completed === false ? "external_launcher_rejected" : undefined,
      };
    } catch (error) {
      return {
        ok: false,
        error: error?.message || "external_launcher_failed",
        reason: "external_launcher_failed",
      };
    }
  }

  const opened = windowLike?.open?.(url, "_blank", "noopener,noreferrer");
  return {
    ok: opened !== null,
    mode: "web_external",
    reason: opened === null ? "popup_blocked" : undefined,
  };
}
