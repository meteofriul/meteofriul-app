import { describe, expect, it } from "vitest";

import {
  DEFAULT_THEME_PREFERENCE,
  normalizeThemePreference,
  readUiThemePreference,
  resolveThemePreference,
  THEME_STORAGE_KEY,
} from "./themePreference";

describe("UI theme preference", () => {
  it("normalizes supported theme values", () => {
    expect(normalizeThemePreference("dark")).toBe("dark");
    expect(normalizeThemePreference("LIGHT")).toBe("light");
    expect(normalizeThemePreference("system")).toBe("system");
    expect(normalizeThemePreference("blue")).toBeNull();
  });

  it("lets the query string override storage", () => {
    const storage = new Map([[THEME_STORAGE_KEY, "dark"]]);

    expect(readUiThemePreference("?theme=light", { getItem: (key) => storage.get(key) })).toBe("light");
  });

  it("resolves system preference from the provided media state", () => {
    expect(resolveThemePreference("system", true)).toBe("dark");
    expect(resolveThemePreference("system", false)).toBe("light");
  });

  it("keeps the system preference separate from its rendered theme", () => {
    expect(readUiThemePreference("", { getItem: () => null })).toBe(DEFAULT_THEME_PREFERENCE);
    expect(resolveThemePreference(DEFAULT_THEME_PREFERENCE, true)).toBe("dark");
    expect(resolveThemePreference(DEFAULT_THEME_PREFERENCE, false)).toBe("light");
  });

  it("preserves an explicit system preference from query or storage", () => {
    expect(readUiThemePreference("?theme=system", { getItem: () => "light" })).toBe("system");
    expect(readUiThemePreference("", { getItem: () => "system" })).toBe("system");
  });

  it("falls back to the system preference when storage is unavailable", () => {
    expect(readUiThemePreference("", {
      getItem: () => {
        throw new DOMException("blocked", "SecurityError");
      },
    })).toBe("system");
  });
});
