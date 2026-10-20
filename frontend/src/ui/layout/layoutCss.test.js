import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const cssPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "layout.css");
const css = fs.readFileSync(cssPath, "utf8");
const componentsCss = fs.readFileSync(
  path.join(path.dirname(cssPath), "../components/components.css"),
  "utf8",
);
const neutralCss = fs.readFileSync(
  path.join(path.dirname(cssPath), "../neutralSurfaces.css"),
  "utf8",
);
const eventsCss = fs.readFileSync(
  path.join(path.dirname(cssPath), "../../features/events/events.css"),
  "utf8",
);

function ruleFrom(source, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return source.match(new RegExp(`^[\\t ]*${escaped}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";
}

function rule(selector) {
  return ruleFrom(css, selector);
}

describe("pilot header branding CSS", () => {
  it("uses a 40px glass profile surface inside the accessible 44px header target", () => {
    const button = ruleFrom(
      componentsCss,
      "html .mf-header-actions > .mf-icon-button.mf-header-profile-button",
    );
    const surface = ruleFrom(componentsCss, ".mf-header-profile-button::before");
    const active = ruleFrom(
      componentsCss,
      ".mf-header-profile-button:not(:disabled):active::before",
    );

    expect(button).toContain("height: var(--mf-touch-target)");
    expect(button).toContain("width: var(--mf-touch-target)");
    expect(button).toContain("border-radius: 50%");
    expect(surface).toContain("inset: 2px");
    expect(surface).toContain("background: rgba(255, 255, 255, 0.88)");
    expect(surface).toContain("box-shadow:");
    expect(active).toContain("transform: scale(0.94)");
    expect(ruleFrom(
      componentsCss,
      'html[data-theme="dark"] .mf-header-actions > .mf-icon-button.mf-header-profile-button',
    )).toContain("color: #fff");
    expect(componentsCss).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.mf-header-profile-button::before\s*\{[^}]*transition: none/);
    expect(neutralCss).toContain(
      ".mf-header-actions > .mf-icon-button:not(.mf-header-profile-button)",
    );
  });

  it("uses a compact light wordmark with gold-only details on the navy canvas", () => {
    const mark = rule(".mf-brand--friulora .mf-brand-mark");
    const title = rule(".mf-brand--friulora .mf-brand-title");
    const visual = rule(".mf-brand-title__visual");
    const meteo = rule(".mf-brand-title__meteo");
    const friul = rule(".mf-brand-title__friul");
    const circumflex = rule(".mf-brand-title__circumflex");
    const underline = rule(".mf-brand-title__underline");

    expect(mark).toContain("flex-basis: 40px");
    expect(mark).toContain("height: 40px");
    expect(mark).toContain("border-radius: 10px");
    expect(title).toContain("color: var(--mf-shell-ink)");
    expect(title).toContain("font-size: clamp(1.0625rem, 4.3vw, 1.25rem)");
    expect(title).toContain("font-weight: 900");
    expect(title).toContain("letter-spacing: 0.015em");
    expect(title).toContain("padding-bottom: 10px");
    expect(visual).toContain("background: transparent");
    expect(visual).toContain("color: inherit");
    expect(meteo).toContain("font-weight: 800");
    expect(friul).toContain("color: inherit");
    expect(friul).toContain("font-weight: 900");
    expect(circumflex).toContain("color: var(--mf-gold)");
    expect(circumflex).toContain("fill: none");
    expect(circumflex).toContain("stroke: currentColor");
    expect(circumflex).toContain("stroke-width: 2.2");
    expect(underline).toContain("color: var(--mf-gold)");
    expect(underline).toContain("fill: currentColor");
    expect(underline).toContain("height: 7px");
  });

  it("uses theme text and gold-detail tokens in dark mode with a restrained subtitle", () => {
    const tagline = rule(".mf-brand--friulora .mf-brand-tagline");
    const darkTitle = rule('html[data-theme="dark"] .mf-brand--friulora .mf-brand-title');
    const darkTagline = rule('html[data-theme="dark"] .mf-brand--friulora .mf-brand-tagline');

    expect(tagline).toContain("font-size: 0.75rem");
    expect(tagline).toContain("font-weight: 500");
    expect(tagline).toContain("color: var(--mf-shell-muted)");
    expect(darkTitle).toContain("color: var(--mf-shell-ink)");
    expect(darkTagline).toContain("color: var(--mf-shell-muted)");
  });

  it("keeps shell colors in the header and uses content colors below it", () => {
    const definitiveBody = ruleFrom(
      neutralCss,
      'html:not([data-theme="dark"]) body:has(.mf-app-shell.is-definitive-app)',
    );
    const definitiveHeader = ruleFrom(
      neutralCss,
      'html:not([data-theme="dark"]) .mf-app-shell.is-definitive-app .mf-app-header',
    );
    const headerBackdrop = ruleFrom(
      neutralCss,
      'html:not([data-theme="dark"]) .mf-app-shell.is-definitive-app .mf-app-header::before',
    );

    expect(rule(".mf-brand--friulora .mf-brand-title")).toContain("color: var(--mf-shell-ink)");
    expect(rule(".mf-brand--friulora .mf-brand-tagline")).toContain("color: var(--mf-shell-muted)");
    expect(definitiveBody).toContain("background: linear-gradient(var(--mf-paper), var(--mf-paper))");
    expect(definitiveHeader).toContain("isolation: isolate");
    expect(definitiveHeader).toContain("position: relative");
    expect(headerBackdrop).toContain("background: var(--mf-definitive-gradient)");
    expect(headerBackdrop).toContain("bottom: 0");
    expect(headerBackdrop).toContain("top: calc(-1 * max(var(--mf-safe-area-inset-top), var(--mf-space-4)))");
    expect(headerBackdrop).toContain("width: 100vw");
    expect(headerBackdrop).toContain("pointer-events: none");
    expect(neutralCss).not.toContain("--mf-definitive-header-fade");
    expect(neutralCss).not.toContain("--mf-definitive-header-edge");
    expect(rule(".mf-tab-page h1")).toContain("color: var(--mf-page-ink)");
    expect(rule(".mf-location-context")).toContain("color: var(--mf-page-muted)");
    expect(rule(".mf-location-context svg")).toContain("color: var(--mf-page-accent)");
    expect(rule(".mf-location-context__text strong")).toContain("color: var(--mf-page-ink)");
    expect(rule('html:not([data-theme="dark"]) .mf-bottom-nav')).toContain("background: #fff");
  });

  it("floats the definitive Android navigation above the page background", () => {
    const nativeShell = rule(".mf-app-shell.is-native-android.is-definitive-app");
    const nativeStrip = rule(
      ".mf-app-shell.is-native-android.is-definitive-app::after",
    );
    const nativeMain = rule(
      ".mf-app-shell.is-native-android.is-definitive-app .mf-app-main",
    );
    const nativeNavigation = rule(
      ".mf-app-shell.is-native-android.is-definitive-app .mf-bottom-nav",
    );

    expect(nativeShell).toContain("--mf-native-bottom-nav-clearance: calc(");
    expect(nativeShell).toContain("grid-template-rows: auto minmax(0, 1fr)");
    expect(nativeShell).toContain("padding-bottom: 0");
    expect(nativeShell).toContain("position: relative");
    expect(nativeStrip).toContain("background: var(--mf-native-navigation-strip)");
    expect(nativeStrip).toContain("height: var(--mf-safe-area-inset-bottom)");
    expect(nativeStrip).toContain("width: 100vw");
    expect(nativeMain).toContain(
      "padding-bottom: var(--mf-native-bottom-nav-clearance)",
    );
    expect(nativeNavigation).toContain(
      "bottom: calc(var(--mf-safe-area-inset-bottom) + var(--mf-space-3))",
    );
    expect(nativeNavigation).toContain("position: absolute");
    const navigationLayer = Number(nativeNavigation.match(/z-index:\s*(\d+)/)?.[1]);
    const eventLinkLayer = Number(ruleFrom(eventsCss, ".mf-events-card__link").match(/z-index:\s*(\d+)/)?.[1]);
    const eventPreviewLayer = Number(ruleFrom(eventsCss, ".mf-event-preview").match(/z-index:\s*(\d+)/)?.[1]);
    expect(navigationLayer).toBeGreaterThan(eventLinkLayer);
    expect(navigationLayer).toBeLessThan(eventPreviewLayer);
  });

  it("floats the Web/PWA navigation on mobile without changing Android", () => {
    const webShell = rule(".mf-app-shell.is-definitive-app:not(.is-native-android)");
    const webMain = rule(".mf-app-shell.is-definitive-app:not(.is-native-android) .mf-app-main");
    const webNavigation = rule(".mf-app-shell.is-definitive-app:not(.is-native-android) .mf-bottom-nav");

    expect(css).toContain("@media (max-width: 719px)");
    expect(webShell).toContain("grid-template-rows: auto minmax(0, 1fr)");
    expect(webShell).toContain("padding-bottom: 0");
    expect(webMain).toContain("padding-bottom: var(--mf-web-bottom-nav-clearance)");
    expect(webNavigation).toContain("position: absolute");
    expect(webNavigation).toContain("z-index: 20");
    expect(css).toMatch(/@media \(min-width: 720px\)[\s\S]*?\.mf-app-shell\.is-definitive-app:not\(\.is-native-android\)\s*\{\s*padding-top: var\(--mf-space-4\)/);
  });

  it("gives route location headers one shared geometry without extra top clearance", () => {
    const routeLocation = rule(".mf-route-location-context");

    expect(routeLocation).toContain("min-height: 26px");
    expect(routeLocation).toContain("padding: 2px 2px 0");
    expect(css).not.toContain(".mf-app-main .mf-route-location-context");
  });

  it("keeps inactive bottom-navigation icons legible in dark mode", () => {
    const inactiveIcon = rule(
      'html[data-theme="dark"] .mf-bottom-nav-item:not(.is-active) svg',
    );

    expect(inactiveIcon).toContain("color: #94a3b8");
  });

  it("restores the approved navy selection colors across the definitive app", () => {
    expect(neutralCss).toContain(".mf-app-shell.is-definitive-app");
    expect(neutralCss).toContain(".mf-bottom-nav-item.is-active");
    expect(neutralCss).toContain("background: var(--mf-definitive-gradient)");
    expect(neutralCss).toContain("border-color: rgb(142 219 255 / 45%)");
    expect(neutralCss).toContain("color: #fff");
    expect(neutralCss).toContain("background: var(--mf-definitive-badge)");
  });

  it("lets light forecasts own their selection instead of inheriting navy navigation", () => {
    const navySelections = neutralCss.match(/html:not\(\[data-theme="dark"\]\) \.mf-app-shell\.is-definitive-app :is\(([^)]+)\)/)?.[1];
    expect(navySelections).toContain(".mf-bottom-nav-item.is-active");
    expect(navySelections).not.toContain(".mf-weather-day-picker");
  });

  it("anchors alert and count badges to opposite corners of the navigation icon", () => {
    const icon = rule(".mf-bottom-nav-item .mf-bottom-nav-item__icon");
    const count = rule(".mf-bottom-nav-item .mf-bottom-nav-count-badge");
    const eventBadge = rule(".mf-bottom-nav-item .mf-bottom-nav-event-badge");
    const communityBadge = rule(".mf-bottom-nav-item .mf-bottom-nav-community-badge");
    const alertBadge = rule(".mf-bottom-nav-alert-badge");
    const alertDot = rule(".mf-bottom-nav-alert-badge::before");

    expect(icon).toContain("height: 24px");
    expect(icon).toContain("width: 24px");
    expect(icon).toContain("overflow: visible");
    expect(count).toContain("border: 1.5px solid var(--mf-nav-bg)");
    expect(count).toContain("bottom: -2px");
    expect(count).toContain("right: -7px");
    expect(count).toContain("height: 14px");
    expect(count).toContain("padding: 0 3px");
    expect(eventBadge).toContain("background: #059669");
    expect(communityBadge).toContain("background: #0284c7");
    expect(alertBadge).toContain("height: 24px");
    expect(alertBadge).toContain("left: calc(50% + 4px)");
    expect(alertBadge).toContain("top: -8px");
    expect(alertBadge).toContain("width: 24px");
    expect(alertDot).toContain("height: 8px");
    expect(alertDot).toContain("width: 8px");
    expect(css).not.toContain("has-event-badge");
    expect(css).not.toContain("mf-bottom-nav-item__label");
  });

  it("keeps the pilot wordmark readable in constrained headers", () => {
    expect(css).toMatch(/@media \(max-width: 420px\)[\s\S]*?\.mf-app-header\s*\{[^}]*flex-wrap: wrap/);
    expect(css).toMatch(/@media \(max-width: 420px\)[\s\S]*?\.mf-brand--friulora \.mf-brand-title\s*\{[^}]*font-size: clamp\(0\.92rem, 5\.4vw, 1\.0625rem\)/);
    expect(css).toMatch(/@media \(max-width: 420px\)[\s\S]*?\.mf-brand--friulora \.mf-brand-tagline\s*\{[^}]*font-size: clamp\(0\.67rem, 3\.8vw, 0\.75rem\)/);
    expect(css).toMatch(/@media \(max-width: 260px\)[\s\S]*?\.mf-app-header\s*\{[^}]*flex-wrap: wrap/);
    expect(css).toMatch(/@media \(max-width: 260px\)[\s\S]*?\.mf-brand--friulora\s*\{[^}]*flex-basis: 100%/);
  });
});
