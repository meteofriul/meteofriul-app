import { describe, expect, it } from "vitest";

import { getDailyHistoryBatchReviewAudit } from "./dailyHistoryBatchReview";

describe("daily history batch review", () => {
  it("tracks the sixteen strong candidates without publishing them", () => {
    const audit = getDailyHistoryBatchReviewAudit();

    expect(audit).toMatchObject({
      schemaVersion: 1,
      totalRecords: 16,
      dateErrors: [],
      byBatchStatus: {
        archive_candidate: 1,
        hold_duplicate_theme: 2,
        local_secondary_candidate: 2,
        ready_for_copy: 2,
        source_lead_found: 9,
      },
      bySurface: {
        archive_or_context: 1,
        hold: 2,
        main_memory_candidate: 11,
        secondary_or_archive: 2,
      },
      mainMemoryCandidates: 11,
      actionableMainCandidates: 11,
      recordsWithSourceLeads: 10,
      readyForCopyIds: [
        "wikidata-fvg-09-10-Q3709251",
        "wikidata-fvg-26-04-Q3625507",
      ],
      holdIds: [
        "wikidata-fvg-21-03-Q4872512",
        "wikidata-fvg-29-07-Q21235600",
      ],
    });
  });

  it("keeps province distribution visible for localized secondary work", () => {
    const audit = getDailyHistoryBatchReviewAudit();

    expect(audit.byProvince).toMatchObject({
      GO: 2,
      PN: 3,
      TS: 3,
      UD: 8,
    });
  });
});
