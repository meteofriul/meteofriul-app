import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave23.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave23.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0803-felice-venezian-e-l-irredentismo-triestino",
  "memory-it-ready-0712-silvio-marcuzzi-e-la-resistenza-nella-pianura-friula",
  "memory-it-ready-0902-giuseppe-revere-letteratura-e-risorgimento",
  "memory-it-ready-0701-alojzij-res-tra-cultura-italiana-e-slovena",
];

describe("Discover daily FUR review wave 23", () => {
  it("reviews exactly the four Italian-selected records", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 4,
      approved: 4,
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

  it("uses reviewed cultural and territorial FUR forms", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("Triest");
    expect(copy).toContain("Gurize");
    expect(copy).toContain("Redipuie");
    expect(copy).toContain("Resistencje");
    expect(copy).toContain("Risorgiment");
    expect(copy).toContain("planure furlane");
    expect(copy).not.toContain("italiana");
    expect(copy).not.toContain("slovena");
  });

  it("publishes the records only after approved IT and FUR", () => {
    const canonicalRecords = localMemory.records.filter((record) => reviewedIds.includes(record.id));

    expect(canonicalRecords).toHaveLength(reviewedIds.length);
    expect(canonicalRecords.every((record) => (
      record.editorialStatus === "ready_for_discover"
      && record.languageStatus.it === "approved"
      && record.languageStatus.fur === "approved"
      && record.readyForUi === true
      && record.source?.type === "verified_source"
    ))).toBe(true);
  });

  it("serves the reviewed FUR primary and local secondaries on their exact dates", () => {
    expect(getLocalMemoryForDate({
      date: "2026-09-02",
      language: "fur",
      location: { city: "Trieste", province: "TS", region: "Friuli Venezia Giulia" },
    })).toMatchObject({
      id: "memory-it-ready-0902-giuseppe-revere-letteratura-e-risorgimento",
      title: "Giuseppe Revere, leterature e Risorgiment",
      selectionKind: "exact_date",
    });

    expect(getLocalMemorySecondaryForDate({
      date: "2026-07-12",
      language: "fur",
      location: { city: "Fogliano Redipuglia", province: "GO", region: "Friuli Venezia Giulia" },
    }).map((record) => record.id)).toContain(
      "memory-it-ready-0712-silvio-marcuzzi-e-la-resistenza-nella-pianura-friula",
    );
  });
});
