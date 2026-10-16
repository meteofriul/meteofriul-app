import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave66.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["05-08", "05-10", "05-12", "05-26"];

describe("Discover daily Italian review wave 66", () => {
  it("selects four institutional memories and keeps 18 May unresolved", () => {
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
      reviewed: 5,
      keepDaily: 4,
      primary: 4,
      secondary: 0,
      hold: 1,
      excluded: 0,
      canonicalPrimaryDatesBefore: 317,
      canonicalPrimaryDatesAfter: 321,
      currentVisiblePrimaryCoverage: 317,
    });
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
    expect(reviewWave.hold).toEqual([
      expect.objectContaining({
        dateIt: "18-05",
        decision: "hold_for_targeted_source",
        readyForUi: false,
      }),
    ]);
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

  it("preserves the intended territorial scope", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-08-05-gemona-linea-emergenza-1976"]).toMatchObject({
      municipality: "Gemona del Friuli",
      province: "UD",
    });
    expect(byId["source-gap-10-05-prime-elezioni-regionali-1964"]).toMatchObject({
      municipality: "Friuli Venezia Giulia",
      province: "FVG",
    });
    expect(byId["source-gap-12-05-fine-repubblica-venezia-1797"].copyIt).toContain("trattato di Campoformio");
    expect(byId["source-gap-26-05-gorizia-primi-giorni-guerra-1915"].copyIt).toContain("Gorizia");
  });
});
