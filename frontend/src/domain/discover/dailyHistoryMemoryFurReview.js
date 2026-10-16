import furReview from "../../data/discover/dailyHistoryMemoryFurReview.json";

function getRecords(source = furReview) {
  return Array.isArray(source?.records) ? source.records : [];
}

function countBy(records, getKey) {
  return records.reduce((counts, record) => {
    const key = getKey(record) || "missing";
    return { ...counts, [key]: (counts[key] || 0) + 1 };
  }, {});
}

export function getDailyHistoryMemoryFurReview(source = furReview) {
  return getRecords(source);
}

export function getDailyHistoryMemoryFurReviewIds(source = furReview) {
  return getRecords(source).map((record) => record.id);
}

export function getDailyHistoryMemoryFurReviewSummary(source = furReview) {
  const records = getRecords(source);

  return {
    totalRecords: records.length,
    bySurface: countBy(records, (record) => record.surface),
    byFurReviewStatus: countBy(records, (record) => record.furReviewStatus),
    recordsWithReviewQuestions: records.filter((record) => record.reviewQuestions?.length > 0).length,
    furApproved: records.filter((record) => record.furReviewStatus === "approved").length,
    readyForUi: Number(source?.summary?.readyForUi || 0),
  };
}
