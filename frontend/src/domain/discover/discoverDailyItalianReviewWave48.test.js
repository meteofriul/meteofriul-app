import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave48.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 48", () => {
  it("assigns exactly one controlled decision to all fifteen candidates", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.policy).toMatchObject({
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      allowExceptionalSportsProfiles: true,
      rejectUncertainCalendarDates: true,
      secondaryRequiresPrimaryAnchor: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
      publishAfterFurOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 11,
      primary: 3,
      secondary: 8,
      hold: 4,
      excluded: 0,
      canonicalPrimaryDatesBefore: 271,
      canonicalPrimaryDatesAfter: 274,
      currentVisiblePrimaryCoverage: 266,
    });
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(15);
  });

  it("adds three worthy primary dates and anchors every secondary selection", () => {
    const primary = reviewWave.keepDaily.filter((record) => record.dailyRole === "primary");
    const secondary = reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary");

    expect(primary.map((record) => record.wikidataId)).toEqual([
      "Q108096676",
      "Q3749574",
      "Q2718356",
    ]);
    for (const selected of primary) {
      expect(localMemory.records.some((record) => (
        record.candidateId !== selected.id
        && record.dailyRole !== "secondary"
        && record.primaryUse === "discover"
        && record.dateAnchors?.includes(toRuntimeDateKey(selected.dateIt))
      ))).toBe(false);
    }

    expect(secondary).toHaveLength(8);
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

  it("keeps exceptional service, culture and sport while rejecting ordinary relevance", () => {
    expect(reviewWave.keepDaily.map((record) => record.wikidataId)).toEqual([
      "Q108096676",
      "Q3498004",
      "Q12795286",
      "Q23309301",
      "Q108911457",
      "Q23309339",
      "Q3749574",
      "Q3885945",
      "Q2718356",
      "Q59533663",
      "Q22682225",
    ]);
    expect(reviewWave.keepDaily.filter((record) => record.canonicalCategory === "sport")).toHaveLength(2);
    expect(reviewWave.keepDaily.some((record) => record.titleIt.includes("Medaglia"))).toBe(false);
  });

  it("uses explicit territories and reviewed non-Wikimedia sources", () => {
    for (const selected of reviewWave.keepDaily) {
      expect(selected.sourceStatus).toBe("pass");
      expect(selected.municipality).toBeTruthy();
      expect(selected.locality).toBeTruthy();
      expect(["GO", "PN", "TS", "UD"]).toContain(selected.province);
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
      expect(selected.sourceUrl).not.toContain("wikidata.org");
      expect(selected.copyIt).toContain(String(selected.year));
    }
  });

  it("keeps four otherwise relevant profiles blocked without an authoritative day", () => {
    expect(reviewWave.hold.map((record) => record.id)).toEqual([
      "master-fvg-24-03-Q976377",
      "master-fvg-05-09-Q16268979",
      "master-fvg-19-09-Q23818700",
      "master-fvg-03-04-Q99506572",
    ]);
    expect(reviewWave.hold.every((record) => record.reason.includes("resta sospesa"))).toBe(true);
    expect(reviewWave.excluded).toEqual([]);
  });
});
