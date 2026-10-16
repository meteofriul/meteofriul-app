import { getLocationMunicipalityName } from "../domain/geo/locationIdentity";
import { getTerritoryKind } from "../domain/scope/productScope";
import {
  getLocalWeatherNationalApiBase,
  getLocalWeatherPilotNow,
  getLocalWeatherPilotTestNow,
  isLocalWeatherNationalPilot,
} from "./localWeatherPilot";
import {
  fetchNationalWeatherV2Bootstrap,
  readNationalWeatherV2PersistedBundle,
} from "./nationalWeatherV2Adapter";
import { fetchLocalWeatherV1Bootstrap } from "./localWeatherV1Adapter";
import {
  enrichNationalWeatherV2WithCams,
  readNationalWeatherV2CamsBundle,
} from "./nationalWeatherV2Cams";
import {
  fetchLocalWeatherV1RuntimeBundle,
  readLocalWeatherV1PersistedBundle,
} from "./localWeatherV1Runtime";
import { WEATHER_PROVIDERS } from "./weatherProviderPolicy";
import {
  isLocalWeatherPilotLocation,
  resolveWeatherHttpApiBase,
  resolveWeatherRequestPolicy,
  resolveWeatherV1RequestBaseUrl,
} from "./weatherProviderRuntime";

