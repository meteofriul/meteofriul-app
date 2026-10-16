import { getLocationLocalityKey } from "./locationIdentity";

const FVG_REGION_KEY = "friuli venezia giulia";

function normalizeTerritoryToken(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function normalizeCountryToken(value) {
  const country = normalizeTerritoryToken(value);
  return ["italia", "italy"].includes(country) ? "it" : country;
}

// Cache keys written before national locations were introduced did not carry
// country/region identity. Keep this exact formatter available only for a
// guarded, one-time FVG migration in the cache adapters; all new writes use
// getLocationCacheKey below.
export function getLegacyLocationCacheKey(location) {
  const city = String(location?.city || "").trim().toLowerCase();
  const locality = location?.locality || location?.displayName
    ? getLocationLocalityKey(location)
    : "";
  const lat = location?.lat == null ? "city" : Number(location.lat).toFixed(4);
  const lon = location?.lon == null ? "city" : Number(location.lon).toFixed(4);

  return [city, locality, lat, lon].filter(Boolean).join("|");
}

export function getLocationCacheKey(location) {
  const city = String(location?.city || "").trim().toLowerCase();
  const locality = location?.locality || location?.displayName
    ? getLocationLocalityKey(location)
    : "";
  const region = normalizeTerritoryToken(
    location?.region || location?.admin1 || location?.state,
  );
  const regionCode = normalizeTerritoryToken(
    location?.regionCode
      || location?.region_code
      || location?.admin1Code
      || location?.admin1_code,
  );
  const country = normalizeCountryToken(
    location?.countryCode
      || location?.country_code
      || location?.country
      || location?.countryName
      || location?.country_name
      || (region === FVG_REGION_KEY ? "IT" : ""),
  );
  const lat = location?.lat == null ? "city" : Number(location.lat).toFixed(4);
  const lon = location?.lon == null ? "city" : Number(location.lon).toFixed(4);
  const territory = [
    country ? `country:${country}` : "",
    region || regionCode ? `region:${region || regionCode}` : "",
  ].filter(Boolean);

  return [city, locality, ...territory, lat, lon].filter(Boolean).join("|");
}

export function getLocationCacheKeyFromCity(city) {
  return getLocationCacheKey({ city });
}
