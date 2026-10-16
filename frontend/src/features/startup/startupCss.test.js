import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const cssPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "startup.css");
const css = fs.readFileSync(cssPath, "utf8");

function rule(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`^${escaped}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";
}

describe("pilot language onboarding CSS", () => {
  it("uses the neutral card surface supplied by the active theme", () => {
    const sharedCard = rule(".mf-web-onboarding__card");

    expect(rule(".mf-pilot-language-onboarding"))
      .toContain("background: var(--mf-neutral-surface)");
    expect(sharedCard).toContain("linear-gradient");
    expect(sharedCard).toContain("var(--mf-surface)");
  });

  it("centers the compact language dialog and uses the canonical navy for its accent", () => {
    expect(rule(".mf-web-onboarding--language")).toContain("align-items: center");
    expect(rule(".mf-web-onboarding--language .mf-pilot-language-onboarding"))
      .toContain("border-top: 4px solid var(--mf-brand-navy)");
    expect(rule(".mf-pilot-language-onboarding__heading"))
      .toContain("grid-template-columns: 52px minmax(0, 1fr)");
    expect(rule(".mf-pilot-language-onboarding__choices"))
      .toContain("grid-template-columns: repeat(2, minmax(0, 1fr))");
    expect(rule(".mf-pilot-language-onboarding__choice"))
      .toContain("min-height: 48px");
    expect(rule(".mf-pilot-language-onboarding__choice.is-active"))
      .toContain("background: var(--mf-brand-navy)");
    expect(rule(".mf-pilot-language-onboarding__choice.is-active"))
      .toContain("color: #fff");
    expect(rule('html[data-theme="dark"] .mf-pilot-language-onboarding h2'))
      .toContain("color: var(--mf-ink)");
  });
});
