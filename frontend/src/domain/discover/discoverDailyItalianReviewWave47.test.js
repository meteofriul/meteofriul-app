import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave47.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 47", () => {
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
      keepDaily: 11,
      primary: 1,
      secondary: 10,
      hold: 4,
      excluded: 0,
      canonicalPrimaryDatesBefore: 270,
      canonicalPrimaryDatesAfter: 271,
      currentVisiblePrimaryCoverage: 265,
    });
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(15);
  });

  it("adds one worthy primary and keeps the other selections secondary to ready anchors", () => {
    const primary = reviewWave.keepDaily.filter((record) => record.dailyRole === "primary");
    const secondary = reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary");

    expect(primary).toHaveLength(1);
    expect(primary[0]).toMatchObject({
      wikidataId: "Q3907862",
      dateIt: "13-09",
      municipality: "Udine",
    });
    expect(localMemory.records.some((record) => (
      record.candidateId !== primary[0].id
      && record.dailyRole !== "secondary"
      && record.primaryUse === "discover"
      && record.dateAnchors?.includes(toRuntimeDateKey(primary[0].dateIt))
    ))).toBe(false);

    expect(secondary).toHaveLength(10);
    for (const selected of secondary) {
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

  it("publishes the eleven selections only after approved bilingual review", () => {
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

  it("corrects source errors instead of propagating them", () => {
    const caimo = reviewWave.keepDaily.find((record) => record.wikidataId === "Q3907862");
    const segre = reviewWave.keepDaily.find((record) => record.wikidataId === "Q3616043");
    const cozzolino = reviewWave.keepDaily.find((record) => record.wikidataId === "Q18811881");

    expect(caimo).toMatchObject({ dateIt: "13-09", year: 1568, municipality: "Udine" });
    expect(caimo.sourceCorrection).toContain("23 settembre");
    expect(segre.titleIt).toContain("Segrè");
    expect(segre.sourceCorrection).toContain("grafia");
    expect(cozzolino.sourceCorrection).toContain("Vincenzo Cozzolino");
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

  it("keeps unresolved calendar conflicts blocked", () => {
    expect(reviewWave.hold.map((record) => record.id)).toEqual([
      "master-fvg-05-09-Q56488041",
      "master-fvg-10-12-Q3702596",
      "master-fvg-19-07-Q3779243",
      "master-fvg-28-06-Q3938951",
    ]);
    expect(reviewWave.hold.every((record) => (
      record.reason.includes("resta sospesa")
      || record.reason.includes("resta sospeso")
    ))).toBe(true);
    expect(reviewWave.excluded).toEqual([]);
  });
});
