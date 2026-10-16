import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave9.json";
import { getLocalMemoryForDate } from "./localMemory";

describe("Discover daily FUR review wave 9", () => {
  it("documents a complete FUR review for the promoted historical batch", () => {
    expect(reviewWave.summary).toMatchObject({
      totalRecords: 12,
      approved: 12,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.every((record) => record.status === "approved")).toBe(true);
    expect(reviewWave.records.map((record) => record.id)).toEqual([
      "memory-it-ready-0806-gorizia-e-la-sesta-battaglia-dell-isonzo",
      "memory-it-ready-1029-pozzuolo-del-friuli-battaglia-di-retroguardia",
      "memory-it-ready-0415-sacile-una-battaglia-napoleonica",
      "memory-it-ready-0401-aquileia-sotto-assedio",
      "memory-it-ready-0729-aquileia-nuovo-assedio-nella-storia-romana",
      "memory-it-ready-0316-valvasone-e-il-passaggio-napoleonico",
      "memory-it-ready-0523-le-battaglie-dell-isonzo",
      "memory-it-ready-0326-paolo-maurensig-narrativa-da-gorizia",
      "memory-it-ready-1207-gino-valle-progetto-e-architettura",
      "memory-it-ready-0120-luca-carlevarijs-vedute-e-pittura",
      "memory-it-ready-0124-gojmir-anton-kos-pittura-tra-confini",
      "memory-it-ready-0912-ermes-midena-architettura-friulana",
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

  it("serves the FUR copies on primary exact dates", () => {
    expect(getLocalMemoryForDate({
      date: "2026-10-29",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-1029-pozzuolo-del-friuli-battaglia-di-retroguardia",
      title: "Puçûl dal Friûl, bataie di retrovuardie",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-01-20",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-0120-luca-carlevarijs-vedute-e-pittura",
      title: "Luca Carlevarijs, vedudis e piture",
      selectionKind: "exact_date",
    });
  });
});
