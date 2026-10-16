import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave57.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedKeptIds = [
  "master-fvg-06-10-Q16574025",
  "master-fvg-08-03-Q3764851",
  "master-fvg-15-07-Q64225994",
];

describe("Discover daily Italian review wave 57", () => {
  it("assigns exactly one controlled decision to all fourteen candidates", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.policy).toMatchObject({
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      rejectBirthplaceOnlyProfiles: true,
      requireOneCanonicalSource: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 14,
      keepDaily: 3,
      primary: 3,
      secondary: 0,
      hold: 2,
      excluded: 9,
      canonicalPrimaryDatesBefore: 274,
      canonicalPrimaryDatesAfter: 277,
      currentVisiblePrimaryCoverage: 269,
    });
    expect(decisionIds).toHaveLength(14);
    expect(new Set(decisionIds).size).toBe(14);
    expect(reviewWave.keepDaily.map((record) => record.id)).toEqual(expectedKeptIds);
  });

  it("publishes three sourced primary memories on previously uncovered dates", () => {
    for (const selected of reviewWave.keepDaily) {
      const dateKey = toRuntimeDateKey(selected.dateIt);
      const canonical = localMemory.records.filter((record) => record.candidateId === selected.id);
      const competingPrimary = localMemory.records.find((record) => (
        record.candidateId !== selected.id
        && record.dailyRole !== "secondary"
        && record.primaryUse === "discover"
        && record.readyForUi === true
        && record.dateAnchors?.includes(dateKey)
      ));

      expect(selected).toMatchObject({
        dailyRole: "primary",
        sourceStatus: "pass",
        readyForUi: false,
      });
      expect(selected.sourceUrl).toMatch(/^https:\/\//);
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
      expect(competingPrimary).toBeUndefined();
      expect(canonical).toHaveLength(1);
      expect(canonical[0]).toMatchObject({
        dailyRole: "primary",
        dateAnchors: [dateKey],
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
    }
  });

  it("keeps only documented industrial, Risorgimento and naval merit", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["master-fvg-06-10-Q16574025"].copyIt).toContain("oltre duemila dipendenti");
    expect(byId["master-fvg-08-03-Q3764851"].sourceLabel).toBe("Treccani - Gioacchino Rasponi");
    expect(byId["master-fvg-15-07-Q64225994"].copyIt).toContain("Medaglia d'oro");
    expect(reviewWave.hold.map((record) => record.id)).toEqual([
      "master-fvg-20-10-Q60062760",
      "master-fvg-28-12-Q3848334",
    ]);
    expect(reviewWave.excluded).toHaveLength(9);
    expect(reviewWave.hold.every((record) => record.reason.length > 120)).toBe(true);
    expect(reviewWave.excluded.every((record) => record.reason.length > 120)).toBe(true);
  });
});
