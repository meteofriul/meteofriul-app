import { describe, expect, it } from "vitest";

import reviewPack from "../../data/discover/dailyHistoryReviewPack.json";
import { getDailyHistoryReviewPackAudit } from "./dailyHistoryReviewPack";

describe("daily history review pack", () => {
  it("keeps the first master review pack unpublished and review-only", () => {
    const audit = getDailyHistoryReviewPackAudit(reviewPack);

    expect(audit).toMatchObject({
      schemaVersion: 1,
      totalRecords: 25,
      readyForUiRecords: 0,
      duplicateDateAnchors: [],
      byReviewStatus: {
        archive_after_review: 11,
        hold_after_review: 2,
        copy_candidate: 6,
        review_pending: 6,
      },
      byEditorialStatus: {
        light_candidate_for_review: 19,
        light_copy_candidate: 6,
      },
      recordsNeedingItCopy: 25,
      recordsNeedingFurCopy: 25,
      recordsWithItDraft: 0,
      recordsWithFurDraft: 0,
    });
  });

  it("keeps the pack balanced enough for manual review", () => {
    const audit = getDailyHistoryReviewPackAudit(reviewPack);

    expect(audit.byCategory).toEqual({
      arte_cultura: 12,
      luoghi_patrimonio: 10,
      scienza_territorio: 3,
    });
    expect(Math.max(...Object.values(audit.byPlace))).toBeLessThanOrEqual(4);
  });
});
