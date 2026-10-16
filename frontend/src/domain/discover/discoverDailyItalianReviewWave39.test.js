import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave39.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 39", () => {
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
      sourceFirst: true,
      publishAfterFurOnly: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.keepDaily).toHaveLength(4);
    expect(reviewWave.keepDaily.every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave.keepDaily)).not.toContain('"fur"');
  });

  it("records fifteen audited decisions without overlap", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(2);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(2);
    expect(reviewWave.hold).toEqual([]);
    expect(reviewWave.excluded).toHaveLength(11);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 4,
      primary: 2,
      secondary: 2,
      hold: 0,
      excluded: 11,
      canonicalPrimaryDatesBefore: 238,
      canonicalPrimaryDatesAfter: 240,
      currentVisiblePrimaryCoverage: 231,
    });
  });

  it("uses primary roles only on uncovered dates", () => {
    const byId = new Map(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId.get("master-fvg-02-05-Q3229700")).toMatchObject({
      dateIt: "02-05",
      dailyRole: "primary",
      priority: 96,
    });
    expect(byId.get("master-fvg-02-12-Q3723601")).toMatchObject({
      dateIt: "02-12",
      dailyRole: "primary",
      priority: 92,
    });
    expect(byId.get("master-fvg-01-09-Q641789")).toMatchObject({
      dateIt: "01-09",
      dailyRole: "secondary",
      priority: 94,
    });
    expect(byId.get("master-fvg-02-09-Q65496893")).toMatchObject({
      dateIt: "02-09",
      dailyRole: "secondary",
      priority: 94,
    });
  });

  it("uses explicit territories and reviewed non-Wikipedia sources", () => {
    for (const selected of reviewWave.keepDaily) {
      expect(selected.sourceStatus).toBe("pass");
      expect(selected.municipality).toBeTruthy();
      expect(selected.province).toMatch(/^(PN|TS)$/);
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
      expect(selected.sourceUrl).not.toContain("wikidata.org");
      expect(selected.copyIt).toContain(String(selected.year));
    }
  });

  it("rejects ordinary sport and generic political or professional profiles", () => {
    const excludedIds = new Set(reviewWave.excluded.map((record) => record.id));

    expect(excludedIds).toContain("master-fvg-01-02-Q2159489");
    expect(excludedIds).toContain("master-fvg-01-03-Q1338092");
    expect(excludedIds).toContain("master-fvg-01-10-Q3675632");
    expect(excludedIds).toContain("master-fvg-02-05-Q16528352");
    expect(excludedIds).toContain("master-fvg-02-09-Q3615792");
    expect(reviewWave.hold).toEqual([]);
  });

  it("maps every selected candidate to one canonical reviewed record", () => {
    for (const selected of reviewWave.keepDaily) {
      const records = localMemory.records.filter((record) => record.candidateId === selected.id);

      expect(records).toHaveLength(1);
      expect(records[0]).toMatchObject({
        dateAnchors: [toRuntimeDateKey(selected.dateIt)],
        dailyRole: selected.dailyRole,
        priority: selected.priority,
        languageStatus: {
          it: "approved",
          fur: "approved",
        },
        title: {
          it: selected.titleIt,
        },
        summary: {
          it: selected.copyIt,
        },
      });
    }
  });
});
