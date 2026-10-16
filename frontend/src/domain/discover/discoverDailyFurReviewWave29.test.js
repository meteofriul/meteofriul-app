import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave29.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave29.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0821-renato-ricamo-e-la-scuola-italiana-di-fisica-nuclear",
  "memory-it-ready-0616-edoardo-muller-una-vita-sui-podi-internazionali",
  "memory-it-ready-1122-davide-liani-musica-e-formazione-in-friuli",
  "memory-it-ready-0606-edvard-rusjan-pioniere-del-volo",
  "memory-it-ready-0221-emilio-comici-e-l-alpinismo-moderno",
  "memory-it-ready-0331-laura-conti-scienza-e-ambientalismo",
  "memory-it-ready-0103-corinna-ulcigrai-e-la-matematica-dei-sistemi-dinamic",
  "memory-it-ready-0203-giulio-gatti-casazza-dalla-scala-al-metropolitan",
  "memory-it-ready-0907-sergio-della-pergola-e-la-demografia-contemporanea",
  "memory-it-ready-0110-paul-henreid-da-trieste-a-casablanca",
  "memory-it-ready-0726-alessandro-trotter-pioniere-della-cecidologia",
  "memory-it-ready-1214-italico-brass-pittura-tra-gorizia-e-venezia",
  "memory-it-ready-0315-sasa-santel-pittura-e-musica-tra-due-culture",
  "memory-it-ready-0825-gino-parin-ritratti-dalla-trieste-europea",
  "memory-it-ready-0601-joze-pirjevec-storico-dei-balcani",
];

describe("Discover daily FUR review wave 29", () => {
  it("reviews exactly the fifteen Italian-selected records", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 15,
      approved: 15,
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

  it("uses reviewed territorial and disciplinary FUR forms", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("Triest");
    expect(copy).toContain("Udin");
    expect(copy).toContain("Gurize");
    expect(copy).toContain("Vignesie");
    expect(copy).toContain("fisiche nucleâr");
    expect(copy).toContain("pionîr dal svol");
    expect(copy).toContain("pitôr");
    expect(copy).toContain("storic dai Balcans");
    expect(copy).not.toContain("Udine");
    expect(copy).not.toContain("Gorizia");
    expect(copy).not.toContain("Trieste");
    expect(copy).not.toContain("pending_review");
    expect(copy).not.toContain("?");
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

  it("serves the six new primaries and nine local secondaries on their exact dates", () => {
    const primaries = [
      ["2026-08-21", { city: "Trieste", province: "TS" }, reviewedIds[0]],
      ["2026-09-07", { city: "Trieste", province: "TS" }, reviewedIds[8]],
      ["2026-01-10", { city: "Trieste", province: "TS" }, reviewedIds[9]],
      ["2026-12-14", { city: "Gorizia", province: "GO" }, reviewedIds[11]],
      ["2026-03-15", { city: "Gorizia", province: "GO" }, reviewedIds[12]],
      ["2026-08-25", { city: "Trieste", province: "TS" }, reviewedIds[13]],
    ];
    const secondaries = [
      ["2026-06-16", { city: "Trieste", province: "TS" }, reviewedIds[1]],
      ["2026-11-22", { city: "Camino al Tagliamento", province: "UD" }, reviewedIds[2]],
      ["2026-06-06", { city: "Trieste", province: "TS" }, reviewedIds[3]],
      ["2026-02-21", { city: "Trieste", province: "TS" }, reviewedIds[4]],
      ["2026-03-31", { city: "Udine", province: "UD" }, reviewedIds[5]],
      ["2026-01-03", { city: "Trieste", province: "TS" }, reviewedIds[6]],
      ["2026-02-03", { city: "Udine", province: "UD" }, reviewedIds[7]],
      ["2026-07-26", { city: "Udine", province: "UD" }, reviewedIds[10]],
      ["2026-06-01", { city: "Trieste", province: "TS" }, reviewedIds[14]],
    ];

    for (const [date, location, expectedId] of primaries) {
      expect(getLocalMemoryForDate({
        date,
        language: "fur",
        location: { ...location, region: "Friuli Venezia Giulia" },
      })).toMatchObject({ id: expectedId, selectionKind: "exact_date" });
    }

    for (const [date, location, expectedId] of secondaries) {
      expect(getLocalMemorySecondaryForDate({
        date,
        language: "fur",
        location: { ...location, region: "Friuli Venezia Giulia" },
      }).map((record) => record.id)).toContain(expectedId);
    }
  });
});
