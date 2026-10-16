import proverbs from "../../data/almanac/proverbs.json";
import proverbCandidates from "../../data/almanac/proverbCandidates.json";
import candidateReview from "../../data/almanac/proverbCandidateReview.json";
import schedule from "../../data/almanac/schedule.json";
import proverbSources from "../../data/almanac/ostermannProverbSources.json";
import localMemoryArchive from "../../data/discover/localMemory.json";
import traditionalSayingsArchive from "../../data/discover/traditionalSayings.json";
import { getTraditionalSayingRecords } from "./traditionalSayings";

const DAILY_TARGET = 366;
const READY_LOCAL_MEMORY_SOURCE_TYPES = new Set(["verified_source", "editorial_note"]);
const READY_SAYING_SOURCE_TYPES = new Set(["verified_source"]);
const PROMOTION_RECOMMENDATIONS = new Set([
  "promote_after_fur_review",
  "replace_existing_after_review",
]);
const CLOSED_SOURCE_STATUSES = new Set(["candidate_extracted", "discover_backlog_extracted"]);

function getRecords(source) {
  if (Array.isArray(source)) return source;
  return Array.isArray(source?.records) ? source.records : [];
}

function normalizeList(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function hasDateAnchors(record) {
  return normalizeList(record?.dateAnchors).length > 0;
}

function hasMonthAnchors(record) {
  return normalizeList(record?.months).length > 0;
}

function countBy(records, getKey) {
  return records.reduce((counts, record) => {
    const key = getKey(record) || "missing";
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});
}

function getScheduledDayKeys(dailySchedule) {
  if (!dailySchedule || typeof dailySchedule !== "object") return [];
  return Object.keys(dailySchedule).filter((key) => key !== "default").sort();
}

function getIds(records) {
  return records.map((record) => record.id).filter(Boolean);
}

function isReadyLocalMemory(record) {
  if (!record || record.readyForUi === false) return false;
  if (record.primaryUse !== "discover") return false;
  if (record.editorialStatus !== "ready_for_discover") return false;
  return READY_LOCAL_MEMORY_SOURCE_TYPES.has(record.source?.type);
}

function isReadyTraditionalSaying(record) {
  if (!record || record.readyForUi === false) return false;
  if (record.primaryUse !== "discover") return false;
  if (record.editorialStatus !== "ready_for_discover") return false;
  return READY_SAYING_SOURCE_TYPES.has(record.source?.type);
}

function getSourcePlanStatus(sourcePlan) {
  const pages = Array.isArray(sourcePlan?.candidatePages) ? sourcePlan.candidatePages : [];
  const closedPages = pages.filter((page) => CLOSED_SOURCE_STATUSES.has(page.status));

  return {
    totalPages: pages.length,
    priorityPages: pages.filter((page) => page.priority === "P1").length,
    closedPages: closedPages.length,
    openPages: pages.length - closedPages.length,
    byStatus: countBy(pages, (page) => page.status),
  };
}

export function getDiscoverSourceAudit({
  localMemorySource = localMemoryArchive,
  traditionalSayingsSource = traditionalSayingsArchive,
  proverbItems = proverbs,
  candidateArchive = proverbCandidates,
  candidateReviewArchive = candidateReview,
  dailySchedule = schedule.dailyProverbs,
  sourcePlan = proverbSources,
} = {}) {
  const localMemoryRecords = getRecords(localMemorySource);
  const traditionalSayingRecords = getTraditionalSayingRecords(traditionalSayingsSource);
  const proverbRecords = getRecords(proverbItems);
  const candidateRecords = getRecords(candidateArchive);
  const reviewRecords = getRecords(candidateReviewArchive);
  const readyLocalMemory = localMemoryRecords.filter(isReadyLocalMemory);
  const readyTraditionalSayings = traditionalSayingRecords.filter(isReadyTraditionalSaying);
  const promotionQueue = reviewRecords.filter((record) => (
    PROMOTION_RECOMMENDATIONS.has(record.recommendation)
  ));
  const scheduledDays = getScheduledDayKeys(dailySchedule);
  const readyExactDateMemories = readyLocalMemory.filter(hasDateAnchors);
  const sourceVerifiedExactDateMemoriesNeedingCopy = localMemoryRecords.filter((record) => (
    record.source?.type === "verified_source" &&
    hasDateAnchors(record) &&
    record.languageStatus?.it !== "approved" &&
    !isReadyLocalMemory(record)
  ));
  const sourceVerifiedExactDateMemoriesAwaitingFur = localMemoryRecords.filter((record) => (
    record.source?.type === "verified_source" &&
    hasDateAnchors(record) &&
    record.languageStatus?.it === "approved" &&
    record.languageStatus?.fur !== "approved" &&
    !isReadyLocalMemory(record)
  ));
  const sourceCandidateExactDateMemories = localMemoryRecords.filter((record) => (
    record.source?.type === "source_candidate" &&
    hasDateAnchors(record)
  ));
  const copyCandidateExactDateMemories = localMemoryRecords.filter((record) => (
    record.editorialStatus === "copy_candidate" &&
    hasDateAnchors(record)
  ));
  const sourceCandidateMemories = localMemoryRecords.filter((record) => (
    record.source?.type === "source_candidate"
  ));

  return {
    policy: {
      sourceFirst: true,
      noCalendarFillerWithoutSource: true,
      exactDailyMemoryRequiresExactDate: true,
      archiveRotationsDoNotCountAsAccaddeOggi: true,
    },
    target: {
      dailySlots: DAILY_TARGET,
      archiveMinimum: Number(sourcePlan?.target?.archiveMinimum) || 500,
    },
    sourcePools: {
      localMemory: {
        totalRecords: localMemoryRecords.length,
        readyRecords: readyLocalMemory.length,
        exactDateReadyRecords: readyLocalMemory.filter(hasDateAnchors).length,
        rotationReadyRecords: readyLocalMemory.filter((record) => !hasDateAnchors(record)).length,
        byEditorialStatus: countBy(localMemoryRecords, (record) => record.editorialStatus),
        bySourceType: countBy(localMemoryRecords, (record) => record.source?.type),
      },
      traditionalSayings: {
        totalRecords: traditionalSayingRecords.length,
        readyRecords: readyTraditionalSayings.length,
        exactDateReadyRecords: readyTraditionalSayings.filter(hasDateAnchors).length,
        rotationReadyRecords: readyTraditionalSayings.filter((record) => !hasDateAnchors(record)).length,
        byEditorialStatus: countBy(traditionalSayingRecords, (record) => record.editorialStatus),
        bySourceType: countBy(traditionalSayingRecords, (record) => record.source?.type),
      },
      publishedProverbs: {
        totalRecords: proverbRecords.length,
        almanacEligibleRecords: proverbRecords.filter((record) => record.almanacEligible === true).length,
        scheduledDays: scheduledDays.length,
        recordsWithDateAnchors: proverbRecords.filter(hasDateAnchors).length,
        recordsWithMonthAnchors: proverbRecords.filter(hasMonthAnchors).length,
      },
      ostermannCandidates: {
        totalRecords: candidateRecords.length,
        recordsWithSourcePage: candidateRecords.filter((record) => Boolean(record.source?.pdfPage)).length,
        recordsWithFur: candidateRecords.filter((record) => Boolean(record.fur)).length,
        recordsWithDateAnchors: candidateRecords.filter(hasDateAnchors).length,
        recordsWithMonthAnchors: candidateRecords.filter(hasMonthAnchors).length,
        byCandidateReviewStatus: countBy(candidateRecords, (record) => record.review?.status),
      },
      ostermannCandidateReview: {
        totalRecords: reviewRecords.length,
        promotionQueue: promotionQueue.length,
        promotionQueueWithDateAnchors: promotionQueue.filter(hasDateAnchors).length,
        promotionQueueWithMonthAnchors: promotionQueue.filter(hasMonthAnchors).length,
        byRecommendation: countBy(reviewRecords, (record) => record.recommendation),
      },
      ostermannSourcePlan: getSourcePlanStatus(sourcePlan),
    },
    memoryTriage: {
      readyExactDateRecordIds: getIds(readyExactDateMemories),
      readyRotationRecordIds: getIds(readyLocalMemory.filter((record) => !hasDateAnchors(record))),
      sourceVerifiedExactDateNeedsCopyRecordIds: getIds(sourceVerifiedExactDateMemoriesNeedingCopy),
      sourceVerifiedExactDateNeedsFurReviewRecordIds: getIds(sourceVerifiedExactDateMemoriesAwaitingFur),
      copyCandidateExactDateNeedsReviewRecordIds: getIds(copyCandidateExactDateMemories),
      sourceCandidateExactDateRecordIds: getIds(sourceCandidateExactDateMemories),
      sourceCandidateNeedsBetterSourceRecordIds: getIds(sourceCandidateMemories),
      nextExactDateWorkRecordIds: getIds([
        ...sourceVerifiedExactDateMemoriesNeedingCopy,
        ...sourceVerifiedExactDateMemoriesAwaitingFur,
        ...copyCandidateExactDateMemories,
        ...sourceCandidateExactDateMemories,
      ]),
      publishableExactDateRecords: readyExactDateMemories.length,
      verifiableExactDateBacklog:
        sourceVerifiedExactDateMemoriesNeedingCopy.length +
        sourceVerifiedExactDateMemoriesAwaitingFur.length +
        copyCandidateExactDateMemories.length +
        sourceCandidateExactDateMemories.length,
    },
    dailyReadiness: {
      localMemoryExactDateGap: Math.max(0, DAILY_TARGET - readyLocalMemory.filter(hasDateAnchors).length),
      traditionalSayingExactDateGap: Math.max(0, DAILY_TARGET - readyTraditionalSayings.filter(hasDateAnchors).length),
      scheduledProverbGap: Math.max(0, DAILY_TARGET - scheduledDays.length),
      hasSourceBacklogForProverbs: candidateRecords.length > 0 || reviewRecords.length > 0,
      hasSourceBacklogForMemories: localMemoryRecords.some((record) => record.source?.type !== "verified_source"),
    },
  };
}
