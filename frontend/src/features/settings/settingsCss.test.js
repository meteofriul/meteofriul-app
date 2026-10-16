import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const directory = path.dirname(fileURLToPath(import.meta.url));
const css = fs.readFileSync(path.join(directory, "settings.css"), "utf8");
const neutralCss = fs.readFileSync(path.join(directory, "../../ui/neutralSurfaces.css"), "utf8");

function ruleFrom(source, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return source.match(new RegExp(`^${escaped}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";
}

describe("pilot settings CSS", () => {
  it("keeps the first-run location disclosure compact, navy and scrollable without changing settings", () => {
    const startupCard = ruleFrom(css, ".mf-settings-disclosure--startup .mf-settings-disclosure__card");
    const startupBody = ruleFrom(css, ".mf-settings-disclosure--startup .mf-settings-disclosure__card > p");
    const startupActions = ruleFrom(css, ".mf-settings-disclosure--startup .mf-settings-disclosure__actions");

    expect(ruleFrom(css, ".mf-settings-disclosure--startup")).toContain("padding-inline: 18px");
    expect(startupActions).toContain("gap: var(--mf-space-2)");
    expect(startupCard).toContain("border-top: 4px solid var(--mf-brand-navy)");
    expect(startupCard).toContain("max-height: min(80dvh, 640px)");
    expect(startupBody).toContain("overflow-y: auto");
    expect(startupActions).toContain("grid-template-columns: repeat(2, minmax(0, 1fr))");
    expect(ruleFrom(css, ".mf-settings-disclosure--startup .mf-settings-disclosure__actions button"))
      .toContain("min-height: 48px");
    expect(ruleFrom(css, ".mf-settings-disclosure__card"))
      .toContain("background: var(--mf-surface-strong)");
    expect(ruleFrom(css, 'html[data-theme="dark"] .mf-settings-disclosure--startup .mf-settings-disclosure__card h2'))
      .toContain("color: var(--mf-ink)");
  });

  it("left-aligns the pilot title beside a 44px icon-only back control", () => {
    const topbar = ruleFrom(css, ".mf-settings-topbar");
    const title = ruleFrom(css, ".mf-settings-topbar > strong");
    const back = ruleFrom(css, ".mf-settings-topbar .mf-settings-back--icon");

    expect(topbar).toContain("display: flex");
    expect(topbar).toContain("gap: 10px");
    expect(title).toContain("font-size: clamp(1.25rem, 4.6vw, 1.375rem)");
    expect(back).toContain("height: 44px");
    expect(back).toContain("width: 44px");
    expect(back).toContain("border-radius: 50%");
    expect(back).toContain("background: rgba(255, 255, 255, 0.86)");
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.mf-settings-topbar \.mf-settings-back--icon\s*\{[^}]*transition: none/);
  });

  it("uses a luminous responsive identity card with accessible touch targets", () => {
    const card = ruleFrom(css, ".mf-settings-identity");
    const avatar = ruleFrom(css, ".mf-settings-identity__avatar");
    const headline = ruleFrom(css, ".mf-settings-identity__headline");
    const refresh = ruleFrom(css, ".mf-settings-identity__refresh");
    const refreshSurface = ruleFrom(css, ".mf-settings-identity__refresh::before");
    const stat = ruleFrom(css, ".mf-settings-identity__stats > span");
    const statValue = ruleFrom(css, ".mf-settings-identity__stat-value");
    const darkCard = ruleFrom(css, 'html[data-theme="dark"] .mf-settings-identity');

    expect(card).toContain("grid-template-columns: 52px minmax(0, 1fr)");
    expect(card).toContain("border-radius: 18px");
    expect(card).toContain("background: #fff");
    expect(card).toContain("box-shadow: 0 4px 16px rgba(0, 40, 80, 0.07)");
    expect(avatar).toContain("height: 52px");
    expect(avatar).toContain("width: 52px");
    expect(avatar).toContain("background: transparent");
    expect(avatar).toContain("box-shadow: none");
    expect(headline).toContain("grid-template-columns: minmax(0, 1fr) 44px");
    expect(headline).toContain("align-items: center");
    expect(refresh).toContain("align-self: center");
    expect(refresh).toContain("height: 44px");
    expect(refresh).toContain("width: 44px");
    expect(refreshSurface).toContain("height: 36px");
    expect(refreshSurface).toContain("width: 36px");
    expect(ruleFrom(css, ".mf-settings-identity__refresh:active::before"))
      .toContain("transform: scale(0.94)");
    expect(stat).toContain("background: #f8fafc");
    expect(stat).toContain("color: #475569");
    expect(statValue).toContain("color: #0369a1");
    expect(statValue).toContain("font-size: 0.74rem");
    expect(statValue).toContain("font-weight: 850");
    expect(statValue).toContain("font-variant-numeric: tabular-nums");
    expect(darkCard).toContain("background: var(--mf-neutral-surface)");
    expect(css).toMatch(/@media \(max-width: 340px\)[\s\S]*?\.mf-settings-identity__stats,[\s\S]*?grid-column: 1 \/ -1/);
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.mf-settings-identity__refresh::before\s*\{[^}]*transition: none/);
    expect(css).toContain("animation: mf-settings-avatar-refresh 260ms ease-out");
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.mf-settings-identity\.is-changing[\s\S]*?animation: none/);
  });

  it("keeps the grouped layout scoped to the pilot and clear of the bottom navigation", () => {
    expect(ruleFrom(css, ".mf-settings-view--pilot"))
      .toContain("padding-bottom: calc(var(--mf-bottom-nav-height, 84px) + 26px)");
    expect(ruleFrom(css, ".mf-settings-view--pilot .mf-settings-panel--pilot-group"))
      .toContain("border-radius: 16px");
    expect(ruleFrom(neutralCss, ".mf-settings-view--pilot .mf-settings-panel--pilot-group"))
      .toContain("box-shadow: 0 3px 10px");
  });

  it("uses compact segmented controls with full touch hit areas", () => {
    const segments = ruleFrom(css, ".mf-settings-segments--inline");
    const language = ruleFrom(css, ".mf-settings-segments.mf-settings-segments--language");
    const option = ruleFrom(css, ".mf-settings-segments--inline .mf-settings-segment");
    const hitArea = ruleFrom(css, ".mf-settings-segments--inline .mf-settings-segment::after");

    expect(segments).toContain("gap: 6px");
    expect(segments).toContain("padding: 5px");
    expect(segments).toContain("border-radius: 16px");
    expect(language).toContain("grid-template-columns: repeat(2, minmax(0, 1fr))");
    expect(option).toContain("min-height: 36px");
    expect(option).toContain("border-radius: 12px");
    expect(hitArea).toContain("inset: -4px 0");
  });

  it("keeps pilot row values before their trailing actions", () => {
    expect(ruleFrom(
      css,
      ".mf-settings-view--pilot .mf-settings-row--with-action .mf-settings-row__value",
    )).toContain("grid-column: 3");
    expect(ruleFrom(
      css,
      ".mf-settings-view--pilot .mf-settings-row--with-action .mf-settings-row__action",
    )).toContain("grid-column: 4");
    expect(ruleFrom(
      css,
      ".mf-settings-view--pilot .mf-settings-row--with-action.mf-settings-row--without-value .mf-settings-row__action",
    )).toContain("grid-column: 3");
  });

  it("uses restrained semantic icon tokens in light and dark themes", () => {
    const pilot = ruleFrom(css, ".mf-settings-view--pilot");
    const darkPilot = ruleFrom(css, 'html[data-theme="dark"] .mf-settings-view--pilot');
    const iconTreatment = css.match(
      /\.mf-settings-view--pilot \.mf-settings-row__icon,\s*\.mf-settings-view--pilot \.mf-settings-privacy-link__icon\s*\{([^}]+)\}/,
    )?.[1] || "";
    const brand = css.match(
      /\.mf-settings-view--pilot\s+\.mf-settings-product-link--brand \.mf-settings-product-link__icon\s*\{([^}]+)\}/,
    )?.[1] || "";
    const brandSize = ruleFrom(css, ".mf-settings-view--pilot .mf-settings-product-link__icon");

    expect(pilot).toContain("--mf-settings-icon-general-bg: rgba(2, 132, 199, 0.12)");
    expect(pilot).toContain("--mf-settings-icon-alert-ink: #b45309");
    expect(pilot).toContain("--mf-settings-icon-notice-ink: #5b21b6");
    expect(pilot).toContain("--mf-settings-icon-privacy-ink: #0f766e");
    expect(pilot).toContain("--mf-settings-icon-support-ink: #e11d48");
    expect(pilot).toContain("--mf-settings-icon-utility-ink: #475569");
    expect(darkPilot).toContain("--mf-settings-icon-general-ink: #7dd3fc");
    expect(darkPilot).toContain("--mf-settings-icon-alert-ink: #fbbf24");
    expect(darkPilot).toContain("--mf-settings-icon-notice-ink: #a5b4fc");
    expect(darkPilot).toContain("--mf-settings-icon-privacy-ink: #5eead4");
    expect(darkPilot).toContain("--mf-settings-icon-support-ink: #fda4af");
    expect(darkPilot).toContain("--mf-settings-icon-utility-ink: #cbd5e1");
    expect(iconTreatment).toContain("background: var(--mf-settings-icon-bg)");
    expect(iconTreatment).toContain("border-color: var(--mf-settings-icon-border)");
    expect(iconTreatment).toContain("color: var(--mf-settings-icon-ink)");
    expect(iconTreatment).toContain("box-shadow: none");
    expect(iconTreatment).not.toContain("gradient");
    expect(ruleFrom(css, ".mf-settings-view--pilot .mf-settings-row--alert"))
      .toContain("--mf-settings-icon-bg: var(--mf-settings-icon-alert-bg)");
    expect(ruleFrom(css, ".mf-settings-view--pilot .mf-settings-row--notice"))
      .toContain("--mf-settings-icon-bg: var(--mf-settings-icon-notice-bg)");
    expect(ruleFrom(css, ".mf-settings-view--pilot .mf-settings-product-link--privacy"))
      .toContain("--mf-settings-icon-bg: var(--mf-settings-icon-privacy-bg)");
    expect(ruleFrom(css, ".mf-settings-view--pilot .mf-settings-product-link--support"))
      .toContain("--mf-settings-icon-bg: var(--mf-settings-icon-support-bg)");
    expect(brandSize).toContain("height: 32px");
    expect(brandSize).toContain("width: 32px");
    expect(brand).toContain("padding: 3px");
    expect(brand).toContain("box-shadow: none");
  });

  it("centers and softens the pilot default-location value without changing ordinary rows", () => {
    const pilotValue = ruleFrom(
      css,
      ".mf-settings-view--pilot .mf-settings-row--default-location .mf-settings-row__value",
    );
    const pilotAction = ruleFrom(
      css,
      ".mf-settings-view--pilot .mf-settings-row--default-location .mf-settings-row__action",
    );

    expect(pilotValue).toContain("align-self: center");
    expect(pilotValue).toContain("color: var(--mf-muted)");
    expect(pilotValue).toContain("font-size: 0.875rem");
    expect(pilotValue).toContain("font-weight: 500");
    expect(pilotAction).toContain("align-self: center");
    expect(css).not.toMatch(/^\.mf-settings-row--default-location\s*\{/m);
  });

  it("visually de-emphasizes only pilot web notification switches that are disabled", () => {
    expect(ruleFrom(
      css,
      '.mf-settings-view--pilot .mf-settings-row[data-pilot-web-read-only="true"] .mf-settings-toggle:disabled',
    )).toContain("opacity: 0.45");
    expect(ruleFrom(css, ".mf-settings-toggle:disabled")).toContain("opacity: 0.58");
  });

  it("keeps the switch convention left for off and right for on", () => {
    expect(ruleFrom(css, ".mf-settings-toggle__thumb")).toContain("transform: translateX(0)");
    expect(ruleFrom(
      css,
      '.mf-settings-toggle[aria-checked="true"] .mf-settings-toggle__thumb',
    )).toContain("transform: translateX(18px)");
  });

  it("preserves dark-mode contrast and stacks the theme selector on narrow screens", () => {
    expect(ruleFrom(
      css,
      'html[data-theme="dark"] .mf-settings-view--pilot .mf-settings-segment.is-active',
    )).toContain("color: var(--mf-deep-blue)");
    expect(css).toContain("@media (max-width: 390px)");
    expect(css).toMatch(/\.mf-settings-segments--theme\s*\{[^}]*grid-column:\s*2;[^}]*width:\s*100%/s);
  });
});
