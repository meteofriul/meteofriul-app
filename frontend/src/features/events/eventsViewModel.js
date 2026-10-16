import {
  EVENTS_CATEGORY_FILTERS,
  EVENTS_TIME_TAB_IDS,
  getEventsBadgeCategoryLabel,
  getEventsCategoryFilterLabel,
  getEventsDateChipMonthLabel,
  getEventsTimeTabLabel,
  getEventsViewCopy,
} from "../../copy/eventsViewCopy";
import { getLocationDisplayName } from "../../domain/geo/locationDisplayName";
import { getDateTimeFormatter } from "../../domain/dateTimeFormatters.js";
import { API_BASE } from "../../services/apiConfig";

const MONTH_INDEX = {
  gen: 0,
  gennaio: 0,
  feb: 1,
  febbraio: 1,
  mar: 2,
  marzo: 2,
  apr: 3,
  aprile: 3,
  mag: 4,
  maggio: 4,
  giu: 5,
  giugno: 5,
  lug: 6,
  luglio: 6,
  ago: 7,
  agosto: 7,
  set: 8,
  sett: 8,
  settembre: 8,
  ott: 9,
  ottobre: 9,
  nov: 10,
  novembre: 10,
  dic: 11,
  dicembre: 11,
};

const UPCOMING_WINDOW_DAYS = 15;
const MS_PER_DAY = 24 * 60 * 60 * 1000;
const KNOWN_CATEGORY_IDS = new Set(
  EVENTS_CATEGORY_FILTERS.map((category) => category.id).filter((id) => id !== "all" && id !== "other"),
);
const EVENT_CATEGORY_RANK_BOOST = {
  famiglia: 26,
  food_wine: 24,
  mercato: 18,
  musica: 40,
  natura: 12,
  sagra: 45,
  sport: 32,
  cultura: 12,
  convegni: 8,
  other: 0,
};
const EVENT_SOURCE_RANK_BOOST = new Map([
  ["turismofvg", 10],
  ["sagrefvg", 10],
  ["pro loco fvg", 8],
  ["paesi in festa", 7],
  ["anteprima sagre", 7],
  ["eventifvg", 6],
]);

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function normalizeUiText(value) {
  return String(value || "")
    .replaceAll("VuÃª", "Vuê")
    .replaceAll("SAGRE / FIESTE LOCÃ‚L", "SAGRIS / FIESTIS LOCÂLS")
    .replaceAll("SAGRE / FIESTE LOCÂL", "SAGRIS / FIESTIS LOCÂLS")
    .replaceAll("MARCJÃ‚T", "MARCJÂT");
}

function removeDanglingTerminalQuote(value) {
  const text = String(value || "").trim();
  const lastChar = text.at(-1);

  if (lastChar === "\"") {
    const quoteCount = [...text].filter((char) => char === "\"").length;
    return quoteCount % 2 === 1 ? text.slice(0, -1).trimEnd() : text;
  }

  if (lastChar === "\u201d") {
    const openingCount = [...text].filter((char) => char === "\u201c").length;
    const closingCount = [...text].filter((char) => char === "\u201d").length;
    return closingCount > openingCount ? text.slice(0, -1).trimEnd() : text;
  }

  return text;
}

function normalizeEventTitle(value) {
  return removeDanglingTerminalQuote(normalizeUiText(value));
}

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function getDayDistance(start, end) {
  return Math.round((startOfDay(end).getTime() - startOfDay(start).getTime()) / MS_PER_DAY);
}

function getInclusiveDurationDays(range) {
  if (!range) return 1;
  return Math.max(1, getDayDistance(range.start, range.end) + 1);
}

function getUpcomingWeekendRange(today = new Date()) {
  const current = startOfDay(today);
  const day = current.getDay();
  const daysUntilSaturday = (6 - day + 7) % 7;
  const saturday = new Date(current);
  saturday.setDate(current.getDate() + daysUntilSaturday);
  const sunday = new Date(saturday);
  sunday.setDate(saturday.getDate() + 1);
  return { saturday, sunday };
}

