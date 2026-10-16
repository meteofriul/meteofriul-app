import { getLocationLocalityKey } from "../../domain/geo/locationIdentity";
import { FIXED_FVG_PLACES } from "../../data/fvgPlaces";

const FVG_REGION_KEY = "friuli venezia giulia";
const LEGACY_QUICK_KEYS = ["udine", "pordenone", "trieste", "gorizia", "tarvisio"];
const PILOT_QUICK_KEYS = ["udine", "trieste", "gorizia", "pordenone"];

export function buildLocationSheetShortcuts({ activeLocation, recentPlaces = [], pilot = false } = {}) {
  const fixedPlaces = (pilot ? PILOT_QUICK_KEYS : LEGACY_QUICK_KEYS)
    .map(key => FIXED_FVG_PLACES[key]).filter(Boolean);
  // Pilot shortcuts stay in a stable position, even for the active location.
  // Keep their records in storage, but do not repeat them in the Recent list.
  const visibleRecentPlaces = filterUniqueLocationPlaces(recentPlaces, {
    activeLocation,
    excludedPlaces: pilot ? [
      ...fixedPlaces,
      // Older municipality recents may predate the canonical ISTAT identity.
      ...fixedPlaces.map(({ name, admin1 }) => ({ name, admin1 })),
    ] : [],
  });
  const quickPlaces = filterUniqueLocationPlaces(fixedPlaces, pilot ? {} : {
    activeLocation,
    excludedPlaces: visibleRecentPlaces,
  });
  return { visibleRecentPlaces, quickPlaces };
}

function normalizeText(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function normalizeCountry(value) {
  const country = normalizeText(value);
  return ["italia", "italy"].includes(country) ? "it" : country;
}

export function getLocationPlaceKey(record) {
  const city = normalizeText(record?.name || record?.city);
  if (!city) return "";

  const region = normalizeText(record?.admin1 || record?.region || record?.state);
  const regionCode = normalizeText(
    record?.regionCode
      || record?.region_code
      || record?.admin1Code
      || record?.admin1_code,
  );
  const country = normalizeCountry(
    record?.countryCode
      || record?.country_code
      || record?.country
      || record?.countryName
      || record?.country_name
      || (region === FVG_REGION_KEY ? "IT" : ""),
  );
  const localityKey = getLocationLocalityKey(record);
  const rawLatitude = record?.latitude ?? record?.lat;
  const rawLongitude = record?.longitude ?? record?.lon;
  const latitude = Number(rawLatitude);
  const longitude = Number(rawLongitude);
  const coordinateKey = rawLatitude != null && rawLatitude !== ""
    && rawLongitude != null && rawLongitude !== ""
    && Number.isFinite(latitude) && Number.isFinite(longitude)
    ? `${latitude.toFixed(4)}|${longitude.toFixed(4)}`
    : "";
  const providerId = normalizeText(record?.id || record?.providerId || record?.provider_id);
  const istatCode = normalizeText(record?.istatCode || record?.istat_code);
  const territoryKey = [
    country ? `country:${country}` : "",
    region || regionCode ? `region:${region || regionCode}` : "",
    istatCode || providerId || coordinateKey
      ? `place:${istatCode || providerId || coordinateKey}`
      : "",
  ].filter(Boolean).join("|");

  return [localityKey || city, territoryKey].filter(Boolean).join("|");
}

export function filterUniqueLocationPlaces(
  places = [],
  {
    activeLocation,
    excludedPlaces = [],
  } = {},
) {
  const hiddenKeys = new Set(
    [
      getLocationPlaceKey(activeLocation),
      ...excludedPlaces.map(getLocationPlaceKey),
    ].filter(Boolean),
  );
  const visibleKeys = new Set();

  return (Array.isArray(places) ? places : []).filter((place) => {
    const key = getLocationPlaceKey(place);

    if (!key || hiddenKeys.has(key) || visibleKeys.has(key)) return false;

    visibleKeys.add(key);
    return true;
  });
}
