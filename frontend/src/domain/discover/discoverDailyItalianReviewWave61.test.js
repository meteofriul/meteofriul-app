import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave61.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = [
  "03-18",
  "03-22",
  "03-23",
  "03-24",
  "04-06",
  "04-08",
  "04-09",
  "04-12",
  "04-13",
  "04-16",
  "04-19",
  "04-22",
  "04-28",
  "05-01",
  "05-06",
];

describe("Discover daily Italian review wave 61", () => {
  it("selects fifteen sourced primary memories for fifteen uncovered dates", () => {
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
      reviewed: 15,
      keepDaily: 15,
      primary: 15,
      secondary: 0,
      hold: 0,
      excluded: 0,
      canonicalPrimaryDatesBefore: 292,
      canonicalPrimaryDatesAfter: 305,
      currentVisiblePrimaryCoverage: 287,
    });
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(15);
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

  it("keeps the batch focused on regional history, institutions and civil memory", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-18-03-porto-franco-trieste-1719"].priority).toBe(100);
    expect(byId["source-gap-22-03-legge-friulano-1996"].canonicalCategory).toBe("lingua_cultura");
    expect(byId["source-gap-12-04-assalto-castello-torre-1402"].copyIt).toContain("Patria del Friuli");
    expect(byId["source-gap-16-04-battaglia-sacile-1809"].copyIt).toContain("Porcia, Fontanafredda e Sacile");
    expect(byId["source-gap-06-05-terremoto-friuli-1976"]).toMatchObject({
      canonicalCategory: "memoria_storica",
      priority: 100,
    });
  });
});
