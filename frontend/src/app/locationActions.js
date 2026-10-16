export function refreshDeviceLocation(resolveDeviceLocation) {
  if (typeof resolveDeviceLocation !== "function") {
    return Promise.resolve({ ok: false, reason: "location_resolver_unavailable" });
  }

  return resolveDeviceLocation({ markLoading: true });
}

export const MANUAL_LOCATION_WEATHER_TIMEOUT_MS = 8000;

function createLocationWeatherError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function loadWeatherWithTimeout(loadWeather, location, timeoutMs) {
  return new Promise((resolve, reject) => {
    const timeoutId = globalThis.setTimeout(() => {
      reject(createLocationWeatherError(
        "LOCATION_WEATHER_TIMEOUT",
        "Tempo esaurito durante il caricamento meteo della localita",
      ));
    }, timeoutMs);

    Promise.resolve()
      .then(() => loadWeather(location, { deferCams: true }))
      .then(resolve, reject)
      .finally(() => globalThis.clearTimeout(timeoutId));
  });
}

function hasRequiredLocationWeather(weather) {
  return Boolean(weather?.current && weather?.forecast);
}

export async function prepareManualLocationChange(
  location,
  {
    loadWeather,
    readWeather,
    timeoutMs = MANUAL_LOCATION_WEATHER_TIMEOUT_MS,
  } = {},
) {
  if (typeof loadWeather !== "function") {
    throw createLocationWeatherError(
      "LOCATION_WEATHER_LOADER_UNAVAILABLE",
      "Caricamento meteo della localita non disponibile",
    );
  }
  if (readWeather !== undefined && typeof readWeather !== "function") {
    throw createLocationWeatherError(
      "LOCATION_WEATHER_READER_INVALID",
      "Lettura cache meteo della localita non valida",
    );
  }
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 60_000) {
    throw createLocationWeatherError(
      "LOCATION_WEATHER_TIMEOUT_INVALID",
      "Timeout caricamento meteo della localita non valido",
    );
  }

  const cachedWeather = (() => {
    try {
      return readWeather?.(location) || null;
    } catch {
      return null;
    }
  })();
  if (hasRequiredLocationWeather(cachedWeather)) return cachedWeather;

  const weather = await loadWeatherWithTimeout(loadWeather, location, timeoutMs);
  if (!hasRequiredLocationWeather(weather)) {
    if (weather?.error instanceof Error) throw weather.error;
    if (typeof weather?.error === "string" && weather.error.trim()) {
      throw createLocationWeatherError(
        "LOCATION_WEATHER_UNAVAILABLE",
        weather.error.trim(),
      );
    }
    throw createLocationWeatherError(
      "LOCATION_WEATHER_UNAVAILABLE",
      "Dati ICON della localita non disponibili",
    );
  }

  return weather;
}

export async function runManualLocationChange(
  location,
  {
    commitLocation,
    disableAutomaticLocation,
    immediate = false,
    ...weatherOptions
  } = {},
) {
  if (typeof commitLocation !== "function") {
    throw createLocationWeatherError(
      "LOCATION_COMMIT_UNAVAILABLE",
      "Cambio localita non disponibile",
    );
  }

  if (immediate) {
    disableAutomaticLocation?.();
    const committed = commitLocation(location);
    // The loader writes its location-keyed cache. Never commit again when
    // this request completes: the user may already have selected another town.
    void prepareManualLocationChange(location, weatherOptions).catch(() => {});
    return committed;
  }
  const weather = await prepareManualLocationChange(location, weatherOptions);
  disableAutomaticLocation?.();
  return commitLocation(location, weather);
}

export function changeAutomaticLocationMode(
  enabled,
  {
    disableAutomaticLocation,
    resolveDeviceLocation,
  } = {},
) {
  if (!enabled) {
    disableAutomaticLocation?.();
    return Promise.resolve({ enabled: false, ok: true });
  }

  return refreshDeviceLocation(resolveDeviceLocation);
}
