import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave7.json";
import { getLocalMemoryForDate } from "./localMemory";

describe("Discover daily FUR review wave 7", () => {
  it("documents a complete FUR review for the promoted cultural batch", () => {
    expect(reviewWave.summary).toMatchObject({
      totalRecords: 12,
      approved: 12,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.every((record) => record.status === "approved")).toBe(true);
    expect(reviewWave.records.map((record) => record.id)).toEqual([
      "memory-it-ready-0129-adelaide-ristori-il-teatro-da-cividale",
      "memory-it-ready-0717-leopoldo-metlicovitz-arte-e-manifesti",
      "memory-it-ready-0720-arduino-berlam-architettura-triestina",
      "memory-it-ready-0828-antonio-somma-parole-per-la-scena",
      "memory-it-ready-0303-arturo-rietti-ritratti-triestini",
      "memory-it-ready-0606-umberto-veruda-pittura-a-trieste",
      "memory-it-ready-0914-marcello-mascherini-scultura-e-scena",
      "memory-it-ready-0824-augusto-cernigoj-avanguardia-a-trieste",
      "memory-it-ready-0127-odorico-politi-pittura-udinese",
      "memory-it-ready-0227-marcello-d-olivo-progetto-e-paesaggio",
      "memory-it-ready-1220-teobaldo-ciconi-teatro-e-poesia",
      "memory-it-ready-1217-arturo-nathan-pittura-e-inquietudine",
    ]);
  });

  it("publishes the reviewed records without duplicating localMemory ids", () => {
    const ids = reviewWave.records.map((record) => record.id);
    const canonicalRecords = localMemory.records.filter((record) => ids.includes(record.id));

    expect(canonicalRecords).toHaveLength(ids.length);
    expect(new Set(localMemory.records.map((record) => record.id)).size).toBe(localMemory.records.length);
    expect(canonicalRecords.every((record) => (
      record.editorialStatus === "ready_for_discover"
      && record.languageStatus.it === "approved"
      && record.languageStatus.fur === "approved"
      && record.readyForUi === true
      && record.source?.type === "verified_source"
    ))).toBe(true);
  });

  it("serves the FUR copies on their exact dates", () => {
    expect(getLocalMemoryForDate({
      date: "2026-01-29",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-0129-adelaide-ristori-il-teatro-da-cividale",
      title: "Adelaide Ristori, il teatri di Cividât",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-12-17",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-1217-arturo-nathan-pittura-e-inquietudine",
      title: "Arturo Nathan, piture triestine",
      selectionKind: "exact_date",
    });
  });
});
