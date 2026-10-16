import {
  OFFICIAL_ALERT_STATES,
  classifyOfficialAlertState,
} from "./officialAlerts";

export const OFFICIAL_ALERT_TRANSITION_STATES = Object.freeze({
  ...OFFICIAL_ALERT_STATES,
  STALE_HELD_ACTIVE: "stale_held_active",
});

export const OFFICIAL_ALERT_TRANSITION_ACTIONS = Object.freeze({
  CLEAR_ALL_ALERTS_AND_BANNERS: "CLEAR_ALL_ALERTS_AND_BANNERS",
  DISABLE_NEW_NOTIFICATIONS: "DISABLE_NEW_NOTIFICATIONS",
  HIDE_BANNER_FROM_HOME: "HIDE_BANNER_FROM_HOME",
  KEEP_BULLETIN_NOTICE: "KEEP_BULLETIN_NOTICE",
  NOTIFY_NEW_OFFICIAL_ALERT: "NOTIFY_NEW_OFFICIAL_ALERT",
  LOG_DIAGNOSTIC_ALERT: "LOG_DIAGNOSTIC_ALERT",
  RESET_STATE_ENGINE: "RESET_STATE_ENGINE",
  RETAIN_DB_CRITICALITY: "RETAIN_DB_CRITICALITY",
  SUPPRESS_DUPLICATE_NOTIFICATION: "SUPPRESS_DUPLICATE_NOTIFICATION",
});

const DEFAULT_HOLD_ACTIVE_MS = 3 * 60 * 60 * 1000;

function getTimestamp(value) {
  if (!value) return null;
  const date = new Date(value);
  const time = date.getTime();
  return Number.isFinite(time) ? time : null;
}

function getNowTimestamp(now) {
  const value = typeof now === "function" ? now() : now;
  if (value === undefined || value === null) return Date.now();
  if (Number.isFinite(Number(value))) return Number(value);
  return getTimestamp(value) ?? Date.now();
}

function getPreviousObservedAt(previousState = {}) {
  return (
    previousState.fetched_at ||
    previousState.fetchedAt ||
    previousState.updated_at ||
    previousState.updatedAt ||
    previousState.lastConfirmedAt ||
    previousState.observedAt ||
    ""
  );
}

function getPreviousExpiresAt(previousState = {}) {
  const explicit = previousState.expires_at || previousState.expiresAt || "";
  if (explicit) return explicit;

  return (previousState.alerts || [])
    .map((alert) => alert?.valid_to || alert?.validTo || alert?.expires_at || alert?.expiresAt || "")
    .filter(Boolean)
    .sort()
    .at(-1) || "";
}

