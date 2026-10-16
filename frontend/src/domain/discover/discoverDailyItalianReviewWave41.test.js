import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave41.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 41", () => {
  it("keeps the Italian selection blocked until FUR approval", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      excludeSportsOnlyProfiles: true,
      rejectBirthplaceOnlyProfiles: true,
      rejectUncertainCalendarDates: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.keepDaily).toHaveLength(12);
    expect(reviewWave.keepDaily.every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave.keepDaily)).not.toContain('"fur"');
  });

  it("records fifteen audited decisions without overlap", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.keepDaily.every((record) => record.dailyRole === "primary")).toBe(true);
    expect(reviewWave.hold).toHaveLength(3);
    expect(reviewWave.excluded).toEqual([]);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 12,
      primary: 12,
      secondary: 0,
      hold: 3,
      excluded: 0,
      canonicalPrimaryDatesBefore: 244,
      canonicalPrimaryDatesAfter: 256,
      currentVisiblePrimaryCoverage: 237,
    });
  });

  it("maps every selected candidate to one published primary record", () => {
    for (const selected of reviewWave.keepDaily) {
      const canonicalRecords = localMemory.records.filter((record) => record.candidateId === selected.id);

      expect(canonicalRecords).toHaveLength(1);
      expect(canonicalRecords[0]).toMatchObject({
        dailyRole: "primary",
        dateAnchors: [toRuntimeDateKey(selected.dateIt)],
        priority: selected.priority,
        editorialStatus: "ready_for_discover",
        languageStatus: {
          it: "approved",
          fur: "approved",
        },
        readyForUi: true,
      });
    }
  });

  it("uses explicit territories and reviewed non-Wikipedia sources", () => {
    for (const selected of reviewWave.keepDaily) {
      expect(selected.sourceStatus).toBe("pass");
      expect(selected.municipality).toBeTruthy();
      expect(selected.province).toMatch(/^(GO|PN|TS|UD)$/);
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
      expect(selected.sourceUrl).not.toContain("wikidata.org");
      expect(selected.copyIt).toContain(String(selected.year));
    }
  });

  it("holds every candidate whose calendar date is not sufficiently certain", () => {
    const holds = new Map(reviewWave.hold.map((record) => [record.id, record.reason]));

    expect(holds.get("master-fvg-06-02-Q3155841")).toContain("non è stato confermato");
    expect(holds.get("master-fvg-10-10-Q23872117")).toContain("18 ottobre 1924");
    expect(holds.get("master-fvg-16-09-Q3623784")).toContain("16 novembre 1874");
  });
});
