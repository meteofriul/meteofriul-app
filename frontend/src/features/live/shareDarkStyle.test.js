import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");

function declarations(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`^${escaped}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";
}

describe("report header share action", () => {
  it("aligns share and close as matching unboxed actions", () => {
    const actions = declarations(".mf-territory-map__report-heading-actions");
    const close = declarations(".mf-territory-map__report-close.mf-icon-button");

    expect(actions).toContain("align-items: center");
    expect(actions).toContain("gap: 12px");
    expect(close).toContain("width: 40px");
    expect(close).toContain("height: 40px");
    expect(close).toContain("border: 0");
    expect(close).toContain("background: transparent");
  });

  it("uses a compact unboxed secondary action in the report heading", () => {
    const rule = declarations(".mf-territory-map__report-share.mf-icon-button");

    expect(rule).toContain("width: 40px");
    expect(rule).toContain("height: 40px");
    expect(rule).toContain("border: 0");
    expect(rule).toContain("background: transparent");
    expect(rule).toContain("color: #52697b");
  });

  it("preserves distinct success and error feedback", () => {
    expect(declarations(".mf-territory-map__report-share.mf-icon-button.is-success"))
      .toContain("color: #047857");
    expect(declarations(".mf-territory-map__report-share.mf-icon-button.is-error"))
      .toContain("color: #b42318");
  });

  it("hides sharing while a destructive confirmation is active", () => {
    expect(declarations(
      ".mf-territory-map__report-detail--pilot:has(.mf-live-community-own-report__withdraw-confirm) .mf-territory-map__report-share",
    )).toContain("display: none");
  });

  it("keeps the dark action visible without overpowering the header", () => {
    const rule = declarations(
      'html[data-theme="dark"] .mf-territory-map__report-share.mf-icon-button',
    );

    expect(rule).toContain("background: transparent");
    expect(rule).toContain("color: #bfe6fb");
  });
});
