import localMemoryArchive from "../../data/discover/localMemory.json";
import traditionalSayingsArchive from "../../data/discover/traditionalSayings.json";
import { getTraditionalSayingRecords } from "./traditionalSayings";

const DAILY_TARGET = 366;
const READY_LOCAL_MEMORY_SOURCE_TYPES = new Set(["verified_source", "editorial_note"]);

function getRecords(source) {
  if (Array.isArray(source)) return source;
  return Array.isArray(source?.records) ? source.records : [];
}

function getCalendarDayKeys() {
  return Array.from({ length: DAILY_TARGET }, (_, index) => {
    const date = new Date(Date.UTC(2024, 0, 1 + index));
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    const day = String(date.getUTCDate()).padStart(2, "0");
    return `${month}-${day}`;
  });
}

function isReadyLocalMemory(record) {
  if (!record || record.readyForUi !== true) return false;
  if (record.primaryUse !== "discover") return false;
  if (record.editorialStatus !== "ready_for_discover") return false;
  return READY_LOCAL_MEMORY_SOURCE_TYPES.has(record.source?.type);
}

function isReadyTraditionalSaying(record) {
  if (!record || record.readyForUi !== true) return false;
  if (record.primaryUse !== "discover") return false;
  if (record.editorialStatus !== "ready_for_discover") return false;
  return record.source?.type === "verified_source";
}

function compareRecords(first, second) {
  const priorityDiff = Number(first.priority || 99) - Number(second.priority || 99);
  if (priorityDiff) return priorityDiff;
  return String(first.id).localeCompare(String(second.id));
}

function findExactRecord(records, dayKey) {
  return records
    .filter((record) => Array.isArray(record.dateAnchors) && record.dateAnchors.includes(dayKey))
    .sort(compareRecords)[0] || null;
}

function getTitle(record) {
  return record?.title?.it || record?.it || record?.fur || "";
}

function getSourceLabel(record) {
  if (!record) return "";
  return record.source?.label || record.source || "";
}

function buildDiscoverSlot(record, missingStatus) {
  if (!record) {
    return {
      status: missingStatus,
      id: null,
      title: "",
      sourceLabel: "",
      sourceStatus: "missing",
    };
  }

  return {
    status: "ready",
    id: record.id,
    title: getTitle(record),
    sourceLabel: getSourceLabel(record),
    sourceStatus: record.source?.type || record.editorialStatus || "ready",
  };
}

export function getDiscoverDailyCalendarPlan({
  localMemorySource = localMemoryArchive,
  traditionalSayingsSource = traditionalSayingsArchive,
} = {}) {
  const readyMemory = getRecords(localMemorySource)
    .filter((record) => isReadyLocalMemory(record) && record.dailyRole !== "secondary");
  const readySayings = getTraditionalSayingRecords(traditionalSayingsSource)
    .filter(isReadyTraditionalSaying);

  return getCalendarDayKeys().map((dayKey) => ({
    dayKey,
    memory: buildDiscoverSlot(findExactRecord(readyMemory, dayKey), "missing_memory"),
    saying: buildDiscoverSlot(findExactRecord(readySayings, dayKey), "missing_saying"),
  }));
}

export function getDiscoverDailyCalendarPlanSummary(options = {}) {
  const plan = getDiscoverDailyCalendarPlan(options);
  const countByStatus = (slotName, status) => plan.filter((row) => row[slotName].status === status).length;
  const memoryMissingDayKeys = plan.filter((row) => row.memory.status !== "ready").map((row) => row.dayKey);
  const sayingMissingDayKeys = plan.filter((row) => row.saying.status !== "ready").map((row) => row.dayKey);

  return {
    dailyTarget: DAILY_TARGET,
    memoryReadyDays: countByStatus("memory", "ready"),
    memoryMissingDays: countByStatus("memory", "missing_memory"),
    sayingReadyDays: countByStatus("saying", "ready"),
    sayingMissingDays: countByStatus("saying", "missing_saying"),
    january: plan.filter((row) => row.dayKey.startsWith("01-")),
    memoryMissingDayKeys,
    sayingMissingDayKeys,
    firstMissingMemoryDays: memoryMissingDayKeys.slice(0, 20),
    firstMissingSayingDays: sayingMissingDayKeys.slice(0, 20),
  };
}
