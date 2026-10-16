import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave68.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["07-09", "07-24", "07-25", "08-09", "08-12", "08-23"];

describe("Discover daily Italian review wave 68", () => {
  it("selects six sourced memories and leaves four repetitive dates unresolved", () => {
    expect(reviewWave.policy).toMatchObject({
      dateFormat: "DD-MM",
      furDeferred: true,
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      rejectSemanticDuplicates: true,
      rejectUncertainCalendarDates: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 10,
      keepDaily: 6,
      primary: 6,
      secondary: 0,
      hold: 4,
      excluded: 0,
      canonicalPrimaryDatesBefore: 327,
      canonicalPrimaryDatesAfter: 333,
      currentVisiblePrimaryCoverage: 327,
    });
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
    expect(reviewWave.hold.map((record) => record.dateIt)).toEqual(["07-08", "10-08", "22-08", "30-08"]);
    expect(reviewWave.hold.every((record) => record.readyForUi === false)).toBe(true);
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
        canonicalCategory: "memoria_storica",
        dailyRole: "primary",
        sourceStatus: "pass",
        readyForUi: false,
      });
      expect(selected.sourceUrl).toMatch(/^https:\/\//);
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
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

  it("preserves the local meaning of wars, institutions and monuments", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-09-07-leone-san-marco-castello-gorizia-1919"]).toMatchObject({ municipality: "Gorizia", province: "GO" });
    expect(byId["source-gap-24-07-bombardamento-orsoline-gorizia-1915"].copyIt).toContain("ventisette religiose");
    expect(byId["source-gap-25-07-gorizia-crisi-serbia-1914"].copyIt).toContain("edizione straordinaria");
    expect(byId["source-gap-09-08-gorizia-controllo-italiano-1916"].copyIt).toContain("3.500 civili");
    expect(byId["source-gap-12-08-armistizio-cormons-1866"].copyIt).toContain("Judrio");
    expect(byId["source-gap-23-08-caneva-resa-venezia-1419"].copyIt).toContain("breve assedio");
  });
});
