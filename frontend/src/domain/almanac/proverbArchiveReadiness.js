import proverbs from "../../data/almanac/proverbs.json";
import proverbCandidates from "../../data/almanac/proverbCandidates.json";
import candidateReview from "../../data/almanac/proverbCandidateReview.json";
import schedule from "../../data/almanac/schedule.json";
import proverbSources from "../../data/almanac/ostermannProverbSources.json";
import { isCandidateRecommendedForPromotion } from "./proverbCandidateReview";

const DEFAULT_DAILY_TARGET = 366;
const DEFAULT_ARCHIVE_TARGET = 500;
const ENCODING_REVIEW_PATTERN = /[\u00c2\u00c3\u00c5]|\u00e2\u20ac/;
const CLOSED_SOURCE_STATUSES = new Set(["candidate_extracted", "discover_backlog_extracted"]);

function getScheduleKeys(dailySchedule) {
  if (!dailySchedule || typeof dailySchedule !== "object") return [];
  return Object.keys(dailySchedule).filter((key) => key !== "default");
}

function getBrokenScheduleReferences(dailySchedule, itemIds) {
  if (!dailySchedule || typeof dailySchedule !== "object") return [];
  return Object.entries(dailySchedule)
    .filter(([, proverbId]) => proverbId && !itemIds.has(proverbId))
    .map(([date, proverbId]) => ({ date, proverbId }));
}

function getCandidateRecords(candidateArchive) {
  return Array.isArray(candidateArchive?.records) ? candidateArchive.records : [];
}

export function needsEncodingReview(record) {
  return ENCODING_REVIEW_PATTERN.test(JSON.stringify(record || {}));
}

export function isPromotionReadyCandidate(record) {
  return (
    record?.review?.status === "ready" &&
    Boolean(record.fur) &&
    Boolean(record.it) &&
    Boolean(record.source?.pdfPage) &&
    !needsEncodingReview(record)
  );
}

export function getProverbArchiveReadiness({
  candidateReviewArchive = candidateReview,
  proverbItems = proverbs,
  candidateArchive = proverbCandidates,
  dailySchedule = schedule.dailyProverbs,
  sourcePlan = proverbSources,
} = {}) {
  const items = Array.isArray(proverbItems) ? proverbItems : [];
  const candidateRecords = getCandidateRecords(candidateArchive);
  const promotionReadyCandidates = candidateRecords.filter(isPromotionReadyCandidate);
  const reviewedPromotionCandidates = candidateRecords.filter((record) => (
    isCandidateRecommendedForPromotion(record.id, candidateReviewArchive)
  ));
  const almanacEligible = items.filter((item) => item?.almanacEligible === true);
  const labReady = items.filter((item) => item?.normalizationStatus === "lab_ready");
  const humanReviewRequired = items.filter((item) => item?.humanReviewRequired === true);
  const itemIds = new Set(items.map((item) => item?.id).filter(Boolean));
  const datedKeys = getScheduleKeys(dailySchedule);
  const brokenScheduleReferences = getBrokenScheduleReferences(dailySchedule, itemIds);
  const encodingReviewItems = items.filter(needsEncodingReview);
  const targetDailySlots = Number(sourcePlan?.target?.dailySlots) || DEFAULT_DAILY_TARGET;
  const targetArchiveMinimum = Number(sourcePlan?.target?.archiveMinimum) || DEFAULT_ARCHIVE_TARGET;
  const candidatePages = Array.isArray(sourcePlan?.candidatePages) ? sourcePlan.candidatePages : [];
  const priorityPages = candidatePages.filter((page) => page.priority === "P1");
  const extractedPages = candidatePages.filter((page) => page.status === "candidate_extracted");
  const discoverBacklogPages = candidatePages.filter((page) => page.status === "discover_backlog_extracted");
  const pendingSourcePages = candidatePages.filter((page) => !CLOSED_SOURCE_STATUSES.has(page.status));

  return {
    targetDailySlots,
    targetArchiveMinimum,
    totalProverbs: items.length,
    candidateProverbs: candidateRecords.length,
    reviewedPromotionCandidates: reviewedPromotionCandidates.length,
    promotionReadyCandidates: promotionReadyCandidates.length,
    almanacEligibleProverbs: almanacEligible.length,
    labReadyProverbs: labReady.length,
    humanReviewRequiredProverbs: humanReviewRequired.length,
    datedSlots: datedKeys.length,
    brokenScheduleReferences,
    missingDailySlots: Math.max(0, targetDailySlots - datedKeys.length),
    missingArchiveRecords: Math.max(0, targetArchiveMinimum - items.length),
    encodingReviewCount: encodingReviewItems.length,
    candidateSourcePages: candidatePages.length,
    extractedCandidateSourcePages: extractedPages.length,
    discoverBacklogSourcePages: discoverBacklogPages.length,
    closedSourcePages: candidatePages.length - pendingSourcePages.length,
    pendingSourcePages: pendingSourcePages.length,
    prioritySourcePages: priorityPages.length,
    readyForDailyCalendar:
      datedKeys.length >= targetDailySlots &&
      almanacEligible.length >= targetDailySlots &&
      brokenScheduleReferences.length === 0 &&
      encodingReviewItems.length === 0,
  };
}
