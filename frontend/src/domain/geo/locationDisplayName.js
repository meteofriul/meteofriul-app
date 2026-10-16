import placeNamesArchive from "../../data/fvgPlaceNamesFur.json";
import {
  getLocationLocality,
  getLocationMunicipality,
  getLocationMunicipalityName,
  getLocationPrimaryName,
  hasDistinctLocality,
} from "./locationIdentity";

function normalizePlaceName(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const PLACE_NAMES = Array.isArray(placeNamesArchive.names) ? placeNamesArchive.names : [];
const PLACE_NAMES_BY_ISTAT = new Map(
  PLACE_NAMES.map((item) => [String(item.istatCode || "").trim(), item]),
);
const PLACE_NAMES_BY_ITALIAN_NAME = new Map(
  PLACE_NAMES.map((item) => [normalizePlaceName(item.it), item]),
);

export function getLocationDisplayName(location, language = "it") {
  const primaryName = getLocationPrimaryName(location);

  if (!primaryName || language !== "fur") return primaryName;

  if (typeof location === "object" && hasDistinctLocality(location)) {
    const locality = location?.locality;
    const localizedLocality = String(
      locality?.fur || locality?.nameFur || locality?.name_fur || "",
    ).trim();

    return localizedLocality || getLocationLocality(location)?.name || primaryName;
  }

  const istatCode = typeof location === "object"
    ? String(
        getLocationMunicipality(location)?.istatCode
          || location?.istatCode
          || "",
      ).trim()
    : "";
  const placeName = (istatCode && PLACE_NAMES_BY_ISTAT.get(istatCode))
    || PLACE_NAMES_BY_ITALIAN_NAME.get(normalizePlaceName(primaryName));

  return placeName?.fur || primaryName;
}

export function getMunicipalityDisplayName(location, language = "it") {
  const municipality = getLocationMunicipality(location);
  const municipalityName = municipality?.name || getLocationMunicipalityName(location);

  if (!municipalityName) return "";

  return getLocationDisplayName({
    city: municipalityName,
    istatCode: municipality?.istatCode,
    municipality,
  }, language);
}

export function getLocationSearchNames(place) {
  const italianName = String(place?.name || place?.city || "").trim();
  const friulianName = getLocationDisplayName(place, "fur");

  return Array.from(new Set([italianName, friulianName].filter(Boolean)));
}
