import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave2.json";
import localMemory from "../../data/discover/localMemory.json";
import {
  getLocalMemoryForDate,
  getLocalMemorySecondaryForDate,
} from "./localMemory";

describe("Discover daily FUR review wave 2", () => {
  it("keeps the reviewed FUR batch complete and approved", () => {
    expect(furReview.records).toHaveLength(17);
    expect(furReview.records.filter((record) => record.status === "approved")).toHaveLength(17);
    expect(furReview.records.filter((record) => record.status === "pending_human_review")).toHaveLength(0);
    expect(new Set(furReview.records.map((record) => record.id)).size).toBe(17);
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
    expect(getLocalMemoryForDate({ date: "2026-10-12", language: "fur" })).toMatchObject({
      id: "memory-it-ready-1012-l-assedio-di-trieste-del-1813",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-01-01", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0101-paolo-diacono-memoria-longobarda",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-11-03", language: "fur" })).toMatchObject({
      id: "memory-it-ready-1103-le-giornate-di-trieste-del-1953",
      selectionKind: "exact_date",
    });
  });

  it("keeps reviewed secondary records as secondary local memories", () => {
    expect(getLocalMemorySecondaryForDate({
      date: "2026-07-06",
      language: "fur",
      location: { city: "Gorizia", region: "Friuli Venezia Giulia" },
    })).toEqual([
      expect.objectContaining({
        id: "memory-it-ready-0706-giuseppe-tominz-ritratti-tra-gorizia-e-trieste",
        selectionKind: "exact_date_secondary",
      }),
    ]);
  });
});
