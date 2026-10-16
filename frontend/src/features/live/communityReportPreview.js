import {
  buildCommunityIdentity,
  buildPublicCommunityIdentitySnapshot,
  normalizePublicCommunityIdentitySnapshot,
} from "../community/communityIdentity";
import {
  LIVE_REPORT_MAX_DISTANCE_KM,
  getLiveReportLocationDecision,
} from "./liveReportLocation";

export const COMMUNITY_REPORT_PREVIEW_QUERY = "communityReportQa";
export const COMMUNITY_REPORT_PREVIEW_MODE_ACTIVE = "active";
export const COMMUNITY_REPORT_PREVIEW_MODE_FORM = "preview";
export const COMMUNITY_REPORT_PREVIEW_MODE_INTERACTIVE = "interactive";

const COMMUNITY_REPORT_PREVIEW_DEV_BUILD = import.meta.env.DEV === true;

const COMMUNITY_REPORT_SIMULATION_TTL_MS = 60 * 60_000;
const COMMUNITY_REPORT_SIMULATION_UNDO_MS = 60_000;

function normalizePlace(value) {
  return String(value || "").trim().toLocaleLowerCase("it");
}

function normalizeSimulationIdentity(identity, placeName = "") {
  return normalizePublicCommunityIdentitySnapshot(identity)
    || buildPublicCommunityIdentitySnapshot(identity, { placeName });
}

function createPreviewIdentity(subjectId, placeName, revision) {
  return buildPublicCommunityIdentitySnapshot(buildCommunityIdentity({
    placeName,
    revision,
    subjectId,
  }));
}

function cloneSimulationIdentityEntries(entries) {
  if (!Array.isArray(entries)) return [];

  return entries
    .map((entry) => {
      const sourceKey = String(entry?.sourceKey ?? entry?.source_key ?? "").trim();
      if (!sourceKey) return null;

      return {
        identity: normalizePublicCommunityIdentitySnapshot(entry?.identity),
        sourceKey,
      };
    })
    .filter(Boolean);
}

function mergeSimulationIdentityEntries(...collections) {
  const entriesBySource = new Map();

  collections.flat().forEach((entry) => {
    const sourceKey = String(entry?.sourceKey || "").trim();
    if (!sourceKey) return;

    entriesBySource.set(sourceKey, {
      identity: normalizePublicCommunityIdentitySnapshot(entry?.identity),
      sourceKey,
    });
  });

  return [...entriesBySource.values()];
}

function cloneSimulationReport(report) {
  return {
    ...report,
    identity: normalizePublicCommunityIdentitySnapshot(report?.identity),
  };
}

export function getLocalCommunityReportPreviewMode({
  dev = COMMUNITY_REPORT_PREVIEW_DEV_BUILD,
  search = globalThis.location?.search || "",
} = {}) {
  if (!COMMUNITY_REPORT_PREVIEW_DEV_BUILD || dev !== true) return "";

  const mode = new URLSearchParams(search).get(COMMUNITY_REPORT_PREVIEW_QUERY);
  return [
    COMMUNITY_REPORT_PREVIEW_MODE_FORM,
    COMMUNITY_REPORT_PREVIEW_MODE_ACTIVE,
    COMMUNITY_REPORT_PREVIEW_MODE_INTERACTIVE,
  ]
    .includes(mode)
    ? mode
    : "";
}

export function isLocalCommunityReportPreviewEnabled(options) {
  return Boolean(getLocalCommunityReportPreviewMode(options));
}

