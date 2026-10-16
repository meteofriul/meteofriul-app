import { describe, expect, it, vi } from "vitest";

import {
  applyNativeSystemBarsTheme,
  NATIVE_SYSTEM_BARS_PLUGIN_NAME,
} from "./nativeSystemBars";

function createCapacitor({ android = true, pluginAvailable = true } = {}) {
  return {
    getPlatform: () => (android ? "android" : "web"),
    isNativePlatform: () => android,
    isPluginAvailable: (name) => pluginAvailable && name === NATIVE_SYSTEM_BARS_PLUGIN_NAME,
  };
}

describe("native system bars", () => {
  it("does nothing outside the native Android runtime", async () => {
    const apply = vi.fn();

    await expect(applyNativeSystemBarsTheme({
      capacitor: createCapacitor({ android: false }),
      systemBarsPlugin: { apply },
      theme: "dark",
    })).resolves.toBe(false);
    expect(apply).not.toHaveBeenCalled();
  });

  it("applies the resolved light or dark theme on Android", async () => {
    const apply = vi.fn().mockResolvedValue(undefined);
    const capacitor = createCapacitor();

    await expect(applyNativeSystemBarsTheme({
      capacitor,
      systemBarsPlugin: { apply },
      theme: "dark",
    })).resolves.toBe(true);
    await expect(applyNativeSystemBarsTheme({
      capacitor,
      systemBarsPlugin: { apply },
      theme: "unexpected",
    })).resolves.toBe(true);

    expect(apply).toHaveBeenNthCalledWith(1, { theme: "dark" });
    expect(apply).toHaveBeenNthCalledWith(2, { theme: "light" });
  });

  it("fails closed when the plugin is unavailable or rejects", async () => {
    const unavailablePlugin = { apply: vi.fn() };
    await expect(applyNativeSystemBarsTheme({
      capacitor: createCapacitor({ pluginAvailable: false }),
      systemBarsPlugin: unavailablePlugin,
      theme: "light",
    })).resolves.toBe(false);
    expect(unavailablePlugin.apply).not.toHaveBeenCalled();

    await expect(applyNativeSystemBarsTheme({
      capacitor: createCapacitor(),
      systemBarsPlugin: { apply: vi.fn().mockRejectedValue(new Error("native failure")) },
      theme: "light",
    })).resolves.toBe(false);
  });
});
