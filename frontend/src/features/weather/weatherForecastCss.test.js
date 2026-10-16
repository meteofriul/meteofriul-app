import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const cssPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "weatherForecast.css");
const css = fs.readFileSync(cssPath, "utf8");

function rule(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`^${escaped}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";
}

describe("weather forecast mobile list CSS", () => {
  it("scopes the raised dark surface tokens to the forecast view", () => {
    const view = rule('html[data-theme="dark"] .mf-weather-forecast-view');

    expect(view).toContain("--mf-neutral-surface: #162235");
    expect(view).toContain("--mf-neutral-border: rgba(255, 255, 255, 0.08)");
  });

  it("keeps air and pollen tiles compact and centered in two flexible columns", () => {
    expect(rule(".mf-weather-cams-card__values")).toContain("repeat(2, minmax(0, 1fr))");
    expect(rule(".mf-weather-cams-card__values > div")).toContain("min-height: 78px");
    expect(rule(".mf-weather-cams-card__values > div")).toContain("text-align: center");
    expect(rule(".mf-weather-cams-card__values dt")).toContain("font-size: 0.875rem");
    expect(rule(".mf-weather-cams-card__values dd")).toContain("font-size: 1.375rem");
    expect(rule(".mf-weather-cams-card__values dd")).toContain("justify-content: center");
    expect(rule(".mf-weather-cams-card__values dd span")).toContain("flex-basis: 100%");
    expect(rule(".mf-weather-cams-card__values dd")).toContain("flex-wrap: wrap");
    expect(rule(".mf-weather-cams-card__values dd span")).toContain("font-size: 0.75rem");
  });
  it("reserves the missing precipitation row without redistributing card spacing", () => {
    expect(rule(".mf-weather-day-summary")).toContain("align-content: start");
    expect(rule(".mf-weather-day-summary .mf-weather-day-summary__metrics")).toContain("min-height: 1.25em");
  });
  it("enlarges weather icons within the existing time column", () => {
    expect(rule(".mf-weather-hourly-row__when .mf-home-meteocon-icon")).toContain("width: 44px");
    expect(rule(".mf-weather-hourly-row__when .mf-home-meteocon-icon")).toContain("height: 44px");
    expect(rule(".mf-weather-day-summary .mf-weather-day-summary__icon")).toContain("width: 48px");
  });
  it("keeps the legacy hourly list in full-width vertical rows", () => {
    const row = rule(".mf-weather-hourly-row");

    expect(row).toContain("grid-template-columns: 50px minmax(0, 1fr) auto 18px");
    expect(row).toContain("min-height: 64px");
    expect(row).toContain("width: 100%");
    expect(css).not.toContain("mf-weather-hourly-timeline__grid");
    expect(row).not.toContain("overflow-x: auto");
  });

  it("keeps the pilot hourly ribbon horizontally scrollable with snap-aligned cards", () => {
    const ribbon = rule(".mf-weather-hour-ribbon");
    const hour = rule(".mf-weather-hour-ribbon > button");

    expect(ribbon).toContain("display: flex");
    expect(ribbon).toContain("gap: 0");
    expect(ribbon).toContain("overflow-x: auto");
    expect(ribbon).toContain("scroll-snap-type: x proximity");
    expect(hour).toContain("background: transparent");
    expect(hour).toContain("border: 1px solid transparent");
    expect(hour).toContain("min-height: 96px");
    expect(hour).toContain("scroll-snap-align: start");
    expect(hour).not.toContain("linear-gradient");
    expect(hour).not.toContain("box-shadow");
    expect(rule(".mf-weather-hour-ribbon__precipitation--empty")).toContain("visibility: hidden");
  });

  it("uses one continuous navy ribbon without secondary icon tiles", () => {
    const day = rule(".mf-weather-day-picker button");
    const ribbon = rule(".mf-weather-hour-ribbon");
    const dayIconContrast = rule('.mf-weather-day-picker button:not([aria-pressed="true"]) .mf-home-meteocon-icon');
    const iconFrame = rule(".mf-weather-hour-ribbon__icon-frame");
    const ribbonIcon = rule(".mf-weather-hour-ribbon__icon-frame .mf-home-meteocon-icon");
    const nightFrame = rule('.mf-weather-hour-ribbon__icon-frame[data-phase="night"]');
    const darkRibbon = rule('html[data-theme="dark"] .mf-weather-hour-ribbon');

    expect(day).toContain("background: color-mix(in srgb, var(--mf-blue-050) 58%, #ffffff)");
    expect(ribbon).toContain("linear-gradient(140deg, #173965, #091d3d)");
    expect(ribbon).toContain("border-radius: 16px");
    expect(ribbon).toContain("margin-top: 4px");
    expect(ribbon).toMatch(/padding: [^;]+;/);
    expect(dayIconContrast).toContain("filter: drop-shadow(0 1px 2px rgb(4 51 85 / 0.2))");
    expect(iconFrame).toContain("height: 42px");
    expect(iconFrame).toContain("width: 42px");
    expect(iconFrame).toContain("background: transparent");
    expect(iconFrame).toContain("border: 0");
    expect(iconFrame).toContain("border-radius: 0");
    expect(iconFrame).toContain("box-shadow: none");
    expect(ribbonIcon).toContain("saturate(1.16)");
    expect(ribbonIcon).not.toContain("brightness(0)");
    expect(ribbonIcon).not.toContain("invert(");
    expect(nightFrame).toContain("background: transparent");
    expect(nightFrame).toContain("border: 0");
    expect(darkRibbon).toContain("linear-gradient(140deg, #173965, #091d3d)");
    expect(darkRibbon).toContain("border-color: rgb(142 219 255 / 32%)");
  });

  it("balances ribbon text hierarchy and marks the current hour accessibly", () => {
    const iconFrame = rule(".mf-weather-hour-ribbon__icon-frame");
    const moon = rule(".mf-weather-hour-ribbon__moon");
    const crescent = rule(".mf-weather-hour-ribbon__night-crescent");
    const selectedMoon = rule(
      '.mf-weather-hour-ribbon > button[aria-pressed="true"] .mf-weather-hour-ribbon__moon',
    );
    const current = rule('.mf-weather-hour-ribbon[data-has-selection="false"] > button[aria-current="time"]');
    const time = rule(".mf-weather-hour-ribbon time");
    const temperature = rule(".mf-weather-hour-ribbon strong");
    const precipitation = rule(".mf-weather-hour-ribbon small");

    expect(iconFrame).toContain("aspect-ratio: 1");
    expect(iconFrame).toContain("display: inline-flex");
    expect(iconFrame).toContain("width: 42px");
    expect(moon).toContain("color: #93c5fd");
    expect(moon).toContain("stroke: #e2e8f0");
    expect(crescent).toContain("color: #93c5fd");
    expect(crescent).toContain("position: absolute");
    expect(time).toContain("color: #cbd5e1");
    expect(temperature).toContain("color: #ffffff");
    expect(temperature).toContain("font-weight: 900");
    expect(precipitation).toContain("color: #93c5fd");
    expect(current).toContain("background: rgb(255 255 255 / 0.12)");
    expect(current).toContain("border-color: rgb(255 255 255 / 0.22)");
    expect(selectedMoon).toContain("color: #ffffff");
    expect(selectedMoon).toContain("stroke: #ffffff");
    expect(selectedMoon).toContain("drop-shadow(0 2px 6px rgb(2 132 199 / 0.55))");
  });

  it("keeps the pilot card header compact and the day controls tactile", () => {
    const header = rule(".mf-weather-hourly-card__pilot-header");
    const day = rule(".mf-weather-day-picker button");
    const activeDay = rule(
      '.mf-weather-hourly-card--ribbon .mf-weather-day-picker button[aria-pressed="true"]',
    );
    const darkActiveDay = rule(
      'html[data-theme="dark"] .mf-weather-hourly-card--ribbon .mf-weather-day-picker button[aria-pressed="true"]',
    );
    const activeDayIcon = rule(
      '.mf-weather-hourly-card--ribbon .mf-weather-day-picker button[aria-pressed="true"] .mf-home-meteocon-icon',
    );

    expect(header).toContain("grid-template-columns: minmax(0, 1fr) auto");
    expect(header).toContain("border-bottom: 1px solid");
    expect(rule(".mf-weather-hourly-card__pilot-model")).toContain("font-size: 0.6875rem");
    expect(day).toContain("border-radius: 16px");
    expect(day).toContain("min-height: 44px");
    expect(rule(".mf-weather-day-picker button > strong")).toContain("white-space: nowrap");
    expect(rule(".mf-weather-day-picker button > strong")).toContain("text-overflow: ellipsis");
    expect(activeDay).toContain("background: linear-gradient(135deg, #38bdf8, #0284c7)");
    expect(activeDay).toContain("border-top: 1.5px solid rgb(255 255 255 / 0.45)");
    expect(activeDay).toContain("box-shadow: 0 6px 16px rgb(2 132 199 / 0.35)");
    expect(activeDay).toContain("color: var(--mf-white)");
    expect(activeDayIcon).toContain("drop-shadow");
    expect(activeDayIcon).toContain("saturate(1.08)");
    expect(activeDayIcon).not.toContain("brightness(0)");
    expect(activeDayIcon).not.toContain("invert(");
    expect(darkActiveDay).toContain("background: linear-gradient(135deg, #38bdf8, #0284c7)");
    expect(rule(".mf-weather-day-picker button:focus-visible,\n.mf-weather-hour-ribbon > button:focus-visible"))
      .toContain("outline: 3px solid var(--mf-focus)");
  });

  it("uses a compact two-column environmental grid with a single safe-area detail sheet", () => {
    const grid = rule(".mf-weather-environment-grid");
    const tile = rule(".mf-weather-environment-tile");
    const sky = rule(".mf-weather-environment-tile--sky");
    const uv = rule(".mf-weather-environment-tile--uv");
    const air = rule(".mf-weather-environment-tile--air");
    const pollen = rule(".mf-weather-environment-tile--pollen");
    const badge = rule(".mf-weather-environment-badge");
    const chevron = rule(".mf-weather-environment-tile__header > svg");
    const sheet = rule(".mf-weather-environment-sheet");
    const close = rule(".mf-weather-environment-sheet__close");

    expect(grid).toContain("grid-template-columns: repeat(2, minmax(0, 1fr))");
    expect(tile).toContain("min-height: 190px");
    expect(tile).toContain("background: var(--mf-neutral-surface)");
    expect(tile).toContain("border: 1px solid var(--mf-neutral-border)");
    expect(tile).not.toContain("linear-gradient");
    expect(tile).toContain("width: 100%");
    expect(sky).toContain("--environment-accent: var(--mf-gold-700)");
    expect(uv).toContain("--environment-accent: #875197");
    expect(air).toContain("--environment-accent: var(--mf-blue)");
    expect(pollen).toContain("--environment-accent: var(--mf-alpine)");
    expect(chevron).toContain("color: var(--mf-muted)");
    expect(badge).toContain("var(--mf-neutral-surface)");
    expect(badge).toContain("color: var(--mf-muted)");
    expect(sheet).toContain("background: var(--mf-neutral-surface)");
    expect(sheet).toContain("border: 1px solid var(--mf-neutral-border)");
    expect(sheet).toContain("max-height: min(86dvh, 760px)");
    expect(sheet).toContain("var(--mf-safe-area-inset-bottom)");
    expect(sheet).toContain("overflow: hidden");
    expect(close).toContain("height: 44px");
    expect(close).toContain("width: 44px");
    expect(rule('html[data-theme="dark"] .mf-weather-environment-tile'))
      .toContain("background: #162235");
    expect(rule('html[data-theme="dark"] .mf-weather-environment-tile--uv'))
      .toContain("--environment-accent: #d5a6e3");
    expect(rule('html[data-theme="dark"] .mf-weather-environment-sheet')).toContain("background: var(--mf-surface)");
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.mf-weather-environment-sheet\[open\][\s\S]*?animation: none/);
  });

  it("uses glossy report-style mini-squircles for the four compact data cards", () => {
    const iconSelector = ".mf-weather-environment-grid > .mf-weather-environment-tile >\n"
      + ".mf-weather-environment-tile__header > .mf-weather-environment-tile__icon";
    const icon = rule(iconSelector);
    const iconGlyph = rule(`${iconSelector} svg`);
    const darkIcon = rule(`html[data-theme="dark"] ${iconSelector}`);
    const darkIconGlyph = rule(`html[data-theme="dark"] ${iconSelector} svg`);
    const sky = rule(".mf-weather-environment-tile--sky");
    const uv = rule(".mf-weather-environment-tile--uv");
    const air = rule(".mf-weather-environment-tile--air");
    const pollen = rule(".mf-weather-environment-tile--pollen");

    expect(icon).toContain("border-radius: 12px");
    expect(icon).toContain("height: 32px");
    expect(icon).toContain("width: 32px");
    expect(icon).toContain("border-top: 1px solid rgb(255 255 255 / 0.5)");
    expect(icon).toContain("var(--environment-icon-from)");
    expect(icon).toContain("var(--environment-icon-to)");
    expect(icon).toContain("0 4px 10px var(--environment-icon-shadow)");
    expect(icon).toContain("color: #fff");
    expect(iconGlyph).toContain("filter: drop-shadow(0 1px 2px rgb(3 41 66 / 0.22))");
    expect(darkIcon).toContain("background: rgb(var(--environment-neon-rgb) / 0.15)");
    expect(darkIcon).toContain("color: var(--environment-neon-color)");
    expect(darkIcon).toContain("0 0 12px rgb(var(--environment-neon-rgb) / 0.22)");
    expect(darkIconGlyph).toContain("drop-shadow(0 0 5px rgb(var(--environment-neon-rgb) / 0.5))");

    expect(sky).toContain("--environment-icon-from: #fbbf24");
    expect(sky).toContain("--environment-icon-to: #d97706");
    expect(sky).toContain("--environment-icon-shadow: rgb(217 119 6 / 0.3)");
    expect(uv).toContain("--environment-icon-from: #c084fc");
    expect(uv).toContain("--environment-icon-to: #7c3aed");
    expect(uv).toContain("--environment-neon-color: #c084fc");
    expect(air).toContain("--environment-icon-from: #38bdf8");
    expect(air).toContain("--environment-icon-to: #0284c7");
    expect(pollen).toContain("--environment-icon-from: #10b981");
    expect(pollen).toContain("--environment-icon-to: #047857");
    expect(pollen).toContain("--environment-neon-color: #34d399");
  });

  it("keeps the UV icon purple while the number communicates the objective risk level", () => {
    const low = rule('.mf-weather-environment-tile--uv[data-uv-level="low"]');
    const moderate = rule('.mf-weather-environment-tile--uv[data-uv-level="moderate"]');
    const high = rule('.mf-weather-environment-tile--uv[data-uv-level="high"]');
    const severe = rule(
      '.mf-weather-environment-tile--uv[data-uv-level="very-high"],\n'
        + '.mf-weather-environment-tile--uv[data-uv-level="extreme"]',
    );

    expect(low).not.toContain("--environment-icon-from");
    expect(low).not.toContain("--environment-neon-color");
    expect(low).toContain("--environment-value-color: #059669");
    expect(moderate).not.toContain("--environment-icon-from");
    expect(moderate).toContain("--environment-value-color: #b45309");
    expect(high).not.toContain("--environment-icon-from");
    expect(high).toContain("--environment-value-color: #7c3aed");
    expect(severe).not.toContain("--environment-icon-from");
    expect(severe).toContain("--environment-value-color: #dc2626");
    expect(rule(".mf-weather-environment-uv-value"))
      .toContain("color: var(--environment-value-color)");

    expect(rule('html[data-theme="dark"] .mf-weather-environment-tile--uv[data-uv-level="low"]'))
      .toContain("--environment-value-color: #34d399");
    expect(rule('html[data-theme="dark"] .mf-weather-environment-tile--uv[data-uv-level="moderate"]'))
      .toContain("--environment-value-color: #fbbf24");
    expect(rule('html[data-theme="dark"] .mf-weather-environment-tile--uv[data-uv-level="high"]'))
      .toContain("--environment-value-color: #c084fc");
    expect(rule(
      'html[data-theme="dark"] .mf-weather-environment-tile--uv[data-uv-level="very-high"],\n'
        + 'html[data-theme="dark"] .mf-weather-environment-tile--uv[data-uv-level="extreme"]',
    )).toContain("--environment-value-color: #fb7185");
  });

  it("keeps CAMS detail traceability and methodology as separate quiet footer rows", () => {
    const status = rule(".mf-weather-environment-sheet .mf-weather-cams-card__status");
    const footer = rule(".mf-weather-environment-sheet .mf-weather-cams-card__footer--detail");
    const rows = rule(".mf-weather-environment-sheet .mf-weather-cams-card__footer--detail small");
    const trace = rule(".mf-weather-environment-sheet .mf-weather-cams-card__trace");
    const methodology = rule(".mf-weather-environment-sheet .mf-weather-cams-card__method-note");
    const methodologyIcon = rule(".mf-weather-environment-sheet .mf-weather-cams-card__method-note svg");
    const darkFooter = rule('html[data-theme="dark"] .mf-weather-environment-sheet .mf-weather-cams-card__footer--detail');

    expect(status).toContain("box-sizing: border-box");
    expect(status).toContain("justify-self: center");
    expect(status).toContain("max-width: 400px");
    expect(status).toContain("padding-inline: 12px");
    expect(status).toContain("text-align: center");
    expect(status).toContain("width: 100%");
    expect(footer).toContain("box-sizing: border-box");
    expect(footer).toContain("display: grid");
    expect(footer).toContain("color: #64748b");
    expect(footer).toMatch(/gap: [^;]+;/);
    expect(footer).toContain("justify-content: stretch");
    expect(footer).toContain("justify-items: center");
    expect(footer).toContain("padding: 10px 12px 6px");
    expect(footer).toContain("width: 100%");
    expect(rows).toContain("font-size: 0.6875rem");
    expect(rows).toContain("line-height: 1.5");
    expect(rows).toContain("margin: 0");
    expect(trace).toContain("display: block");
    expect(trace).toContain("max-width: 400px");
    expect(trace).toContain("text-align: center");
    expect(trace).toContain("width: 100%");
    expect(methodology).toContain("display: grid");
    expect(methodology).toContain("align-items: start");
    expect(methodology).toContain("grid-template-columns: auto minmax(0, 1fr)");
    expect(methodology).toMatch(/gap: [^;]+;/);
    expect(methodology).toContain("justify-self: center");
    expect(methodology).toContain("max-width: 400px");
    expect(methodology).toContain("width: 100%");
    expect(methodologyIcon).toMatch(/(?:flex:\s*0 0 auto|flex-shrink:\s*0)/);
    expect(darkFooter).toContain("color: var(--mf-muted)");
  });

  it("keeps selected state visible without relying on colour alone", () => {
    const selected = rule('.mf-weather-hourly-list li[data-selected="true"]');

    expect(selected).toContain("box-shadow: inset 4px 0 0");
  });

  it("keeps detail metrics in two columns and the location pill compact", () => {
    expect(rule(".mf-weather-hourly-detail")).toContain("grid-template-columns: repeat(2, minmax(0, 1fr))");
    expect(rule(".mf-weather-forecast-header .mf-location-change")).toContain("min-height: 28px");
  });

  it("makes charts responsive without a fixed rendered width", () => {
    const chart = rule(".mf-weather-chart svg");

    expect(chart).toContain("max-width: 100%");
    expect(chart).toContain("width: 100%");
    expect(chart).toContain("height: auto");
  });
});
