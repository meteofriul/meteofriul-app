import { communityStorageKey } from "../../services/localCommunityPilot";

export const REPORT_LOCATION_NOTICE_VERSION = "precise-location-notice-v1";
export const REPORT_LOCATION_NOTICE_CONSENT_KEY = communityStorageKey(
  "meteoFriul:reportLocationNoticeConsent:v1",
);

function resolveStorage(storage) {
  if (storage !== undefined) return storage;

  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}

export function hasReportLocationNoticeConsent({ storage } = {}) {
  try {
    return resolveStorage(storage)?.getItem?.(REPORT_LOCATION_NOTICE_CONSENT_KEY)
      === REPORT_LOCATION_NOTICE_VERSION;
  } catch {
    return false;
  }
}

export function rememberReportLocationNoticeConsent({ storage } = {}) {
  try {
    const resolvedStorage = resolveStorage(storage);
    if (typeof resolvedStorage?.setItem !== "function") return false;
    resolvedStorage.setItem(
      REPORT_LOCATION_NOTICE_CONSENT_KEY,
      REPORT_LOCATION_NOTICE_VERSION,
    );
    return true;
  } catch {
    return false;
  }
}
