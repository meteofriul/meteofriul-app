import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave40.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 40", () => {
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
    expect(reviewWave.keepDaily).toHaveLength(8);
    expect(reviewWave.keepDaily.every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave.keepDaily)).not.toContain('"fur"');
  });

  it("records fifteen audited decisions without overlap", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(4);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(4);
    expect(reviewWave.hold).toEqual([]);
    expect(reviewWave.excluded).toHaveLength(7);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 8,
      primary: 4,
      secondary: 4,
      hold: 0,
      excluded: 7,
      canonicalPrimaryDatesBefore: 240,
      canonicalPrimaryDatesAfter: 244,
      currentVisiblePrimaryCoverage: 233,
    });
  });

  it("uses primary roles only on uncovered dates", () => {
    const byId = new Map(reviewWave.keepDaily.map((record) => [record.id, record]));

    for (const id of [
      "master-fvg-03-06-Q18644770",
      "master-fvg-03-12-Q3659310",
      "master-fvg-04-01-Q4979365",
      "master-fvg-05-04-Q7454162",
    ]) {
      expect(byId.get(id).dailyRole).toBe("primary");
    }
    for (const id of [
      "master-fvg-03-04-Q918301",
      "master-fvg-03-08-Q3991119",
      "master-fvg-03-08-Q18118106",
      "master-fvg-05-08-Q570580",
    ]) {
      expect(byId.get(id).dailyRole).toBe("secondary");
    }
    expect(byId.get("master-fvg-03-08-Q3991119").priority).toBeGreaterThan(
      byId.get("master-fvg-03-08-Q18118106").priority,
    );
  });

  it("uses explicit territories and reviewed non-Wikipedia sources", () => {
    for (const selected of reviewWave.keepDaily) {
      expect(selected.sourceStatus).toBe("pass");
      expect(selected.municipality).toBeTruthy();
      expect(selected.province).toMatch(/^(PN|TS|UD)$/);
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
      expect(selected.sourceUrl).not.toContain("wikidata.org");
      expect(selected.copyIt).toContain(String(selected.year));
    }
  });

  it("rejects ordinary profiles and the record with an uncertain calendar date", () => {
    const excludedIds = new Set(reviewWave.excluded.map((record) => record.id));

    expect(excludedIds).toContain("master-fvg-03-05-Q96973711");
    expect(excludedIds).toContain("master-fvg-04-05-Q3858823");
    expect(excludedIds).toContain("master-fvg-04-06-Q16555047");
    expect(excludedIds).toContain("master-fvg-05-01-Q3770098");
    expect(excludedIds).toContain("master-fvg-05-04-Q55217569");
    expect(reviewWave.excluded.find((record) => record.id === "master-fvg-04-05-Q3858823").reason)
      .toContain("incompatibili");
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
