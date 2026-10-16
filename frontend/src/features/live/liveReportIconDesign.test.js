import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("./live.css", import.meta.url), "utf8");

const reportPalettes = {
  fog: {
    end: "#475569",
    shadow: "rgba(71, 85, 105, 0.3)",
    start: "#94A3B8",
    startRgb: "148, 163, 184",
  },
  hail: {
    end: "#4F46E5",
    shadow: "rgba(79, 70, 229, 0.36)",
    start: "#818CF8",
    startRgb: "129, 140, 248",
  },
  ice: {
    end: "#0284C7",
    shadow: "rgba(13, 148, 136, 0.35)",
    start: "#2DD4BF",
    startRgb: "45, 212, 191",
  },
  quiet: {
    end: "#059669",
    shadow: "rgba(5, 150, 105, 0.35)",
    start: "#34D399",
    startRgb: "52, 211, 153",
  },
  rain: {
    end: "#2563EB",
    shadow: "rgba(37, 99, 235, 0.35)",
    start: "#60A5FA",
    startRgb: "96, 165, 250",
  },
  snow: {
    end: "#0284C7",
    shadow: "rgba(2, 132, 199, 0.32)",
    start: "#38BDF8",
    startRgb: "56, 189, 248",
  },
  storm: {
    end: "#6D28D9",
    shadow: "rgba(124, 58, 237, 0.38)",
    start: "#A855F7",
    startRgb: "168, 85, 247",
  },
  wind: {
    end: "#7C3AED",
    shadow: "rgba(147, 51, 234, 0.38)",
    start: "#C084FC",
    startRgb: "192, 132, 252",
  },
};

function parseDeclarations(body) {
  const declarations = {};
  const declarationPattern = /(?:^|;)\s*([\w-]+)\s*:\s*([^;]+)/g;

  for (const match of body.matchAll(declarationPattern)) {
    declarations[match[1]] = match[2].trim();
  }

  return declarations;
}

