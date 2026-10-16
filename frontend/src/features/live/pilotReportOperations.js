import {
  correctLocalCommunityReport,
  fetchLocalCommunityOperation,
  getPersistentLiveReportClientId,
  postCommunityReport,
  withdrawLocalCommunityReport,
} from "../../services/liveApi";
import { communityStorageKey, isLocalCommunityPilot } from "../../services/localCommunityPilot";
import {
  readCommunityPersonalState,
  expireCommunityReport,
  refreshCommunityReportReceipt,
  rememberCommunityReport,
  withdrawCommunityReport,
} from "./communityPersonalState";
import { COMMUNITY_GUIDELINES_POLICY_VERSION } from "./liveReportPolicy";
import { readPendingLiveCommunityReportUpdates } from "./liveReportController";

const STORAGE_NAME = "meteoFriul:communityPilotOperations:v2";
const inFlight = new Map();

function storageOrDefault(storage) {
  if (storage !== undefined) return storage;
  try { return globalThis.localStorage; } catch { return null; }
}

function readState(storage) {
  try {
    const raw = JSON.parse(storage?.getItem(communityStorageKey(STORAGE_NAME)) || "null");
    return { pending: Array.isArray(raw?.pending) ? raw.pending : [], replacement: raw?.replacement || null };
  } catch { return { pending: [], replacement: null }; }
}

function writeState(state, storage) {
  if (!storage) throw new Error("persistent_identity_required");
  const text = JSON.stringify(state);
  storage.setItem(communityStorageKey(STORAGE_NAME), text);
  if (storage.getItem(communityStorageKey(STORAGE_NAME)) !== text) throw new Error("persistent_identity_required");
}

export function readPilotPendingOperations({ storage } = {}) {
  return isLocalCommunityPilot() ? readState(storageOrDefault(storage)).pending : [];
}

export function readPilotReplacement({ storage } = {}) {
  if (!isLocalCommunityPilot()) return null;
  const replacement = readState(storageOrDefault(storage)).replacement;
  return Number(replacement?.expiresAt) > 0 && Number(replacement.expiresAt) <= Date.now() ? null : replacement;
}

export function getPilotMutationFeedback(result) {
  if (result?.retired) return "La vecchia azione non è stata applicata. Ora puoi inviare una nuova osservazione con Segnala.";
  if (result?.replacementPhase === "withdrawal" && result?.uncertain) {
    return "La risposta al ritiro non è arrivata. Verifica l’esito prima di continuare: nessun nuovo invio è stato avviato.";
  }
  if (result?.replacementWithdrawn && !result?.ok) {
    if (result.uncertain) return "La precedente segnalazione è stata ritirata. L’esito del nuovo invio è da verificare: potrebbe essere già riuscito. Riprova per recuperarlo senza duplicarlo.";
    const explanation = getPilotMutationFeedback({ ...result, replacementWithdrawn: false, replacementPhase: "" });
    return `La precedente segnalazione è stata ritirata. Il nuovo invio non è stato completato. ${explanation}`;
  }
  const code = String(result?.code || result?.detail?.code || result?.reason || "");
  const seconds = Math.ceil(Number(result?.retryAfterSeconds || result?.detail?.retry_after_seconds) || 0);
  const wait = seconds > 0 ? ` Puoi riprovare tra ${seconds < 60 ? `${seconds} s` : `${Math.ceil(seconds / 60)} min`}.` : "";
  if (/quota.*(hour|60)|hour.*(quota|limit)/.test(code)) return `Hai raggiunto il limite di 4 osservazioni negli ultimi 60 minuti.${wait}`;
  if (/quota.*(day|24)|daily.*(quota|limit)/.test(code)) return `Hai raggiunto il limite di 12 osservazioni nelle ultime 24 ore.${wait}`;
  if (/already_recent|duplicate/.test(code)) return "Hai già segnalato questo fenomeno in questo Comune. Puoi aggiornare l’osservazione esistente.";
  if (/interval|cooldown/.test(code)) return `Attendi almeno 3 minuti tra due nuove osservazioni.${wait}`;
  if (/correction.*(expired|window)/.test(code)) return "Sono trascorsi i 5 minuti disponibili per correggere questa osservazione.";
  if (/location|municipality|gps/.test(code)) return "Verifica il GPS: la posizione deve essere compatibile con il Comune dell’osservazione.";
  if (/replacement/.test(code)) return "La sostituzione senza attesa non è disponibile. Restano validi i normali limiti di invio.";
  if (/observation_expired/.test(code)) return "Questa osservazione è scaduta. Per descrivere la situazione attuale, invia una nuova osservazione.";
  if (/group_hidden|not_active|not_updateable|not_correctable|not_replaceable/.test(code)) return "Questa osservazione non è più modificabile. Le smentite e le protezioni restano valide.";
  if (/revision_conflict/.test(code)) return "L’osservazione è cambiata. Chiudi e riapri la scheda prima di riprovare.";
  if (code === "persistent_identity_required") return "Per inviare in sicurezza occorre poter salvare l’identità e l’operazione su questo dispositivo.";
  if (code === "pending_operation") return "Un’operazione precedente è ancora da verificare. Recupera il suo esito prima di procedere.";
  if (result?.uncertain) return "La risposta non è arrivata. Verifica l’esito: l’operazione potrebbe essere già riuscita.";
  return result?.detail?.message || "Operazione non riuscita. Riprova dopo aver verificato la connessione.";
}

