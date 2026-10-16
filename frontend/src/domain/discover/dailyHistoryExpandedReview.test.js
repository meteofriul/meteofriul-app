import { describe, expect, it } from "vitest";

import expandedReview from "../../data/discover/dailyHistoryExpandedReview.json";
import { getDailyHistoryExpandedReviewAudit } from "./dailyHistoryExpandedReview";

describe("daily history expanded review pack", () => {
  it("keeps the expanded extraction unpublished and deduplicated", () => {
    const audit = getDailyHistoryExpandedReviewAudit(expandedReview);

    expect(audit).toMatchObject({
      schemaVersion: 1,
      totalRecords: 80,
      readyForUiRecords: 0,
      duplicateWikidataIds: [],
      duplicateDateAnchors: [],
      byExtractionClass: {
        archive_review: 12,
        light_daily_review: 68,
      },
      byReviewStatus: {
        archive_after_review: 34,
        copy_candidate: 23,
        hold_bad_source: 1,
        hold_strong_source: 22,
      },
      byPostReviewEditorialStatus: {
        archive_candidate_after_review: 34,
        hold_requires_strong_source: 22,
        hold_source_not_usable: 1,
        light_copy_candidate: 23,
      },
      byEditorialClass: {
        A: 13,
        B: 55,
        C: 12,
      },
      recordsNeedingItCopy: 80,
      recordsNeedingFurCopy: 80,
    });
  });

  it("keeps the extraction broad enough for review without overloading one place", () => {
    const audit = getDailyHistoryExpandedReviewAudit(expandedReview);

    expect(audit.byCategory).toMatchObject({
      arte_cultura: 28,
      luoghi_patrimonio: 13,
      memoria_storica: 28,
    });
    expect(Math.max(...Object.values(audit.byPlace))).toBeLessThanOrEqual(10);
  });

  it("normalizes reviewed titles as readable strings", () => {
    const records = expandedReview.records || [];

    expect(records.every((record) => typeof record.title === "string" && record.title.length > 0)).toBe(true);
    expect(records.some((record) => record.title.includes("[object Object]"))).toBe(false);
  });
});
