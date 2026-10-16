import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave73.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["11-21", "12-05", "12-24"];

describe("Discover daily Italian review wave 73", () => {
  it("selects three sourced memories without using deaths or minor profiles", () => {
    expect(reviewWave.policy).toMatchObject({
      dateFormat: "DD-MM",
      furDeferred: true,
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      rejectSemanticDuplicates: true,
      rejectUncertainCalendarDates: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 3,
      keepDaily: 3,
      primary: 3,
      secondary: 0,
      hold: 0,
      excluded: 0,
      canonicalPrimaryDatesBefore: 348,
      canonicalPrimaryDatesAfter: 351,
      currentVisiblePrimaryCoverage: 348,
    });
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
    expect(reviewWave.hold).toEqual([]);
    expect(reviewWave.excluded).toEqual([]);
  });

  it("keeps exact Italian dates, institutional sources and unique primary records", () => {
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
      expect(["memoria_storica", "cultura"]).toContain(selected.canonicalCategory);
      expect(selected.sourceUrl).toMatch(/^https:\/\/goriziagrandeguerra\.cultura\.gov\.it\//);
      expect(sourceEntityIds.has(selected.sourceEntityId)).toBe(false);
      sourceEntityIds.add(selected.sourceEntityId);
      expect(competingReadyPrimary).toBeUndefined();
      expect(canonical).toHaveLength(1);
      expect(canonical[0]).toMatchObject({
        dateAnchors: [dateKey],
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
    }
  });

  it("keeps every copy on the selected historical fact", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-21-11-alojzij-res-gorizia-in-fiamme-1915"].copyIt).toContain("testimonianza diretta");
    expect(byId["source-gap-05-12-goriziani-rifiutano-evacuazione-1915"].copyIt).toContain("rifiuta di partire");
    expect(byId["source-gap-05-12-goriziani-rifiutano-evacuazione-1915"].copyIt).not.toMatch(/morte|morti|uccis|esplos/i);
    expect(byId["source-gap-24-12-natale-bambini-orsoline-gorizia-1916"]).toMatchObject({
      municipality: "Gorizia",
      locality: "Monastero delle Orsoline, Gorizia",
      province: "GO",
      canonicalCategory: "cultura",
    });
  });
});
