import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave67.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["06-02", "06-07", "06-17", "06-22", "06-26", "07-04"];

describe("Discover daily Italian review wave 67", () => {
  it("selects six sourced memories and leaves four weak dates unresolved", () => {
    expect(reviewWave.policy).toMatchObject({
      dateFormat: "DD-MM",
      furDeferred: true,
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
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
      canonicalPrimaryDatesBefore: 321,
      canonicalPrimaryDatesAfter: 327,
      currentVisiblePrimaryCoverage: 321,
    });
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
    expect(reviewWave.hold.map((record) => record.dateIt)).toEqual(["18-05", "13-06", "27-06", "30-06"]);
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

  it("preserves local scope and the historical meaning of each source", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-02-06-repubblica-confine-orientale-1946"].copyIt).toContain("non partecipa però al voto");
    expect(byId["source-gap-07-06-udine-passa-a-venezia-1420"]).toMatchObject({ municipality: "Udine", province: "UD" });
    expect(byId["source-gap-17-06-conquista-plava-1915"].copyIt).toContain("testa di ponte");
    expect(byId["source-gap-22-06-banda-civica-gorizia-1915"].copyIt).toContain("banda civica");
    expect(byId["source-gap-26-06-manifesto-civili-gorizia-1915"].copyIt).toContain("restare in casa");
    expect(byId["source-gap-04-07-gorizia-nuove-provincie-1919"].copyIt).toContain("amministrazione militare");
  });
});
