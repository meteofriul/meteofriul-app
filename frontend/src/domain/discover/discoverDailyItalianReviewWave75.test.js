import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave75.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["08-22", "08-30", "09-30", "10-04"];

describe("Discover daily Italian review wave 75", () => {
  it("selects four sourced memories without using generic profiles or uncertain dates", () => {
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
      reviewed: 4,
      keepDaily: 4,
      primary: 4,
      secondary: 0,
      hold: 0,
      excluded: 0,
      canonicalPrimaryDatesBefore: 353,
      canonicalPrimaryDatesAfter: 357,
      currentVisiblePrimaryCoverage: 353,
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
      expect(selected.sourceLabel).toBe("Ministero della Cultura - Biblioteca Statale Isontina");
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

  it("keeps the stories distinct and preserves Wagna as the physical locality", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-22-08-tipografia-paternolli-gorizia-1918"].copyIt).toContain("tipografia Paternolli");
    expect(byId["source-gap-30-08-suor-camilla-ospedale-gorizia-1917"].copyIt).toContain("feriti intrasportabili");
    expect(byId["source-gap-30-09-ora-legale-gorizia-1917"].copyIt).toContain("ora legale");
    expect(byId["source-gap-04-10-fatti-wagna-profughi-goriziani-1917"]).toMatchObject({
      municipality: "Gorizia",
      locality: "Campo profughi di Wagna, Stiria",
      province: "GO",
    });
    expect(byId["source-gap-04-10-fatti-wagna-profughi-goriziani-1917"].copyIt).toContain("profughi goriziani");
    expect(reviewWave.keepDaily.map((record) => record.titleIt).join(" ")).not.toMatch(/nasce|muore|morte/i);
  });
});
