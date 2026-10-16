import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave34.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 34", () => {
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
    expect(reviewWave.keepDaily).toHaveLength(6);
    expect(reviewWave.keepDaily.every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave.keepDaily)).not.toContain('"fur"');
  });

  it("records fifteen audited decisions without overlap", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(0);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(6);
    expect(reviewWave.hold).toHaveLength(1);
    expect(reviewWave.excluded).toHaveLength(8);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 6,
      primary: 0,
      secondary: 6,
      hold: 1,
      excluded: 8,
      canonicalPrimaryDatesBefore: 237,
      canonicalPrimaryDatesAfter: 237,
      currentVisiblePrimaryCoverage: 229,
    });
  });

  it("keeps Pancino secondary when a later wave adds a stronger primary", () => {
    const pancino = reviewWave.keepDaily.find((record) => record.id === "master-fvg-11-04-Q3764684");
    const dateKey = toRuntimeDateKey(pancino.dateIt);
    const existingPrimary = localMemory.records.find((record) => (
      record.primaryUse === "discover"
      && record.dailyRole !== "secondary"
      && record.dateAnchors?.includes(dateKey)
      && record.candidateId !== pancino.id
    ));

    expect(pancino.dailyRole).toBe("secondary");
    expect(existingPrimary).toMatchObject({
      candidateId: "master-fvg-11-04-Q3771762",
      dailyRole: "primary",
      readyForUi: true,
    });
    expect(reviewWave.summary.canonicalPrimaryDatesAfter).toBe(
      reviewWave.summary.canonicalPrimaryDatesBefore,
    );
  });

  it("preserves the stronger primary memories on the other selected dates", () => {
    const expectedPrimaryByDate = new Map([
      ["08-05", "Gino de Finetti, artista di confine"],
      ["08-08", "Nasce l'Universita di Trieste"],
      ["06-15", "Lojze Spacal e il Carso"],
      ["07-18", "Geppino Micheletti, il medico di Vergarolla"],
      ["06-20", "Antonio Mattioni, un pioniere del volo a reazione"],
    ]);

    for (const [dateKey, title] of expectedPrimaryByDate) {
      const primary = localMemory.records.find((record) => (
        record.primaryUse === "discover"
        && record.dailyRole !== "secondary"
        && record.readyForUi === true
        && record.dateAnchors?.includes(dateKey)
      ));
      expect(primary?.title?.it).toBe(title);
    }
  });

  it("uses explicit territories and non-Wikipedia sources", () => {
    for (const selected of reviewWave.keepDaily) {
      expect(selected.sourceStatus).toBe("pass");
      expect(selected.municipality).toBeTruthy();
      expect(selected.province).toMatch(/^(PN|UD|TS)$/);
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
      expect(selected.sourceUrl).not.toContain("wikidata.org");
      expect(selected.copyIt).toContain(String(selected.year));
    }
  });

  it("holds the uncertain academic date and applies the agreed exclusions", () => {
    const heldIds = new Set(reviewWave.hold.map((record) => record.id));
    const excludedIds = new Set(reviewWave.excluded.map((record) => record.id));

    expect(heldIds).toEqual(new Set(["master-fvg-19-11-Q3769707"]));
    expect(excludedIds).toContain("master-fvg-11-07-Q361532");
    expect(excludedIds).toContain("master-fvg-03-06-Q3771061");
    expect(excludedIds).toContain("master-fvg-13-02-Q16597179");
    expect(excludedIds).toContain("master-fvg-17-04-Q24942555");
    expect([...heldIds, ...excludedIds]).not.toContain(reviewWave.keepDaily[0].id);
  });

  it("maps each selected candidate to one canonical reviewed record", () => {
    for (const selected of reviewWave.keepDaily) {
      const records = localMemory.records.filter((record) => record.candidateId === selected.id);

      expect(records).toHaveLength(1);
      expect(records[0]).toMatchObject({
        dateAnchors: [toRuntimeDateKey(selected.dateIt)],
        dailyRole: "secondary",
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
