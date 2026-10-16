import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave3.json";
import localMemory from "../../data/discover/localMemory.json";
import {
  getLocalMemoryForDate,
  getLocalMemorySecondaryForDate,
} from "./localMemory";

describe("Discover daily FUR review wave 3", () => {
  it("keeps the reviewed FUR batch complete and approved", () => {
    expect(furReview.records).toHaveLength(12);
    expect(furReview.records.filter((record) => record.status === "approved")).toHaveLength(12);
    expect(furReview.records.filter((record) => record.status === "pending_human_review")).toHaveLength(0);
    expect(new Set(furReview.records.map((record) => record.id)).size).toBe(12);
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
    expect(getLocalMemoryForDate({ date: "2026-01-02", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0102-alessandro-de-stefani-scrittura-e-scena",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-08-06", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0806-la-battaglia-di-doberdo",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-08-29", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0829-michelangelo-grigoletti-pittura-pordenonese",
      selectionKind: "exact_date",
    });
  });

  it("keeps reviewed secondary records as secondary local memories", () => {
    expect(getLocalMemorySecondaryForDate({
      date: "2026-04-14",
      language: "fur",
      location: { city: "Trieste", region: "Friuli Venezia Giulia" },
    })).toEqual([
      expect.objectContaining({
        id: "memory-it-ready-0414-luigi-carnera-astronomia-triestina",
        selectionKind: "exact_date_secondary",
      }),
    ]);
  });
});
