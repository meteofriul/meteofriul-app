import archive from "../../data/discover/localMemory.json";
import { FIXED_FVG_PLACES } from "../../data/fvgPlaces";

const DAY_MS = 24 * 60 * 60 * 1000;
const FUR_MONTHS = [
  "Zen\u00e2r",
  "Fevr\u00e2r",
  "Mar\u00e7",
  "Avr\u00eel",
  "Mai",
  "Jugn",
  "Lui",
  "Avost",
  "Setembar",
  "Otubar",
  "Novembar",
  "Dicembar",
];

const CATEGORY_ALIASES = Object.freeze({
  architettura: "cultura",
  arte: "cultura",
  arte_cultura: "cultura",
  design: "cultura",
  letteratura: "cultura",
  lingua_cultura: "cultura",
  memoria_storica: "storia",
  musica: "cultura",
  scienza_territorio: "scienza",
  storia_cultura: "storia",
  territorio: "scienza",
});

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

function localizedValue(value, language) {
  if (!value || typeof value !== "object") return "";
  return value[language] || value.it || value.fur || "";
}

function normalizeAreaToken(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ");
}

function addAreaToken(tokens, value) {
  const token = normalizeAreaToken(value);
  if (!token) return;

  tokens.add(token);
  tokens.add(token.replace(/\s+/g, "_"));
  tokens.add(token.replace(/\s+/g, "-"));
}

function findFixedPlace(location) {
  const city = normalizeAreaToken(location?.city || location?.name);
  if (!city) return null;

  return Object.values(FIXED_FVG_PLACES).find((place) => normalizeAreaToken(place.name) === city) || null;
}

function getLocationProfile(location) {
  const fixedPlace = findFixedPlace(location);
  const cityTokens = new Set();
  const provinceTokens = new Set();

  addAreaToken(cityTokens, location?.city);
  addAreaToken(cityTokens, location?.name);
  addAreaToken(cityTokens, fixedPlace?.name);
  addAreaToken(provinceTokens, location?.province);
  addAreaToken(provinceTokens, location?.provinceName);
  addAreaToken(provinceTokens, fixedPlace?.province);
  addAreaToken(provinceTokens, fixedPlace?.provinceName);

  return {
    cityLabel: String(location?.city || location?.name || fixedPlace?.name || "").trim(),
    cityTokens,
    istatCode: String(location?.istatCode || fixedPlace?.istatCode || "").trim(),
    provinceCode: String(location?.province || fixedPlace?.province || "").trim().toUpperCase(),
    provinceLabel: String(location?.provinceName || fixedPlace?.provinceName || "").trim(),
    provinceTokens,
  };
}

function getLocationAreaTokens(location) {
  const profile = getLocationProfile(location);
  return new Set([...profile.cityTokens, ...profile.provinceTokens]);
}

function recordMatchesAreaTokens(record, areaTokens) {
  if (!areaTokens.size) return false;
  const areas = Array.isArray(record?.areas) ? record.areas : [];
  if (!areas.length) return false;

  return areas.some((area) => areaTokens.has(normalizeAreaToken(area)) || areaTokens.has(String(area || "").trim().toLowerCase()));
}

function recordMatchesLocationTokens(record, locationTokens) {
  if (!locationTokens.size) return true;
  return recordMatchesAreaTokens(record, locationTokens);
}

function getRecordLocationScope(record, profile) {
  const targets = Array.isArray(record?.localityFocus?.targets)
    ? record.localityFocus.targets
    : [];

  if (profile.istatCode && targets.some((target) => (
    target?.scope === "municipality" && String(target.istatCode || "") === profile.istatCode
  ))) return "city";

  if (profile.provinceCode && targets.some((target) => (
    target?.scope === "province" && String(target.code || "").toUpperCase() === profile.provinceCode
  ))) return "province";

  return targets.some((target) => target?.scope === "region" && target?.code === "FVG")
    ? "region"
    : null;
}

function getLocationScopeLabel(scope, profile) {
  if (scope === "city" && profile.cityLabel) return profile.cityLabel;
  if (scope === "province" && profile.provinceLabel) {
    return [profile.provinceCode, profile.provinceLabel].filter(Boolean).join(" · ");
  }
  return "Friuli Venezia Giulia";
}

function getStableTextHash(value) {
  return Array.from(String(value || "")).reduce(
    (hash, character) => ((hash * 31) + character.charCodeAt(0)) >>> 0,
    0,
  );
}

function getRecords(source = archive) {
  return Array.isArray(source?.records) ? source.records : [];
}