export function createCommunityReportActivePreviewState(
  dataState,
  { now = Date.now() } = {},
) {
  const generatedAt = new Date(now).toISOString();
  const definitions = [
    {
      confirmations: { no: 0, yes: 4 },
      count: 3,
      groupId: "qa-rain-pordenone",
      lat: 45.9567,
      lon: 12.6605,
      minutesAgo: 4,
      place: "Pordenone",
      identityPlace: "Pordenon",
      subjectIds: ["claf", "acuile", "cjan"],
      typeId: "rain",
    },
    {
      confirmations: { no: 1, yes: 2 },
      count: 2,
      groupId: "qa-wind-cordenons",
      lat: 45.9836,
      lon: 12.7004,
      minutesAgo: 11,
      place: "Cordenons",
      identityPlace: "Cordenons",
      subjectIds: ["cevron", "cjampane"],
      typeId: "wind",
    },
    {
      confirmations: { no: 0, yes: 1 },
      count: 1,
      groupId: "qa-quiet-sacile",
      lat: 45.9509,
      lon: 12.5022,
      minutesAgo: 18,
      place: "Sacile",
      identityPlace: "Sacîl",
      subjectIds: ["cocal"],
      typeId: "quiet",
    },
  ];
  const groups = definitions.map((definition) => {
    const createdAt = now - definition.minutesAgo * 60_000;
    const sourceKeys = Array.from(
      { length: definition.count },
      (_, index) => `qa-source:${definition.groupId}:${index + 1}`,
    );
    const identities = sourceKeys.map((sourceKey, index) => ({
      identity: createPreviewIdentity(
        definition.subjectIds[index],
        definition.identityPlace,
        index,
      ),
      sourceKey,
    }));
    return {
      confirmations: definition.confirmations,
      count: definition.count,
      createdAt,
      expiresAt: createdAt + 60 * 60_000,
      groupId: definition.groupId,
      id: definition.groupId,
      identities,
      identity: identities[0].identity,
      lat: definition.lat,
      lon: definition.lon,
      place: definition.place,
      reportIds: [`${definition.groupId}-1`],
      sourceKeys,
      typeId: definition.typeId,
    };
  });
  const reports = groups.map((group) => ({
    createdAt: group.createdAt,
    expiresAt: group.expiresAt,
    groupId: group.groupId,
    id: `${group.groupId}-1`,
    identity: group.identities[0].identity,
    lat: group.lat,
    lon: group.lon,
    place: group.place,
    sourceKey: group.sourceKeys[0],
    typeId: group.typeId,
  }));

  return {
    ...dataState,
    community: {
      ...(dataState?.community || {}),
      ageMs: 0,
      error: null,
      payload: {
        ...(dataState?.community?.payload || {}),
        generated_at: generatedAt,
        map_groups: groups,
        reports,
      },
      status: "fresh",
    },
  };
}

export function createCommunityReportPreviewLocation({
  locations = [],
  maxDistanceKm = LIVE_REPORT_MAX_DISTANCE_KM,
  preferredPlace = "",
} = {}) {
  const validLocations = locations.filter((location) => (
    String(location?.place || "").trim()
    && Number.isFinite(Number(location?.lat))
    && Number.isFinite(Number(location?.lon))
  ));
  const preferredKey = normalizePlace(preferredPlace);
  const selected = validLocations.find(
    (location) => normalizePlace(location.place) === preferredKey,
  ) || validLocations[0];

  if (!selected) return { ok: false, reason: "unavailable" };

  const coords = {
    accuracyM: 0,
    lat: Number(selected.lat),
    lon: Number(selected.lon),
  };
  const decision = getLiveReportLocationDecision(coords, {
    locations: validLocations,
    maxDistanceKm,
  });

  if (!decision.ok) return decision;

  return {
    ...decision,
    coords,
    ok: true,
    selectedPlace: decision.detectedPlace,
    source: "local_preview",
  };
}

export async function blockCommunityReportPreviewSubmission() {
  return { ok: false, reason: "preview_only" };
}

function getSimulationTimestamp(now) {
  const timestamp = Number(typeof now === "function" ? now() : now);
  return Number.isFinite(timestamp) ? timestamp : Date.now();
}

function getSimulationPlace(location) {
  return String(
    location?.selectedPlace
      || location?.detectedPlace
      || "Pordenone",
  ).trim();
}

function getSimulationGroupId(typeId, place) {
  const placeKey = normalizePlace(place)
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/g, "");

  return `qa-local-${typeId}-${placeKey || "localita"}`;
}

