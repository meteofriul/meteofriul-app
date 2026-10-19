import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const cssPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "weatherNavigation.css");
const neutralCssPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "../../ui/neutralSurfaces.css");
const css = fs.readFileSync(cssPath, "utf8");
const neutralCss = fs.readFileSync(neutralCssPath, "utf8");

function ruleFrom(source, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return source.match(new RegExp(`^${escaped}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";
}

function rule(selector) {
  return ruleFrom(css, selector);
}

describe("weather route context CSS", () => {
  it("keeps the location and section controls in a compact vertical rhythm", () => {
    expect(rule(".mf-weather-route-shell")).toContain("display: grid");
    expect(rule(".mf-weather-route-shell")).toContain("gap: var(--mf-space-3)");
    expect(rule(".mf-weather-route-context .mf-location-context__action")).toContain("margin-left: 4px");
    expect(rule(".mf-weather-route-context .mf-location-context__action")).toContain("font-size: 0.78rem");
    expect(rule(".mf-weather-section-nav__item")).toContain("min-height: 44px");
  });

  it("uses a slim theme-aware glass treatment in the compact pilot variant", () => {
    const compactBar = rule(".mf-weather-section-nav--compact");
    const compactItem = rule(".mf-weather-section-nav--compact .mf-weather-section-nav__item");
    const compactHitArea = rule(".mf-weather-section-nav--compact .mf-weather-section-nav__item::before");
    const compactActive = rule(".mf-weather-section-nav--compact .mf-weather-section-nav__item.is-active");
    const darkBar = rule('html[data-theme="dark"] .mf-weather-section-nav--compact');
    const darkInactive = rule([
      'html[data-theme="dark"]',
      "  .mf-weather-section-nav--compact",
      "  .mf-weather-section-nav__item:not(.is-active)",
    ].join("\n"));
    const darkActive = rule([
      'html[data-theme="dark"]',
      "  .mf-weather-section-nav--compact",
      "  .mf-weather-section-nav__item.is-active",
    ].join("\n"));
    const compactPressed = rule([
      ".mf-weather-section-nav--compact",
      "  .mf-weather-section-nav__item:not(.is-active, :disabled):active",
    ].join("\n"));
    const darkPressed = rule([
      'html[data-theme="dark"]',
      "  .mf-weather-section-nav--compact",
      "  .mf-weather-section-nav__item:not(.is-active, :disabled):active",
    ].join("\n"));

    expect(compactBar).toContain("gap: 4px");
    expect(compactBar).toContain("padding: 3px");
    expect(compactBar).toContain("background: rgba(255, 255, 255, 0.85)");
    expect(compactBar).toContain("backdrop-filter: blur(12px)");
    expect(compactBar).toContain("box-shadow: 0 4px 16px rgba(0, 40, 80, 0.08)");
    expect(compactItem).toContain("min-height: 32px");
    expect(compactItem).toContain("color: #475569");
    expect(compactHitArea).toContain("inset: -6px 0");
    expect(compactActive).toContain("linear-gradient(135deg, #0277b5 0%, #0369a1 100%)");
    expect(darkBar).toContain("background: rgba(15, 23, 42, 0.75)");
    expect(darkBar).toContain("backdrop-filter: blur(16px)");
    expect(darkInactive).toContain("color: #94a3b8");
    expect(darkActive).toContain("linear-gradient(135deg, #0277b5 0%, #0369a1 100%)");
    expect(compactPressed).toContain("background: rgba(2, 132, 199, 0.1)");
    expect(darkPressed).toContain("background: rgba(255, 255, 255, 0.06)");
    expect(neutralCss).toContain(
      ".mf-weather-section-nav:not(.mf-weather-section-nav--compact)",
    );
  });

  it("uses the calmer selected colors only in dark Meteo", () => {
    const darkTab = ruleFrom(neutralCss, 'html[data-theme="dark"] .mf-app-shell.is-definitive-app .mf-weather-route-shell .mf-weather-section-nav--compact .mf-weather-section-nav__item.is-active');

    expect(darkTab).toContain("background: linear-gradient(135deg, #0277b5, #0369a1)");
    expect(neutralCss).not.toContain('.mf-weather-day-picker button[aria-pressed="true"]');
    expect(darkTab).toContain("color: #fff");
    expect(neutralCss).toContain('html:not([data-theme="dark"]) .mf-app-shell.is-definitive-app :is(');
    expect(neutralCss).toContain("background: var(--mf-definitive-gradient)");
  });
});
