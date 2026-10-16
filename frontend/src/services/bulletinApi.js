import { API_BASE } from "./apiConfig";
import { getLocationMunicipalityName } from "../domain/geo/locationIdentity";

function getLocationCity(location) {
  return getLocationMunicipalityName(location);
}

function parseCoordinate(value) {
  if (typeof value === "string") {
    return value.trim() === "" ? NaN : Number(value);
  }
  return typeof value === "number" ? value : NaN;
}

function buildLocationQuery(location) {
  const city = String(getLocationCity(location) || "").trim();

  if (!city) {
    throw new Error("Localita bollettino mancante");
  }

  const params = new URLSearchParams({ city });
  const lat = parseCoordinate(location?.lat);
  const lon = parseCoordinate(location?.lon);

  if (Number.isFinite(lat) && Number.isFinite(lon)) {
    params.set("lat", String(lat));
    params.set("lon", String(lon));
  }

  return params;
}

function appendForceToken(params, { force = false, now = Date.now } = {}) {
  if (!force) return params;

  const timestamp = typeof now === "function" ? now() : now;
  params.set("_", String(timestamp));
  return params;
}

export function buildBulletinForecastUrl(
  location,
  { apiBase = API_BASE, force = false, now = Date.now } = {},
) {
  const base = String(apiBase || "").replace(/\/$/, "");
  const params = appendForceToken(buildLocationQuery(location), { force, now });

  return `${base}/weather/forecast?${params.toString()}`;
}

export function buildOfficialAlertsUrl(
  { apiBase = API_BASE, force = false, now = Date.now } = {},
) {
  const base = String(apiBase || "").replace(/\/$/, "");
  const params = appendForceToken(new URLSearchParams(), { force, now });
  const query = params.toString();

  return `${base}/weather/official-alerts${query ? `?${query}` : ""}`;
}

export async function fetchOfficialAlertsPayload(
  {
    apiBase = API_BASE,
    fetchImpl = globalThis.fetch,
    force = false,
    now = Date.now,
  } = {},
) {
  if (typeof fetchImpl !== "function") {
    throw new Error("Fetch non disponibile");
  }

  const response = await fetchImpl(
    buildOfficialAlertsUrl({ apiBase, force, now }),
    { cache: force ? "no-store" : "default" },
  );

  if (!response?.ok) {
    throw new Error("Risposta allerte ufficiali non valida");
  }

  const payload = await response.json();
  if (!payload || (typeof payload !== "object" && !Array.isArray(payload))) {
    throw new Error("Dati allerte ufficiali mancanti");
  }

  return payload;
}

export async function fetchBulletinPayload(
  location,
  {
    apiBase = API_BASE,
    fetchImpl = globalThis.fetch,
    force = false,
    includeAlerts = true,
    now = Date.now,
  } = {},
) {
  if (typeof fetchImpl !== "function") {
    throw new Error("Fetch non disponibile");
  }

  const forecastUrl = buildBulletinForecastUrl(location, { apiBase, force, now });
  const requestOptions = { cache: force ? "no-store" : "default" };
  const alertsPromise = includeAlerts
    ? fetchOfficialAlertsPayload({
        apiBase,
        fetchImpl,
        force,
        now,
      }).catch(() => null)
    : Promise.resolve(null);
  const forecastResponse = await fetchImpl(forecastUrl, requestOptions);

  if (!forecastResponse?.ok) {
    await alertsPromise;
    throw new Error("Risposta bollettino OSMER non valida");
  }

  const forecast = await forecastResponse.json();
  if (!forecast || typeof forecast !== "object") {
    await alertsPromise;
    throw new Error("Dati bollettino OSMER mancanti");
  }

  return {
    city: String(getLocationCity(location) || forecast.city || "").trim(),
    forecast,
    officialAlerts: await alertsPromise,
    raw: {
      forecast,
    },
  };
}
