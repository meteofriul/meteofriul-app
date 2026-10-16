import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave44.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 44", () => {
  it("assigns exactly one controlled decision to all fifteen candidates", () => {
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
      secondaryRequiresPrimaryAnchor: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
      publishAfterFurOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 10,
      primary: 2,
      secondary: 8,
      hold: 2,
      excluded: 3,
      canonicalPrimaryDatesBefore: 268,
      canonicalPrimaryDatesAfter: 270,
      currentVisiblePrimaryCoverage: 263,
    });
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(15);
  });

  it("publishes only Pieri and Bulfoni as new primary memories", () => {
    const primaries = reviewWave.keepDaily.filter((record) => record.dailyRole === "primary");

    expect(primaries.map((record) => record.id)).toEqual([
      "master-fvg-06-02-Q3763134",
      "master-fvg-06-11-Q5295407",
    ]);
    expect(new Set(primaries.map((record) => record.dateIt))).toEqual(new Set(["06-02", "06-11"]));
  });

  it("keeps every other approved profile secondary to an existing date anchor", () => {
    const secondaries = reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary");

    expect(secondaries).toHaveLength(8);
    for (const selected of secondaries) {
      const dateKey = toRuntimeDateKey(selected.dateIt);
      const existingPrimary = localMemory.records.find((record) => (
        record.candidateId !== selected.id
        && record.dailyRole !== "secondary"
        && record.primaryUse === "discover"
        && record.readyForUi === true
        && record.dateAnchors?.includes(dateKey)
      ));

      expect(existingPrimary, `missing primary anchor for ${selected.id}`).toBeTruthy();
    }
  });

  it("publishes all ten selections only after approved bilingual review", () => {
    for (const selected of reviewWave.keepDaily) {
      const canonicalRecords = localMemory.records.filter((record) => record.candidateId === selected.id);

      expect(canonicalRecords).toHaveLength(1);
      expect(canonicalRecords[0]).toMatchObject({
        dailyRole: selected.dailyRole,
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
      expect(["PN", "TS", "UD"]).toContain(selected.province);
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
      expect(selected.sourceUrl).not.toContain("wikidata.org");
      expect(selected.copyIt).toContain(String(selected.year));
    }
  });

  it("does not publish held or excluded profiles", () => {
    const blockedIds = [
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];
    const canonicalCandidateIds = new Set(localMemory.records.map((record) => record.candidateId));

    expect(blockedIds).toHaveLength(5);
    for (const blockedId of blockedIds) expect(canonicalCandidateIds.has(blockedId)).toBe(false);
    expect(reviewWave.excluded.map((record) => record.id)).toContain("master-fvg-07-02-Q3737787");
  });
});
