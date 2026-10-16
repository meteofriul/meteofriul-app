import { describe, expect, it } from "vitest";

import {
  getDiscoverDailyCalendarPlan,
  getDiscoverDailyCalendarPlanSummary,
} from "./discoverDailyCalendarPlan";

describe("discover daily calendar plan", () => {
  it("builds one work row for each leap-year day", () => {
    const plan = getDiscoverDailyCalendarPlan();

    expect(plan).toHaveLength(366);
    expect(plan[0].dayKey).toBe("01-01");
    expect(plan.at(-1).dayKey).toBe("12-31");
  });

  it("tracks exact-date anchors separately from the everyday saying rotation", () => {
    const summary = getDiscoverDailyCalendarPlanSummary();

    expect(summary.dailyTarget).toBe(366);
    expect(summary.memoryReadyDays).toBe(366);
    expect(summary.memoryMissingDays).toBe(0);
    expect(summary.memoryMissingDayKeys).toEqual([]);
    expect(summary.sayingReadyDays).toBe(8);
    expect(summary.sayingMissingDays).toBe(358);
    expect(summary.sayingMissingDayKeys).toHaveLength(358);
  });

  it("keeps the completed memory calendar separate from the saying backlog", () => {
    const summary = getDiscoverDailyCalendarPlanSummary();

    expect(summary.january).toHaveLength(31);
    expect(summary.january[0]).toMatchObject({
      dayKey: "01-01",
      memory: {
        status: "ready",
        id: "memory-it-ready-0101-paolo-diacono-memoria-longobarda",
      },
      saying: { status: "missing_saying" },
    });
    expect(summary.firstMissingMemoryDays).toEqual([]);
    expect(summary.firstMissingSayingDays.slice(0, 3)).toEqual(["01-01", "01-03", "01-04"]);
  });

  it("maps known January saying days without mixing Almanacco records", () => {
    const plan = getDiscoverDailyCalendarPlan();
    const januarySecond = plan.find((row) => row.dayKey === "01-02");

    expect(januarySecond).toMatchObject({
      saying: {
        status: "ready",
        id: "saying-ostermann-san-macari-setembar",
      },
    });
    expect(januarySecond).not.toHaveProperty("proverb");
  });
});
