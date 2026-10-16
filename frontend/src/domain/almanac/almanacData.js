import earthTips from "../../data/almanac/earthTips.json";
import proverbs from "../../data/almanac/proverbs.json";
import saintProfiles from "../../data/almanac/saintProfiles.json";
import saints from "../../data/almanac/saints.json";
import schedule from "../../data/almanac/schedule.json";
import culturalItems from "../../data/ostermannCulturalDiscover.json";
import {
  getDiscoverTemporalRank,
  normalizeDiscoverSeason,
} from "../discover/discoverTemporalSelection";
import { getMoonPhase } from "./moonPhase";
import { getSunCycle } from "./sunCycle";

const DAY_MS = 24 * 60 * 60 * 1000;
const DEFAULT_LOCATION = {
  latitude: 46.0711,
  longitude: 13.2346,
  timeZone: "Europe/Rome",
};

const SEASON_STARTS = [
  { id: "spring", month: 2, day: 20 },
  { id: "summer", month: 5, day: 21 },
  { id: "autumn", month: 8, day: 22 },
  { id: "winter", month: 11, day: 21 },
];

const SEASON_LABELS = {
  it: {
    autumn: "Autunno",
    spring: "Primavera",
    summer: "Estate",
    winter: "Inverno",
  },
  fur: {
    autumn: "Sierade",
    spring: "Primevere",
    summer: "Istat",
    winter: "Invier",
  },
};

const PROVERB_TARGETS = {
  DATED: "almanac_dated",
  DATE_RANGE: "almanac_date_range",
  MONTHLY: "almanac_monthly",
  MOVABLE_FEAST: "almanac_movable_feast",
  SEASONAL: "almanac_seasonal",
  WEATHER_SIGN: "almanac_weather_sign",
  LUNAR_CYCLE: "almanac_lunar_cycle",
};

const DATE_BOUND_PROVERB_CATEGORIES = new Set([
  "almanacco_santi",
  "calendario_vendemmia",
]);

function toDate(value) {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? new Date() : date;
}

function formatAlmanacKey(date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return {
    dayKey: `${month}-${day}`,
    monthKey: month,
  };
}

function getDayOfYear(date) {
  const start = Date.UTC(date.getFullYear(), 0, 1);
  const current = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());

  return Math.floor((current - start) / DAY_MS) + 1;
}

function getSeasonStartDate(year, season) {
  return new Date(year, season.month, season.day);
}

function getSeasonInfo(date, language = "it") {
  const year = date.getFullYear();
  const current = new Date(date);
  current.setHours(0, 0, 0, 0);
  const starts = SEASON_STARTS.map((season) => ({
    ...season,
    start: getSeasonStartDate(year, season),
  }));
  let active = starts[starts.length - 1];

  for (const season of starts) {
    if (current >= season.start) active = season;
  }

  if (active.id === "winter" && current < starts[0].start) {
    active = {
      ...SEASON_STARTS[3],
      start: getSeasonStartDate(year - 1, SEASON_STARTS[3]),
    };
  }

  const currentUtc = Date.UTC(current.getFullYear(), current.getMonth(), current.getDate());
  const activeUtc = Date.UTC(active.start.getFullYear(), active.start.getMonth(), active.start.getDate());
  const day = Math.floor((currentUtc - activeUtc) / DAY_MS) + 1;
  const labels = SEASON_LABELS[language === "fur" ? "fur" : "it"];

  return {
    day,
    id: active.id,
    label: labels[active.id],
  };
}

function getLocalizedField(value, language = "it") {
  if (!value || typeof value !== "object") return "";
  return value[language] && value[language] !== "pending_review" ? value[language] : value.it || value.fur || "";
}

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

