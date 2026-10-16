import expandedReview from "../../data/discover/dailyHistoryExpandedReview.json";

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

export function getDailyHistoryExpandedReviewAudit(source = expandedReview) {
  const records = getRecords(source);
  const wikidataIds = records.map((record) => record.wikidataId).filter(Boolean);
  const dateAnchors = records.map((record) => record.dateAnchor).filter(Boolean);

  return {
    schemaVersion: source?.schemaVersion,
    totalRecords: records.length,
    readyForUiRecords: records.filter((record) => record.readyForUi === true).length,
    duplicateWikidataIds: wikidataIds.filter((id, index) => wikidataIds.indexOf(id) !== index),
    duplicateDateAnchors: dateAnchors.filter((dateAnchor, index) => dateAnchors.indexOf(dateAnchor) !== index),
    byExtractionClass: countBy(records, (record) => record.extractionClass),
    byReviewStatus: countBy(records, (record) => record.reviewStatus),
    byPostReviewEditorialStatus: countBy(records, (record) => record.editorialStatus),
    byEditorialClass: countBy(records, (record) => record.editorialClass),
    byCategory: countBy(records, (record) => record.category),
    byPlace: countBy(records, (record) => record.place),
    recordsNeedingItCopy: records.filter((record) => record.languageStatus?.it !== "approved").length,
    recordsNeedingFurCopy: records.filter((record) => record.languageStatus?.fur !== "approved").length,
    recordIds: records.map((record) => record.id),
  };
}
