import { describe, expect, it } from "vitest";

import review from "../../data/discover/dailyHistoryProminentProfilesReview.json";
import { getDailyHistoryProminentProfilesReviewAudit } from "./dailyHistoryProminentProfilesReview";

describe("daily history prominent profiles review", () => {
  it("keeps the prominent profile batch unpublished and free of deaths", () => {
    const audit = getDailyHistoryProminentProfilesReviewAudit(review);

    expect(review.purpose).toContain("Non letto dalla UI");
    expect(review.policy).toMatchObject({
      doNotPublishFromThisFile: true,
      excludeDeaths: true,
      avoidGenericMediaProfiles: true,
      dateFormat: "DD-MM",
      requiresHumanReview: true,
      requiresFurReview: true,
      furWorkDeferredUntilItalianSelectionConfirmed: true,
    });
    expect(audit).toMatchObject({
      schemaVersion: 1,
      totalRecords: 34,
      readyForUiRecords: 0,
      deathRecords: [],
      eventRecords: [],
      duplicateWikidataIds: [],
      invalidItalianDates: [],
    });
  });

  it("separates new copy work from already staged Discover records", () => {
    const audit = getDailyHistoryProminentProfilesReviewAudit(review);

    expect(audit.byDecision).toEqual({
      reuse_existing_local_memory: 5,
      upgrade_existing_local_memory: 1,
      evergreen_candidate_date_conflict: 2,
      copy_candidate: 9,
      discard_below_prominence_threshold: 1,
      it_review_candidate: 9,
      it_archive_review_candidate: 3,
      hold_source_significance: 2,
      hold_niche_profile: 1,
      hold_for_living_person_review: 1,
    });
    expect(audit.bySurface).toEqual({
      memory_of_the_day: 21,
      discover_archive: 8,
      hold: 5,
    });
    expect(audit.newCopyCandidates).toBe(9);
    expect(audit.newCopyCandidatesNeedingFur).toBe(9);
    expect(audit.newCopyCandidatesWithDeferredFur).toBe(9);
    expect(audit.italianReviewCandidates).toBe(9);
    expect(audit.italianReviewCandidatesWithFurStarted).toBe(0);
    expect(audit.italianArchiveReviewCandidates).toBe(3);
    expect(audit.italianArchiveReviewCandidatesWithFurStarted).toBe(0);
    expect(audit.belowProminenceThresholdRecords).toEqual([
      "profile-copy-0301-nico-naldini",
    ]);
    expect(audit.existingReuseRecords).toBe(5);
    expect(audit.upgradeExistingRecords).toBe(1);
  });
});
