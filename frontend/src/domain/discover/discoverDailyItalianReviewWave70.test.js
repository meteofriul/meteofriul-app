import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave70.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["11-01", "11-07", "11-08", "11-13", "11-18", "12-15"];

describe("Discover daily Italian review wave 70", () => {
  it("selects six sourced memories and keeps four unsuitable records out of the daily slot", () => {
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
      reviewed: 10,
      keepDaily: 6,
      primary: 6,
      secondary: 0,
      hold: 4,
      excluded: 0,
      canonicalPrimaryDatesBefore: 338,
      canonicalPrimaryDatesAfter: 344,
      currentVisiblePrimaryCoverage: 338,
    });
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
    expect(reviewWave.hold.map((record) => record.dateIt)).toEqual(["15-11", "21-11", "27-11", "05-12"]);
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
        dailyRole: "primary",
        sourceStatus: "pass",
        readyForUi: false,
      });
      expect(["memoria_storica", "arte_cultura"]).toContain(selected.canonicalCategory);
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

  it("does not invent a municipality for the two regional military passages", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-01-11-gorizia-civili-rimasti-1917"]).toMatchObject({ municipality: "Gorizia", province: "GO" });
    expect(byId["source-gap-07-11-proclama-municipio-gorizia-1918"].copyIt).toContain("Ugo Cristofoletti");
    expect(byId["source-gap-08-11-diaz-comando-dopo-caporetto-1917"]).toMatchObject({ municipality: "Friuli Venezia Giulia", province: "FVG" });
    expect(byId["source-gap-13-11-prima-battaglia-piave-1917"]).toMatchObject({ municipality: "Friuli Venezia Giulia", province: "FVG" });
    expect(byId["source-gap-18-11-gorizia-pioggia-proiettili-1915"].copyIt).toContain("Lucia Bortolotti");
    expect(byId["source-gap-15-12-statuto-deputazione-storia-patria-friuli-1918"].copyIt).toContain("decreto luogotenenziale numero 2026");
  });
});
