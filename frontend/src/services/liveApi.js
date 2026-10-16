import { API_BASE } from "./apiConfig";
import {
  FIREBASE_APP_CHECK_HEADER,
  getFirebaseAppCheckToken,
} from "./firebaseAppCheckAdapter";
import { toPublicCommunityIdentityWire } from "../features/community/communityIdentity";
import {
  communityStorageKey,
  getLocalCommunityPilotApiBase,
  getLocalCommunityReadScope,
  isLocalCommunityPilot,
  isLocalCommunityDevelopmentRuntime,
  LOCAL_COMMUNITY_PILOT_HEADER,
} from "./localCommunityPilot";

export const LIVE_WEBCAMS_TIMEOUT_MS = 6500;
export const LIVE_COMMUNITY_TIMEOUT_MS = 5000;
export const LIVE_REPORT_TIMEOUT_MS = 12000;
export const LIVE_REPORT_CLIENT_ID_KEY = communityStorageKey("meteoFriul:communityClientId:v1");
export const LIVE_REPORT_SESSION_CLIENT_ID_KEY = communityStorageKey("meteoFriul:communitySessionClientId:v1");

const defaultClientSession = { clientId: "" };

function getErrorDetail(payload, fallback) {
  const detail = payload?.detail;

  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (typeof detail?.message === "string" && detail.message.trim()) return detail.message.trim();

  return fallback;
}

function parseRetryAfterSeconds(response, payload) {
  const detailSeconds = Number(
    payload?.detail?.retry_after_seconds ?? payload?.retry_after_seconds,
  );
  if (Number.isFinite(detailSeconds) && detailSeconds > 0) {
    return Math.ceil(detailSeconds);
  }

  const retryAfter = response?.headers?.get?.("Retry-After");
  const headerSeconds = Number(retryAfter);
  if (Number.isFinite(headerSeconds) && headerSeconds > 0) {
    return Math.ceil(headerSeconds);
  }

  return null;
}

export class LiveApiError extends Error {
  constructor(message, { detail = null, retryAfterSeconds = null, status = null } = {}) {
    super(message);
    this.name = "LiveApiError";
    this.detail = detail;
    this.retryAfterSeconds = retryAfterSeconds;
    this.status = status;
  }
}

