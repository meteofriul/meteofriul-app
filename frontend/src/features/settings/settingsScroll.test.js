import { describe, expect, it, vi } from "vitest";

import { resetAppMainScroll } from "./settingsScroll";

describe("settings scroll", () => {
  it("resets the app scroll container before an internal settings page opens", () => {
    const appMain = { scrollTop: 640 };
    const documentRef = {
      querySelector: vi.fn().mockReturnValue(appMain),
    };

    expect(resetAppMainScroll(documentRef)).toBe(true);
    expect(documentRef.querySelector).toHaveBeenCalledWith(".mf-app-main");
    expect(appMain.scrollTop).toBe(0);
  });
});
