import { describe, expect, it } from "vitest";

import { getProverbRepertoireMatrix } from "./proverbRepertoireMatrix";

describe("proverb repertoire matrix", () => {
  it("measures the real gap between published proverbs, candidates, and the yearly target", () => {
    const matrix = getProverbRepertoireMatrix();

    expect(matrix.target).toMatchObject({
      archiveMinimum: 500,
      dailySlots: 366,
      distinctDailyProverbs: 366,
    });
    expect(matrix.published.total).toBe(379);
    expect(matrix.published.almanacEligible).toBe(369);
    expect(matrix.candidates.total).toBe(122);
    expect(matrix.candidates.alreadyPublished).toBe(83);
    expect(matrix.candidates.unpublished).toBe(39);
    expect(matrix.totals.rawCombinedRecords).toBe(501);
    expect(matrix.totals.uniqueWorkingRecords).toBe(418);
    expect(matrix.gaps.publishedArchiveGap).toBe(121);
    expect(matrix.gaps.workingArchiveGap).toBe(82);
    expect(matrix.gaps.distinctPublishedProverbGap).toBe(0);
    expect(matrix.gaps.distinctEligibleProverbGap).toBe(0);
    expect(matrix.gaps.distinctWorkingProverbGap).toBe(0);
    expect(matrix.totals.isArchiveReady).toBe(false);
    expect(matrix.totals.isWorkingArchiveReady).toBe(false);
    expect(matrix.totals.hasDistinctProverbForEveryDay).toBe(true);
  });

  it("keeps fixed daily coverage separate from monthly, seasonal, and weather rotations", () => {
    const matrix = getProverbRepertoireMatrix();

    expect(matrix.calendar.scheduledDateAnchorCount).toBe(33);
    expect(matrix.calendar.candidateDateAnchorCount).toBe(35);
    expect(matrix.calendar.knownDateAnchorCount).toBe(41);
    expect(matrix.calendar.missingKnownDateAnchors).toBe(325);
    expect(matrix.gaps.dailyScheduleGap).toBe(333);
    expect(matrix.totals.isDailyCalendarReady).toBe(false);
  });

  it("shows where the dated candidate coverage is thin by month", () => {
    const matrix = getProverbRepertoireMatrix();

    expect(matrix.calendar.byMonth["01"]).toMatchObject({
      knownDateAnchors: 9,
      scheduledDateAnchors: 7,
    });
    expect(matrix.calendar.byMonth["04"]).toMatchObject({
      knownDateAnchors: 1,
      scheduledDateAnchors: 1,
    });
    expect(matrix.calendar.byMonth["12"]).toMatchObject({
      knownDateAnchors: 6,
      scheduledDateAnchors: 4,
    });
    expect(matrix.calendar.weakMonths).toEqual(["04", "10"]);
  });

  it("separates raw candidate buckets from already published almanac buckets", () => {
    const matrix = getProverbRepertoireMatrix();

    expect(matrix.published.byTargetUse).toMatchObject({
      almanac_dated: 17,
      almanac_monthly: 23,
      almanac_seasonal: 6,
      almanac_weather_sign: 15,
      almanac_lunar_cycle: 4,
      almanac_movable_feast: 6,
      almanac_date_range: 3,
      generic: 305,
    });
    expect(matrix.candidates.byReviewStatus).toMatchObject({
      candidate: 14,
      source_checked: 108,
    });
    expect(matrix.candidates.byInferredBucket).toMatchObject({
      dated: 45,
      movable_date: 4,
      monthly: 3,
      seasonal: 17,
      weather_sign: 53,
    });
    expect(matrix.candidates.withSourcePage).toBe(122);
    expect(matrix.candidates.withFur).toBe(118);
  });

  it("tracks remaining Ostermann source pages after the extraction tranches", () => {
    const matrix = getProverbRepertoireMatrix();

    expect(matrix.sourcePlan).toMatchObject({
      extractedPages: 39,
      discoverBacklogPages: 3,
      closedPages: 42,
      priorityPages: 36,
      totalPages: 42,
      unextractedPages: [],
    });
  });
});
