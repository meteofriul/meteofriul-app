import proverbCandidates from "../../data/almanac/proverbCandidates.json";
import proverbs from "../../data/almanac/proverbs.json";
import schedule from "../../data/almanac/schedule.json";
import proverbSources from "../../data/almanac/ostermannProverbSources.json";

const MONTH_KEYS = Array.from({ length: 12 }, (_, index) => String(index + 1).padStart(2, "0"));
const CLOSED_SOURCE_STATUSES = new Set(["candidate_extracted", "discover_backlog_extracted"]);
const WEATHER_HINTS = new Set([
  "aria",
  "bora",
  "brina",
  "caldo",
  "freddo",
  "garbino",
  "grandine",
  "gelo",
  "ghiaccio",
  "meteo",
  "nebbia",
  "neve",
  "nubi",
  "pioggia",
  "temporale",
  "vento",
]);

function countBy(items, getKey) {
  return items.reduce((counts, item) => {
    const key = getKey(item) || "missing";
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});
}

function getCandidateRecords(candidateArchive) {
  return Array.isArray(candidateArchive?.records) ? candidateArchive.records : [];
}

function getScheduleKeys(dailySchedule) {
  if (!dailySchedule || typeof dailySchedule !== "object") return [];
  return Object.keys(dailySchedule).filter((key) => key !== "default").sort();
}

