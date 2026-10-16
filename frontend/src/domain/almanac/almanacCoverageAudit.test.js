import { describe, expect, it } from "vitest";

import earthTips from "../../data/almanac/earthTips.json";
import proverbs from "../../data/almanac/proverbs.json";
import saints from "../../data/almanac/saints.json";
import schedule from "../../data/almanac/schedule.json";
import culturalItems from "../../data/ostermannCulturalDiscover.json";
import { getOstermannDiscoverBacklogSummary } from "../discover/ostermannDiscoverBacklog";
import { getAnnualProverbCalendarAudit } from "./almanacData";

function getLeapYearDayKeys() {
  return Array.from({ length: 366 }, (_, index) => {
    const date = new Date(Date.UTC(2024, 0, 1 + index));
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    const day = String(date.getUTCDate()).padStart(2, "0");

    return `${month}-${day}`;
  });
}

function isAlmanacEligible(item) {
  return item?.section === "almanacco" &&
    item.editorialStatus !== "archive" &&
    item.editorialStatus !== "excluded";
}

describe("almanac 365 coverage audit", () => {
  it("keeps saint calendar coverage complete for leap-year day keys", () => {
    const missingDays = getLeapYearDayKeys().filter((dayKey) => !saints[dayKey]);

    expect(missingDays).toEqual([]);
    expect(Boolean(saints.default)).toBe(true);
  });

  it("keeps earth tips available for every month", () => {
    const monthKeys = Array.from({ length: 12 }, (_, index) => String(index + 1).padStart(2, "0"));
    const missingMonths = monthKeys.filter((monthKey) => !Array.isArray(earthTips[monthKey]));

    expect(missingMonths).toEqual([]);
    expect(monthKeys.every((monthKey) => earthTips[monthKey].length >= 2)).toBe(true);
    expect(Boolean(earthTips.default)).toBe(true);
  });

  it("keeps enough approved proverbs for a unique annual calendar and a collision reserve", () => {
    const scheduledDays = Object.keys(schedule.dailyProverbs || {}).filter((key) => key !== "default");
    const almanacEligible = proverbs.filter((proverb) => proverb.almanacEligible);
    const eligibleIds = new Set(almanacEligible.map((proverb) => proverb.id));
    const invalidScheduledDays = Object.entries(schedule.dailyProverbs || {})
      .filter(([dayKey, proverbId]) => dayKey !== "default" && !eligibleIds.has(proverbId));

    expect(scheduledDays).toHaveLength(33);
    expect(almanacEligible.length).toBeGreaterThanOrEqual(369);
    expect(invalidScheduledDays).toEqual([]);
    expect(Boolean(schedule.dailyProverbs?.default)).toBe(true);

    const commonYear = getAnnualProverbCalendarAudit(2026);
    const leapYear = getAnnualProverbCalendarAudit(2028);

    expect(commonYear).toMatchObject({ assignedDays: 365, uniqueProverbs: 365 });
    expect(leapYear).toMatchObject({ assignedDays: 366, uniqueProverbs: 366 });
  });

  it("tracks exact-date traditions separately from seasonal fallbacks", () => {
    const eligibleItems = culturalItems.filter(isAlmanacEligible);
    const exactDateDays = new Set(
      eligibleItems.flatMap((item) => (Array.isArray(item.dateAnchors) ? item.dateAnchors : [])),
    );
    const rangeItems = eligibleItems.filter((item) => Array.isArray(item.dateRanges) && item.dateRanges.length);

    expect(eligibleItems).toHaveLength(40);
    expect(exactDateDays.size).toBe(6);
    expect(rangeItems).toHaveLength(6);
  });

  it("keeps raw Ostermann backlog out of UI-ready Almanacco coverage", () => {
    const summary = getOstermannDiscoverBacklogSummary();

    expect(summary.readyForUiRecords).toBe(0);
    expect(summary.pendingFurRecords).toBe(summary.totalRecords);
  });
});
