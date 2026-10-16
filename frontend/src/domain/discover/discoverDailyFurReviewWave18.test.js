import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave18.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave18.json";
import { getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-1204-gae-aulenti-architettura-senza-confini",
  "memory-it-ready-0418-ardito-desio-dal-friuli-al-k2",
  "memory-it-ready-1211-eugenio-curiel-scienza-e-resistenza",
  "memory-it-ready-1122-jacopo-pirona-e-il-vocabolario-friulano",
  "memory-it-ready-0726-carlo-sgorlon-il-friuli-nei-romanzi",
  "memory-it-ready-0311-salvatore-pincherle-e-l-analisi-moderna",
  "memory-it-ready-0410-victor-de-sabata-una-bacchetta-internazionale",
  "memory-it-ready-0828-enrico-peressutti-e-l-architettura-moderna",
  "memory-it-ready-0130-annibale-comessatti-geometria-da-udine",
  "memory-it-ready-0728-alberto-mazzucato-musica-e-insegnamento",
];

describe("Discover daily FUR review wave 18", () => {
  it("reviews exactly the ten Italian-selected secondary records", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 10,
      approved: 10,
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

  it("uses the approved official Friulian place names", () => {
    const copy = reviewWave.records.map((record) => record.summaryFur).join(" ");

    expect(copy).toContain("Palaçûl");
    expect(copy).toContain("Palme");
    expect(copy).toContain("Dignan");
    expect(copy).toContain("Cjassà");
    expect(copy).toContain("Pinçan");
    expect(copy).not.toMatch(/Palazzolo dello Stella|Palmanova|Dignano|Cassacco|Pinzano al Tagliamento/);
  });

  it("publishes the ten records only after approved IT and FUR", () => {
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
    const cassaccoJuly26 = getLocalMemorySecondaryForDate({
      date: "2026-07-26",
      language: "fur",
      location: { city: "Cassacco", province: "UD", region: "Friuli Venezia Giulia" },
    });

    expect(cassaccoJuly26.map((card) => card.id)).toContain(
      "memory-it-ready-0726-carlo-sgorlon-il-friuli-nei-romanzi",
    );
    expect(cassaccoJuly26.find((card) => card.id.includes("carlo-sgorlon"))).toMatchObject({
      title: "Carlo Sgorlon, il Friûl tai romans",
      selectionKind: "exact_date_secondary",
    });

    const pordenoneJuly26 = getLocalMemorySecondaryForDate({
      date: "2026-07-26",
      language: "fur",
      location: { city: "Pordenone", province: "PN", region: "Friuli Venezia Giulia" },
    });

    expect(pordenoneJuly26.map((card) => card.id)).not.toContain(
      "memory-it-ready-0726-carlo-sgorlon-il-friuli-nei-romanzi",
    );
  });
});
