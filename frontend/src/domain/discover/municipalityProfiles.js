import { FIXED_FVG_PLACES, FVG_PLACES_SOURCE } from "../../data/fvgPlaces";
import profilesArchive from "../../data/discover/municipalityProfiles.json";
import milestoneSources from "../../data/discover/municipalityMilestoneSources.json";
import { getLocationDisplayName } from "../geo/locationDisplayName";

const ISTAT_MUNICIPALITIES_URL = "https://www.istat.it/classificazione/codici-dei-comuni-delle-province-e-delle-regioni/";

const PROVINCE_NAMES_FUR = Object.freeze({
  GO: "Gurize",
  PN: "Pordenon",
  TS: "Triest",
  UD: "Udin",
});

const READY_EDITORIAL_STATUSES = new Set(["pilot_ready", "reviewed", "registry_ready"]);
const READY_SOURCE_TYPES = new Set([
  "official_municipality",
  "national_institution",
  "regional_institution",
  "cultural_institution",
  "wikipedia_reference",
  "official_registry",
]);

const ROMAN_DIGITS = Object.freeze({
  I: 1,
  V: 5,
  X: 10,
  L: 50,
  C: 100,
  D: 500,
  M: 1000,
});

function parseRomanNumeral(value) {
  const token = String(value || "").toUpperCase();
  let total = 0;

  for (let index = 0; index < token.length; index += 1) {
    const current = ROMAN_DIGITS[token[index]];
    const next = ROMAN_DIGITS[token[index + 1]] || 0;
    if (!current) return null;
    total += current < next ? -current : current;
  }

  return total || null;
}

