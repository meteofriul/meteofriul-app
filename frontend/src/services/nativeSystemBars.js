import { Capacitor, registerPlugin } from "@capacitor/core";

import { isAndroidCapacitorRuntime } from "./apiConfig";

export const NATIVE_SYSTEM_BARS_PLUGIN_NAME = "MeteoSystemBars";

const MeteoSystemBars = registerPlugin(NATIVE_SYSTEM_BARS_PLUGIN_NAME);

export async function applyNativeSystemBarsTheme({
  theme,
  capacitor = Capacitor,
  systemBarsPlugin = MeteoSystemBars,
} = {}) {
  if (!isAndroidCapacitorRuntime(capacitor)) return false;
  if (!capacitor?.isPluginAvailable?.(NATIVE_SYSTEM_BARS_PLUGIN_NAME)) return false;
  if (typeof systemBarsPlugin?.apply !== "function") return false;

  const normalizedTheme = theme === "dark" ? "dark" : "light";
  try {
    await systemBarsPlugin.apply({ theme: normalizedTheme });
    return true;
  } catch {
    return false;
  }
}
