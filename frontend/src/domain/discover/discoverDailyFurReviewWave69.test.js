import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave69.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave69.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 69", () => {
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

    expect(corpus).toContain("Ai 16 di Setembar dal 1951");
    expect(corpus).toContain("Gradiscje");
    expect(corpus).toContain("Tratât di Viene");
    expect(corpus).toContain("Palmanove");
    expect(corpus).toContain("Vignesie");
    expect(corpus).toContain("Pordenon");
    expect(corpus).toContain("pugnâl di ram");
    expect(corpus).toContain("preistorie");
    expect(corpus).toContain("autodeterminazion dai furlans");
    expect(corpus).toContain("Gurize");
  });
});
