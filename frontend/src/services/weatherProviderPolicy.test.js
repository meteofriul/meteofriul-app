import { afterEach, describe, expect, it, vi } from "vitest";

import {
  WEATHER_PROVIDERS,
  WeatherProviderPolicyError,
  resolveWeatherProviderPolicy,
} from "./weatherProviderPolicy";

function expectPolicyError(config, code) {
  try {
    resolveWeatherProviderPolicy(config);
    throw new Error("Expected weather provider policy to reject the configuration");
  } catch (error) {
    expect(error).toBeInstanceOf(WeatherProviderPolicyError);
    expect(error).toMatchObject({ name: "WeatherProviderPolicyError", code, message: code });
  }
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("weather provider policy", () => {
  it("selects autonomous with no fallback in the normal new-version configuration", () => {
    const config = Object.freeze({ primary: "autonomous" });
    const policy = resolveWeatherProviderPolicy(config);

    expect(policy).toEqual({
      primary: "autonomous",
      fallback: null,
      automaticFallback: false,
      onPrimaryError: "surface_error",
      operatorOverride: null,
      localPilot: false,
      selectionReason: "configured_autonomous",
    });
    expect(Object.isFrozen(policy)).toBe(true);
    expect(config).toEqual({ primary: "autonomous" });
    expect(WEATHER_PROVIDERS).toEqual({ AUTONOMOUS: "autonomous", OPEN_METEO: "open_meteo" });
  });

  it("allows Open-Meteo only when the final primary and explicit operator override agree", () => {
    expect(resolveWeatherProviderPolicy({
      primary: "open_meteo",
      operatorOverride: "open_meteo",
    })).toEqual({
      primary: "open_meteo",
      fallback: null,
      automaticFallback: false,
      onPrimaryError: "surface_error",
      operatorOverride: "open_meteo",
      localPilot: false,
      selectionReason: "operator_open_meteo_override",
    });

    for (const operatorOverride of [undefined, null]) {
      const config = { primary: "open_meteo" };
      if (operatorOverride !== undefined) config.operatorOverride = operatorOverride;
      expectPolicyError(config, "weather_provider_open_meteo_requires_operator_override");
    }
    expectPolicyError(
      { primary: "autonomous", operatorOverride: "open_meteo" },
      "weather_provider_override_requires_open_meteo_primary",
    );
  });

  it("forces autonomous in local-pilot and rejects every Open-Meteo override", () => {
    expect(resolveWeatherProviderPolicy({ primary: "autonomous", localPilot: true })).toMatchObject({
      primary: "autonomous",
      fallback: null,
      automaticFallback: false,
      operatorOverride: null,
      localPilot: true,
      selectionReason: "local_pilot_forced_autonomous",
    });

    for (const config of [
      { primary: "open_meteo", localPilot: true },
      { primary: "open_meteo", operatorOverride: "open_meteo", localPilot: true },
      { primary: "autonomous", operatorOverride: "open_meteo", localPilot: true },
    ]) {
      expectPolicyError(config, "weather_provider_local_pilot_open_meteo_forbidden");
    }
  });

  it("fails closed when configuration or primary is absent", () => {
    for (const config of [undefined, null]) {
      expectPolicyError(config, "weather_provider_config_required");
    }
    for (const config of [{}, { localPilot: true }, { operatorOverride: null }]) {
      expectPolicyError(config, "weather_provider_primary_required");
    }
  });

  it.each([
    ["icon", "weather_provider_primary_invalid"],
    ["OPEN_METEO", "weather_provider_primary_invalid"],
    [" open_meteo ", "weather_provider_primary_invalid"],
    ["", "weather_provider_primary_invalid"],
    [true, "weather_provider_primary_invalid"],
  ])("rejects unknown or coerced primary %j", (primary, code) => {
    expectPolicyError({ primary }, code);
  });

  it("rejects unknown keys, runtime health inputs and mistyped guards", () => {
    for (const config of [
      { primary: "autonomous", fallback: "open_meteo" },
      { primary: "autonomous", networkAvailable: false },
      { primary: "autonomous", primaryError: true },
    ]) {
      expectPolicyError(config, "weather_provider_config_unknown_key");
    }
    for (const localPilot of ["true", 1, null, undefined]) {
      expectPolicyError(
        { primary: "autonomous", localPilot },
        "weather_provider_local_pilot_invalid",
      );
    }
    for (const operatorOverride of [true, false, "autonomous", "OPEN_METEO", " open_meteo "]) {
      expectPolicyError(
        { primary: "autonomous", operatorOverride },
        "weather_provider_operator_override_invalid",
      );
    }
  });

  it("accepts only inert plain data and never invokes configuration accessors", () => {
    for (const config of ["autonomous", [], new Date(), Object.create({ primary: "autonomous" })]) {
      expectPolicyError(config, "weather_provider_config_must_be_plain_object");
    }

    const accessor = {};
    Object.defineProperty(accessor, "primary", {
      enumerable: true,
      get: vi.fn(() => "autonomous"),
    });
    expectPolicyError(accessor, "weather_provider_config_accessors_forbidden");
    expect(Object.getOwnPropertyDescriptor(accessor, "primary").get).not.toHaveBeenCalled();

    const symbolConfig = { primary: "autonomous" };
    symbolConfig[Symbol("hidden-runtime-input")] = true;
    expectPolicyError(symbolConfig, "weather_provider_config_unknown_key");

    const nullPrototypeConfig = Object.assign(Object.create(null), { primary: "autonomous" });
    expect(resolveWeatherProviderPolicy(nullPrototypeConfig).primary).toBe("autonomous");
  });

  it("is deterministic and never reads network, storage, clock or browser status", () => {
    const fetch = vi.fn();
    const storage = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    const now = vi.spyOn(Date, "now");
    vi.stubGlobal("fetch", fetch);
    vi.stubGlobal("localStorage", storage);
    vi.stubGlobal("navigator", {
      get onLine() {
        throw new Error("navigator.onLine must not be read");
      },
    });

    const config = { primary: "autonomous", operatorOverride: null, localPilot: false };
    expect(resolveWeatherProviderPolicy(config)).toEqual(resolveWeatherProviderPolicy(config));
    expect(fetch).not.toHaveBeenCalled();
    expect(storage.getItem).not.toHaveBeenCalled();
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.removeItem).not.toHaveBeenCalled();
    expect(now).not.toHaveBeenCalled();
  });
});
