import { afterEach, describe, expect, it, vi } from "vitest";

import * as localWeatherPilot from "./localWeatherPilot";
import { WeatherProviderPolicyError } from "./weatherProviderPolicy";
import {
  CURRENT_APP_WEATHER_PROVIDER_CONFIG,
  PRODUCTION_WEATHER_V1_BASE_URL,
  isLocalWeatherPilotLocation,
  resolveWeatherHttpApiBase,
  resolveWeatherRequestPolicy,
  resolveWeatherV1RequestBaseUrl,
  usesAutonomousWeatherProvider,
} from "./weatherProviderRuntime";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("weather provider runtime", () => {
  it("keeps the current app on the official autonomous configuration", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);

    expect(CURRENT_APP_WEATHER_PROVIDER_CONFIG).toEqual({
      primary: "autonomous",
      operatorOverride: null,
    });
    expect(resolveWeatherRequestPolicy()).toMatchObject({
      primary: "autonomous",
      fallback: null,
      automaticFallback: false,
      selectionReason: "configured_autonomous",
    });
    expect(usesAutonomousWeatherProvider()).toBe(true);
  });

  it("selects autonomous only from a complete explicit production configuration", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);

    const policy = resolveWeatherRequestPolicy({
      configuredPrimary: "autonomous",
      configuredOperatorOverride: undefined,
    });
    expect(policy).toMatchObject({
      primary: "autonomous",
      fallback: null,
      automaticFallback: false,
      onPrimaryError: "surface_error",
      localPilot: false,
    });
    expect(resolveWeatherV1RequestBaseUrl(policy, {
      configuredBaseUrl: "https://weather.example.test/data/",
    })).toBe("https://weather.example.test/data");
  });

  it("fails closed for partial Open-Meteo configuration and defaults to the official autonomous base", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);

    expect(() => resolveWeatherRequestPolicy({
      configuredPrimary: "open_meteo",
      configuredOperatorOverride: undefined,
    })).toThrow("weather_provider_open_meteo_requires_operator_override");

    const autonomous = resolveWeatherRequestPolicy({
      providerConfig: { primary: "autonomous" },
    });
    expect(resolveWeatherV1RequestBaseUrl(autonomous, {
      configuredBaseUrl: undefined,
    })).toBe(PRODUCTION_WEATHER_V1_BASE_URL);
    expect(() => resolveWeatherV1RequestBaseUrl(autonomous, {
      configuredBaseUrl: null,
    })).toThrow("weather_provider_v1_base_url_required");
    expect(() => resolveWeatherV1RequestBaseUrl(autonomous, {
      configuredBaseUrl: " https://weather.example.test",
    })).toThrow("weather_provider_v1_base_url_invalid");
  });

  it("forces the local pilot to autonomous and rejects an Open-Meteo injection", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);

    const policy = resolveWeatherRequestPolicy();
    expect(policy).toMatchObject({
      primary: "autonomous",
      fallback: null,
      automaticFallback: false,
      localPilot: true,
      selectionReason: "local_pilot_forced_autonomous",
    });
    expect(resolveWeatherV1RequestBaseUrl(policy, {
      configuredBaseUrl: "https://must-not-be-used.example.test",
    })).toBe("/__local-weather-pilot");

    expect(() => resolveWeatherRequestPolicy({
      providerConfig: {
        primary: "open_meteo",
        operatorOverride: "open_meteo",
      },
    })).toThrowError(expect.objectContaining({
      name: "WeatherProviderPolicyError",
      code: "weather_provider_local_pilot_open_meteo_forbidden",
    }));
  });

  it("keeps explicit FVG locations autonomous and rejects Roma without an ICON-2I national catalog", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const udine = {
      city: "Udine",
      countryCode: "IT",
      region: "Friuli Venezia Giulia",
      regionCode: "IT-36",
    };
    const roma = {
      city: "Roma",
      countryCode: "IT",
      region: "Lazio",
      regionCode: "IT-62",
    };

    expect(isLocalWeatherPilotLocation(udine)).toBe(true);
    expect(resolveWeatherRequestPolicy({ location: udine })).toMatchObject({
      primary: "autonomous",
      localPilot: true,
    });
    expect(resolveWeatherHttpApiBase(udine, {
      configuredApiBase: "https://ordinary.example/api",
    })).toBe("/__local-weather-pilot");

    expect(() => isLocalWeatherPilotLocation(roma)).toThrowError(
      expect.objectContaining({ code: "weather_provider_location_not_enabled" }),
    );
    expect(() => resolveWeatherRequestPolicy({ location: roma })).toThrowError(
      expect.objectContaining({ code: "weather_provider_location_not_enabled" }),
    );
    expect(() => resolveWeatherHttpApiBase(roma, {
      configuredApiBase: "https://ordinary.example/api",
    })).toThrowError(
      expect.objectContaining({ code: "weather_provider_location_not_enabled" }),
    );
    expect(() => resolveWeatherHttpApiBase(roma, {
      apiBase: "https://injected.example/api",
    })).toThrowError(
      expect.objectContaining({ code: "weather_provider_location_not_enabled" }),
    );
  });

  it("admits explicit Italian locations only when the national pilot is guarded on", () => {
    const roma = {
      city: "Roma", countryCode: "IT", region: "Lazio", regionCode: "IT-62",
    };

    expect(isLocalWeatherPilotLocation(roma, {
      localPilot: true,
      nationalPilot: true,
    })).toBe(true);
    expect(resolveWeatherRequestPolicy({
      location: roma,
      localPilot: true,
      nationalPilot: true,
    })).toMatchObject({ primary: "autonomous", localPilot: true });
  });

  it("rejects an explicitly foreign location instead of routing it to an Italian provider", () => {
    const location = {
      city: "Nova Gorica",
      countryCode: "SI",
      region: "Gorizia",
      regionCode: "SI-044",
    };

    expect(() => resolveWeatherRequestPolicy({ location })).toThrowError(
      expect.objectContaining({ code: "weather_provider_location_unsupported" }),
    );
    expect(() => resolveWeatherHttpApiBase(location)).toThrowError(
      expect.objectContaining({ code: "weather_provider_location_unsupported" }),
    );
  });

  it("uses build-time configuration without consulting runtime health", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    vi.stubEnv("VITE_WEATHER_PROVIDER_PRIMARY", "autonomous");

    expect(usesAutonomousWeatherProvider()).toBe(true);
  });

  it("returns a typed policy error for a malformed base", () => {
    const policy = resolveWeatherRequestPolicy({
      localPilot: false,
      providerConfig: { primary: "autonomous" },
    });

    try {
      resolveWeatherV1RequestBaseUrl(policy, { configuredBaseUrl: "/weather?run=latest" });
      throw new Error("expected invalid base");
    } catch (error) {
      expect(error).toBeInstanceOf(WeatherProviderPolicyError);
      expect(error.code).toBe("weather_provider_v1_base_url_invalid");
    }
  });
});
