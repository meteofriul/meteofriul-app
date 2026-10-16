import review from "../../data/discover/dailyHistoryMemoryPromotionReview.json";
import localMemory from "../../data/discover/localMemory.json";

function getRecords(source = review) {
  return Array.isArray(source?.records) ? source.records : [];
}

function countBy(records, getKey) {
  return records.reduce((counts, record) => {
    const key = getKey(record) || "missing";
    return { ...counts, [key]: (counts[key] || 0) + 1 };
  }, {});
}

function isPromotionTrackRecord(record) {
  return (
    typeof record?.id === "string" &&
    record.id.startsWith("memory-copy-") &&
    (record.editorialStatus === "copy_candidate" || record.editorialStatus === "source_verified")
  );
}

function getPromotionTrackIds(source = localMemory) {
  const records = Array.isArray(source?.records) ? source.records : [];
  return records
    .filter(isPromotionTrackRecord)
    .map((record) => record.id)
    .sort();
}

function getLocalMemoryById(source = localMemory) {
  const records = Array.isArray(source?.records) ? source.records : [];
  return new Map(records.map((record) => [record.id, record]));
}

function getPromotionBlockers(record) {
  const blockers = [];

  if (record?.source?.type !== "verified_source") blockers.push("source_final_check");
  if (record?.languageStatus?.it !== "approved") blockers.push("it_copy_approval");
  if (record?.languageStatus?.fur !== "approved") blockers.push("fur_human_review");
  if (record?.editorialStatus !== "ready_for_discover") blockers.push("ready_for_discover_status");
  if (record?.readyForUi !== true) blockers.push("ready_for_ui_flag");

  return blockers;
}

export function getDailyHistoryMemoryPromotionReview(source = review) {
  return getRecords(source);
}

export function getDailyHistoryMemoryPromotionQueue({
  reviewSource = review,
  localMemorySource = localMemory,
  recommendation = "primary_promotion_candidate",
  limit,
} = {}) {
  const memoryById = getLocalMemoryById(localMemorySource);
  const records = getRecords(reviewSource)
    .filter((record) => !recommendation || record.recommendation === recommendation)
    .slice()
    .sort((first, second) => Number(first.priority) - Number(second.priority));

  const queue = records.map((record) => {
    const memoryRecord = memoryById.get(record.id);

    return {
      id: record.id,
      recommendation: record.recommendation,
      priority: record.priority,
      reason: record.reason,
      title: memoryRecord?.title || {},
      dateAnchors: memoryRecord?.dateAnchors || [],
      areas: memoryRecord?.areas || [],
      source: memoryRecord?.source || {},
      blockers: getPromotionBlockers(memoryRecord),
      needsBeforePublish: record.needsBeforePublish || [],
    };
  });

  return typeof limit === "number" ? queue.slice(0, limit) : queue;
}

export function getDailyHistoryMemoryPromotionReviewSummary({
  reviewSource = review,
  localMemorySource = localMemory,
} = {}) {
  const records = getRecords(reviewSource);
  const reviewIds = records.map((record) => record.id).sort();
  const promotionTrackIds = getPromotionTrackIds(localMemorySource);

  return {
    totalRecords: records.length,
    byRecommendation: countBy(records, (record) => record.recommendation),
    highestPriorityId: records
      .slice()
      .sort((first, second) => Number(first.priority) - Number(second.priority))[0]?.id,
    reviewCoversAllPromotionTrackRecords: JSON.stringify(reviewIds) === JSON.stringify(promotionTrackIds),
    missingFromReview: promotionTrackIds.filter((id) => !reviewIds.includes(id)),
    extraInReview: reviewIds.filter((id) => !promotionTrackIds.includes(id)),
    recordsWithoutNeeds: records.filter((record) => !record.needsBeforePublish?.length).map((record) => record.id),
    primaryQueueReadyForPublish: getDailyHistoryMemoryPromotionQueue({
      reviewSource,
      localMemorySource,
      recommendation: "primary_promotion_candidate",
    }).filter((record) => record.blockers.length === 0).length,
  };
}
