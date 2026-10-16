import { FIXED_FVG_PLACES } from "../../data/fvgPlaces";
import { isFvgLocation } from "../../domain/scope/productScope";
import { getPilotDetectedMunicipality } from "./pilotDetectedMunicipality";

const MANUAL_SOURCES = new Set(["", "manual", "manual_recent", "manual_search"]);
const MUNICIPALITIES = Object.values(FIXED_FVG_PLACES);
const BY_ISTAT = new Map(MUNICIPALITIES.map((place) => [place.istatCode, place]));

function token(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function values(...entries) {
  return entries.filter((entry) => entry != null && String(entry).trim() !== "")
    .map((entry) => String(entry).trim());
}

const BY_NAME = new Map(MUNICIPALITIES.map((place) => [token(place.name), place]));

function getSelectedMunicipality(location) {
  if (!location || !MANUAL_SOURCES.has(String(location.source || "").trim().toLowerCase())) return null;
  if (!isFvgLocation(location)) return null;

  const municipality = location.municipality;
  const countryCodes = values(location.countryCode, location.country_code);
  const countries = values(location.country, location.countryName, location.country_name);
  const regions = values(location.region, location.admin1, location.state);
  const regionCodes = values(location.regionCode, location.region_code, location.admin1Code, location.admin1_code);
  if (
    countryCodes.some((value) => value.toUpperCase() !== "IT")
    || countries.some((value) => !["it", "italia", "italy"].includes(token(value)))
    || regions.some((value) => token(value) !== "friuli venezia giulia")
    || regionCodes.some((value) => value.toUpperCase() !== "IT-36")
  ) return null;

  const codes = values(
    location.istatCode, location.istat_code, location.istat,
    municipality?.istatCode, municipality?.istat_code, municipality?.istat,
  );
  const names = values(
    location.city, location.name,
    typeof municipality === "string" ? municipality : municipality?.name,
  );
  if (new Set(codes).size > 1) return null;
  const place = codes.length ? BY_ISTAT.get(codes[0]) : BY_NAME.get(token(names[0]));
  if (!place || names.some((name) => token(name) !== token(place.name))) return null;

  const provinces = values(location.province, municipality?.province);
  if (provinces.some((value) => value.toUpperCase() !== place.province)) return null;

  return location.istatCode === place.istatCode && location.city === place.name
    ? location
    : { ...location, city: place.name, istatCode: place.istatCode };
}

/** The pilot card follows the current municipality, never editorial fallback. */
export function getPilotMunicipalityContext({
  activeLocation,
  autoLocationEnabled = false,
  deviceLocationStatus,
} = {}) {
  if (autoLocationEnabled === true && deviceLocationStatus?.status === "success") {
    const location = getPilotDetectedMunicipality({ autoLocationEnabled, deviceLocationStatus });
    // A successful external GPS result supersedes any older manual selection.
    return location ? { location, mode: "detected" } : null;
  }

  const location = getSelectedMunicipality(activeLocation);
  return location ? { location, mode: "selected" } : null;
}
