import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave16.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave16.json";
import { getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0321-marcello-dudovich-e-l-arte-del-manifesto",
  "memory-it-ready-0412-giorgio-carmelich-e-il-futurismo-giuliano",
  "memory-it-ready-0616-lado-piscanc-poesia-dal-confine-orientale",
  "memory-it-ready-0121-nicolo-de-miniussi-da-trieste-a-waterloo",
  "memory-it-ready-0616-amalia-lydia-lalli-dal-friuli-alla-resistenza",
];

describe("Discover daily FUR review wave 16", () => {
  it("reviews exactly the five Italian-selected secondary records", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 5,
      approved: 5,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.map((record) => record.id)).toEqual(reviewedIds);
    expect(reviewWave.records.every((record) => record.status === "approved")).toBe(true);

    const canonicalIdsByCandidate = new Map(
      localMemory.records
        .filter((record) => record.candidateId)
        .map((record) => [record.candidateId, record.id]),
    );
    expect(italianWave.keepDaily.map((record) => canonicalIdsByCandidate.get(record.id))).toEqual(reviewedIds);
  });

  it("publishes the five records only after approved IT and FUR", () => {
    const canonicalRecords = localMemory.records.filter((record) => reviewedIds.includes(record.id));

    expect(canonicalRecords).toHaveLength(reviewedIds.length);
    expect(canonicalRecords.every((record) => (
      record.editorialStatus === "ready_for_discover"
      && record.languageStatus.it === "approved"
      && record.languageStatus.fur === "approved"
      && record.readyForUi === true
      && record.source?.type === "verified_source"
      && record.dailyRole === "secondary"
    ))).toBe(true);
  });

  it("serves same-date secondary memories only when they match the location", () => {
    const triesteJune16 = getLocalMemorySecondaryForDate({
      date: "2026-06-16",
      language: "fur",
      location: { city: "Trieste", province: "TS", region: "Friuli Venezia Giulia" },
    });

    expect(triesteJune16.map((card) => card.id)).toEqual([
      "memory-it-ready-0616-lado-piscanc-poesia-dal-confine-orientale",
      "memory-it-ready-0616-edoardo-muller-una-vita-sui-podi-internazionali",
      "memory-it-ready-0616-giorgio-pilleri-dal-cervello-ai-cetacei",
    ]);

    const udJune16 = getLocalMemorySecondaryForDate({
      date: "2026-06-16",
      language: "fur",
      location: { city: "Flaibano", province: "UD", region: "Friuli Venezia Giulia" },
    });

    expect(udJune16.map((card) => card.id)).toEqual([
      "memory-it-ready-0616-amalia-lydia-lalli-dal-friuli-alla-resistenza",
    ]);
    expect(udJune16[0]).toMatchObject({
      title: "Amalia Lydia Lalli, dal Friûl ae Resistencje",
      selectionKind: "exact_date_secondary",
    });
  });
});
