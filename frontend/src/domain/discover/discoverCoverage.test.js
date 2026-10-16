import { describe, expect, it } from "vitest";

import { getDiscoverCoverageSummary } from "./discoverCoverage";

describe("discover content coverage", () => {
  it("measures Scopri as a complete exact-date memory calendar plus daily rotation", () => {
    const summary = getDiscoverCoverageSummary();

    expect(summary.dailyTarget).toBe(366);
    expect(summary.discover.curatedReady).toBe(109);
    expect(summary.discover.curatedFurApproved).toBe(109);
    expect(summary.discover.localMemoryReady).toBe(567);
    expect(summary.discover.localMemoryExactDateDays).toBe(366);
    expect(summary.discover.localMemoryAllExactDateDays).toBe(366);
    expect(summary.discover.localMemorySecondaryReady).toBe(198);
    expect(summary.discover.localMemoryMissingDays).toHaveLength(0);
    expect(summary.discover.localMemoryRotationRecords).toBe(3);
    expect(summary.discover.traditionalSayingsReady).toBe(80);
    expect(summary.discover.traditionalSayingsExactDateDays).toBe(8);
    expect(summary.discover.traditionalSayingsDailySelectionDays).toBe(366);
    expect(summary.discover.traditionalSayingsMissingDays).toHaveLength(0);
    expect(summary.discover.backlogRecords).toBe(29);
    expect(summary.discover.backlogReadyForUi).toBe(0);
    expect(summary.readiness.discoverHasDailyRotationPool).toBe(true);
    expect(summary.readiness.discoverExactDateCalendarReady).toBe(false);
    expect(summary.readiness.discoverDailyExperienceReady).toBe(true);
    expect(summary.readiness.localMemoryCalendarReady).toBe(true);
    expect(summary.readiness.traditionalSayingsCalendarReady).toBe(false);
    expect(summary.readiness.traditionalSayingsDailySelectionReady).toBe(true);
  });
  it("does not mix Almanacco readiness into Scopri coverage", () => {
    const summary = getDiscoverCoverageSummary();

    expect(summary).not.toHaveProperty("almanac");
    expect(summary.readiness).not.toHaveProperty("proverbDailyCalendarReady");
    expect(summary.readiness).not.toHaveProperty("almanacBaseReady");
  });

  it("does not count explicitly blocked curated records", () => {
    const summary = getDiscoverCoverageSummary({
      culturalDiscoverRecords: [{
        id: "blocked-ready-record",
        editorialStatus: "ready_it",
        languageStatus: { fur: "approved" },
        readyForUi: false,
      }],
      localMemorySource: { records: [] },
      ostermannBacklogSource: { records: [] },
      traditionalSayingsSource: { records: [] },
    });

    expect(summary.discover.curatedReady).toBe(0);
    expect(summary.readiness.discoverHasDailyRotationPool).toBe(false);
  });
});
