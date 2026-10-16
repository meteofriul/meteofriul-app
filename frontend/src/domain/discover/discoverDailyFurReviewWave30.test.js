import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave30.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave30.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-1120-rita-rosani-e-la-resistenza",
  "memory-it-ready-0531-dante-vaglieri-e-gli-scavi-di-ostia",
  "memory-it-ready-1112-marina-apollonio-oltre-il-cerchio",
  "memory-it-ready-0618-antonio-zanon-e-l-economia-del-friuli-moderno",
  "memory-it-ready-1026-cecilia-deganutti-infermiera-e-partigiana",
  "memory-it-ready-0927-sergio-stefanutti-e-l-aeronautica-sperimentale",
  "memory-it-ready-0813-ida-marcaria-sopravvissuta-ad-auschwitz",
  "memory-it-ready-0320-pinko-tomazic-e-l-antifascismo-sloveno-a-trieste",
  "memory-it-ready-1209-bruno-vasari-la-memoria-della-deportazione",
  "memory-it-ready-0425-gianni-widmer-pioniere-del-volo-adriatico",
  "memory-it-ready-1222-anna-maria-di-giorgio-e-la-fisiologia-dei-sensi",
  "memory-it-ready-0110-enrico-rocca-una-voce-tra-cultura-italiana-e-tedesca",
];

describe("Discover daily FUR review wave 30", () => {
  it("reviews exactly the twelve Italian-selected records", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 12,
      approved: 12,
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

  it("uses reviewed FUR forms and keeps names and toponyms intact", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("Triest");
    expect(copy).toContain("Udin");
    expect(copy).toContain("Gurize");
    expect(copy).toContain("Sant Denêl dal Friûl");
    expect(copy).toContain("Pinko Tomažič");
    expect(copy).toContain("Resistencje");
    expect(copy).toContain("archeologjichis");
    expect(copy).toContain("aviazion");
    expect(copy).toContain("deportazion");
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

  it("serves the three new primaries and nine local secondaries on their exact dates", () => {
    const primaries = [
      ["2026-11-20", { city: "Trieste", province: "TS" }, reviewedIds[0]],
      ["2026-06-18", { city: "Udine", province: "UD" }, reviewedIds[3]],
      ["2026-12-09", { city: "Trieste", province: "TS" }, reviewedIds[8]],
    ];
    const secondaries = [
      ["2026-05-31", { city: "Trieste", province: "TS" }, reviewedIds[1]],
      ["2026-11-12", { city: "Trieste", province: "TS" }, reviewedIds[2]],
      ["2026-10-26", { city: "Udine", province: "UD" }, reviewedIds[4]],
      ["2026-09-27", { city: "Udine", province: "UD" }, reviewedIds[5]],
      ["2026-08-13", { city: "Trieste", province: "TS" }, reviewedIds[6]],
      ["2026-03-20", { city: "Trieste", province: "TS" }, reviewedIds[7]],
      ["2026-04-25", { city: "Trieste", province: "TS" }, reviewedIds[9]],
      ["2026-12-22", { city: "San Daniele del Friuli", province: "UD" }, reviewedIds[10]],
      ["2026-01-10", { city: "Gorizia", province: "GO" }, reviewedIds[11]],
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
