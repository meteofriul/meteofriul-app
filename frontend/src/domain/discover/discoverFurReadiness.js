import localMemoryArchive from "../../data/discover/localMemory.json";
import ostermannDiscoverBacklogArchive from "../../data/discover/ostermannDiscoverBacklog.json";
import traditionalSayingsArchive from "../../data/discover/traditionalSayings.json";
import curatedDiscoverArchive from "./discoverCulturalRecords";
import { isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getTraditionalSayingRecords } from "./traditionalSayings";

const LOCAL_MEMORY_READY_STATUS = "ready_for_discover";
const LOCAL_MEMORY_READY_SOURCE_TYPES = new Set(["verified_source", "editorial_note"]);

function getRecords(source) {
  if (Array.isArray(source)) return source;
  return Array.isArray(source?.records) ? source.records : [];
}

export function isCuratedDiscoverVisible(record) {
  return isCuratedDiscoverUiReady(record);
}

export function isLocalMemoryVisible(record) {
  if (!record || record.readyForUi === false) return false;
  if (record.primaryUse !== "discover") return false;
  if (record.editorialStatus !== LOCAL_MEMORY_READY_STATUS) return false;
  return LOCAL_MEMORY_READY_SOURCE_TYPES.has(record.source?.type);
}

export function isFurApproved(record) {
  return record?.languageStatus?.fur === "approved";
}

function hasPendingBacklogFur(record) {
  return record?.title?.fur === "pending_review" || record?.summary?.fur === "pending_review";
}

function blockedRef(record, source) {
  return {
    id: record.id,
    source,
    status: record.languageStatus?.fur || "missing",
  };
}

function needsFurReview(record) {
  return record?.languageStatus?.fur === "human_review_needed" ||
    record?.languageStatus?.fur === "pending_review" ||
    hasPendingBacklogFur(record);
}

export function getDiscoverFurReadinessSummary({
  curatedRecords = curatedDiscoverArchive,
  localMemorySource = localMemoryArchive,
  backlogSource = ostermannDiscoverBacklogArchive,
  traditionalSayingsSource = traditionalSayingsArchive,
} = {}) {
  const curated = getRecords(curatedRecords);
  const localMemory = getRecords(localMemorySource);
  const backlog = getRecords(backlogSource);
  const traditionalSayings = getTraditionalSayingRecords(traditionalSayingsSource);

  const visibleCurated = curated.filter(isCuratedDiscoverVisible);
  const visibleLocalMemory = localMemory.filter(isLocalMemoryVisible);
  const visibleTraditionalSayings = traditionalSayings.filter(isLocalMemoryVisible);
  const hiddenInFurCurated = visibleCurated.filter((record) => !isFurApproved(record));
  const hiddenInFurLocalMemory = visibleLocalMemory.filter((record) => !isFurApproved(record));
  const hiddenInFurTraditionalSayings = visibleTraditionalSayings.filter((record) => !isFurApproved(record));
  const localMemoryBlockedUntilPromotion = localMemory.filter((record) => (
    needsFurReview(record) && !isLocalMemoryVisible(record)
  ));
  const backlogBlockedUntilPromotion = backlog.filter((record) => (
    needsFurReview(record) &&
    record.editorialStatus !== LOCAL_MEMORY_READY_STATUS &&
    record.readyForUi !== true
  ));
  const furVisibleCurated = visibleCurated.filter(isFurApproved);
  const furVisibleLocalMemory = visibleLocalMemory.filter(isFurApproved);
  const furVisibleTraditionalSayings = visibleTraditionalSayings.filter(isFurApproved);
  const furVisibleRecords = furVisibleCurated.length + furVisibleLocalMemory.length + furVisibleTraditionalSayings.length;

  return {
    curatedRecords: curated.length,
    visibleCuratedRecords: visibleCurated.length,
    visibleCuratedFurApprovedRecords: furVisibleCurated.length,
    visibleCuratedFurShortReadyRecords: visibleCurated.filter((record) => (
      record.languageStatus?.fur === "short_ready"
    )).length,
    hiddenInFurCuratedRecords: hiddenInFurCurated.length,
    hiddenInFurCuratedRecordRefs: hiddenInFurCurated.map((record) => blockedRef(record, "curated")),

    localMemoryRecords: localMemory.length,
    visibleLocalMemoryRecords: visibleLocalMemory.length,
    visibleLocalMemoryFurApprovedRecords: furVisibleLocalMemory.length,
    hiddenInFurLocalMemoryRecords: hiddenInFurLocalMemory.length,
    hiddenInFurLocalMemoryRecordRefs: hiddenInFurLocalMemory.map((record) => (
      blockedRef(record, "local_memory")
    )),
    localMemoryFurHumanReviewNeededRecords: localMemory.filter((record) => (
      record.languageStatus?.fur === "human_review_needed"
    )).length,
    localMemoryBlockedUntilPromotionRecords: localMemoryBlockedUntilPromotion.length,
    localMemoryBlockedUntilPromotionRecordRefs: localMemoryBlockedUntilPromotion.map((record) => (
      blockedRef(record, "local_memory")
    )),

    traditionalSayingsRecords: traditionalSayings.length,
    visibleTraditionalSayingsRecords: visibleTraditionalSayings.length,
    visibleTraditionalSayingsFurApprovedRecords: furVisibleTraditionalSayings.length,
    hiddenInFurTraditionalSayingsRecords: hiddenInFurTraditionalSayings.length,
    hiddenInFurTraditionalSayingsRecordRefs: hiddenInFurTraditionalSayings.map((record) => (
      blockedRef(record, "traditional_sayings")
    )),

    backlogRecords: backlog.length,
    backlogPendingFurRecords: backlog.filter(hasPendingBacklogFur).length,
    backlogBlockedUntilPromotionRecords: backlogBlockedUntilPromotion.length,
    backlogBlockedUntilPromotionRecordRefs: backlogBlockedUntilPromotion.map((record) => ({
      id: record.id,
      source: "ostermann_backlog",
      status: "not_promoted",
    })),
    backlogReadyForUiRecords: backlog.filter((record) => (
      record.editorialStatus === LOCAL_MEMORY_READY_STATUS || record.readyForUi === true
    )).length,

    furVisibleRecords,
    hiddenInFurRecords:
      hiddenInFurCurated.length +
      hiddenInFurLocalMemory.length +
      hiddenInFurTraditionalSayings.length,
    discoverFurDisplayReady: furVisibleRecords > 0,
    discoverFurCoverageComplete:
      hiddenInFurCurated.length === 0 &&
      hiddenInFurLocalMemory.length === 0 &&
      hiddenInFurTraditionalSayings.length === 0,
  };
}
