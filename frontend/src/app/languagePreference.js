export const LANGUAGE_STORAGE_KEY = "mfLanguage";

const VALID_LANGUAGE_VALUES = new Set(["it", "fur"]);

function getBrowserStorage() {
  return globalThis.window?.localStorage;
}

export function normalizeLanguagePreference(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return VALID_LANGUAGE_VALUES.has(normalized) ? normalized : null;
}

export function readUiLanguagePreference(storage = getBrowserStorage()) {
  try {
    return normalizeLanguagePreference(storage?.getItem(LANGUAGE_STORAGE_KEY)) || "it";
  } catch {
    return "it";
  }
}

export function writeUiLanguagePreference(language, storage = getBrowserStorage()) {
  const normalized = normalizeLanguagePreference(language) || "it";

  try {
    storage?.setItem(LANGUAGE_STORAGE_KEY, normalized);
  } catch {
    // UI state still updates even if storage is unavailable.
  }

  return normalized;
}

export function syncDocumentLanguage(
  language,
  documentElement = globalThis.document?.documentElement,
) {
  const normalized = normalizeLanguagePreference(language) || "it";

  documentElement?.setAttribute?.("lang", normalized);
  return normalized;
}
