import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave25.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave25.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0811-eduard-joseph-d-alton-tra-natura-e-archeologia",
  "memory-it-ready-0911-fabio-doplicher-tra-poesia-e-teatro",
  "memory-it-ready-0918-carlo-podrecca-patriota-e-storico-delle-valli-del-na",
  "memory-it-ready-1104-anton-kasutnik-tra-storia-e-teatro",
];

describe("Discover daily FUR review wave 25", () => {
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

  it("uses reviewed territorial, scientific and cultural FUR forms", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("Aquilee");
    expect(copy).toContain("Triest");
    expect(copy).toContain("Cividât dal Friûl");
    expect(copy).toContain("Valadis dal Nadison");
    expect(copy).toContain("Tarvis");
    expect(copy).toContain("Gurize");
    expect(copy).toContain("archeologjie");
    expect(copy).toContain("dramaturc");
    expect(copy).not.toContain("Aquileia");
    expect(copy).not.toContain("Cividale del Friuli");
    expect(copy).not.toContain("Tarvisio");
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

  it("serves the reviewed FUR primaries and local secondaries on their exact dates", () => {
    expect(getLocalMemoryForDate({
      date: "2026-08-11",
      language: "fur",
      location: { city: "Aquileia", province: "UD", region: "Friuli Venezia Giulia" },
    })).toMatchObject({
      id: "memory-it-ready-0811-eduard-joseph-d-alton-tra-natura-e-archeologia",
      title: "Eduard Joseph d'Alton tra nature e archeologjie",
      selectionKind: "exact_date",
    });

    expect(getLocalMemoryForDate({
      date: "2026-09-11",
      language: "fur",
      location: { city: "Trieste", province: "TS", region: "Friuli Venezia Giulia" },
    })).toMatchObject({
      id: "memory-it-ready-0911-fabio-doplicher-tra-poesia-e-teatro",
      title: "Fabio Doplicher tra poesie e teatri",
      selectionKind: "exact_date",
    });

    expect(getLocalMemorySecondaryForDate({
      date: "2026-09-18",
      language: "fur",
      location: { city: "Cividale del Friuli", province: "UD", region: "Friuli Venezia Giulia" },
    }).map((record) => record.id)).toContain(
      "memory-it-ready-0918-carlo-podrecca-patriota-e-storico-delle-valli-del-na",
    );

    expect(getLocalMemorySecondaryForDate({
      date: "2026-11-04",
      language: "fur",
      location: { city: "Tarvisio", province: "UD", region: "Friuli Venezia Giulia" },
    }).map((record) => record.id)).toContain(
      "memory-it-ready-1104-anton-kasutnik-tra-storia-e-teatro",
    );
  });
});
