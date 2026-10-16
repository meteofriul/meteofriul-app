import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave51.json";

describe("Discover daily Italian review wave 51", () => {
  it("assigns exactly one controlled decision to all fifteen candidates", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.policy).toMatchObject({
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      rejectBirthplaceOnlyProfiles: true,
      rejectSemanticDuplicates: true,
      rejectInternallyInconsistentSources: true,
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

  it("links eleven semantic duplicates to published canonical memories", () => {
    const duplicates = reviewWave.excluded.filter((record) => record.duplicateOf);

    expect(duplicates).toHaveLength(11);
    for (const duplicate of duplicates) {
      const canonical = localMemory.records.find((record) => record.id === duplicate.duplicateOf);

      expect(canonical, `missing canonical record ${duplicate.duplicateOf}`).toBeTruthy();
      expect(canonical.readyForUi).toBe(true);
      expect(canonical.primaryUse).toBe("discover");
    }
  });

  it("leaves the Camagni draft unpublished instead of duplicating it", () => {
    const camagni = reviewWave.excluded.find((record) => record.id === "master-fvg-25-03-Q3769521");
    const draft = localMemory.records.find((record) => record.id === camagni.existingDraft);

    expect(draft).toBeTruthy();
    expect(draft.readyForUi).toBe(false);
    expect(draft.languageStatus.fur).not.toBe("approved");
    expect(camagni.reason).toContain("non supera la soglia editoriale");
  });

  it("rejects ordinary relevance and the internally inconsistent historical record", () => {
    const dellaTorre = reviewWave.excluded.find((record) => record.id === "master-fvg-01-05-Q27150629");
    const genericIds = reviewWave.excluded
      .filter((record) => record.id === "master-fvg-11-06-Q27986842" || record.id === "master-fvg-12-08-Q3767101")
      .map((record) => record.id);

    expect(dellaTorre.reason).toContain("incoerenza cronologica");
    expect(dellaTorre.reason).toContain("1263");
    expect(genericIds).toEqual([
      "master-fvg-11-06-Q27986842",
      "master-fvg-12-08-Q3767101",
    ]);
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
