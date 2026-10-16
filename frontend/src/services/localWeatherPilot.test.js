import { afterEach, describe, expect, it, vi } from "vitest";

import * as apiConfig from "./apiConfig";
import { buildBulletinForecastUrl, buildOfficialAlertsUrl } from "./bulletinApi";
import {
  getLocalWeatherPilotApiBase,
  getLocalWeatherNationalApiBase,
  getLocalWeatherPilotNow,
  getLocalWeatherPilotTestNow,
  isDefinitiveAppExperience,
  isLocalWeatherPilot,
  isLocalWeatherNationalPilot,
  isOfficialAppRelease,
  PRODUCTION_NATIONAL_WEATHER_API_BASE,
  resolveLocalWeatherPilot,
} from "./localWeatherPilot";

const enabled = {
  androidBuildFlag: "0",
  dev: true,
  mode: "local-pilot",
  flag: "1",
  hostname: "127.0.0.1",
  nativeAndroid: false,
};

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("local weather pilot opt-in", () => {
  it("separates the definitive official experience from the protected pilot runtime", () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("MODE", "android");
    vi.stubEnv("VITE_DEFINITIVE_APP_EXPERIENCE", "1");
    vi.stubEnv("VITE_OFFICIAL_APP_RELEASE", "1");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT", "0");
    vi.stubEnv("VITE_ANDROID_LOCAL_WEATHER_PILOT", "0");
    vi.stubGlobal("location", { hostname: "localhost" });
    vi.spyOn(apiConfig, "isAndroidCapacitorRuntime").mockReturnValue(true);

    expect(isDefinitiveAppExperience()).toBe(true);
    expect(isOfficialAppRelease()).toBe(true);
    expect(isLocalWeatherPilot()).toBe(false);
  });

  it("defaults to disabled and requires every explicit guard", () => {
    expect(resolveLocalWeatherPilot()).toBe(false);
    expect(resolveLocalWeatherPilot(enabled)).toBe(true);
    for (const missing of Object.keys(enabled)) {
      const candidate = { ...enabled };
      delete candidate[missing];
      expect(resolveLocalWeatherPilot(candidate), missing).toBe(false);
    }
  });

  it.each([
    { dev: false }, { dev: "true" }, { mode: "development" }, { mode: "production" },
    { mode: "android" }, { mode: "cloudflare" }, { flag: "0" }, { flag: true },
    { flag: "true" }, { nativeAndroid: true }, { hostname: "meteofriul.app" },
    { hostname: "127.0.0.1.evil.invalid" }, { hostname: "192.168.1.10" },
    { hostname: "0.0.0.0" }, { hostname: "" },
  ])("rejects an unsafe or incomplete runtime: %j", (override) => {
    expect(resolveLocalWeatherPilot({ ...enabled, ...override })).toBe(false);
  });

  it("accepts only the fully bound native Android local-pilot build", () => {
    const android = {
      androidBuildFlag: "1",
      dev: false,
      flag: "1",
      hostname: "localhost",
      mode: "android-local-pilot",
      nativeAndroid: true,
    };
    expect(resolveLocalWeatherPilot(android)).toBe(true);

    for (const missing of Object.keys(android)) {
      const candidate = { ...android };
      delete candidate[missing];
      expect(resolveLocalWeatherPilot(candidate), missing).toBe(false);
    }
    expect(resolveLocalWeatherPilot({ ...android, hostname: "127.0.0.1" })).toBe(true);
    expect(resolveLocalWeatherPilot({ ...android, nativeAndroid: false })).toBe(false);
    expect(resolveLocalWeatherPilot({ ...android, dev: true })).toBe(false);
  });

  it.each(["127.0.0.1", "localhost", "[::1]", "::1"])("accepts explicit loopback %s", (hostname) => {
    expect(resolveLocalWeatherPilot({ ...enabled, hostname })).toBe(true);
  });

  it("accepts the guarded browser cloud-reader mode on loopback", () => {
    expect(resolveLocalWeatherPilot({
      ...enabled,
      mode: "local-pilot-cloud",
    })).toBe(true);
    expect(resolveLocalWeatherPilot({
      ...enabled,
      mode: "local-pilot-cloud",
      hostname: "meteofriul.app",
    })).toBe(false);
  });

  it("reads runtime flags dynamically without persisting a user preference", () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("MODE", "local-pilot");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT", "1");
    vi.stubEnv("VITE_ANDROID_LOCAL_WEATHER_PILOT", "0");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT_API_BASE", "/__local-weather-pilot");
    vi.stubEnv("VITE_LOCAL_WEATHER_NATIONAL_ENABLED", "1");
    vi.stubEnv("VITE_LOCAL_WEATHER_NATIONAL_API_BASE", "/__local-weather-national");
    vi.stubGlobal("location", { hostname: "127.0.0.1" });
    vi.spyOn(apiConfig, "isAndroidCapacitorRuntime").mockReturnValue(false);
    const storage = { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn() };
    vi.stubGlobal("localStorage", storage);

    expect(isLocalWeatherPilot()).toBe(true);
    expect(isLocalWeatherNationalPilot()).toBe(true);
    expect(getLocalWeatherNationalApiBase()).toBe("/__local-weather-national");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT", "0");
    expect(isLocalWeatherPilot()).toBe(false);
    expect(isLocalWeatherNationalPilot()).toBe(false);
    expect(getLocalWeatherNationalApiBase()).toBe(PRODUCTION_NATIONAL_WEATHER_API_BASE);
    expect(storage.getItem).not.toHaveBeenCalled();
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

  it("recognizes the guarded cloud reader from the actual Vite runtime flags", () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("MODE", "local-pilot-cloud");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT", "1");
    vi.stubEnv("VITE_ANDROID_LOCAL_WEATHER_PILOT", "0");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT_API_BASE", "/__local-weather-pilot");
    vi.stubGlobal("location", { hostname: "127.0.0.1" });
    vi.spyOn(apiConfig, "isAndroidCapacitorRuntime").mockReturnValue(false);

    expect(isLocalWeatherPilot()).toBe(true);
    expect(getLocalWeatherPilotApiBase()).toBe("/__local-weather-pilot");
    expect(isLocalWeatherNationalPilot()).toBe(false);
  });

  it("keeps native official routes on API_BASE while weather v1 uses adb loopback", () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("MODE", "android-local-pilot");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT", "1");
    vi.stubEnv("VITE_ANDROID_LOCAL_WEATHER_PILOT", "1");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT_API_BASE", "http://127.0.0.1:8781");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT_NOW", "2026-09-04T05:00:00Z");
    vi.stubGlobal("location", { hostname: "localhost" });
    vi.spyOn(apiConfig, "isAndroidCapacitorRuntime").mockReturnValue(true);

    expect(isLocalWeatherPilot()).toBe(true);
    expect(getLocalWeatherPilotApiBase()).toBe("http://127.0.0.1:8781");
    expect(getLocalWeatherPilotTestNow()).toBe("2026-09-04T05:00:00Z");
    expect(getLocalWeatherPilotNow()).toBe(Date.parse("2026-09-04T05:00:00Z"));
    expect(buildBulletinForecastUrl("Udine")).toBe(`${apiConfig.API_BASE}/weather/forecast?city=Udine`);
    expect(buildOfficialAlertsUrl()).toBe(`${apiConfig.API_BASE}/weather/official-alerts`);
    expect(buildOfficialAlertsUrl()).not.toContain("127.0.0.1:8781");
  });

  it("ignores a fixed clock when the guarded pilot is disabled", () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("MODE", "production");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT", "0");
    vi.stubEnv("VITE_ANDROID_LOCAL_WEATHER_PILOT", "0");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT_NOW", "2026-09-04T05:00:00Z");
    vi.stubGlobal("location", { hostname: "meteofriul.app" });
    vi.spyOn(apiConfig, "isAndroidCapacitorRuntime").mockReturnValue(false);
    vi.spyOn(Date, "now").mockReturnValue(123456);

    expect(getLocalWeatherPilotTestNow()).toBeNull();
    expect(getLocalWeatherPilotNow()).toBe(123456);
  });

  it("never redirects official bulletin or alerts even with the pilot enabled", () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("MODE", "local-pilot");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT", "1");
    vi.stubEnv("VITE_ANDROID_LOCAL_WEATHER_PILOT", "0");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT_API_BASE", "/__local-weather-pilot");
    vi.stubGlobal("location", { hostname: "127.0.0.1" });
    vi.spyOn(apiConfig, "isAndroidCapacitorRuntime").mockReturnValue(false);

    expect(isLocalWeatherPilot()).toBe(true);
    expect(getLocalWeatherPilotApiBase()).toBe("/__local-weather-pilot");
    expect(buildBulletinForecastUrl("Udine")).toBe(`${apiConfig.API_BASE}/weather/forecast?city=Udine`);
    expect(buildOfficialAlertsUrl()).toBe(`${apiConfig.API_BASE}/weather/official-alerts`);
  });
});
