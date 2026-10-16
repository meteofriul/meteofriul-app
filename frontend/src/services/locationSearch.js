import { FIXED_FVG_PLACES } from "../data/fvgPlaces";
import { getLocationSearchNames } from "../domain/geo/locationDisplayName";
import { API_BASE } from "./apiConfig";
import {
  getLocalWeatherNationalApiBase,
  isLocalWeatherNationalPilot,
} from "./localWeatherPilot";

const ITALY_COUNTRY_CODE = "IT";

export class LocationSearchUnavailableError extends Error {
  constructor() {
    super("location_search_source_unavailable");
    this.name = "LocationSearchUnavailableError";
  }
}
const MAX_LOCATION_RESULTS = 8;
const NATIONAL_PILOT_SEARCH_KIND = "meteofriul.weather.icon.national.local_pilot_search";
const NATIONAL_PILOT_CONTRACT = "weather/v2/icon2i";
const MAIN_PLACE_PRIORITY = new Map([
  ["udine", 1000],
  ["trieste", 980],
  ["pordenone", 960],
  ["gorizia", 940],
  ["monfalcone", 860],
  ["sacile", 820],
  ["codroipo", 800],
  ["cividale del friuli", 780],
  ["gemona del friuli", 760],
  ["tolmezzo", 740],
  ["tarvisio", 720],
  ["lignano sabbiadoro", 700],
  ["grado", 680],
  ["spilimbergo", 660],
  ["palmanova", 640],
  ["cordenons", 620],
  ["san vito al tagliamento", 600],
]);

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function normalizeNationalPilotQuery(value) {
  return normalizeText(value)
    .replace(/[^0-9a-z]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function getPlaceText(place) {
  const names = getLocationSearchNames(place).map(normalizeText);
  const name = names[0] || "";
  const province = normalizeText(place.province);

  return { name, names, province };
}

function matchesPlaceQuery(key, place, cleanQuery) {
  const { names, province } = getPlaceText(place);
  const compactQuery = cleanQuery.replace(/\s+/g, "");

  return (
    key.includes(cleanQuery) ||
    names.some((name) => name.includes(cleanQuery)) ||
    names.some((name) => name.replace(/\s+/g, "").includes(compactQuery)) ||
    cleanQuery.includes(key) ||
    province === cleanQuery
  );
}

function getMatchScore(key, place, cleanQuery) {
  const { name, names, province } = getPlaceText(place);
  const compactQuery = cleanQuery.replace(/\s+/g, "");
  const mainPriority = MAIN_PLACE_PRIORITY.get(name) || 0;
  const exactMatch = names.some((item) => (
    item === cleanQuery || item.replace(/\s+/g, "") === compactQuery
  ));
  const prefixMatch = names.some((item) => (
    item.startsWith(cleanQuery) || item.replace(/\s+/g, "").startsWith(compactQuery)
  ));
  const wordStarts = names.some((item) => (
    item.split(" ").some((part) => part.startsWith(cleanQuery))
  ));
  const containsMatch = names.some((item) => item.includes(cleanQuery));
  const compactContainsMatch = names.some((item) => (
    item.replace(/\s+/g, "").includes(compactQuery)
  ));
  let matchPriority = 0;

  if (exactMatch) {
    matchPriority = 10000;
  } else if (prefixMatch) {
    matchPriority = 9000;
  } else if (wordStarts) {
    matchPriority = 8400;
  } else if (key?.startsWith(cleanQuery)) {
    matchPriority = 8200;
  } else if (containsMatch) {
    matchPriority = 7000;
  } else if (compactContainsMatch) {
    matchPriority = 6600;
  } else if (province === cleanQuery) {
    matchPriority = 8000;
  } else if (cleanQuery.includes(key)) {
    matchPriority = 2600;
  }

  return matchPriority + mainPriority + Math.min(Number(place.population || 0), 200000) / 100000;
}

function getPlaceIdentity(place) {
  // ISTAT identifies the municipality across local and national catalogues;
  // display names, region punctuation and provider ids are not its identity.
  const municipalityCode = String(place?.istatCode || place?.istat_code || "").trim();
  const municipalityCountry = String(place?.countryCode || place?.country_code || "IT").toUpperCase();
  if (municipalityCountry === "IT" && /^\d{6}$/u.test(municipalityCode)) {
    return `IT|istat:${municipalityCode}`;
  }
  const name = normalizeText(place?.name);
  const country = normalizeText(
    place?.countryCode
      || place?.country_code
      || place?.country
      || place?.countryName
      || place?.country_name,
  );
  const region = normalizeText(
    place?.admin1
      || place?.region
      || place?.state
      || place?.regionCode
      || place?.region_code
      || place?.admin1Code
      || place?.admin1_code,
  );
  const rawLatitude = place?.latitude ?? place?.lat;
  const rawLongitude = place?.longitude ?? place?.lon;
  const latitude = Number(rawLatitude);
  const longitude = Number(rawLongitude);
  const coordinateKey = rawLatitude != null && rawLatitude !== ""
    && rawLongitude != null && rawLongitude !== ""
    && Number.isFinite(latitude) && Number.isFinite(longitude)
    ? `${latitude.toFixed(4)}|${longitude.toFixed(4)}`
    : "";
  const providerId = normalizeText(place?.id || place?.providerId || place?.provider_id);
  const istatCode = normalizeText(place?.istatCode || place?.istat_code);

  return `${name}|${country}|${region}|${providerId || istatCode || coordinateKey}`;
}

function normalizePlace(place) {
  const name = String(place?.name || "").trim();
  if (!name) return null;

  const admin1 = String(place.admin1 || place.region || place.state || "").trim();
  const country = String(
    place.country || place.countryName || place.country_name || "",
  ).trim();
  const explicitCountryCode = String(place.countryCode || place.country_code || "").trim();
  const countryKey = normalizeText(country);
  const countryCode = String(
    explicitCountryCode
      || (!country || ["italia", "italy"].includes(countryKey) ? ITALY_COUNTRY_CODE : ""),
  ).trim().toUpperCase();
  const regionCode = String(
    place.regionCode
      || place.region_code
      || place.admin1Code
      || place.admin1_code
      || "",
  ).trim().toUpperCase();
  const normalized = {
    name,
    admin1,
    latitude: Number.isFinite(Number(place.latitude ?? place.lat)) ? Number(place.latitude ?? place.lat) : null,
    longitude: Number.isFinite(Number(place.longitude ?? place.lon)) ? Number(place.longitude ?? place.lon) : null,
    population: Number(place.population || 0),
    province: String(place.province || "").trim(),
    provinceName: String(place.provinceName || place.province_name || place.admin2 || "").trim(),
    istatCode: String(place.istatCode || place.istat_code || "").trim(),
  };

  const provider = String(place.provider || "").trim();
  const providerId = String(place.providerId || place.provider_id || place.id || "").trim();

  if (countryCode) normalized.countryCode = countryCode;
  if (country) normalized.country = country;
  if (regionCode) normalized.regionCode = regionCode;
  if (provider) normalized.provider = provider;
  if (providerId) normalized.providerId = providerId;

  return normalized;
}

function normalizeNationalPilotResults(payload, cleanQuery) {
  if (
    payload?.schema_version !== 1
    || payload?.kind !== NATIONAL_PILOT_SEARCH_KIND
    || payload?.contract !== NATIONAL_PILOT_CONTRACT
    || payload?.status !== "experimental_local_pilot_only"
    || normalizeText(payload?.query) !== cleanQuery
    || !Array.isArray(payload?.results)
    || payload.results.length > MAX_LOCATION_RESULTS
  ) {
    throw new TypeError("national_pilot_location_search_invalid");
  }

  return payload.results.map((result) => {
    const latitude = Number(result?.latitude);
    const longitude = Number(result?.longitude);
    const istatCode = String(result?.istat_code || "").trim();
    const name = String(result?.name || "").trim();
    const province = String(result?.province || "").trim().toUpperCase();
    const provinceName = String(result?.province_name || "").trim();
    const admin1 = String(result?.region_name || "").trim();
    const regionCode = String(result?.region_iso || "").trim().toUpperCase();
    if (
      !/^\d{6}$/u.test(istatCode)
      || !name
      || !/^[A-Z]{2}$/u.test(province)
      || !provinceName
      || !admin1
      || !/^IT-[A-Z0-9]{2,3}$/u.test(regionCode)
      || !Number.isFinite(latitude)
      || !Number.isFinite(longitude)
      || latitude < -90
      || latitude > 90
      || longitude < -180
      || longitude > 180
    ) {
      throw new TypeError("national_pilot_location_search_invalid");
    }
    return {
      name,
      admin1,
      regionCode,
      country: "Italia",
      countryCode: ITALY_COUNTRY_CODE,
      latitude,
      longitude,
      province,
      provinceName,
      istatCode,
      provider: "national_icon2i_pilot_catalog",
      providerId: istatCode,
    };
  });
}

export function getLocalFvgLocationResults(query, { limit = MAX_LOCATION_RESULTS } = {}) {
  const cleanQuery = normalizeText(query);
  if (cleanQuery.length < 2) return [];

  const uniqueMap = new Map();

  Object.entries(FIXED_FVG_PLACES)
    .filter(([key, place]) => matchesPlaceQuery(key, place, cleanQuery))
    .map(([key, place]) => ({ key, place: normalizePlace(place) }))
    .filter(({ place }) => Boolean(place))
    .sort((first, second) => getMatchScore(second.key, second.place, cleanQuery) - getMatchScore(first.key, first.place, cleanQuery))
    .map(({ place }) => place)
    .filter(Boolean)
    .forEach((place) => {
      const key = getPlaceIdentity(place);
      if (!uniqueMap.has(key)) {
        uniqueMap.set(key, place);
      }
    });

  return Array.from(uniqueMap.values()).slice(0, limit);
}

export function mergeLocationResults(
  primaryPlaces = [],
  secondaryPlaces = [],
  {
    limit = MAX_LOCATION_RESULTS,
    query = "",
  } = {},
) {
  const uniqueMap = new Map();
  const cleanQuery = normalizeText(query);

  [...primaryPlaces, ...secondaryPlaces]
    .map(normalizePlace)
    .filter(Boolean)
    .forEach((place) => {
      const key = getPlaceIdentity(place);
      if (!uniqueMap.has(key)) {
        uniqueMap.set(key, place);
      }
    });

  const mergedPlaces = Array.from(uniqueMap.values());

  return mergedPlaces
    .sort((first, second) => {
      if (cleanQuery.length >= 2) {
        return getMatchScore("", second, cleanQuery) - getMatchScore("", first, cleanQuery);
      }

      return (second.population || 0) - (first.population || 0);
    })
    .slice(0, limit);
}

export async function searchVerifiedMunicipalities(
  query,
  { apiBase = API_BASE, fetchImpl = globalThis.fetch } = {},
) {
  if (normalizeText(query).length < 2 || typeof fetchImpl !== "function") return [];
  const base = String(apiBase || "").replace(/\/$/, "");
  const response = await fetchImpl(
    `${base}/location/municipalities/search?q=${encodeURIComponent(query)}`,
  );
  if (!response?.ok) throw new LocationSearchUnavailableError();
  const payload = await response.json();
  if (!Array.isArray(payload) || payload.length > MAX_LOCATION_RESULTS) {
    throw new TypeError("verified_municipality_search_invalid");
  }
  return payload.map((item) => {
    const place = normalizePlace(item);
    const rawLatitude = item?.latitude ?? item?.lat;
    const rawLongitude = item?.longitude ?? item?.lon;
    if (
      !place
      || rawLatitude == null
      || rawLongitude == null
      || rawLatitude === ""
      || rawLongitude === ""
      || !/^\d{6}$/u.test(place.istatCode)
      || !/^[A-Z]{2}$/u.test(place.province)
      || !place.admin1
      || place.countryCode !== ITALY_COUNTRY_CODE
      || place.provider !== "istat_municipality_catalog"
      || place.providerId !== place.istatCode
      || !Number.isFinite(place.latitude)
      || !Number.isFinite(place.longitude)
      || place.latitude < -90
      || place.latitude > 90
      || place.longitude < -180
      || place.longitude > 180
    ) throw new TypeError("verified_municipality_search_invalid");
    return place;
  });
}

export function mergeVerifiedMunicipalityResults(
  ordinaryPlaces = [],
  verifiedPlaces = [],
  { limit = MAX_LOCATION_RESULTS, query = "" } = {},
) {
  const ordinary = Array.isArray(ordinaryPlaces) ? ordinaryPlaces : [];
  const verified = Array.isArray(verifiedPlaces) ? verifiedPlaces : [];
  const consumed = new Set();
  const canonical = verified.map((municipality) => {
    const matchIndex = ordinary.findIndex((place, index) => (
      !consumed.has(index)
      && (
        (place.istatCode && place.istatCode === municipality.istatCode)
        || (
          normalizeText(place.name) === normalizeText(municipality.name)
          && normalizeText(place.province) === normalizeText(municipality.province)
          && normalizeText(place.admin1).replace(/-/gu, " ")
            === normalizeText(municipality.admin1).replace(/-/gu, " ")
        )
      )
    ));
    if (matchIndex < 0) return municipality;
    consumed.add(matchIndex);
    const place = ordinary[matchIndex];
    if (place.istatCode === municipality.istatCode) return place;
    // Keep the established weather point, but take the identity exclusively
    // from the checked ISTAT result. Never infer it from a matching name alone.
    return {
      ...place,
      name: municipality.name,
      admin1: municipality.admin1,
      province: municipality.province,
      provinceName: municipality.provinceName,
      istatCode: municipality.istatCode,
      country: "Italia",
      countryCode: ITALY_COUNTRY_CODE,
    };
  });
  return mergeLocationResults(
    canonical,
    ordinary.filter((_, index) => !consumed.has(index)),
    { limit, query },
  );
}

export async function searchLocations(
  query,
  {
    apiBase = API_BASE,
    fetchImpl = globalThis.fetch,
    limit = MAX_LOCATION_RESULTS,
    nationalPilot = isLocalWeatherNationalPilot(),
    nationalApiBase = getLocalWeatherNationalApiBase(),
  } = {},
) {
  const localResults = getLocalFvgLocationResults(query, { limit });
  const cleanQuery = normalizeText(query);

  if (cleanQuery.length < 2 || typeof fetchImpl !== "function") {
    return localResults;
  }

  if (nationalPilot) {
    try {
      const base = String(nationalApiBase || "").replace(/\/+$/, "");
      if (!base) return localResults;
      const response = await fetchImpl(
        `${base}/weather/v2/icon2i/search.json?q=${encodeURIComponent(query)}`,
      );
      if (!response?.ok) {
        if (localResults.length === 0) throw new LocationSearchUnavailableError();
        return localResults;
      }
      const payload = await response.json();
      const nationalResults = normalizeNationalPilotResults(
        payload,
        normalizeNationalPilotQuery(query),
      );
      return mergeLocationResults(localResults, nationalResults, { limit, query });
    } catch (error) {
      if (localResults.length > 0) return localResults;
      if (error instanceof LocationSearchUnavailableError) throw error;
      throw new LocationSearchUnavailableError();
    }
  }

  try {
    const base = String(apiBase || "").replace(/\/$/, "");
    const response = await fetchImpl(`${base}/location/search?q=${encodeURIComponent(query)}`);
    if (!response?.ok) {
      if (Number(response?.status) === 503 && localResults.length === 0) {
        throw new LocationSearchUnavailableError();
      }
      return localResults;
    }

    const remoteResults = await response.json();

    return mergeLocationResults(localResults, Array.isArray(remoteResults) ? remoteResults : [], { limit, query });
  } catch (error) {
    if (error instanceof LocationSearchUnavailableError) throw error;
    return localResults;
  }
}
