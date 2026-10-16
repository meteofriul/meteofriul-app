import {
  getLocationLocalityKey,
  normalizeLocalityIdentity,
  normalizeLocationDataPoint,
  normalizeLocationResolution,
  normalizeMunicipalityIdentity,
} from "../domain/geo/locationIdentity";
import { FIXED_FVG_PLACES } from "../data/fvgPlaces";

export const DEFAULT_APP_LOCATION = {
  city: "Udine",
  displayName: "Udine",
  region: "Friuli Venezia Giulia",
  province: "UD",
  provinceName: "Udine",
  istatCode: "030129",
  locality: {
    name: "Udine",
    kind: "municipality",
  },
  municipality: {
    name: "Udine",
    istatCode: "030129",
    province: "UD",
    provinceName: "Udine",
  },
  lat: null,
  lon: null,
  source: "placeholder",
};

export const APP_LOCATION_STORAGE_KEY = "defaultLocation";
export const APP_RECENT_LOCATIONS_STORAGE_KEY = "recentLocations";
export const APP_AUTO_LOCATION_STORAGE_KEY = "autoLocationEnabled";
const MAX_RECENT_LOCATIONS = 6;
const FVG_PROVINCES = new Set(["GO", "PN", "TS", "UD"]);
const FVG_ISTAT_PREFIXES = new Set(["030", "031", "032", "093"]);

function getStorage(storage = globalThis.window?.localStorage) {
  return storage || null;
}

