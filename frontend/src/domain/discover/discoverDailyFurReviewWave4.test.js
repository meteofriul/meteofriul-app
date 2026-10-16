import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave4.json";
import localMemory from "../../data/discover/localMemory.json";
import {
  getLocalMemoryForDate,
  getLocalMemorySecondaryForDate,
} from "./localMemory";

describe("Discover daily FUR review wave 4", () => {
  it("keeps the reviewed FUR batch complete and approved", () => {
    expect(furReview.records).toHaveLength(5);
    expect(furReview.records.filter((record) => record.status === "approved")).toHaveLength(5);
    expect(furReview.records.filter((record) => record.status === "pending_human_review")).toHaveLength(0);
    expect(new Set(furReview.records.map((record) => record.id)).size).toBe(5);
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
    expect(getLocalMemoryForDate({ date: "2026-01-08", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0108-bernardo-maria-de-rubeis-storia-da-cividale",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-02-16", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0216-ruggero-timeus-trieste-e-il-novecento",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-10-16", language: "fur" })).toMatchObject({
      id: "memory-it-ready-1016-louis-toffoli-pittura-triestina-d-origine",
      selectionKind: "exact_date",
    });
  });

  it("keeps reviewed secondary records as secondary local memories", () => {
    expect(getLocalMemorySecondaryForDate({
      date: "2026-02-26",
      language: "fur",
      location: { city: "Trieste", region: "Friuli Venezia Giulia" },
    })).toEqual([
      expect.objectContaining({
        id: "memory-it-ready-0226-alexander-kircher-mare-e-pittura",
        selectionKind: "exact_date_secondary",
      }),
    ]);
  });
});
