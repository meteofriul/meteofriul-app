import {
  getLocalWeatherPilotApiBase,
  isLocalWeatherNationalPilot,
  isLocalWeatherPilot,
} from "./localWeatherPilot";
import { API_BASE } from "./apiConfig";
import { ANDROID_LOOPBACK_ONLY_BUILD } from "./localOnlyBuild";
import { getTerritoryKind, isFvgLocation } from "../domain/scope/productScope";
import {
  WEATHER_PROVIDERS,
  WeatherProviderPolicyError,
  resolveWeatherProviderPolicy,
} from "./weatherProviderPolicy";

export const PRODUCTION_WEATHER_V1_BASE_URL = ANDROID_LOOPBACK_ONLY_BUILD ? "" : "https://meteofriul-weather-49007668366.europe-west1.run.app";

// ICON/CAMS is the only weather provider in the official application. An
// explicit build variable may still repeat this choice, but cannot silently
// restore the retired Open-Meteo runtime.
export const CURRENT_APP_WEATHER_PROVIDER_CONFIG = Object.freeze({
  primary: WEATHER_PROVIDERS.AUTONOMOUS,
  operatorOverride: null,
});

function configuredProviderInput(primary, operatorOverride) {
  if (primary === undefined && operatorOverride === undefined) {
    return CURRENT_APP_WEATHER_PROVIDER_CONFIG;
  }
  return {
    primary,
    operatorOverride: operatorOverride === undefined ? null : operatorOverride,
  };
}

function hasExplicitTerritoryIdentity(location) {
  if (!location || typeof location !== "object" || Array.isArray(location)) return false;

  return [
    location.countryCode,
    location.country_code,
    location.country,
    location.regionCode,
    location.region_code,
    location.region,
    location.admin1,
    location.state,
    location.province,
    location.istatCode,
    location.istat_code,
    location.municipality?.province,
    location.municipality?.istatCode,
  ].some((value) => String(value || "").trim());
}

function assertSupportedWeatherTerritory(location) {
  if (!hasExplicitTerritoryIdentity(location)) return;
  if (["fvg", "italy"].includes(getTerritoryKind(location))) return;
  throw new WeatherProviderPolicyError("weather_provider_location_unsupported");
}

/**
 * The ordinary autonomous pilot contains only the FVG catalog. The separately
 * guarded national-v2 capability expands it to explicit Italian locations;
 * foreign identities still fail before any transport is selected.
 */
export function isLocalWeatherPilotLocation(
  location,
  {
    localPilot = isLocalWeatherPilot(),
    nationalPilot = isLocalWeatherNationalPilot(),
  } = {},
) {
  if (!localPilot) return false;
  if (!hasExplicitTerritoryIdentity(location)) return true;
  assertSupportedWeatherTerritory(location);
  if (!isFvgLocation(location) && !nationalPilot) {
    throw new WeatherProviderPolicyError("weather_provider_location_not_enabled");
  }
  return true;
}

/**
 * Bind the pure provider policy to build-time/operator configuration.
 *
 * The local pilot and official app are autonomous. Supplying either build
 * variable opts into strict validation, so a partial or misspelled legacy
 * override fails closed.
 */
export function resolveWeatherRequestPolicy({
  localPilot = isLocalWeatherPilot(),
  nationalPilot = isLocalWeatherNationalPilot(),
  location,
  providerConfig,
  configuredPrimary = import.meta.env.VITE_WEATHER_PROVIDER_PRIMARY,
  configuredOperatorOverride = import.meta.env.VITE_WEATHER_PROVIDER_OPERATOR_OVERRIDE,
} = {}) {
  assertSupportedWeatherTerritory(location);
  if (localPilot) {
    isLocalWeatherPilotLocation(location, { localPilot, nationalPilot });
    if (providerConfig === undefined) {
      return resolveWeatherProviderPolicy({
        primary: WEATHER_PROVIDERS.AUTONOMOUS,
        localPilot: true,
      });
    }

    const requested = resolveWeatherProviderPolicy(providerConfig);
    return resolveWeatherProviderPolicy({
      primary: requested.primary,
      operatorOverride: requested.operatorOverride,
      localPilot: true,
    });
  }

  return resolveWeatherProviderPolicy(
    providerConfig === undefined
      ? configuredProviderInput(configuredPrimary, configuredOperatorOverride)
      : providerConfig,
  );
}

export function usesAutonomousWeatherProvider(options) {
  return resolveWeatherRequestPolicy(options).primary === WEATHER_PROVIDERS.AUTONOMOUS;
}

/**
 * Resolve only the transport base; provider selection remains an independent,
 * fail-closed decision. The autonomous pilot has no ordinary-weather escape
 * hatch: unsupported territory identities are rejected before a URL can be
 * built.
 */
export function resolveWeatherHttpApiBase(
  location,
  {
    apiBase,
    configuredApiBase = API_BASE,
    localPilot = isLocalWeatherPilot(),
    localPilotBaseUrl = getLocalWeatherPilotApiBase(),
  } = {},
) {
  assertSupportedWeatherTerritory(location);
  const locationPilot = isLocalWeatherPilotLocation(location, { localPilot });
  if (apiBase !== undefined) return apiBase;
  if (locationPilot) return localPilotBaseUrl;
  return configuredApiBase;
}

export function resolveWeatherV1RequestBaseUrl(
  policy,
  {
    configuredBaseUrl = import.meta.env.VITE_WEATHER_V1_BASE_URL || PRODUCTION_WEATHER_V1_BASE_URL,
    localPilotBaseUrl = getLocalWeatherPilotApiBase(),
  } = {},
) {
  if (policy?.primary !== WEATHER_PROVIDERS.AUTONOMOUS) return null;

  const candidate = policy.localPilot ? localPilotBaseUrl : configuredBaseUrl;
  if (typeof candidate !== "string") {
    throw new WeatherProviderPolicyError("weather_provider_v1_base_url_required");
  }
  const result = candidate.replace(/\/+$/, "");
  const hasControl = Array.from(result).some((character) => character.charCodeAt(0) < 0x20);
  if (
    !result ||
    result.trim() !== result ||
    result.includes("?") ||
    result.includes("#") ||
    result.includes("\\") ||
    hasControl
  ) {
    throw new WeatherProviderPolicyError("weather_provider_v1_base_url_invalid");
  }
  return result;
}