function parseRules(source) {
  const withoutComments = source.replace(/\/\*[\s\S]*?\*\//g, "");
  return [...withoutComments.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((match) => ({
    declarations: parseDeclarations(match[2]),
    selectors: match[1].split(",").map((selector) => selector.trim()),
  }));
}

const rules = parseRules(css);

function styleFor(...selectors) {
  const declarations = {};

  rules.forEach((rule) => {
    if (rule.selectors.some((selector) => selectors.includes(selector))) {
      Object.assign(declarations, rule.declarations);
    }
  });

  return declarations;
}

function resolveCustomProperties(value, declarations) {
  let resolved = value || "";

  for (let attempt = 0; attempt < 12; attempt += 1) {
    const next = resolved.replace(/var\(\s*(--[\w-]+)\s*\)/g, (reference, property) => (
      declarations[property] ?? reference
    ));
    if (next === resolved) break;
    resolved = next;
  }

  return resolved;
}

function canonical(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/\s*([(),])\s*/g, "$1")
    .trim();
}

function resolvedDeclaration(style, ...properties) {
  const property = properties.find((candidate) => style[candidate]);
  return canonical(resolveCustomProperties(property ? style[property] : "", style));
}

function expectPaletteBadge(style, palette) {
  const background = resolvedDeclaration(style, "background", "background-image");
  const shadow = resolvedDeclaration(style, "box-shadow");

  expect(background).toContain(canonical(
    `linear-gradient(135deg, ${palette.start}, ${palette.end})`,
  ));
  expect(shadow).toContain(canonical(`0 6px 14px ${palette.shadow}`));
}

function expectSixPercentTint(background, palette) {
  const colorMix = canonical(`${palette.start} 6%`);
  const rgba = canonical(`rgba(${palette.startRgb}, 0.06)`);

  expect(
    background.includes(colorMix) || background.includes(rgba),
    `expected a 6% ${palette.start} tint in: ${background}`,
  ).toBe(true);
}

describe("modern live-report icon badges", () => {
  it("keeps the ordinary composer on its legacy neutral treatment", () => {
    const option = styleFor(".mf-live-report-option");
    const badge = styleFor(".mf-live-report-option", ".mf-live-report-option > span");

    expect(resolvedDeclaration(option, "--mf-live-report-color")).toBe("#087b71");
    expect(resolvedDeclaration(option, "--mf-live-report-soft")).toBe("#e4f4f1");
    expect(resolvedDeclaration(option, "background")).toBe("var(--mf-surface)");
    expect(resolvedDeclaration(badge, "background", "background-image")).toBe("#e4f4f1");
    expect(resolvedDeclaration(badge, "color")).toBe("#087b71");
  });

  it("scopes the glossy white-glyph badge treatment to the pilot report form", () => {
    const scopedOption = styleFor(".mf-live-report-form--pilot .mf-live-report-option");
    const scopedBadge = styleFor(".mf-live-report-form--pilot .mf-live-report-option > span");
    const badge = styleFor(
      ".mf-live-report-option",
      ".mf-live-report-option > span",
      ".mf-live-report-form--pilot .mf-live-report-option",
      ".mf-live-report-form--pilot .mf-live-report-option > span",
    );

    expect(Object.keys(scopedOption)).not.toHaveLength(0);
    expect(resolvedDeclaration(scopedBadge, "background", "background-image"))
      .toContain("linear-gradient(135deg");
    expect(resolvedDeclaration(badge, "border-radius")).toMatch(/^(?:12|13|14)px$/);
    expect(resolvedDeclaration(badge, "border-top")).toBe(
      canonical("1px solid rgba(255, 255, 255, 0.45)"),
    );
    expect(resolvedDeclaration(badge, "color")).toMatch(/^(?:#fff|#ffffff|white)$/);
  });

  it.each(Object.entries(reportPalettes))(
    "uses the DOCX %s gradient and glow in the pilot form badge",
    (type, palette) => {
      const scopedPalette = styleFor(
        `.mf-live-report-form--pilot .mf-live-report-option--${type}`,
      );
      const badge = styleFor(
        ".mf-live-report-option",
        ".mf-live-report-option > span",
        `.mf-live-report-option--${type}`,
        ".mf-live-report-form--pilot .mf-live-report-option",
        ".mf-live-report-form--pilot .mf-live-report-option > span",
        `.mf-live-report-form--pilot .mf-live-report-option--${type}`,
      );

      const scopedPaletteValues = canonical(Object.values(scopedPalette).join(";"));
      expect(scopedPaletteValues).toContain(canonical(palette.start));
      expect(scopedPaletteValues).toContain(canonical(palette.end));
      expect(scopedPaletteValues).toContain(canonical(palette.shadow));
      expectPaletteBadge(badge, palette);
    },
  );

  it("keeps the selected-state treatment inside the pilot modifier", () => {
    const activeOption = styleFor(
      ".mf-live-report-form--pilot .mf-live-report-option.is-active",
    );
    const activeBadge = styleFor(
      ".mf-live-report-form--pilot .mf-live-report-option.is-active > span",
    );
    const optionValues = canonical(Object.values(activeOption).join(";"));

    expect(optionValues).toContain("2px");
    expect(optionValues).toContain("6%");
    expect(resolvedDeclaration(activeBadge, "transform")).toBe("scale(1.05)");
    expect(resolvedDeclaration(activeBadge, "box-shadow")).not.toBe("");
  });

  it.each(Object.entries(reportPalettes))(
    "uses a 2px %s selection edge, 6% tint and stronger badge glow",
    (type, palette) => {
      const option = styleFor(
        ".mf-live-report-option",
        ".mf-live-report-option.is-active",
        `.mf-live-report-option--${type}`,
        ".mf-live-report-form--pilot .mf-live-report-option",
        ".mf-live-report-form--pilot .mf-live-report-option.is-active",
        `.mf-live-report-form--pilot .mf-live-report-option--${type}`,
      );
      const normalBadge = styleFor(
        ".mf-live-report-option",
        ".mf-live-report-option > span",
        `.mf-live-report-option--${type}`,
        ".mf-live-report-form--pilot .mf-live-report-option",
        ".mf-live-report-form--pilot .mf-live-report-option > span",
        `.mf-live-report-form--pilot .mf-live-report-option--${type}`,
      );
      const activeBadge = styleFor(
        ".mf-live-report-option",
        ".mf-live-report-option > span",
        ".mf-live-report-option.is-active",
        ".mf-live-report-option.is-active > span",
        `.mf-live-report-option--${type}`,
        ".mf-live-report-form--pilot .mf-live-report-option",
        ".mf-live-report-form--pilot .mf-live-report-option > span",
        ".mf-live-report-form--pilot .mf-live-report-option.is-active",
        ".mf-live-report-form--pilot .mf-live-report-option.is-active > span",
        `.mf-live-report-form--pilot .mf-live-report-option--${type}`,
      );
      const borderContract = canonical([
        resolvedDeclaration(option, "border"),
        resolvedDeclaration(option, "border-width"),
        resolvedDeclaration(option, "border-color"),
      ].join(" "));
      const activeBackground = resolvedDeclaration(option, "background", "background-color");
      const normalShadow = resolvedDeclaration(normalBadge, "box-shadow");
      const activeShadow = resolvedDeclaration(activeBadge, "box-shadow");

      expect(borderContract).toContain("2px");
      expect(borderContract).toContain(canonical(palette.start));
      expectSixPercentTint(activeBackground, palette);
      expect(resolvedDeclaration(activeBadge, "transform")).toBe("scale(1.05)");
      expect(activeShadow).not.toBe("");
      expect(activeShadow).not.toBe(normalShadow);
      expect(activeShadow).toContain(canonical(palette.shadow));
      expect(resolvedDeclaration(activeBadge, "color")).toMatch(/^(?:#fff|#ffffff|white)$/);
    },
  );

  it.each(Object.entries(reportPalettes))(
    "keeps the %s detail-card icon on the same DOCX palette",
    (type, palette) => {
      const detailBadge = styleFor(
        ".mf-territory-map__report-type-icon",
        `.mf-territory-map__report-type-icon--${type}`,
      );

      expectPaletteBadge(detailBadge, palette);
      expect(resolvedDeclaration(detailBadge, "border-radius")).toMatch(/^(?:12|13|14)px$/);
      expect(resolvedDeclaration(detailBadge, "border-top")).toBe(
        canonical("1px solid rgba(255, 255, 255, 0.45)"),
      );
      expect(resolvedDeclaration(detailBadge, "color")).toMatch(/^(?:#fff|#ffffff|white)$/);
    },
  );

  it.each(Object.entries(reportPalettes))(
    "keeps round %s map markers on the same report-icon palette",
    (type, palette) => {
      const surfaces = [
        {
          bases: [
            ".mf-live-community-map__marker",
            ".mf-live-community-map--immersive .mf-live-community-map__marker",
            ".mf-live-community-map-layer--pilot .mf-live-community-map--immersive "
              + ".mf-live-community-map__marker",
          ],
          category: ".mf-live-community-map-layer--pilot .mf-live-community-map--immersive "
            + `.mf-live-community-map__marker.mf-live-community-map__marker--${type}`,
        },
        {
          bases: [
            ".mf-live-community-map__marker",
            ".mf-live-community-map-layer--inline.mf-live-territory-workspace "
              + ".mf-territory-map .mf-live-community-map__marker",
          ],
          category: ".mf-live-community-map-layer--inline.mf-live-territory-workspace "
            + ".mf-territory-map .mf-live-community-map__marker"
            + `.mf-live-community-map__marker--${type}`,
        },
      ];

      surfaces.forEach(({ bases, category }) => {
        const marker = {
          ...styleFor(...bases),
          ...styleFor(category),
        };

        expectPaletteBadge(marker, palette);
        expect(resolvedDeclaration(marker, "border-radius")).toBe("50%");
        expect(resolvedDeclaration(marker, "border-top")).toBe(
          canonical("1px solid rgba(255, 255, 255, 0.45)"),
        );
        expect(resolvedDeclaration(marker, "color")).toMatch(/^(?:#fff|#ffffff|white)$/);
      });
    },
  );
});
