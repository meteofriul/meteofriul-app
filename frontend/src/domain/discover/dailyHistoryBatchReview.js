import batchReview from "../../data/discover/dailyHistoryBatchReview.json";
import { convertSourceDayKeyToDateAnchor } from "./dailyHistoryCandidates";

function getRecords(source) {
  return Array.isArray(source?.records) ? source.records : [];
}

function countBy(records, keyFn) {
  return records.reduce((acc, record) => {
    const key = keyFn(record) || "unknown";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

export function getDailyHistoryBatchReviewAudit(source = batchReview) {
  const records = getRecords(source);
  const dateErrors = records
    .filter((record) => record.dateAnchor !== convertSourceDayKeyToDateAnchor(record.sourceDayKey))
    .map((record) => record.sourceCandidateId);
  const mainCandidates = records.filter((record) => record.surface === "main_memory_candidate");
  const actionableMainCandidates = mainCandidates.filter((record) => (
    ["ready_for_copy", "source_lead_found", "source_review_needed"].includes(record.batchStatus)
  ));
  const recordsWithSourceLeads = records.filter((record) => (
    Array.isArray(record.sourceLeads) && record.sourceLeads.length > 0
  ));

  return {
    schemaVersion: source?.schemaVersion,
    totalRecords: records.length,
    dateErrors,
    byBatchStatus: countBy(records, (record) => record.batchStatus),
    bySurface: countBy(records, (record) => record.surface),
    byProvince: countBy(records, (record) => record.province),
    mainMemoryCandidates: mainCandidates.length,
    actionableMainCandidates: actionableMainCandidates.length,
    recordsWithSourceLeads: recordsWithSourceLeads.length,
    readyForCopyIds: records
      .filter((record) => record.batchStatus === "ready_for_copy")
      .map((record) => record.sourceCandidateId),
    holdIds: records
      .filter((record) => record.surface === "hold")
      .map((record) => record.sourceCandidateId),
  };
}
