import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave28.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave28.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0209-emilio-mattioni-e-l-architettura-del-friuli-moderno",
  "memory-it-ready-0318-edoardo-del-neri-tra-pittura-e-incisione",
  "memory-it-ready-0325-giuseppe-giacomo-battig-pittore-dell-ottocento-goriz",
  "memory-it-ready-0425-alberto-colantuoni-dal-teatro-al-premio-viareggio",
  "memory-it-ready-0527-giorgio-kirschner-e-la-grande-musica-corale",
  "memory-it-ready-1128-oscar-hermann-lamb-tra-trieste-e-la-secessione-vienn",
  "memory-it-ready-1031-dyalma-stultus-e-l-arte-triestina-del-novecento",
  "memory-it-ready-0620-antonio-mattioni-un-pioniere-del-volo-a-reazione",
  "memory-it-ready-1022-leone-morandini-arte-e-tutela-di-cividale",
];

describe("Discover daily FUR review wave 28", () => {
  it("reviews exactly the nine Italian-selected records", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 9,
      approved: 9,
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

  it("uses reviewed territorial, artistic and technical FUR forms", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("Udin");
    expect(copy).toContain("Gurize");
    expect(copy).toContain("Triest");
    expect(copy).toContain("Cividât dal Friûl");
    expect(copy).toContain("pitôr");
    expect(copy).toContain("incisôr");
    expect(copy).toContain("architet");
    expect(copy).toContain("Nûfcent");
    expect(copy).not.toContain("Udine");
    expect(copy).not.toContain("Gorizia");
    expect(copy).not.toContain("Trieste");
    expect(copy).not.toContain("Cividale del Friuli");
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
    const primaries = [
      ["2026-02-09", { city: "Udine", province: "UD" }, reviewedIds[0]],
      ["2026-04-25", { city: "Trieste", province: "TS" }, reviewedIds[3]],
      ["2026-06-20", { city: "Cividale del Friuli", province: "UD" }, reviewedIds[7]],
    ];
    const secondaries = [
      ["2026-03-18", { city: "Gorizia", province: "GO" }, reviewedIds[1]],
      ["2026-03-25", { city: "Gorizia", province: "GO" }, reviewedIds[2]],
      ["2026-05-27", { city: "Trieste", province: "TS" }, reviewedIds[4]],
      ["2026-11-28", { city: "Trieste", province: "TS" }, reviewedIds[5]],
      ["2026-10-31", { city: "Trieste", province: "TS" }, reviewedIds[6]],
      ["2026-10-22", { city: "Cividale del Friuli", province: "UD" }, reviewedIds[8]],
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
