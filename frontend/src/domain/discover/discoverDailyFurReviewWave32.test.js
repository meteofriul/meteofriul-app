import { describe, expect, it } from "vitest";

import italianWave from "../../data/discover/discoverDailyItalianReviewWave32.json";
import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave32.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const approvedIds = [
  "memory-it-ready-1223-olga-brunner-e-un-salotto-per-la-musica-europea",
  "memory-it-ready-1024-gianandrea-gropplero-dalla-resistenza-alla-cooperazi",
  "memory-it-ready-0526-roberto-damiani-e-la-cultura-civile-di-trieste",
  "memory-it-ready-1026-gianpaolo-tosel-e-le-inchieste-sulle-brigate-rosse",
  "memory-it-ready-0929-umberto-manfrin-il-segno-friulano-di-tiramolla",
];

describe("Discover daily FUR review wave 32", () => {
  it("approves the five Italian-selected records after terminology review", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 5,
      approved: 5,
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

  it("publishes all five records with approved IT and FUR", () => {
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

  it("keeps reviewed names, dates and territories without unresolved copy", () => {
    const copy = reviewWave.records
      .filter((record) => record.status === "approved")
      .map((record) => `${record.titleFur} ${record.summaryFur}`)
      .join(" ");

    expect(copy).toContain("Ai 23 di Dicembar dal 1885");
    expect(copy).toContain("Ai 24 di Otubar dal 1921");
    expect(copy).toContain("Ai 26 di Mai dal 1943");
    expect(copy).toContain("Ai 29 di Setembar dal 1927");
    expect(copy).toContain("Triest");
    expect(copy).toContain("Udin");
    expect(copy).toContain("Resistencje");
    expect(copy).not.toContain("pending_review");
    expect(copy).not.toContain("?");
  });

  it("serves two new primaries and three approved local secondaries on their exact dates", () => {
    const primaries = [
      ["2026-10-24", { city: "Udine", province: "UD" }, approvedIds[1]],
      ["2026-09-29", { city: "Udine", province: "UD" }, approvedIds[4]],
    ];
    const secondaries = [
      ["2026-12-23", { city: "Trieste", province: "TS" }, approvedIds[0]],
      ["2026-05-26", { city: "Trieste", province: "TS" }, approvedIds[2]],
      ["2026-10-26", { city: "Udine", province: "UD" }, approvedIds[3]],
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
