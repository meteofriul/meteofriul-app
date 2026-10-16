import candidateReview from "../../data/almanac/proverbCandidateReview.json";
import proverbs from "../../data/almanac/proverbs.json";
import { isPromotionRecommendation } from "./proverbCandidateReview";

export const PROVERB_PROMOTION_TARGETS = Object.freeze({
  PUBLISHED_PROVERB: "published_proverb",
  DATED: "almanac_dated",
  MONTHLY: "almanac_monthly",
  SEASONAL: "almanac_seasonal",
  WEATHER_SIGN: "almanac_weather_sign",
  LUNAR_CYCLE: "almanac_lunar_cycle",
});

const TARGET_ORDER = [
  PROVERB_PROMOTION_TARGETS.PUBLISHED_PROVERB,
  PROVERB_PROMOTION_TARGETS.DATED,
  PROVERB_PROMOTION_TARGETS.MONTHLY,
  PROVERB_PROMOTION_TARGETS.SEASONAL,
  PROVERB_PROMOTION_TARGETS.WEATHER_SIGN,
  PROVERB_PROMOTION_TARGETS.LUNAR_CYCLE,
];

const PENDING_TARGETS = new Set([
  PROVERB_PROMOTION_TARGETS.DATED,
  PROVERB_PROMOTION_TARGETS.MONTHLY,
  PROVERB_PROMOTION_TARGETS.SEASONAL,
  PROVERB_PROMOTION_TARGETS.WEATHER_SIGN,
  PROVERB_PROMOTION_TARGETS.LUNAR_CYCLE,
]);

function getReviewRecords(reviewArchive) {
  return Array.isArray(reviewArchive?.records) ? reviewArchive.records : [];
}

function getPublishedIds(proverbItems) {
  return new Set((Array.isArray(proverbItems) ? proverbItems : [])
    .map((item) => item?.id)
    .filter(Boolean));
}

function normalizeList(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function toPlanItem(record) {
  return {
    id: record.id,
    recommendation: record.recommendation,
    targetUse: record.targetUse || null,
    priority: record.priority || null,
    reviewedAt: record.reviewedAt || null,
    dateAnchors: normalizeList(record.dateAnchors),
    months: normalizeList(record.months),
    seasons: normalizeList(record.seasons),
    sourceCheck: record.sourceCheck || null,
  };
}

function countByTarget(records) {
  const counts = TARGET_ORDER.reduce((accumulator, target) => {
    accumulator[target] = 0;
    return accumulator;
  }, {});

  records.forEach((record) => {
    const target = record.targetUse || "missing";
    counts[target] = (counts[target] || 0) + 1;
  });

  return counts;
}

function getDuplicateDateAnchors(items) {
  const seen = new Set();
  const duplicates = new Set();

  items.forEach((item) => {
    item.dateAnchors.forEach((dateAnchor) => {
      if (seen.has(dateAnchor)) {
        duplicates.add(dateAnchor);
      }
      seen.add(dateAnchor);
    });
  });

  return [...duplicates].sort();
}

export function getProverbPromotionPlan(reviewArchive = candidateReview, proverbItems = proverbs) {
  const reviewedRecords = getReviewRecords(reviewArchive);
  const publishedIds = getPublishedIds(proverbItems);
  const promotionRecords = reviewedRecords.filter((record) => (
    isPromotionRecommendation(record.recommendation)
  ));
  const alreadyPublishedCandidates = promotionRecords
    .filter((record) => publishedIds.has(record.id))
    .map(toPlanItem);
  const pendingCandidates = promotionRecords
    .filter((record) => !publishedIds.has(record.id))
    .map(toPlanItem);
  const fixedDateCandidates = promotionRecords
    .filter((record) => record.targetUse === PROVERB_PROMOTION_TARGETS.DATED)
    .map(toPlanItem);

  const pendingFixedDateCandidates = pendingCandidates.filter(
    (candidate) => candidate.targetUse === PROVERB_PROMOTION_TARGETS.DATED,
  );
  const monthlyCandidates = pendingCandidates.filter(
    (candidate) => candidate.targetUse === PROVERB_PROMOTION_TARGETS.MONTHLY,
  );
  const seasonalCandidates = pendingCandidates.filter(
    (candidate) => candidate.targetUse === PROVERB_PROMOTION_TARGETS.SEASONAL,
  );
  const weatherSignCandidates = pendingCandidates.filter(
    (candidate) => candidate.targetUse === PROVERB_PROMOTION_TARGETS.WEATHER_SIGN,
  );
  const lunarCycleCandidates = pendingCandidates.filter(
    (candidate) => candidate.targetUse === PROVERB_PROMOTION_TARGETS.LUNAR_CYCLE,
  );
  const fixedDateCandidatesWithoutDate = fixedDateCandidates.filter(
    (candidate) => candidate.dateAnchors.length === 0,
  );
  const nonFixedDateCandidatesWithDate = pendingCandidates.filter((candidate) => (
    candidate.targetUse !== PROVERB_PROMOTION_TARGETS.DATED && candidate.dateAnchors.length > 0
  ));
  const missingTargetCandidates = pendingCandidates.filter((candidate) => !candidate.targetUse);
  const unknownTargetCandidates = pendingCandidates.filter((candidate) => (
    candidate.targetUse && !PENDING_TARGETS.has(candidate.targetUse)
  ));

  return {
    reviewedAt: reviewArchive?.reviewedAt || null,
    totalReviewed: reviewedRecords.length,
    promotionCandidateCount: promotionRecords.length,
    alreadyPublishedCount: alreadyPublishedCandidates.length,
    pendingPromotionCount: pendingCandidates.length,
    byTargetUse: countByTarget(promotionRecords),
    alreadyPublishedByTargetUse: countByTarget(alreadyPublishedCandidates),
    pendingByTargetUse: countByTarget(pendingCandidates),
    alreadyPublishedCandidates,
    fixedDateCandidates,
    pendingFixedDateCandidates,
    monthlyCandidates,
    seasonalCandidates,
    weatherSignCandidates,
    lunarCycleCandidates,
    fixedDateCandidateCount: fixedDateCandidates.length,
    pendingFixedDateCandidateCount: pendingFixedDateCandidates.length,
    fixedDateScheduleSlots: fixedDateCandidates.flatMap((candidate) => (
      candidate.dateAnchors.map((dateAnchor) => ({
        dateAnchor,
        id: candidate.id,
      }))
    )),
    duplicateDateAnchors: getDuplicateDateAnchors(fixedDateCandidates),
    guardrails: {
      readyForAutomaticPublication: false,
      manualStepRequired: "final_fur_review_then_controlled_proverbs_and_schedule_update",
      fixedDateCandidatesWithoutDate,
      nonFixedDateCandidatesWithDate,
      missingTargetCandidates,
      unknownTargetCandidates,
    },
  };
}
