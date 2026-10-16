import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave77.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave77.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 77", () => {
  it("approves all five Italian selections without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 5,
      approved: 5,
      pendingHumanReview: 0,
    });
    expect(furReview.records.every((record) => record.status === "approved")).toBe(true);
  });

  it("covers exactly the canonical records selected in Italian", () => {
    const expectedIds = italianReview.keepDaily.map((selected) => (
      localMemory.records.find((record) => record.candidateId === selected.id)?.id
    ));

    expect(furReview.records.map((record) => record.id)).toEqual(expectedIds);
    expect(expectedIds.every(Boolean)).toBe(true);
  });

  it("publishes bilingual copy without changing Italian source or priority", () => {
    for (const item of furReview.records) {
      const canonical = localMemory.records.find((record) => record.id === item.id);
      const selected = italianReview.keepDaily.find((record) => record.id === canonical?.candidateId);

      expect(canonical).toMatchObject({
        candidateId: selected?.id,
        category: selected?.canonicalCategory,
        dailyRole: "primary",
        priority: selected?.priority,
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
        title: { it: selected?.titleIt, fur: item.titleFur },
        summary: { it: selected?.copyIt, fur: item.summaryFur },
        source: { label: selected?.sourceLabel },
      });
    }
  });

  it("uses established FUR place names and keeps official unit names", () => {
    const corpus = furReview.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(corpus).toContain("Ai 30 di Jugn dal 1828");
    expect(corpus).toContain("Gurize, Triest-Cjaudistrie");
    expect(corpus).toContain("A Udin la grande fiere di San Lurinç");
    expect(corpus).toContain("Consei dai Dîs");
    expect(corpus).toContain("Brigade mecanizade «Gorizia»");
    expect(corpus).toContain("I auguris dai fruts di cjase in cjase");
  });
});
