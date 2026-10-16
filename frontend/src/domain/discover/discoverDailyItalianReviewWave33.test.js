import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave33.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 33", () => {
  it("keeps the single Italian selection blocked until FUR approval", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      excludeSportsOnlyProfiles: true,
      rejectBirthplaceOnlyProfiles: true,
      rejectSemanticDuplicates: true,
      rejectUncertainCalendarDates: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      allowMultipleMemoriesPerDate: true,
      secondaryOrderedByPriority: true,
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

    expect(reviewWave.keepDaily).toHaveLength(1);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(0);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(1);
    expect(reviewWave.hold).toHaveLength(1);
    expect(reviewWave.excluded).toHaveLength(13);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 1,
      primary: 0,
      secondary: 1,
      hold: 1,
      excluded: 13,
      canonicalPrimaryDatesBefore: 237,
      canonicalPrimaryDatesAfter: 237,
      currentVisiblePrimaryCoverage: 229,
    });
  });

  it("does not inflate primary coverage and preserves the stronger 14 July memory", () => {
    const selected = reviewWave.keepDaily[0];
    const dateKey = toRuntimeDateKey(selected.dateIt);
    const existingPrimary = localMemory.records.find((record) => (
      record.primaryUse === "discover"
      && record.dailyRole !== "secondary"
      && record.dateAnchors?.includes(dateKey)
      && record.candidateId !== selected.id
    ));

    expect(selected).toMatchObject({
      id: "master-fvg-14-07-Q1195788",
      dailyRole: "secondary",
    });
    expect(existingPrimary?.title?.it).toBe("Scipio Slataper, Trieste e il Carso");
    expect(reviewWave.summary.canonicalPrimaryDatesAfter).toBe(
      reviewWave.summary.canonicalPrimaryDatesBefore,
    );
  });

  it("uses an explicit territory and a non-Wikipedia source", () => {
    const selected = reviewWave.keepDaily[0];

    expect(selected.sourceStatus).toBe("pass");
    expect(selected.municipality).toBe("Trieste");
    expect(selected.province).toBe("TS");
    expect(selected.sourceUrl).not.toContain("wikipedia.org");
    expect(selected.sourceUrl).not.toContain("wikidata.org");
    expect(selected.copyIt.toLowerCase()).toContain("14 luglio");
  });

  it("holds the sensitive military profile and applies the agreed exclusions", () => {
    const heldIds = new Set(reviewWave.hold.map((record) => record.id));
    const excludedIds = new Set(reviewWave.excluded.map((record) => record.id));

    expect(heldIds).toEqual(new Set(["master-fvg-01-03-Q3608381"]));
    expect(excludedIds).toContain("master-fvg-22-01-Q116323663");
    expect(excludedIds).toContain("master-fvg-15-01-Q354229");
    expect(excludedIds).toContain("master-fvg-19-05-Q760748");
    expect(excludedIds).toContain("master-fvg-01-04-Q3792641");
    expect([...heldIds, ...excludedIds]).not.toContain(reviewWave.keepDaily[0].id);
  });

  it("maps the selected candidate to one canonical reviewed record", () => {
    const selected = reviewWave.keepDaily[0];
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
  });
});
