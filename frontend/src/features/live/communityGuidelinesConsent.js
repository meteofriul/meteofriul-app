import { communityStorageKey } from "../../services/localCommunityPilot";

export const COMMUNITY_GUIDELINES_CONSENT_KEY = communityStorageKey("meteoFriul:communityGuidelinesConsent:v1");

function resolveStorage(storage) {
  if (storage !== undefined) return storage;

  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}

function normalizeVersion(value) {
  return String(value || "").trim();
}

export function hasCommunityGuidelinesConsent(
  policyVersion,
  { storage } = {},
) {
  const expectedVersion = normalizeVersion(policyVersion);
  if (!expectedVersion) return false;

  try {
    return normalizeVersion(
      resolveStorage(storage)?.getItem?.(COMMUNITY_GUIDELINES_CONSENT_KEY),
    ) === expectedVersion;
  } catch {
    return false;
  }
}

export function rememberCommunityGuidelinesConsent(
  policyVersion,
  { storage } = {},
) {
  const normalizedVersion = normalizeVersion(policyVersion);
  if (!normalizedVersion) return false;

  try {
    resolveStorage(storage)?.setItem?.(
      COMMUNITY_GUIDELINES_CONSENT_KEY,
      normalizedVersion,
    );
    return true;
  } catch {
    return false;
  }
}

export function clearCommunityGuidelinesConsent({ storage } = {}) {
  try {
    resolveStorage(storage)?.removeItem?.(COMMUNITY_GUIDELINES_CONSENT_KEY);
  } catch {
    // The next contribution will simply request consent again.
  }
}