function normalizeSignaturePart(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function buildAlertSignatureFromAlerts(alerts = []) {
  if (!Array.isArray(alerts) || !alerts.length) return "";

  return alerts
    .map((alert = {}) => [
      alert.id,
      alert.level,
      alert.severity,
      alert.color,
      alert.valid_from || alert.validFrom,
      alert.valid_to || alert.validTo,
      alert.title,
      alert.official_text || alert.officialText,
    ].map(normalizeSignaturePart).join("|"))
    .sort()
    .join("||");
}

function getAlertSignature(state = {}) {
  return (
    state.alertSignature ||
    state.alert_signature ||
    state.notificationSignature ||
    buildAlertSignatureFromAlerts(state.actionableAlerts || state.alerts || [])
  );
}

function shouldNotifyActiveObservation(previousState = null, observation = {}) {
  if (observation.state !== OFFICIAL_ALERT_STATES.ACTIVE) return false;
  if (!isPreviousActive(previousState || {})) return true;

  const previousSignature = getAlertSignature(previousState || {});
  const nextSignature = getAlertSignature(observation);

  if (!previousSignature || !nextSignature) {
    return previousSignature !== nextSignature;
  }

  return previousSignature !== nextSignature;
}

function isPreviousActive(previousState = {}) {
  return previousState.state === OFFICIAL_ALERT_STATES.ACTIVE ||
    previousState.state === OFFICIAL_ALERT_TRANSITION_STATES.STALE_HELD_ACTIVE;
}

function isWithinHoldWindow(previousState = {}, { now, holdActiveMs = DEFAULT_HOLD_ACTIVE_MS } = {}) {
  const observedAt = getTimestamp(getPreviousObservedAt(previousState));
  if (observedAt === null) return false;

  return getNowTimestamp(now) - observedAt <= holdActiveMs;
}

function hasExpiredPreviousAlert(previousState = {}, now) {
  const expiresAt = getTimestamp(getPreviousExpiresAt(previousState));
  if (expiresAt === null) return false;

  return expiresAt < getNowTimestamp(now);
}

function buildFinalState(state, observation, overrides = {}) {
  return {
    ...observation,
    active: state === OFFICIAL_ALERT_STATES.ACTIVE,
    canClearPreviousAlert: state === OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
    canNotify: state === OFFICIAL_ALERT_STATES.ACTIVE,
    canShowBulletinNotice: state === OFFICIAL_ALERT_STATES.ACTIVE,
    canShowFreshBanner: state === OFFICIAL_ALERT_STATES.ACTIVE,
    canShowHomeBanner: state === OFFICIAL_ALERT_STATES.ACTIVE,
    freshness: observation.freshness,
    state,
    ...overrides,
  };
}

export function transitionOfficialAlertState(previousState = null, newObservation = null, context = {}) {
  const observation = classifyOfficialAlertState(newObservation, { now: context.now });
  const actions = [];

  if (observation.state === OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED) {
    return {
      actions: [
        OFFICIAL_ALERT_TRANSITION_ACTIONS.CLEAR_ALL_ALERTS_AND_BANNERS,
        OFFICIAL_ALERT_TRANSITION_ACTIONS.RESET_STATE_ENGINE,
      ],
      finalState: buildFinalState(OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED, observation),
      observation,
    };
  }

  if (
    isPreviousActive(previousState || {}) &&
    hasExpiredPreviousAlert(previousState || {}, context.now) &&
    observation.state !== OFFICIAL_ALERT_STATES.ACTIVE
  ) {
    return {
      actions: [
        OFFICIAL_ALERT_TRANSITION_ACTIONS.HIDE_BANNER_FROM_HOME,
        OFFICIAL_ALERT_TRANSITION_ACTIONS.RETAIN_DB_CRITICALITY,
      ],
      finalState: buildFinalState(OFFICIAL_ALERT_STATES.EXPIRED, observation, {
        active: false,
        canClearPreviousAlert: false,
        canNotify: false,
        canShowBulletinNotice: true,
        canShowFreshBanner: false,
        canShowHomeBanner: false,
        confidence: "low",
        freshness: "stale",
        previousState,
      }),
      observation,
    };
  }

  if (observation.state === OFFICIAL_ALERT_STATES.ACTIVE) {
    const canNotify = shouldNotifyActiveObservation(previousState, observation);

    return {
      actions: [
        canNotify
          ? OFFICIAL_ALERT_TRANSITION_ACTIONS.NOTIFY_NEW_OFFICIAL_ALERT
          : OFFICIAL_ALERT_TRANSITION_ACTIONS.SUPPRESS_DUPLICATE_NOTIFICATION,
      ],
      finalState: buildFinalState(OFFICIAL_ALERT_STATES.ACTIVE, observation, {
        alertSignature: getAlertSignature(observation),
        canNotify,
      }),
      observation,
    };
  }

  if (
    isPreviousActive(previousState || {}) &&
    observation.state === OFFICIAL_ALERT_STATES.DIAGNOSTIC &&
    isWithinHoldWindow(previousState || {}, context)
  ) {
    actions.push(
      OFFICIAL_ALERT_TRANSITION_ACTIONS.DISABLE_NEW_NOTIFICATIONS,
      OFFICIAL_ALERT_TRANSITION_ACTIONS.KEEP_BULLETIN_NOTICE,
      OFFICIAL_ALERT_TRANSITION_ACTIONS.LOG_DIAGNOSTIC_ALERT,
    );

    return {
      actions,
      finalState: buildFinalState(OFFICIAL_ALERT_TRANSITION_STATES.STALE_HELD_ACTIVE, observation, {
        active: false,
        alertSignature: getAlertSignature(previousState || {}),
        alerts: previousState?.alerts || [],
        canClearPreviousAlert: false,
        canNotify: false,
        canShowBulletinNotice: true,
        canShowFreshBanner: false,
        canShowHomeBanner: true,
        confidence: "low",
        count: previousState?.count || previousState?.alerts?.length || 0,
        freshness: "stale",
        heldPreviousState: previousState,
        previousState,
      }),
      observation,
    };
  }

  if (observation.state !== OFFICIAL_ALERT_STATES.ACTIVE) {
    actions.push(OFFICIAL_ALERT_TRANSITION_ACTIONS.DISABLE_NEW_NOTIFICATIONS);
  }

  return {
    actions,
    finalState: buildFinalState(observation.state, observation),
    observation,
  };
}
