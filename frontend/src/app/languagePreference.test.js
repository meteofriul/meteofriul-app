import { describe, expect, it, vi } from "vitest";

import {
  LANGUAGE_STORAGE_KEY,
  normalizeLanguagePreference,
  readUiLanguagePreference,
  syncDocumentLanguage,
  writeUiLanguagePreference,
} from "./languagePreference";

describe("UI language preference", () => {
  it("normalizes supported language values", () => {
    expect(normalizeLanguagePreference("it")).toBe("it");
    expect(normalizeLanguagePreference("FUR")).toBe("fur");
    expect(normalizeLanguagePreference("de")).toBeNull();
  });

  it("reads stored language preference", () => {
    const storage = new Map([[LANGUAGE_STORAGE_KEY, "fur"]]);

    expect(readUiLanguagePreference({ getItem: (key) => storage.get(key) })).toBe("fur");
  });

  it("keeps Italian as the default language", () => {
    expect(readUiLanguagePreference({ getItem: () => null })).toBe("it");
    expect(readUiLanguagePreference({ getItem: () => "unknown" })).toBe("it");
  });

  it("writes normalized language preference", () => {
    const storage = { setItem: vi.fn() };

    expect(writeUiLanguagePreference("FUR", storage)).toBe("fur");
    expect(storage.setItem).toHaveBeenCalledWith(LANGUAGE_STORAGE_KEY, "fur");
  });

  it("still returns a normalized value when storage is unavailable", () => {
    const storage = {
      setItem: () => {
        throw new Error("blocked");
      },
    };

    expect(writeUiLanguagePreference("fur", storage)).toBe("fur");
  });

  it("keeps the document language aligned with the visible UI", () => {
    const documentElement = { setAttribute: vi.fn() };

    expect(syncDocumentLanguage("FUR", documentElement)).toBe("fur");
    expect(documentElement.setAttribute).toHaveBeenCalledWith("lang", "fur");
  });
});
