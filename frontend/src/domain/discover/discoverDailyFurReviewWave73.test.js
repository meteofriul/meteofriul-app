import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave73.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave73.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 73", () => {
  it("approves all three Italian selections without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 3,
      approved: 3,
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

    expect(corpus).toContain("Ai 21 di Novembar dal 1915");
    expect(corpus).toContain("Gurize in flamis");
    expect(corpus).toContain("testemoneance direte");
    expect(corpus).toContain("Ai 5 di Dicembar dal 1915");
    expect(corpus).toContain("no vuelin lassâ la citât");
    expect(corpus).toContain("Ai 24 di Dicembar dal 1916");
    expect(corpus).toContain("Nadâl pai fruts des Orsolinis");
  });
});
