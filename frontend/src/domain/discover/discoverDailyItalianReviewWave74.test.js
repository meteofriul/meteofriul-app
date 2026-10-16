import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave74.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["11-24", "11-27"];

describe("Discover daily Italian review wave 74", () => {
  it("selects two sourced civic memories without using deaths or minor profiles", () => {
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
      reviewed: 2,
      keepDaily: 2,
      primary: 2,
      secondary: 0,
      hold: 0,
      excluded: 0,
      canonicalPrimaryDatesBefore: 351,
      canonicalPrimaryDatesAfter: 353,
      currentVisiblePrimaryCoverage: 351,
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
        canonicalCategory: "memoria_storica",
        sourceStatus: "pass",
        readyForUi: false,
      });
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

  it("keeps the copy on civilian life and wartime health care", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-24-11-strade-deserte-gorizia-1915"].copyIt).toContain("negozi di alimentari");
    expect(byId["source-gap-24-11-strade-deserte-gorizia-1915"].copyIt).toContain("sotto bombardamento");
    expect(byId["source-gap-27-11-ospedale-femminile-militare-gorizia-1915"]).toMatchObject({
      municipality: "Gorizia",
      locality: "Ospedale femminile, Gorizia",
      province: "GO",
    });
    expect(byId["source-gap-27-11-ospedale-femminile-militare-gorizia-1915"].copyIt).toContain("trasferiti a Trieste");
    expect(reviewWave.keepDaily.map((record) => record.copyIt).join(" ")).not.toMatch(/morte|morti|uccis/i);
  });
});
