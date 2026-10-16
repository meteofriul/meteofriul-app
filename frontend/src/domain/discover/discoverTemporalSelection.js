function getDateParts(value) {
  if (typeof value === "string") {
    const isoMatch = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (isoMatch) {
      return {
        year: Number.parseInt(isoMatch[1], 10),
        month: Number.parseInt(isoMatch[2], 10),
        day: Number.parseInt(isoMatch[3], 10),
      };
    }
  }

  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;

  return {
    year: parsed.getFullYear(),
    month: parsed.getMonth() + 1,
    day: parsed.getDate(),
  };
}

const DAY_MS = 24 * 60 * 60 * 1000;

const STABLE_MONTH_OFFSETS = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];

function getStableCivilDayIndex(value) {
  const parts = getDateParts(value);
  if (!parts) return 0;
  return STABLE_MONTH_OFFSETS[parts.month - 1] + parts.day - 1;
}

function compareDiscoverRecords(first, second) {
  const priorityDiff = Number(first.record?.priority || 99) - Number(second.record?.priority || 99);
  if (priorityDiff) return priorityDiff;
  return String(first.record?.id || "").localeCompare(String(second.record?.id || ""));
}

function getContentKey(record) {
  return record?.candidateId || record?.id;
}

function formatDateKey(month, day) {
  return `${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

const SEASON_ALIASES = {
  all: "all",
  autumn: "autunno",
  autunno: "autunno",
  fall: "autunno",
  estate: "estate",
  inverno: "inverno",
  primavera: "primavera",
  spring: "primavera",
  summer: "estate",
  winter: "inverno",
};

export function normalizeDiscoverSeason(value) {
  return SEASON_ALIASES[String(value || "").trim().toLowerCase()] || "";
}

export function getDiscoverRecordSeasons(record) {
  const normalized = [...new Set(
    (Array.isArray(record?.seasons) ? record.seasons : [])
      .map(normalizeDiscoverSeason)
      .filter(Boolean),
  )];
  const explicitSeasons = normalized.filter((season) => season !== "all");

  return explicitSeasons.length ? explicitSeasons : normalized;
}

function getDiscoverRecordMonths(record) {
  return [...new Set(
    (Array.isArray(record?.months) ? record.months : [])
      .map((month) => Number.parseInt(String(month), 10))
      .filter((month) => month >= 1 && month <= 12),
  )];
}

export function getDiscoverDateKey(value) {
  const parts = getDateParts(value);
  return parts ? formatDateKey(parts.month, parts.day) : "";
}

export function getDiscoverSeason(value) {
  const parts = getDateParts(value);
  if (!parts) return "";
  if ([12, 1, 2].includes(parts.month)) return "inverno";
  if ([3, 4, 5].includes(parts.month)) return "primavera";
  if ([6, 7, 8].includes(parts.month)) return "estate";
  return "autunno";
}

export function getGregorianEasterDateKey(year) {
  const parsedYear = Number.parseInt(String(year), 10);
  if (!Number.isFinite(parsedYear)) return "";

  const a = parsedYear % 19;
  const b = Math.floor(parsedYear / 100);
  const c = parsedYear % 100;
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

  return formatDateKey(month, day);
}

export function getGregorianEasterRelativeDateKey(year, offsetDays = 0) {
  const parsedYear = Number.parseInt(String(year), 10);
  const parsedOffset = Number.parseInt(String(offsetDays), 10);
  const easterKey = getGregorianEasterDateKey(parsedYear);
  if (!easterKey || !Number.isFinite(parsedOffset)) return "";

  const [month, day] = easterKey.split("-").map(Number);
  const relativeDate = new Date(Date.UTC(parsedYear, month - 1, day + parsedOffset));
  return formatDateKey(relativeDate.getUTCMonth() + 1, relativeDate.getUTCDate());
}

function getPalmSundayDateKey(year) {
  const easterKey = getGregorianEasterDateKey(year);
  if (!easterKey) return "";
  const [month, day] = easterKey.split("-").map(Number);
  const palmSunday = new Date(Date.UTC(year, month - 1, day - 7));
  return formatDateKey(palmSunday.getUTCMonth() + 1, palmSunday.getUTCDate());
}

function matchesDateRange(dateKey, range) {
  const [start, end] = String(range || "").split("..");
  if (!start || !end) return false;
  if (start <= end) return dateKey >= start && dateKey <= end;
  return dateKey >= start || dateKey <= end;
}

export function matchesDiscoverMovableDate(record, value) {
  const parts = getDateParts(value);
  const dateKey = getDiscoverDateKey(value);
  if (!parts || !dateKey) return false;

  return (record?.movableDates || []).some((token) => {
    if (token === "easter") return dateKey === getGregorianEasterDateKey(parts.year);
    if (token === "easter_relative") return dateKey === getPalmSundayDateKey(parts.year);
    return false;
  });
}

export function matchesDiscoverNthWeekdayDate(record, value) {
  const rules = record?.nthWeekdayDates;
  const parts = getDateParts(value);
  if (!parts || !Array.isArray(rules) || !rules.length) return false;
  const validRule = (rule) => rule
    && Number.isInteger(rule.month) && rule.month >= 1 && rule.month <= 12
    && Number.isInteger(rule.weekday) && rule.weekday >= 0 && rule.weekday <= 6
    && Number.isInteger(rule.ordinal) && rule.ordinal >= 1 && rule.ordinal <= 5;
  if (!rules.every(validRule)) return false;

  // Use a civil UTC date, avoiding local DST and Date.UTC's special years 0–99.
  const date = new Date(0);
  date.setUTCFullYear(parts.year, parts.month - 1, parts.day);
  if (date.getUTCFullYear() !== parts.year || date.getUTCMonth() !== parts.month - 1
    || date.getUTCDate() !== parts.day) return false;

  return rules.some((rule) => rule.month === parts.month
    && rule.weekday === date.getUTCDay()
    && rule.ordinal === Math.floor((parts.day - 1) / 7) + 1);
}

export function matchesDiscoverMovableDateRange(record, value) {
  const parts = getDateParts(value);
  if (!parts) return false;

  const current = Date.UTC(parts.year, parts.month - 1, parts.day);
  return (record?.movableDateRanges || []).some((range) => {
    if (range?.anchor !== "easter") return false;

    const startOffset = Number.parseInt(String(range.startOffsetDays), 10);
    const endOffset = Number.parseInt(String(range.endOffsetDays), 10);
    if (!Number.isFinite(startOffset) || !Number.isFinite(endOffset)) return false;

    const easterKey = getGregorianEasterDateKey(parts.year);
    if (!easterKey) return false;
    const [month, day] = easterKey.split("-").map(Number);
    const easter = Date.UTC(parts.year, month - 1, day);
    const start = easter + Math.min(startOffset, endOffset) * DAY_MS;
    const end = easter + Math.max(startOffset, endOffset) * DAY_MS;
    return current >= start && current <= end;
  });
}

export function getDiscoverTemporalRank(record, value) {
  const parts = getDateParts(value);
  const dateKey = getDiscoverDateKey(value);
  if (!record || !parts || !dateKey) return null;

  if (record.dateAnchors?.includes(dateKey)) return 0;
  if (matchesDiscoverMovableDate(record, value)) return 1;
  if (matchesDiscoverNthWeekdayDate(record, value)) return 1;
  if (matchesDiscoverMovableDateRange(record, value)) return 2;
  if ((record.dateRanges || []).some((range) => matchesDateRange(dateKey, range))) return 2;

  // An explicit ordinal rule never becomes an annual/monthly fallback on a miss.
  if (Object.hasOwn(record, "nthWeekdayDates")) return null;

  const recurrence = record.recurrence || "";
  const months = getDiscoverRecordMonths(record);
  if (months.length && !months.includes(parts.month)) return null;

  const seasons = getDiscoverRecordSeasons(record);
  const season = getDiscoverSeason(value);
  const hasSeasonConstraint = seasons.length > 0 && !seasons.includes("all");
  if (hasSeasonConstraint && !seasons.includes(season)) return null;

  if (recurrence === "weather") return null;
  if (months.length) return 3;

  if (recurrence === "seasonal" && seasons.length) return 3;
  if (!recurrence && hasSeasonConstraint) return 3;
  if (recurrence === "always") return hasSeasonConstraint ? 3 : 4;

  const hasDateConstraint = Boolean(
    record.dateAnchors?.length ||
    record.dateRanges?.length ||
    record.movableDateRanges?.length ||
    record.movableDates?.length,
  );
  if (!recurrence && !hasDateConstraint) return 4;

  return null;
}

export function pickDiscoverTemporalRecord(records, value, {
  blendBroader = false,
  excludedContentKeys = new Set(),
  offset = 0,
} = {}) {
  const parts = getDateParts(value);
  if (!parts) return null;

  const rankedRecords = records
    .filter((record) => !excludedContentKeys.has(getContentKey(record)))
    .map((record) => ({ record, rank: getDiscoverTemporalRank(record, value) }))
    .filter(({ rank }) => rank !== null)
    .sort((first, second) => first.rank - second.rank || compareDiscoverRecords(first, second));
  if (!rankedRecords.length) return null;

  const bestRank = rankedRecords[0].rank;
  const bestRecords = rankedRecords.filter(({ rank }) => rank === bestRank);
  if (bestRank < 2) {
    return bestRecords[(parts.year + offset) % bestRecords.length].record;
  }

  const dayIndex = getStableCivilDayIndex(value) + offset;
  // Il calendario civile usa sempre uno slot anche per il 29 febbraio: così la
  // stessa data avanza di una posizione ogni anno senza che il bisestile annulli
  // la variazione annuale. Exact date e ricorrenze mobili restano nel ramo sopra.
  const rotationIndex = dayIndex + parts.year;
  const nextBroaderRank = blendBroader
    ? rankedRecords.find(({ rank }) => rank > bestRank)?.rank
    : null;
  const broaderRecords = nextBroaderRank == null
    ? []
    : rankedRecords.filter(({ rank }) => rank === nextBroaderRank);
  if (!broaderRecords.length) {
    return bestRecords[rotationIndex % bestRecords.length].record;
  }

  // Gli intervalli precisi restano prevalenti (due giorni su tre), mentre mese
  // e stagione si alternano con il livello temporale immediatamente più ampio.
  // In questo modo la rotazione varia senza saltare direttamente al catalogo
  // generale e senza lasciare indietro i candidati mensili.
  const cadence = bestRank === 2 ? 3 : 2;
  const cyclePosition = rotationIndex % cadence;
  const useBroaderPool = cyclePosition === cadence - 1;
  const selectedPool = useBroaderPool ? broaderRecords : bestRecords;
  const completedCycles = Math.floor(rotationIndex / cadence);
  const selectionIndex = useBroaderPool
    ? completedCycles
    : rotationIndex - completedCycles;

  return selectedPool[selectionIndex % selectedPool.length].record;
}

export function getDiscoverSeasonForRecord(record, value) {
  const currentSeason = getDiscoverSeason(value);
  const seasons = getDiscoverRecordSeasons(record);

  if (seasons.includes(currentSeason)) return currentSeason;
  if (seasons.includes("all") || !seasons.length) return "all";
  return seasons[0];
}
