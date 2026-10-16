import { describe, expect, it } from "vitest";

import review from "../../data/discover/dailyHistoryHistoricalEventsReview.json";
import { getDailyHistoryHistoricalEventsReviewAudit } from "./dailyHistoryHistoricalEventsReview";

describe("daily history historical events review", () => {
  it("keeps historical event staging unpublished and event-only", () => {
    const audit = getDailyHistoryHistoricalEventsReviewAudit(review);

    expect(review.purpose).toContain("Non letto dalla UI");
    expect(review.policy).toMatchObject({
      doNotPublishFromThisFile: true,
      historicalEventsBeforeSimpleBirths: true,
      dateFormat: "DD-MM",
      requiresHumanReview: true,
      requiresFurReview: true,
      furWorkDeferredUntilItalianSelectionConfirmed: true,
    });
    expect(audit).toMatchObject({
      schemaVersion: 1,
      totalRecords: 12,
      readyForUiRecords: 0,
      nonEventRecords: [],
      deathRecords: [],
      duplicateWikidataIds: [],
      invalidItalianDates: [],
    });
  });

  it("separates usable copy candidates from broad historical holds", () => {
    const audit = getDailyHistoryHistoricalEventsReviewAudit(review);

    expect(audit.byDecision).toEqual({
      copy_candidate: 3,
      evergreen_archive_candidate: 1,
      hold_strong_source: 6,
      hold_duplicate_theme: 1,
      discard_entity_not_event: 1,
    });
    expect(audit.bySurface).toEqual({
      memory_of_the_day: 3,
      discover_archive: 1,
      hold: 8,
    });
    expect(audit.copyCandidates).toBe(3);
    expect(audit.evergreenArchiveCandidates).toBe(1);
    expect(audit.copyCandidatesNeedingFur).toBe(3);
    expect(audit.copyCandidatesWithDeferredFur).toBe(3);
  });
});
