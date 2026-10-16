import candidateReview from "../../data/almanac/proverbCandidateReview.json";

export const PROMOTION_RECOMMENDATIONS = new Set([
  "promote_after_fur_review",
  "replace_existing_after_review",
]);

function getReviewRecords(reviewArchive) {
  return Array.isArray(reviewArchive?.records) ? reviewArchive.records : [];
}

export function getCandidateReviewById(id, reviewArchive = candidateReview) {
  return getReviewRecords(reviewArchive).find((record) => record.id === id) || null;
}

export function isPromotionRecommendation(recommendation) {
  return PROMOTION_RECOMMENDATIONS.has(recommendation);
}

export function isCandidateRecommendedForPromotion(id, reviewArchive = candidateReview) {
  const review = getCandidateReviewById(id, reviewArchive);
  return isPromotionRecommendation(review?.recommendation);
}

export function getCandidateReviewSummary(reviewArchive = candidateReview) {
  const records = getReviewRecords(reviewArchive);
  const byRecommendation = records.reduce((accumulator, record) => {
    const key = record.recommendation || "missing";
    accumulator[key] = (accumulator[key] || 0) + 1;
    return accumulator;
  }, {});
  const byPriority = records.reduce((accumulator, record) => {
    const key = record.priority || "missing";
    accumulator[key] = (accumulator[key] || 0) + 1;
    return accumulator;
  }, {});
  const promotionIds = records
    .filter((record) => isPromotionRecommendation(record.recommendation))
    .map((record) => record.id);

  return {
    reviewedAt: reviewArchive?.reviewedAt || null,
    totalReviewed: records.length,
    byPriority,
    byRecommendation,
    promotionCandidateCount: promotionIds.length,
    promotionCandidateIds: promotionIds,
  };
}
