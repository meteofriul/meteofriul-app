import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave78.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["12-08", "12-29"];

describe("Discover daily Italian review wave 78", () => {
  it("closes the exact-date calendar with two sourced primary memories", () => {
    expect(reviewWave.summary).toEqual({
      reviewed: 2,
      keepDaily: 2,
      primary: 2,
      secondary: 0,
      hold: 0,
      excluded: 0,
      canonicalPrimaryDatesBefore: 364,
      canonicalPrimaryDatesAfter: 366,
      currentVisiblePrimaryCoverage: 364,
    });
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
    expect(reviewWave.hold).toEqual([]);
  });

  it("keeps the source-first publication guard", () => {
    expect(reviewWave.policy).toMatchObject({
      dateFormat: "DD-MM",
      sourceFirst: true,
      publishAfterFurOnly: true,
      excludeDeaths: true,
      rejectSemanticDuplicates: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.keepDaily.every((record) => (
      record.sourceStatus === "pass"
      && record.readyForUi === false
      && Boolean(record.sourceEntityId)
    ))).toBe(true);
  });

  it("uses one cultural source and one scientific territorial source", () => {
    expect(reviewWave.keepDaily.map((record) => record.canonicalCategory)).toEqual([
      "tradizioni",
      "scienza_territorio",
    ]);
    expect(reviewWave.keepDaily[0].sourceLabel).toBe("Ostermann 1894 - pagina 598");
    expect(reviewWave.keepDaily[1].sourceUrl).toBe(
      "https://www.alpinafriulana.it/wp-content/uploads/2013/01/IN-ALTO-2015-2016.pdf",
    );
  });

  it("creates one unique canonical record for each selected date", () => {
    const selectedIds = new Set();
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

      expect(selectedIds.has(selected.id)).toBe(false);
      expect(sourceEntityIds.has(selected.sourceEntityId)).toBe(false);
      selectedIds.add(selected.id);
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

  it("does not use deaths or minor profiles", () => {
    const corpus = reviewWave.keepDaily.map((record) => `${record.titleIt} ${record.copyIt}`).join(" ");

    expect(corpus).toContain("processione dell'8 dicembre");
    expect(corpus).toContain("osservazioni meteorologiche giornaliere");
    expect(corpus).not.toMatch(/muore|morte|deced/i);
  });
});