function createSimulationSubmissionResult(
  typeId,
  location,
  { identity = null, now = Date.now, sequence = 0 } = {},
) {
  const normalizedTypeId = String(typeId || "").trim();
  const lat = Number(location?.coords?.lat);
  const lon = Number(location?.coords?.lon);
  const place = getSimulationPlace(location);
  if (
    !normalizedTypeId
    || !place
    || !Number.isFinite(lat)
    || !Number.isFinite(lon)
  ) {
    return { ok: false, reason: "preview_invalid" };
  }

  const timestamp = getSimulationTimestamp(now);
  const suffix = Math.max(0, Math.floor(Number(sequence) || 0));
  const reportId = `qa-local-${normalizedTypeId}-${timestamp}-${suffix}`;
  const identitySnapshot = normalizeSimulationIdentity(identity, place);

  return {
    ok: true,
    report: {
      createdAt: timestamp,
      expiresAt: timestamp + COMMUNITY_REPORT_SIMULATION_TTL_MS,
      groupId: getSimulationGroupId(normalizedTypeId, place),
      id: reportId,
      identity: identitySnapshot,
      lat,
      lon,
      place,
      sourceKey: "qa-local-preview",
      typeId: normalizedTypeId,
    },
    undoUntil: timestamp + COMMUNITY_REPORT_SIMULATION_UNDO_MS,
  };
}

function cloneSimulationGroup(group) {
  return {
    ...group,
    confirmations: {
      no: Math.max(0, Number(group?.confirmations?.no) || 0),
      yes: Math.max(0, Number(group?.confirmations?.yes) || 0),
    },
    reportIds: [...(Array.isArray(group?.reportIds) ? group.reportIds : [])],
    identities: cloneSimulationIdentityEntries(group?.identities),
    identity: normalizePublicCommunityIdentitySnapshot(group?.identity),
    sourceKeys: [...(Array.isArray(group?.sourceKeys) ? group.sourceKeys : [])],
  };
}

/**
 * Creates a Web Storage compatible object that never touches browser storage.
 * It is intentionally reset whenever its owner recreates it (for example on reload).
 */
export function createCommunityReportPreviewMemoryStorage(initialValues = {}) {
  const values = new Map(
    Object.entries(initialValues).map(([key, value]) => [String(key), String(value)]),
  );

  return {
    clear() {
      values.clear();
    },
    getItem(key) {
      const normalizedKey = String(key);
      return values.has(normalizedKey) ? values.get(normalizedKey) : null;
    },
    key(index) {
      return [...values.keys()][Number(index)] ?? null;
    },
    get length() {
      return values.size;
    },
    removeItem(key) {
      values.delete(String(key));
    },
    setItem(key, value) {
      values.set(String(key), String(value));
    },
  };
}

/**
 * Owns only the volatile community portion of the interactive QA preview.
 * Webcam/runtime state remains outside this object and can be overlaid later.
 */
export function createCommunityReportSimulationOverlay(
  dataState,
  { now = Date.now() } = {},
) {
  const previewState = createCommunityReportActivePreviewState(dataState, { now });
  const payload = previewState.community.payload;

  return {
    generatedAt: payload.generated_at,
    mapGroups: payload.map_groups.map(cloneSimulationGroup),
    nextReportSequence: 1,
    ownedReportIds: [],
    reports: payload.reports.map(cloneSimulationReport),
    votes: {},
  };
}

export function applyCommunityReportSimulationOverlay(dataState, overlay) {
  return {
    ...dataState,
    community: {
      ...(dataState?.community || {}),
      ageMs: 0,
      error: null,
      payload: {
        ...(dataState?.community?.payload || {}),
        generated_at: overlay.generatedAt,
        map_groups: overlay.mapGroups.map(cloneSimulationGroup),
        reports: overlay.reports.map(cloneSimulationReport),
      },
      status: "fresh",
    },
  };
}