export function getWeatherAlmanacTags(weather = {}) {
  const source = weather || {};
  const condition = normalizeText(source.condition || source.summary || source.label);
  const temperature = Number(source.temperature ?? source.temperatureC);
  const windSpeed = Number(source.windSpeed ?? source.windKmh);
  const tags = new Set();

  if (condition.includes("tempor")) tags.add("temporale");
  if (condition.includes("grand")) tags.add("grandine");
  if (condition.includes("piogg") || condition.includes("pluie") || condition.includes("ploie")) tags.add("pioggia");
  if (
    condition.includes("nubi") ||
    condition.includes("nuvol") ||
    condition.includes("coperto") ||
    condition.includes("velatur")
  ) tags.add("nubi");
  if (condition.includes("nebb") || condition.includes("fosch") || condition.includes("brume")) tags.add("nebbia");
  if (condition.includes("neve") || condition.includes("nêf") || condition.includes("nef")) tags.add("neve");
  if (condition.includes("gelo") || Number.isFinite(temperature) && temperature <= 2) tags.add("gelo");
  if (condition.includes("sole") || condition.includes("sereno") || Number.isFinite(temperature) && temperature >= 28) {
    tags.add("caldo");
    tags.add("irrigazione");
    tags.add("orto");
    tags.add("sole");
  }
  if (condition.includes("garbin")) tags.add("garbino");
  if (condition.includes("bora")) tags.add("bora");
  if (condition.includes("vento") || condition.includes("vint") || condition.includes("bora") || windSpeed >= 30) {
    tags.add("vento");
    tags.add("sostegni");
    tags.add("prudenza");
  }

  return [...tags];
}

function isEligibleCulturalItem(item) {
  return (
    item?.section === "almanacco" &&
    item.editorialStatus !== "archive" &&
    item.editorialStatus !== "excluded"
  );
}

function matchesAlmanacPeriod(item, date) {
  const { monthKey } = formatAlmanacKey(date);
  const season = normalizeDiscoverSeason(getSeasonInfo(date).id);
  const months = Array.isArray(item.months) ? item.months : [];
  const seasons = (Array.isArray(item.seasons) ? item.seasons : [])
    .map(normalizeDiscoverSeason)
    .filter(Boolean);

  if (months.length && !months.includes(monthKey)) return false;
  if (seasons.length && !seasons.includes("all") && !seasons.includes(season)) return false;

  return true;
}

function pickFromPool(items, date, maxWindow = 7) {
  if (!items.length) return null;

  const sorted = [...items].sort((first, second) => Number(second.priority || 0) - Number(first.priority || 0));
  const topPriority = Number(sorted[0]?.priority || 0);
  const pool = sorted.filter((item) => topPriority - Number(item.priority || 0) <= 2).slice(0, maxWindow);

  return pool[getDayOfYear(date) % pool.length] || sorted[0];
}

export function pickDailyTradition(date, weather = null) {
  const effectiveDate = toDate(date);
  const weatherTags = new Set(getWeatherAlmanacTags(weather));
  const items = Array.isArray(culturalItems) ? culturalItems.filter(isEligibleCulturalItem) : [];
  const rankedItems = items
    .map((item) => ({ item, rank: getDiscoverTemporalRank(item, effectiveDate) }))
    .filter(({ rank }) => rank !== null);
  const contextualRank = rankedItems
    .filter(({ rank }) => rank < 3)
    .reduce((best, { rank }) => Math.min(best, rank), Number.POSITIVE_INFINITY);
  const contextualItems = Number.isFinite(contextualRank)
    ? rankedItems.filter(({ rank }) => rank === contextualRank).map(({ item }) => item)
    : [];

  if (contextualItems.length) return pickFromPool(contextualItems, effectiveDate, 3);

  if (weatherTags.size) {
    const weatherItems = items.filter((item) => (
      item.recurrence === "weather" &&
      matchesAlmanacPeriod(item, effectiveDate) &&
      Array.isArray(item.weatherTags) &&
      item.weatherTags.some((tag) => weatherTags.has(tag))
    ));
    const selected = pickFromPool(weatherItems, effectiveDate);
    if (selected) return selected;
  }

  const periodItems = rankedItems
    .filter(({ item, rank }) => (
      rank >= 3 &&
      item.recurrence !== "weather" &&
      matchesAlmanacPeriod(item, effectiveDate)
    ))
    .map(({ item }) => item);

  return pickFromPool(periodItems, effectiveDate);
}

