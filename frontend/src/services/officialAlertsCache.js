import {
  OFFICIAL_ALERT_STATES,
  classifyOfficialAlertState,
  getOfficialAlertRecords,
} from "../domain/alerts/officialAlerts";
import { readJsonCache, removeJsonCache, writeJsonCache } from "./jsonCache";

export const REGIONAL_OFFICIAL_ALERTS_CACHE_KEY = "officialAlertsRegionalCache:v1:fvg";

const PERSISTABLE_STATES = new Set([
  OFFICIAL_ALERT_STATES.ACTIVE,
  OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
]);

function getNowValue(now) {
  return typeof now === "function" ? now() : now;
}

function getTimestamp(value) {
  if (!value) return null;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : null;
}

function getActiveExpiry(value) {
  const explicit = getTimestamp(value?.expires_at || value?.expiresAt);
  if (explicit !== null) return explicit;

  const expiries = getOfficialAlertRecords(value)
    .map((alert) => getTimestamp(
      alert?.valid_to || alert?.validTo || alert?.expires_at || alert?.expiresAt,
    ))
    .filter((timestamp) => timestamp !== null);

  return expiries.length ? Math.max(...expiries) : null;
}

function isPersistableRegionalState(value, { now = Date.now } = {}) {
  const alertState = classifyOfficialAlertState(value, { now });
  if (!PERSISTABLE_STATES.has(alertState.state)) return false;
  if (alertState.state !== OFFICIAL_ALERT_STATES.ACTIVE) return true;

  const expiry = getActiveExpiry(value);
  return expiry !== null && expiry > Number(getNowValue(now));
}

export function readRegionalOfficialAlertsCache({ storage, now = Date.now } = {}) {
  const cached = readJsonCache(
    REGIONAL_OFFICIAL_ALERTS_CACHE_KEY,
    Number.POSITIVE_INFINITY,
    { storage, now },
  );
  if (!cached) return null;

  if (isPersistableRegionalState(cached, { now })) return cached;

  removeJsonCache(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY, { storage });
  return null;
}

export function writeRegionalOfficialAlertsCache(value, { storage, now = Date.now } = {}) {
  if (!isPersistableRegionalState(value, { now })) return false;

  return writeJsonCache(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY, value, { storage, now });
}

export function resolveOfficialAlerts(nextAlerts, previousAlerts, { now = Date.now } = {}) {
  const nextState = classifyOfficialAlertState(nextAlerts, { now });

  if (
    nextState.state === OFFICIAL_ALERT_STATES.ACTIVE
    || nextState.state === OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED
  ) {
    return nextAlerts;
  }

  const previousState = classifyOfficialAlertState(previousAlerts, { now });
  if (previousState.state === OFFICIAL_ALERT_STATES.ACTIVE) return previousAlerts;

  return nextAlerts || null;
}

export function hydrateOfficialAlertsFromRegionalCache(
  locationAlerts,
  { storage, now = Date.now } = {},
) {
  const regionalAlerts = readRegionalOfficialAlertsCache({ storage, now });
  if (regionalAlerts) return regionalAlerts;

  if (writeRegionalOfficialAlertsCache(locationAlerts, { storage, now })) {
    return locationAlerts;
  }

  return locationAlerts || null;
}

export function reconcileRegionalOfficialAlerts(
  nextAlerts,
  previousLocationAlerts = null,
  { storage, now = Date.now } = {},
) {
  const regionalAlerts = readRegionalOfficialAlertsCache({ storage, now });
  const previousAlerts = regionalAlerts
    || hydrateOfficialAlertsFromRegionalCache(previousLocationAlerts, { storage, now });
  const resolved = resolveOfficialAlerts(nextAlerts, previousAlerts, { now });

  writeRegionalOfficialAlertsCache(resolved, { storage, now });
  return resolved;
}
