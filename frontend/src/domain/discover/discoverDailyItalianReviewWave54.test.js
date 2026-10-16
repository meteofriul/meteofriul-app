import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave54.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const keptCandidateIds = [
  "master-fvg-03-07-Q21651754",
  "master-fvg-03-08-Q3741704",
  "master-fvg-07-05-Q3751271",
  "master-fvg-01-09-Q16658024",
  "master-fvg-11-07-Q3645735",
];

describe("Discover daily Italian review wave 54", () => {
  it("assigns one controlled decision to all 18 residual candidates", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.policy).toMatchObject({
      allowExceptionalSportsProfiles: true,
      requireOneCanonicalSource: true,
      rejectBirthplaceOnlyProfiles: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      secondaryRequiresPrimaryAnchor: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 18,
      keepDaily: 5,
      primary: 0,
      secondary: 5,
      hold: 6,
      excluded: 7,
      canonicalPrimaryDatesBefore: 274,
      canonicalPrimaryDatesAfter: 274,
      currentVisiblePrimaryCoverage: 269,
    });
    expect(decisionIds).toHaveLength(18);
    expect(new Set(decisionIds).size).toBe(18);
    expect(reviewWave.keepDaily.map((record) => record.id)).toEqual(keptCandidateIds);
  });

  it("publishes only sourced secondary memories on dates with a ready primary anchor", () => {
    for (const selected of reviewWave.keepDaily) {
      const dateKey = toRuntimeDateKey(selected.dateIt);
      const primaryAnchor = localMemory.records.find((record) => (
        record.dailyRole !== "secondary"
        && record.primaryUse === "discover"
        && record.readyForUi === true
        && record.dateAnchors?.includes(dateKey)
      ));
      const canonical = localMemory.records.filter((record) => record.candidateId === selected.id);

      expect(selected).toMatchObject({
        dailyRole: "secondary",
        sourceStatus: "pass",
        readyForUi: false,
      });
      expect(selected.sourceUrl).toMatch(/^https:\/\//);
      expect(primaryAnchor, `${selected.id} requires a ready primary anchor`).toBeTruthy();
      expect(canonical).toHaveLength(1);
      expect(canonical[0]).toMatchObject({
        dailyRole: "secondary",
        dateAnchors: [dateKey],
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
    }
  });

  it("stores the reviewed source and merit for every selected record", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["master-fvg-03-07-Q21651754"]).toMatchObject({
      municipality: "Pordenone",
      canonicalCategory: "cultura",
      sourceLabel: "Treccani - Federico Flora",
    });
    expect(byId["master-fvg-03-08-Q3741704"].copyIt).toContain("guida la Zanichelli");
    expect(byId["master-fvg-07-05-Q3751271"].copyIt).toContain("Martin Mystère");
    expect(byId["master-fvg-01-09-Q16658024"].copyIt).toContain("Simon Wiesenthal");
    expect(byId["master-fvg-11-07-Q3645735"]).toMatchObject({
      municipality: "Monfalcone",
      canonicalCategory: "sport",
      sourceLabel: "CONI - Bruno Dreossi",
    });
    expect(byId["master-fvg-11-07-Q3645735"].copyIt).toContain("medaglia di bronzo");
  });

  it("holds incomplete evidence instead of merging sources implicitly", () => {
    const heldIds = reviewWave.hold.map((record) => record.id);

    expect(heldIds).toEqual([
      "master-fvg-03-09-Q109070765",
      "master-fvg-03-09-Q3619847",
      "master-fvg-07-04-Q17637150",
      "master-fvg-08-09-Q108915794",
      "master-fvg-11-01-Q15144200",
      "master-fvg-12-01-Q27078123",
    ]);
    expect(reviewWave.hold.every((record) => record.reason.length > 80)).toBe(true);
  });

  it("excludes generic profiles consistently with the editorial threshold", () => {
    const excludedIds = reviewWave.excluded.map((record) => record.id);

    expect(excludedIds).toEqual([
      "master-fvg-04-06-Q87270949",
      "master-fvg-04-06-Q1110961",
      "master-fvg-07-05-Q330860",
      "master-fvg-10-06-Q3505631",
      "master-fvg-11-01-Q19361842",
      "master-fvg-11-07-Q47482503",
      "master-fvg-11-08-Q98257368",
    ]);
    expect(reviewWave.excluded.every((record) => record.reason.length > 80)).toBe(true);
  });
});
