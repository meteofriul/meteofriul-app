import finalReview from "../../data/discover/dailyHistoryMemoryFinalReview.json";

function getRecords(source = finalReview) {
  return Array.isArray(source?.records) ? source.records : [];
}

function countBy(records, getKey) {
  return records.reduce((counts, record) => {
    const key = getKey(record) || "missing";
    return { ...counts, [key]: (counts[key] || 0) + 1 };
  }, {});
}

function hasNoRemainingBlockers(record) {
  return !Array.isArray(record?.remainingBlockers) || record.remainingBlockers.length === 0;
}

export function getDailyHistoryMemoryFinalReview(source = finalReview) {
  return getRecords(source);
}

export function getDailyHistoryMemoryFinalReviewSummary(source = finalReview) {
  const records = getRecords(source);
  const recordsReadyForPublish = records.filter((record) => (
    record.publishDecision === "ready_for_ui" && hasNoRemainingBlockers(record)
  ));

  return {
    totalRecords: records.length,
    byDecision: countBy(records, (record) => record.decision),
    byPublishDecision: countBy(records, (record) => record.publishDecision),
    byEditorialRank: countBy(records, (record) => record.editorialTriage?.rank),
    byEditorialSurface: countBy(records, (record) => record.editorialTriage?.surface),
    dailyPrimaryCandidateIds: records
      .filter((record) => record.editorialTriage?.surface === "daily_primary")
      .map((record) => record.id),
    dailySecondaryCandidateIds: records
      .filter((record) => record.editorialTriage?.surface === "daily_secondary")
      .map((record) => record.id),
    archiveCandidateIds: records
      .filter((record) => record.editorialTriage?.surface === "archive")
      .map((record) => record.id),
    recordsWithoutEditorialTriage: records
      .filter((record) => !record.editorialTriage?.rank || !record.editorialTriage?.surface)
      .map((record) => record.id),
    furApproved: records.filter((record) => record.copyReview?.fur === "approved").length,
    readyForUi: recordsReadyForPublish.length,
    recordsReadyForPublish: recordsReadyForPublish.map((record) => record.id),
    recordsWithoutBlockers: records.filter(hasNoRemainingBlockers).map((record) => record.id),
    recordsWithoutSourceReview: records
      .filter((record) => !record.sourceReview?.url || !record.sourceReview?.note)
      .map((record) => record.id),
  };
}

export function getDailyHistoryMemoryFinalReviewIds(source = finalReview) {
  return getRecords(source).map((record) => record.id);
}
