import {
  DEVICE_GEOLOCATION_OPTIONS,
  requestDeviceCoordinates,
} from "../../services/deviceLocation";
import {
  deleteCommunityReport,
  getOrCreateLiveReportClientId,
  getPersistentLiveReportClientId,
  postCommunityReport,
  postCommunityReportConfirmation,
  postCommunityReportFlag,
  resolveLocalCommunityReportLocation,
  updateLocalCommunityReport,
  withdrawLocalCommunityReport,
} from "../../services/liveApi";
import {
  communityStorageKey,
  isLocalCommunityPilot,
} from "../../services/localCommunityPilot";
import {
  LIVE_REPORT_LOCATIONS,
  LIVE_REPORT_MAX_ACCURACY_M,
  LIVE_REPORT_MAX_AGE_MS,
  LIVE_REPORT_MAX_DISTANCE_KM,
  getLiveReportLocationDecision,
} from "./liveReportLocation";
import { COMMUNITY_GUIDELINES_POLICY_VERSION } from "./liveReportPolicy";
import { performPilotReportOperation, readPilotPendingOperations, readPilotReplacement } from "./pilotReportOperations";

export const LIVE_REPORT_UPDATE_OPERATIONS_KEY = communityStorageKey(
  "meteoFriul:communityReportUpdateOperations:v1",
);
export const LIVE_REPORT_SUBMIT_MAX_AGE_MS = 30 * 1000;

const activeUpdatePromises = new Map();
const activeReplacementSubmissions = new Map();
const updateOperationMemory = new Map();
// An accepted refresh remains active for about one hour. Keeping the recovery
// key slightly longer covers a response lost near the original expiry without
// surfacing a retry for an observation that cannot still be current.
const LIVE_REPORT_UPDATE_OPERATION_RETENTION_MS = 65 * 60 * 1000;
const LIVE_REPORT_UPDATE_OPERATION_LIMIT = 32;
const TERMINAL_UPDATE_REJECTION_CODES = new Set([
  "community_group_hidden",
  "community_observation_not_active",
  "community_observation_not_updateable",
  "community_observation_owner_mismatch",
]);

function getUpdateOperationStorage(storage) {
  if (storage !== undefined) return storage;
  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}

function normalizeStoredUpdateOperations(value, now = Date.now()) {
  const numericNow = Number(now);
  return Object.fromEntries(Object.entries(
    value && typeof value === "object" && !Array.isArray(value) ? value : {},
  )
    .filter(([, operation]) => (
      String(operation?.operationId || "").trim()
      && Number.isInteger(Number(operation?.expectedRevision))
      && Number(operation.expectedRevision) > 0
      && Number.isFinite(Number(operation?.createdAt))
      && Number(operation.createdAt) > numericNow - LIVE_REPORT_UPDATE_OPERATION_RETENTION_MS
      && Number(operation.createdAt) <= numericNow
    ))
    .sort(([, first], [, second]) => Number(second.createdAt) - Number(first.createdAt))
    .slice(0, LIVE_REPORT_UPDATE_OPERATION_LIMIT));
}

function pruneUpdateOperationMemory(now) {
  const normalized = normalizeStoredUpdateOperations(
    Object.fromEntries(updateOperationMemory.entries()),
    now,
  );
  updateOperationMemory.clear();
  Object.entries(normalized).forEach(([reportId, operation]) => {
    updateOperationMemory.set(reportId, operation);
  });
}

function readStoredUpdateOperations(storage, now) {
  try {
    const parsed = JSON.parse(storage?.getItem?.(LIVE_REPORT_UPDATE_OPERATIONS_KEY) || "null");
    return normalizeStoredUpdateOperations(parsed, now);
  } catch {
    return {};
  }
}

function writeStoredUpdateOperations(operations, storage) {
  try {
    storage?.setItem?.(LIVE_REPORT_UPDATE_OPERATIONS_KEY, JSON.stringify(operations));
  } catch {
    // Module memory still preserves the key for the running app instance.
  }
}

