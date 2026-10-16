import { describe, expect, it } from "vitest";

import italianWave from "../../data/discover/discoverDailyItalianReviewWave31.json";
import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave31.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const approvedIds = [
  "memory-it-ready-0623-ivan-grbec-e-la-musica-slovena-di-trieste",
  "memory-it-ready-1125-lucia-rodocanachi-la-traduttrice-rimasta-nell-ombra",
  "memory-it-ready-0102-riccardo-cassin-alpinismo-e-resistenza",
  "memory-it-ready-0509-roberto-malaroda-e-la-geologia-sul-campo",
  "memory-it-ready-0711-teddy-reno-da-trieste-alla-canzone-italiana",
  "memory-it-ready-0503-renato-balestra-e-l-alta-moda-italiana",
  "memory-it-ready-0515-francesco-carnelutti-e-la-scuola-del-diritto",
  "memory-it-ready-1221-moira-orfei-la-regina-del-circo",
  "memory-it-ready-0909-francesco-robortello-e-il-metodo-degli-umanisti",
  "memory-it-ready-0829-romilda-pantaleoni-la-prima-desdemona-di-verdi",
  "memory-it-ready-0305-alfred-jaell-pianista-triestino-sulle-scene-europee",
];

describe("Discover daily FUR review wave 31", () => {
  it("approves the eleven Italian-selected records after terminology review", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 11,
      approved: 11,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.filter((record) => record.status === "approved").map((record) => record.id)).toEqual(approvedIds);
    expect(reviewWave.records.filter((record) => record.status === "pending_human_review")).toEqual([]);

    const canonicalIdsByCandidate = new Map(
      localMemory.records
        .filter((record) => record.candidateId)
        .map((record) => [record.candidateId, record.id]),
    );
    expect(italianWave.keepDaily.map((record) => canonicalIdsByCandidate.get(record.id))).toEqual(
      reviewWave.records.map((record) => record.id),
    );
  });

  it("publishes all eleven records with approved IT and FUR", () => {
    const approvedRecords = localMemory.records.filter((record) => approvedIds.includes(record.id));

    expect(approvedRecords).toHaveLength(approvedIds.length);
    expect(approvedRecords.every((record) => (
      record.editorialStatus === "ready_for_discover"
      && record.languageStatus.it === "approved"
      && record.languageStatus.fur === "approved"
      && record.readyForUi === true
      && record.source?.type === "verified_source"
    ))).toBe(true);
  });

  it("keeps reviewed names, toponyms and the corrected Robortello date", () => {
    const copy = reviewWave.records
      .filter((record) => record.status === "approved")
      .map((record) => `${record.titleFur} ${record.summaryFur}`)
      .join(" ");

    expect(copy).toContain("Triest");
    expect(copy).toContain("Udin");
    expect(copy).toContain("Codroip");
    expect(copy).toContain("Resistencje");
    expect(copy).toContain("Ai 9 di Setembar dal 1516");
    expect(copy).toContain("Alfred Jaëll");
    expect(copy).not.toContain("pending_review");
    expect(copy).not.toContain("?");
  });

  it("serves six new primaries and five approved local secondaries on their exact dates", () => {
    const primaries = [
      ["2026-06-23", { city: "Trieste", province: "TS" }, approvedIds[0]],
      ["2026-11-25", { city: "Trieste", province: "TS" }, approvedIds[1]],
      ["2026-07-11", { city: "Trieste", province: "TS" }, approvedIds[4]],
      ["2026-05-03", { city: "Trieste", province: "TS" }, approvedIds[5]],
      ["2026-12-21", { city: "Codroipo", province: "UD" }, approvedIds[7]],
      ["2026-09-09", { city: "Udine", province: "UD" }, approvedIds[8]],
    ];
    const secondaries = [
      ["2026-01-02", { city: "San Vito al Tagliamento", province: "PN" }, approvedIds[2]],
      ["2026-05-09", { city: "San Canzian d'Isonzo", province: "GO" }, approvedIds[3]],
      ["2026-08-29", { city: "Udine", province: "UD" }, approvedIds[9]],
      ["2026-03-05", { city: "Trieste", province: "TS" }, approvedIds[10]],
      ["2026-05-15", { city: "Udine", province: "UD" }, approvedIds[6]],
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
