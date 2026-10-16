import prominentProfilesReview from "../../data/discover/dailyHistoryProminentProfilesReview.json";
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

export function getDailyHistoryProminentProfilesReviewAudit(source = prominentProfilesReview) {
  const records = getRecords(source);
  const newCopyCandidates = records.filter((record) => record.batchDecision === "copy_candidate");
  const italianReviewCandidates = records.filter(
    (record) => record.batchDecision === "it_review_candidate",
  );
  const italianArchiveReviewCandidates = records.filter(
    (record) => record.batchDecision === "it_archive_review_candidate",
  );

  return {
    schemaVersion: source?.schemaVersion,
    totalRecords: records.length,
    readyForUiRecords: records.filter((record) => record.readyForUi === true).length,
    deathRecords: records.filter((record) => record.type === "Morte").map((record) => record.id),
    eventRecords: records.filter((record) => record.type === "Evento").map((record) => record.id),
    duplicateWikidataIds: records
      .map((record) => record.wikidataId)
      .filter((wikidataId, index, ids) => wikidataId && ids.indexOf(wikidataId) !== index),
    invalidItalianDates: records
      .filter((record) => !isValidItalianDayMonth(record.dateIt))
      .map((record) => record.id),
    byDecision: countBy(records, (record) => record.batchDecision),
    bySurface: countBy(records, (record) => record.surface),
    newCopyCandidates: newCopyCandidates.length,
    newCopyCandidatesNeedingFur: newCopyCandidates.filter((record) => record.copyDraft?.fur !== "approved").length,
    newCopyCandidatesWithDeferredFur: newCopyCandidates.filter(
      (record) => record.copyDraft?.fur === "deferred_until_it_selection",
    ).length,
    italianReviewCandidates: italianReviewCandidates.length,
    italianReviewCandidatesWithFurStarted: italianReviewCandidates.filter(
      (record) => record.copyDraft?.fur || record.languageStatus?.fur !== "not_started",
    ).length,
    italianArchiveReviewCandidates: italianArchiveReviewCandidates.length,
    italianArchiveReviewCandidatesWithFurStarted: italianArchiveReviewCandidates.filter(
      (record) => record.copyDraft?.fur || record.languageStatus?.fur !== "not_started",
    ).length,
    belowProminenceThresholdRecords: records
      .filter((record) => record.batchDecision === "discard_below_prominence_threshold")
      .map((record) => record.id),
    existingReuseRecords: records.filter((record) => record.batchDecision === "reuse_existing_local_memory").length,
    upgradeExistingRecords: records.filter((record) => record.batchDecision === "upgrade_existing_local_memory").length,
  };
}
