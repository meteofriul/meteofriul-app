import { API_BASE } from "./apiConfig";
import { getLocationMunicipalityName } from "../domain/geo/locationIdentity";

function getLocationCity(location) {
  return getLocationMunicipalityName(location);
}

function buildLocationQuery(location) {
  const city = String(getLocationCity(location) || "").trim();

  if (!city) {
    throw new Error("Localita radar mancante");
  }

  const params = new URLSearchParams({ city });
  const lat = typeof location === "object" ? Number(location?.lat) : NaN;
  const lon = typeof location === "object" ? Number(location?.lon) : NaN;

  if (Number.isFinite(lat) && Number.isFinite(lon)) {
    params.set("lat", String(lat));
    params.set("lon", String(lon));
  }

  return params;
}

export function buildRadarUrl(
  location,
  { apiBase = API_BASE, force = false, now = Date.now } = {},
) {
  const base = String(apiBase || "").replace(/\/$/, "");
  const params = buildLocationQuery(location);

  if (force) {
    const timestamp = typeof now === "function" ? now() : now;
    params.set("_", String(timestamp));
  }

  return `${base}/weather/radar?${params.toString()}`;
}

export function normalizeRadarPayload(payload, { fallbackCity = "" } = {}) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Dati radar mancanti");
  }

  const products = Array.isArray(payload.products)
    ? payload.products.filter((product) => (
      product &&
      typeof product === "object" &&
      String(product.product_type || "").trim() &&
      String(product.time || product.updated_at || "").trim()
    ))
    : [];

  if (!payload.available || !String(payload?.tiles?.base_url || "").trim() || !products.length) {
    throw new Error(payload.message || "Radar temporaneamente non disponibile");
  }

  return {
    ...payload,
    city: String(payload.city || fallbackCity || "").trim(),
    products,
  };
}

export async function fetchRadarPayload(
  location,
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

  const url = buildRadarUrl(location, { apiBase, force, now });
  const response = await fetchImpl(url, {
    cache: force ? "no-store" : "default",
  });

  if (!response?.ok) {
    throw new Error("Risposta radar non valida");
  }

  const payload = await response.json();

  return normalizeRadarPayload(payload, {
    fallbackCity: getLocationCity(location),
  });
}
