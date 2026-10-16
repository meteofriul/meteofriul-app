import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave72.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["11-15", "12-23"];

describe("Discover daily Italian review wave 72", () => {
  it("selects two sourced memories and leaves two weaker December facts outside the daily slot", () => {
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
      keepDaily: 2,
      primary: 2,
      secondary: 0,
      hold: 2,
      excluded: 0,
      canonicalPrimaryDatesBefore: 346,
      canonicalPrimaryDatesAfter: 348,
      currentVisiblePrimaryCoverage: 346,
    });
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
    expect(reviewWave.hold.map((record) => record.dateIt)).toEqual(["08-12", "29-12"]);
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

  it("keeps the Cravos memory on the arrest and the Ungaretti memory on the literary event", () => {
    const byId = Object.fromEntries(reviewWave.keepDaily.map((record) => [record.id, record]));

    expect(byId["source-gap-15-11-emilio-cravos-protesta-gorizia-1915"]).toMatchObject({
      municipality: "Gorizia",
      locality: "Osteria Tausani, Gorizia",
      province: "GO",
    });
    expect(byId["source-gap-15-11-emilio-cravos-protesta-gorizia-1915"].copyIt).toContain("lo arrestano");
    expect(byId["source-gap-15-11-emilio-cravos-protesta-gorizia-1915"].copyIt).not.toMatch(/fucilat|morte/i);

    expect(byId["source-gap-23-12-ungaretti-veglia-san-michele-1915"]).toMatchObject({
      municipality: "Sagrado",
      locality: "Monte San Michele",
      province: "GO",
      canonicalCategory: "cultura",
    });
    expect(byId["source-gap-23-12-ungaretti-veglia-san-michele-1915"].copyIt).toContain("Veglia");
    expect(byId["source-gap-23-12-ungaretti-veglia-san-michele-1915"].copyIt).toContain("Josef Klain");
  });
});