function acceptedResult(operation, response, storage) {
  if (response?.ok === true && response.reconciled_only === true && response.operation_id === operation.operationId) {
    const state = readState(storage);
    state.pending = state.pending.filter((item) => item.operationId !== operation.operationId);
    writeState(state, storage);
    return { ok: true, reconciledOnly: true, expired: true, operationId: operation.operationId, reportId: response.report_id };
  }
  const validAction = { create: undefined, correct: "corrected", withdraw: "withdrawn", replace: "replacement_ready" }[operation.kind];
  if (response?.ok !== true || (validAction && response.action !== validAction)
    || (["create", "correct"].includes(operation.kind) && !response.report?.id)
    || (operation.kind === "correct" && (response.report.id !== operation.reportId || Number(response.report.revision) <= operation.expectedRevision))
    || (["withdraw", "replace"].includes(operation.kind) && response.report_id !== operation.reportId)
    || (operation.kind === "replace" && !response.replacement_token)) {
    return { ok: false, reason: "invalid_response", uncertain: true };
  }
  const report = response.report ? {
    ...response.report,
    correctionUntil: response.correction_until ?? response.report.correctionUntil,
    replacementAvailable: response.replacement_available ?? response.report.replacementAvailable,
  } : null;
  let personal = readCommunityPersonalState({ storage });
  // Only retire local receipts after the server accepted the atomic replacement.
  for (const replacedId of response.replaced_report_ids || []) {
    personal = withdrawCommunityReport(personal, replacedId, { storage });
  }
  if (report && Number(report.expiresAt || report.expires_at) <= Date.now()) expireCommunityReport(personal, report.id, { storage });
  else if (operation.kind === "create") rememberCommunityReport(personal, report, { storage });
  else if (operation.kind === "correct") refreshCommunityReportReceipt(personal, report, { storage });
  else withdrawCommunityReport(personal, operation.reportId, { storage });
  const state = readState(storage);
  state.pending = state.pending.filter((item) => item.operationId !== operation.operationId);
  if (operation.kind === "replace") state.replacement = {
    token: response.replacement_token,
    reportId: operation.reportId,
    expiresAt: response.replacement_expires_at || null,
  };
  if (operation.kind === "create" && operation.replacementToken === state.replacement?.token) state.replacement = null;
  writeState(state, storage);
  return {
    ok: true, action: response.action || "created", report,
    reportId: report?.id || operation.reportId, revision: response.revision || report?.revision,
    replacementToken: response.replacement_token || null,
    operationId: operation.operationId, idempotentReplay: Boolean(response.idempotent_replay),
    cooldownUntil: response.cooldown_until,
    replacedReportIds: response.replaced_report_ids || [],
    expired: Boolean(report && Number(report.expiresAt || report.expires_at) <= Date.now()),
  };
}

