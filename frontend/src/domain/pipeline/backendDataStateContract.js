import {
  OFFICIAL_ALERT_STATES,
  classifyOfficialAlertState,
} from "../alerts/officialAlerts";
import {
  transitionOfficialAlertState,
} from "../alerts/officialAlertTransition";
import {
  OSMER_BULLETIN_TRANSITION_STATES,
  transitionOsmerBulletinState,
} from "../weather/osmerBulletinTransition";
import {
  classifyOsmerStructuredSnapshot,
} from "../weather/osmerStructuredContract";

export const BACKEND_DATA_STATE_SCHEMA_VERSION = "1.0";

function getNowIso(now) {
  const value = typeof now === "function" ? now() : now;
  if (value instanceof Date) return value.toISOString();
  if (value) {
    const date = new Date(value);
    if (Number.isFinite(date.getTime())) return date.toISOString();
  }

  return new Date().toISOString();
}

function normalizeToken(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function normalizeConfidence(value) {
  const token = normalizeToken(value);
  if (["alta", "high"].includes(token)) return "high";
  if (["media", "medium", "medium_low"].includes(token)) return "medium";
  if (["bassa", "low"].includes(token)) return "low";
  return value || "";
}

function getSnapshotSourceKind(snapshot = {}, fallback = "") {
  return snapshot.source_kind || snapshot.fonte || snapshot.sourceKind || fallback || "unavailable";
}

function getSnapshotObservedAt(snapshot = {}, context = {}) {
  return (
    snapshot.updated_at ||
    snapshot.updatedAt ||
    snapshot.published_at ||
    snapshot.publishedAt ||
    snapshot.checked_at ||
    snapshot.checkedAt ||
    getNowIso(context.now)
  );
}

function getAlertFetchStatus(classifiedAlert, rawObservation = {}) {
  if (classifiedAlert.state === OFFICIAL_ALERT_STATES.UNAVAILABLE) {
    return classifiedAlert.error ? "unavailable" : "skipped";
  }
  if (rawObservation.fetch_status || rawObservation.fetchStatus) {
    return rawObservation.fetch_status || rawObservation.fetchStatus;
  }
  return "success";
}

function getAlertParserStatus(classifiedAlert) {
  if (classifiedAlert.state === OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED) return "empty_confirmed";
  if (classifiedAlert.state === OFFICIAL_ALERT_STATES.DIAGNOSTIC) return "diagnostic";
  if (classifiedAlert.state === OFFICIAL_ALERT_STATES.UNAVAILABLE) return "not_run";
  return "success";
}

export function buildOfficialAlertObservationDocument(rawObservation = {}, context = {}) {
  const classified = classifyOfficialAlertState(rawObservation, {
    now: context.now ?? context.observedAt,
  });
  const observedAt = context.observedAt || classified.fetchedAt || getNowIso(context.now);

  return {
    active: Boolean(rawObservation?.active),
    alerts: classified.alerts,
    count: classified.count,
    error: classified.error,
    expires_at: classified.expiresAt,
    fetch_status: getAlertFetchStatus(classified, rawObservation),
    observation_id: context.observationId || `official-alerts-${observedAt}`,
    observed_at: observedAt,
    parser_status: getAlertParserStatus(classified),
    raw_ref: context.rawRef || "",
    schema_version: BACKEND_DATA_STATE_SCHEMA_VERSION,
    source_authority: classified.sourceAuthority,
    source_mode: classified.sourceMode,
    source_url: rawObservation?.source?.url || rawObservation?.source_url || "",
    warning: classified.warning,
  };
}

export function buildOfficialAlertStateDocument(previousState = null, rawObservation = {}, context = {}) {
  const transition = transitionOfficialAlertState(previousState, rawObservation, context);
  const finalState = transition.finalState;

  return {
    active: Boolean(finalState.active),
    alert_signature: finalState.alertSignature || "",
    alerts: finalState.alerts || [],
    can_clear_previous_alert: Boolean(finalState.canClearPreviousAlert),
    can_notify: Boolean(finalState.canNotify),
    can_show_bulletin_notice: Boolean(finalState.canShowBulletinNotice),
    can_show_home_banner: Boolean(finalState.canShowHomeBanner),
    confidence: normalizeConfidence(finalState.confidence),
    count: finalState.count || 0,
    error: finalState.error || "",
    expires_at: finalState.expiresAt || finalState.expires_at || "",
    fetched_at: finalState.fetchedAt || finalState.fetched_at || context.fetchedAt || getNowIso(context.now),
    freshness: finalState.freshness || "",
    previous_state: previousState?.state || "",
    schema_version: BACKEND_DATA_STATE_SCHEMA_VERSION,
    source_authority: finalState.sourceAuthority || finalState.source_authority || "",
    source_mode: finalState.sourceMode || finalState.source_mode || "",
    state: finalState.state,
    state_id: context.stateId || "official-alert-state-current",
    transition_actions: transition.actions,
    warning: finalState.warning || "",
  };
}

export function buildOfficialAlertTransitionDocument(previousState = null, rawObservation = {}, context = {}) {
  const stateDocument = buildOfficialAlertStateDocument(previousState, rawObservation, context);
  const computedAt = context.computedAt || getNowIso(context.now);

  return {
    actions: stateDocument.transition_actions,
    alert_signature_after: stateDocument.alert_signature,
    alert_signature_before: previousState?.alert_signature || previousState?.alertSignature || "",
    computed_at: computedAt,
    dry_run: context.dryRun !== false,
    from_state: previousState?.state || "",
    observation_id: context.observationId || "",
    previous_state_id: context.previousStateId || "official-alert-state-current",
    reason: context.reason || stateDocument.state,
    schema_version: BACKEND_DATA_STATE_SCHEMA_VERSION,
    to_state: stateDocument.state,
    transition_id: context.transitionId || `official-alert-transition-${computedAt}`,
  };
}

export function buildOsmerBulletinObservationDocument(rawObservation = {}, context = {}) {
  const snapshot = rawObservation?.snapshot || rawObservation || {};
  const contract = classifyOsmerStructuredSnapshot(snapshot);
  const observedAt = context.observedAt || getSnapshotObservedAt(snapshot, context);

  return {
    days: snapshot.days || [],
    error: snapshot.error || "",
    id_emissione: snapshot.id_emissione || "",
    language: context.language || snapshot.language || "it",
    observation_id: context.observationId || `osmer-structured-${observedAt}`,
    observed_at: observedAt,
    quality: snapshot.quality || {},
    raw_ref: context.rawRef || "",
    requested_date: snapshot.requested_date || context.requestedDate || "",
    schema_version: BACKEND_DATA_STATE_SCHEMA_VERSION,
    source_date: snapshot.source_date || "",
    source_kind: getSnapshotSourceKind(snapshot, contract.sourceKind),
    source_status: snapshot.source_status || contract.sourceStatus || "",
    source_url: snapshot.source_url || "",
  };
}

function getOsmerWarnings(finalState = {}) {
  const warnings = [];
  if (finalState.status === OSMER_BULLETIN_TRANSITION_STATES.STALE_FROM_CACHE) {
    warnings.push("osmer_lookback_snapshot_used");
  }
  if (finalState.status === OSMER_BULLETIN_TRANSITION_STATES.PARTIAL_HEALED) {
    warnings.push("osmer_source_mix_healed");
  }
  if (finalState.status === OSMER_BULLETIN_TRANSITION_STATES.UNAVAILABLE) {
    warnings.push("osmer_source_unavailable");
  }
  return warnings;
}

export function buildOsmerBulletinStateDocument(previousState = null, rawObservation = {}, context = {}) {
  const transition = transitionOsmerBulletinState(previousState, rawObservation, context);
  const finalState = transition.finalState;
  const snapshot = finalState.snapshot || {};
  const validDates = (snapshot.days || []).map((day) => day.valid_date).filter(Boolean);

  return {
    can_render_native_map: Boolean(finalState.canRenderNativeMap),
    can_use_as_current: Boolean(finalState.canUseAsCurrent),
    confidence: normalizeConfidence(finalState.confidence || finalState.contract?.confidence),
    days: snapshot.days || [],
    fetched_at: getSnapshotObservedAt(snapshot, context),
    healed_manifest: finalState.healedAreasByDate || snapshot.quality?.healed_missing_areas_by_date || {},
    requested_date: snapshot.requested_date || context.requestedDate || "",
    schema_version: BACKEND_DATA_STATE_SCHEMA_VERSION,
    source_date: snapshot.source_date || "",
    source_kind: finalState.sourceKind || finalState.contract?.sourceKind || getSnapshotSourceKind(snapshot),
    source_mix: Boolean(finalState.sourceKind === "mixed" || snapshot.source_mix || snapshot.quality?.source_mix),
    source_status: snapshot.source_status || finalState.contract?.sourceStatus || "",
    state: finalState.status,
    state_id: context.stateId || "osmer-bulletin-state-current",
    transition_actions: transition.actions,
    valid_dates: validDates,
    warnings: getOsmerWarnings(finalState),
  };
}

export function buildOsmerBulletinTransitionDocument(previousState = null, rawObservation = {}, context = {}) {
  const stateDocument = buildOsmerBulletinStateDocument(previousState, rawObservation, context);
  const computedAt = context.computedAt || getNowIso(context.now);

  return {
    actions: stateDocument.transition_actions,
    computed_at: computedAt,
    from_state: previousState?.state || previousState?.status || "",
    healed_manifest: stateDocument.healed_manifest,
    observation_id: context.observationId || "",
    previous_state_id: context.previousStateId || "osmer-bulletin-state-current",
    reason: context.reason || stateDocument.state,
    schema_version: BACKEND_DATA_STATE_SCHEMA_VERSION,
    source_mix: stateDocument.source_mix,
    to_state: stateDocument.state,
    transition_id: context.transitionId || `osmer-bulletin-transition-${computedAt}`,
  };
}
