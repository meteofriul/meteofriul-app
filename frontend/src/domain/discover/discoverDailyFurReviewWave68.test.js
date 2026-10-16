import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave68.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave68.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 68", () => {
  it("approves all six Italian selections without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 6,
      approved: 6,
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

  it("uses established FUR chronology, places and institutions", () => {
    const corpus = furReview.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(corpus).toContain("Ai 9 di Lui dal 1919");
    expect(corpus).toContain("Leon di San Marc");
    expect(corpus).toContain("munistîr des Ursulinis");
    expect(corpus).toContain("Serbie");
    expect(corpus).toContain("Ai 9 di Avost dal 1916");
    expect(corpus).toContain("Armistizi di Cormons");
    expect(corpus).toContain("Judri");
    expect(corpus).toContain("Cjanive");
    expect(corpus).toContain("curt assedi");
  });
});
