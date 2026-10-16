import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave62.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = [
  "06-08",
  "06-25",
  "07-02",
  "07-05",
  "08-01",
  "11-09",
  "12-01",
  "12-06",
  "12-18",
  "12-25",
];

describe("Discover daily Italian review wave 62", () => {
  it("selects ten sourced primary memories for ten uncovered dates", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.policy).toMatchObject({
      furDeferred: true,
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      rejectBirthplaceOnlyProfiles: true,
      rejectSemanticDuplicates: true,
      requireOneCanonicalSource: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 10,
      keepDaily: 10,
      primary: 10,
      secondary: 0,
      hold: 0,
      excluded: 0,
      canonicalPrimaryDatesBefore: 302,
      canonicalPrimaryDatesAfter: 312,
      currentVisiblePrimaryCoverage: 302,
    });
    expect(decisionIds).toHaveLength(10);
    expect(new Set(decisionIds).size).toBe(10);
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
  });

  it("publishes every reviewed record once after FUR approval", () => {
    const sourceEntityIds = new Set();

    for (const selected of reviewWave.keepDaily) {
      const dateKey = toRuntimeDateKey(selected.dateIt);
      const canonical = localMemory.records.filter((record) => record.candidateId === selected.id);
      const competingReadyPrimary = localMemory.records.find((record) => (
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
      expect(selected.sourceEntityId).toBeTruthy();
      expect(sourceEntityIds.has(selected.sourceEntityId)).toBe(false);
      sourceEntityIds.add(selected.sourceEntityId);
      expect(competingReadyPrimary).toBeUndefined();
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

  it("keeps the batch focused on culturally significant regional profiles", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));
    const paulin = localMemory.records.find((record) => record.id === "memory-copy-0705-flavio-paulin");

    expect(paulin).toMatchObject({ recommendedSurface: "archive", dailyRole: "secondary" });
    expect(byId["source-gap-08-06-luciano-petech-1914"].canonicalCategory).toBe("scienza");
    expect(byId["source-gap-02-07-gio-batta-morassi-1934"].copyIt).toContain("foresta di Tarvisio");
    expect(byId["source-gap-09-11-mario-benedetti-1955"].canonicalCategory).toBe("letteratura");
    expect(byId["source-gap-06-12-anton-ukmar-1900"]).toMatchObject({
      canonicalCategory: "memoria_storica",
      priority: 96,
    });
    expect(byId["source-gap-18-12-bonaldo-stringher-1854"].copyIt).toContain("primo governatore");
  });
});
