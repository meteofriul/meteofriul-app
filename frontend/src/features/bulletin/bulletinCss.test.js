import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("./bulletin.css", import.meta.url), "utf8");

function readRule(selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`^${escapedSelector}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";
}

describe("story bulletin day tabs", () => {
  it("keeps full weekday labels readable in a horizontally scrollable row", () => {
    const scrollerRule = readRule(".mf-bulletin-tabs");
    const rowRule = readRule(".mf-bulletin-view--story .mf-bulletin-tabs .mf-tabs");
    const tabRule = readRule(".mf-bulletin-view--story .mf-bulletin-tabs .mf-tab");

    expect(scrollerRule).toContain("overflow-x: auto");
    expect(rowRule).toContain("grid-auto-columns: minmax(7em, 1fr)");
    expect(rowRule).toContain("grid-auto-flow: column");
    expect(tabRule).toContain("width: 100%");
  });
});

describe("compact pilot radar controls", () => {
  it("renders the player as one dark glass capsule with accessible targets", () => {
    const controlsRule = readRule(".mf-bulletin-radar-floating-controls");
    const playRule = readRule(
      ".mf-bulletin-radar-floating-controls .mf-bulletin-radar-play",
    );
    const compactTimelineRule = readRule(".mf-bulletin-radar-timeline--compact");
    const compactStartRule = readRule(".mf-bulletin-radar-timeline__compact-start");
    const compactRangeRule = readRule(
      ".mf-bulletin-radar-timeline--compact .mf-bulletin-radar-timeline__range",
    );

    expect(controlsRule).toContain("border-radius: 9999px");
    const playIconRule = readRule(
      ".mf-bulletin-radar-floating-controls .mf-bulletin-radar-play .lucide-play",
    );

    expect(controlsRule).toContain("background: rgba(15, 23, 42, 0.72)");
    expect(controlsRule).toContain("backdrop-filter: blur(12px) saturate(1.15)");
    expect(controlsRule).toContain("width: min(calc(100% - 24px), 360px)");
    expect(playRule).toContain("width: 44px");
    expect(playRule).toContain("min-height: 44px");
    expect(playRule).toContain("border-radius: 50%");
    expect(playRule).toContain("justify-content: center");
    expect(playIconRule).toContain("transform: translateX(1px)");
    expect(compactTimelineRule).toContain("grid-template-columns: auto minmax(0, 1fr) auto");
    expect(compactStartRule).toContain("font-size: 0.5rem");
    expect(compactStartRule).toContain("white-space: nowrap");
    expect(compactRangeRule).toContain("height: 44px");
    expect(compactRangeRule).toContain("background-size: 100% 4px");
    expect(css).toContain("repeat(var(--mf-radar-tick-segments), minmax(0, 1fr))");
    expect(css).toContain("background: #0f172a");
  });

  it("keeps the quantitative legend accessible but visually compact", () => {
    const compactScaleRule = readRule(".mf-bulletin-radar-scale--compact");
    const compactBarRule = readRule(
      ".mf-bulletin-radar-scale--compact .mf-bulletin-radar-scale__bar",
    );
    const compactLabelsRule = readRule(
      ".mf-bulletin-radar-scale--compact .mf-bulletin-radar-scale__labels",
    );
    const attributionRule = readRule(
      ".mf-bulletin-radar-window--overlay-controls .leaflet-control-attribution",
    );

    expect(compactScaleRule).toContain("gap: 3px");
    expect(compactBarRule).toContain("height: 4px");
    expect(compactLabelsRule).toContain("grid-template-columns: repeat(2, minmax(0, 1fr))");
    expect(attributionRule).toContain("margin-bottom: 68px");
  });
});
