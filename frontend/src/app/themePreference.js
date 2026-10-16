export const THEME_QUERY_PARAM = "theme";
export const THEME_STORAGE_KEY = "mfTheme";
export const DEFAULT_THEME_PREFERENCE = "system";

const VALID_THEME_VALUES = new Set(["light", "dark", "system"]);

function getBrowserSearch() {
  return globalThis.window?.location?.search || "";
}

function getBrowserStorage() {
  return globalThis.window?.localStorage;
}

export function normalizeThemePreference(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return VALID_THEME_VALUES.has(normalized) ? normalized : null;
}

function resolveSystemTheme(systemDark) {
  return systemDark ? "dark" : "light";
}

export function resolveThemePreference(preference, systemDark = false) {
  const normalized = normalizeThemePreference(preference) || DEFAULT_THEME_PREFERENCE;
  if (normalized === "system") return resolveSystemTheme(systemDark);
  return normalized;
}

export function readUiThemePreference(
  search = getBrowserSearch(),
  storage = getBrowserStorage(),
) {
  const params = new URLSearchParams(search);
  const queryTheme = normalizeThemePreference(params.get(THEME_QUERY_PARAM));
  if (queryTheme) return queryTheme;

  try {
    const storedTheme = normalizeThemePreference(storage?.getItem(THEME_STORAGE_KEY));
    if (storedTheme) return storedTheme;
  } catch {
    return DEFAULT_THEME_PREFERENCE;
  }

  return DEFAULT_THEME_PREFERENCE;
}
