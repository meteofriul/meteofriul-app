import { describe, expect, it, vi } from "vitest";

import {
  configureBackgroundLocation,
  DEFAULT_BACKGROUND_WEATHER_PREFETCH,
  DEFAULT_BACKGROUND_LOCATION_STATUS,
  normalizeBackgroundWeatherPrefetch,
  normalizeBackgroundLocationStatus,
  openBackgroundLocationSettings,
  readBackgroundLocationStatus,
  readBackgroundWeatherPrefetch,
  refreshBackgroundLocation,
} from "./backgroundLocationAdapter";

const ANDROID_CAPACITOR = {
  getPlatform: () => "android",
  isNativePlatform: () => true,
  isPluginAvailable: () => true,
};

describe("backgroundLocationAdapter", () => {
  it("normalizes only bounded, non-sensitive status fields", () => {
    expect(normalizeBackgroundLocationStatus({
      available: true,
      backgroundPermission: true,
      configured: true,
      lastAttemptAt: 1234.8,
      lastDisplayName: " Vigonovo ",
      lastStatus: "resolved",
      lastSuccessAt: 1220,
      lastTrigger: "geofence_exit",
      localTargetEligible: true,
      precisePermission: true,
      trackingActive: true,
      lat: 45.99,
      lon: 12.55,
    })).toEqual({
      available: true,
      backgroundPermission: true,
      configured: true,
      lastAttemptAt: 1234,
      lastDisplayName: "Vigonovo",
      lastStatus: "resolved",
      lastSuccessAt: 1220,
      lastTrigger: "geofence_exit",
      localTargetEligible: true,
      precisePermission: true,
      trackingActive: true,
    });
  });

  it("configures the Android plugin with the existing installation id", async () => {
    const plugin = {
      configure: vi.fn().mockResolvedValue({ available: true, configured: true }),
    };
    const result = await configureBackgroundLocation({
      capacitor: ANDROID_CAPACITOR,
      disclosureAccepted: true,
      enabled: true,
      installationId: "0123456789abcdef0123456789abcdef",
      plugin,
    });

    expect(plugin.configure).toHaveBeenCalledWith({
      disclosureAccepted: true,
      enabled: true,
      installationId: "0123456789abcdef0123456789abcdef",
    });
    expect(result.configured).toBe(true);
  });

  it("disables an upgraded native configuration until disclosure consent is recorded", async () => {
    const plugin = {
      configure: vi.fn().mockResolvedValue({ available: true, configured: false }),
    };

    const result = await configureBackgroundLocation({
      capacitor: ANDROID_CAPACITOR,
      disclosureAccepted: false,
      enabled: true,
      installationId: "0123456789abcdef0123456789abcdef",
      plugin,
    });

    expect(plugin.configure).toHaveBeenCalledWith({
      disclosureAccepted: false,
      enabled: false,
      installationId: "",
    });
    expect(result.configured).toBe(false);
  });

  it("preserves recorded consent when collection is disabled for another prerequisite", async () => {
    const plugin = {
      configure: vi.fn().mockResolvedValue({ available: true, configured: false }),
    };

    await configureBackgroundLocation({
      capacitor: ANDROID_CAPACITOR,
      disclosureAccepted: true,
      enabled: false,
      plugin,
    });

    expect(plugin.configure).toHaveBeenCalledWith({
      disclosureAccepted: true,
      enabled: false,
      installationId: "",
    });
  });

  it("normalizes a complete native weather prefetch", () => {
    const payload = { current: { temperature: 18 }, forecast: { daily: [] } };

    expect(normalizeBackgroundWeatherPrefetch({
      available: true,
      city: " Pordenone ",
      lat: 45.9567,
      lon: 12.6605,
      payload,
      savedAt: 1234.8,
      trigger: "periodic",
    })).toEqual({
      available: true,
      city: "Pordenone",
      lat: 45.9567,
      lon: 12.6605,
      payload,
      savedAt: 1234,
      trigger: "periodic",
    });
  });

  it("is inert outside native Android", async () => {
    const plugin = { configure: vi.fn() };
    const result = await configureBackgroundLocation({
      capacitor: { isNativePlatform: () => false },
      enabled: false,
      plugin,
    });

    expect(result).toEqual(DEFAULT_BACKGROUND_LOCATION_STATUS);
    expect(plugin.configure).not.toHaveBeenCalled();
  });

  it("reads status and exposes settings/manual refresh", async () => {
    const plugin = {
      getStatus: vi.fn().mockResolvedValue({ available: true, trackingActive: true }),
      openSettings: vi.fn().mockResolvedValue(undefined),
      refreshNow: vi.fn().mockResolvedValue({ available: true, lastStatus: "resolved" }),
    };

    expect((await readBackgroundLocationStatus({
      capacitor: ANDROID_CAPACITOR,
      plugin,
    })).trackingActive).toBe(true);
    await openBackgroundLocationSettings({ capacitor: ANDROID_CAPACITOR, plugin });
    expect((await refreshBackgroundLocation({
      capacitor: ANDROID_CAPACITOR,
      plugin,
    })).lastStatus).toBe("resolved");
    expect(plugin.openSettings).toHaveBeenCalledTimes(1);
    expect(plugin.refreshNow).toHaveBeenCalledTimes(1);
  });

  it("reads native weather prefetch and is inert when unavailable", async () => {
    const payload = { current: {}, forecast: {} };
    const plugin = {
      getWeatherPrefetch: vi.fn().mockResolvedValue({
        available: true,
        city: "Pordenone",
        lat: 45.9567,
        lon: 12.6605,
        payload,
        savedAt: 1000,
      }),
    };

    expect(await readBackgroundWeatherPrefetch({
      capacitor: ANDROID_CAPACITOR,
      plugin,
    })).toMatchObject({ available: true, payload, savedAt: 1000 });
    expect(await readBackgroundWeatherPrefetch({
      capacitor: { isNativePlatform: () => false },
      plugin,
    })).toEqual(DEFAULT_BACKGROUND_WEATHER_PREFETCH);
  });
});
