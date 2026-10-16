import { API_BASE } from "./apiConfig";
import { readJsonCache, writeJsonCache } from "./jsonCache";
import {
  normalizeLocalityIdentity,
  normalizeLocationDataPoint,
  normalizeLocationResolution,
  normalizeMunicipalityIdentity,
} from "../domain/geo/locationIdentity";

export const LOCATION_REVERSE_CACHE_PREFIX = "locationReverseCache:v3";
export const LOCATION_REVERSE_CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

function coerceFiniteNumber(value) {
  if (value == null || value === "") return null;

  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

export function normalizeReverseCoordinates(coords = {}) {
  const record = coords || {};
  const lat = coerceFiniteNumber(record.lat);
  const lon = coerceFiniteNumber(record.lon);

  if (lat == null || lon == null) return null;

  return { lat, lon };
}

export function isFvgReverseLocation(location) {
  return normalizeText(location?.region).includes("friuli");
}

export function getReverseLocationCacheKey(lat, lon) {
  const coords = normalizeReverseCoordinates({ lat, lon });

  if (!coords) {
    throw new Error("Coordinate reverse geocoding mancanti");
  }

  return `${LOCATION_REVERSE_CACHE_PREFIX}:${coords.lat.toFixed(6)}:${coords.lon.toFixed(6)}`;
}

export function buildReverseLocationUrl({ apiBase = API_BASE } = {}) {
  const base = String(apiBase || "").replace(/\/$/, "");

  return `${base}/location/reverse`;
}

export function normalizeReverseLocationPayload(payload, { lat, lon, source = "gps" } = {}) {
  const fallbackCoords = normalizeReverseCoordinates({ lat, lon });
  const payloadCoords = normalizeReverseCoordinates(payload);
  const dataPoint = normalizeLocationDataPoint(payload?.dataPoint);
  const hasExplicitMunicipality = Boolean(
    payload && Object.prototype.hasOwnProperty.call(payload, "municipality"),
  );
  const municipality = hasExplicitMunicipality && payload.municipality == null
    ? null
    : normalizeMunicipalityIdentity(payload?.municipality, {
        fallbackIstatCode: payload?.istatCode || payload?.istat,
        fallbackName: payload?.city,
        fallbackProvince: payload?.province,
        fallbackProvinceName: payload?.provinceName,
      });
  const city = String(municipality?.name || payload?.city || "").trim() || "Posizione attuale";
  const displayName = String(
    payload?.displayName
      || (typeof payload?.locality === "string" ? payload.locality : payload?.locality?.name)
      || city,
  ).trim() || city;
  const hasExplicitLocality = Boolean(
    payload && Object.prototype.hasOwnProperty.call(payload, "locality"),
  );
  const locality = hasExplicitLocality && payload.locality == null
    ? null
    : normalizeLocalityIdentity(payload?.locality, {
        fallbackName: displayName,
      });
  const resolution = normalizeLocationResolution(payload?.resolution);
  const region = String(payload?.region || "").trim() || "Italia";
  const coords = dataPoint || payloadCoords || fallbackCoords || { lat: null, lon: null };
  const location = {
    city,
    displayName,
    region,
    lat: coords.lat,
    lon: coords.lon,
    source: String(source || "gps").trim() || "gps",
  };
  const province = String(municipality?.province || payload?.province || "").trim().toUpperCase();
  const provinceName = String(municipality?.provinceName || payload?.provinceName || "").trim();
  const istatCode = String(municipality?.istatCode || payload?.istatCode || "").trim();

  if (province) location.province = province;
  if (provinceName) location.provinceName = provinceName;
  if (istatCode) location.istatCode = istatCode;
  location.locality = locality;
  location.municipality = municipality;
  if (dataPoint) location.dataPoint = dataPoint;
  if (resolution) location.resolution = resolution;

  return {
    ...location,
    insideFvg: isFvgReverseLocation(location),
  };
}

export async function resolveReverseLocation(
  coords,
  {
    apiBase = API_BASE,
    cacheEnabled = true,
    fetchImpl = globalThis.fetch,
    maxAgeMs = LOCATION_REVERSE_CACHE_MAX_AGE_MS,
    now = Date.now,
    signal,
    source = "gps",
    storage,
  } = {},
) {
  const normalizedCoords = normalizeReverseCoordinates(coords);
  const rawAccuracyM = coerceFiniteNumber(coords?.accuracyM ?? coords?.accuracy_m);
  const accuracyM = rawAccuracyM != null && rawAccuracyM >= 0 ? rawAccuracyM : null;

  if (!normalizedCoords) {
    throw new Error("Coordinate reverse geocoding mancanti");
  }

  const cacheKey = getReverseLocationCacheKey(normalizedCoords.lat, normalizedCoords.lon);
  const cachedLocation = cacheEnabled
    ? readJsonCache(cacheKey, maxAgeMs, { storage, now })
    : null;

  if (cachedLocation?.city) {
    return {
      ok: true,
      fromCache: true,
      cacheKey,
      location: normalizeReverseLocationPayload(cachedLocation, {
        ...normalizedCoords,
        source,
      }),
    };
  }

  if (typeof fetchImpl !== "function") {
    return {
      ok: false,
      fromCache: false,
      cacheKey,
      error: "fetch_unavailable",
      location: normalizeReverseLocationPayload(null, {
        ...normalizedCoords,
        source,
      }),
    };
  }

  try {
    const url = buildReverseLocationUrl({ apiBase });
    const request = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...normalizedCoords,
        ...(accuracyM != null ? { accuracyM } : {}),
      }),
      ...(signal ? { signal } : {}),
    };
    const response = await fetchImpl(url, request);

    if (!response?.ok) {
      throw new Error("Risposta reverse geocoding non valida");
    }

    const payload = await response.json();
    const location = normalizeReverseLocationPayload(payload, {
      ...normalizedCoords,
      source,
    });

    const cachedPayload = {
      city: location.city,
      displayName: location.displayName,
      region: location.region,
      lat: location.lat,
      lon: location.lon,
      locality: location.locality,
      municipality: location.municipality,
    };

    if (location.province) cachedPayload.province = location.province;
    if (location.provinceName) cachedPayload.provinceName = location.provinceName;
    if (location.istatCode) cachedPayload.istatCode = location.istatCode;
    if (location.dataPoint) cachedPayload.dataPoint = location.dataPoint;
    if (location.resolution) cachedPayload.resolution = location.resolution;

    if (cacheEnabled && location.resolution?.status !== "municipality_only") {
      writeJsonCache(cacheKey, cachedPayload, { storage, now });
    }

    return {
      ok: true,
      fromCache: false,
      cacheKey,
      location,
    };
  } catch (error) {
    return {
      ok: false,
      fromCache: false,
      cacheKey,
      error: error?.name === "AbortError"
        ? "aborted"
        : error?.message || "reverse_location_failed",
      location: normalizeReverseLocationPayload(null, {
        ...normalizedCoords,
        source,
      }),
    };
  }
}
