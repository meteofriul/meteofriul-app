import { describe, expect, it } from "vitest";

import { getDiscoverCalendarReadinessAudit } from "./discoverCalendarReadinessAudit";

describe("discover calendar readiness audit", () => {
  it("separates ready daily content from extraction backlog", () => {
    const audit = getDiscoverCalendarReadinessAudit();

    expect(audit.dailyTarget).toBe(366);
    expect(audit.readyNow).toMatchObject({
      memoryReadyDays: 366,
      sayingReadyDays: 366,
      sayingExactDateDays: 8,
    });
    expect(audit.reviewBacklog).toMatchObject({
      historyEligibleCandidates: 1048,
      historyUnqueuedEligibleCandidates: 155,
      historyCoveredDays: 332,
      historyCoveredUnqueuedDays: 111,
      historyNextLightReviewCandidates: 0,
      historyNextLightReviewOnePerDay: true,
      ostermannBacklogRecords: 29,
      ostermannBacklogReadyForUi: 0,
    });
    expect(audit.reviewBacklog.historyFirstLightReviewDaysForMissingMemory).toEqual([]);
  });

  it("separates complete daily rotation from exact-date saying anchors", () => {
    const audit = getDiscoverCalendarReadinessAudit();

    expect(audit.gaps).toMatchObject({
      memoryMissingDays: 0,
      sayingMissingDays: 0,
      sayingExactDateMissingDays: 358,
      historySourceEmptyDays: 34,
      memoryMissingDaysWithLightReviewCandidates: 0,
      memoryMissingDaysWithUnqueuedHistoryCandidates: 0,
      memoryMissingDaysWithoutUnqueuedHistoryCandidates: 0,
    });
    expect(audit.gaps.firstMemoryMissingDaysWithoutUnqueuedHistoryCandidates).toEqual([]);
    expect(audit.reviewBacklog.historyBySuggestedReviewLane).toMatchObject({
      light_review: 182,
      hold_strong_source: 116,
      archive_review: 551,
      archive_low_priority: 199,
    });
  });
});
