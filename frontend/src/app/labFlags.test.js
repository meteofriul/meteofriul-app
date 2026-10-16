import { describe, expect, it } from "vitest";

import { readBooleanFlag, readUiV3LabFlag, UI_V3_STORAGE_KEY } from "./labFlags";

describe("UI 3 lab flags", () => {
  it("parses explicit boolean-like values", () => {
    expect(readBooleanFlag("1")).toBe(true);
    expect(readBooleanFlag("true")).toBe(true);
    expect(readBooleanFlag("0")).toBe(false);
    expect(readBooleanFlag("off")).toBe(false);
    expect(readBooleanFlag("maybe")).toBeNull();
  });

  it("lets the query string override storage", () => {
    const storage = new Map([[UI_V3_STORAGE_KEY, "0"]]);

    expect(readUiV3LabFlag("?uiV3=1", { getItem: (key) => storage.get(key) })).toBe(true);
  });

  it("keeps lab UI disabled by default", () => {
    expect(readUiV3LabFlag("", { getItem: () => null })).toBe(false);
  });

  it("lets storage explicitly enable the lab UI", () => {
    const storage = new Map([[UI_V3_STORAGE_KEY, "true"]]);

    expect(readUiV3LabFlag("", { getItem: (key) => storage.get(key) })).toBe(true);
  });
});
