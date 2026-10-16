import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave24.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave24.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-1022-camillo-castiglioni-e-l-industria-mitteleuropea",
  "memory-it-ready-0919-teho-teardo-musica-tra-cinema-e-teatro",
  "memory-it-ready-1116-rado-bordon-tra-poesia-e-traduzione",
  "memory-it-ready-1213-luciano-zani-e-la-ritirata-dal-fronte-russo",
  "memory-it-ready-0208-luigi-bevilacqua-sergente-del-genio",
];

describe("Discover daily FUR review wave 24", () => {
  it("reviews exactly the five Italian-selected records", () => {
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

  it("uses reviewed cultural, historical and territorial FUR forms", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("Triest");
    expect(copy).toContain("Pordenon");
    expect(copy).toContain("Cormons");
    expect(copy).toContain("Flaiban");
    expect(copy).toContain("Lusinç");
    expect(copy).toContain("Prime Vuere mondiâl");
    expect(copy).toContain("Medaie di aur al valôr militâr");
    expect(copy).toContain("David di Donatello");
    expect(copy).not.toContain("Pordenone");
    expect(copy).not.toContain("Flaibano");
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

  it("serves the reviewed FUR primaries and local secondary on their exact dates", () => {
    expect(getLocalMemoryForDate({
      date: "2026-10-22",
      language: "fur",
      location: { city: "Trieste", province: "TS", region: "Friuli Venezia Giulia" },
    })).toMatchObject({
      id: "memory-it-ready-1022-camillo-castiglioni-e-l-industria-mitteleuropea",
      title: "Camillo Castiglioni, finance e industrie mitteleuropeane",
      selectionKind: "exact_date",
    });

    expect(getLocalMemorySecondaryForDate({
      date: "2026-09-19",
      language: "fur",
      location: { city: "Pordenone", province: "PN", region: "Friuli Venezia Giulia" },
    }).map((record) => record.id)).toContain(
      "memory-it-ready-0919-teho-teardo-musica-tra-cinema-e-teatro",
    );
  });
});
