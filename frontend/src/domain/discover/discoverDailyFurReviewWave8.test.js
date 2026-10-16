import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave8.json";
import { getLocalMemoryForDate } from "./localMemory";

describe("Discover daily FUR review wave 8", () => {
  it("documents a complete FUR review for the promoted historical-cultural batch", () => {
    expect(reviewWave.summary).toMatchObject({
      totalRecords: 10,
      approved: 10,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.every((record) => record.status === "approved")).toBe(true);
    expect(reviewWave.records.map((record) => record.id)).toEqual([
      "memory-it-ready-1210-farfa-futurismo-da-trieste",
      "memory-it-ready-0407-bruno-croatto-pittura-e-incisione",
      "memory-it-ready-0920-carolus-cergoly-trieste-in-versi",
      "memory-it-ready-0301-carlo-marin-muggia-e-scrittura",
      "memory-it-ready-0214-bruno-giordano-sanzin-poesia-triestina",
      "memory-it-ready-0415-renzo-rosso-narrativa-triestina",
      "memory-it-ready-0816-ugo-mioni-libri-e-ragazzi",
      "memory-it-ready-1021-filippo-zamboni-poesia-e-risorgimento",
      "memory-it-ready-0924-enrico-nordio-forme-per-trieste",
      "memory-it-ready-1002-pierviviano-zecchini-san-vito-e-cultura",
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
      date: "2026-12-10",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-1210-farfa-futurismo-da-trieste",
      title: "Farfa, futurisim di Triest",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-10-02",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-1002-pierviviano-zecchini-san-vito-e-cultura",
      title: "Pierviviano Zecchini, San Vît e culture",
      selectionKind: "exact_date",
    });
  });
});
