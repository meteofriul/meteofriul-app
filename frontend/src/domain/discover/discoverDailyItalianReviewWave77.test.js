import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave77.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const expectedDates = ["06-30", "08-10", "09-25", "10-20", "12-28"];

describe("Discover daily Italian review wave 77", () => {
  it("selects five exact-date memories and leaves only two dates on hold", () => {
    expect(reviewWave.summary).toEqual({
      reviewed: 7,
      keepDaily: 5,
      primary: 5,
      secondary: 0,
      hold: 2,
      excluded: 0,
      canonicalPrimaryDatesBefore: 359,
      canonicalPrimaryDatesAfter: 364,
      currentVisiblePrimaryCoverage: 359,
    });
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual(expectedDates);
    expect(reviewWave.hold.map((record) => toRuntimeDateKey(record.dateIt))).toEqual([
      "12-08",
      "12-29",
    ]);
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

  it("uses distinct territorial, cultural and institutional sources", () => {
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

  it("keeps Ostermann visible only on the records drawn from his book", () => {
    const ostermannRecords = reviewWave.keepDaily.filter((record) => record.sourceLabel.startsWith("Ostermann"));
    const institutionalRecords = reviewWave.keepDaily.filter((record) => !record.sourceLabel.startsWith("Ostermann"));

    expect(ostermannRecords.map((record) => toRuntimeDateKey(record.dateIt))).toEqual([
      "08-10",
      "09-25",
      "12-28",
    ]);
    expect(institutionalRecords.map((record) => record.sourceUrl)).toEqual([
      "https://www.dizionariobiograficodeifriulani.it/walland-giuseppe",
      "https://www.esercito.difesa.it/organizzazione/capo-di-sme/comfoter/comando-forze-operative-nord/brigata-pozzuolo-del-friuli/reggimento-logistico-pozzuolo-del-friuli-/la-storia/126045.html",
    ]);
  });

  it("does not use deaths, minor profiles or invented local detail", () => {
    const corpus = reviewWave.keepDaily.map((record) => `${record.titleIt} ${record.copyIt}`).join(" ");

    expect(corpus).toContain("Locum beati Petri");
    expect(corpus).toContain("fiera di San Lorenzo");
    expect(corpus).toContain("Consiglio dei Dieci");
    expect(corpus).toContain("Brigata meccanizzata «Gorizia»");
    expect(corpus).toContain("giorno degli Innocenti");
    expect(corpus).not.toMatch(/nasce|muore|morte|deced/i);
  });
});
