import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave72.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave72.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 72", () => {
  it("approves both Italian selections without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 2,
      approved: 2,
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

  it("publishes the approved bilingual copy without changing the Italian decisions", () => {
    for (const item of furReview.records) {
      const canonical = localMemory.records.find((record) => record.id === item.id);
      const selected = italianReview.keepDaily.find((record) => record.id === canonical?.candidateId);

      expect(canonical).toMatchObject({
        candidateId: selected?.id,
        dailyRole: "primary",
        priority: selected?.priority,
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
        title: { it: selected?.titleIt, fur: item.titleFur },
        summary: { it: selected?.copyIt, fur: item.summaryFur },
      });
    }
  });

  it("keeps established FUR historical and territorial terminology", () => {
    const corpus = furReview.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(corpus).toContain("Ai 15 di Novembar dal 1915");
    expect(corpus).toContain("Gurize");
    expect(corpus).toContain("al ven arestât");
    expect(corpus).toContain("Ai 23 di Dicembar dal 1915");
    expect(corpus).toContain("Veglia");
    expect(corpus).toContain("Cjars");
    expect(corpus).toContain("Grande Vuere");
  });
});
