import {
  getLocationLocality,
  getLocationMunicipality,
  getLocationMunicipalityName,
  getLocationPrimaryName,
} from "./locationIdentity";

export const AUTO_LOCATION_FOREGROUND_RECHECK_MS = 30 * 60 * 1000;
export const FAST_LOCATION_MAX_AGE_MS = 2 * 60 * 1000;
export const FAST_LOCATION_MAX_ACCURACY_M = 250;
export const CONFIRM_LOCATION_MAX_AGE_MS = FAST_LOCATION_MAX_AGE_MS;
export const CONFIRM_LOCATION_MAX_ACCURACY_M = FAST_LOCATION_MAX_ACCURACY_M;

export function normalizeLocationSource(source) {
  return String(source || "").trim().toLowerCase();
}

export function isManualDefaultLocationRecord(record, { autoLocationEnabled = false } = {}) {
  if (!record?.city) return false;

  const source = normalizeLocationSource(record.source);

  if (!source) {
    return !autoLocationEnabled;
  }

  return source === "manual";
}

export function shouldKeepAutoLocationEnabledAfterFailure(reason) {
  const normalizedReason = normalizeLocationSource(reason);

  return normalizedReason !== "denied" &&
    normalizedReason !== "permission_denied" &&
    normalizedReason !== "unsupported";
}

export function shouldRunForegroundAutoLocationCheck({
  autoLocationEnabled,
  now,
  lastCheckedAt,
  minIntervalMs = AUTO_LOCATION_FOREGROUND_RECHECK_MS,
}) {
  if (!autoLocationEnabled) return false;
  if (!Number.isFinite(now)) return false;
  if (!Number.isFinite(lastCheckedAt) || lastCheckedAt <= 0) return true;

  return now - lastCheckedAt >= minIntervalMs;
}

function coerceFiniteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function getGpsLocationQualityDecision(payload) {
  if (!payload?.ok) {
    return { usable: false, confidence: "none", reason: payload?.reason || "unavailable" };
  }

  const lat = coerceFiniteNumber(payload.lat);
  const lon = coerceFiniteNumber(payload.lon);
  const ageMs = coerceFiniteNumber(payload.age_ms ?? payload.ageMs);
  const accuracyM = coerceFiniteNumber(payload.accuracy_m ?? payload.accuracyM);

  if (lat == null || lon == null || ageMs == null || ageMs < 0 || accuracyM == null) {
    return { usable: false, confidence: "none", reason: "missing_quality" };
  }

  if (ageMs <= FAST_LOCATION_MAX_AGE_MS && accuracyM <= FAST_LOCATION_MAX_ACCURACY_M) {
    return { usable: true, confidence: "fast", lat, lon, ageMs, accuracyM };
  }

  if (ageMs <= CONFIRM_LOCATION_MAX_AGE_MS && accuracyM <= CONFIRM_LOCATION_MAX_ACCURACY_M) {
    return { usable: true, confidence: "confirm", lat, lon, ageMs, accuracyM };
  }

  return { usable: false, confidence: "none", reason: "stale_or_imprecise" };
}

function normalizeLocationText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

export function isSameResolvedPlace(first, second) {
  const firstLocality = getLocationLocality(first);
  const secondLocality = getLocationLocality(second);
  const firstLocalityId = normalizeLocationText(firstLocality?.id);
  const secondLocalityId = normalizeLocationText(secondLocality?.id);

  if (Boolean(firstLocalityId) !== Boolean(secondLocalityId)) {
    return false;
  }
  if (firstLocalityId && secondLocalityId && firstLocalityId !== secondLocalityId) {
    return false;
  }

  const firstCity = normalizeLocationText(getLocationPrimaryName(first));
  const secondCity = normalizeLocationText(getLocationPrimaryName(second));

  if (!firstCity || !secondCity || firstCity !== secondCity) {
    return false;
  }

  const firstMunicipality = getLocationMunicipality(first);
  const secondMunicipality = getLocationMunicipality(second);
  const firstIstat = normalizeLocationText(firstMunicipality?.istatCode);
  const secondIstat = normalizeLocationText(secondMunicipality?.istatCode);

  if (firstIstat && secondIstat && firstIstat !== secondIstat) return false;

  const firstMunicipalityName = normalizeLocationText(getLocationMunicipalityName(first));
  const secondMunicipalityName = normalizeLocationText(getLocationMunicipalityName(second));

  if (
    firstMunicipalityName
    && secondMunicipalityName
    && firstMunicipalityName !== secondMunicipalityName
  ) return false;

  const firstRegion = normalizeLocationText(first?.region);
  const secondRegion = normalizeLocationText(second?.region);

  return !firstRegion || !secondRegion || firstRegion === secondRegion;
}

export function shouldReplaceResolvedPlace(current, resolved) {
  if (!isSameResolvedPlace(current, resolved)) return true;

  return ["manual", "placeholder"].includes(normalizeLocationSource(current?.source));
}
