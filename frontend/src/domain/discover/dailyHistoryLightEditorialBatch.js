import lightEditorialBatch from "../../data/discover/dailyHistoryLightEditorialBatch.json";

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

export function getDailyHistoryLightEditorialBatchAudit(source = lightEditorialBatch) {
  const records = getRecords(source);
  const copyCandidates = records.filter((record) => record.batchDecision === "copy_candidate");

  return {
    schemaVersion: source?.schemaVersion,
    totalRecords: records.length,
    readyForUiRecords: records.filter((record) => record.readyForUi === true).length,
    byDecision: countBy(records, (record) => record.batchDecision),
    bySurface: countBy(records, (record) => record.surface),
    copyCandidates: copyCandidates.length,
    copyCandidatesWithItDraft: copyCandidates.filter((record) => Boolean(record.copyDraft?.it)).length,
    copyCandidatesNeedingFur: copyCandidates.filter((record) => record.copyDraft?.fur !== "approved").length,
    duplicateDates: records
      .map((record) => record.dateAnchor)
      .filter((dateAnchor, index, dates) => dateAnchor && dates.indexOf(dateAnchor) !== index),
    duplicateWikidataIds: records
      .map((record) => record.wikidataId)
      .filter((wikidataId, index, ids) => wikidataId && ids.indexOf(wikidataId) !== index),
  };
}
