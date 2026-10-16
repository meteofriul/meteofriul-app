export const BACKGROUND_LOCATION_DISCLOSURE_STORAGE_KEY =
  "meteofriul:background-location-disclosure:v1";
export const BACKGROUND_LOCATION_DISCLOSURE_CONSENT_STORAGE_KEY =
  "meteofriul:background-location-disclosure-consent:v1";

function resolveStorage(storage) {
  if (storage) return storage;
  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}

export function hasShownBackgroundLocationDisclosure({ storage } = {}) {
  try {
    return resolveStorage(storage)?.getItem(BACKGROUND_LOCATION_DISCLOSURE_STORAGE_KEY)
      === "shown";
  } catch {
    return false;
  }
}

export function markBackgroundLocationDisclosureShown({ storage } = {}) {
  try {
    const targetStorage = resolveStorage(storage);
    if (!targetStorage) return false;

    targetStorage.setItem(
      BACKGROUND_LOCATION_DISCLOSURE_STORAGE_KEY,
      "shown",
    );
    return true;
  } catch {
    // The disclosure remains safe to show again if storage is unavailable.
    return false;
  }
}

export function hasAcceptedBackgroundLocationDisclosure({ storage } = {}) {
  try {
    return resolveStorage(storage)?.getItem(
      BACKGROUND_LOCATION_DISCLOSURE_CONSENT_STORAGE_KEY,
    ) === "accepted";
  } catch {
    return false;
  }
}

export function markBackgroundLocationDisclosureAccepted({ storage } = {}) {
  try {
    const targetStorage = resolveStorage(storage);
    if (!targetStorage) return false;

    targetStorage.setItem(
      BACKGROUND_LOCATION_DISCLOSURE_CONSENT_STORAGE_KEY,
      "accepted",
    );
    return true;
  } catch {
    // Background collection remains disabled when consent cannot be persisted.
    return false;
  }
}

export function shouldOpenBackgroundLocationDisclosure({
  autoLocationEnabled,
  hasAccepted,
  isNativeAndroid,
} = {}) {
  return Boolean(
    isNativeAndroid
    && !hasAccepted
    && autoLocationEnabled
  );
}
