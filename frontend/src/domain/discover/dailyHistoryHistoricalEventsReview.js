import historicalEventsReview from "../../data/discover/dailyHistoryHistoricalEventsReview.json";
import { isValidItalianDayMonth } from "./discoverEditorialPolicy";

function getRecords(source) {
  return Array.isArray(source?.records) ? source.records : [];
}

function countBy(records, keyFn) {
  return records.reduce((acc, record) => {
    const key = keyFn(record) || "missing";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

export function getDailyHistoryHistoricalEventsReviewAudit(source = historicalEventsReview) {
  const records = getRecords(source);
  const copyCandidates = records.filter((record) => record.batchDecision === "copy_candidate");
  const evergreenArchiveCandidates = records.filter(
    (record) => record.batchDecision === "evergreen_archive_candidate",
  );

  return {
    schemaVersion: source?.schemaVersion,
    totalRecords: records.length,
    readyForUiRecords: records.filter((record) => record.readyForUi === true).length,
    nonEventRecords: records.filter((record) => record.type !== "Evento").map((record) => record.id),
    deathRecords: records.filter((record) => record.type === "Morte").map((record) => record.id),
    duplicateWikidataIds: records
      .map((record) => record.wikidataId)
      .filter((wikidataId, index, ids) => wikidataId && ids.indexOf(wikidataId) !== index),
    invalidItalianDates: records
      .filter((record) => !isValidItalianDayMonth(record.dateIt))
      .map((record) => record.id),
    byDecision: countBy(records, (record) => record.batchDecision),
    bySurface: countBy(records, (record) => record.surface),
    copyCandidates: copyCandidates.length,
    evergreenArchiveCandidates: evergreenArchiveCandidates.length,
    copyCandidatesNeedingFur: copyCandidates.filter((record) => record.copyDraft?.fur !== "approved").length,
    copyCandidatesWithDeferredFur: copyCandidates.filter(
      (record) => record.copyDraft?.fur === "deferred_until_it_selection",
    ).length,
  };
}
