const FVG_REGION_CODE = "IT-36";
const FVG_REGION_LABEL = "Friuli Venezia Giulia";
const FVG_PROVINCES = new Set(["GO", "PN", "TS", "UD"]);
const FVG_ISTAT_PREFIXES = new Set(["030", "031", "032", "093"]);
const ITALIAN_REGION_CODES = Object.freeze([
  "IT-21", "IT-23", "IT-25", "IT-32", "IT-34", "IT-36", "IT-42", "IT-45",
  "IT-52", "IT-55", "IT-57", "IT-62", "IT-65", "IT-67", "IT-72", "IT-75",
  "IT-77", "IT-78", "IT-82", "IT-88",
]);

function normalizeToken(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function getRegionCode(location) {
  return String(
    location?.regionCode
      || location?.region_code
      || location?.admin1Code
      || location?.admin1_code
      || "",
  ).trim().toUpperCase();
}

export const PRODUCT_SCOPE = Object.freeze({
  editorial: "fvg-editorial",
  events: "fvg-events",
  fvgRegionCode: FVG_REGION_CODE,
  nationalWeather: "italy-weather",
});

export const COMMUNITY_REGION_NOT_ENABLED_CODE = "community_region_not_enabled";

export function isFvgLocation(location) {
  if (!location || typeof location !== "object") return false;

  const regionCode = getRegionCode(location);
  if (regionCode) return regionCode === FVG_REGION_CODE;

  const region = normalizeToken(location.region || location.admin1 || location.state);
  if (region) return region === normalizeToken(FVG_REGION_LABEL);

  const province = String(
    location.province || location.municipality?.province || "",
  ).trim().toUpperCase();
  if (province) return FVG_PROVINCES.has(province);

  const istatCode = String(
    location.istatCode || location.istat_code || location.municipality?.istatCode || "",
  ).trim();
  return istatCode.length === 6 && FVG_ISTAT_PREFIXES.has(istatCode.slice(0, 3));
}

export function getTerritoryKind(location) {
  if (isFvgLocation(location)) return "fvg";

  const regionCode = getRegionCode(location);
  if (regionCode.startsWith("IT-")) return "italy";

  const countryCode = String(location?.countryCode || location?.country_code || "")
    .trim()
    .toUpperCase();
  const country = normalizeToken(location?.country);
  if (countryCode === "IT" || country === "italia" || country === "italy") return "italy";
  return "unknown";
}

export function resolveProductScope(
  location,
  { language = "it", nationalForecastEnabled = false, nationalCommunityEnabled = false } = {},
) {
  const territory = getTerritoryKind(location);
  const inFvg = territory === "fvg";
  const inItaly = inFvg || territory === "italy";
  const fur = language === "fur";
  const forecastEnabled = inFvg || (inItaly && nationalForecastEnabled);
  const communityWrite = inFvg || (inItaly && nationalCommunityEnabled);

  return {
    territory,
    sources: {
      forecast: {
        provider: "icon-2i",
        scope: "italy",
        status: forecastEnabled ? "enabled" : inItaly ? "planned" : "unsupported",
      },
      icon2i: {
        provider: "icon-2i",
        scope: "italy",
        status: forecastEnabled ? "enabled" : inItaly ? "planned" : "unsupported",
      },
      radar: {
        provider: "radar-dpc",
        scope: "italy",
        status: inItaly ? "enabled" : "unsupported",
      },
      nationalAlerts: {
        provider: "dpc",
        scope: "italy",
        status: inItaly ? "enabled" : "unsupported",
      },
      osmer: {
        provider: "osmer-arpa-fvg",
        scope: FVG_REGION_CODE,
        status: inFvg ? "enabled" : "unsupported",
      },
      webcams: {
        provider: "fvg-editorial-webcams",
        scope: FVG_REGION_CODE,
        status: inFvg ? "enabled" : "unsupported",
      },
      events: {
        provider: "fvg-events",
        scope: FVG_REGION_CODE,
        status: inFvg ? "enabled" : "unsupported",
      },
    },
    community: {
      read: inItaly,
      readScope: "italy",
      write: communityWrite,
      writeScope: nationalCommunityEnabled ? "italy-local-pilot" : "pilot-regions",
      enabledRegions: nationalCommunityEnabled ? [...ITALIAN_REGION_CODES] : [FVG_REGION_CODE],
      reasonCode: communityWrite ? null : COMMUNITY_REGION_NOT_ENABLED_CODE,
      unavailableMessage: communityWrite
        ? ""
        : fur
          ? "Lis segnalazions partecipativis no son inmò ativis in cheste regjon."
          : "Le segnalazioni partecipative non sono ancora attive in questa regione.",
    },
    editorial: {
      followsWeatherLocation: false,
      regionCode: FVG_REGION_CODE,
      scopeId: PRODUCT_SCOPE.editorial,
    },
  };
}
