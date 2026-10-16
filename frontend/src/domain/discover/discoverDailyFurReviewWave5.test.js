import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave5.json";
import localMemory from "../../data/discover/localMemory.json";
import { getLocalMemoryForDate } from "./localMemory";

describe("Discover daily FUR review wave 5", () => {
  it("keeps the reviewed FUR batch complete and approved", () => {
    expect(furReview.records).toHaveLength(8);
    expect(furReview.records.filter((record) => record.status === "approved")).toHaveLength(8);
    expect(furReview.records.filter((record) => record.status === "pending_human_review")).toHaveLength(0);
    expect(new Set(furReview.records.map((record) => record.id)).size).toBe(8);
  });

  it("publishes only records with approved FUR", () => {
    const canonicalById = new Map(localMemory.records.map((record) => [record.id, record]));

    for (const review of furReview.records) {
      const record = canonicalById.get(review.id);
      expect(record).toBeTruthy();
      expect(record).toMatchObject({
        title: { fur: review.titleFur },
        summary: { fur: review.summaryFur },
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
    }
  });

  it("returns approved FUR on primary reviewed dates", () => {
    expect(getLocalMemoryForDate({ date: "2026-05-09", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0509-la-riunione-adriatica-di-sicurta",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-09-03", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0903-karel-vladimir-truhlar-poesia-e-pensiero",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-06-21", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0621-luigi-comel-disegno-e-pittura",
      selectionKind: "exact_date",
    });
  });
});
