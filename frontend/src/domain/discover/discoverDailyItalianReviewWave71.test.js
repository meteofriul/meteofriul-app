import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave71.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["06-27", "08-07"];

describe("Discover daily Italian review wave 71", () => {
  it("selects two sourced memories and leaves six weak dates outside the daily slot", () => {
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
      reviewed: 8,
      keepDaily: 2,
      primary: 2,
      secondary: 0,
      hold: 6,
      excluded: 0,
      canonicalPrimaryDatesBefore: 344,
      canonicalPrimaryDatesAfter: 346,
      currentVisiblePrimaryCoverage: 344,
    });
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
    expect(reviewWave.hold.map((record) => record.dateIt)).toEqual([
      "18-05",
      "13-06",
      "30-06",
      "24-12",
      "28-12",
      "29-12",
    ]);
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
        canonicalCategory: "memoria_storica",
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

  it("uses the regional scope only for the Costituente and keeps Trieste explicit", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-27-06-costituente-nome-friuli-venezia-giulia-1947"]).toMatchObject({
      municipality: "Friuli Venezia Giulia",
      locality: "Assemblea Costituente, Roma",
      province: "FVG",
    });
    expect(byId["source-gap-27-06-costituente-nome-friuli-venezia-giulia-1947"].copyIt).toContain("Tiziano Tessitori");
    expect(byId["source-gap-07-08-dannunzio-volo-trieste-1915"]).toMatchObject({
      municipality: "Trieste",
      locality: "Trieste",
      province: "TS",
    });
    expect(byId["source-gap-07-08-dannunzio-volo-trieste-1915"].copyIt).toContain("postazioni militari");
  });
});
