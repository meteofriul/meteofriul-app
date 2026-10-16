import { describe, expect, it, vi } from "vitest";

import { syncWebThemeColor, WEB_THEME_COLOR } from "./webThemeColor";

describe("web theme color", () => {
  it("follows the app theme for browser and PWA system chrome", () => {
    const setAttribute = vi.fn();
    const documentLike = {
      querySelector: vi.fn(() => ({ setAttribute })),
    };

    expect(syncWebThemeColor("dark", { documentLike })).toBe(true);
    expect(syncWebThemeColor("light", { documentLike })).toBe(true);
    expect(setAttribute).toHaveBeenNthCalledWith(1, "content", WEB_THEME_COLOR.dark);
    expect(setAttribute).toHaveBeenNthCalledWith(2, "content", WEB_THEME_COLOR.light);
    expect(documentLike.querySelector).toHaveBeenCalledWith('meta[name="theme-color"]');
  });

  it("does nothing if the page has no theme-color meta tag", () => {
    expect(syncWebThemeColor("dark", { documentLike: { querySelector: () => null } }))
      .toBe(false);
  });
});