export async function reconcilePilotReportOperation(operation, {
  storage, resolver = fetchLocalCommunityOperation,
  clientIdResolver = getPersistentLiveReportClientId,
} = {}) {
  if (!isLocalCommunityPilot()) return { ok: false, reason: "local_pilot_required" };
  const resolvedStorage = storageOrDefault(storage);
  try {
    const clientId = clientIdResolver({ storage: resolvedStorage });
    if (!clientId) return { ok: false, reason: "persistent_identity_required" };
    const result = await resolver({ clientId, operationId: operation.operationId });
    if (result?.status === "accepted") return acceptedResult(operation, result.result, resolvedStorage);
    if (result?.status === "not_found" && result.rules_version === "community-reports-v3"
      && operation.kind !== "create") {
      // Only the new server can retire an unapplied legacy intent. Never drop
      // an uncertain creation, a receipt, or an operation on a network error.
      const state = readState(resolvedStorage);
      state.pending = state.pending.filter((item) => item.operationId !== operation.operationId);
      writeState(state, resolvedStorage);
      return { ok: false, retired: true, reason: "new_observation_required" };
    }
    // A request may still be in flight. Keep its ID even when not found yet.
    return { ok: false, reason: "pending_operation", uncertain: true, notFound: result?.status === "not_found" };
  } catch { return { ok: false, reason: "request_failed", uncertain: true }; }
}

export async function performPilotReportOperation(kind, payload, {
  storage,
  clientIdResolver = getPersistentLiveReportClientId,
  resolver = fetchLocalCommunityOperation,
  sender = kind === "create" ? postCommunityReport : kind === "correct" ? correctLocalCommunityReport : withdrawLocalCommunityReport,
  operationIdFactory = () => globalThis.crypto.randomUUID(),
} = {}) {
  if (!isLocalCommunityPilot()) return { ok: false, reason: "local_pilot_required" };
  const resolvedStorage = storageOrDefault(storage);
  let operation;
  try {
    if (readPendingLiveCommunityReportUpdates({ operationStorage: resolvedStorage }).length) {
      return { ok: false, reason: "pending_operation" };
    }
    const clientId = clientIdResolver({ storage: resolvedStorage });
    if (!clientId) return { ok: false, reason: "persistent_identity_required" };
    const state = readState(resolvedStorage);
    // Persist only intent and IDs; precise GPS is never stored by this journal.
    const intent = {
      kind, reportId: payload.reportId || "", expectedRevision: payload.expectedRevision || null,
      typeId: payload.typeId || "", istatCode: payload.istatCode || "",
      selectedPlace: payload.selectedPlace || "", replacementToken: payload.replacementToken || "",
    };
    operation = state.pending[0];
    if (operation) {
      const recovered = await reconcilePilotReportOperation(operation, { storage: resolvedStorage, resolver, clientIdResolver });
      const sameIntent = ["kind", "reportId", "typeId", "replacementToken"].every((key) => operation.intent[key] === intent[key]);
      if (recovered.ok) return sameIntent ? recovered : { ok: false, reason: "pending_operation", reconciled: true };
      if (!sameIntent || !recovered.notFound) return recovered;
    } else {
      operation = { ...intent, intent, operationId: operationIdFactory(), createdAt: Date.now() };
      state.pending.push(operation);
      writeState(state, resolvedStorage);
    }
    if (inFlight.has(operation.operationId)) return inFlight.get(operation.operationId);
    const promise = (async () => {
      try {
        const response = await sender({
          ...payload, clientId, operationId: operation.operationId,
          // Retry exactly the persisted intent. Fresh GPS in another Comune
          // must be rejected by the server, never silently retarget this ID.
          expectedRevision: operation.expectedRevision || undefined,
          ...(operation.istatCode ? { istatCode: operation.istatCode, selectedPlace: operation.selectedPlace } : {}),
          action: kind === "replace" ? "replace" : "withdraw",
          policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
        });
        return acceptedResult(operation, response, resolvedStorage);
      } catch (error) {
        const status = Number(error?.status);
        const uncertain = !Number.isFinite(status) || status >= 500 || status === 408;
        if (!uncertain) {
          const current = readState(resolvedStorage);
          current.pending = current.pending.filter((item) => item.operationId !== operation.operationId);
          if (/replacement/.test(String(error?.detail?.code || "")) && payload.replacementToken === current.replacement?.token) current.replacement = null;
          writeState(current, resolvedStorage);
        }
        return {
          ok: false, uncertain, reason: uncertain ? "request_failed" : "rejected",
          code: error?.detail?.code, detail: error?.detail, status,
          retryAfterSeconds: error?.retryAfterSeconds,
        };
      }
    })();
    inFlight.set(operation.operationId, promise);
    try { return await promise; } finally { inFlight.delete(operation.operationId); }
  } catch {
    return { ok: false, reason: "persistent_identity_required", uncertain: Boolean(operation) };
  }
}
