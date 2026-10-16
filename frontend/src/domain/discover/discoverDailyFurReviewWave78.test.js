import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave78.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave78.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 78", () => {
  it("approves both final Italian selections without pending entries", () => {
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

  it("publishes bilingual copy without changing source, category or priority", () => {
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

  it("uses established FUR place names and cultural-scientific vocabulary", () => {
    const corpus = furReview.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(corpus).toContain("A Glemone la Imacolade");
    expect(corpus).toContain("cjandelis al popul");
    expect(corpus).toContain("Ai 29 di Dicembar dal 1726 al nas a Feagne");
    expect(corpus).toContain("osservazions meteorologjichis");
  });
});