export function applyCommunityReportSimulationSubmission(
  overlay,
  typeId,
  location,
  { identity = null, now = Date.now } = {},
) {
  const result = createSimulationSubmissionResult(typeId, location, {
    identity,
    now,
    sequence: overlay.nextReportSequence,
  });
  if (!result.ok) return { overlay, result };

  const report = result.report;
  const existingGroup = overlay.mapGroups.find((group) => group.groupId === report.groupId);
  const nextGroup = existingGroup
    ? {
      ...cloneSimulationGroup(existingGroup),
      count: Math.max(0, Number(existingGroup.count) || 0) + 1,
      createdAt: report.createdAt,
      expiresAt: Math.max(Number(existingGroup.expiresAt) || 0, report.expiresAt),
      identities: mergeSimulationIdentityEntries(
        existingGroup.identities,
        [{ identity: report.identity, sourceKey: report.sourceKey }],
      ),
      identity: report.identity,
      reportIds: [...new Set([...(existingGroup.reportIds || []), report.id])],
      sourceKeys: [...new Set([...(existingGroup.sourceKeys || []), report.sourceKey])],
    }
    : {
      confirmations: { no: 0, yes: 0 },
      count: 1,
      createdAt: report.createdAt,
      expiresAt: report.expiresAt,
      groupId: report.groupId,
      id: report.groupId,
      identities: [{ identity: report.identity, sourceKey: report.sourceKey }],
      identity: report.identity,
      lat: report.lat,
      lon: report.lon,
      place: report.place,
      reportIds: [report.id],
      sourceKeys: [report.sourceKey],
      typeId: report.typeId,
    };
  const mapGroups = existingGroup
    ? overlay.mapGroups.map((group) => (
      group.groupId === report.groupId ? nextGroup : cloneSimulationGroup(group)
    ))
    : [...overlay.mapGroups.map(cloneSimulationGroup), nextGroup];

  return {
    overlay: {
      ...overlay,
      generatedAt: new Date(report.createdAt).toISOString(),
      mapGroups,
      nextReportSequence: overlay.nextReportSequence + 1,
      ownedReportIds: [...overlay.ownedReportIds, report.id],
      reports: [...overlay.reports.map(cloneSimulationReport), cloneSimulationReport(report)],
      votes: { ...overlay.votes },
    },
    result,
  };
}

export function applyCommunityReportSimulationConfirmation(
  overlay,
  groupId,
  vote,
  { now = Date.now } = {},
) {
  const normalizedGroupId = String(groupId || "").trim();
  const normalizedVote = String(vote || "").trim().toLowerCase();
  if (!normalizedGroupId || !["yes", "no"].includes(normalizedVote)) {
    return { overlay, result: { ok: false, reason: "preview_invalid" } };
  }

  const target = overlay.mapGroups.find((group) => group.groupId === normalizedGroupId);
  if (!target) {
    return { overlay, result: { ok: false, reason: "preview_not_found", status: 404 } };
  }

  const previousVote = overlay.votes[normalizedGroupId] || "";
  if (previousVote === normalizedVote) {
    return {
      overlay,
      result: {
        confirmations: { ...target.confirmations },
        group: cloneSimulationGroup(target),
        groupId: normalizedGroupId,
        ok: true,
        vote: normalizedVote,
      },
    };
  }

  const confirmations = {
    no: Math.max(0, Number(target.confirmations?.no) || 0),
    yes: Math.max(0, Number(target.confirmations?.yes) || 0),
  };
  if (["yes", "no"].includes(previousVote)) {
    confirmations[previousVote] = Math.max(0, confirmations[previousVote] - 1);
  }
  confirmations[normalizedVote] += 1;
  const updatedGroup = { ...cloneSimulationGroup(target), confirmations };
  const timestamp = getSimulationTimestamp(now);
  const nextOverlay = {
    ...overlay,
    generatedAt: new Date(timestamp).toISOString(),
    mapGroups: overlay.mapGroups.map((group) => (
      group.groupId === normalizedGroupId ? updatedGroup : cloneSimulationGroup(group)
    )),
    ownedReportIds: [...overlay.ownedReportIds],
    reports: overlay.reports.map(cloneSimulationReport),
    votes: { ...overlay.votes, [normalizedGroupId]: normalizedVote },
  };

  return {
    overlay: nextOverlay,
    result: {
      confirmations: { ...confirmations },
      group: cloneSimulationGroup(updatedGroup),
      groupId: normalizedGroupId,
      ok: true,
      vote: normalizedVote,
    },
  };
}

