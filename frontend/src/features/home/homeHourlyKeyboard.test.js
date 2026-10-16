import { describe, expect, it } from "vitest";

import { getHourlyScrollTarget } from "./homeHourlyKeyboard";

const viewport = { scrollLeft: 100, scrollWidth: 3072, clientWidth: 384, slotWidth: 64 };

describe("Home hourly keyboard navigation", () => {
  it("moves by one hourly column with the horizontal arrows", () => {
    expect(getHourlyScrollTarget("ArrowRight", viewport)).toBe(164);
    expect(getHourlyScrollTarget("ArrowLeft", viewport)).toBe(36);
  });

  it("reaches both ends without scrolling the page vertically", () => {
    expect(getHourlyScrollTarget("Home", viewport)).toBe(0);
    expect(getHourlyScrollTarget("End", viewport)).toBe(2688);
    expect(getHourlyScrollTarget("ArrowDown", viewport)).toBeNull();
    expect(getHourlyScrollTarget("ArrowUp", viewport)).toBeNull();
    expect(getHourlyScrollTarget("Tab", viewport)).toBeNull();
  });

  it("clamps navigation at the start and the last available hour", () => {
    expect(getHourlyScrollTarget("ArrowLeft", { ...viewport, scrollLeft: 0 })).toBe(0);
    expect(getHourlyScrollTarget("ArrowRight", { ...viewport, scrollLeft: 2688 })).toBe(2688);
    expect(getHourlyScrollTarget("End", { ...viewport, scrollWidth: 200 })).toBe(0);
  });
});