async function fetchJson(
  path,
  {
    appCheckToken = "",
    body,
    fetchImpl = globalThis.fetch,
    method = "GET",
    signal,
    timeoutMs = LIVE_COMMUNITY_TIMEOUT_MS,
  } = {},
) {
  if (typeof fetchImpl !== "function") {
    throw new Error("Fetch non disponibile");
  }

  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  else signal?.addEventListener("abort", abort, { once: true });
  const timeoutId = globalThis.setTimeout?.(() => controller.abort(), timeoutMs);

  try {
    const headers = body === undefined ? {} : { "Content-Type": "application/json" };
    const normalizedAppCheckToken = String(appCheckToken || "").trim();
    if (normalizedAppCheckToken) {
      headers[FIREBASE_APP_CHECK_HEADER] = normalizedAppCheckToken;
    }

    const localCommunity = isLocalCommunityPilot() && path.startsWith("/community/");
    if (isLocalCommunityDevelopmentRuntime() && localCommunity) {
      headers[LOCAL_COMMUNITY_PILOT_HEADER] = "local-only";
    }
    const response = await fetchImpl(`${localCommunity ? getLocalCommunityPilotApiBase() : API_BASE}${path}`, {
      body: body === undefined ? undefined : JSON.stringify(body),
      headers: Object.keys(headers).length ? headers : undefined,
      method,
      signal: controller.signal,
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new LiveApiError(
        getErrorDetail(payload, `Endpoint live ${response.status}`),
        {
          detail: payload?.detail ?? payload,
          retryAfterSeconds: parseRetryAfterSeconds(response, payload),
          status: response.status,
        },
      );
    }

    return payload;
  } catch (error) {
    if (error?.name === "AbortError") {
      if (signal?.aborted) throw error;
      throw new Error("Endpoint live non raggiungibile entro il tempo previsto", { cause: error });
    }

    throw error;
  } finally {
    signal?.removeEventListener("abort", abort);
    if (timeoutId !== undefined) globalThis.clearTimeout?.(timeoutId);
  }
}

async function fetchMutationJson(
  path,
  {
    appCheckTokenProvider = getFirebaseAppCheckToken,
    ...options
  } = {},
) {
  const appCheckToken = isLocalCommunityDevelopmentRuntime() && path.startsWith("/community/")
    ? ""
    : await appCheckTokenProvider();

  return fetchJson(path, {
    ...options,
    appCheckToken,
  });
}

export function fetchLiveWebcams(options = {}) {
  return fetchJson("/live/webcams", {
    timeoutMs: LIVE_WEBCAMS_TIMEOUT_MS,
    ...options,
  });
}

export function fetchCommunityReports(options = {}) {
  const { communityLocation, ...requestOptions } = options;
  const scope = getLocalCommunityReadScope(communityLocation);
  if (isLocalCommunityPilot() && scope.startsWith("lat=")) {
    const params = new URLSearchParams(scope);
    return fetchJson("/community/reports/query", {
      ...requestOptions,
      method: "POST",
      body: { lat: Number(params.get("lat")), lon: Number(params.get("lon")), radius_km: 30 },
    });
  }
  return fetchJson(`/community/reports${scope ? `?${scope}` : ""}`, {
    timeoutMs: LIVE_COMMUNITY_TIMEOUT_MS,
    ...requestOptions,
  });
}

export function resolveLocalCommunityReportLocation({ coords, ageMs }, options = {}) {
  if (!isLocalCommunityPilot()) throw new Error("local_community_pilot_required");
  return fetchJson("/community/resolve", {
    ...options,
    body: { lat: coords?.lat, lon: coords?.lon, accuracy_m: coords?.accuracyM, age_ms: ageMs },
    method: "POST",
    timeoutMs: LIVE_REPORT_TIMEOUT_MS,
  });
}

export function fetchCommunityReputation(
  { clientId },
  options = {},
) {
  return fetchMutationJson("/community/reputation", {
    body: { client_id: clientId },
    method: "POST",
    timeoutMs: LIVE_COMMUNITY_TIMEOUT_MS,
    ...options,
  });
}

export function postCommunityReport(
  { acceptedTerms, clientId, coords, identity, policyVersion, selectedPlace, typeId, istatCode, ageMs, operationId, replacementToken },
  options = {},
) {
  const publicIdentity = toPublicCommunityIdentityWire(identity);

  return fetchMutationJson("/community/reports", {
    body: {
      accepted_terms: acceptedTerms,
      client_id: clientId,
      ...(publicIdentity ? { identity: publicIdentity } : {}),
      lat: coords?.lat,
      lon: coords?.lon,
      policy_version: policyVersion,
      selected_place: selectedPlace,
      type_id: typeId,
      ...(isLocalCommunityPilot() ? {
        istat_code: istatCode,
        accuracy_m: coords?.accuracyM,
        age_ms: ageMs,
        operation_id: operationId,
        ...(replacementToken ? { replacement_token: replacementToken } : {}),
      } : {}),
    },
    method: "POST",
    timeoutMs: LIVE_REPORT_TIMEOUT_MS,
    ...options,
  });
}

export function postCommunityReportConfirmation(
  { acceptedTerms, clientId, groupId, policyVersion, vote, coords, ageMs, reportIds },
  options = {},
) {
  return fetchMutationJson(`/community/reports/${encodeURIComponent(groupId)}/confirmation`, {
    body: {
      accepted_terms: acceptedTerms,
      client_id: clientId,
      policy_version: policyVersion,
      vote,
      ...(isLocalCommunityPilot() ? {
        lat: coords?.lat, lon: coords?.lon, accuracy_m: coords?.accuracyM,
        age_ms: ageMs, report_ids: reportIds || [],
      } : {}),
    },
    method: "POST",
    timeoutMs: LIVE_REPORT_TIMEOUT_MS,
    ...options,
  });
}

export function fetchCommunityHistory({ location, clientId, offset = 0, cursor = null, grouped = false }, options = {}) {
  const scope = new URLSearchParams(getLocalCommunityReadScope(location));
  if (!scope.size) return Promise.reject(new Error("Seleziona una località per lo storico."));
  return fetchMutationJson("/community/history", {
    method: "POST", timeoutMs: LIVE_COMMUNITY_TIMEOUT_MS, ...options,
    body: { client_id: clientId, offset, radius_km: 30,
      ...(grouped ? { grouped: true } : {}),
      ...(cursor ? { before_created_at: cursor.createdAt, before_id: cursor.id } : {}),
      ...(scope.has("istat_code") ? { istat_code: scope.get("istat_code") }
        : { lat: Number(scope.get("lat")), lon: Number(scope.get("lon")) }),
    },
  });
}

export function postCommunityReportFlag(
  { clientId, groupId, reason },
  options = {},
) {
  return fetchMutationJson(`/community/reports/${encodeURIComponent(groupId)}/flags`, {
    body: {
      client_id: clientId,
      reason,
    },
    method: "POST",
    timeoutMs: LIVE_REPORT_TIMEOUT_MS,
    ...options,
  });
}

export function deleteCommunityReport(
  { clientId, reportId },
  options = {},
) {
  return fetchMutationJson(`/community/reports/${encodeURIComponent(reportId)}`, {
    body: {
      client_id: clientId,
      ...(isLocalCommunityPilot() ? { action: "undo" } : {}),
    },
    method: "DELETE",
    timeoutMs: LIVE_REPORT_TIMEOUT_MS,
    ...options,
  });
}

export function withdrawLocalCommunityReport(
  { clientId, reportId, operationId, expectedRevision, action = "withdraw" },
  options = {},
) {
  if (!isLocalCommunityPilot()) {
    throw new Error("local_community_pilot_required");
  }
  return fetchMutationJson(`/community/reports/${encodeURIComponent(reportId)}`, {
    body: { action, client_id: clientId, operation_id: operationId, expected_revision: expectedRevision },
    method: "DELETE",
    timeoutMs: LIVE_REPORT_TIMEOUT_MS,
    ...options,
  });
}

export function correctLocalCommunityReport(payload, options = {}) {
  if (!isLocalCommunityPilot()) throw new Error("local_community_pilot_required");
  return fetchMutationJson(`/community/reports/${encodeURIComponent(payload.reportId)}/correction`, {
    body: {
      client_id: payload.clientId,
      operation_id: payload.operationId,
      expected_revision: payload.expectedRevision,
      accepted_terms: payload.acceptedTerms,
      policy_version: payload.policyVersion,
      type_id: payload.typeId,
      selected_place: payload.selectedPlace,
      istat_code: payload.istatCode,
      lat: payload.coords?.lat,
      lon: payload.coords?.lon,
      accuracy_m: payload.coords?.accuracyM,
      age_ms: payload.ageMs,
    },
    method: "POST",
    timeoutMs: LIVE_REPORT_TIMEOUT_MS,
    ...options,
  });
}

export function fetchLocalCommunityOperation({ clientId, operationId }, options = {}) {
  if (!isLocalCommunityPilot()) throw new Error("local_community_pilot_required");
  return fetchMutationJson(`/community/operations/${encodeURIComponent(operationId)}`, {
    body: { client_id: clientId },
    method: "POST",
    timeoutMs: LIVE_REPORT_TIMEOUT_MS,
    ...options,
  });
}

export function updateLocalCommunityReport(
  {
    acceptedTerms,
    ageMs,
    clientId,
    coords,
    expectedRevision,
    operationId,
    policyVersion,
    reportId,
  },
  options = {},
) {
  if (!isLocalCommunityPilot()) {
    throw new Error("local_community_pilot_required");
  }
  return fetchMutationJson(`/community/reports/${encodeURIComponent(reportId)}`, {
    body: {
      accepted_terms: acceptedTerms,
      accuracy_m: coords?.accuracyM,
      age_ms: ageMs,
      client_id: clientId,
      expected_revision: expectedRevision,
      lat: coords?.lat,
      lon: coords?.lon,
      operation_id: operationId,
      policy_version: policyVersion,
    },
    method: "PATCH",
    timeoutMs: LIVE_REPORT_TIMEOUT_MS,
    ...options,
  });
}

export function getOrCreateLiveReportClientId({
  cryptoLike = globalThis.crypto,
  sessionStorage,
  sessionState = defaultClientSession,
  storage,
} = {}) {
  const getSessionClientId = () => String(sessionState?.clientId || "").trim();
  const rememberClientId = (clientId) => {
    if (sessionState && typeof sessionState === "object") {
      sessionState.clientId = clientId;
    }
    return clientId;
  };
  const generateClientId = () => (
    typeof cryptoLike?.randomUUID === "function"
      ? cryptoLike.randomUUID()
      : `live-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
  );
  const remembered = getSessionClientId();
  if (remembered) return remembered;

  let resolvedStorage = storage;
  if (resolvedStorage === undefined) {
    try {
      resolvedStorage = globalThis.localStorage;
    } catch {
      resolvedStorage = null;
    }
  }
  let resolvedSessionStorage = sessionStorage;
  if (resolvedSessionStorage === undefined) {
    try {
      resolvedSessionStorage = globalThis.sessionStorage;
    } catch {
      resolvedSessionStorage = null;
    }
  }

  try {
    const stored = String(
      resolvedSessionStorage?.getItem?.(LIVE_REPORT_SESSION_CLIENT_ID_KEY) || "",
    ).trim();
    if (stored) {
      const clientId = rememberClientId(stored);
      try {
        resolvedStorage?.setItem?.(LIVE_REPORT_CLIENT_ID_KEY, clientId);
      } catch {
        // The active session identity remains authoritative.
      }
      return clientId;
    }
  } catch {
    // Fall through to persistent storage.
  }

  try {
    const stored = String(resolvedStorage?.getItem?.(LIVE_REPORT_CLIENT_ID_KEY) || "").trim();
    if (stored) {
      const clientId = rememberClientId(stored);
      try {
        resolvedSessionStorage?.setItem?.(LIVE_REPORT_SESSION_CLIENT_ID_KEY, clientId);
      } catch {
        // Module memory still keeps the persistent identity for this app instance.
      }
      return clientId;
    }
  } catch {
    // Module memory still provides stability within the running app session.
  }

  const generated = rememberClientId(generateClientId());
  try {
    resolvedStorage?.setItem?.(LIVE_REPORT_CLIENT_ID_KEY, generated);
  } catch {
    // Session storage below preserves identity when persistent storage is blocked.
  }
  try {
    resolvedSessionStorage?.setItem?.(LIVE_REPORT_SESSION_CLIENT_ID_KEY, generated);
  } catch {
    // Module memory remains the final fallback.
  }

  return generated;
}

export function readExistingLiveReportClientId({
  sessionStorage,
  sessionState = defaultClientSession,
  storage,
} = {}) {
  const remembered = String(sessionState?.clientId || "").trim();
  if (remembered) return remembered;

  let resolvedSessionStorage = sessionStorage;
  if (resolvedSessionStorage === undefined) {
    try {
      resolvedSessionStorage = globalThis.sessionStorage;
    } catch {
      resolvedSessionStorage = null;
    }
  }

  try {
    const sessionClientId = String(
      resolvedSessionStorage?.getItem?.(LIVE_REPORT_SESSION_CLIENT_ID_KEY) || "",
    ).trim();
    if (sessionClientId) return sessionClientId;
  } catch {
    // Fall through to the existing persistent identity without mutating storage.
  }

  let resolvedStorage = storage;
  if (resolvedStorage === undefined) {
    try {
      resolvedStorage = globalThis.localStorage;
    } catch {
      resolvedStorage = null;
    }
  }

  try {
    return String(
      resolvedStorage?.getItem?.(LIVE_REPORT_CLIENT_ID_KEY) || "",
    ).trim();
  } catch {
    return "";
  }
}

export function getPersistentLiveReportClientId(options = {}) {
  let resolvedStorage = options.storage;
  if (resolvedStorage === undefined) {
    try {
      resolvedStorage = globalThis.localStorage;
    } catch {
      return "";
    }
  }
  if (!resolvedStorage) return "";

  try {
    const clientId = getOrCreateLiveReportClientId({
      ...options,
      storage: resolvedStorage,
    });
    if (!clientId) return "";

    resolvedStorage.setItem?.(LIVE_REPORT_CLIENT_ID_KEY, clientId);
    return String(resolvedStorage.getItem?.(LIVE_REPORT_CLIENT_ID_KEY) || "").trim() === clientId
      ? clientId
      : "";
  } catch {
    return "";
  }
}