export function applyCommunityReportSimulationUndo(
  overlay,
  reportId,
  { now = Date.now } = {},
) {
  const normalizedReportId = String(reportId || "").trim();
  const report = overlay.reports.find((entry) => entry.id === normalizedReportId);
  if (!report || !overlay.ownedReportIds.includes(normalizedReportId)) {
    return { overlay, result: { ok: false, reason: "preview_not_found", status: 404 } };
  }

  const target = overlay.mapGroups.find((group) => group.groupId === report.groupId);
  const remainingReportIds = (target?.reportIds || []).filter(
    (entry) => entry !== normalizedReportId,
  );
  const remainingCount = Math.max(0, (Number(target?.count) || 0) - 1);
  const removeGroup = !target || (remainingCount === 0 && remainingReportIds.length === 0);
  const mapGroups = overlay.mapGroups
    .filter((group) => group.groupId !== report.groupId || !removeGroup)
    .map((group) => (
      group.groupId === report.groupId
        ? { ...cloneSimulationGroup(group), count: remainingCount, reportIds: remainingReportIds }
        : cloneSimulationGroup(group)
    ));
  const votes = { ...overlay.votes };
  if (removeGroup) delete votes[report.groupId];
  const timestamp = getSimulationTimestamp(now);

  return {
    overlay: {
      ...overlay,
      generatedAt: new Date(timestamp).toISOString(),
      mapGroups,
      ownedReportIds: overlay.ownedReportIds.filter((entry) => entry !== normalizedReportId),
      reports: overlay.reports
        .filter((entry) => entry.id !== normalizedReportId)
        .map(cloneSimulationReport),
      votes,
    },
    result: { ok: true, reportId: normalizedReportId },
  };
}

export async function simulateCommunityReportSubmission(
  typeId,
  location,
  { identity = null, now = Date.now } = {},
) {
  return createSimulationSubmissionResult(typeId, location, { identity, now });
}

export async function simulateCommunityReportConfirmation(groupId, vote) {
  const normalizedGroupId = String(groupId || "").trim();
  const normalizedVote = String(vote || "").trim().toLowerCase();
  if (!normalizedGroupId || !["yes", "no"].includes(normalizedVote)) {
    return { ok: false, reason: "preview_invalid" };
  }

  return {
    groupId: normalizedGroupId,
    ok: true,
    vote: normalizedVote,
  };
}

export async function simulateCommunityReportUndo(reportId) {
  const normalizedReportId = String(reportId || "").trim();
  return normalizedReportId
    ? { ok: true, reportId: normalizedReportId }
    : { ok: false, reason: "preview_invalid" };
}

// Browser-only QA mirrors the pilot actions without calling any community API.
export function applyPilotReportSimulationSubmission(overlay, typeId, location, {
  correctionReport = null, replacementReport = null, replacementToken = "", identity = null,
} = {}, { now = Date.now() } = {}) {
  const payload = { typeId, location, identity, report: correctionReport, replacementToken };
  if (!replacementReport) return applyPilotReportSimulation(overlay, correctionReport ? "correct" : "create", payload, { now });
  if (correctionReport) return { overlay, result: { ok: false, reason: "invalid_intent" } };
  const reportId = String(replacementReport.reportId || replacementReport.id || "").trim();
  let current = overlay;
  let grant = current.pilotReplacement;
  if (grant && grant.previous.id !== reportId) return { overlay, result: { ok: false, reason: "pending_operation" } };
  if (!grant?.token) {
    const retired = applyPilotReportSimulation(current, "replace", { reportId }, { now });
    if (!retired.result.ok) return {
      ...retired,
      result: { ...retired.result, replacementPhase: "withdrawal", replacementWithdrawn: false },
    };
    current = retired.overlay;
    grant = current.pilotReplacement;
  }
  const mutation = grant.previous.expiresAt <= now
    ? { overlay: current, result: { ok: false, code: "community_replacement_expired", reason: "rejected" } }
    : applyPilotReportSimulation(current, "create", { ...payload, replacementToken: grant.token }, { now });
  return {
    ...mutation,
    result: {
      ...mutation.result, replacedReportId: reportId, replacementPhase: "creation", replacementWithdrawn: true,
      replacementToken: mutation.result.ok ? null : grant.token,
    },
  };
}

