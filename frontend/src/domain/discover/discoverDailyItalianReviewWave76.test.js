import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave76.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 76", () => {
  it("promotes only the two new distinct memories", () => {
    expect(reviewWave.summary).toEqual({
      reviewed: 7,
      keepDaily: 2,
      primary: 2,
      secondary: 0,
      hold: 5,
      excluded: 0,
      canonicalPrimaryDatesBefore: 357,
      canonicalPrimaryDatesAfter: 359,
      currentVisiblePrimaryCoverage: 357,
    });
    expect(reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt))).toEqual([
      "05-18",
      "06-13",
    ]);
    expect(reviewWave.hold.map((record) => toRuntimeDateKey(record.dateIt))).toEqual([
      "08-10",
      "09-25",
      "10-20",
      "12-08",
      "12-29",
    ]);
  });

  it("keeps prior hold decisions instead of filling dates for coverage", () => {
    expect(reviewWave.policy).toMatchObject({
      sourceFirst: true,
      publishAfterFurOnly: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
      rejectSemanticDuplicates: true,
    });
    expect(reviewWave.hold.every((record) => record.reason.includes("Wave"))).toBe(true);
  });

  it("keeps exact institutional sources and unique canonical records", () => {
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
        municipality: "Gorizia",
        province: "GO",
        dailyRole: "primary",
        canonicalCategory: "memoria_storica",
        sourceStatus: "pass",
        readyForUi: false,
      });
      expect(selected.sourceLabel).toBe("Ministero della Cultura - Biblioteca Statale Isontina");
      expect(selected.sourceUrl).toMatch(/^https:\/\/goriziagrandeguerra\.cultura\.gov\.it\//);
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

  it("keeps the two stories concrete and distinct", () => {
    const corpus = reviewWave.keepDaily.map((record) => `${record.titleIt} ${record.copyIt}`).join(" ");

    expect(corpus).toContain("sei bambini");
    expect(corpus).toContain("profughi goriziani");
    expect(corpus).not.toMatch(/nasce|muore|morte/i);
  });
});