function getProverbById(id) {
  return Array.isArray(proverbs) ? proverbs.find((item) => item.id === id) || null : null;
}

function listIncludes(value, expected) {
  return Array.isArray(value) && value.includes(expected);
}

function matchesSeason(item, season) {
  if (!Array.isArray(item.seasons) || item.seasons.length === 0) return true;
  return item.seasons.includes("all") || item.seasons.includes(season);
}

function matchesLunarCalendarRule(item, date) {
  const rule = item.lunarRule;
  if (!rule) return false;
  if (rule.type === "any_lunar_day") return true;
  if (rule.type !== "first_tuesday_of_lunation") return false;

  const moon = getMoonPhase(date);
  const maxMoonAgeDays = Number(rule.maxMoonAgeDays || 7);

  return date.getDay() === 2 && moon.age >= 0 && moon.age <= maxMoonAgeDays;
}

function getGregorianEasterDate(year) {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;

  return new Date(year, month - 1, day, 12);
}

function matchesMovableFeast(item, date) {
  const rules = Array.isArray(item.movableFeasts) ? item.movableFeasts : [];

  return rules.some((rule) => {
    if (rule?.id !== "easter") return false;

    const feastDate = getGregorianEasterDate(date.getFullYear());
    feastDate.setDate(feastDate.getDate() + Number(rule.offsetDays || 0));

    return formatAlmanacKey(feastDate).dayKey === formatAlmanacKey(date).dayKey;
  });
}

function toMonthDayOrdinal(value) {
  const match = /^(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) return null;

  return Number(match[1]) * 32 + Number(match[2]);
}

function matchesDateRange(item, date) {
  const ranges = Array.isArray(item.dateRanges) ? item.dateRanges : [];
  const current = toMonthDayOrdinal(formatAlmanacKey(date).dayKey);

  return ranges.some((range) => {
    const from = toMonthDayOrdinal(range?.from);
    const to = toMonthDayOrdinal(range?.to);
    if (from === null || to === null || current === null) return false;

    return from <= to
      ? current >= from && current <= to
      : current >= from || current <= to;
  });
}

function isGenericProverbCandidate(item) {
  if (!item || item.almanacTargetUse) return false;
  if (Array.isArray(item.dateAnchors) && item.dateAnchors.length) return false;
  if (Array.isArray(item.months) && item.months.length) return false;
  if (
    Array.isArray(item.seasons) &&
    item.seasons.length &&
    !item.seasons.includes("all")
  ) return false;
  if (DATE_BOUND_PROVERB_CATEGORIES.has(item.category)) return false;

  // Records classified as monthly need an explicit monthly/lunar rule before
  // they can enter Almanacco; otherwise a month or moon phase may be wrong.
  return item.category !== "meteo_mensile";
}