export function applyPilotReportSimulation(overlay, kind, payload, { now = Date.now() } = {}) {
  const fail = (code) => ({ overlay, result: { ok: false, code, reason: "rejected" } });
  const reportId = payload.reportId || payload.report?.reportId;
  const previous = overlay.reports.find((report) => report.id === reportId && overlay.ownedReportIds.includes(report.id));
  const previousGroup = previous && overlay.mapGroups.find((group) => group.groupId === previous.groupId);
  const creates = (overlay.pilotCreates || []).filter((timestamp) => timestamp > now - 24 * 60 * 60_000);
  if (kind !== "create") {
    if (!previous || previous.expiresAt <= now) return fail("community_observation_expired");
    if (Number(previousGroup?.confirmations?.no) >= 3) return fail("community_group_hidden");
  }
  if (kind === "update") {
    const report = { ...previous, revision: (previous.revision || 1) + 1, updatedAt: now, expiresAt: now + COMMUNITY_REPORT_SIMULATION_TTL_MS };
    return { overlay: {
      ...overlay,
      reports: overlay.reports.map((entry) => entry.id === report.id ? report : entry),
      mapGroups: overlay.mapGroups.map((entry) => entry.groupId === report.groupId ? { ...entry, expiresAt: report.expiresAt, updatedAt: now } : entry),
    }, result: { ok: true, action: "updated", report, revision: report.revision } };
  }
  if (kind === "withdraw" || kind === "replace") {
    if (kind === "replace" && previous.replacementAvailable !== true) return fail("community_replacement_unavailable");
    const mutation = applyCommunityReportSimulationUndo(overlay, reportId, { now: () => now });
    const token = kind === "replace" ? `qa-replace:${reportId}` : null;
    return {
      overlay: { ...mutation.overlay, votes: { ...overlay.votes }, pilotReplacement: token ? { token, previous } : overlay.pilotReplacement },
      result: { ok: true, reportId, action: token ? "replacement_ready" : "withdrawn", replacementToken: token },
    };
  }
  if (kind === "correct" && now >= Number(previous.correctionUntil)) return fail("community_correction_window_closed");
  const replacement = payload.replacementToken && overlay.pilotReplacement?.token === payload.replacementToken ? overlay.pilotReplacement : null;
  if (kind === "create") {
    if (creates.length >= 12) return fail("community_daily_limit");
    if (creates.filter((time) => time > now - 60 * 60_000).length >= 4) return fail("community_hourly_limit");
    if (!replacement && creates.some((time) => time > now - 120_000)) return fail("community_minimum_interval");
  }
  if (overlay.reports.some((entry) => overlay.ownedReportIds.includes(entry.id)
    && entry.id !== reportId && entry.expiresAt > now && entry.typeId === payload.typeId
    && entry.place === payload.location.selectedPlace)) return fail("community_observation_already_recent");
  const base = kind === "correct" ? applyCommunityReportSimulationUndo(overlay, reportId, { now: () => now }).overlay : overlay;
  const mutation = applyCommunityReportSimulationSubmission(base, payload.typeId, payload.location, { identity: previous?.identity || payload.identity, now: () => now });
  if (!mutation.result.ok) return mutation;
  const generatedId = mutation.result.report.id;
  const ancestor = previous || replacement?.previous;
  const report = {
    ...mutation.result.report,
    id: previous?.id || generatedId,
    createdAt: previous?.createdAt || now,
    expiresAt: previous?.expiresAt || now + COMMUNITY_REPORT_SIMULATION_TTL_MS,
    correctionUntil: previous?.correctionUntil || now + 300_000,
    replacementAvailable: previous ? previous.replacementAvailable : !replacement,
    revision: previous ? (previous.revision || 1) + 1 : 1,
    lineageGroupIds: ancestor ? [...new Set([...(ancestor.lineageGroupIds || []), ancestor.groupId])] : [],
  };
  return { overlay: {
    ...mutation.overlay,
    pilotCreates: kind === "create" ? [...creates, now] : creates,
    pilotReplacement: replacement ? null : overlay.pilotReplacement,
    ownedReportIds: mutation.overlay.ownedReportIds.map((id) => id === generatedId ? report.id : id),
    reports: mutation.overlay.reports.map((entry) => entry.id === generatedId ? report : entry),
    mapGroups: mutation.overlay.mapGroups.map((entry) => entry.groupId === report.groupId ? {
      ...entry, lineageGroupIds: report.lineageGroupIds,
      confirmations: previousGroup?.confirmations || entry.confirmations,
      createdAt: report.createdAt, expiresAt: report.expiresAt,
      reportIds: entry.reportIds.map((id) => id === generatedId ? report.id : id),
    } : entry),
    votes: { ...overlay.votes },
  }, result: { ok: true, action: previous ? "corrected" : "created", report, revision: report.revision } };
}