function normalizeDateKey(date) {
  if (typeof date === "string") {
    const isoMatch = date.match(/^\d{4}-(\d{2})-(\d{2})/);
    if (isoMatch) return `${isoMatch[1]}-${isoMatch[2]}`;

    const monthDayMatch = date.match(/^(\d{2})-(\d{2})$/);
    if (monthDayMatch) return date;
  }

  const parsedDate = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(parsedDate.getTime())) return null;

  const month = String(parsedDate.getMonth() + 1).padStart(2, "0");
  const day = String(parsedDate.getDate()).padStart(2, "0");
  return `${month}-${day}`;
}

function formatDateKeyLabel(dateKey, language) {
  const match = String(dateKey || "").match(/^(\d{2})-(\d{2})$/);
  if (!match) return String(dateKey || "");

  const monthIndex = Number(match[1]) - 1;
  const day = Number(match[2]);
  const parsedDate = new Date(Date.UTC(2000, monthIndex, day));
  const isValidDate = monthIndex >= 0
    && monthIndex < 12
    && day > 0
    && parsedDate.getUTCMonth() === monthIndex
    && parsedDate.getUTCDate() === day;

  if (!isValidDate) return dateKey;
  if (getLanguageKey(language) === "fur") return `${day} di ${FUR_MONTHS[monthIndex]}`;

  return new Intl.DateTimeFormat("it-IT", {
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(parsedDate);
}

function dayOfYear(date) {
  const parsedDate = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(parsedDate.getTime())) return 0;
  const start = Date.UTC(parsedDate.getFullYear(), 0, 0);
  const current = Date.UTC(parsedDate.getFullYear(), parsedDate.getMonth(), parsedDate.getDate());
  return Math.floor((current - start) / DAY_MS);
}

function isUiReady(record) {
  if (!record || record.readyForUi !== true) return false;
  if (record.primaryUse !== "discover") return false;
  if (record.editorialStatus !== "ready_for_discover") return false;

  const sourceType = record.source?.type;
  return sourceType === "verified_source" || sourceType === "editorial_note";
}

function isFurReady(record) {
  return record?.languageStatus?.fur === "approved";
}

function isSecondaryMemory(record) {
  return record?.dailyRole === "secondary";
}

function isLocalityFocusReady(record) {
  return record?.localityFocus?.temporal === "evergreen"
    && Array.isArray(record.localityFocus.targets)
    && record.localityFocus.targets.length > 0;
}

function compareRecords(first, second) {
  const priorityDiff = Number(first.priority || 99) - Number(second.priority || 99);
  if (priorityDiff) return priorityDiff;
  return String(first.id).localeCompare(String(second.id));
}

function getCategoryLabel(record, source, language) {
  const category = record?.category || "storia";
  const categoryKey = CATEGORY_ALIASES[category] || category;
  return localizedValue(source?.categories?.[categoryKey], language) || category.replaceAll("_", " ");
}

function buildLocalMemoryCard(record, source, language, dateLabel, selectionKind, extra = {}) {
  const languageKey = getLanguageKey(language);
  const canUseRequestedLanguage = languageKey !== "fur" || isFurReady(record);
  const contentLanguage = canUseRequestedLanguage ? languageKey : "it";

  return {
    id: record.id,
    contentKey: record.candidateId || record.id,
    title: localizedValue(record.title, contentLanguage),
    text: localizedValue(record.summary, contentLanguage),
    type: record.category,
    typeLabel: getCategoryLabel(record, source, languageKey),
    dailyRole: record.dailyRole || "primary",
    seasonLabel: formatDateKeyLabel(dateLabel, languageKey),
    selectionKind,
    sourceLabel: record.source?.label || "",
    sourceNote: record.source?.url || "",
    isFurPending: languageKey === "fur" && !canUseRequestedLanguage,
    ...extra,
  };
}

export function getLocalMemorySummary(source = archive) {
  const records = getRecords(source);
  const readyLocalityFocusRecords = records.filter((record) => isUiReady(record) && isLocalityFocusReady(record));
  const categoryCounts = records.reduce((counts, record) => {
    const key = record.category || "uncategorized";
    return { ...counts, [key]: (counts[key] || 0) + 1 };
  }, {});

  return {
    totalRecords: records.length,
    readyForDiscoverRecords: records.filter(isUiReady).length,
    sourceNeededRecords: records.filter((record) => record.editorialStatus === "source_needed").length,
    sourceCandidateRecords: records.filter((record) => record.editorialStatus === "source_candidate").length,
    sourceVerifiedRecords: records.filter((record) => record.editorialStatus === "source_verified").length,
    copyDraftItRecords: records.filter((record) => record.languageStatus?.it === "copy_draft").length,
    copyDraftFurRecords: records.filter((record) => record.languageStatus?.fur === "copy_draft_pending_review").length,
    approvedItRecords: records.filter((record) => record.languageStatus?.it === "approved").length,
    approvedFurRecords: records.filter((record) => record.languageStatus?.fur === "approved").length,
    furHumanReviewNeededRecords: records.filter((record) => record.languageStatus?.fur === "human_review_needed").length,
    exactDateRecords: records.filter((record) => Array.isArray(record.dateAnchors) && record.dateAnchors.length > 0).length,
    localityFocusReadyRecords: readyLocalityFocusRecords.length,
    localityFocusProvinceCodes: Array.from(new Set(readyLocalityFocusRecords.flatMap((record) => (
      record.localityFocus.targets
        .filter((target) => target.scope === "province")
        .map((target) => target.code)
    )))).sort(),
    categories: categoryCounts,
  };
}

export function getLocalMemoryForDate({
  date = new Date(),
  language = "it",
  source = archive,
} = {}) {
  const languageKey = getLanguageKey(language);
  const dateKey = normalizeDateKey(date);
  if (!dateKey) return null;

  const readyRecords = getRecords(source)
    .filter((record) => (
      isUiReady(record) &&
      !isSecondaryMemory(record) &&
      (languageKey !== "fur" || isFurReady(record))
    ))
    .sort(compareRecords);
  const exactRecords = readyRecords.filter((record) => record.dateAnchors?.includes(dateKey));
  const selectedExact = exactRecords[0] || null;

  if (selectedExact) {
    return buildLocalMemoryCard(selectedExact, source, language, dateKey, "exact_date");
  }

  const rotatingRecords = readyRecords.filter((record) => !record.dateAnchors?.length);
  if (!rotatingRecords.length) return null;

  const selectedRotation = rotatingRecords[dayOfYear(date) % rotatingRecords.length];
  return buildLocalMemoryCard(selectedRotation, source, language, dateKey, "rotation");
}

export function getLocalMemorySecondaryForDate({
  date = new Date(),
  language = "it",
  location = null,
  source = archive,
  limit = 3,
} = {}) {
  const languageKey = getLanguageKey(language);
  const dateKey = normalizeDateKey(date);
  if (!dateKey) return [];

  const locationTokens = getLocationAreaTokens(location);
  const secondaryRecords = getRecords(source)
    .filter((record) => (
      isUiReady(record) &&
      isSecondaryMemory(record) &&
      record.dateAnchors?.includes(dateKey) &&
      (languageKey !== "fur" || isFurReady(record)) &&
      recordMatchesLocationTokens(record, locationTokens)
    ))
    .sort(compareRecords);

  const cards = secondaryRecords.map((record) => (
    buildLocalMemoryCard(record, source, language, dateKey, "exact_date_secondary")
  ));

  return typeof limit === "number" ? cards.slice(0, limit) : cards;
}

export function getLocalMemoryForLocation({
  date = new Date(),
  excludeIds = [],
  language = "it",
  location = null,
  source = archive,
} = {}) {
  const languageKey = getLanguageKey(language);
  const profile = getLocationProfile(location);
  const excluded = excludeIds instanceof Set ? excludeIds : new Set(excludeIds);
  const readyRecords = getRecords(source)
    .filter((record) => (
      isUiReady(record) &&
      isLocalityFocusReady(record) &&
      !excluded.has(record.id) &&
      !excluded.has(record.candidateId) &&
      (languageKey !== "fur" || isFurReady(record))
    ))
    .sort((first, second) => {
      const localityPriorityDiff = Number(first.localityFocus?.priority || 99)
        - Number(second.localityFocus?.priority || 99);
      return localityPriorityDiff || compareRecords(first, second);
    });

  for (const scope of ["city", "province", "region"]) {
    const candidates = readyRecords.filter((record) => getRecordLocationScope(record, profile) === scope);
    if (!candidates.length) continue;

    const locationKey = profile.cityLabel || profile.provinceLabel || "friuli-venezia-giulia";
    const selectedIndex = (dayOfYear(date) + getStableTextHash(locationKey)) % candidates.length;
    const selected = candidates[selectedIndex];
    const scopeLabel = getLocationScopeLabel(scope, profile);

    return buildLocalMemoryCard(
      selected,
      source,
      language,
      scopeLabel,
      "location_focus",
      {
        locationScope: scope,
        locationLabel: scopeLabel,
        visualKind: "location",
      },
    );
  }

  return null;
}

export function getLocalMemoryRecords(source = archive) {
  return getRecords(source);
}
