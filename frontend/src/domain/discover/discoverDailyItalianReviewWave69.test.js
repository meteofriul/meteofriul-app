import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave69.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["09-16", "10-03", "10-11", "10-23", "10-25"];

describe("Discover daily Italian review wave 69", () => {
  it("selects five sourced memories and leaves four weaker or repetitive dates unresolved", () => {
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
      reviewed: 9,
      keepDaily: 5,
      primary: 5,
      secondary: 0,
      hold: 4,
      excluded: 0,
      canonicalPrimaryDatesBefore: 333,
      canonicalPrimaryDatesAfter: 338,
      currentVisiblePrimaryCoverage: 333,
    });
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
    expect(reviewWave.hold.map((record) => record.dateIt)).toEqual(["25-09", "30-09", "04-10", "20-10"]);
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
      expect(["memoria_storica", "scienza_territorio"]).toContain(selected.canonicalCategory);
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

  it("preserves the territorial meaning of institutions, trade, archaeology and autonomy", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-16-09-fogolars-progetto-friuli-nel-mondo-1951"].copyIt).toContain("Fogolârs Furlans");
    expect(byId["source-gap-03-10-trattato-vienna-palmanova-1866"]).toMatchObject({ municipality: "Palmanova", province: "UD" });
    expect(byId["source-gap-11-10-ducale-vino-pordenone-1524"].copyIt).toContain("Girolamo Priuli");
    expect(byId["source-gap-23-10-tina-jama-pugnale-rame-2024"].copyIt).toContain("4.000 anni");
    expect(byId["source-gap-25-10-autodeterminazione-friulani-vienna-1918"].copyIt).toContain("Giuseppe Bugatto");
  });
});
