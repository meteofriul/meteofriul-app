import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave53.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave53.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 53", () => {
  it("approves the only Italian selection without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 1,
      approved: 1,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(1);
    expect(furReview.records[0].status).toBe("approved");
  });

  it("covers exactly the canonical record selected in Italian", () => {
    const selected = italianReview.keepDaily[0];
    const canonical = localMemory.records.find((record) => record.candidateId === selected.id);

    expect(furReview.records[0].id).toBe(canonical?.id);
  });

  it("publishes the reviewed FUR copy without changing the Italian decision", () => {
    const item = furReview.records[0];
    const selected = italianReview.keepDaily[0];
    const canonical = localMemory.records.find((record) => record.id === item.id);

    expect(canonical).toMatchObject({
      candidateId: selected.id,
      dailyRole: "secondary",
      priority: selected.priority,
      editorialStatus: "ready_for_discover",
      languageStatus: { it: "approved", fur: "approved" },
      readyForUi: true,
      title: { it: selected.titleIt, fur: item.titleFur },
      summary: { it: selected.copyIt, fur: item.summaryFur },
    });
  });

  it("uses established FUR territory and preserves international proper names", () => {
    const item = furReview.records[0];

    expect(item.summaryFur).toContain("San Vît dal Tiliment");
    expect(item.summaryFur).toContain("dîs stagjons");
    expect(item.summaryFur).toContain("Major League Baseball");
    expect(item.summaryFur).toContain("Canadian Baseball Hall of Fame");
    expect(`${item.titleFur} ${item.summaryFur}`).not.toContain("pending_review");
  });
});
