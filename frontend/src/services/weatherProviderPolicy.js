const AUTONOMOUS = "autonomous";
const OPEN_METEO = "open_meteo";
const OPEN_METEO_OPERATOR_OVERRIDE = OPEN_METEO;
const ALLOWED_KEYS = new Set(["primary", "operatorOverride", "localPilot"]);

export const WEATHER_PROVIDERS = Object.freeze({
  AUTONOMOUS,
  OPEN_METEO,
});

export class WeatherProviderPolicyError extends Error {
  constructor(code) {
    super(code);
    this.name = "WeatherProviderPolicyError";
    this.code = code;
  }
}

function fail(code) {
  throw new WeatherProviderPolicyError(code);
}

function readConfig(config) {
  if (config === undefined || config === null) fail("weather_provider_config_required");
  if (typeof config !== "object" || Array.isArray(config)) {
    fail("weather_provider_config_must_be_plain_object");
  }

  let prototype;
  let descriptors;
  try {
    prototype = Object.getPrototypeOf(config);
    descriptors = Object.getOwnPropertyDescriptors(config);
  } catch {
    fail("weather_provider_config_unreadable");
  }
  if (prototype !== Object.prototype && prototype !== null) {
    fail("weather_provider_config_must_be_plain_object");
  }

  const keys = Reflect.ownKeys(descriptors);
  if (keys.some((key) => typeof key !== "string" || !ALLOWED_KEYS.has(key))) {
    fail("weather_provider_config_unknown_key");
  }
  if (keys.some((key) => descriptors[key].get || descriptors[key].set)) {
    fail("weather_provider_config_accessors_forbidden");
  }

  return {
    hasPrimary: Object.hasOwn(descriptors, "primary"),
    primary: descriptors.primary?.value,
    operatorOverride: Object.hasOwn(descriptors, "operatorOverride")
      ? descriptors.operatorOverride.value
      : null,
    localPilot: Object.hasOwn(descriptors, "localPilot")
      ? descriptors.localPilot.value
      : false,
  };
}

/**
 * Resolve the numerical-weather provider for one app configuration.
 *
 * This function deliberately accepts no health, network, cache or error state.
 * A caller must surface an autonomous-provider failure; the returned policy
 * never authorizes an automatic retry through Open-Meteo.
 */
export function resolveWeatherProviderPolicy(config) {
  const {
    hasPrimary,
    primary,
    operatorOverride,
    localPilot,
  } = readConfig(config);

  if (!hasPrimary) fail("weather_provider_primary_required");
  if (primary !== AUTONOMOUS && primary !== OPEN_METEO) {
    fail("weather_provider_primary_invalid");
  }
  if (typeof localPilot !== "boolean") fail("weather_provider_local_pilot_invalid");
  if (operatorOverride !== null && operatorOverride !== OPEN_METEO_OPERATOR_OVERRIDE) {
    fail("weather_provider_operator_override_invalid");
  }

  if (localPilot) {
    if (primary !== AUTONOMOUS || operatorOverride !== null) {
      fail("weather_provider_local_pilot_open_meteo_forbidden");
    }
    return Object.freeze({
      primary: AUTONOMOUS,
      fallback: null,
      automaticFallback: false,
      onPrimaryError: "surface_error",
      operatorOverride: null,
      localPilot: true,
      selectionReason: "local_pilot_forced_autonomous",
    });
  }

  if (primary === OPEN_METEO && operatorOverride !== OPEN_METEO_OPERATOR_OVERRIDE) {
    fail("weather_provider_open_meteo_requires_operator_override");
  }
  if (primary === AUTONOMOUS && operatorOverride !== null) {
    fail("weather_provider_override_requires_open_meteo_primary");
  }

  return Object.freeze({
    primary,
    fallback: null,
    automaticFallback: false,
    onPrimaryError: "surface_error",
    operatorOverride,
    localPilot: false,
    selectionReason: primary === OPEN_METEO
      ? "operator_open_meteo_override"
      : "configured_autonomous",
  });
}