function optionalLocalStorage(storage) {
  if (storage !== undefined) return storage;
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function usesNationalWeatherV2(location) {
  if (!location || typeof location !== "object" || Array.isArray(location)) return false;
  const territory = getTerritoryKind(location);
  if (isLocalWeatherNationalPilot()) return territory === "fvg" || territory === "italy";
  return territory === "italy";
}

export function buildWeatherBootstrapUrl(
  location,
  {
    apiBase,
    force = false,
    now = Date.now,
  } = {},
) {
  const city = getLocationMunicipalityName(location);
  const trimmedCity = String(city || "").trim();

  if (!trimmedCity) {
    throw new Error("Localita meteo mancante");
  }

  const base = String(resolveWeatherHttpApiBase(location, { apiBase })).replace(/\/$/, "");
  let url = `${base}/weather/bootstrap?city=${encodeURIComponent(trimmedCity)}`;
  const lat = typeof location === "object" ? location?.lat : null;
  const lon = typeof location === "object" ? location?.lon : null;

  if (lat && lon) {
    url += `&lat=${lat}&lon=${lon}`;
  }

  if (force) {
    const timestamp = typeof now === "function" ? now() : now;
    url += `${url.includes("?") ? "&" : "?"}_=${timestamp}`;
  }

  return url;
}

export function normalizeWeatherBootstrapPayload(
  payload,
  { fallbackCity, requireCompleteCurrent = true } = {},
) {
  const current = payload?.current || null;
  const forecast = payload?.forecast || null;

  if (!current || !forecast) {
    throw new Error("Dati meteo mancanti");
  }

  if (
    requireCompleteCurrent &&
    current.temperature == null &&
    current.weathercode == null &&
    current.wind_speed == null
  ) {
    throw new Error("Dati meteo incompleti");
  }

  return {
    city: payload?.city || fallbackCity || current.city || "",
    current,
    forecast,
    officialAlerts: payload?.official_alerts || null,
    osmerAudit: payload?.osmer_audit || null,
    raw: payload,
  };
}

export function readWeatherBootstrapCache(
  location,
  {
    now = Date.now,
    requireCompleteCurrent = true,
    runtimeBundleReader = readLocalWeatherV1PersistedBundle,
    storage,
    providerConfig,
    weatherV1BaseUrl,
    nationalBaseUrl = getLocalWeatherNationalApiBase(),
    nationalBundleReader = readNationalWeatherV2PersistedBundle,
    verificationNow,
    verifyWindowMs,
  } = {},
) {
  try {
    const fallbackCity = getLocationMunicipalityName(location);
    const providerPolicy = resolveWeatherRequestPolicy({ location, providerConfig });
    if (providerPolicy.primary !== WEATHER_PROVIDERS.AUTONOMOUS) return null;
    const weatherModelNow = getLocalWeatherPilotTestNow()
      ? getLocalWeatherPilotNow
      : now;
    if (usesNationalWeatherV2(location)) {
      const payload = nationalBundleReader(location, {
        baseUrl: nationalBaseUrl,
        now: weatherModelNow,
        storage: optionalLocalStorage(storage),
      });
      if (!payload) return null;
      const enriched = readNationalWeatherV2CamsBundle(payload, {
        baseUrl: resolveWeatherV1RequestBaseUrl(providerPolicy, { configuredBaseUrl: weatherV1BaseUrl }),
        now: weatherModelNow,
        ...(verificationNow === undefined ? {} : { verificationNow }),
        ...(verifyWindowMs === undefined ? {} : { verifyWindowMs }),
      });
      return normalizeWeatherBootstrapPayload(enriched, {
        fallbackCity,
        requireCompleteCurrent,
      });
    }
    const payload = runtimeBundleReader(location, {
      baseUrl: resolveWeatherV1RequestBaseUrl(providerPolicy, {
        configuredBaseUrl: weatherV1BaseUrl,
      }),
      now: weatherModelNow,
      storage: optionalLocalStorage(storage),
    });
    if (!payload) return null;
    return normalizeWeatherBootstrapPayload(payload, {
      fallbackCity,
      requireCompleteCurrent,
    });
  } catch {
    return null;
  }
}

export async function fetchWeatherBootstrap(
  location,
  {
    apiBase,
    fetchImpl = globalThis.fetch,
    force = false,
    now = Date.now,
    requireCompleteCurrent = true,
    storage,
    weatherV1Fetcher = fetchLocalWeatherV1Bootstrap,
    deferCams = false,
    retryUnavailableCams = false,
    onCamsUpdate,
    onCamsFailure,
    providerConfig,
    verificationNow,
    verifyWindowMs,
    weatherV1BaseUrl,
    nationalBaseUrl = getLocalWeatherNationalApiBase(),
    nationalFetcher = fetchNationalWeatherV2Bootstrap,
    nationalCamsFetcher,
  } = {},
) {
  if (typeof fetchImpl !== "function") {
    throw new Error("Fetch non disponibile");
  }

  const fallbackCity = getLocationMunicipalityName(location);
  const providerPolicy = resolveWeatherRequestPolicy({ location, providerConfig });
  if (providerPolicy.primary === WEATHER_PROVIDERS.AUTONOMOUS) {
    if (usesNationalWeatherV2(location)) {
      const weatherModelNow = getLocalWeatherPilotTestNow()
        ? getLocalWeatherPilotNow
        : now;
      const payload = await nationalFetcher(location, {
        baseUrl: nationalBaseUrl,
        fetchImpl,
        force,
        now: weatherModelNow,
        storage: optionalLocalStorage(storage),
      });
      const enriched = await enrichNationalWeatherV2WithCams(payload, {
        baseUrl: resolveWeatherV1RequestBaseUrl(providerPolicy, { configuredBaseUrl: weatherV1BaseUrl }),
        fetchImpl, force, now: weatherModelNow, storage: optionalLocalStorage(storage), deferCams, retryUnavailableCams,
        ...(nationalCamsFetcher === undefined ? {} : { camsFetcher: nationalCamsFetcher }),
        ...(verificationNow === undefined ? {} : { verificationNow }),
        ...(verifyWindowMs === undefined ? {} : { verifyWindowMs }),
        ...(onCamsUpdate === undefined ? {} : { onCamsUpdate: typeof onCamsUpdate === "function"
          ? (bundle, lifecycle) => onCamsUpdate(normalizeWeatherBootstrapPayload(bundle, { fallbackCity, requireCompleteCurrent }), lifecycle)
          : onCamsUpdate }),
        ...(onCamsFailure === undefined ? {} : { onCamsFailure }),
      });
      return normalizeWeatherBootstrapPayload(enriched, {
        fallbackCity,
        requireCompleteCurrent,
      });
    }
    if (typeof deferCams !== "boolean") {
      throw new Error("Modalita CAMS weather v1 locale non valida");
    }
    if (onCamsUpdate !== undefined && typeof onCamsUpdate !== "function") {
      throw new Error("Callback CAMS weather v1 locale non valida");
    }
    if (onCamsFailure !== undefined && typeof onCamsFailure !== "function") {
      throw new Error("Callback errore CAMS weather v1 locale non valida");
    }
    const handleCamsUpdate = typeof onCamsUpdate === "function"
      ? (bundle) => onCamsUpdate(normalizeWeatherBootstrapPayload(bundle, {
        fallbackCity,
        requireCompleteCurrent,
      }))
      : undefined;
    const weatherModelNow = getLocalWeatherPilotTestNow()
      ? getLocalWeatherPilotNow
      : now;
    const payload = await fetchLocalWeatherV1RuntimeBundle(location, {
      baseUrl: resolveWeatherV1RequestBaseUrl(providerPolicy, {
        configuredBaseUrl: weatherV1BaseUrl,
      }),
      bundleFetcher: weatherV1Fetcher,
      fetchImpl,
      force,
      retryUnavailableCams,
      now: weatherModelNow,
      storage: optionalLocalStorage(storage),
      ...(verificationNow === undefined ? {} : { verificationNow }),
      ...(verifyWindowMs === undefined ? {} : { verifyWindowMs }),
      ...(deferCams ? {
        deferCams: true,
        ...(handleCamsUpdate ? { onCamsUpdate: handleCamsUpdate } : {}),
        ...(onCamsFailure ? { onCamsFailure } : {}),
      } : {}),
    });
    return normalizeWeatherBootstrapPayload(payload, {
      fallbackCity,
      requireCompleteCurrent,
    });
  }

  const url = buildWeatherBootstrapUrl(location, { apiBase, force, now });
  const response = await fetchImpl(url, {
    cache: force || isLocalWeatherPilotLocation(location) ? "no-store" : "default",
  });

  if (!response?.ok) {
    throw new Error("Risposta meteo non valida");
  }

  const payload = await response.json();
  return normalizeWeatherBootstrapPayload(payload, {
    fallbackCity,
    requireCompleteCurrent,
  });
}
