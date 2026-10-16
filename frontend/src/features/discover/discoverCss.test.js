import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("./discover.css", import.meta.url), "utf8");

function declarationsFor(selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`${escapedSelector}\\s*\\{([^}]+)\\}`))?.[1] || "";
}

describe("Discover theme colors", () => {
  it("uses semantic theme colors for the other-saints hierarchy", () => {
    expect(declarationsFor(".mf-discover-other-saints h3")).toContain("color: var(--mf-ink)");
    expect(declarationsFor(".mf-discover-other-saints p")).toContain("color: var(--mf-muted)");
    expect(declarationsFor(".mf-discover-other-saints button")).toContain("color: var(--mf-blue)");
  });

  it("keeps the municipality feature and white editorial cards unchanged", () => {
    const municipality = declarationsFor(".mf-discover-card--municipality");
    const editorial = declarationsFor(".mf-discover-view--editorial");
    const darkEditorial = declarationsFor('html[data-theme="dark"] .mf-discover-view--editorial');

    expect(municipality).toContain("linear-gradient(145deg, #0768a7 0%, #064b78 100%)");
    expect(municipality).toContain("border-color: rgb(var(--mf-gold-rgb) / 0.58)");
    expect(municipality).toContain("box-shadow: 0 14px 30px rgba(3, 67, 111, 0.18)");
    expect(editorial).toContain("--mf-editorial-surface: #ffffff");
    expect(darkEditorial).toContain("--mf-editorial-surface: var(--mf-neutral-surface)");
  });

  it("uses readable content colors for headings outside cards", () => {
    expect(declarationsFor(".mf-discover-focus__label,\n.mf-discover-section > h2,\n.mf-discover-calendar-heading > h2"))
      .toContain("color: var(--mf-page-ink)");
    expect(declarationsFor(".mf-discover-view--editorial > .mf-discover-section > h2,\n.mf-discover-view--editorial .mf-discover-calendar-heading > h2"))
      .toContain("color: var(--mf-page-ink)");
    expect(declarationsFor(".mf-discover-view--editorial > .mf-discover-source"))
      .toContain("color: var(--mf-page-muted)");
  });

  it("raises archival and Ostermann source contrast only in the dark editorial view", () => {
    const darkSources = declarationsFor(
      'html[data-theme="dark"] .mf-discover-view--editorial .mf-discover-editorial-source',
    );

    expect(darkSources).toContain("color: #a5b4fc");
    expect(declarationsFor(".mf-discover-view--editorial .mf-discover-editorial-source"))
      .toContain("color: var(--mf-soft)");
    expect(declarationsFor(".mf-discover-view--editorial .mf-discover-earth-tip"))
      .toContain("border-left: 4px solid var(--mf-alpine)");
    expect(declarationsFor(".mf-discover-view--editorial .mf-discover-earth-tip h3 > svg"))
      .toContain("color: var(--mf-alpine)");
  });
});

describe("Discover pilot editorial spacing", () => {
  it("matches the municipality feature gap around the curiosity section without changing other section spacing", () => {
    expect(declarationsFor(".mf-discover-view")).toContain("gap: var(--mf-space-3)");
    expect(declarationsFor(".mf-discover-view--editorial > .mf-discover-section:not(:first-child)"))
      .toContain("margin-block-start: max(0px, calc(29px - var(--mf-space-3)))");
    const curiosity = declarationsFor(".mf-discover-view--editorial > .mf-discover-section.mf-discover-why");
    expect(curiosity).toContain("gap: 0");
    expect(curiosity).toContain("margin-block-start: 0");
    expect(declarationsFor(".mf-discover-view--editorial .mf-discover-why > h2"))
      .toContain("margin-block: 0 8px");
  });
});
