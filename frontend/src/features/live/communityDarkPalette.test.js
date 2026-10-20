import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");
const sectionStart = css.indexOf("/* Shared dark palette for pilot Community dialogs;");
const sectionEnd = css.indexOf("@keyframes", sectionStart);
const section = sectionStart >= 0 && sectionEnd > sectionStart
  ? css.slice(sectionStart, sectionEnd).replace(/\/\*[\s\S]*?\*\//g, "")
  : "";
const receiptRoot = 'html[data-theme="dark"] .mf-live-report-form--pilot';
const mapRoot = 'html[data-theme="dark"] .mf-territory-map__report-detail--pilot';
const rules = [...section.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(([, selectors, body]) => ({
  selectors: selectors.split(",").map((selector) => selector.trim()),
  declarations: Object.fromEntries([...body.matchAll(/([\w-]+)\s*:\s*([^;]+);/g)]
    .map(([, property, value]) => [property, value.trim()])),
}));

function declarationsFor(selector) {
  return Object.assign({}, ...rules
    .filter((rule) => rule.selectors.includes(selector))
    .map((rule) => rule.declarations));
}

const tokens = declarationsFor(receiptRoot);

function color(value) {
  if (/^#[\da-f]{3}$/i.test(value)) {
    return [...value.slice(1)].map((channel) => parseInt(channel.repeat(2), 16));
  }
  if (/^#[\da-f]{6}$/i.test(value)) {
    return [...value.slice(1).matchAll(/../g)].map(([channel]) => parseInt(channel, 16));
  }
  const rgba = /^rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\)$/.exec(value);
  if (rgba) return rgba.slice(1).map(Number);
  throw new Error(`Unsupported palette color: ${value}`);
}

function composite(foreground, background) {
  const alpha = foreground[3] ?? 1;
  return foreground.slice(0, 3).map((channel, index) => (
    channel * alpha + background[index] * (1 - alpha)
  ));
}

function luminance(rgb) {
  const linear = rgb.slice(0, 3).map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}

function contrast(foreground, background) {
  const foregroundLuminance = luminance(composite(foreground, background));
  const backgroundLuminance = luminance(background);
  return (Math.max(foregroundLuminance, backgroundLuminance) + 0.05)
    / (Math.min(foregroundLuminance, backgroundLuminance) + 0.05);
}

describe("pilot Community dark palette", () => {
  it("defines the agreed shared tokens only on the two dark pilot roots", () => {
    expect(section).not.toBe("");
    expect(tokens).toEqual({
      "--mf-community-card-bg": "rgba(255, 255, 255, 0.05)",
      "--mf-community-card-border": "rgba(255, 255, 255, 0.12)",
      "--mf-community-divider": "rgba(255, 255, 255, 0.1)",
      "--mf-community-text": "#f8fafc",
      "--mf-community-secondary": "#cbd5e1",
      "--mf-community-alias-border": "#f2c94c",
      "--mf-community-alias-bg": "rgba(242, 201, 76, 0.12)",
      "--mf-community-alias-text": "#fff",
      "--mf-community-alias-glow": "0 0 10px rgba(242, 201, 76, 0.2)",
      "--mf-community-heart": "#fb7185",
      "--mf-community-heart-bg": "rgba(244, 63, 94, 0.15)",
      "--mf-community-action-bg": "rgba(56, 169, 244, 0.15)",
      "--mf-community-action-border": "#38a9f4",
      "--mf-community-action-text": "#e0f2fe",
      "--mf-community-action-glow": "0 0 12px rgba(56, 169, 244, 0.25)",
      "--mf-community-danger-bg": "rgba(239, 68, 68, 0.14)",
      "--mf-community-danger-border": "#f87171",
      "--mf-community-danger-text": "#fecaca",
      "--mf-community-danger-glow": "0 0 10px rgba(239, 68, 68, 0.2)",
      "--mf-community-neutral-bg": "rgba(255, 255, 255, 0.06)",
      "--mf-community-neutral-border": "rgba(255, 255, 255, 0.25)",
      "--mf-community-neutral-text": "#fff",
    });
    expect(declarationsFor(mapRoot)).toEqual(tokens);
    for (const rule of rules) {
      for (const selector of rule.selectors) {
        expect([receiptRoot, mapRoot].some((scope) => (
          selector === scope || selector.startsWith(`${scope} `)
        )), selector).toBe(true);
      }
    }
  });

  it.each([
    `${receiptRoot} .mf-live-report-success__summary`,
    `${mapRoot} .mf-territory-map__report-community-status`,
    `${mapRoot} .mf-live-community-own-report--compact`,
  ])("neutralizes the card gradient and shadow at %s", (selector) => {
    expect(declarationsFor(selector)).toMatchObject({
      background: "var(--mf-community-card-bg)",
      "border-color": "var(--mf-community-card-border)",
      "box-shadow": "none",
      color: "var(--mf-community-text)",
    });
  });

  it.each([
    `${mapRoot} .mf-territory-map__report-community-single`,
    `${mapRoot} .mf-territory-map__report-community-toggle`,
  ])("applies amber fill and explicit readable alias text at %s", (selector) => {
    expect(declarationsFor(selector)).toMatchObject({
      background: "var(--mf-community-alias-bg)",
      "border-style": "solid",
      "border-width": "1.5px",
      "border-color": "var(--mf-community-alias-border)",
      color: "var(--mf-community-alias-text) !important",
      "box-shadow": "var(--mf-community-alias-glow)",
    });
  });

  it.each([
    `${receiptRoot} .mf-live-report-success__description`,
    `${receiptRoot} .mf-live-report-success__expiry`,
    `${receiptRoot} .mf-live-report-success__place`,
    `${mapRoot} .mf-territory-map__report-heading-copy small`,
    `${mapRoot} .mf-territory-map__report-community-identities-label`,
    `${mapRoot} .mf-live-community-own-report__expiry`,
    `${mapRoot} .mf-live-community-own-report__explanation`,
    `${mapRoot} .mf-live-community-own-report__withdraw-confirm > small:not(.mf-live-community-own-report__withdraw-error)`,
  ])("uses the shared secondary color at %s", (selector) => {
    expect(declarationsFor(selector).color).toBe("var(--mf-community-secondary)");
  });

  it("overrides the existing important identity caption and explicit map alias colors", () => {
    expect(declarationsFor(`${receiptRoot} .mf-live-report-success__identity-label`).color)
      .toBe("var(--mf-community-secondary) !important");
    expect(declarationsFor(`${receiptRoot} .mf-live-report-success__identity-inline`)).toEqual({});
    expect(declarationsFor(`${mapRoot} .mf-territory-map__report-community-summary`).color)
      .toBe("var(--mf-community-alias-text)");
    expect(declarationsFor(`${mapRoot} .mf-territory-map__report-community-list-item`).color)
      .toBe("var(--mf-community-text)");
  });

  it("keeps the primary update solid blue without overwriting success or retry styling", () => {
    const primaryRules = rules.filter((rule) => (
      rule.declarations.background === "var(--mf-community-action-bg)"
    ));
    expect(primaryRules).toHaveLength(1);
    expect(primaryRules[0].selectors).toEqual([
      `${mapRoot} .mf-live-community-own-report--compact .mf-live-community-own-report__choice`,
    ]);
    expect(primaryRules[0].declarations).toEqual({
      background: "var(--mf-community-action-bg)",
    });
    expect(declarationsFor(`${mapRoot} .mf-live-community-own-report__update:not(.is-success):not(.is-error)`))
      .toEqual({
        "border-color": "var(--mf-community-action-border)",
        background: "linear-gradient(135deg, #1d4ed8, #0369a1)",
        color: "#fff",
      });
  });

  it("keeps withdrawal ghosted, makes confirmation decisively red and cancel solid", () => {
    expect(declarationsFor(`${mapRoot} .mf-live-community-own-report__withdraw`)).toEqual({
      "border-color": "transparent",
      background: "transparent",
      color: "var(--mf-community-danger-text)",
    });
    expect(declarationsFor(`${mapRoot} .mf-live-community-own-report__withdraw-confirm button.is-destructive`))
      .toEqual({
        "border-color": "#f87171",
        background: "rgba(220, 38, 38, 0.32)",
        color: "#fee2e2",
      });
    expect(declarationsFor(`${mapRoot} .mf-live-community-own-report__withdraw-confirm button:not(.is-destructive)`))
      .toEqual({
        "border-color": "#38a9f4",
        background: "#1e5fa8",
        color: "#fff",
      });
  });

  it("adds action glows only to enabled controls while preserving disabled opacity", () => {
    const actionGlowRules = rules.filter((rule) => (
      /var\(--mf-community-(?:action|danger)-glow\)/.test(rule.declarations["box-shadow"] || "")
    ));
    expect(actionGlowRules).toHaveLength(2);
    expect(actionGlowRules.flatMap((rule) => rule.selectors)).toEqual([
      `${mapRoot} .mf-live-community-own-report__update:not(.is-success):not(.is-error):enabled`,
      `${mapRoot} .mf-live-community-own-report--compact .mf-live-community-own-report__choice:enabled`,
      `${mapRoot} .mf-live-community-own-report__withdraw-confirm button.is-destructive:enabled`,
    ]);
    for (const rule of actionGlowRules) {
      expect(Object.keys(rule.declarations)).toEqual(["box-shadow"]);
      expect(rule.selectors.every((selector) => selector.endsWith(":enabled"))).toBe(true);
    }
    for (const rule of rules) {
      expect(rule.declarations).not.toHaveProperty("opacity");
      expect(rule.selectors.some((selector) => selector.includes(":disabled"))).toBe(false);
    }
  });

  it("colors only the withdrawal explanation as secondary and leaves its error state intact", () => {
    const withdrawalCaptionSelectors = rules
      .filter((rule) => rule.declarations.color === "var(--mf-community-secondary)")
      .flatMap((rule) => rule.selectors)
      .filter((selector) => selector.includes("__withdraw-confirm"));
    expect(withdrawalCaptionSelectors).toEqual([
      `${mapRoot} .mf-live-community-own-report__withdraw-confirm > small:not(.mf-live-community-own-report__withdraw-error)`,
    ]);
    expect(declarationsFor(`${mapRoot} .mf-live-community-own-report__withdraw-error`)).toEqual({});
  });

  it("gives only the pilot report receipt checkmark its approved green treatment", () => {
    expect(declarationsFor(`${receiptRoot} .mf-live-report-success--pilot-receipt .mf-live-report-success__icon`))
      .toEqual({
        background: "rgba(34, 197, 94, 0.16)",
        color: "#86efac",
        "box-shadow": "none",
      });
  });

  it("does not restyle the blue map CTA or overwrite global button/color tokens", () => {
    expect(section).not.toMatch(/mf-live-report-map-action|mf-button|mf-app-button|AppButton/);
    expect(section).not.toMatch(/--mf-(?:blue|ink|muted|surface|gold)(?:[\w-]*)\s*:/);
    expect(section).not.toContain(".mf-live-report-form__footer");
  });

  it.each([
    ["receipt modal", "#0b2742"],
    ["community map base", "#0a2b3d"],
    ["community map rendered popup", "#1a263b"],
  ])("keeps composited text and success icon contrast readable on the real %s surface", (_name, surface) => {
    // Read every proposed foreground/fill from CSS; only the real opaque
    // parent surfaces are fixtures. Composite in sRGB before linearizing.
    const base = color(surface);
    const card = composite(color(tokens["--mf-community-card-bg"]), base);
    const aliasPill = composite(color(tokens["--mf-community-alias-bg"]), card);
    const successIcon = declarationsFor(
      `${receiptRoot} .mf-live-report-success--pilot-receipt .mf-live-report-success__icon`,
    );
    const successBackground = composite(color(successIcon.background), base);
    expect(contrast(color(tokens["--mf-community-secondary"]), base)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(color(tokens["--mf-community-secondary"]), card)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(color(tokens["--mf-community-alias-text"]), aliasPill)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(color(successIcon.color), successBackground)).toBeGreaterThanOrEqual(3);
    for (const action of ["action", "danger", "neutral"]) {
      const actionBackground = composite(color(tokens[`--mf-community-${action}-bg`]), card);
      expect(contrast(color(tokens[`--mf-community-${action}-text`]), actionBackground), action)
        .toBeGreaterThanOrEqual(4.5);
    }
  });
});