function isStandaloneRomanOne(value, offset, fullText) {
  const precedingCharacter = fullText[offset - 1];
  const followingCharacter = fullText[offset + value.length];
  if (followingCharacter === "'" || followingCharacter === "’") return false;
  if (precedingCharacter === "." && followingCharacter === ".") return false;

  if (value !== "I") return true;

  const before = fullText.slice(Math.max(0, offset - 28), offset);
  const after = fullText.slice(offset + value.length, offset + value.length + 28);
  if (/Ecomuse[ou]\s*$/i.test(before) && /^\s+Mistîrs\b/.test(after)) return false;
  return /(?:secol|secui)\s*$/i.test(before)
    || /^(?:\s*[-–]\s*[IVXLCDM]+|\s+(?:secolo|secul|secui)\b)/i.test(after)
    || /[A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'’.-]+\s+$/.test(before);
}

function formatHistoricalText(value, languageKey) {
  const text = String(value || "");

  return text.replace(/(?<![\p{L}\p{N}])[IVXLCDM]+(?![\p{L}\p{N}])/gu, (token, offset) => {
    if (!isStandaloneRomanOne(token, offset, text)) return token;
    const number = parseRomanNumeral(token);
    if (!number) return token;
    return languageKey === "fur" ? String(number) : `${number}°`;
  });
}

function formatHistoricalPeriod(value, languageKey) {
  if (typeof value === "number") return value;

  const text = String(value || "").trim();
  const qualifiedCentury = text.match(/^(fine|inizio)\s+([IVXLCDM]+)$/i);
  if (qualifiedCentury) {
    const number = parseRomanNumeral(qualifiedCentury[2]);
    if (!number) return text;
    if (languageKey === "fur") {
      return qualifiedCentury[1].toLowerCase() === "fine"
        ? `Ae fin dal secul ${number}`
        : `Al inizi dal secul ${number}`;
    }
    return `${qualifiedCentury[1].toLowerCase()} ${number}°`;
  }

  const centuryRange = text.match(/^([IVXLCDM]+)(?:\s*[-–]\s*([IVXLCDM]+))?$/);
  if (!centuryRange) return formatHistoricalText(text, languageKey);

  const first = parseRomanNumeral(centuryRange[1]);
  const second = centuryRange[2] ? parseRomanNumeral(centuryRange[2]) : null;
  if (!first || (centuryRange[2] && !second)) return text;

  if (languageKey === "fur") {
    return second ? `Secui ${first}-${second}` : `Secul ${first}`;
  }

  return second ? `${first}°-${second}° sec.` : `${first}° sec.`;
}

function normalizePlaceName(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function getArchiveProfiles(source = profilesArchive) {
  return Array.isArray(source?.profiles) ? source.profiles : [];
}

function buildRegistryProfile(slug, place) {
  const provinceNameFur = PROVINCE_NAMES_FUR[place.province] || place.provinceName;

  return {
    id: `municipality-profile-${slug}`,
    istatCode: place.istatCode,
    municipality: place.name,
    province: place.province,
    aliases: [place.name],
    title: {
      it: `Un primo sguardo a ${place.name}`,
      fur: `Un prin sguart a ${place.name}`,
    },
    summary: {
      it: `${place.name} è un comune del Friuli Venezia Giulia, nell'area di ${place.provinceName}. La scheda presenta la località e apre alle memorie e alle tradizioni del suo territorio.`,
      fur: `${place.name} al è un comun dal Friûl Vignesie Julie, inte aree di ${provinceNameFur}. La schede e presente la localitât e e vierç lis memoriis e lis tradizions dal so teritori.`,
    },
    milestones: [],
    source: {
      label: "ISTAT - Codici delle unità amministrative",
      type: "official_registry",
      url: ISTAT_MUNICIPALITIES_URL,
      dataset: FVG_PLACES_SOURCE.municipalities,
    },
    languageStatus: {
      it: "approved",
      fur: "approved",
    },
    editorialStatus: "registry_ready",
    profileTier: "registry",
    readyForUi: true,
  };
}

function buildDefaultProfiles() {
  const editorialByIstatCode = new Map(
    getArchiveProfiles().map((profile) => [profile.istatCode, profile]),
  );

  return Object.entries(FIXED_FVG_PLACES).map(([slug, place]) => {
    const editorialProfile = editorialByIstatCode.get(place.istatCode);

    if (editorialProfile) {
      return {
        ...editorialProfile,
        profileTier: "editorial",
      };
    }

    return buildRegistryProfile(slug, place);
  });
}

const DEFAULT_PROFILES = Object.freeze(buildDefaultProfiles());

function getProfiles(source) {
  if (source !== undefined) return getArchiveProfiles(source);
  return DEFAULT_PROFILES;
}

function isLanguageReady(profile, language) {
  return profile?.languageStatus?.[language] === "approved";
}

function isProfileReady(profile, language) {
  return profile?.readyForUi === true
    && READY_EDITORIAL_STATUSES.has(profile?.editorialStatus)
    && READY_SOURCE_TYPES.has(profile?.source?.type)
    && isLanguageReady(profile, language);
}

function findProfile(location, source) {
  const profiles = getProfiles(source);
  const istatCode = String(location?.istatCode || "").trim();

  if (istatCode) {
    const exactIstatProfile = profiles.find((profile) => profile.istatCode === istatCode);
    if (exactIstatProfile) return exactIstatProfile;
  }

  const cityKey = normalizePlaceName(location?.city);
  if (!cityKey) return null;

  return profiles.find((profile) => (
    normalizePlaceName(profile.municipality) === cityKey
    || (profile.aliases || []).some((alias) => normalizePlaceName(alias) === cityKey)
  )) || null;
}

export function getMunicipalityProfile({
  language = "it",
  location = null,
  source,
} = {}) {
  const languageKey = language === "fur" ? "fur" : "it";
  const profile = findProfile(location, source);

  if (!profile || !isProfileReady(profile, languageKey)) return null;

  const locationLabel = getLocationDisplayName(
    { city: profile.municipality, istatCode: profile.istatCode },
    languageKey,
  );

  return {
    id: profile.id,
    contentKey: profile.id,
    title: formatHistoricalText(profile.title[languageKey], languageKey),
    text: formatHistoricalText(profile.summary[languageKey], languageKey),
    type: "municipality",
    typeLabel: languageKey === "fur" ? "Il comun" : "Il comune",
    seasonLabel: locationLabel,
    selectionKind: "municipality_profile",
    sourceLabel: profile.source.label,
    sourceNote: profile.source.url,
    sourceType: profile.source.type,
    visualKind: "municipality",
    locationScope: "city",
    locationLabel,
    province: profile.province,
    istatCode: profile.istatCode,
    profileTier: profile.profileTier || "editorial",
    milestones: (profile.milestones || []).map((milestone) => ({
      id: milestone.id,
      period: formatHistoricalPeriod(milestone.year || milestone.century, languageKey),
      label: formatHistoricalText(milestone.label[languageKey], languageKey),
      source: milestone.source || milestoneSources[milestone.id] || profile.source,
      supportingSources: milestone.supportingSources || [],
    })),
  };
}

export function getMunicipalityProfileRecords(source) {
  return getProfiles(source);
}
