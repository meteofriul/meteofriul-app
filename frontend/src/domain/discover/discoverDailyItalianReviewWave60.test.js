import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave60.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = [
  "01-07",
  "01-09",
  "01-13",
  "01-18",
  "01-19",
  "02-10",
  "02-15",
  "02-23",
  "02-24",
  "02-26",
  "03-02",
  "03-07",
  "03-09",
  "03-13",
  "03-14",
];

describe("Discover daily Italian review wave 60", () => {
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
      canonicalPrimaryDatesBefore: 277,
      canonicalPrimaryDatesAfter: 292,
      currentVisiblePrimaryCoverage: 272,
    });
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(15);
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
  });

  it("publishes every reviewed record once after the FUR approval", () => {
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

  it("keeps the batch above the agreed historical and cultural threshold", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-10-02-trattato-parigi-1947"].priority).toBe(100);
    expect(byId["source-gap-15-02-lino-zanussi-1920"].copyIt).toContain("territorio pordenonese");
    expect(byId["source-gap-24-02-ultimo-convoglio-risiera-1945"].canonicalCategory).toBe("memoria_storica");
    expect(byId["source-gap-09-03-umberto-saba-1883"]).toMatchObject({
      canonicalCategory: "letteratura",
      municipality: "Trieste",
    });
    expect(byId["source-gap-14-03-marija-bernetic-1902"].copyIt).toContain("comunità slovena");
  });
});
