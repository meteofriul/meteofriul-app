import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave75.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave75.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 75", () => {
  it("approves all four Italian selections without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 4,
      approved: 4,
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

  it("keeps established FUR historical, temporal and territorial terminology", () => {
    const corpus = furReview.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(corpus).toContain("Ai 22 di Avost dal 1918");
    expect(corpus).toContain("lis ruvinis de tipografie");
    expect(corpus).toContain("Ai 30 di Avost dal 1917");
    expect(corpus).toContain("medaie di bronç");
    expect(corpus).toContain("Ai 30 di Setembar dal 1917");
    expect(corpus).toContain("La ore legâl e jentre in vore a Gurize");
    expect(corpus).toContain("Ai 4 di Otubar dal 1917");
    expect(corpus).toContain("profughs gorizians");
    expect(corpus).toContain("cjamp di Wagna");
  });
});