function rangesOverlap(startA, endA, startB, endB) {
  return startA <= endB && endA >= startB;
}

export function parseEventDateRange(dateStr, { now = new Date() } = {}) {
  const text = normalizeText(dateStr);
  const year = now.getFullYear();
  const matches = [...text.matchAll(/\b(\d{1,2})(?:°|º)?\s+([a-zà-ÿ]+)(?:\s+(\d{4}))?\b/g)];

  if (!matches.length) return null;

  const dates = matches
    .map((match) => {
      const day = Number(match[1]);
      const month = MONTH_INDEX[match[2]];
      const parsedYear = Number(match[3] || year);

      if (!Number.isFinite(day) || month == null || !Number.isFinite(parsedYear)) return null;
      return new Date(parsedYear, month, day);
    })
    .filter(Boolean);

  if (!dates.length) return null;

  if (dates.length === 1) {
    const single = dates[0];
    const prefix = text.slice(0, text.indexOf(matches[0][0]));
    const dayMatches = [...prefix.matchAll(/\b(\d{1,2})(?:°|º)?\b/g)]
      .map((match) => Number(match[1]))
      .filter((day) => day >= 1 && day <= 31);

    if (dayMatches.length) {
      return {
        end: single,
        start: new Date(single.getFullYear(), single.getMonth(), dayMatches[0]),
      };
    }

    return { end: single, start: single };
  }

  return {
    end: dates[dates.length - 1],
    start: dates[0],
  };
}

export function classifyEventTime(dateStr, { now = new Date() } = {}) {
  if (!dateStr) return "outside";

  const low = normalizeText(dateStr);
  const range = parseEventDateRange(dateStr, { now });
  const today = startOfDay(now);

  if (low.includes("oggi") || low.includes("vuê")) return "today";
  if (low.includes("domani") || low.includes("doman")) return "next";
  if (!range) return "outside";

  const horizon = new Date(today);
  horizon.setDate(today.getDate() + UPCOMING_WINDOW_DAYS);
  if (range.end < today || range.start > horizon) return "outside";
  if (range.start <= today && range.end >= today) return "today";

  const { saturday, sunday } = getUpcomingWeekendRange(today);
  if (rangesOverlap(range.start, range.end, saturday, sunday)) return "weekend";

  return "next";
}

function normalizeSourceName(source) {
  return normalizeText(source);
}

function isSagraReviewSource(event) {
  const source = normalizeSourceName(event?.source);
  return source === "sagrefvg" ||
    source === "anteprima sagre" ||
    source === "paesi in festa" ||
    source === "pro loco fvg";
}

export function getEventFilterCategory(event) {
  const eventCategory = KNOWN_CATEGORY_IDS.has(event?.category) ? event.category : "other";
  if (isSagraReviewSource(event) && eventCategory === "food_wine") {
    return "sagra";
  }
  return eventCategory;
}

function getEventImageUrl(image) {
  if (!image) return "";

  if (String(image).startsWith("/api/")) {
    return `${API_BASE.replace(/\/api\/?$/, "")}${image}`;
  }

  return image;
}

