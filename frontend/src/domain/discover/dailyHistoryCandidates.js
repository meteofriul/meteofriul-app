import candidatesArchive from "../../data/discover/dailyHistoryCandidates.json";
import { getDiscoverEditorialPolicyAudit } from "./discoverEditorialPolicy";

export function convertSourceDayKeyToDateAnchor(sourceDayKey) {
  if (typeof sourceDayKey !== "string") return null;
  const parts = sourceDayKey.split("-");
  if (parts.length !== 2) return null;
  const [day, month] = parts;
  if (!/^\d{2}$/.test(day) || !/^\d{2}$/.test(month)) return null;
  return `${month}-${day}`;
}

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

function normalize(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("it-IT");
}

function getLocationScore(candidate, context = {}) {
  const city = normalize(context.city);
  const province = normalize(context.province);
  const place = normalize(candidate.place);
  const candidateProvince = normalize(candidate.province);
  const areas = Array.isArray(candidate.areas)
    ? candidate.areas.map(normalize)
    : [];

  if (city && (place === city || areas.includes(city))) return 100;
  if (province && candidateProvince === province) return 70;
  return 10;
}

export function getLocalizedSecondaryDailyHistoryEntries(record, context = {}) {
  const candidates = Array.isArray(record?.dayComposition?.secondaryCandidates)
    ? record.dayComposition.secondaryCandidates
    : [];
  const maxVisible = Number.isInteger(record?.dayComposition?.secondarySelection?.maxVisibleSecondary)
    ? record.dayComposition.secondarySelection.maxVisibleSecondary
    : 2;

  return candidates
    .map((candidate) => ({
      ...candidate,
      locationScore: getLocationScore(candidate, context),
    }))
    .filter((candidate) => candidate.locationScore >= 40)
    .sort((a, b) => {
      if (b.locationScore !== a.locationScore) return b.locationScore - a.locationScore;
      return String(a.title).localeCompare(String(b.title), "it-IT");
    })
    .slice(0, maxVisible);
}

export function getDailyHistoryCandidatesAudit(source = candidatesArchive) {
  const records = getRecords(source);
  const editorialPolicy = getDiscoverEditorialPolicyAudit(records);
  const dateAnchors = records.map((record) => record.dateAnchor).filter(Boolean);
  const uniqueDateAnchors = new Set(dateAnchors);
  const dateFormatErrors = records
    .filter((record) => record.dateAnchor !== convertSourceDayKeyToDateAnchor(record.sourceDayKey))
    .map((record) => record.id);
  const publishableRecords = records.filter((record) => record.readyForUi === true);
  const sourceReviewedRecords = records.filter((record) => record.sourceReview?.reviewedAt);
  const sourceVerificationAttemptedRecords = records.filter((record) => (
    record.sourceReview?.verificationAttempt?.reviewedAt
  ));
  const sourceVerificationRetriedRecords = records.filter((record) => (
    record.sourceReview?.verificationRetry?.retriedAt
  ));
  const recordsWithDayComposition = records.filter((record) => record.dayComposition);
  const secondaryCandidates = recordsWithDayComposition.flatMap((record) => (
    Array.isArray(record.dayComposition?.secondaryCandidates)
      ? record.dayComposition.secondaryCandidates
      : []
  ));
  const discardedSameDayCandidates = recordsWithDayComposition.flatMap((record) => (
    Array.isArray(record.dayComposition?.discardedSameDayCandidates)
      ? record.dayComposition.discardedSameDayCandidates
      : []
  ));

  return {
    schemaVersion: source?.schemaVersion,
    sourceDateFormat: source?.sourceInput?.sourceDateFormat,
    appDateFormat: source?.sourceInput?.appDateFormat,
    totalRecords: records.length,
    uniqueDateAnchors: uniqueDateAnchors.size,
    duplicateDateAnchors: dateAnchors.filter((dateAnchor, index) => dateAnchors.indexOf(dateAnchor) !== index),
    dateFormatErrors,
    publishableRecords: publishableRecords.length,
    byReviewStatus: countBy(records, (record) => record.reviewStatus),
    byEditorialStatus: countBy(records, (record) => record.editorialStatus),
    byEditorialReadiness: editorialPolicy.byReadiness,
    lightCandidateRecordIds: editorialPolicy.lightCandidateRecordIds,
    strongSourceRequiredRecordIds: editorialPolicy.strongSourceRequiredRecordIds,
    strongReadyForCopyRecordIds: editorialPolicy.strongReadyForCopyRecordIds,
    bySourceType: countBy(records, (record) => record.source?.type),
    sourceReviewedRecords: sourceReviewedRecords.length,
    bySourceReviewStatus: countBy(sourceReviewedRecords, (record) => record.sourceReview?.status),
    sourceVerificationAttemptedRecords: sourceVerificationAttemptedRecords.length,
    bySourceVerificationOutcome: countBy(
      sourceVerificationAttemptedRecords,
      (record) => record.sourceReview?.verificationAttempt?.outcome,
    ),
    sourceVerificationRetriedRecords: sourceVerificationRetriedRecords.length,
    bySourceVerificationRetryOutcome: countBy(
      sourceVerificationRetriedRecords,
      (record) => (
        record.sourceReview?.verificationRetry?.secondRetryOutcome ||
        record.sourceReview?.verificationRetry?.retryOutcome
      ),
    ),
    recordsWithDayComposition: recordsWithDayComposition.length,
    secondarySameDayCandidates: secondaryCandidates.length,
    discardedSameDayCandidates: discardedSameDayCandidates.length,
    recordsNeedingItCopy: records.filter((record) => record.languageStatus?.it !== "approved").length,
    recordsNeedingFurCopy: records.filter((record) => record.languageStatus?.fur !== "approved").length,
    recordIds: records.map((record) => record.id),
  };
}
