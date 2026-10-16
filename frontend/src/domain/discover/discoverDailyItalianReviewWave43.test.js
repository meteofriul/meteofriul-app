import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave43.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 43", () => {
  it("applies the strict editorial policy to all fifteen candidates", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.policy).toMatchObject({
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      excludeSportsOnlyProfiles: true,
      allowExceptionalSportsProfiles: true,
      rejectBirthplaceOnlyProfiles: true,
      rejectUncertainCalendarDates: true,
      secondaryRequiresPrimaryAnchor: true,
      publishAfterFurOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 5,
      primary: 5,
      secondary: 0,
      hold: 5,
      excluded: 5,
      canonicalPrimaryDatesBefore: 263,
      canonicalPrimaryDatesAfter: 268,
      currentVisiblePrimaryCoverage: 258,
    });
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(15);
  });

  it("publishes five new primary dates with approved bilingual copy", () => {
    for (const selected of reviewWave.keepDaily) {
      const canonicalRecords = localMemory.records.filter((record) => record.candidateId === selected.id);

      expect(selected.dailyRole).toBe("primary");
      expect(canonicalRecords).toHaveLength(1);
      expect(canonicalRecords[0]).toMatchObject({
        dailyRole: "primary",
        dateAnchors: [toRuntimeDateKey(selected.dateIt)],
        priority: selected.priority,
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
    }
  });

  it("uses explicit territories and reviewed non-Wikimedia sources", () => {
    for (const selected of reviewWave.keepDaily) {
      expect(selected.sourceStatus).toBe("pass");
      expect(selected.municipality).toBeTruthy();
      expect(selected.province).toBe("TS");
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
      expect(selected.sourceUrl).not.toContain("wikidata.org");
      expect(selected.copyIt).toContain(String(selected.year));
    }
  });

  it("keeps uncertain dates and the unanchored secondary profile unpublished", () => {
    const heldIds = new Set(reviewWave.hold.map((record) => record.id));
    const canonicalCandidateIds = new Set(localMemory.records.map((record) => record.candidateId));

    expect(heldIds).toContain("master-fvg-13-11-Q47470515");
    expect(heldIds).toContain("master-fvg-26-06-Q3634671");
    expect(heldIds).toContain("master-fvg-09-01-Q1089072");
    expect(heldIds).toContain("master-fvg-01-11-Q3639381");
    expect(heldIds).toContain("master-fvg-15-07-Q87736992");
    for (const heldId of heldIds) expect(canonicalCandidateIds.has(heldId)).toBe(false);
  });

  it("does not promote the five profiles rejected by the agreed thresholds", () => {
    const canonicalCandidateIds = new Set(localMemory.records.map((record) => record.candidateId));

    expect(reviewWave.excluded).toHaveLength(5);
    for (const excluded of reviewWave.excluded) {
      expect(canonicalCandidateIds.has(excluded.id)).toBe(false);
      expect(excluded.reason.length).toBeGreaterThan(50);
    }
  });
});
