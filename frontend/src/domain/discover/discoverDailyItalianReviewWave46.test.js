import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave46.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 46", () => {
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
      keepDaily: 15,
      primary: 0,
      secondary: 15,
      hold: 0,
      excluded: 0,
      canonicalPrimaryDatesBefore: 270,
      canonicalPrimaryDatesAfter: 270,
      currentVisiblePrimaryCoverage: 265,
    });
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(15);
  });

  it("keeps every selected profile secondary to an existing ready primary date anchor", () => {
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

  it("publishes all fifteen selections only after approved bilingual review", () => {
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

  it("records name, birthplace and date corrections instead of propagating source conflicts", () => {
    const luzzatto = reviewWave.keepDaily.find((record) => record.wikidataId === "Q4154174");
    const manzini = reviewWave.keepDaily.find((record) => record.wikidataId === "Q4013371");
    const goldschmiedt = reviewWave.keepDaily.find((record) => record.wikidataId === "Q1553553");

    expect(luzzatto.titleIt).toContain("Laura Coen Luzzatto");
    expect(luzzatto.sourceCorrection).toContain("Laura Luzzatto Coen");
    expect(manzini).toMatchObject({ dateIt: "20-08", year: 1872, municipality: "Udine" });
    expect(manzini.sourceCorrection).toContain("San Daniele del Friuli");
    expect(goldschmiedt).toMatchObject({ dateIt: "29-05", year: 1850 });
    expect(goldschmiedt.sourceCorrection).toContain("5 ottobre");
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

  it("does not leave unresolved or excluded records in this reviewed batch", () => {
    expect(reviewWave.hold).toEqual([]);
    expect(reviewWave.excluded).toEqual([]);
  });
});
