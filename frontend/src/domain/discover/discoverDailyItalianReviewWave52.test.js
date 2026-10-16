import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave52.json";

describe("Discover daily Italian review wave 52", () => {
  it("assigns exactly one controlled decision to all fifteen candidates", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.policy).toMatchObject({
      excludeGenericPoliticalProfiles: true,
      excludeSportsOnlyProfiles: true,
      allowExceptionalSportsProfiles: true,
      rejectSemanticDuplicates: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 0,
      primary: 0,
      secondary: 0,
      hold: 0,
      excluded: 15,
      canonicalPrimaryDatesBefore: 274,
      canonicalPrimaryDatesAfter: 274,
      currentVisiblePrimaryCoverage: 269,
    });
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(15);
  });

  it("links twelve semantic duplicates to published canonical memories", () => {
    const duplicates = reviewWave.excluded.filter((record) => record.duplicateOf);

    expect(duplicates).toHaveLength(12);
    for (const duplicate of duplicates) {
      const canonical = localMemory.records.find((record) => record.id === duplicate.duplicateOf);

      expect(canonical, `missing canonical record ${duplicate.duplicateOf}`).toBeTruthy();
      expect(canonical.readyForUi).toBe(true);
      expect(canonical.primaryUse).toBe("discover");
    }
  });

  it("applies the agreed relevance thresholds to politics and sport", () => {
    const pascolat = reviewWave.excluded.find((record) => record.id === "master-fvg-11-12-Q108620032");
    const sports = reviewWave.excluded.filter((record) => (
      record.id === "master-fvg-23-08-Q332742" || record.id === "master-fvg-08-03-Q2705256"
    ));

    expect(pascolat.reason).toContain("soltanto come politico");
    expect(sports).toHaveLength(2);
    expect(sports.every((record) => record.reason.includes("sportiv") || record.reason.includes("calcistic"))).toBe(true);
    expect(sports.every((record) => record.reason.includes("eccezionale"))).toBe(true);
  });

  it("does not stage records and keeps calendar coverage unchanged", () => {
    const canonicalDates = new Set(
      localMemory.records
        .filter((record) => record.primaryUse === "discover" && record.dailyRole !== "secondary")
        .flatMap((record) => record.dateAnchors || []),
    );
    const visibleDates = new Set(
      localMemory.records
        .filter((record) => (
          record.primaryUse === "discover"
          && record.dailyRole !== "secondary"
          && record.readyForUi === true
        ))
        .flatMap((record) => record.dateAnchors || []),
    );

    expect(reviewWave.keepDaily).toEqual([]);
    expect(reviewWave.hold).toEqual([]);
    expect(canonicalDates.size).toBeGreaterThanOrEqual(reviewWave.summary.canonicalPrimaryDatesAfter);
    expect(visibleDates.size).toBeGreaterThanOrEqual(reviewWave.summary.currentVisiblePrimaryCoverage);
  });
});
