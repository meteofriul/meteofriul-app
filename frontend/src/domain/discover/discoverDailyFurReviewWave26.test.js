import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave26.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave26.json";
import { getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0418-alcide-paolini-tra-scrittura-ed-editoria",
  "memory-it-ready-0227-ugo-guarino-arte-e-liberta",
  "memory-it-ready-0321-mario-ceconi-scultura-del-novecento",
  "memory-it-ready-0816-fulvio-papi-filosofia-e-impegno-civile",
  "memory-it-ready-0818-demetrio-livaditi-e-la-ciarla",
];

describe("Discover daily FUR review wave 26", () => {
  it("reviews exactly the five Italian-selected secondary records", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 5,
      approved: 5,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.map((record) => record.id)).toEqual(reviewedIds);
    expect(reviewWave.records.every((record) => record.status === "approved")).toBe(true);
    expect(italianWave.keepDaily.every((record) => record.dailyRole === "secondary")).toBe(true);

    const canonicalIdsByCandidate = new Map(
      localMemory.records
        .filter((record) => record.candidateId)
        .map((record) => [record.candidateId, record.id]),
    );
    expect(italianWave.keepDaily.map((record) => canonicalIdsByCandidate.get(record.id))).toEqual(reviewedIds);
  });

  it("uses approved territorial and cultural FUR forms without uncertain specialist labels", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("Udin");
    expect(copy).toContain("Triest");
    expect(copy).toContain("Friûl");
    expect(copy).toContain("Nûfcent");
    expect(copy).toContain("Bienâl di Vignesie");
    expect(copy).toContain("Risorgiment triestin");
    expect(copy).not.toContain("Udine");
    expect(copy).not.toContain("Trieste");
    expect(copy).not.toContain("diretôr editoriâl");
    expect(copy).not.toContain("riforme psichiatriche");
    expect(copy).not.toContain("filosofie teoretiche");
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

  it("serves every reviewed record as a local secondary on its exact date", () => {
    const cases = [
      ["2026-04-18", { city: "Udine", province: "UD" }, reviewedIds[0]],
      ["2026-02-27", { city: "Trieste", province: "TS" }, reviewedIds[1]],
      ["2026-03-21", { city: "Trieste", province: "TS" }, reviewedIds[2]],
      ["2026-08-16", { city: "Trieste", province: "TS" }, reviewedIds[3]],
      ["2026-08-18", { city: "Trieste", province: "TS" }, reviewedIds[4]],
    ];

    for (const [date, location, expectedId] of cases) {
      expect(getLocalMemorySecondaryForDate({
        date,
        language: "fur",
        location: { ...location, region: "Friuli Venezia Giulia" },
      }).map((record) => record.id)).toContain(expectedId);
    }
  });
});
