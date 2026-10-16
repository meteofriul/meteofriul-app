import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave35.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 35", () => {
  it("keeps every Italian selection blocked until FUR approval", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      excludeSportsOnlyProfiles: true,
      allowExceptionalSportsProfiles: true,
      rejectBirthplaceOnlyProfiles: true,
      rejectSemanticDuplicates: true,
      rejectUncertainCalendarDates: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      allowMultipleMemoriesPerDate: true,
      secondaryOrderedByPriority: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.keepDaily).toHaveLength(7);
    expect(reviewWave.keepDaily.every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave.keepDaily)).not.toContain('"fur"');
  });

  it("records fifteen audited decisions without overlap", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(1);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(6);
    expect(reviewWave.hold).toHaveLength(0);
    expect(reviewWave.excluded).toHaveLength(8);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 7,
      primary: 1,
      secondary: 6,
      hold: 0,
      excluded: 8,
      canonicalPrimaryDatesBefore: 237,
      canonicalPrimaryDatesAfter: 238,
      currentVisiblePrimaryCoverage: 229,
    });
  });

  it("adds Fulvia Franco as the only new primary memory", () => {
    const primaries = reviewWave.keepDaily.filter((record) => record.dailyRole === "primary");

    expect(primaries).toHaveLength(1);
    expect(primaries[0]).toMatchObject({
      id: "master-fvg-21-05-Q1396089",
      dateIt: "21-05",
      municipality: "Trieste",
      province: "TS",
    });
    expect(reviewWave.summary.canonicalPrimaryDatesAfter).toBe(
      reviewWave.summary.canonicalPrimaryDatesBefore + 1,
    );
  });

  it("keeps Micheletto secondary behind the existing 22 January primary", () => {
    const micheletto = reviewWave.keepDaily.find(
      (record) => record.id === "master-fvg-22-01-Q2632675",
    );
    const existingPrimary = localMemory.records.find((record) => (
      record.primaryUse === "discover"
      && record.dailyRole !== "secondary"
      && record.dateAnchors?.includes(toRuntimeDateKey(micheletto.dateIt))
      && record.candidateId !== micheletto.id
    ));

    expect(micheletto.dailyRole).toBe("secondary");
    expect(existingPrimary?.title?.it).toBe("Luigi Loir, Gorizia e l'illustrazione");
  });

  it("keeps the stronger Mara Navarria memory ahead of Michele Mian", () => {
    const mian = reviewWave.keepDaily.find((record) => record.id === "master-fvg-18-07-Q2518079");
    const navarria = localMemory.records.find((record) => (
      record.title?.it === "Mara Navarria, dalla Bassa friulana all'oro olimpico"
    ));

    expect(mian.dailyRole).toBe("secondary");
    expect(navarria.dailyRole).toBe("secondary");
    expect(navarria.priority).toBeLessThan(mian.priority);
  });

  it("uses explicit territories and non-Wikipedia sources", () => {
    for (const selected of reviewWave.keepDaily) {
      expect(selected.sourceStatus).toBe("pass");
      expect(selected.municipality).toBeTruthy();
      expect(selected.province).toMatch(/^(PN|UD|GO|TS)$/);
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
      expect(selected.sourceUrl).not.toContain("wikidata.org");
      expect(selected.copyIt).toContain(String(selected.year));
    }
  });

  it("applies the agreed exclusions to generic, birthplace-only and ordinary sport records", () => {
    const excludedIds = new Set(reviewWave.excluded.map((record) => record.id));

    expect(excludedIds).toContain("master-fvg-08-06-Q55281792");
    expect(excludedIds).toContain("master-fvg-12-06-Q1229104");
    expect(excludedIds).toContain("master-fvg-06-08-Q26211124");
    expect(excludedIds).toContain("master-fvg-09-08-Q66761914");
    expect(excludedIds).toContain("master-fvg-18-03-Q2070334");
    expect(reviewWave.hold).toEqual([]);
  });

  it("maps each selected candidate to one canonical reviewed record", () => {
    for (const selected of reviewWave.keepDaily) {
      const records = localMemory.records.filter((record) => record.candidateId === selected.id);

      expect(records).toHaveLength(1);
      expect(records[0]).toMatchObject({
        dateAnchors: [toRuntimeDateKey(selected.dateIt)],
        dailyRole: selected.dailyRole,
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