function createUpdateOperationId(cryptoLike = globalThis.crypto) {
  return typeof cryptoLike?.randomUUID === "function"
    ? cryptoLike.randomUUID()
    : `community-update-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function getOrCreateUpdateOperation(
  reportId,
  expectedRevision,
  { now = Date.now(), operationIdFactory = createUpdateOperationId, storage } = {},
) {
  pruneUpdateOperationMemory(now);
  const resolvedStorage = getUpdateOperationStorage(storage);
  const stored = readStoredUpdateOperations(resolvedStorage, now);
  const rememberedInMemory = updateOperationMemory.get(reportId);
  const remembered = stored[reportId] || (
    Number(rememberedInMemory?.createdAt) > Number(now) - LIVE_REPORT_UPDATE_OPERATION_RETENTION_MS
      ? rememberedInMemory
      : null
  );
  if (
    remembered
    && String(remembered.operationId || "").trim()
    && Number.isInteger(Number(remembered.expectedRevision))
    && Number(remembered.expectedRevision) > 0
  ) {
    updateOperationMemory.set(reportId, remembered);
    return remembered;
  }

  const operation = {
    createdAt: Number(now),
    expectedRevision,
    operationId: String(operationIdFactory()).trim(),
  };
  if (!operation.operationId) throw new Error("community_update_operation_id_unavailable");
  updateOperationMemory.set(reportId, operation);
  writeStoredUpdateOperations({ ...stored, [reportId]: operation }, resolvedStorage);
  return operation;
}

function clearUpdateOperation(reportId, operationId, storage, now) {
  const current = updateOperationMemory.get(reportId);
  if (!current || current.operationId === operationId) updateOperationMemory.delete(reportId);

  const resolvedStorage = getUpdateOperationStorage(storage);
  const stored = readStoredUpdateOperations(resolvedStorage, now);
  if (stored[reportId]?.operationId !== operationId) return;
  delete stored[reportId];
  writeStoredUpdateOperations(stored, resolvedStorage);
}

export function readPendingLiveCommunityReportUpdates({
  now = Date.now,
  operationStorage,
} = {}) {
  const numericNow = Number(typeof now === "function" ? now() : now);
  const resolvedNow = Number.isFinite(numericNow) ? numericNow : Date.now();
  pruneUpdateOperationMemory(resolvedNow);
  const resolvedStorage = getUpdateOperationStorage(operationStorage);
  const stored = readStoredUpdateOperations(resolvedStorage, resolvedNow);
  const memory = operationStorage === undefined
    ? Object.fromEntries(updateOperationMemory.entries())
    : {};
  const operations = normalizeStoredUpdateOperations({ ...memory, ...stored }, resolvedNow);

  // Reading is also the bounded pruning point used when the app is reopened.
  writeStoredUpdateOperations(operations, resolvedStorage);
  return Object.entries(operations).map(([reportId, operation]) => ({
    ...operation,
    reportId,
  }));
}

export function reconcilePendingLiveCommunityReportUpdate(
  report,
  {
    now = Date.now,
    operationStorage,
  } = {},
) {
  const reportId = String(report?.id || report?.reportId || "").trim();
  const groupId = String(report?.groupId || report?.group_id || "").trim();
  const revision = Number(report?.revision);
  const numericNow = Number(typeof now === "function" ? now() : now);
  const resolvedNow = Number.isFinite(numericNow) ? numericNow : Date.now();
  const expiresAt = Number(report?.expiresAt || report?.expires_at);
  if (
    !reportId
    || !groupId
    || !Number.isInteger(revision)
    || revision <= 0
    || !Number.isFinite(expiresAt)
    || expiresAt <= resolvedNow
  ) {
    return { ok: false, reason: "invalid_report" };
  }

  const pending = readPendingLiveCommunityReportUpdates({ now, operationStorage })
    .find((operation) => operation.reportId === reportId);
  if (!pending) return { ok: false, reason: "no_pending_update" };
  if (revision <= pending.expectedRevision) {
    return {
      expectedRevision: pending.expectedRevision,
      ok: false,
      reason: "revision_not_advanced",
      reportId,
      revision,
    };
  }

  clearUpdateOperation(
    reportId,
    pending.operationId,
    operationStorage,
    resolvedNow,
  );
  return {
    action: "reconciled",
    expectedRevision: pending.expectedRevision,
    ok: true,
    operationId: pending.operationId,
    report,
    reportId,
    revision,
  };
}

function getCommunityErrorCode(error) {
  return error?.detail && typeof error.detail === "object"
    ? String(error.detail.code || "").trim()
    : "";
}

function getExpiredObservationState(detail, expectedReportId) {
  const state = detail?.state;
  const reportId = String(state?.report_id || "").trim();
  const status = String(state?.status || "").trim();
  const expiresAt = Number(state?.expires_at);
  const serverTime = Number(state?.server_time);
  const revision = Number(state?.revision);
  if (
    reportId !== expectedReportId
    || status !== "expired"
    || !Number.isFinite(expiresAt)
    || expiresAt <= 0
    || !Number.isFinite(serverTime)
    || serverTime <= 0
    || serverTime < expiresAt
    || !Number.isInteger(revision)
    || revision <= 0
  ) {
    return null;
  }
  return {
    ...state,
    expires_at: expiresAt,
    report_id: reportId,
    revision,
    server_time: serverTime,
    status,
  };
}

function getRecentObservationState(detail, expectedReportId, expectedRevision) {
  const state = detail?.state;
  const reportId = String(state?.report_id || "").trim();
  const status = String(state?.status || "").trim();
  const expiresAt = Number(state?.expires_at);
  const serverTime = Number(state?.server_time);
  const revision = Number(state?.revision);
  if (
    reportId !== expectedReportId
    || status !== "recent"
    || !Number.isFinite(expiresAt)
    || expiresAt <= 0
    || !Number.isFinite(serverTime)
    || serverTime <= 0
    || expiresAt <= serverTime
    || !Number.isInteger(revision)
    || revision <= expectedRevision
  ) {
    return null;
  }
  return {
    ...state,
    expires_at: expiresAt,
    report_id: reportId,
    revision,
    server_time: serverTime,
    status,
  };
}

export async function locateLiveCommunityReport({
  coordinateResolver = requestDeviceCoordinates,
  locations = LIVE_REPORT_LOCATIONS,
  maxDistanceKm = LIVE_REPORT_MAX_DISTANCE_KM,
  nationalResolver = resolveLocalCommunityReportLocation,
  pilotEnabled = isLocalCommunityPilot(),
  requireCurrent = false,
} = {}) {
  const localCommunityPilot = pilotEnabled === true;
  const requestedDistance = Number(maxDistanceKm);
  const effectiveMaxDistanceKm = Number.isFinite(requestedDistance) && requestedDistance > 0
    ? Math.min(requestedDistance, LIVE_REPORT_MAX_DISTANCE_KM)
    : LIVE_REPORT_MAX_DISTANCE_KM;
  const deviceLocation = await coordinateResolver({
    maxAccuracyM: localCommunityPilot ? 500 : LIVE_REPORT_MAX_ACCURACY_M,
    maxAgeMs: requireCurrent ? LIVE_REPORT_SUBMIT_MAX_AGE_MS : LIVE_REPORT_MAX_AGE_MS,
    ...(requireCurrent ? {
      options: DEVICE_GEOLOCATION_OPTIONS,
      requireCurrent: true,
    } : {}),
  });
  if (!deviceLocation?.ok) {
    return {
      ok: false,
      reason: deviceLocation?.reason || "unavailable",
      source: deviceLocation?.source || null,
    };
  }

  const rawAccuracyM = deviceLocation.coords?.accuracyM;
  const accuracyM = rawAccuracyM == null ? Number.NaN : Number(rawAccuracyM);
  const rawAgeMs = deviceLocation.ageMs;
  const ageMs = rawAgeMs == null ? Number.NaN : Number(rawAgeMs);
  if (
    !Number.isFinite(accuracyM)
    || accuracyM < 0
    || (localCommunityPilot && accuracyM === 0)
    || accuracyM > (localCommunityPilot ? 500 : LIVE_REPORT_MAX_ACCURACY_M)
    || !Number.isFinite(ageMs)
    || ageMs < 0
    || ageMs > LIVE_REPORT_MAX_AGE_MS
  ) {
    return {
      ok: false,
      reason: "stale_or_imprecise",
      source: deviceLocation.source || null,
    };
  }

  if (localCommunityPilot) {
    const locatedAt = Date.now() - ageMs;
    try {
      const decision = await nationalResolver({ coords: deviceLocation.coords, ageMs });
      if (!decision?.ok || !/^\d{6}$/.test(String(decision.istatCode || ""))) {
        return { ok: false, reason: "out_of_area" };
      }
      return {
        ...decision,
        coords: deviceLocation.coords,
        locatedAt,
        source: deviceLocation.source || null,
      };
    } catch (error) {
      return {
        ok: false,
        reason: "location_verification_failed",
        error: error?.message || "Posizione non verificabile.",
      };
    }
  }

  const decision = getLiveReportLocationDecision(deviceLocation.coords, {
    locations,
    maxDistanceKm: effectiveMaxDistanceKm,
  });
  if (!decision.ok) {
    return {
      ...decision,
      source: deviceLocation.source || null,
    };
  }

  return {
    ...decision,
    coords: deviceLocation.coords,
    selectedPlace: decision.detectedPlace,
    source: deviceLocation.source || null,
  };
}

export async function submitLiveCommunityReport(
  typeId,
  location,
  {
    acceptedTerms = false,
    clientIdResolver = getOrCreateLiveReportClientId,
    identity = null,
    policyVersion = COMMUNITY_GUIDELINES_POLICY_VERSION,
    reportPoster = postCommunityReport,
    correctionReport = null,
    replacementReport = null,
    replacementToken = "",
    operationStorage,
    pilotOperation = performPilotReportOperation,
  } = {},
) {
  const normalizedTypeId = String(typeId || "").trim();
  if (!normalizedTypeId) return { ok: false, reason: "missing_type" };
  if (!location?.coords) return { ok: false, reason: "location_required" };
  if (
    acceptedTerms !== true
    || policyVersion !== COMMUNITY_GUIDELINES_POLICY_VERSION
  ) {
    return { ok: false, reason: "terms_required" };
  }

  const selectedPlace = String(location.selectedPlace || "").trim();
  const allowedPlaces = Array.isArray(location.nearbyPlaces)
    ? location.nearbyPlaces.map((item) => String(item.place || "").trim())
    : [];
  if (!selectedPlace || !allowedPlaces.includes(selectedPlace)) {
    return { ok: false, reason: "invalid_place" };
  }

  if (replacementReport && !isLocalCommunityPilot()) return { ok: false, reason: "local_pilot_required" };
  if (correctionReport && replacementReport) return { ok: false, reason: "invalid_intent" };

  if (isLocalCommunityPilot()) {
    const payload = {
      acceptedTerms, coords: location.coords, identity, selectedPlace,
      typeId: normalizedTypeId, istatCode: location.istatCode,
      ageMs: Date.now() - Number(location.locatedAt),
      ...(correctionReport ? {
        reportId: correctionReport.reportId || correctionReport.id,
        expectedRevision: correctionReport.revision,
      } : { replacementToken }),
    };
    if (replacementReport) {
      const reportId = String(replacementReport.reportId || replacementReport.id || "").trim();
      const expectedRevision = Number(replacementReport.revision);
      if (!reportId || !Number.isInteger(expectedRevision) || expectedRevision <= 0) {
        return { ok: false, reason: "invalid_report" };
      }
      const validateFreshLocation = () => {
        const ageMs = Date.now() - Number(location.locatedAt);
        const { lat, lon, accuracyM } = location.coords;
        if (location.locatedAt == null || !Number.isFinite(ageMs) || ageMs < 0 || ageMs > LIVE_REPORT_MAX_AGE_MS
          || accuracyM == null || !Number.isFinite(Number(accuracyM)) || Number(accuracyM) <= 0 || Number(accuracyM) > 500
          || lat == null || lon == null || !Number.isFinite(Number(lat)) || !Number.isFinite(Number(lon))
          || Math.abs(Number(lat)) > 90 || Math.abs(Number(lon)) > 180) return "stale_or_imprecise";
        if (!/^\d{6}$/.test(String(location.istatCode || ""))) return "location_verification_failed";
        return "";
      };
      const invalidLocation = validateFreshLocation();
      if (invalidLocation) return { ok: false, reason: invalidLocation };
      if (activeReplacementSubmissions.has(reportId)) return activeReplacementSubmissions.get(reportId);
      const options = { storage: operationStorage };
      const operation = (async () => {
        let grant = readPilotReplacement(options);
        if (grant && grant.reportId !== reportId) {
          return { ok: false, reason: "pending_operation" };
        }
        if (!grant?.token) {
          const retired = await pilotOperation("replace", { reportId, expectedRevision }, options);
          if (!retired?.ok || !retired.replacementToken) {
            return {
              ...retired, ok: false,
              code: retired?.code || retired?.detail?.code || "community_replacement_withdrawal_incomplete",
              replacementPhase: "withdrawal",
              replacementWithdrawn: Boolean(retired?.ok),
            };
          }
          grant = { token: retired.replacementToken, reportId };
        }
        // A slow retirement may outlive the GPS freshness window. Preserve the
        // persisted grant and require fresh coordinates instead of creating.
        const staleAfterRetirement = validateFreshLocation();
        const result = staleAfterRetirement
          ? { ok: false, reason: staleAfterRetirement, code: "community_location_stale" }
          : await pilotOperation("create", {
            ...payload, ageMs: Date.now() - Number(location.locatedAt), replacementToken: grant.token,
          }, options);
        return {
          ...result,
          ...(!result?.ok ? { code: result?.code || result?.detail?.code || "community_replacement_create_incomplete" } : {}),
          replacedReportId: reportId,
          replacementPhase: "creation",
          replacementWithdrawn: true,
          replacementToken: result?.ok ? null : grant.token,
        };
      })();
      activeReplacementSubmissions.set(reportId, operation);
      try { return await operation; } finally { activeReplacementSubmissions.delete(reportId); }
    }
    return pilotOperation(correctionReport ? "correct" : "create", payload, { storage: operationStorage });
  }

  try {
    const response = await reportPoster({
      acceptedTerms,
      clientId: clientIdResolver(),
      coords: location.coords,
      ...(identity ? { identity } : {}),
      policyVersion,
      selectedPlace,
      typeId: normalizedTypeId,
      ...(isLocalCommunityPilot() ? {
        istatCode: location.istatCode,
        ageMs: Date.now() - Number(location.locatedAt),
      } : {}),
    });

    return {
      cooldownUntil: Number(response?.cooldown_until) || null,
      ok: true,
      report: response?.report || null,
      source: location.source || null,
      undoUntil: Number(response?.undo_until) || null,
    };
  } catch (error) {
    const detailCode = error?.detail && typeof error.detail === "object"
      ? String(error.detail.code || "").trim()
      : "";
    const failure = {
      error: error instanceof Error ? error.message : String(error || ""),
      ok: false,
      reason: Number(error?.status) === 429
        ? "cooldown"
        : detailCode === "community_region_not_enabled"
          ? detailCode
          : "request_failed",
    };
    if (error?.status != null && Number.isFinite(Number(error.status))) {
      failure.status = Number(error.status);
    }
    if (error?.detail != null) failure.detail = error.detail;
    if (
      error?.retryAfterSeconds != null
      && Number.isFinite(Number(error.retryAfterSeconds))
    ) {
      failure.retryAfterSeconds = Math.ceil(Number(error.retryAfterSeconds));
    }
    return failure;
  }
}

export async function undoLiveCommunityReport(
  reportId,
  {
    clientIdResolver = getOrCreateLiveReportClientId,
    reportDeleter = deleteCommunityReport,
  } = {},
) {
  const normalizedReportId = String(reportId || "").trim();
  if (!normalizedReportId) return { ok: false, reason: "missing_report" };

  try {
    const response = await reportDeleter({
      clientId: clientIdResolver(),
      reportId: normalizedReportId,
    });

    return {
      ok: true,
      reportId: response?.report_id || normalizedReportId,
    };
  } catch (error) {
    const failure = {
      error: error instanceof Error ? error.message : String(error || ""),
      ok: false,
      reason: Number(error?.status) === 429 ? "cooldown" : "request_failed",
    };
    if (error?.status != null && Number.isFinite(Number(error.status))) {
      failure.status = Number(error.status);
    }
    if (error?.detail != null) failure.detail = error.detail;
    if (
      error?.retryAfterSeconds != null
      && Number.isFinite(Number(error.retryAfterSeconds))
    ) {
      failure.retryAfterSeconds = Math.ceil(Number(error.retryAfterSeconds));
    }
    return failure;
  }
}

const activeWithdrawalPromises = new Map();

export function withdrawLiveCommunityReport(
  reportId,
  {
    clientIdResolver = getOrCreateLiveReportClientId,
    reportWithdrawer = withdrawLocalCommunityReport,
  } = {},
) {
  const normalizedReportId = String(reportId || "").trim();
  if (!normalizedReportId) return Promise.resolve({ ok: false, reason: "missing_report" });
  if (!isLocalCommunityPilot()) {
    return Promise.resolve({ ok: false, reason: "local_pilot_required" });
  }
  const pending = activeWithdrawalPromises.get(normalizedReportId);
  if (pending) return pending;

  const operation = Promise.resolve().then(async () => {
    try {
      const response = await reportWithdrawer({
        clientId: clientIdResolver(),
        reportId: normalizedReportId,
      });
      if (
        response?.ok !== true
        || response?.action !== "withdrawn"
        || String(response?.report_id || "").trim() !== normalizedReportId
      ) {
        return {
          detail: response ?? null,
          ok: false,
          reason: "invalid_response",
        };
      }
      return {
        action: response.action,
        cooldownUntil: Number(response?.cooldown_until) || null,
        ok: true,
        reportId: response.report_id,
      };
    } catch (error) {
      const status = Number(error?.status);
      if (status === 404) {
        return {
          alreadyInactive: true,
          ok: true,
          reason: "not_active",
          reportId: normalizedReportId,
          status,
        };
      }
      return {
        detail: error?.detail ?? null,
        error: error instanceof Error ? error.message : String(error || ""),
        ok: false,
        reason: status === 403 ? "not_owner" : "request_failed",
        ...(Number.isFinite(status) ? { status } : {}),
      };
    }
  });
  activeWithdrawalPromises.set(normalizedReportId, operation);
  operation.finally(() => {
    if (activeWithdrawalPromises.get(normalizedReportId) === operation) {
      activeWithdrawalPromises.delete(normalizedReportId);
    }
  });
  return operation;
}

export function updateLiveCommunityReport(
  report,
  location,
  {
    acceptedTerms = false,
    clientIdResolver = getOrCreateLiveReportClientId,
    now = Date.now,
    operationIdFactory,
    operationStorage,
    policyVersion = COMMUNITY_GUIDELINES_POLICY_VERSION,
    reportUpdater = updateLocalCommunityReport,
  } = {},
) {
  const normalizedReportId = String(
    typeof report === "string" ? report : report?.reportId || report?.id || "",
  ).trim();
  const requestedRevision = Number(
    typeof report === "object" ? report?.revision : Number.NaN,
  );
  const expectedRevision = Number.isInteger(requestedRevision) && requestedRevision > 0
    ? requestedRevision
    : 1;
  if (!normalizedReportId) return Promise.resolve({ ok: false, reason: "missing_report" });
  if (!isLocalCommunityPilot()) {
    return Promise.resolve({ ok: false, reason: "local_pilot_required" });
  }
  if (readPilotPendingOperations({ storage: operationStorage }).length) {
    return Promise.resolve({ ok: false, reason: "pending_operation" });
  }
  if (acceptedTerms !== true || policyVersion !== COMMUNITY_GUIDELINES_POLICY_VERSION) {
    return Promise.resolve({ ok: false, reason: "terms_required" });
  }
  if (!location?.coords) return Promise.resolve({ ok: false, reason: "location_required" });

  const locatedAt = Number(location.locatedAt);
  const numericNow = Number(now());
  const ageMs = numericNow - locatedAt;
  const accuracyM = Number(location.coords?.accuracyM);
  if (
    !Number.isFinite(locatedAt)
    || !Number.isFinite(ageMs)
    || ageMs < 0
    || ageMs > LIVE_REPORT_MAX_AGE_MS
    || !Number.isFinite(accuracyM)
    || accuracyM <= 0
    || accuracyM > 500
  ) {
    return Promise.resolve({ ok: false, reason: "stale_or_imprecise" });
  }

  let pendingOperation;
  try {
    pendingOperation = getOrCreateUpdateOperation(normalizedReportId, expectedRevision, {
      operationIdFactory,
      now: numericNow,
      storage: operationStorage,
    });
  } catch (error) {
    return Promise.resolve({
      error: error instanceof Error ? error.message : String(error || ""),
      ok: false,
      reason: "request_failed",
    });
  }
  const operationKey = `${normalizedReportId}:${pendingOperation.operationId}`;
  const active = activeUpdatePromises.get(operationKey);
  if (active) return active;

  const operation = Promise.resolve().then(async () => {
    try {
      const response = await reportUpdater({
        acceptedTerms,
        ageMs,
        clientId: clientIdResolver(),
        coords: location.coords,
        expectedRevision: pendingOperation.expectedRevision,
        operationId: pendingOperation.operationId,
        policyVersion,
        reportId: normalizedReportId,
      });
      const responseReportId = String(response?.report?.id || "").trim();
      const revision = Number(response?.revision ?? response?.report?.revision);
      if (
        response?.ok !== true
        || response?.action !== "updated"
        || responseReportId !== normalizedReportId
        || !Number.isInteger(revision)
        || revision <= pendingOperation.expectedRevision
      ) {
        return {
          detail: response ?? null,
          ok: false,
          operationId: pendingOperation.operationId,
          reason: "invalid_response",
        };
      }
      clearUpdateOperation(normalizedReportId, pendingOperation.operationId, operationStorage, numericNow);
      return {
        action: response.action,
        idempotentReplay: Boolean(response?.idempotent_replay),
        ok: true,
        operationId: pendingOperation.operationId,
        previousExpiresAt: Number(response?.previous_expires_at) || null,
        report: response.report,
        reportId: responseReportId,
        revision,
        updatedAt: Number(response?.updated_at) || null,
      };
    } catch (error) {
      const code = getCommunityErrorCode(error);
      const status = Number(error?.status);
      const expiredState = code === "community_observation_expired"
        ? getExpiredObservationState(error?.detail, normalizedReportId)
        : null;
      if (expiredState) {
        clearUpdateOperation(normalizedReportId, pendingOperation.operationId, operationStorage, numericNow);
        return {
          code,
          detail: error.detail,
          ok: false,
          operationId: pendingOperation.operationId,
          reason: "observation_expired",
          reportId: normalizedReportId,
          serverState: expiredState,
          ...(Number.isFinite(status) ? { status } : {}),
        };
      }
      const recentConflictState = code === "community_observation_revision_conflict"
        ? getRecentObservationState(
          error?.detail,
          normalizedReportId,
          pendingOperation.expectedRevision,
        )
        : null;
      if (recentConflictState || code === "community_idempotency_conflict") {
        clearUpdateOperation(normalizedReportId, pendingOperation.operationId, operationStorage, numericNow);
        return {
          code,
          detail: error.detail,
          ok: false,
          operationId: pendingOperation.operationId,
          reason: "observation_conflict",
          reportId: normalizedReportId,
          serverState: recentConflictState,
          ...(Number.isFinite(status) ? { status } : {}),
        };
      }
      if (TERMINAL_UPDATE_REJECTION_CODES.has(code)) {
        clearUpdateOperation(normalizedReportId, pendingOperation.operationId, operationStorage, numericNow);
        return {
          code,
          detail: error.detail,
          error: error instanceof Error ? error.message : String(error || ""),
          ok: false,
          operationId: pendingOperation.operationId,
          reason: "observation_rejected",
          reportId: normalizedReportId,
          ...(Number.isFinite(status) ? { status } : {}),
        };
      }
      if (["community_observation_location_changed", "community_gps_stale", "community_gps_imprecise", "community_minimum_interval", "community_update_limit"].includes(code)) {
        clearUpdateOperation(normalizedReportId, pendingOperation.operationId, operationStorage, numericNow);
      }
      return {
        code,
        detail: error?.detail ?? null,
        error: error instanceof Error ? error.message : String(error || ""),
        ok: false,
        operationId: pendingOperation.operationId,
        reason: code === "community_observation_location_changed" ? "location_mismatch" : "request_failed",
        reportId: normalizedReportId,
        ...(Number.isFinite(status) ? { status } : {}),
      };
    }
  });
  activeUpdatePromises.set(operationKey, operation);
  operation.then(() => {
    if (activeUpdatePromises.get(operationKey) === operation) {
      activeUpdatePromises.delete(operationKey);
    }
  });
  return operation;
}

export async function confirmLiveCommunityReport(
  groupId,
  vote,
  {
    acceptedTerms = false,
    clientIdResolver = getOrCreateLiveReportClientId,
    confirmationPoster = postCommunityReportConfirmation,
    persistentClientIdResolver = getPersistentLiveReportClientId,
    policyVersion = "",
    reportIds = [],
    locationResolver = locateLiveCommunityReport,
  } = {},
) {
  const normalizedGroupId = String(groupId || "").trim();
  const normalizedVote = String(vote || "").trim().toLowerCase();
  if (!normalizedGroupId || !["yes", "no"].includes(normalizedVote)) {
    return { ok: false, reason: "invalid_confirmation" };
  }
  if (
    acceptedTerms !== true
    || policyVersion !== COMMUNITY_GUIDELINES_POLICY_VERSION
  ) {
    return { ok: false, reason: "terms_required" };
  }

  try {
    const nationalRules = isLocalCommunityPilot();
    const clientId = nationalRules || normalizedVote === "no"
      ? persistentClientIdResolver()
      : clientIdResolver();
    if ((nationalRules || normalizedVote === "no") && !clientId) {
      return { ok: false, reason: "persistent_identity_required" };
    }

    let location;
    if (nationalRules) {
      location = await locationResolver({ requireCurrent: true });
      if (!location?.ok) return { ...location, ok: false, reason: "vote_location_required" };
      if (!reportIds.length) return { ok: false, reason: "observation_changed" };
    }
    const response = await confirmationPoster({
      acceptedTerms,
      clientId,
      groupId: normalizedGroupId,
      policyVersion,
      vote: normalizedVote,
      ...(nationalRules ? { coords: location.coords,
        ageMs: Math.max(0, Date.now() - location.locatedAt), reportIds } : {}),
    });

    return {
      confirmations: response?.confirmations || null,
      group: response?.group || null,
      ok: true,
      vote: response?.vote || normalizedVote,
    };
  } catch (error) {
    const failure = {
      error: error instanceof Error ? error.message : String(error || ""),
      ok: false,
      reason: Number(error?.status) === 429 ? "cooldown" : "request_failed",
    };
    if (error?.status != null && Number.isFinite(Number(error.status))) {
      failure.status = Number(error.status);
    }
    if (error?.detail != null) failure.detail = error.detail;
    if (
      error?.retryAfterSeconds != null
      && Number.isFinite(Number(error.retryAfterSeconds))
    ) {
      failure.retryAfterSeconds = Math.ceil(Number(error.retryAfterSeconds));
    }
    return failure;
  }
}

export const COMMUNITY_REPORT_FLAG_REASONS = Object.freeze([
  "inaccurate",
  "duplicate",
  "misuse",
]);

export async function flagLiveCommunityReport(
  groupId,
  reason,
  {
    clientIdResolver = getOrCreateLiveReportClientId,
    flagPoster = postCommunityReportFlag,
  } = {},
) {
  const normalizedGroupId = String(groupId || "").trim();
  const normalizedReason = String(reason || "").trim().toLowerCase();
  if (
    !normalizedGroupId
    || !COMMUNITY_REPORT_FLAG_REASONS.includes(normalizedReason)
  ) {
    return { ok: false, reason: "invalid_flag" };
  }

  try {
    const response = await flagPoster({
      clientId: clientIdResolver(),
      groupId: normalizedGroupId,
      reason: normalizedReason,
    });

    return {
      flagCount: Math.max(0, Number(response?.flag_count) || 0),
      groupId: response?.group_id || normalizedGroupId,
      hidden: Boolean(response?.hidden),
      ok: true,
      reason: response?.reason || normalizedReason,
    };
  } catch (error) {
    const failure = {
      error: error instanceof Error ? error.message : String(error || ""),
      ok: false,
      reason: Number(error?.status) === 429 ? "cooldown" : "request_failed",
    };
    if (error?.status != null && Number.isFinite(Number(error.status))) {
      failure.status = Number(error.status);
    }
    if (error?.detail != null) failure.detail = error.detail;
    if (
      error?.retryAfterSeconds != null
      && Number.isFinite(Number(error.retryAfterSeconds))
    ) {
      failure.retryAfterSeconds = Math.ceil(Number(error.retryAfterSeconds));
    }
    return failure;
  }
}
