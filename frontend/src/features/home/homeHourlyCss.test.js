import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");

describe("Home hourly horizontal scroller", () => {
  it("uses a single scrollable row without shrinking all 48 slots onto the screen", () => {
    const rule = css.match(/^\.mf-home-hourly__grid\s*\{([^}]+)\}/m)?.[1] || "";

    expect(rule).toContain("grid-auto-flow: column");
    expect(rule).toContain("grid-auto-columns: clamp(64px,");
    expect(rule).toContain("overflow-x: auto");
    expect(rule).toContain("scrollbar-width: none");
    expect(rule).toContain("calc((100% - 36px) / 6)");
    expect(rule).not.toContain("grid-template-columns: repeat(6,");
    expect(rule).not.toContain("touch-action: pan-x");
  });

  it("hides the scrollbar without adding an empty track or losing scrolling", () => {
    const grid = css.match(/^\.mf-home-hourly__grid\s*\{([^}]+)\}/m)?.[1] || "";
    const scrollbar = css.match(/^\.mf-home-hourly__grid::-webkit-scrollbar\s*\{([^}]+)\}/m)?.[1] || "";

    expect(scrollbar).toContain("display: none");
    expect(grid).not.toContain("padding-bottom");
    expect(css).not.toContain(".mf-home-hourly__header");
  });

  it.each(["mf-home-view", "mf-home-now", "mf-home-hourly"])(
    "lets %s contain horizontal overflow without widening Home",
    (className) => {
      const rule = css.match(new RegExp(`^\\.${className}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";

      expect(rule).toContain("min-width: 0");
    },
  );

  it("provides visible keyboard focus and a day boundary", () => {
    expect(css).toContain(".mf-home-hourly__grid:focus-visible");
    expect(css).toContain(".mf-home-hourly__slot--new-day");
  });
});
