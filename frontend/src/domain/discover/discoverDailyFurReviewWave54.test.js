import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave54.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave54.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 54", () => {
  it("approves all five Italian selections without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 5,
      approved: 5,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(5);
    expect(furReview.records.every((record) => record.status === "approved")).toBe(true);
  });

  it("covers exactly the canonical records selected in Italian", () => {
    const expectedIds = italianReview.keepDaily.map((selected) => (
      localMemory.records.find((record) => record.candidateId === selected.id)?.id
    ));

    expect(furReview.records.map((record) => record.id)).toEqual(expectedIds);
    expect(expectedIds.every(Boolean)).toBe(true);
  });

  it("publishes every reviewed FUR copy without changing the Italian decisions", () => {
    for (const item of furReview.records) {
      const canonical = localMemory.records.find((record) => record.id === item.id);
      const selected = italianReview.keepDaily.find((record) => record.id === canonical?.candidateId);

      expect(canonical).toMatchObject({
        candidateId: selected?.id,
        dailyRole: "secondary",
        priority: selected?.priority,
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
        title: { it: selected?.titleIt, fur: item.titleFur },
        summary: { it: selected?.copyIt, fur: item.summaryFur },
      });
    }
  });

  it("uses established FUR territory, chronology and proper names", () => {
    const corpus = furReview.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(corpus).toContain("Pordenon");
    expect(corpus).toContain("Udin");
    expect(corpus).toContain("Triest");
    expect(corpus).toContain("Monfalcon");
    expect(corpus).toContain("Academie dai Lincei");
    expect(corpus).toContain("Martin Mystère");
    expect(corpus).toContain("medaie di bronç");
    expect(corpus).not.toContain("pending_review");
  });
});
