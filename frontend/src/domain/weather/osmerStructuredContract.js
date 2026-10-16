import { OSMER_AREA_TO_MAP_ZONE_ID } from "./osmerAdapter";

export const OSMER_STRUCTURED_STATES = Object.freeze({
  PARTIAL: "partial",
  READY: "ready",
  STALE: "stale",
  UNAVAILABLE: "unavailable",
});

export const OSMER_SOURCE_KINDS = Object.freeze({
  MIXED: "mixed",
  OFFICIAL_PROJECTED: "official_projected",
  STRUCTURED_XML: "structured_xml",
  UNKNOWN: "unknown",
});

const REQUIRED_AREA_IDS = Object.keys(OSMER_AREA_TO_MAP_ZONE_ID);
const REQUIRED_FASCE_IDS = ["F1", "F2", "F3", "F4"];

function normalizeToken(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function getSnapshotSourceKind(snapshot = {}) {
  const sourceKind = normalizeToken(snapshot.source_kind || snapshot.fonte);
  if (sourceKind === OSMER_SOURCE_KINDS.STRUCTURED_XML) return OSMER_SOURCE_KINDS.STRUCTURED_XML;
  if (sourceKind === OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED) return OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED;
  return OSMER_SOURCE_KINDS.UNKNOWN;
}

function getAreaSourceKind(area = {}, fallback = OSMER_SOURCE_KINDS.UNKNOWN) {
  const sourceKind = normalizeToken(area.source_kind || area.sourceKind);
  if (sourceKind === OSMER_SOURCE_KINDS.STRUCTURED_XML) return OSMER_SOURCE_KINDS.STRUCTURED_XML;
  if (sourceKind === OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED) return OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED;
  return fallback;
}

function getDaySourceKind(day = {}, snapshot = {}) {
  const daySourceKind = normalizeToken(day.source_kind || day.sourceKind);
  const fallback =
    daySourceKind === OSMER_SOURCE_KINDS.STRUCTURED_XML ||
    daySourceKind === OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED
      ? daySourceKind
      : getSnapshotSourceKind(snapshot);
  const areaSourceKinds = new Set(
    Object.values(day.areas9 || {})
      .map((area) => getAreaSourceKind(area, fallback))
      .filter((sourceKind) => sourceKind !== OSMER_SOURCE_KINDS.UNKNOWN),
  );

  if (areaSourceKinds.size === 1) return [...areaSourceKinds][0];
  if (areaSourceKinds.size > 1) return OSMER_SOURCE_KINDS.MIXED;
  return fallback;
}

function getMissingKeys(source = {}, requiredKeys = []) {
  return requiredKeys.filter((key) => !source?.[key]);
}

function isSnapshotUnavailable(snapshot = {}) {
  const sourceStatus = normalizeToken(snapshot.source_status || snapshot.sourceStatus);
  return sourceStatus.includes("unavailable") || sourceStatus.includes("404") || sourceStatus.includes("failed");
}

function isSnapshotStale(snapshot = {}) {
  return Boolean(snapshot.is_stale || snapshot.isStale || isSnapshotUnavailable(snapshot));
}

export function classifyOsmerStructuredDay(day = null, { snapshot = null } = {}) {
  const missingAreas = getMissingKeys(day?.areas9, REQUIRED_AREA_IDS);
  const missingFasce = getMissingKeys(day?.fasce4, REQUIRED_FASCE_IDS);
  const sourceKind = getDaySourceKind(day || {}, snapshot || {});
  const stale = isSnapshotStale(snapshot || {});
  let state = OSMER_STRUCTURED_STATES.READY;

  if (!day) {
    state = OSMER_STRUCTURED_STATES.UNAVAILABLE;
  } else if (stale) {
    state = OSMER_STRUCTURED_STATES.STALE;
  } else if (missingAreas.length || missingFasce.length) {
    state = OSMER_STRUCTURED_STATES.PARTIAL;
  }

  const hasCompleteAreas = missingAreas.length === 0;
  const hasCompleteFasce = missingFasce.length === 0;
  const canRenderMap = Boolean(day && hasCompleteAreas && state !== OSMER_STRUCTURED_STATES.STALE);
  const canRenderNativeMap = canRenderMap && sourceKind === OSMER_SOURCE_KINDS.STRUCTURED_XML;
  const canRenderProjectedMap = canRenderMap && sourceKind === OSMER_SOURCE_KINDS.OFFICIAL_PROJECTED;

  return {
    areaCount: REQUIRED_AREA_IDS.length - missingAreas.length,
    canRenderMap,
    canRenderNativeMap,
    canRenderProjectedMap,
    canUseFullBulletin:
      state === OSMER_STRUCTURED_STATES.READY &&
      sourceKind === OSMER_SOURCE_KINDS.STRUCTURED_XML,
    confidence: day?.quality?.confidence || snapshot?.quality?.confidence || "",
    fasceCount: REQUIRED_FASCE_IDS.length - missingFasce.length,
    hasCompleteAreas,
    hasCompleteFasce,
    missingAreas,
    missingFasce,
    sourceKind,
    state,
    validDate: day?.valid_date || "",
  };
}

export function classifyOsmerStructuredSnapshot(snapshot = null) {
  const days = Array.isArray(snapshot?.days) ? snapshot.days : [];
  const dayContracts = days.map((day) => classifyOsmerStructuredDay(day, { snapshot }));
  let state = OSMER_STRUCTURED_STATES.READY;

  if (!snapshot || !days.length) {
    state = OSMER_STRUCTURED_STATES.UNAVAILABLE;
  } else if (isSnapshotStale(snapshot)) {
    state = OSMER_STRUCTURED_STATES.STALE;
  } else if (dayContracts.some((day) => day.state === OSMER_STRUCTURED_STATES.PARTIAL)) {
    state = OSMER_STRUCTURED_STATES.PARTIAL;
  }

  return {
    canRenderNativeMap:
      state !== OSMER_STRUCTURED_STATES.STALE &&
      dayContracts.some((day) => day.canRenderNativeMap),
    canUseAsCurrent: state === OSMER_STRUCTURED_STATES.READY,
    confidence: snapshot?.quality?.confidence || "",
    dayContracts,
    daysCount: days.length,
    isStale: state === OSMER_STRUCTURED_STATES.STALE,
    parserVersion: snapshot?.parser_version || "",
    schemaVersion: snapshot?.schema_version || "",
    sourceKind: getSnapshotSourceKind(snapshot || {}),
    sourceStatus: snapshot?.source_status || "",
    state,
  };
}