function normalizeCoordinate(value) {
  if (value == null || value === "") return null;

  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function normalizePositionAccuracy(value) {
  if (value == null || value === "") return null;

  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : null;
}

function normalizePositionCapturedAt(value) {
  if (!value) return "";

  const capturedAt = new Date(value);
  return Number.isNaN(capturedAt.getTime()) ? "" : capturedAt.toISOString();
}

function normalizeMunicipalityLookupToken(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function hasFvgMunicipalityIdentity(municipality) {
  const province = String(municipality?.province || "").trim().toUpperCase();
  const istatCode = String(municipality?.istatCode || "").trim();
  return FVG_PROVINCES.has(province)
    || (istatCode.length === 6 && FVG_ISTAT_PREFIXES.has(istatCode.slice(0, 3)));
}

const FVG_MUNICIPALITIES_BY_ISTAT = new Map(
  Object.values(FIXED_FVG_PLACES)
    .filter((place) => String(place?.istatCode || "").trim())
    .map((place) => [String(place.istatCode).trim(), place]),
);

const FVG_MUNICIPALITIES_BY_NAME = new Map(
  Object.values(FIXED_FVG_PLACES)
    .filter((place) => normalizeMunicipalityLookupToken(place?.name))
    .map((place) => [normalizeMunicipalityLookupToken(place.name), place]),
);

function getManualMunicipalityCatalogPoint({
  city,
  displayName,
  locality,
  municipality,
  source,
}) {
  const normalizedSource = String(source || "").trim().toLowerCase();
  if (normalizedSource !== "manual_recent") return null;

  const cityToken = normalizeMunicipalityLookupToken(city);
  const displayToken = normalizeMunicipalityLookupToken(displayName);
  const localityToken = normalizeMunicipalityLookupToken(locality?.name);
  if (!cityToken || (displayToken && displayToken !== cityToken)) return null;
  if (localityToken && localityToken !== cityToken) return null;

  const istatCode = String(municipality?.istatCode || "").trim();
  const place = FVG_MUNICIPALITIES_BY_ISTAT.get(istatCode)
    || FVG_MUNICIPALITIES_BY_NAME.get(cityToken);
  const lat = Number(place?.latitude);
  const lon = Number(place?.longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;

  return {
    lat,
    lon,
    source: "municipality_catalog",
  };
}

export function normalizeAppLocation(record) {
  if (!record || typeof record !== "object") return null;

  const hasExplicitMunicipality = Object.prototype.hasOwnProperty.call(record, "municipality");
  const municipality = hasExplicitMunicipality && record.municipality == null
    ? null
    : normalizeMunicipalityIdentity(record.municipality, {
        fallbackIstatCode: record.istatCode || record.istat,
        fallbackName: record.city || record.name,
        fallbackProvince: record.province,
        fallbackProvinceName: record.provinceName,
      });
  const city = String(municipality?.name || record.city || record.name || "").trim();
  if (!city) return null;

  const displayName = String(
    record.displayName
      || (typeof record.locality === "string" ? record.locality : record.locality?.name)
      || city,
  ).trim();
  const hasExplicitLocality = Object.prototype.hasOwnProperty.call(record, "locality");
  const locality = hasExplicitLocality && record.locality == null
    ? null
    : normalizeLocalityIdentity(record.locality, {
        fallbackName: displayName || city,
      });
  const resolution = normalizeLocationResolution(record.resolution);
  const source = String(record.source || "manual").trim() || "manual";
  const dataPoint = normalizeLocationDataPoint(record.dataPoint)
    || getManualMunicipalityCatalogPoint({
      city,
      displayName,
      locality,
      municipality,
      source,
    });
  const positionAccuracyM = normalizePositionAccuracy(record.positionAccuracyM);
  const positionCapturedAt = normalizePositionCapturedAt(record.positionCapturedAt);
  const normalizedSource = source.toLowerCase();
  const isAutomaticSource = !["manual", "manual_recent", "placeholder"].includes(normalizedSource);
  const dropsLegacyPreciseCoordinates = isAutomaticSource || normalizedSource === "manual_recent";

  const explicitRegion = String(record.region || record.admin1 || record.state || "").trim();
  const inferredFvgRegion = hasFvgMunicipalityIdentity(municipality)
    ? DEFAULT_APP_LOCATION.region
    : "";
  const normalized = {
    city,
    displayName: displayName || city,
    region: explicitRegion || inferredFvgRegion,
    lat: dataPoint?.lat ?? (dropsLegacyPreciseCoordinates ? null : normalizeCoordinate(record.lat)),
    lon: dataPoint?.lon ?? (dropsLegacyPreciseCoordinates ? null : normalizeCoordinate(record.lon)),
    source,
  };
  const countryCode = String(record.countryCode || record.country_code || "").trim().toUpperCase();
  const country = String(record.country || "").trim();
  const regionCode = String(record.regionCode || record.region_code || "").trim().toUpperCase();
  const province = String(municipality?.province || record.province || "").trim().toUpperCase();
  const provinceName = String(municipality?.provinceName || record.provinceName || "").trim();
  const istatCode = String(municipality?.istatCode || record.istatCode || "").trim();

  if (province) normalized.province = province;
  if (provinceName) normalized.provinceName = provinceName;
  if (istatCode) normalized.istatCode = istatCode;
  if (countryCode) normalized.countryCode = countryCode;
  if (country) normalized.country = country;
  if (regionCode) normalized.regionCode = regionCode;
  if (hasExplicitLocality || locality) normalized.locality = locality;
  if (hasExplicitMunicipality || municipality) normalized.municipality = municipality;
  if (dataPoint) normalized.dataPoint = dataPoint;
  if (resolution) normalized.resolution = resolution;
  if (positionAccuracyM != null) normalized.positionAccuracyM = positionAccuracyM;
  if (positionCapturedAt) normalized.positionCapturedAt = positionCapturedAt;

  return normalized;
}

function getAppLocationKey(location) {
  const normalized = normalizeAppLocation(location);
  if (!normalized) return "";

  const localityKey = getLocationLocalityKey(normalized);
  const countryKey = String(normalized.countryCode || normalized.country || "IT").trim().toLowerCase();
  const regionKey = String(normalized.regionCode || normalized.region || "unknown").trim().toLowerCase();
  const provinceKey = String(normalized.province || "unknown").trim().toLowerCase();
  const coordinateKey = normalized.lat != null && normalized.lon != null
    && Number.isFinite(Number(normalized.lat))
    && Number.isFinite(Number(normalized.lon))
    ? `${Number(normalized.lat).toFixed(4)}|${Number(normalized.lon).toFixed(4)}`
    : "";

  return `${countryKey}|${regionKey}|${provinceKey}|${localityKey || normalized.city}|${coordinateKey}`.toLowerCase();
}

function isLegacyRecentForVerifiedMunicipality(legacy, verified) {
  if (legacy.istatCode || !verified.istatCode) return false;

  const legacyName = normalizeMunicipalityLookupToken(legacy.municipality?.name || legacy.city);
  const verifiedName = normalizeMunicipalityLookupToken(verified.municipality?.name || verified.city);
  const legacyDisplayName = normalizeMunicipalityLookupToken(legacy.displayName);
  const verifiedDisplayName = normalizeMunicipalityLookupToken(verified.displayName);
  const legacyRegion = normalizeMunicipalityLookupToken(legacy.region);
  const verifiedRegion = normalizeMunicipalityLookupToken(verified.region);
  const legacyProvince = String(legacy.province || legacy.municipality?.province || "").trim().toUpperCase();
  const verifiedProvince = String(verified.province || verified.municipality?.province || "").trim().toUpperCase();
  const legacyCountry = String(legacy.countryCode || "IT").trim().toUpperCase();
  const verifiedCountry = String(verified.countryCode || "IT").trim().toUpperCase();

  return Boolean(
    legacyName && legacyName === verifiedName
    && legacyDisplayName === legacyName
    && verifiedDisplayName === verifiedName
    && legacyRegion && legacyRegion === verifiedRegion
    && legacyProvince && legacyProvince === verifiedProvince
    && legacyCountry === verifiedCountry,
  );
}

function normalizeRecentLocations(locations) {
  const normalizedLocations = (Array.isArray(locations) ? locations : [])
    .map(normalizeAppLocation)
    .filter(Boolean);
  const verifiedMunicipalities = normalizedLocations.filter((location) => location.istatCode);
  const uniqueMap = new Map();

  normalizedLocations.forEach((location) => {
    // Retire a legacy municipality only when one verified identity proves the match.
    // Distinct settlements and ambiguous same-name municipalities remain separate.
    if (verifiedMunicipalities.filter((verified) =>
      isLegacyRecentForVerifiedMunicipality(location, verified)).length === 1) return;

    const key = getAppLocationKey(location);
    if (key && !uniqueMap.has(key)) uniqueMap.set(key, location);
  });

  return Array.from(uniqueMap.values()).slice(0, MAX_RECENT_LOCATIONS);
}

export function isSameAppLocation(first, second) {
  const firstKey = getAppLocationKey(first);
  const secondKey = getAppLocationKey(second);

  return Boolean(firstKey && firstKey === secondKey);
}

export function readStoredAppLocation({ storage } = {}) {
  const localStorage = getStorage(storage);
  if (!localStorage) return null;

  try {
    return normalizeAppLocation(JSON.parse(localStorage.getItem(APP_LOCATION_STORAGE_KEY)));
  } catch {
    return null;
  }
}

export function readInitialAppLocation(options = {}) {
  return readStoredAppLocation(options) || DEFAULT_APP_LOCATION;
}

export function writeStoredAppLocation(location, { storage } = {}) {
  const localStorage = getStorage(storage);
  const normalized = normalizeAppLocation(location);

  if (!localStorage || !normalized) return null;

  try {
    localStorage.setItem(APP_LOCATION_STORAGE_KEY, JSON.stringify(normalized));
    return normalized;
  } catch {
    return null;
  }
}

export function readStoredAutoLocationEnabled({ storage } = {}) {
  const localStorage = getStorage(storage);
  if (!localStorage) return false;

  try {
    return localStorage.getItem(APP_AUTO_LOCATION_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function writeStoredAutoLocationEnabled(enabled, { storage } = {}) {
  const localStorage = getStorage(storage);
  if (!localStorage) return false;

  try {
    localStorage.setItem(APP_AUTO_LOCATION_STORAGE_KEY, enabled ? "true" : "false");
    return true;
  } catch {
    return false;
  }
}

export function readStoredRecentLocations({ storage } = {}) {
  const localStorage = getStorage(storage);
  if (!localStorage) return [];

  try {
    const records = JSON.parse(localStorage.getItem(APP_RECENT_LOCATIONS_STORAGE_KEY));
    if (!Array.isArray(records)) return [];

    return normalizeRecentLocations(records);
  } catch {
    return [];
  }
}

export function writeStoredRecentLocations(locations, { storage } = {}) {
  const localStorage = getStorage(storage);
  if (!localStorage) return [];

  const normalizedLocations = normalizeRecentLocations(locations);

  try {
    localStorage.setItem(APP_RECENT_LOCATIONS_STORAGE_KEY, JSON.stringify(normalizedLocations));
  } catch {
    return [];
  }

  return normalizedLocations;
}

export function appendStoredRecentLocation(location, { storage } = {}) {
  const normalized = normalizeAppLocation(location);
  if (!normalized) return readStoredRecentLocations({ storage });

  const recentLocations = readStoredRecentLocations({ storage });
  const nextLocations = [
    normalized,
    ...recentLocations.filter((item) => !isSameAppLocation(item, normalized)),
  ];

  return writeStoredRecentLocations(nextLocations, { storage });
}

export function removeStoredRecentLocation(location, { storage } = {}) {
  const normalized = normalizeAppLocation(location);
  if (!normalized) return readStoredRecentLocations({ storage });

  const recentLocations = readStoredRecentLocations({ storage });
  const nextLocations = recentLocations.filter((item) => !isSameAppLocation(item, normalized));

  return writeStoredRecentLocations(nextLocations, { storage });
}
