import reviewPack from "../../data/discover/dailyHistoryReviewPack.json";

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

export function getDailyHistoryReviewPackAudit(source = reviewPack) {
  const records = getRecords(source);
  const dateAnchors = records.map((record) => record.dateAnchor).filter(Boolean);
  const duplicateDateAnchors = dateAnchors.filter((dateAnchor, index) => (
    dateAnchors.indexOf(dateAnchor) !== index
  ));

  return {
    schemaVersion: source?.schemaVersion,
    totalRecords: records.length,
    readyForUiRecords: records.filter((record) => record.readyForUi === true).length,
    duplicateDateAnchors,
    byReviewStatus: countBy(records, (record) => record.reviewStatus),
    byEditorialStatus: countBy(records, (record) => record.editorialStatus),
    byCategory: countBy(records, (record) => record.category),
    byPlace: countBy(records, (record) => record.place),
    recordsNeedingItCopy: records.filter((record) => record.languageStatus?.it !== "approved").length,
    recordsNeedingFurCopy: records.filter((record) => record.languageStatus?.fur !== "approved").length,
    recordsWithItDraft: records.filter((record) => Boolean(record.copyDraft?.it)).length,
    recordsWithFurDraft: records.filter((record) => Boolean(record.copyDraft?.fur)).length,
    recordIds: records.map((record) => record.id),
  };
}