function getDatesInYear(year) {
  const dates = [];
  const cursor = new Date(year, 0, 1, 12);

  while (cursor.getFullYear() === year) {
    dates.push(new Date(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }

  return dates;
}

function stableHash(value) {
  let hash = 2166136261;

  for (const character of String(value)) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }

  return hash >>> 0;
}

export function isProverbTemporallyCompatible(
  item,
  date,
  dailyProverbs = schedule.dailyProverbs,
) {
  if (!item?.almanacEligible) return false;

  const effectiveDate = toDate(date);
  const { dayKey, monthKey } = formatAlmanacKey(effectiveDate);
  if (dailyProverbs?.[dayKey] === item.id) return true;

  const season = getSeasonInfo(effectiveDate).id;

  switch (item.almanacTargetUse) {
    case PROVERB_TARGETS.DATED:
      return listIncludes(item.dateAnchors, dayKey);
    case PROVERB_TARGETS.DATE_RANGE:
      return matchesDateRange(item, effectiveDate);
    case PROVERB_TARGETS.MOVABLE_FEAST:
      return matchesMovableFeast(item, effectiveDate);
    case PROVERB_TARGETS.LUNAR_CYCLE:
      return matchesLunarCalendarRule(item, effectiveDate);
    case PROVERB_TARGETS.MONTHLY:
      return listIncludes(item.months, monthKey);
    case PROVERB_TARGETS.SEASONAL:
    case PROVERB_TARGETS.WEATHER_SIGN:
      return matchesSeason(item, season);
    default:
      return isGenericProverbCandidate(item);
  }
}

const annualProverbCalendarCache = new Map();

export function buildAnnualProverbCalendar(year, dailyProverbs = schedule.dailyProverbs) {
  const numericYear = Number(year);
  const effectiveYear = Number.isInteger(numericYear) ? numericYear : new Date().getFullYear();
  const useCache = dailyProverbs === schedule.dailyProverbs;

  if (useCache && annualProverbCalendarCache.has(effectiveYear)) {
    return annualProverbCalendarCache.get(effectiveYear);
  }

  const dates = getDatesInYear(effectiveYear);
  const datesByKey = new Map(dates.map((date) => [formatAlmanacKey(date).dayKey, date]));
  const candidates = Array.isArray(proverbs)
    ? proverbs.filter((item) => item.almanacEligible)
    : [];
  const candidatesById = new Map(candidates.map((item) => [item.id, item]));
  const calendar = new Map();
  const assignedIds = new Set();

  Object.entries(dailyProverbs || {})
    .filter(([dayKey]) => dayKey !== "default")
    .sort(([first], [second]) => first.localeCompare(second))
    .forEach(([dayKey, proverbId]) => {
      const record = candidatesById.get(proverbId);
      if (!datesByKey.has(dayKey) || !record || assignedIds.has(proverbId)) return;

      calendar.set(dayKey, record);
      assignedIds.add(proverbId);
    });

  const constrained = candidates
    .filter((item) => !assignedIds.has(item.id) && !isGenericProverbCandidate(item))
    .map((item) => ({
      item,
      validDates: dates.filter((date) => isProverbTemporallyCompatible(item, date, dailyProverbs)),
    }))
    .sort((first, second) => (
      first.validDates.length - second.validDates.length ||
      first.item.id.localeCompare(second.item.id)
    ));

  constrained.forEach(({ item, validDates }) => {
    const availableDates = validDates.filter((date) => !calendar.has(formatAlmanacKey(date).dayKey));
    if (!availableDates.length) return;

    const selectedIndex = stableHash(`${effectiveYear}:${item.id}`) % availableDates.length;
    const selectedDate = availableDates[selectedIndex];
    calendar.set(formatAlmanacKey(selectedDate).dayKey, item);
    assignedIds.add(item.id);
  });

  const generic = candidates
    .filter((item) => !assignedIds.has(item.id) && isGenericProverbCandidate(item))
    .sort((first, second) => (
      stableHash(`${effectiveYear}:${first.id}`) - stableHash(`${effectiveYear}:${second.id}`) ||
      first.id.localeCompare(second.id)
    ));
  const freeDates = dates.filter((date) => !calendar.has(formatAlmanacKey(date).dayKey));

  freeDates.forEach((date, index) => {
    const record = generic[index];
    if (!record) return;
    calendar.set(formatAlmanacKey(date).dayKey, record);
    assignedIds.add(record.id);
  });

  const fallback = getProverbById(dailyProverbs?.default) || generic[0] || candidates[0] || null;
  if (fallback) {
    dates.forEach((date) => {
      const { dayKey } = formatAlmanacKey(date);
      if (!calendar.has(dayKey)) calendar.set(dayKey, fallback);
    });
  }

  if (useCache) annualProverbCalendarCache.set(effectiveYear, calendar);
  return calendar;
}

export function getAnnualProverbCalendarAudit(year, dailyProverbs = schedule.dailyProverbs) {
  const numericYear = Number(year);
  const effectiveYear = Number.isInteger(numericYear) ? numericYear : new Date().getFullYear();
  const dates = getDatesInYear(effectiveYear);
  const calendar = buildAnnualProverbCalendar(effectiveYear, dailyProverbs);
  const selectedIds = [...calendar.values()].map((item) => item.id);
  const countsById = selectedIds.reduce((counts, id) => {
    counts.set(id, (counts.get(id) || 0) + 1);
    return counts;
  }, new Map());
  const eligibleIds = new Set(
    proverbs.filter((item) => item.almanacEligible).map((item) => item.id),
  );
  const incompatibleAssignments = dates
    .map((date) => ({ date, item: calendar.get(formatAlmanacKey(date).dayKey) }))
    .filter(({ date, item }) => item && !isProverbTemporallyCompatible(item, date, dailyProverbs))
    .map(({ date, item }) => ({ dayKey: formatAlmanacKey(date).dayKey, proverbId: item.id }));

  return {
    year: effectiveYear,
    daysInYear: dates.length,
    assignedDays: calendar.size,
    uniqueProverbs: countsById.size,
    duplicateIds: [...countsById.entries()]
      .filter(([, count]) => count > 1)
      .map(([id, count]) => ({ id, count })),
    missingDayKeys: dates
      .map((date) => formatAlmanacKey(date).dayKey)
      .filter((dayKey) => !calendar.has(dayKey)),
    unusedEligibleIds: [...eligibleIds].filter((id) => !countsById.has(id)),
    incompatibleAssignments,
  };
}

export function pickDailyProverb(date, weather = null, dailyProverbs = schedule.dailyProverbs) {
  void weather;
  const effectiveDate = toDate(date);
  const { dayKey } = formatAlmanacKey(effectiveDate);

  return buildAnnualProverbCalendar(effectiveDate.getFullYear(), dailyProverbs).get(dayKey)
    || getProverbById(dailyProverbs?.default)
    || null;
}

export function pickEarthTips(date, weather = null, count = 1) {
  const effectiveDate = toDate(date);
  const { monthKey } = formatAlmanacKey(effectiveDate);
  const monthlyTips = earthTips[monthKey] || [];
  const weatherTags = new Set(getWeatherAlmanacTags(weather));
  const scored = monthlyTips.map((item, index) => ({
    item,
    index,
    score: Array.isArray(item.tags) ? item.tags.filter((tag) => weatherTags.has(tag)).length : 0,
  }));
  const ordered = [...scored].sort((first, second) => second.score - first.score || first.index - second.index);

  return ordered.slice(0, count).map((entry) => entry.item);
}

export function getSaintForDate(date) {
  const effectiveDate = toDate(date);
  const { dayKey } = formatAlmanacKey(effectiveDate);
  const saint = saints[dayKey] || saints.default;
  const profile = saintProfiles[dayKey];

  return profile ? { ...saint, ...profile } : saint;
}

export function buildAlmanacData({
  date = new Date(),
  location = DEFAULT_LOCATION,
  now = new Date(),
  weather = null,
} = {}) {
  const effectiveDate = toDate(date);
  const season = getSeasonInfo(effectiveDate);

  return {
    date: effectiveDate,
    dayOfYear: getDayOfYear(effectiveDate),
    keys: formatAlmanacKey(effectiveDate),
    moon: getMoonPhase(effectiveDate),
    proverb: pickDailyProverb(effectiveDate, weather),
    saint: getSaintForDate(effectiveDate),
    season,
    sun: getSunCycle({
      date: effectiveDate,
      latitude: location.latitude ?? location.lat ?? DEFAULT_LOCATION.latitude,
      longitude: location.longitude ?? location.lon ?? DEFAULT_LOCATION.longitude,
      now,
      timeZone: location.timeZone || DEFAULT_LOCATION.timeZone,
    }),
    tips: pickEarthTips(effectiveDate, weather),
    tradition: pickDailyTradition(effectiveDate, weather),
  };
}

export function localizeAlmanacRecord(record, language = "it") {
  return getLocalizedField(record, language);
}

export function getAlmanacSeasonInfo(date, language = "it") {
  return getSeasonInfo(toDate(date), language);
}
