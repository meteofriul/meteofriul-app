import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave37.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 37", () => {
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
    expect(reviewWave.keepDaily).toHaveLength(1);
    expect(reviewWave.keepDaily[0].readyForUi).toBe(false);
    expect(JSON.stringify(reviewWave.keepDaily)).not.toContain('"fur"');
  });

  it("records fifteen audited decisions without overlap", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(0);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(1);
    expect(reviewWave.hold).toEqual([]);
    expect(reviewWave.excluded).toHaveLength(14);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 1,
      primary: 0,
      secondary: 1,
      hold: 0,
      excluded: 14,
      canonicalPrimaryDatesBefore: 238,
      canonicalPrimaryDatesAfter: 238,
      currentVisiblePrimaryCoverage: 231,
    });
  });

  it("keeps Henrika Šantel secondary behind the existing primary memory", () => {
    const selected = reviewWave.keepDaily[0];
    const existingPrimary = localMemory.records.find((record) => (
      record.primaryUse === "discover"
      && record.dailyRole !== "secondary"
      && record.dateAnchors?.includes(toRuntimeDateKey(selected.dateIt))
      && record.candidateId !== selected.id
    ));

    expect(selected).toMatchObject({
      id: "master-fvg-17-08-Q18508284",
      dateIt: "17-08",
      municipality: "Gorizia",
      province: "GO",
      dailyRole: "secondary",
    });
    expect(existingPrimary).toMatchObject({
      id: "memory-it-ready-0817-tina-modotti-fotografia-e-impegno-civile",
      dailyRole: "primary",
    });
    expect(reviewWave.summary.canonicalPrimaryDatesAfter).toBe(
      reviewWave.summary.canonicalPrimaryDatesBefore,
    );
  });

  it("uses an explicit territory and an institutional non-Wikipedia source", () => {
    const selected = reviewWave.keepDaily[0];

    expect(selected.sourceStatus).toBe("pass");
    expect(selected.municipality).toBe("Gorizia");
    expect(selected.province).toBe("GO");
    expect(selected.sourceUrl).toContain("ng-slo.si");
    expect(selected.sourceUrl).not.toContain("wikipedia.org");
    expect(selected.sourceUrl).not.toContain("wikidata.org");
    expect(selected.copyIt).toContain(String(selected.year));
  });

  it("rejects ordinary sport, generic politics and birthplace-only profiles", () => {
    const excludedIds = new Set(reviewWave.excluded.map((record) => record.id));

    expect(excludedIds).toContain("master-fvg-10-11-Q78770");
    expect(excludedIds).toContain("master-fvg-11-06-Q9258367");
    expect(excludedIds).toContain("master-fvg-13-06-Q6761014");
    expect(excludedIds).toContain("master-fvg-18-01-Q520868");
    expect(excludedIds).toContain("master-fvg-19-04-Q328126");
    expect(reviewWave.hold).toEqual([]);
  });

  it("maps the selected candidate to one canonical reviewed record", () => {
    const selected = reviewWave.keepDaily[0];
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
  });
});
