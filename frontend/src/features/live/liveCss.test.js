import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

describe("live report disabled controls", () => {
  it("makes the definitive map alias prominent without truncating long names", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const status = css.match(/\.mf-live-community-map-layer--pilot \.mf-territory-map__report-community-status\s*\{([^}]+)\}/)?.[1] || "";
    const identities = css.match(/\.mf-live-community-map-layer--pilot \.mf-territory-map__report-community-identities\s*\{([^}]+)\}/)?.[1] || "";
    const summary = css.match(/\.mf-live-community-map-layer--pilot \.mf-territory-map__report-community-summary\s*\{([^}]+)\}/)?.[1] || "";

    expect(status).toContain("font-size: 0.82rem");
    expect(identities).toContain("font-size: 0.82rem");
    expect(summary).toContain("font-size: 1rem");
    expect(summary).toContain("white-space: normal");
    expect(summary).toContain("overflow-wrap: anywhere");
  });

  it("keeps pilot votes aligned on one line and removes the identity-only divider", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const compactButton = css.match(/\.mf-live-community-map-layer--inline \.mf-territory-map__report-detail--pilot \.mf-live-community-map__confirm--compact \.mf-live-community-map__confirm-button\s*\{([^}]+)\}/)?.[1] || "";
    const compactLabel = css.match(/\.mf-live-community-map-layer--inline \.mf-territory-map__report-detail--pilot \.mf-live-community-map__confirm--compact \.mf-live-community-map__confirm-label\s*\{([^}]+)\}/)?.[1] || "";
    const identity = css.match(/\.mf-territory-map__report-community-status--identity-only \.mf-territory-map__report-community-identities\s*\{([^}]+)\}/)?.[1] || "";
    const singleIdentity = css.match(/\.mf-territory-map__report-community-identities--single \.mf-territory-map__report-community-single\s*\{([^}]+)\}/)?.[1] || "";
    expect(compactButton).toContain("grid-template-columns: 16px minmax(0, 1fr) auto");
    expect(compactButton).toContain("min-height: 46px");
    expect(compactButton).toContain("font-weight: 650");
    expect(compactLabel).toContain("white-space: nowrap");
    expect(identity).toContain("grid-column: 1");
    expect(identity).toContain("border-top: 0");
    expect(identity).toContain("padding-top: 0");
    expect(singleIdentity).toContain("margin-left: 0");
    expect(singleIdentity).toContain("border: 0");
    expect(singleIdentity).toContain("background: transparent");
  });

  it("scopes aligned management and compact sharing to the pilot presentation", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const actions = css.match(/\.mf-live-community-own-report--compact \.mf-live-community-own-report__update,\s*\.mf-live-community-own-report--compact \.mf-live-community-own-report__withdraw\s*\{([^}]+)\}/)?.[1] || "";
    const sharing = css.match(/\.mf-territory-map__report-share\.mf-icon-button\s*\{([^}]+)\}/)?.[1] || "";
    const identity = css.match(/^\.mf-territory-map__report-community-single\s*\{([^}]+)\}/m)?.[1] || "";

    expect(actions).toContain("width: 100%");
    expect(actions).toContain("min-height: 48px");
    expect(actions).toContain("text-align: center");
    expect(actions).toContain("justify-content: center");
    expect(sharing).toContain("width: 40px");
    expect(sharing).toContain("height: 40px");
    expect(sharing).toContain("border: 0");
    expect(sharing).toContain("background: transparent");
    expect(identity).toContain("display: inline-flex");
    expect(identity).toContain("border-radius: 999px");
    expect(css).toContain('html[data-theme="dark"] .mf-live-community-own-report--compact .mf-live-community-own-report__choice');
    expect(css).toContain(".mf-live-community-own-report--compact button:focus-visible");
  });

  it("balances the pilot identity, action contents and ownership summary", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const summary = css.match(/\.mf-live-community-own-report--compact \.mf-live-community-own-report__summary\s*\{([^}]+)\}/)?.[1] || "";
    const identity = css.match(/\.mf-territory-map__report-community-status--identity-only \.mf-territory-map__report-community-identities--single\s*\{([^}]+)\}/)?.[1] || "";
    const update = css.match(/\.mf-live-community-own-report--compact \.mf-live-community-own-report__update\s*\{([^}]+)\}/)?.[1] || "";
    expect(summary).toContain("display: flex");
    expect(summary).toContain("justify-content: space-between");
    expect(summary).toContain("flex-wrap: wrap");
    expect(identity).toContain("display: flex");
    expect(identity).toContain("justify-content: flex-start");
    expect(identity).toContain("gap: 10px");
    expect(update).toContain("grid-template-columns: auto minmax(0, max-content)");
  });

  it("centers the icon and text together inside full-width compact management choices", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const choice = css.match(/^\.mf-live-community-own-report--compact \.mf-live-community-own-report__choice\s*\{([^}]+)\}/m)?.[1] || "";
    const icon = css.match(/^\.mf-live-community-own-report--compact \.mf-live-community-own-report__choice svg\s*\{([^}]+)\}/m)?.[1] || "";

    expect(choice).toContain("display: flex");
    expect(choice).toContain("align-items: center");
    expect(choice).toContain("justify-content: center");
    expect(choice).toContain("text-align: center");
    expect(choice).toContain("width: 100%");
    expect(icon).toContain("flex: 0 0 auto");
  });

  it.each([
    ".mf-live-report-form--sheet .mf-live-report-form__header span",
    ".mf-live-report-form__header span",
    ".mf-live-report-option strong",
    ".mf-live-report-location__copy small",
    ".mf-live-report-location__copy strong",
    ".mf-live-report-location__selector > span",
    ".mf-live-report-location__selector select",
    ".mf-live-report-location__selector small",
    ".mf-live-report-terms legend",
    ".mf-live-report-terms p",
    ".mf-live-report-terms summary",
    ".mf-live-report-terms label",
    ".mf-live-report-meta",
    ".mf-live-report-meta strong",
    ".mf-live-report-form .mf-live-note",
    ".mf-live-report-match strong",
    ".mf-live-report-match small",
    ".mf-live-report-success > span:not(.mf-live-report-success__icon)",
    ".mf-live-report-success small",
  ])("uses the readable small-text token inside Segnala: %s", (selector) => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const rule = css.match(new RegExp(`^${escapedSelector}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";

    expect(rule).toContain("font-size: var(--mf-text-sm)");
  });

  it("lets a report location wrap instead of truncating its larger text", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const rule = css.match(/\.mf-live-report-location__copy strong\s*\{([^}]+)\}/)?.[1] || "";

    expect(rule).toContain("overflow-wrap: anywhere");
    expect(rule).not.toContain("white-space: nowrap");
    expect(rule).not.toContain("text-overflow: ellipsis");
  });

  it("gives the disabled submit button an explicit muted appearance", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const rule = css.match(/\.mf-live-report-submit:disabled\s*\{([^}]+)\}/)?.[1] || "";

    expect(rule).toContain("box-shadow: none");
    expect(rule).toContain("background:");
    expect(rule).toContain("opacity:");
  });

  it("presents pilot duration as a compact badge and the emergency note as quiet footer copy", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const durationRule = css.match(/\.mf-live-report-duration\s*\{([^}]+)\}/)?.[1] || "";
    const safetyRule = css.match(/\.mf-live-report-safety\s*\{([^}]+)\}/)?.[1] || "";

    expect(durationRule).toContain("display: inline-flex");
    expect(durationRule).toContain("align-items: center");
    expect(durationRule).toContain("border-radius: 999px");
    expect(durationRule).toContain("font-size: 11px");
    expect(safetyRule).toContain("color: var(--mf-muted)");
    expect(safetyRule).toContain("font-size: 11px");
    expect(safetyRule).toContain("text-align: center");
  });

  it("styles the pilot success summary as a compact receipt with an inline identity", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const pilotReceiptRule = css.match(
      /\.mf-live-report-success--pilot-receipt\s*\{([^}]+)\}/,
    )?.[1] || "";
    const titleRule = css.match(/\.mf-live-report-success__title\s*\{([^}]+)\}/)?.[1] || "";
    const summaryRule = css.match(/\.mf-live-report-success__summary\s*\{([^}]+)\}/)?.[1] || "";
    const summaryRowRule = css.match(
      /\.mf-live-report-success__summary-row\s*\{([^}]+)\}/,
    )?.[1] || "";
    const phenomenonRule = css.match(
      /\.mf-live-report-success__phenomenon\s*\{([^}]+)\}/,
    )?.[1] || "";
    const phenomenonLabelRule = css.match(
      /\.mf-live-report-success__phenomenon strong\s*\{([^}]+)\}/,
    )?.[1] || "";
    const expiryRule = css.match(
      /\.mf-live-report-success__expiry\s*\{([^}]+)\}/,
    )?.[1] || "";
    const placeRule = css.match(
      /\.mf-live-report-success__place\s*\{([^}]+)\}/,
    )?.[1] || "";
    const identityLabelRule = css.match(
      /\.mf-live-report-success__identity-label\s*\{([^}]+)\}/,
    )?.[1] || "";
    const identityInlineRule = css.match(
      /\.mf-live-report-success__identity-inline\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(pilotReceiptRule).toContain("min-height: 0");
    expect(pilotReceiptRule).toContain("width: 100%");
    expect(css).not.toContain(".mf-live-report-form--pilot .mf-live-report-success {");
    expect(titleRule).toContain("font-size: 18px");
    expect(titleRule).toContain("font-weight: 700");
    expect(summaryRule).toContain("display: grid");
    expect(summaryRule).toContain("border: 1px solid var(--mf-neutral-border)");
    expect(summaryRule).toContain("border-radius: 12px");
    expect(summaryRule).toContain("text-align: center");
    expect(summaryRowRule).toContain("display: flex");
    expect(summaryRowRule).toContain("justify-content: center");
    expect(phenomenonRule).toContain("display: flex");
    expect(phenomenonRule).toContain("align-items: center");
    expect(phenomenonLabelRule).toContain("font-size: 16px");
    expect(expiryRule).toContain("font-size: 14px");
    expect(placeRule).toContain("font-size: 14px");
    expect(identityLabelRule).toContain("font-size: 14px");
    expect(identityInlineRule).toContain("justify-content: center");
    expect(identityInlineRule).toContain("font-size: 14px");
    expect(identityInlineRule).toContain("border: 0");
    expect(identityInlineRule).toContain("background: transparent");
    expect(identityInlineRule).toContain("box-shadow: none");
  });

  it("keeps the pilot receipt balanced with a visually light close action", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const header = css.match(/\.mf-live-report-form--receipt \.mf-live-report-form__header\s*\{([^}]+)\}/)?.[1] || "";
    const close = css.match(/\.mf-live-report-form--receipt \.mf-live-report-form__header \.mf-icon-button\s*\{([^}]+)\}/)?.[1] || "";
    const description = css.match(/\.mf-live-report-success__description\s*\{([^}]+)\}/)?.[1] || "";
    const identity = css.match(/\.mf-live-report-success__identity-block\s*\{([^}]+)\}/)?.[1] || "";
    const footer = css.match(/\.mf-live-report-form--receipt \.mf-live-report-form__footer\s*\{([^}]+)\}/)?.[1] || "";
    const mapAction = css.match(/\.mf-live-report-form--receipt \.mf-live-report-map-action\s*\{([^}]+)\}/)?.[1] || "";
    expect(header).toContain("position: absolute");
    expect(header).toContain("right: 4px");
    expect(header).toContain("border: 0");
    expect(close).toContain("width: 44px");
    expect(close).toContain("border: 0");
    expect(close).toContain("background: transparent");
    expect(description).toContain("text-align: center");
    expect(description).toContain("max-width: 42ch");
    expect(identity).toContain("display: flex");
    expect(identity).toContain("flex-wrap: wrap");
    expect(identity).toContain("border: 0");
    expect(footer).toContain("padding: 20px 18px 18px");
    expect(footer).toContain("border-top: 0");
    expect(mapAction).toContain("padding: 12px 24px");
    expect(mapAction).toContain("border-radius: 12px");
  });

  it("distinguishes pilot update, withdrawal, success and retry actions", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const stableActionRule = css.match(
      /\.mf-live-community-own-report--pilot \.mf-live-community-own-report__update,\s*\.mf-live-community-own-report--pilot \.mf-live-community-own-report__withdraw\s*\{([^}]+)\}/,
    )?.[1] || "";
    const updateRule = css.match(
      /\.mf-live-community-own-report--pilot \.mf-live-community-own-report__update\s*\{([^}]+)\}/,
    )?.[1] || "";
    const withdrawRule = [...css.matchAll(
      /\.mf-live-community-own-report--pilot \.mf-live-community-own-report__withdraw\s*\{([^}]+)\}/g,
    )].map((match) => match[1]).find((rule) => rule.includes("background:")) || "";
    const successRule = css.match(
      /\.mf-live-community-own-report--pilot \.mf-live-community-own-report__update\.is-success\s*\{([^}]+)\}/,
    )?.[1] || "";
    const errorRule = css.match(
      /\.mf-live-community-own-report--pilot \.mf-live-community-own-report__update\.is-error\s*\{([^}]+)\}/,
    )?.[1] || "";
    const labelRule = css.match(
      /\.mf-live-community-own-report--pilot \.mf-live-community-own-report__update-label\s*\{([^}]+)\}/,
    )?.[1] || "";
    const hintRule = css.match(
      /\.mf-live-community-own-report--pilot \.mf-live-community-own-report__update-hint\s*\{([^}]+)\}/,
    )?.[1] || "";
    const announcementRule = css.match(
      /\.mf-live-community-own-report__update-announcement\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(stableActionRule).toContain("width: min(100%, 240px)");
    expect(stableActionRule).toContain("min-height: 54px");
    expect(updateRule).toContain("background: #e0f2fe");
    expect(updateRule).toContain("color:");
    expect(withdrawRule).toContain("background:");
    expect(withdrawRule).toContain("border-color:");
    expect(withdrawRule).toContain("color:");
    expect(withdrawRule).not.toBe(updateRule);
    expect(successRule).toContain("background:");
    expect(successRule).toContain("border-color:");
    expect(successRule).toContain("color:");
    expect(errorRule).toContain("background:");
    expect(errorRule).toContain("border-color:");
    expect(errorRule).toContain("color:");
    expect(successRule).not.toBe(errorRule);
    expect(labelRule).toContain("grid-area: label");
    expect(labelRule).toContain("line-height:");
    expect(hintRule).toContain("grid-area: hint");
    expect(hintRule).toContain("font-size:");
    expect(announcementRule).toContain("position: absolute");
    expect(announcementRule).toContain("clip:");
  });

  it("keeps the report sheet fixed while only its middle section scrolls", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const layerRule = css.match(/\.mf-live-report-layer\s*\{([^}]+)\}/)?.[1] || "";
    const bodyRule = css.match(
      /\.mf-live-report-form--sheet \.mf-live-report-form__body\s*\{([^}]+)\}/,
    )?.[1] || "";
    const footerRule = css.match(
      /\.mf-live-report-form--sheet \.mf-live-report-form__footer\s*\{([^}]+)\}/,
    )?.[1] || "";
    const handleRule = css.match(
      /\.mf-live-report-form--sheet \.mf-live-report-form__header::before\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(css).toContain("html.mf-community-report-open .mf-app-main");
    expect(layerRule).toContain("align-items: center");
    expect(layerRule).toContain("safe-area-inset-top");
    expect(layerRule).toContain("safe-area-inset-right");
    expect(layerRule).toContain("safe-area-inset-bottom");
    expect(layerRule).toContain("safe-area-inset-left");
    expect(css).toContain("max-height: min(760px, 100%)");
    expect(css).toContain("var(--mf-safe-area-inset-bottom)");
    expect(bodyRule).toContain("overflow: hidden auto");
    expect(bodyRule).toContain("overscroll-behavior: contain");
    expect(footerRule).toContain("border-top:");
    expect(footerRule).not.toContain("safe-area-inset-bottom");
    expect(handleRule).toContain("display: none");
    expect(css).toContain("max(20px, var(--mf-safe-area-inset-right))");
    expect(css).toContain("max(20px, var(--mf-safe-area-inset-left))");
  });

  it("keeps the ordinary community map compact and makes only the pilot layer immersive", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const mapRule = css.match(/\.mf-live-community-map\s*\{([^}]+)\}/)?.[1] || "";
    const pilotLayerRule = css.match(
      /\.mf-live-community-map-layer--pilot\s*\{([^}]+)\}/,
    )?.[1] || "";
    const immersiveMapRule = css.match(
      /\.mf-live-community-map--immersive\s*\{([^}]+)\}/,
    )?.[1] || "";
    const pilotToolbarRule = css.match(
      /\.mf-live-community-map-layer--pilot \.mf-live-community-map-layer__toolbar\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(mapRule).toContain("height: 220px");
    expect(pilotLayerRule).toContain("position: fixed");
    expect(pilotLayerRule).toContain("inset: 0");
    expect(pilotLayerRule).toContain("overflow: hidden");
    expect(pilotLayerRule).toContain("z-index:");
    expect(immersiveMapRule).toContain("height: 100%");
    expect(immersiveMapRule).toContain("border-radius: 0");
    expect(pilotToolbarRule).toContain("width: fit-content");
    expect(pilotToolbarRule).toContain("border-radius: 999px");
    expect(pilotToolbarRule).toContain("background: var(--mf-neutral-surface)");
    expect(pilotToolbarRule).toContain("border: 1px solid var(--mf-neutral-border)");
  });

  it("presents immersive marker details as a bottom sheet without a visible system scrollbar", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const detailRule = css.match(
      /\.mf-live-community-map--immersive \.mf-live-community-map__detail\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(detailRule).toContain("right: 0");
    expect(detailRule).toContain("bottom: 0");
    expect(detailRule).toContain("left: 0");
    expect(detailRule).toContain("overflow-y: auto");
    expect(detailRule).toContain("scrollbar-width: none");
    expect(detailRule).toContain("touch-action: pan-y");
    expect(detailRule).toContain("background: var(--mf-neutral-surface)");
    expect(detailRule).toContain("border-radius: 24px 24px 0 0");
    expect(css).toMatch(
      /\.mf-live-community-map--immersive \.mf-live-community-map__detail-grabber\s*\{[^}]*touch-action:\s*none/,
    );
    expect(detailRule).toMatch(/border-radius:\s*(?:1[6-9]|[2-9]\d)px\s+(?:1[6-9]|[2-9]\d)px\s+0\s+0/);
    expect(css).toMatch(
      /\.mf-live-community-map--immersive \.mf-live-community-map__detail::-webkit-scrollbar\s*\{[^}]*display:\s*none/,
    );
    expect(css).toMatch(
      /\.mf-live-community-map--immersive \.mf-live-community-map__confirm-button:not\(\.mf-live-community-map__confirm-button--no\)\s*\{[^}]*var\(--mf-blue-050\)[^}]*color:\s*var\(--mf-blue-700\)/,
    );
    expect(css).toMatch(
      /\.mf-live-community-map--immersive \.mf-live-community-map__confirm-button--no\[aria-pressed="true"\]\s*\{[^}]*background:\s*#475569[^}]*color:\s*#fff/,
    );
  });

  it("keeps the pilot Territory map inline and presents report details as a vertical card", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const fittedMainRule = css.match(
      /\.mf-app-main--territory-fit\s*\{([^}]+)\}/,
    )?.[1] || "";
    const nativeFittedMainRule = css.match(
      /\.mf-app-shell\.is-native-android\.is-definitive-app \.mf-app-main--territory-fit\s*\{([^}]+)\}/,
    )?.[1] || "";
    const webFittedMainRule = css.match(
      /\.mf-app-shell\.is-definitive-app:not\(\.is-native-android\) \.mf-app-main--territory-fit\s*\{([^}]+)\}/,
    )?.[1] || "";
    const fittedShellRule = css.match(
      /\.mf-app-main--territory-fit > \.mf-weather-route-shell\s*\{([^}]+)\}/,
    )?.[1] || "";
    const nativeFittedShellRule = css.match(
      /\.mf-app-shell\.is-native-android\.is-definitive-app\s+\.mf-app-main--territory-fit > \.mf-weather-route-shell\s*\{([^}]+)\}/,
    )?.[1] || "";
    const webFittedShellRule = css.match(
      /\.mf-app-shell\.is-definitive-app:not\(\.is-native-android\)\s+\.mf-app-main--territory-fit > \.mf-weather-route-shell\s*\{([^}]+)\}/,
    )?.[1] || "";
    const fittedWorkspaceRule = css.match(
      /\.mf-app-main--territory-fit\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s*\{([^}]+)\}/,
    )?.[1] || "";
    const inlineLayerRule = css.match(
      /^\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const inlineMapRule = [...css.matchAll(
      /^\.mf-live-community-map-layer--inline \.mf-territory-map--inline\s*\{([^}]+)\}/gm,
    )].map((match) => match[1]).find((rule) => (
      rule.includes("--mf-territory-map-dock-height")
    )) || "";
    const dockRule = css.match(
      /\.mf-live-community-map-layer--inline \.mf-territory-map__dock\s*\{([^}]+)\}/,
    )?.[1] || "";
    const radarActiveRule = css.match(
      /\.mf-live-community-map-layer--inline \.mf-territory-map--radar-active\s*\{([^}]+)\}/,
    )?.[1] || "";
    const radarStatusRule = css.match(
      /\.mf-live-community-map-layer--inline\s+\.mf-territory-map--radar-active:has\(\.mf-territory-radar-statuses\)\s*\{([^}]+)\}/,
    )?.[1] || "";
    const radarDoubleStatusRule = css.match(
      /\.mf-live-community-map-layer--inline\s+\.mf-territory-map--radar-active:has\(\s*\.mf-territory-radar-status \+ \.mf-territory-radar-status\s*\)\s*\{([^}]+)\}/,
    )?.[1] || "";
    const radarDockRule = css.match(
      /\.mf-live-community-map-layer--inline \.mf-territory-map__dock--radar\s*\{([^}]+)\}/,
    )?.[1] || "";
    const radarDockNavigationRule = css.match(
      /\.mf-live-community-map-layer--inline\s+\.mf-territory-map__dock--radar\s+\.mf-territory-map__navigation\s*\{([^}]+)\}/,
    )?.[1] || "";
    const detailLayerRule = css.match(
      /\.mf-live-community-map-layer--inline \.mf-territory-map__detail-layer\s*\{([^}]+)\}/,
    )?.[1] || "";
    const detailRule = css.match(
      /\.mf-live-community-map-layer--inline \.mf-territory-map \.mf-live-community-map__detail\.mf-territory-map__report-detail\s*\{([^}]+)\}/,
    )?.[1] || "";
    const reportActionRule = css.match(
      /\.mf-territory-map__report-action\s*\{([^}]+)\}/,
    )?.[1] || "";
    const reportUnavailableRule = css.match(
      /\.mf-territory-map__report-unavailable\s*\{([^}]+)\}/,
    )?.[1] || "";
    const fittedPageRule = css.match(
      /\.mf-app-main--territory-fit \.mf-tab-page--live\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(fittedMainRule).toContain("overflow-y: auto");
    expect(fittedMainRule).toContain("padding-bottom: 0");
    expect(nativeFittedMainRule).toContain("padding-bottom: var(--mf-native-bottom-nav-clearance)");
    expect(webFittedMainRule).toContain("padding-bottom: var(--mf-web-bottom-nav-clearance)");
    expect(fittedShellRule).toContain("grid-template-rows: auto auto minmax(0, 1fr)");
    expect(fittedShellRule).toContain("height: 100%");
    expect(fittedShellRule).toContain("min-height: 620px");
    expect(nativeFittedShellRule).toContain("min-height: 0");
    expect(webFittedShellRule).toContain("min-height: 0");
    expect(fittedPageRule).toContain("padding-bottom: 0");
    expect(fittedWorkspaceRule).toContain("height: 100%");
    expect(inlineLayerRule).toContain("position: relative");
    expect(inlineLayerRule).toContain("height: clamp(");
    expect(inlineLayerRule).toContain("border-radius: 20px");
    expect(inlineLayerRule).not.toContain("position: fixed");
    expect(inlineMapRule).toContain("--mf-territory-map-dock-height:");
    expect(inlineMapRule).toContain("overflow: hidden");
    expect(dockRule).toContain("position: absolute");
    expect(dockRule).toContain("bottom: 0");
    expect(dockRule).toContain("display: grid");
    expect(radarActiveRule).toContain("--mf-territory-map-dock-height: 110px");
    expect(radarStatusRule).toContain("--mf-territory-map-dock-height: 132px");
    expect(radarDoubleStatusRule).toContain("--mf-territory-map-dock-height: 150px");
    expect(radarDockRule).toContain("grid-template-rows: 4px minmax(44px, 1fr) 48px");
    expect(radarDockRule).toContain("gap: 0");
    expect(radarDockRule).toContain("padding-block: 5px 8px");
    expect(radarDockNavigationRule).toContain("grid-row: 3");
    expect(reportActionRule).toContain("min-height: 48px");
    expect(reportActionRule).toMatch(/grid-row:\s*(?:4(?:\s*\/\s*5)?|-2\s*\/\s*-1)/);
    expect(reportUnavailableRule).toContain("grid-row: 4");
    expect(detailLayerRule).toContain("place-items: center");
    expect(detailRule).toContain("position: relative");
    expect(detailRule).toContain("width: min(360px, 100%)");
    expect(detailRule).toContain("border-radius: 22px");
    expect(detailRule).toContain("background: #fff");
  });

  it("keeps the Territory radar player on one compact row with an on-demand legend", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const rule = (pattern) => css.match(pattern)?.[1] || "";
    const overlay = rule(
      /\.mf-live-community-map-layer--pilot \.mf-territory-radar-overlay\s*\{([^}]+)\}/,
    );
    const player = rule(
      /\.mf-live-community-map-layer--pilot \.mf-territory-radar-player\s*\{([^}]+)\}/,
    );
    const play = rule(
      /\.mf-live-community-map-layer--pilot \.mf-territory-radar-play\s*\{([^}]+)\}/,
    );
    const timeline = rule(
      /\.mf-live-community-map-layer--pilot \.mf-territory-radar-timeline\s*\{([^}]+)\}/,
    );
    const info = rule(
      /\.mf-live-community-map-layer--pilot \.mf-territory-radar-info\s*\{([^}]+)\}/,
    );
    const scale = rule(
      /\.mf-live-community-map-layer--pilot \.mf-territory-radar-scale\s*\{([^}]+)\}/,
    );
    const radarAttribution = rule(
      /\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map--radar-active\s+\.leaflet-control-attribution\s*\{([^}]+)\}/,
    );
    const radarAttributionWithLegend = rule(
      /\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map--radar-active:has\(\.mf-territory-radar-info\[aria-expanded="true"\]\)\s+\.leaflet-control-attribution\s*\{([^}]+)\}/,
    );
    const inlineOverlay = rule(
      /\.mf-live-community-map-layer--inline\.mf-live-territory-workspace \.mf-territory-radar-overlay\s*\{([^}]+)\}/,
    );

    expect(overlay).toContain("position: relative");
    expect(overlay).toContain("inset: auto");
    expect(overlay).toContain("min-height: 44px");
    expect(overlay).toContain("padding: 4px 0 6px");
    expect(overlay).toContain("border-bottom: 1px solid rgba(0, 0, 0, 0.06)");
    expect(overlay).toContain("border-radius: 0");
    expect(overlay).toContain("background: transparent");
    expect(overlay).toContain("box-shadow: none");
    expect(overlay).toContain("backdrop-filter: none");
    expect(inlineOverlay).toContain("position: relative");
    expect(inlineOverlay).toContain("inset: auto");
    expect(inlineOverlay).toContain("animation: none");
    expect(inlineOverlay).not.toContain("bottom: 100%");
    expect(player).toContain("grid-template-columns: 32px minmax(72px, 1fr) auto 32px");
    expect(play).toContain("width: 32px");
    expect(play).toContain("height: 32px");
    expect(timeline).toContain("display: flex");
    expect(timeline).not.toContain("grid-template-areas");
    expect(info).toContain("width: 32px");
    expect(info).toContain("height: 32px");
    expect(scale).toContain("position: absolute");
    expect(scale).toContain("bottom: calc(100% + 14px)");
    expect(scale).toContain("width: min(220px, calc(100% - 12px))");
    expect(radarAttribution)
      .toContain("bottom: calc(var(--mf-territory-map-dock-height) + 4px)");
    expect(radarAttributionWithLegend)
      .toContain("bottom: calc(var(--mf-territory-map-dock-height) + 52px)");
  });

  it("gives the report CTA the same luminous treatment as the confirm action", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const reportActionRule = css.match(
      /\.mf-territory-map__report-action\s*\{([^}]+)\}/,
    )?.[1] || "";
    const reportActionInteractionRule = css.match(
      /\.mf-territory-map__report-action:hover,\s*\.mf-territory-map__report-action:focus-visible\s*\{([^}]+)\}/,
    )?.[1] || "";
    const reportActionFocusRule = [...css.matchAll(
      /\.mf-territory-map__report-action:focus-visible\s*\{([^}]+)\}/g,
    )].map((match) => match[1]).find((rule) => rule.includes("outline:")) || "";
    const confirmRule = css.match(
      /\.mf-live-community-map-layer--inline \.mf-territory-map__report-detail \.mf-live-community-map__confirm-button:not\(\.mf-live-community-map__confirm-button--no\)\s*\{([^}]+)\}/,
    )?.[1] || "";
    const sharedLuminousDeclarations = [
      "background: linear-gradient(135deg, #2563eb, #0284c7)",
      "border-top: 1.5px solid rgba(255, 255, 255, 0.4)",
      "box-shadow: 0 10px 24px -4px rgba(37, 99, 235, 0.45)",
    ];

    sharedLuminousDeclarations.forEach((declaration) => {
      expect(confirmRule).toContain(declaration);
      expect(reportActionRule).toContain(declaration);
    });
    expect(reportActionRule).toContain("color: #fff");
    expect(reportActionRule).toContain("transition:");
    expect(reportActionInteractionRule).toContain("transform: translateY(-1px)");
    expect(reportActionInteractionRule).toContain("box-shadow:");
    expect(reportActionFocusRule).toContain("outline: 3px solid");
    expect(reportActionFocusRule).toContain("outline-offset: 2px");
  });

  it("gives inline report details a luminous primary hierarchy and restrained secondary actions", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const headingRule = css.match(
      /\.mf-territory-map__report-primary-heading\s*\{([^}]+)\}/,
    )?.[1] || "";
    const headingCopyRule = css.match(
      /\.mf-territory-map__report-heading-copy\s*\{([^}]+)\}/,
    )?.[1] || "";
    const headingTitleRule = css.match(
      /\.mf-territory-map__report-heading-copy > strong\s*\{([^}]+)\}/,
    )?.[1] || "";
    const headingMetaRule = css.match(
      /\.mf-territory-map__report-heading-copy > small\s*\{([^}]+)\}/,
    )?.[1] || "";
    const typeIconRule = css.match(
      /\.mf-territory-map__report-type-icon\s*\{([^}]+)\}/,
    )?.[1] || "";
    const headingButtonRule = css.match(
      /\.mf-territory-map__report-heading-button\.mf-icon-button\s*\{([^}]+)\}/,
    )?.[1] || "";
    const headingActionsRule = css.match(
      /\.mf-territory-map__report-heading-actions\s*\{([^}]+)\}/,
    )?.[1] || "";
    const closeRule = css.match(
      /\.mf-territory-map__report-close\.mf-icon-button\s*\{([^}]+)\}/,
    )?.[1] || "";
    const liveBadgeRule = css.match(
      /\.mf-territory-map__report-community-status\s*\{([^}]+)\}/,
    )?.[1] || "";
    const liveIndicatorRule = css.match(
      /\.mf-territory-map__report-community-status-dot\s*\{([^}]+)\}/,
    )?.[1] || "";
    const identitiesRule = css.match(
      /\.mf-territory-map__report-community-identities\s*\{([^}]+)\}/,
    )?.[1] || "";
    const identityToggleRule = css.match(
      /\.mf-territory-map__report-community-toggle\s*\{([^}]+)\}/,
    )?.[1] || "";
    const avatarStackRule = css.match(
      /\.mf-territory-map__report-community-avatar-stack\s*\{([^}]+)\}/,
    )?.[1] || "";
    const avatarOverlapRule = css.match(
      /\.mf-territory-map__report-community-avatar-stack \.mf-community-avatar \+ \.mf-community-avatar\s*\{([^}]+)\}/,
    )?.[1] || "";
    const identitySummaryRule = css.match(
      /\.mf-territory-map__report-community-summary\s*\{([^}]+)\}/,
    )?.[1] || "";
    const identityListRule = css.match(
      /\.mf-territory-map__report-community-list\s*\{([^}]+)\}/,
    )?.[1] || "";
    const identityListItemRule = css.match(
      /\.mf-territory-map__report-community-list-item\s*\{([^}]+)\}/,
    )?.[1] || "";
    const darkIdentitiesRule = css.match(
      /html\[data-theme="dark"\] \.mf-territory-map__report-community-identities\s*\{([^}]+)\}/,
    )?.[1] || "";
    const hiddenSummaryRule = css.match(
      /\.mf-live-community-map-layer--inline \.mf-territory-map__report-detail \.mf-live-community-map__phenomenon--summary-hidden\s*\{([^}]+)\}/,
    )?.[1] || "";
    const confirmRule = css.match(
      /\.mf-live-community-map-layer--inline \.mf-territory-map__report-detail \.mf-live-community-map__confirm-button:not\(\.mf-live-community-map__confirm-button--no\)\s*\{([^}]+)\}/,
    )?.[1] || "";
    const denyRule = css.match(
      /\.mf-live-community-map-layer--inline \.mf-territory-map__report-detail \.mf-live-community-map__confirm-button--no\s*\{([^}]+)\}/,
    )?.[1] || "";
    const denyCountRule = css.match(
      /^\.mf-live-community-map__confirm-button--no \.mf-live-community-map__confirm-count\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const focusRule = css.match(
      /\.mf-live-community-map-layer--inline \.mf-territory-map__report-detail \.mf-live-community-map__confirm-button:focus-visible\s*\{([^}]+)\}/,
    )?.[1] || "";
    const darkDenyPressedRule = css.match(
      /html\[data-theme="dark"\] \.mf-live-community-map-layer--inline \.mf-territory-map__report-detail \.mf-live-community-map__confirm-button--no\[aria-pressed="true"\]\s*\{([^}]+)\}/,
    )?.[1] || "";
    const darkDenyCountRule = css.match(
      /html\[data-theme="dark"\] \.mf-live-community-map-layer--inline \.mf-territory-map__report-detail \.mf-live-community-map__confirm-button--no \.mf-live-community-map__confirm-count\s*\{([^}]+)\}/,
    )?.[1] || "";
    const countRule = css.match(
      /^\.mf-live-community-map__confirm-count\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const shareRule = css.match(
      /\.mf-territory-map__report-share\.mf-icon-button\s*\{([^}]+)\}/,
    )?.[1] || "";
    const shareFocusRule = css.match(
      /\.mf-territory-map__report-share\.mf-icon-button:hover,\s*\.mf-territory-map__report-share\.mf-icon-button:focus-visible\s*\{([^}]+)\}/,
    )?.[1] || "";
    const shareSuccessRule = css.match(
      /\.mf-territory-map__report-share\.mf-icon-button\.is-success\s*\{([^}]+)\}/,
    )?.[1] || "";
    const shareErrorRule = css.match(
      /\.mf-territory-map__report-share\.mf-icon-button\.is-error\s*\{([^}]+)\}/,
    )?.[1] || "";
    const shareStatusRule = css.match(
      /\.mf-territory-map__share-status\s*\{([^}]+)\}/,
    )?.[1] || "";
    const darkShareRule = css.match(
      /html\[data-theme="dark"\] \.mf-territory-map__report-share\.mf-icon-button\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(headingRule).toContain("grid-template-columns: auto minmax(0, 1fr) auto");
    expect(headingCopyRule).toContain("display: grid");
    expect(headingCopyRule).toContain("gap: 2px");
    expect(headingCopyRule).toContain("min-width: 0");
    expect(headingTitleRule).toContain("font-size: 1.12rem");
    expect(headingTitleRule).toContain("font-weight: 900");
    expect(headingTitleRule).toContain("-webkit-line-clamp: 2");
    expect(headingMetaRule).toContain("text-overflow: ellipsis");
    expect(typeIconRule).toContain("background: linear-gradient(");
    expect(typeIconRule).toContain("box-shadow:");
    expect(typeIconRule).toContain("color: #fff");
    expect(headingButtonRule).toContain("background: transparent");
    expect(headingButtonRule).toContain("box-shadow: none");
    expect(headingButtonRule).toContain("width: 40px");
    expect(headingButtonRule).toContain("height: 40px");
    expect(headingActionsRule).toContain("align-items: center");
    expect(headingActionsRule).toContain("gap: 12px");
    expect(closeRule).toContain("width: 40px");
    expect(closeRule).toContain("height: 40px");
    expect(closeRule).toContain("border: 0");
    expect(closeRule).toContain("background: transparent");
    expect(liveBadgeRule).toContain("border: 1px solid rgba(56, 189, 248, 0.2)");
    expect(liveBadgeRule).toContain("background: rgba(56, 189, 248, 0.08)");
    expect(liveBadgeRule).toContain("box-shadow: inset");
    expect(liveBadgeRule).toContain("grid-template-columns: auto minmax(0, 1fr)");
    expect(liveIndicatorRule).toContain("background: #22c55e");
    expect(liveIndicatorRule).toContain("0 0 8px #22c55e");
    expect(liveIndicatorRule).toContain("animation: mf-territory-report-live-pulse");
    expect(identitiesRule).toContain("grid-column: 2");
    expect(identitiesRule).toContain("border-top: 1px solid");
    expect(identitiesRule).toContain("grid-template-columns: auto minmax(0, 1fr)");
    expect(identityToggleRule).toContain("display: flex");
    expect(identityToggleRule).toContain("width: 100%");
    expect(avatarStackRule).toContain("display: inline-flex");
    expect(avatarOverlapRule).toContain("margin-left: -7px");
    expect(identitySummaryRule).toContain("text-overflow: ellipsis");
    expect(identitySummaryRule).toContain("white-space: nowrap");
    expect(identityListRule).toContain("grid-column: 2");
    expect(identityListRule).toContain("display: grid");
    expect(identityListItemRule).toContain("text-overflow: ellipsis");
    expect(darkIdentitiesRule).toContain("color: #cbd5e1");
    expect(css).not.toContain(".mf-territory-map__report-author");
    expect(css).not.toContain(".mf-territory-map__report-author-avatar");
    expect(hiddenSummaryRule).toContain("padding-top: 0");
    expect(hiddenSummaryRule).toContain("border-top: 0");
    expect(css).toMatch(/@keyframes mf-territory-report-live-pulse\s*\{/);
    expect(css).toMatch(
      /@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.mf-territory-map__report-community-status-dot\s*\{[^}]*animation:\s*none/,
    );
    expect(confirmRule).toMatch(
      /background:\s*linear-gradient\(135deg,\s*(?:#38bdf8|#2563eb),\s*(?:#1d4ed8|#0284c7)\)/i,
    );
    expect(confirmRule).toContain(
      "box-shadow: 0 10px 24px -4px rgba(37, 99, 235, 0.45)",
    );
    expect(confirmRule).toContain("color: #fff");
    expect(confirmRule).toContain(
      "border-top: 1.5px solid rgba(255, 255, 255, 0.4)",
    );
    expect(denyRule).toContain("border: 1.5px solid #cbd5e1");
    expect(denyRule).toContain("background: #f1f5f9");
    expect(denyRule).toContain("color: #475569");
    expect(denyRule).not.toContain("box-shadow:");
    expect(denyCountRule).toContain("color: #475569");
    expect(countRule).toContain("min-width: 22px");
    expect(countRule).toContain("height: 22px");
    expect(countRule).toContain("border-radius: 999px");
    expect(countRule).toContain("font-variant-numeric: tabular-nums");
    expect(focusRule).toContain("outline: 3px solid");
    expect(focusRule).toContain("outline-offset: 2px");
    expect(darkDenyPressedRule).toContain("background: #64748b");
    expect(darkDenyPressedRule).toContain("color: #fff");
    expect(darkDenyCountRule).toContain("color: #e2e8f0");
    expect(shareRule).toContain("width: 40px");
    expect(shareRule).toContain("height: 40px");
    expect(shareRule).toContain("border: 0");
    expect(shareRule).toContain("background: transparent");
    expect(shareRule).toContain("color: #52697b");
    expect(shareFocusRule).toContain("background: #edf7fd");
    expect(shareSuccessRule).toContain("color: #047857");
    expect(shareErrorRule).toContain("color: #b42318");
    expect(shareStatusRule).toContain("position: absolute");
    expect(shareStatusRule).toContain("clip-path: inset(50%)");
    expect(darkShareRule).toContain("border: 0");
    expect(darkShareRule).toContain("background: transparent");
    expect(darkShareRule).toContain("color: #bfe6fb");
  });

  it("lights the selected moderation reason and clearly separates active and disabled flagging", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const reasonRule = css.match(
      /\.mf-live-moderation-dialog__reasons label\s*\{([^}]+)\}/,
    )?.[1] || "";
    const checkedReasonRule = css.match(
      /\.mf-live-moderation-dialog__reasons label:has\(input:checked\)\s*\{([^}]+)\}/,
    )?.[1] || "";
    const radioRule = css.match(
      /\.mf-live-moderation-dialog__reasons input\s*\{([^}]+)\}/,
    )?.[1] || "";
    const activeFlagRule = css.match(
      /\.mf-live-moderation-dialog__submit--flag\s*\{([^}]+)\}/,
    )?.[1] || "";
    const disabledFlagRule = css.match(
      /\.mf-live-moderation-dialog__submit--flag:disabled\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(reasonRule).toContain("border: 1px solid #e2e8f0");
    expect(reasonRule).toContain("background: #fff");
    expect(checkedReasonRule).toContain("border-color: #0284c7");
    expect(checkedReasonRule).toContain("background: rgba(2, 132, 199, 0.06)");
    expect(radioRule).toContain("accent-color: #0284c7");
    expect(activeFlagRule).toContain(
      "background: linear-gradient(135deg, #e11d48, #be123c)",
    );
    expect(activeFlagRule).toContain(
      "box-shadow: 0 8px 18px rgba(244, 63, 94, 0.35)",
    );
    expect(activeFlagRule).toContain("color: #fff");
    expect(disabledFlagRule).toContain("border-color: #e2e8f0");
    expect(disabledFlagRule).toContain("background: #e2e8f0");
    expect(disabledFlagRule).toContain("box-shadow: none");
    expect(disabledFlagRule).toContain("color: #94a3b8");
    expect(disabledFlagRule).toContain("opacity: 1");
  });

  it("styles the inline Territory navigation as one flat tab bar", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const workspaceSelector = "\\.mf-live-community-map-layer--inline\\.mf-live-territory-workspace";
    const navigationRule = css.match(
      new RegExp(`${workspaceSelector} \\.mf-territory-map__navigation\\s*\\{([^}]+)\\}`),
    )?.[1] || "";
    const buttonRule = css.match(
      new RegExp(
        `${workspaceSelector} \\.mf-territory-map__navigation button,\\s*`
        + `${workspaceSelector} \\.mf-territory-map__navigation button\\.is-active\\s*\\{([^}]+)\\}`,
      ),
    )?.[1] || "";
    const activeRule = [...css.matchAll(
      new RegExp(`^${workspaceSelector} \\.mf-territory-map__navigation button\\.is-active\\s*\\{([^}]+)\\}`, "gm"),
    )].map((match) => match[1]).find((rule) => rule.includes("color: var(--mf-blue)")) || "";
    const activeUnderlineRule = css.match(
      new RegExp(`^${workspaceSelector} \\.mf-territory-map__navigation button\\.is-active::after\\s*\\{([^}]+)\\}`, "m"),
    )?.[1] || "";

    expect(navigationRule).toContain("gap: 0");
    expect(navigationRule).toContain("padding: 0");
    expect(navigationRule).toContain("border-bottom: 1px solid var(--mf-neutral-border)");
    expect(navigationRule).toContain("border-radius: 0");
    expect(navigationRule).toContain("background: transparent");
    expect(buttonRule).toContain("min-height: 48px");
    expect(buttonRule).toContain("border-radius: 0");
    expect(activeRule).toContain("background: transparent");
    expect(activeRule).toContain("color: var(--mf-blue)");
    expect(activeRule).toContain("box-shadow: none");
    expect(activeUnderlineRule).toContain("left: 0");
    expect(activeUnderlineRule).toContain("right: 0");
    expect(activeUnderlineRule).toContain("height: 3px");
    expect(activeUnderlineRule).toContain("background: var(--mf-blue)");
  });

  it("raises preview and expanded browse panels inside the inline Territory dock", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const declarationsFor = (className) => {
      const escaped = className.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return [...css.matchAll(new RegExp(`[^{}]*${escaped}[^{}]*\\{([^}]+)\\}`, "g"))]
        .map((match) => match[1])
        .join("\n");
    };
    const dockRules = declarationsFor(".mf-territory-map__dock");
    const expandedRules = declarationsFor(".mf-territory-map--panel-expanded");
    const grabberRules = declarationsFor(".mf-territory-map__dock-grabber");
    const sheetRules = declarationsFor(".mf-territory-map__browse-sheet");
    const listRules = declarationsFor(".mf-territory-map__browse-list");
    const toggleRules = declarationsFor(".mf-territory-map__browse-toggle");
    const groupRules = declarationsFor(".mf-territory-map__webcam-groups");
    const groupButtonRules = declarationsFor(".mf-territory-map__webcam-groups button");

    expect(dockRules).toContain("height: var(--mf-territory-map-dock-height)");
    expect(dockRules).toContain("transition: height");
    expect(expandedRules).toContain("--mf-territory-map-dock-height:");
    expect(grabberRules).toContain("border-radius: 999px");
    expect(grabberRules).toContain("background:");
    expect(sheetRules).toContain("position: relative");
    expect(sheetRules).toContain("overflow: hidden");
    expect(listRules).toContain("overflow-y: auto");
    expect(toggleRules).toContain("min-height: 44px");
    expect(groupRules).toContain("justify-content: safe center");
    expect(groupRules).toContain("overflow-x: auto");
    expect(groupRules).toContain("scrollbar-width: none");
    expect(groupButtonRules).toContain("--mf-definitive-gradient");
    expect(groupButtonRules).toContain("color: #fff");
    expect(css).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.mf-territory-map__dock[\s\S]*?transition:\s*none/,
    );
  });

  it("uses compact webcam pins, photographic thumbnails, and a one-card preview dock", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const declarationsFor = (selectorFragment) => {
      const escaped = selectorFragment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return [...css.matchAll(new RegExp(`[^{}]*${escaped}[^{}]*\\{([^}]+)\\}`, "g"))]
        .map((match) => match[1])
        .join("\n");
    };
    const marker = declarationsFor(".mf-territory-map__webcam-marker");
    const markerVisual = declarationsFor(".mf-territory-map__webcam-marker::before");
    const clusterCount = declarationsFor(".mf-territory-map__webcam-cluster-count");
    const thumbnail = declarationsFor(".mf-territory-map__webcam-thumbnail");
    const thumbnailImage = declarationsFor(".mf-territory-map__webcam-thumbnail img");
    const previewDock = declarationsFor(".mf-territory-map--inline");
    const webcamPreviewDock = declarationsFor(".mf-territory-map--webcams-open");
    const emptyReportsDock = declarationsFor(".mf-territory-map--reports-empty");
    const compactSheet = declarationsFor(
      ".mf-territory-map__browse-sheet--compact",
    );
    const darkMarker = css.match(
      /html\[data-theme="dark"\][^{]*\.mf-territory-map__webcam-marker\s*\{([^}]+)\}/,
    )?.[1] || "";
    const highlightedMarker = declarationsFor(".is-highlighted");
    const unhealthyMarker = declarationsFor(".is-health-not-ok");

    expect(marker).toContain("width: 44px");
    expect(marker).toContain("height: 44px");
    expect(marker).toContain("pointer-events: auto");
    expect(markerVisual).toContain("width: 32px");
    expect(markerVisual).toContain("height: 32px");
    expect(clusterCount).toContain("left: 50%");
    expect(clusterCount).toContain("right: auto");
    expect(clusterCount).toContain("justify-items: center");
    expect(clusterCount).toContain("text-align: center");
    expect(clusterCount).toContain("transform: translateX(-50%)");
    expect(thumbnail).toContain("width: 52px");
    expect(thumbnail).toContain("height: 38px");
    expect(thumbnail).toContain("overflow: hidden");
    expect(thumbnailImage).toContain("object-fit: cover");
    expect(previewDock).toContain("--mf-territory-map-dock-preview-height:");
    expect(previewDock).toContain("--mf-territory-map-dock-preview-height: 260px");
    expect(webcamPreviewDock).toContain("--mf-territory-map-dock-height: 190px");
    expect(emptyReportsDock).toContain("--mf-territory-map-dock-height: 220px");
    expect(compactSheet).toContain("align-content: start");
    expect(compactSheet).toContain("grid-template-rows: auto minmax(0, 1fr)");
    expect(darkMarker).toContain("--mf-webcam-pin-background: rgba(19, 29, 46");
    expect(darkMarker).toContain("color: #e2e8f0");
    expect(highlightedMarker).toContain("animation:");
    expect(unhealthyMarker).toContain("color: #dc2626");
    expect(unhealthyMarker).toContain("--mf-webcam-pin-border: rgba(220, 38, 38");
    expect(css).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.mf-territory-map__webcam-marker[\s\S]*?animation:\s*none/,
    );
  });

  it("keeps every community marker at least 44px large even with lighter pilot styling", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const markerRule = css.match(
      /\.mf-live-community-map__marker\s*\{([^}]+)\}/,
    )?.[1] || "";
    const width = Number(markerRule.match(/width:\s*(\d+)px/)?.[1]);
    const height = Number(markerRule.match(/height:\s*(\d+)px/)?.[1]);

    expect(width).toBeGreaterThanOrEqual(44);
    expect(height).toBeGreaterThanOrEqual(44);
    expect(markerRule).toContain("pointer-events: auto");
  });

  it("keeps round pilot markers on the same luminous treatment as report icons", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const rule = (selector) => {
      const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return css.match(new RegExp(`^${escaped}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";
    };
    const immersiveMarker = rule(
      ".mf-live-community-map--immersive .mf-live-community-map__marker",
    );
    const pilotImmersiveMarker = rule(
      ".mf-live-community-map-layer--pilot .mf-live-community-map--immersive .mf-live-community-map__marker",
    );
    const inlineMarker = rule(
      ".mf-live-community-map-layer--inline.mf-live-territory-workspace .mf-territory-map .mf-live-community-map__marker",
    );
    const ordinaryMarker = rule(".mf-live-community-map__marker");

    expect(ordinaryMarker).toContain("background: var(--mf-live-marker-color)");
    expect(ordinaryMarker).toContain("color: #fff");
    expect(immersiveMarker).toContain("background: #fff");
    expect(immersiveMarker).toContain("color: var(--mf-live-marker-color)");
    [pilotImmersiveMarker, inlineMarker].forEach((marker) => {
      expect(marker).toContain("width: 46px");
      expect(marker).toContain("height: 46px");
      expect(marker).toContain("border-top: 1px solid rgba(255, 255, 255, 0.45)");
      expect(marker).toContain(
        "background: linear-gradient(135deg, var(--mf-report-icon-from), var(--mf-report-icon-to))",
      );
      expect(marker).toContain("0 6px 14px var(--mf-report-icon-shadow)");
      expect(marker).toContain("color: #fff");
    });
    ["rain", "storm", "hail", "snow", "ice", "fog", "wind", "quiet"].forEach((type) => {
      expect(css).toContain(
        ".mf-live-community-map-layer--inline.mf-live-territory-workspace "
          + ".mf-territory-map .mf-live-community-map__marker"
          + `.mf-live-community-map__marker--${type}`,
      );
    });

    expect(rule(".mf-live-community-map__marker--wind"))
      .toContain("--mf-live-marker-color: #148878");
    const darkMarker = rule(
      'html[data-theme="dark"] .mf-live-community-map--immersive .mf-live-community-map__marker',
    );
    expect(darkMarker).not.toContain("background: #fff");
    expect(darkMarker).not.toContain("color: var(--mf-live-marker-color)");
  });

  it("styles grouped markers as a dimmed 44px radial fan with reduced-motion support", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const rule = (className) => css.match(
      new RegExp(`\\.${className}\\s*\\{([^}]+)\\}`, "m"),
    )?.[1] || "";
    const backdrop = rule("mf-territory-map__cluster-backdrop");
    const toggle = rule("mf-territory-map__cluster-toggle");
    const petal = rule("mf-territory-map__cluster-petal");
    const leg = rule("mf-territory-map__cluster-leg");

    expect(backdrop).toContain("background: rgba(0, 15, 30, 0.25)");
    expect(toggle).toContain("width: 44px");
    expect(toggle).toContain("height: 44px");
    expect(petal).toContain("width: 44px");
    expect(petal).toContain("height: 44px");
    expect(petal).toContain("var(--mf-cluster-x)");
    expect(petal).toContain("mf-territory-cluster-petal-in");
    expect(leg).toContain("height: 2px");
    expect(css).toContain("@keyframes mf-territory-cluster-petal-in");
    expect(css).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.mf-territory-map__cluster-petal[\s\S]*?animation:\s*none/,
    );
  });

  it("uses a dark loading surface behind the dark territory basemap", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const rule = css.match(
      /html\[data-theme="dark"\] \.mf-live-community-map-layer--pilot \.mf-live-community-map__canvas\.leaflet-container\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(rule).toContain("background: #090e17");
  });

  it("slightly lifts only the dark territory basemap tiles", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const rule = css.match(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--pilot\s+\.mf-territory-map\s+\.leaflet-tile-pane\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(rule).toContain("filter: brightness(1.28) contrast(0.98)");
  });

  it("builds a scoped dark elevation hierarchy with luminous Territory controls and lists", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const rule = (pattern) => css.match(pattern)?.[1] || "";
    const route = rule(
      /html\[data-theme="dark"\] \.mf-app-main--territory-fit\s*\{([^}]+)\}/,
    );
    const workspace = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s*\{([^}]+)\}/,
    );
    const dock = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map__dock\s*\{([^}]+)\}/,
    );
    const inactiveControl = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map__control:not\(\.mf-territory-map__control--alert\)\s*\{([^}]+)\}/,
    );
    const gpsIcon = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map__control--gps:not\(\.is-pulsing\) > svg\s*\{([^}]+)\}/,
    );
    const radarPlayer = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-radar-overlay:not\(\.mf-territory-radar-overlay--unavailable\)\s*\{([^}]+)\}/,
    );
    const radarLive = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-radar-live\s*\{([^}]+)\}/,
    );
    const activeControl = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+:is\(\s*\.mf-territory-map__control\[aria-pressed="true"\],\s*\.mf-territory-map__control--webcam\.is-active\s*\)\s*\{([^}]+)\}/,
    );
    const cta = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map__report-action\s*\{([^}]+)\}/,
    );
    const browseItem = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map__dock \.mf-territory-map__browse-list\s*> \.mf-territory-map__browse-item\s*\{([^}]+)\}/,
    );
    const browseIcon = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map__dock \.mf-territory-map__browse-item > span:first-child\s*\{([^}]+)\}/,
    );
    const rainPalette = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map__browse-item--rain\s*\{([^}]+)\}/,
    );
    const windPalette = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map__browse-item--wind\s*\{([^}]+)\}/,
    );
    const inactiveFilter = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map__webcam-groups button\s*\{([^}]+)\}/,
    );
    const activeFilter = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map__webcam-groups button\.is-active\s*\{([^}]+)\}/,
    );
    const activeFilterCount = rule(
      /html\[data-theme="dark"\]\s+\.mf-live-community-map-layer--inline\.mf-live-territory-workspace\s+\.mf-territory-map__webcam-groups button\.is-active em\s*\{([^}]+)\}/,
    );

    expect(route).toContain("--mf-territory-dark-level-0: #090e17");
    expect(route).toContain("--mf-territory-dark-level-1: #131d2e");
    expect(route).toContain("--mf-territory-dark-level-2: #1a263b");
    expect(route).not.toMatch(/(?:^|\n)\s*background:/);
    expect(workspace).toContain("background: var(--mf-territory-dark-level-0, #090e17)");
    expect(dock).toContain("background: rgba(19, 29, 46, 0.98)");
    expect(dock).toContain("border-top-color: rgba(255, 255, 255, 0.08)");
    expect(inactiveControl).toContain("background: rgba(19, 29, 46, 0.85)");
    expect(inactiveControl).toContain("border-color: rgba(255, 255, 255, 0.15)");
    expect(inactiveControl).toContain("color: #e2e8f0");
    expect(gpsIcon).toContain("color: #e2e8f0");
    expect(gpsIcon).toContain("stroke: currentColor");
    expect(gpsIcon).toContain("drop-shadow(0 0 4px rgba(226, 232, 240, 0.2))");
    expect(radarPlayer).toContain("background: transparent");
    expect(radarPlayer).toContain("border-bottom-color: rgba(255, 255, 255, 0.08)");
    expect(radarPlayer).toContain("box-shadow: none");
    expect(radarPlayer).toContain("-webkit-backdrop-filter: none");
    expect(radarPlayer).toContain("backdrop-filter: none");
    expect(radarPlayer).toContain("color: #cbd5e1");
    expect(radarLive).toContain("color: #10b981");
    expect(css).toContain("rgba(255, 255, 255, 0.15) var(--mf-territory-radar-progress) 100%");
    expect(activeControl).toContain("background: linear-gradient(135deg, #38bdf8, #0284c7)");
    expect(activeControl).toContain("box-shadow: 0 0 20px rgba(56, 189, 248, 0.45)");
    expect(cta).toContain("#38bdf8 0%");
    expect(cta).toContain("#1d4ed8 100%");
    expect(cta).toContain("box-shadow: 0 8px 24px -4px rgba(56, 189, 248, 0.4)");
    expect(browseItem).toContain("background: var(--mf-territory-dark-level-2, #1a263b)");
    expect(browseItem).toContain("border-color: rgba(255, 255, 255, 0.07)");
    expect(browseIcon).toContain(
      "background: linear-gradient(135deg, var(--mf-browse-icon-from), var(--mf-browse-icon-to))",
    );
    expect(browseIcon).toContain("color: #fff");
    expect(rainPalette).toContain("--mf-browse-icon-from: #60a5fa !important");
    expect(rainPalette).toContain("--mf-browse-icon-to: #2563eb !important");
    expect(windPalette).toContain("--mf-browse-icon-from: #c084fc !important");
    expect(windPalette).toContain("--mf-browse-icon-to: #7c3aed !important");
    expect(inactiveFilter).toContain("background: rgba(255, 255, 255, 0.05)");
    expect(inactiveFilter).toContain("color: #94a3b8");
    expect(activeFilter).toContain("background: linear-gradient(135deg, #38bdf8, #0284c7)");
    expect(activeFilter).toContain("color: #020617");
    expect(activeFilterCount).toContain("background: #fff");
    expect(activeFilterCount).toContain("color: #1e3a8a");
  });

  it("animates the report opening while respecting reduced motion", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");

    expect(css).toContain("animation: mf-live-report-backdrop-in");
    expect(css).toContain("animation: mf-live-report-dialog-in");
    expect(css).toContain("@keyframes mf-live-report-dialog-in");
    expect(css).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.mf-live-report-form--sheet[\s\S]*?animation: none/,
    );
  });

  it("keeps the vertical disclosure for ordinary builds and adds a scoped pilot carousel", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const triggerRule = css.match(
      /\.mf-live-webcam-picker__trigger\s*\{([^}]+)\}/,
    )?.[1] || "";
    const optionRule = css.match(
      /\.mf-live-webcam-picker__options button\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(triggerRule).toContain("min-height: 48px");
    expect(triggerRule).toContain("grid-template-columns: minmax(0, 1fr) auto");
    expect(optionRule).toContain("min-height: 44px");
    expect(optionRule).toContain("grid-template-columns: 18px minmax(0, 1fr) auto");
    expect(css).toContain(".mf-live-webcam-picker__options[hidden]");
    expect(css).not.toContain(".mf-live-webcam-strip");

    const carouselRule = css.match(
      /\.mf-live-webcam-carousel\s*\{([^}]+)\}/,
    )?.[1] || "";
    const carouselItemRule = css.match(
      /\.mf-live-webcam-carousel__item\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(carouselRule).toContain("grid-auto-flow: column");
    expect(carouselRule).toContain("overflow-x: auto");
    expect(carouselRule).toContain("scroll-snap-type: inline mandatory");
    expect(carouselItemRule).toContain("scroll-snap-align: start");
    expect(css).toContain(".mf-live-view--compact-territory .mf-live-card--webcam .mf-tab");
  });

  it("uses scoped horizontal community cards and a compact disclosure only in the pilot flow", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const compactListRule = css.match(
      /\.mf-live-community-list--carousel\s*\{([^}]+)\}/,
    )?.[1] || "";
    const compactItemRule = css.match(
      /\.mf-live-community-list--carousel \.mf-live-community-item\s*\{([^}]+)\}/,
    )?.[1] || "";
    const mapToggleRule = css.match(
      /\.mf-live-community-map-toggle\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(compactListRule).toContain("grid-auto-flow: column");
    expect(compactListRule).toContain("overflow-x: auto");
    expect(compactListRule).toContain("scroll-snap-type: inline mandatory");
    expect(compactItemRule).toContain("scroll-snap-align: start");
    expect(mapToggleRule).toContain("min-height:");
  });

  it("uses neutral blue community surfaces only in the compact pilot flow", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const compactCardRule = css.match(
      /^\.mf-live-view--compact-territory \.mf-live-card--community\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const ordinaryItemRule = css.match(/^\.mf-live-community-item\s*\{([^}]+)\}/m)?.[1] || "";
    const compactItemRule = css.match(
      /^\.mf-live-view--compact-territory \.mf-live-community-list--carousel \.mf-live-community-item\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const compactConfirmRule = css.match(
      /^\.mf-live-view--compact-territory \.mf-live-community-list--carousel \.mf-live-community-item__confirm\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const mapToggleRule = css.match(/^\.mf-live-community-map-toggle\s*\{([^}]+)\}/m)?.[1] || "";

    expect(compactCardRule).toContain("background: var(--mf-neutral-surface)");
    expect(compactCardRule).toContain("border: 1px solid var(--mf-neutral-border)");
    expect(compactCardRule).toContain("box-shadow: var(--mf-neutral-shadow)");
    expect(compactCardRule).not.toContain("linear-gradient");
    expect(ordinaryItemRule).toContain("border-left: 3px solid #15958a");
    expect(compactItemRule).toContain("background: var(--mf-neutral-surface)");
    expect(compactItemRule).toContain("border: 1px solid var(--mf-neutral-border)");
    expect(compactConfirmRule).toContain("var(--mf-blue-050)");
    expect(compactConfirmRule).toContain("color: var(--mf-blue-700)");
    expect(mapToggleRule).toContain("background: var(--mf-neutral-surface)");
    expect(mapToggleRule).toContain("border: 1px solid var(--mf-neutral-border)");
    expect(mapToggleRule).toContain("border-radius: 999px");
    expect(mapToggleRule).toContain("color: var(--mf-blue-700)");
  });

  it("keeps the compact community palette neutral and blue in dark mode", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const darkCardRule = css.match(
      /^html\[data-theme="dark"\] \.mf-live-view--compact-territory \.mf-live-card--community\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const darkSummaryRule = css.match(
      /^html\[data-theme="dark"\] \.mf-live-view--compact-territory \.mf-live-community-summary\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const darkIconRule = css.match(
      /^html\[data-theme="dark"\] \.mf-live-view--compact-territory \.mf-live-card--community \.mf-live-section-header__icon\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const scopedConfirmRule = css.match(
      /^\.mf-live-view--compact-territory \.mf-live-community-list--carousel \.mf-live-community-item__confirm\s*\{([^}]+)\}/m,
    )?.[1] || "";

    expect(darkCardRule).toContain("background: var(--mf-neutral-surface)");
    expect(darkCardRule).not.toContain("linear-gradient");
    expect(darkSummaryRule).toContain("var(--mf-blue-050)");
    expect(darkSummaryRule).toContain("var(--mf-neutral-surface)");
    expect(darkIconRule).toContain("var(--mf-blue-050)");
    expect(darkIconRule).toContain("color: var(--mf-blue-700)");
    expect(scopedConfirmRule).toContain("var(--mf-blue-050)");
    expect(scopedConfirmRule).toContain("color: var(--mf-blue-700)");
  });

  it("keeps the neutral report composer appearance scoped to its pilot modifier", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const pilotSheetRule = css.match(
      /^\.mf-live-report-form--sheet\.mf-live-report-form--pilot\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const pilotChromeRule = css.match(
      /^\.mf-live-report-form--pilot :is\(\.mf-live-report-form__header, \.mf-live-report-form__footer\)\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const pilotFieldsRule = css.match(
      /^\.mf-live-report-form--pilot :is\(\.mf-live-report-option:not\(\.is-active\), \.mf-live-report-location:not\(\.mf-live-report-location--error\), \.mf-live-report-location__selector, \.mf-live-report-terms\)\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const ordinarySheetRule = css.match(
      /\.mf-live-report-form--sheet,\s*\nhtml\[data-theme="dark"\] \.mf-live-report-form--sheet\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(pilotSheetRule).toContain("background: var(--mf-neutral-surface)");
    expect(pilotSheetRule).toContain("border: 1px solid var(--mf-neutral-border)");
    expect(pilotChromeRule).toContain("background: var(--mf-neutral-surface)");
    expect(pilotChromeRule).toContain("border-color: var(--mf-neutral-border)");
    expect(pilotFieldsRule).toContain("background: var(--mf-neutral-surface)");
    expect(pilotFieldsRule).toContain("border-color: var(--mf-neutral-border)");
    expect(pilotFieldsRule).not.toMatch(/#dff2ee|#e7f4f2|#edf7f5/);
    expect(ordinarySheetRule).toContain("background: var(--mf-surface)");
  });

  it("scopes the new community summary surface to the pilot layout", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const ordinarySummaryRule = css.match(
      /^\.mf-live-community-summary\s*\{([^}]+)\}/m,
    )?.[1] || "";
    const pilotSummaryRule = css.match(
      /^\.mf-live-view--compact-territory \.mf-live-community-summary\s*\{([^}]+)\}/m,
    )?.[1] || "";

    expect(ordinarySummaryRule).not.toContain("background:");
    expect(ordinarySummaryRule).not.toContain("border:");
    expect(ordinarySummaryRule).not.toContain("padding:");
    expect(pilotSummaryRule).toContain("background:");
    expect(pilotSummaryRule).toContain("border:");
    expect(pilotSummaryRule).toContain("padding:");
  });

  it("styles the pilot source links as a compact footer with full-size touch targets", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const sourceRule = css.match(
      /\.mf-live-territory-sources\s*\{([^}]+)\}/,
    )?.[1] || "";
    const linkRule = css.match(
      /\.mf-live-territory-sources__links a\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(sourceRule).toContain("display: grid");
    expect(linkRule).toContain("min-height: 44px");
    expect(linkRule).toContain("text-decoration: none");
  });

  it("reserves a 16:9 webcam skeleton and styles a light failure action", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const skeletonMediaRule = css.match(
      /\.mf-live-webcam-skeleton__media\s*\{([^}]+)\}/,
    )?.[1] || "";
    const failureActionRule = css.match(
      /\.mf-live-webcam-preview__fallback-actions button\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(skeletonMediaRule).toContain("aspect-ratio: 16 / 9");
    expect(failureActionRule).toContain("min-height: 44px");
    expect(failureActionRule).toContain("border: 0");
    expect(failureActionRule).toContain("background: transparent");
    expect(failureActionRule).not.toContain("border-radius: 999px");
    expect(css).toContain(".mf-live-webcam-preview__fallback-actions button");
    expect(css).toContain(".mf-live-webcam-preview__fallback-visual");
    expect(css).toContain(".mf-live-webcam-preview__fallback-copy");
    expect(css).toContain(".mf-live-webcam-preview__source-meta");
    expect(css).toContain(".mf-live-webcam-preview__provider");
    expect(css).toContain('@media (prefers-reduced-motion: reduce)');
  });

  it("presents the external webcam action as a compact icon link", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
    const sourceLinkRule = css.match(
      /\.mf-live-webcam-preview__source a\s*\{([^}]+)\}/,
    )?.[1] || "";
    const sourceActionRule = css.match(
      /\.mf-live-webcam-preview__source-action\s*\{([^}]+)\}/,
    )?.[1] || "";

    expect(sourceLinkRule).toContain("border: 0");
    expect(sourceLinkRule).toContain("background: transparent");
    expect(sourceLinkRule).toContain("text-decoration: none");
    expect(sourceLinkRule).not.toContain("border-radius: 999px");
    expect(sourceActionRule).toContain("width: 32px");
  });

  it("limits the compact paragraph spacing to the community introduction", () => {
    const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");

    expect(css).toContain(".mf-live-community-intro");
    expect(css).not.toContain(".mf-live-card--community > p");
  });
});
