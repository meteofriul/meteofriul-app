import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave45.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 45", () => {
  it("assigns exactly one controlled decision to all fifteen candidates", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.policy).toMatchObject({
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      rejectUncertainCalendarDates: true,
      secondaryRequiresPrimaryAnchor: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
      correctSourceDatasetErrors: true,
      publishAfterFurOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 12,
      primary: 0,
      secondary: 12,
      hold: 3,
      excluded: 0,
      canonicalPrimaryDatesBefore: 270,
      canonicalPrimaryDatesAfter: 270,
      currentVisiblePrimaryCoverage: 265,
    });
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(15);
  });

  it("keeps every approved profile secondary to an existing primary date anchor", () => {
    expect(reviewWave.keepDaily.every((record) => record.dailyRole === "secondary")).toBe(true);

    for (const selected of reviewWave.keepDaily) {
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

  it("publishes all twelve selections only after approved bilingual review", () => {
    for (const selected of reviewWave.keepDaily) {
      const canonicalRecords = localMemory.records.filter((record) => record.candidateId === selected.id);

      expect(canonicalRecords).toHaveLength(1);
      expect(canonicalRecords[0]).toMatchObject({
        dailyRole: "secondary",
        dateAnchors: [toRuntimeDateKey(selected.dateIt)],
        priority: selected.priority,
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
    }
  });

  it("records source corrections instead of propagating dataset errors", () => {
    const marinelli = reviewWave.keepDaily.find((record) => record.wikidataId === "Q1062218");
    const pizzorno = reviewWave.keepDaily.find((record) => record.wikidataId === "Q3610213");

    expect(marinelli).toMatchObject({ dateIt: "11-02", year: 1874 });
    expect(marinelli.sourceCorrection).toContain("1876");
    expect(pizzorno).toMatchObject({ dateIt: "13-07", year: 1924 });
    expect(pizzorno.sourceCorrection).toContain("1 gennaio 1924");
  });

  it("uses explicit territories and reviewed non-Wikimedia sources", () => {
    for (const selected of reviewWave.keepDaily) {
      expect(selected.sourceStatus).toBe("pass");
      expect(selected.municipality).toBeTruthy();
      expect(["GO", "PN", "TS", "UD"]).toContain(selected.province);
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
      expect(selected.sourceUrl).not.toContain("wikidata.org");
      expect(selected.copyIt).toContain(String(selected.year));
    }
  });

  it("keeps the three unresolved biographies out of canonical memory", () => {
    const heldIds = reviewWave.hold.map((record) => record.id);
    const canonicalCandidateIds = new Set(localMemory.records.map((record) => record.candidateId));

    expect(heldIds).toEqual([
      "master-fvg-14-02-Q3724205",
      "master-fvg-09-05-Q7002093",
      "master-fvg-09-09-Q3955850",
    ]);
    for (const heldId of heldIds) expect(canonicalCandidateIds.has(heldId)).toBe(false);
  });
});
