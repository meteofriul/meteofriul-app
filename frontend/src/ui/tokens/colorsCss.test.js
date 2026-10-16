import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const colors = readFileSync(new URL("./colors.css", import.meta.url), "utf8");
const base = readFileSync(new URL("../base.css", import.meta.url), "utf8");

function declarationsFor(source, selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return source.match(new RegExp(`^${escapedSelector}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";
}

describe("app canvas theme tokens", () => {
  it("moves quickly from the navy header to the powder-blue light content canvas", () => {
    const light = declarationsFor(colors, ":root");
    const lightBody = declarationsFor(base, 'html:not([data-theme="dark"]) body');
    const endPosition = Number(
      light.match(/--mf-body-gradient-end-position:\s*(\d+)px/)?.[1],
    );

    expect(light).toContain("--mf-app-canvas: #052d4a");
    expect(light).toContain("--mf-paper: #b6d5e5");
    expect(light).toContain("--mf-body-gradient-start: #063a60");
    expect(light).toContain("--mf-body-gradient-transition: #8fbed8");
    expect(light).toContain("--mf-body-gradient-end: var(--mf-paper)");
    expect(endPosition).toBeGreaterThanOrEqual(160);
    expect(endPosition).toBeLessThanOrEqual(320);
    expect(lightBody).toContain("var(--mf-body-gradient-start-position)");
    expect(lightBody).toContain("var(--mf-body-gradient-transition)");
    expect(lightBody).toContain("var(--mf-body-gradient-transition-position)");
    expect(lightBody).toContain("var(--mf-body-gradient-end-position)");
    expect(lightBody).toContain("var(--mf-paper)");
    expect(light).toContain("--mf-shell-ink: #ffffff");
    expect(light).toContain("--mf-shell-muted: #bfdceb");
    expect(light).toContain("--mf-shell-accent: #8bd3ff");
    expect(light).toContain("--mf-page-ink: var(--mf-ink)");
    expect(light).toContain("--mf-page-muted: var(--mf-deep-blue)");
    expect(light).toContain("--mf-page-accent: var(--mf-deep-blue)");
    expect(light).toContain("--mf-neutral-surface: #ffffff");
    expect(light).toContain("--mf-brand-navy: #091d3d");
    expect(light).toContain("--mf-ink: #092a43");
    expect(light).toContain("--mf-muted: #40566a");
  });

  it("keeps the existing dark canvas separate from the light transition", () => {
    const dark = declarationsFor(colors, 'html[data-theme="dark"]');
    const html = declarationsFor(base, "html");
    const body = declarationsFor(base, "body");

    expect(dark).toContain("--mf-app-canvas: #061a2e");
    expect(dark).toContain("--mf-paper: #061a2e");
    expect(dark).toContain("--mf-body-gradient-transition: rgba(7, 30, 52, 1)");
    expect(dark).toContain("--mf-body-gradient-end-position: 46%");
    expect(dark).toContain("--mf-page-ink: var(--mf-shell-ink)");
    expect(dark).toContain("--mf-page-muted: var(--mf-shell-muted)");
    expect(dark).toContain("--mf-page-accent: var(--mf-shell-accent)");
    expect(dark).not.toContain("#8fbed8");
    expect(dark).not.toContain("#b6d5e5");
    expect(html).toContain("background: var(--mf-app-canvas)");
    expect(body).toContain("var(--mf-app-canvas)");
  });
});