function normalizeLocationToken(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function normalizeDedupeToken(value) {
  return normalizeLocationToken(value)
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function splitEventLocations(place) {
  return String(place || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function getActiveLocationCity(location) {
  return typeof location === "string" ? location.trim() : String(location?.city || "").trim();
}

function getLocalizedEventPlace(place, language) {
  return splitEventLocations(place)
    .map((part) => getLocationDisplayName(part, language))
    .join(", ");
}

function getMultiLocationLabel(place, { language = "it", location = null } = {}) {
  const parts = splitEventLocations(place);
  if (parts.length < 2) return "";

  const activeCity = getActiveLocationCity(location);
  if (!activeCity) return "";

  const normalizedActiveCity = normalizeLocationToken(activeCity);
  const matchingPart = parts.find((part) => normalizeLocationToken(part) === normalizedActiveCity);
  if (!matchingPart) return "";

  const suffix = getEventsViewCopy(language).multiLocationSuffix || "e altre localit\u00e0";
  return `${getLocationDisplayName(matchingPart, language)} ${suffix}`;
}

function formatEventDistance(event) {
  const rawDistance = event?.distance_km;
  if (
    (typeof rawDistance !== "number" && typeof rawDistance !== "string") ||
    (typeof rawDistance === "string" && !rawDistance.trim())
  ) return "";

  const distanceKm = Number(rawDistance);
  if (!Number.isFinite(distanceKm) || distanceKm <= 0) return "";

  const approximatePrefix = event?.distance_is_approximate === true ? "~" : "";

  if (distanceKm < 1) {
    const roundedMeters = Math.round(distanceKm * 10) * 100;
    if (roundedMeters <= 0) return `${approximatePrefix}<100 m`;
    if (roundedMeters > 0 && roundedMeters < 1000) {
      return `${approximatePrefix}${roundedMeters} m`;
    }
    return `${approximatePrefix}1 km`;
  }

  const distanceLabel = new Intl.NumberFormat("it-IT", {
    maximumFractionDigits: distanceKm < 10 ? 1 : 0,
  }).format(distanceKm);
  return `${approximatePrefix}${distanceLabel} km`;
}

function getEventLocationLabel(event, { language = "it", location = null } = {}) {
  const place = String(
    event?.display_mode === "umbrella"
      ? event?.location_label || event?.place || event?.event_city
      : event?.event_city || event?.place || event?.provider_place || event?.city || "",
  ).trim();

  if (!place || place.toLowerCase() === "data in aggiornamento") return "";

  const localizedPlace = getLocalizedEventPlace(place, language) || place;

  const distanceLabel = formatEventDistance(event);
  if (distanceLabel) return `${localizedPlace} · ${distanceLabel}`;

  const multiLocationLabel = getMultiLocationLabel(place, { language, location });
  if (multiLocationLabel) return multiLocationLabel;

  return localizedPlace;
}

function getSourceLabel(source) {
  if (!source) return "";
  if (source === "TurismoFVG") return "TurismoFVG";
  if (source === "SagreFVG") return "SagreFVG";
  if (source === "Pro Loco FVG") return "Pro Loco FVG";
  if (source === "Paesi in Festa") return "Paesi in Festa";
  if (source === "Anteprima Sagre") return "Anteprima Sagre";
  if (source === "EventiFVG") return "EventiFVG";
  return source;
}

function getCategoryLabel(event, language) {
  const languageKey = getLanguageKey(language);
  const fallback = getEventsBadgeCategoryLabel("other", languageKey);
  if (isSagraReviewSource(event) && (event.category === "sagra" || event.category === "food_wine")) {
    return getEventsBadgeCategoryLabel("sagra", languageKey);
  }

  const categoryLabel = getEventsBadgeCategoryLabel(event.category, languageKey, { fallback: false });
  if (categoryLabel) return categoryLabel;

  const label = event.category_label || fallback;
  const normalized = normalizeText(label);

  if (languageKey === "it") {
    if (normalized === "family" || normalized.includes("bambini")) return getEventsBadgeCategoryLabel("famiglia", languageKey);
    if (normalized === "food" || normalized.includes("wine")) return getEventsBadgeCategoryLabel("food_wine", languageKey);
    return label;
  }

  if (normalized.includes("sagra") || normalized.includes("festa")) return getEventsBadgeCategoryLabel("sagra", languageKey);
  if (normalized.includes("mercat") || normalized.includes("fier")) return getEventsBadgeCategoryLabel("mercato", languageKey);
  if (normalized.includes("enogastr") || normalized.includes("gusto") || normalized.includes("sapori")) {
    return getEventsBadgeCategoryLabel("food_wine", languageKey);
  }
  if (normalized.includes("musica") || normalized.includes("concert")) return getEventsBadgeCategoryLabel("musica", languageKey);
  if (normalized.includes("sport")) return getEventsBadgeCategoryLabel("sport", languageKey);
  if (normalized.includes("cultur") || normalized.includes("mostr") || normalized.includes("teatro")) {
    return getEventsBadgeCategoryLabel("cultura", languageKey);
  }
  if (normalized.includes("natura") || normalized.includes("escursion") || normalized.includes("cammin")) {
    return getEventsBadgeCategoryLabel("natura", languageKey);
  }
  if (normalized.includes("famiglia") || normalized.includes("family") || normalized.includes("bambini")) {
    return getEventsBadgeCategoryLabel("famiglia", languageKey);
  }
  if (normalized.includes("convegn")) return getEventsBadgeCategoryLabel("convegni", languageKey);

  return fallback;
}

function formatEventCivilDate(date, options) {
  // Event dates are civil calendar days, not instants. Copy their local fields
  // to UTC so reusable formatters never capture an obsolete device timezone.
  const civilDate = new Date(0);
  civilDate.setUTCFullYear(date.getFullYear(), date.getMonth(), date.getDate());
  return getDateTimeFormatter("it-IT", { ...options, timeZone: "UTC" }).format(civilDate);
}

export function formatEventDateChip(dateStr, language = "it", { now = new Date() } = {}) {
  const label = dateStr || getEventsViewCopy(language).dateFallbackToday;
  if (/^fino\s+al\s+\d{1,2}\s+[a-zà-ÿ]+\s+20\d{2}$/i.test(String(label).trim())) {
    return {
      accessibleLabel: normalizeUiText(label),
      compact: normalizeUiText(label),
      isRange: false,
      label: normalizeUiText(label),
    };
  }
  const range = parseEventDateRange(label, { now });

  if (!range) {
    const compact = normalizeUiText(String(label).replace(/^dal\s+/i, "").replace(/\s+al\s+/i, " - "));

    return {
      accessibleLabel: normalizeUiText(label),
      compact,
      isRange: false,
      label: normalizeUiText(label),
    };
  }

  const startMonth = getEventsDateChipMonthLabel(range.start.getMonth(), language);
  const endMonth = getEventsDateChipMonthLabel(range.end.getMonth(), language);
  const isRange = range.start.getTime() !== range.end.getTime();
  const preservesYear = /\b(?:19|20)\d{2}\b/.test(String(label));
  const startYear = preservesYear ? ` ${range.start.getFullYear()}` : "";
  const endYear = preservesYear ? ` ${range.end.getFullYear()}` : "";
  const accessibleLabel = isRange
    ? language === "fur"
      ? `${range.start.getDate()} ${startMonth}${startYear} - ${range.end.getDate()} ${endMonth}${endYear}`
      : `dal ${range.start.getDate()} ${formatEventCivilDate(range.start, { month: "long" })}${startYear} al ${range.end.getDate()} ${formatEventCivilDate(range.end, { month: "long" })}${endYear}`
    : language === "fur"
      ? `${range.start.getDate()} ${startMonth}${startYear}`
      : `${range.start.getDate()} ${formatEventCivilDate(range.start, { month: "long" })}${startYear}`;

  return {
    accessibleLabel,
    end: {
      day: String(range.end.getDate()),
      month: endMonth,
    },
    isRange,
    label: normalizeUiText(label),
    start: {
      day: String(range.start.getDate()),
      month: startMonth,
    },
  };
}

function getEventDateSortValue(record, now) {
  if (record.raw?.schedule_kind === "month_range" && /^\d{4}-\d{2}-\d{2}$/.test(record.raw?.sort_date || "")) {
    return new Date(`${record.raw.sort_date}T12:00:00`).getTime();
  }
  const range = parseEventDateRange(record.date, { now });
  return range?.start?.getTime?.() || Number.MAX_SAFE_INTEGER;
}

function getEventDedupeKey(record, now) {
  const titleKey = normalizeDedupeToken(record.title);
  if (!titleKey) return record.id || "";

  const range = parseEventDateRange(record.date, { now });
  const dateKey = range
    ? `${range.start.toISOString().slice(0, 10)}:${range.end.toISOString().slice(0, 10)}`
    : normalizeDedupeToken(record.date);

  const place = normalizeDedupeToken(record.raw?.event_city || record.raw?.place || record.location);
  const venue = normalizeDedupeToken(record.raw?.venue || record.raw?.address || "");
  const time = normalizeDedupeToken(record.raw?.time || record.raw?.start_time || "");
  return `${titleKey}|${dateKey}|${place}|${venue}|${time}`;
}

// Presentation grouping only: keep every occurrence and its source payload.
// A shared detail URL is required; title/poster similarity alone is not evidence.
export function groupEventOccurrences(records = [], allRecords = records) {
  const groups = new Map();
  const result = [];
  for (const record of allRecords) {
    const city = normalizeDedupeToken(record.raw?.event_city || record.raw?.place || record.location);
    const venue = normalizeDedupeToken(record.raw?.venue || record.raw?.address || "");
    let url = "";
    try {
      const parsed = new URL(record.url);
      if (["https:", "http:"].includes(parsed.protocol) && parsed.pathname !== "/") {
        parsed.hash = "";
        for (const key of [...parsed.searchParams.keys()]) {
          if (/^utm_/i.test(key)) parsed.searchParams.delete(key);
        }
        parsed.searchParams.sort();
        url = parsed.href;
      }
    } catch { /* No reliable identity: leave separate. */ }
    const key = url && city && record.title
      ? JSON.stringify([url, normalizeDedupeToken(record.title), city, venue, record.category]) : null;
    const existing = key && groups.get(key);
    if (existing) {
      existing.occurrences.push(record);
    } else {
      const group = { ...record, occurrences: [record] };
      result.push(group);
      if (key) groups.set(key, group);
    }
  }
  const visible = new Set(records);
  return result.filter((group) => group.occurrences.some((item) => visible.has(item)))
    .map((group) => ({ ...group, visibleOccurrences: group.occurrences.filter((item) => visible.has(item)) }));
}

export function getContextualEventsSummary(eventRecords = []) {
  const todayCount = groupEventOccurrences(
    eventRecords.filter((event) => event.timeCategory === "today"),
  ).length;
  const upcomingCount = groupEventOccurrences(
    eventRecords.filter((event) => ["weekend", "next"].includes(event.timeCategory)),
  ).length;

  return todayCount > 0
    ? { count: todayCount, period: "today", todayCount, upcomingCount }
    : { count: upcomingCount, period: "next", todayCount, upcomingCount };
}

function getLocationRankBoost(record, location) {
  const activeCity = getActiveLocationCity(location);
  if (!activeCity) return 0;

  const activeToken = normalizeLocationToken(activeCity);
  const programmeCity = record.raw?.display_mode === "umbrella"
    ? normalizeLocationToken(record.raw?.programme_city) : "";
  if (programmeCity && programmeCity === activeToken) return 180;
  const rawPlace = String(
    record.raw?.event_city ||
    record.raw?.place ||
    record.raw?.provider_place ||
    record.raw?.city ||
    "",
  );
  const places = splitEventLocations(rawPlace);
  const matchingPlace = places.find((place) => normalizeLocationToken(place) === activeToken);
  const singlePlace = places.length === 1 ? places[0] : "";

  if (singlePlace && normalizeLocationToken(singlePlace) === activeToken) return 180;
  if (matchingPlace) return 140;

  const distance = Number(record.raw?.distance_km);
  if (Number.isFinite(distance) && distance >= 0) {
    return Math.max(0, 120 - (distance * 8));
  }

  return 0;
}

function getEventRankScore(record, { location = null, now = new Date() } = {}) {
  const range = parseEventDateRange(record.date, { now });
  const today = startOfDay(now);
  const duration = getInclusiveDurationDays(range);
  const sourceKey = normalizeSourceName(record.source || record.raw?.source);
  let score = 0;

  if (record.timeCategory === "today") score += 600;
  else if (record.timeCategory === "weekend") score += 420;
  else if (record.timeCategory === "next") score += 250;
  else score -= 500;

  if (range) {
    const eventStart = startOfDay(range.start);
    const startsToday = eventStart.getTime() === today.getTime();
    const alreadyOngoing = eventStart < today && startOfDay(range.end) >= today;

    if (startsToday) score += 80;
    else if (alreadyOngoing) score += 20;

    if (duration > 14) score -= 170;
    else if (duration > 7) score -= 130;
    else if (duration > 3) score -= 55;
    else if (duration > 1) score -= 10;
  }

  score += getLocationRankBoost(record, location);
  if (record.localProgrammePriority) score += 300;
  score += EVENT_CATEGORY_RANK_BOOST[record.category] || 0;
  score += EVENT_SOURCE_RANK_BOOST.get(sourceKey) || 0;
  if (record.image) score += 12;
  if (record.url) score += 6;

  return score;
}

export function rankEventsForLocation(eventRecords = [], { location = null, now = new Date() } = {}) {
  const ranked = [...eventRecords].sort((first, second) => {
    const scoreDelta = getEventRankScore(second, { location, now }) - getEventRankScore(first, { location, now });
    if (scoreDelta) return scoreDelta;

    const dateDelta = getEventDateSortValue(first, now) - getEventDateSortValue(second, now);
    if (dateDelta) return dateDelta;

    const firstDuration = getInclusiveDurationDays(parseEventDateRange(first.date, { now }));
    const secondDuration = getInclusiveDurationDays(parseEventDateRange(second.date, { now }));
    if (firstDuration !== secondDuration) return firstDuration - secondDuration;

    return first.title.localeCompare(second.title, "it");
  });

  const seen = new Set();
  return ranked.filter((record) => {
    const key = getEventDedupeKey(record, now);
    if (!key) return true;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function sortEventsForTimeTab(eventRecords = [], tabId = "today", { now = new Date() } = {}) {
  if (tabId === "today") return eventRecords;

  return eventRecords
    .map((event, index) => ({ event, index }))
    .sort((first, second) => {
      const priorityDelta = Number(second.event.localProgrammePriority) - Number(first.event.localProgrammePriority);
      if (priorityDelta) return priorityDelta;
      const dateDelta = getEventDateSortValue(first.event, now) - getEventDateSortValue(second.event, now);
      if (dateDelta) return dateDelta;
      return first.index - second.index;
    })
    .map(({ event }) => event);
}

export function buildEventRecord(event, { language = "it", location = null, now = new Date() } = {}) {
  const category = getEventFilterCategory(event);
  const date = event?.date || event?.date_label || event?.dateLabel || event?.start_date || "";
  const endOnlyRange = event?.schedule_kind === "end_only"
    ? parseEventDateRange(date, { now }) : null;
  const monthRangeStatus = (() => {
    if (event?.schedule_kind !== "month_range") return null;
    const start = event?.start_date;
    const end = event?.end_date;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(start || "") || !/^\d{4}-\d{2}-\d{2}$/.test(end || "")) return "outside";
    const today = startOfDay(now);
    const horizon = new Date(today);
    horizon.setDate(today.getDate() + UPCOMING_WINDOW_DAYS);
    return new Date(`${end}T12:00:00`) >= today && new Date(`${start}T12:00:00`) <= horizon
      ? "next" : "outside";
  })();
  const occurrenceDates = (Array.isArray(event?.occurrences) ? event.occurrences : [])
    .filter(day => typeof day === "string" && /^\d{4}-\d{2}-\d{2}$/.test(day))
    .map(day => new Date(`${day}T12:00:00`))
    .filter(day => Number.isFinite(day.getTime()));
  const categories = occurrenceDates.map(day => classifyEventTime(
    formatEventCivilDate(day, { day: "numeric", month: "long", year: "numeric" }), { now },
  ));
  const occurrenceCategory = ["today", "weekend", "next"].find(value => categories.includes(value)) || "outside";
  const description = String(event?.description || "").trim();
  const excerpt = occurrenceDates.length ? description.replace(
    /^\s*\d{1,2}(?:\s*[,e]\s*\d{1,2})+\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\b(?:\s+20\d{2})?[\s:–—-]*/i, "",
  ) : description;
  const programmeCity = normalizeLocationToken(event?.programme_city);
  const localProgrammePriority = event?.display_mode === "umbrella"
    && Number(event?.active_session_count) > 0
    && Boolean(programmeCity)
    && programmeCity === normalizeLocationToken(getActiveLocationCity(location));

  return {
    category,
    categoryLabel: normalizeUiText(getCategoryLabel(event, language)),
    date,
    dateChip: formatEventDateChip(date, language, { now }),
    scheduleLabel: occurrenceDates.length
      ? `${language === "fur" ? "Zornadis" : "Giornate"}: ${occurrenceDates.map(day => formatEventCivilDate(day, { day: "numeric", month: "short" })).join(" · ")}`
      : "",
    excerpt,
    id: event?.id || event?.url || event?.title || "",
    image: getEventImageUrl(event?.image),
    localProgrammePriority,
    location: normalizeUiText(getEventLocationLabel(event, { language, location })),
    raw: event,
    source: getSourceLabel(event?.source),
    timeCategory: monthRangeStatus || (event?.schedule_kind === "end_only"
      ? endOnlyRange?.end >= startOfDay(now) ? "next" : "outside"
      : event?.preview_outside_window
      ? "next"
      : occurrenceDates.length ? occurrenceCategory : classifyEventTime(date, { now })),
    title: normalizeEventTitle(event?.title || event?.name || ""),
    url: event?.url || "",
  };
}

export function buildEventsViewModel(
  dataState = {},
  {
    language = "it",
    location = null,
    now = new Date(),
  } = {},
) {
  const languageKey = getLanguageKey(language);
  const copy = getEventsViewCopy(languageKey);
  const items = Array.isArray(dataState.items) ? dataState.items : [];
  const eventRecords = rankEventsForLocation(
    items.map((event) => buildEventRecord(event, { language: languageKey, location, now })),
    { location, now },
  );
  const hasItems = eventRecords.length > 0;
  const isLoading = Boolean(dataState.isRefreshing && !hasItems);
  const message = (() => {
    if (isLoading) return copy.loadingBody;
    if (dataState.error && hasItems) return languageKey === "fur" ? "O mostri i evenis salvats." : "Mostro gli eventi salvati.";
    if (dataState.isPartial || dataState.shouldRetry) return copy.loadingBody;
    if (dataState.error && !hasItems) return copy.emptyBody;
    return "";
  })();

  return {
    categories: EVENTS_CATEGORY_FILTERS.map((category) => ({
      id: category.id,
      label: getEventsCategoryFilterLabel(category.id, languageKey),
    })),
    copy,
    countLabel: `${Number(dataState.total || eventRecords.length)} ${copy.eventCountLabel}`,
    error: dataState.error || null,
    hasLocation: Boolean(location?.city),
    isLoading,
    items: eventRecords,
    locationLabel: getLocationDisplayName(location, languageKey),
    message,
    status: dataState.status || "empty",
    tabs: EVENTS_TIME_TAB_IDS.map((id) => ({
      id,
      label: getEventsTimeTabLabel(id, languageKey, { short: true }),
    })),
    total: Number(dataState.total || eventRecords.length),
  };
}
