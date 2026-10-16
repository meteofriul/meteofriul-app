import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave36.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 36", () => {
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

    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(1);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(3);
    expect(reviewWave.hold).toEqual([]);
    expect(reviewWave.excluded).toHaveLength(11);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 4,
      primary: 1,
      secondary: 3,
      hold: 0,
      excluded: 11,
      canonicalPrimaryDatesBefore: 238,
      canonicalPrimaryDatesAfter: 238,
      currentVisiblePrimaryCoverage: 230,
    });
  });

  it("uses Barzilai as the only selected primary without inflating canonical coverage", () => {
    const primary = reviewWave.keepDaily.find((record) => record.dailyRole === "primary");
    const bisiach = localMemory.records.find((record) => record.id === "memory-copy-0507-gianni-bisiach");

    expect(primary).toMatchObject({
      id: "master-fvg-07-05-Q3945954",
      dateIt: "07-05",
      municipality: "Trieste",
      province: "TS",
    });
    expect(bisiach).toMatchObject({ dailyRole: "secondary", readyForUi: false });
    expect(reviewWave.summary.canonicalPrimaryDatesAfter).toBe(
      reviewWave.summary.canonicalPrimaryDatesBefore,
    );
  });

  it("keeps the other three selections secondary behind existing primary dates", () => {
    const secondaries = reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary");

    for (const selected of secondaries) {
      const existingPrimary = localMemory.records.find((record) => (
        record.primaryUse === "discover"
        && record.dailyRole !== "secondary"
        && record.dateAnchors?.includes(toRuntimeDateKey(selected.dateIt))
        && record.candidateId !== selected.id
      ));
      expect(existingPrimary).toBeTruthy();
    }
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

  it("rejects ordinary sport, birthplace-only profiles and generic relevance", () => {
    const excludedIds = new Set(reviewWave.excluded.map((record) => record.id));

    expect(excludedIds).toContain("master-fvg-22-01-Q357693");
    expect(excludedIds).toContain("master-fvg-22-09-Q3433481");
    expect(excludedIds).toContain("master-fvg-03-03-Q282119");
    expect(excludedIds).toContain("master-fvg-04-02-Q1335813");
    expect(excludedIds).toContain("master-fvg-05-01-Q273804");
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
