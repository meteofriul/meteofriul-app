import localMemoryArchive from "../../data/discover/localMemory.json";
import ostermannDiscoverBacklog from "../../data/discover/ostermannDiscoverBacklog.json";
import traditionalSayingsArchive from "../../data/discover/traditionalSayings.json";
import culturalDiscoverArchive from "./discoverCulturalRecords";
import { isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import {
  getTraditionalSayingForDate,
  getTraditionalSayingRecords,
} from "./traditionalSayings";

const DAILY_TARGET = 366;
const READY_LOCAL_MEMORY_SOURCE_TYPES = new Set(["verified_source", "editorial_note"]);

function getRecords(source) {
  if (Array.isArray(source)) return source;
  return Array.isArray(source?.records) ? source.records : [];
}

function getLeapYearDates() {
  return Array.from({ length: DAILY_TARGET }, (_, index) => {
    return new Date(Date.UTC(2024, 0, 1 + index, 12));
  });
}

function getLeapYearDayKeys(dates) {
  return dates.map((date) => {
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    const day = String(date.getUTCDate()).padStart(2, "0");
    return `${month}-${day}`;
  });
}

function getDateAnchors(records) {
  return [...new Set(records.flatMap((record) => (
    Array.isArray(record?.dateAnchors) ? record.dateAnchors : []
  )))].sort();
}

function isLocalMemoryReady(record) {
  if (!record || record.readyForUi !== true) return false;
  if (record.primaryUse !== "discover") return false;
  if (record.editorialStatus !== "ready_for_discover") return false;
  return READY_LOCAL_MEMORY_SOURCE_TYPES.has(record.source?.type);
}

export function getDiscoverCoverageSummary({
  culturalDiscoverRecords = culturalDiscoverArchive,
  localMemorySource = localMemoryArchive,
  ostermannBacklogSource = ostermannDiscoverBacklog,
  traditionalSayingsSource = traditionalSayingsArchive,
} = {}) {
  const curatedRecords = getRecords(culturalDiscoverRecords);
  const localMemoryRecords = getRecords(localMemorySource);
  const backlogRecords = getRecords(ostermannBacklogSource);
  const traditionalSayingRecords = getTraditionalSayingRecords(traditionalSayingsSource);
  const readyCurated = curatedRecords.filter(isCuratedDiscoverUiReady);
  const readyLocalMemory = localMemoryRecords.filter(isLocalMemoryReady);
  const readyPrimaryLocalMemory = readyLocalMemory.filter((record) => record.dailyRole !== "secondary");
  const readySecondaryLocalMemory = readyLocalMemory.filter((record) => record.dailyRole === "secondary");
  const readyTraditionalSayings = traditionalSayingRecords.filter(isLocalMemoryReady);
  const leapYearDates = getLeapYearDates();
  const leapYearDayKeys = getLeapYearDayKeys(leapYearDates);
  const localMemoryAllExactDays = getDateAnchors(readyLocalMemory);
  const localMemoryExactDays = getDateAnchors(readyPrimaryLocalMemory);
  const traditionalSayingExactDays = getDateAnchors(readyTraditionalSayings);
  const traditionalSayingSelections = leapYearDates.map((date) => getTraditionalSayingForDate({
    date,
    language: "it",
    source: traditionalSayingsSource,
  }));
  const missingLocalMemoryDays = leapYearDayKeys.filter((dayKey) => !localMemoryExactDays.includes(dayKey));
  const missingTraditionalSayingDays = leapYearDayKeys.filter((_, index) => (
    !traditionalSayingSelections[index]
  ));
  const traditionalSayingDailySelectionDays = DAILY_TARGET - missingTraditionalSayingDays.length;
  return {
    dailyTarget: DAILY_TARGET,
    discover: {
      curatedReady: readyCurated.length,
      curatedFurApproved: readyCurated.filter((record) => record.languageStatus?.fur === "approved").length,
      curatedExactDateDays: getDateAnchors(readyCurated).length,
      localMemoryReady: readyLocalMemory.length,
      localMemoryExactDateDays: localMemoryExactDays.length,
      localMemoryAllExactDateDays: localMemoryAllExactDays.length,
      localMemorySecondaryReady: readySecondaryLocalMemory.length,
      localMemoryMissingDays: missingLocalMemoryDays,
      localMemoryRotationRecords: readyPrimaryLocalMemory.filter((record) => !record.dateAnchors?.length).length,
      traditionalSayingsReady: readyTraditionalSayings.length,
      traditionalSayingsExactDateDays: traditionalSayingExactDays.length,
      traditionalSayingsDailySelectionDays: traditionalSayingDailySelectionDays,
      traditionalSayingsMissingDays: missingTraditionalSayingDays,
      backlogRecords: backlogRecords.length,
      backlogReadyForUi: backlogRecords.filter((record) => record.readyForUi === true).length,
    },
    readiness: {
      discoverHasDailyRotationPool:
        readyCurated.length > 0 ||
        readyLocalMemory.length > 0 ||
        readyTraditionalSayings.length > 0,
      discoverExactDateCalendarReady:
        localMemoryExactDays.length >= DAILY_TARGET &&
        traditionalSayingExactDays.length >= DAILY_TARGET,
      discoverDailyExperienceReady:
        localMemoryExactDays.length >= DAILY_TARGET &&
        readyCurated.length > 0,
      localMemoryCalendarReady: localMemoryExactDays.length >= DAILY_TARGET,
      traditionalSayingsCalendarReady: traditionalSayingExactDays.length >= DAILY_TARGET,
      traditionalSayingsDailySelectionReady: traditionalSayingDailySelectionDays >= DAILY_TARGET,
    },
  };
}
