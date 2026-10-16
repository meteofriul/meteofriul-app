import backlogAudit from "../../data/discover/dailyHistoryBacklogAudit.json";

function getDays(source) {
  return Array.isArray(source?.days) ? source.days : [];
}

function getNextReviewCandidates(source) {
  return Array.isArray(source?.nextReviewCandidates) ? source.nextReviewCandidates : [];
}

function getNextLightReviewCandidates(source) {
  return Array.isArray(source?.nextLightReviewCandidates) ? source.nextLightReviewCandidates : [];
}

function getNextPrimaryGapCandidates(source) {
  return Array.isArray(source?.nextPrimaryGapCandidates) ? source.nextPrimaryGapCandidates : [];
}

export function getDailyHistoryBacklogAudit(source = backlogAudit) {
  const days = getDays(source);
  const nextReviewCandidates = getNextReviewCandidates(source);
  const nextLightReviewCandidates = getNextLightReviewCandidates(source);
  const nextPrimaryGapCandidates = getNextPrimaryGapCandidates(source);
  const unqueuedCandidateDays = days
    .filter((day) => Number(day.unqueuedEligibleCandidates || 0) > 0)
    .map((day) => day.dayKey);
  const unqueuedCandidateDateAnchors = days
    .filter((day) => Number(day.unqueuedEligibleCandidates || 0) > 0)
    .map((day) => day.dateAnchor || day.dayKey);
  const lightReviewCandidateDays = days
    .filter((day) => day.topUnqueued?.some((candidate) => candidate.suggestedReviewLane === "light_review"))
    .map((day) => day.dayKey);
  const lightReviewCandidateDateAnchors = days
    .filter((day) => day.topUnqueued?.some((candidate) => candidate.suggestedReviewLane === "light_review"))
    .map((day) => day.dateAnchor || day.dayKey);

  return {
    schemaVersion: source?.schemaVersion,
    sourceDays: source?.summary?.sourceDays || days.length,
    sourceCandidates: source?.summary?.sourceCandidates || 0,
    eligibleCandidates: source?.summary?.eligibleCandidates || 0,
    unqueuedEligibleCandidates: source?.summary?.unqueuedEligibleCandidates || 0,
    coveredDays: source?.summary?.coveredDays || days.filter((day) => day.eligibleCandidates > 0).length,
    emptyDays: source?.summary?.emptyDays || [],
    coveredUnqueuedDays: source?.summary?.coveredUnqueuedDays || days.filter((day) => day.unqueuedEligibleCandidates > 0).length,
    emptyUnqueuedDays: source?.summary?.emptyUnqueuedDays || [],
    unqueuedCandidateDays,
    unqueuedCandidateDateAnchors,
    lightReviewCandidateDays,
    lightReviewCandidateDateAnchors,
    firstUnqueuedCandidateDays: unqueuedCandidateDays.slice(0, 20),
    firstLightReviewCandidateDays: lightReviewCandidateDays.slice(0, 20),
    byEligibleCategory: source?.summary?.byEligibleCategory || {},
    byEligibleEditorialClass: source?.summary?.byEligibleEditorialClass || {},
    bySuggestedReviewLane: source?.summary?.bySuggestedReviewLane || {},
    nextReviewCandidates: nextReviewCandidates.length,
    nextLightReviewCandidates: nextLightReviewCandidates.length,
    readyPrimaryDays: source?.summary?.readyPrimaryDays || 0,
    missingPrimaryDays: source?.summary?.missingPrimaryDays || 0,
    missingPrimaryDaysWithUnqueuedCandidates:
      source?.summary?.missingPrimaryDaysWithUnqueuedCandidates || 0,
    missingPrimaryDaysWithoutUnqueuedCandidates:
      source?.summary?.missingPrimaryDaysWithoutUnqueuedCandidates || 0,
    nextPrimaryGapCandidates: nextPrimaryGapCandidates.length,
    nextReviewCandidateIds: nextReviewCandidates.map((candidate) => candidate.wikidataId),
    nextLightReviewCandidateIds: nextLightReviewCandidates.map((candidate) => candidate.wikidataId),
    nextLightReviewSourceDays: nextLightReviewCandidates.map((candidate) => candidate.sourceDayKey),
    nextPrimaryGapCandidateDateAnchors: nextPrimaryGapCandidates
      .map((candidate) => candidate.dateAnchor),
    duplicateNextReviewWikidataIds: nextReviewCandidates
      .map((candidate) => candidate.wikidataId)
      .filter((id, index, ids) => id && ids.indexOf(id) !== index),
    duplicateNextLightReviewWikidataIds: nextLightReviewCandidates
      .map((candidate) => candidate.wikidataId)
      .filter((id, index, ids) => id && ids.indexOf(id) !== index),
    duplicateNextLightReviewSourceDays: nextLightReviewCandidates
      .map((candidate) => candidate.sourceDayKey)
      .filter((day, index, days) => day && days.indexOf(day) !== index),
    duplicateNextPrimaryGapDateAnchors: nextPrimaryGapCandidates
      .map((candidate) => candidate.dateAnchor)
      .filter((day, index, days) => day && days.indexOf(day) !== index),
  };
}
