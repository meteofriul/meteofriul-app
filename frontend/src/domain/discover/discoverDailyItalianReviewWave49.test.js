import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave49.json";

describe("Discover daily Italian review wave 49", () => {
  it("assigns exactly one controlled decision to all fifteen candidates", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.policy).toMatchObject({
      excludeDeaths: true,
      rejectBirthplaceOnlyProfiles: true,
      rejectSemanticDuplicates: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
      publishAfterFurOnly: true,
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

  it("does not stage or publish records from a cleanup-only wave", () => {
    expect(reviewWave.keepDaily).toEqual([]);
    expect(reviewWave.hold).toEqual([]);

    for (const excluded of reviewWave.excluded) {
      expect(localMemory.records.some((record) => record.candidateId === excluded.id)).toBe(false);
    }
  });

  it("links fourteen semantic duplicates to their existing canonical memories", () => {
    const duplicates = reviewWave.excluded.filter((record) => record.duplicateOf);

    expect(duplicates).toHaveLength(14);
    for (const duplicate of duplicates) {
      const canonical = localMemory.records.find((record) => record.id === duplicate.duplicateOf);

      expect(canonical, `missing canonical record ${duplicate.duplicateOf}`).toBeTruthy();
      expect(canonical.readyForUi).toBe(true);
      expect(canonical.primaryUse).toBe("discover");
      expect(duplicate.reason).toMatch(/gia/i);
    }
  });

  it("rejects the remaining birthplace-only profile without filling an uncovered day", () => {
    const kircher = reviewWave.excluded.find((record) => record.id === "master-fvg-26-02-Q1748033");

    expect(kircher).toBeTruthy();
    expect(kircher.duplicateOf).toBeUndefined();
    expect(kircher.reason).toContain("nacque a Trieste");
    expect(kircher.reason).toContain("Non viene promosso soltanto");
  });

  it("keeps the canonical and visible primary-date coverage unchanged", () => {
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

    expect(canonicalDates.size).toBeGreaterThanOrEqual(reviewWave.summary.canonicalPrimaryDatesAfter);
    expect(visibleDates.size).toBeGreaterThanOrEqual(reviewWave.summary.currentVisiblePrimaryCoverage);
  });
});