function normalizeList(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function collectDateAnchors(items) {
  return [...new Set(items.flatMap((item) => normalizeList(item?.dateAnchors)))].sort();
}

function createMonthMatrix() {
  return MONTH_KEYS.reduce((months, month) => {
    months[month] = {
      candidateDateAnchors: 0,
      knownDateAnchors: 0,
      scheduledDateAnchors: 0,
    };
    return months;
  }, {});
}

function addDateAnchorsToMonths(months, anchors, key) {
  anchors.forEach((anchor) => {
    const month = String(anchor).slice(0, 2);
    if (!months[month]) return;
    months[month][key] += 1;
  });
}

function hasWeatherHint(record) {
  const tags = [
    ...normalizeList(record?.tags),
    record?.category,
  ].filter(Boolean);

  return tags.some((tag) => WEATHER_HINTS.has(String(tag).toLowerCase()));
}

function inferCandidateBucket(candidate) {
  if (normalizeList(candidate?.dateAnchors).length) return "dated";
  if (normalizeList(candidate?.movableDates).length) return "movable_date";
  if (normalizeList(candidate?.months).length) return "monthly";
  if (hasWeatherHint(candidate)) return "weather_sign";
  if (normalizeList(candidate?.seasons).length) return "seasonal";
  return "generic_or_context";
}

export function getProverbRepertoireMatrix({
  candidateArchive = proverbCandidates,
  dailySchedule = schedule.dailyProverbs,
  proverbItems = proverbs,
  sourcePlan = proverbSources,
} = {}) {
  const published = Array.isArray(proverbItems) ? proverbItems : [];
  const candidates = getCandidateRecords(candidateArchive);
  const scheduledDateAnchors = getScheduleKeys(dailySchedule);
  const candidateDateAnchors = collectDateAnchors(candidates);
  const knownDateAnchors = [...new Set([...scheduledDateAnchors, ...candidateDateAnchors])].sort();
  const targetDailySlots = Number(sourcePlan?.target?.dailySlots) || 366;
  const targetDistinctDailyProverbs = Number(sourcePlan?.target?.distinctDailyProverbs)
    || targetDailySlots;
  const targetArchiveMinimum = Number(sourcePlan?.target?.archiveMinimum) || 500;
  const sourcePages = Array.isArray(sourcePlan?.candidatePages) ? sourcePlan.candidatePages : [];
  const extractedSourcePages = sourcePages.filter((page) => page.status === "candidate_extracted");
  const discoverBacklogSourcePages = sourcePages.filter((page) => page.status === "discover_backlog_extracted");
  const pendingSourcePages = sourcePages.filter((page) => !CLOSED_SOURCE_STATUSES.has(page.status));
  const byMonth = createMonthMatrix();

  addDateAnchorsToMonths(byMonth, scheduledDateAnchors, "scheduledDateAnchors");
  addDateAnchorsToMonths(byMonth, candidateDateAnchors, "candidateDateAnchors");
  addDateAnchorsToMonths(byMonth, knownDateAnchors, "knownDateAnchors");

  const publishedIds = new Set(published.map((item) => item?.id).filter(Boolean));
  const candidateOnlyRecords = candidates.filter((item) => !publishedIds.has(item?.id));
  const rawCombinedRecords = published.length + candidates.length;
  const uniqueWorkingRecords = published.length + candidateOnlyRecords.length;
  const publishedAlmanacEligible = published.filter(
    (item) => item?.almanacEligible === true,
  ).length;

  return {
    target: {
      archiveMinimum: targetArchiveMinimum,
      dailySlots: targetDailySlots,
      distinctDailyProverbs: targetDistinctDailyProverbs,
    },
    published: {
      total: published.length,
      almanacEligible: publishedAlmanacEligible,
      labReady: published.filter((item) => item?.normalizationStatus === "lab_ready").length,
      humanReviewRequired: published.filter((item) => item?.humanReviewRequired === true).length,
      byNormalizationStatus: countBy(published, (item) => item?.normalizationStatus || "missing"),
      byTargetUse: countBy(published, (item) => item?.almanacTargetUse || "generic"),
      genericFallbackPool: published.filter((item) => item?.almanacEligible === true && !item?.almanacTargetUse).length,
    },
    candidates: {
      total: candidates.length,
      alreadyPublished: candidates.length - candidateOnlyRecords.length,
      unpublished: candidateOnlyRecords.length,
      byReviewStatus: countBy(candidates, (item) => item?.review?.status || "missing"),
      byInferredBucket: countBy(candidates, inferCandidateBucket),
      withFur: candidates.filter((item) => Boolean(item?.fur)).length,
      withSourcePage: candidates.filter((item) => Boolean(item?.source?.pdfPage)).length,
      withDateAnchors: candidates.filter((item) => normalizeList(item?.dateAnchors).length > 0).length,
      withMovableDates: candidates.filter((item) => normalizeList(item?.movableDates).length > 0).length,
    },
    calendar: {
      scheduledDateAnchors,
      candidateDateAnchors,
      knownDateAnchors,
      scheduledDateAnchorCount: scheduledDateAnchors.length,
      candidateDateAnchorCount: candidateDateAnchors.length,
      knownDateAnchorCount: knownDateAnchors.length,
      missingKnownDateAnchors: Math.max(0, targetDailySlots - knownDateAnchors.length),
      byMonth,
      weakMonths: MONTH_KEYS.filter((month) => byMonth[month].knownDateAnchors < 2),
    },
    sourcePlan: {
      totalPages: sourcePages.length,
      extractedPages: extractedSourcePages.length,
      discoverBacklogPages: discoverBacklogSourcePages.length,
      closedPages: sourcePages.length - pendingSourcePages.length,
      unextractedPages: pendingSourcePages.map((page) => page.pdfPage),
      priorityPages: sourcePages.filter((page) => page.priority === "P1").length,
    },
    gaps: {
      publishedArchiveGap: Math.max(0, targetArchiveMinimum - published.length),
      workingArchiveGap: Math.max(0, targetArchiveMinimum - uniqueWorkingRecords),
      distinctPublishedProverbGap: Math.max(
        0,
        targetDistinctDailyProverbs - published.length,
      ),
      distinctEligibleProverbGap: Math.max(
        0,
        targetDistinctDailyProverbs - publishedAlmanacEligible,
      ),
      distinctWorkingProverbGap: Math.max(
        0,
        targetDistinctDailyProverbs - uniqueWorkingRecords,
      ),
      dailyScheduleGap: Math.max(0, targetDailySlots - scheduledDateAnchors.length),
      knownDateAnchorGap: Math.max(0, targetDailySlots - knownDateAnchors.length),
    },
    totals: {
      rawCombinedRecords,
      uniqueWorkingRecords,
      isDailyCalendarReady: scheduledDateAnchors.length >= targetDailySlots,
      isArchiveReady: published.length >= targetArchiveMinimum,
      isWorkingArchiveReady: uniqueWorkingRecords >= targetArchiveMinimum,
      hasDistinctProverbForEveryDay: publishedAlmanacEligible >= targetDistinctDailyProverbs,
    },
  };
}
