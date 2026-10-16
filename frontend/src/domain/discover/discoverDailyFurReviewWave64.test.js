import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave64.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave64.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 64", () => {
  it("approves the Italian selection without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 1,
      approved: 1,
      pendingHumanReview: 0,
    });
    expect(furReview.records[0].status).toBe("approved");
  });

  it("publishes the same bilingual copy selected in Italian", () => {
    const selected = italianReview.keepDaily[0];
    const item = furReview.records[0];
    const canonical = localMemory.records.find((record) => record.id === item.id);

    expect(canonical).toMatchObject({
      candidateId: selected.id,
      priority: selected.priority,
      title: { it: selected.titleIt, fur: item.titleFur },
      summary: { it: selected.copyIt, fur: item.summaryFur },
      editorialStatus: "ready_for_discover",
      languageStatus: { it: "approved", fur: "approved" },
      readyForUi: true,
    });
    expect(item.summaryFur).toContain("Ai 19 di Mai dal 1975");
    expect(item.summaryFur).toContain("Basse furlane");
  });
});
