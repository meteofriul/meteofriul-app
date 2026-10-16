import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave27.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave27.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0902-ferruccio-dardi-e-la-battaglia-di-el-qatara",
  "memory-it-ready-0906-francesco-maria-franceschinis-matematica-e-insegname",
  "memory-it-ready-0819-mario-rigutti-una-vita-dedicata-alle-stelle",
  "memory-it-ready-0921-edoardo-weiss-pioniere-della-psicoanalisi",
  "memory-it-ready-0728-davide-besso-e-il-periodico-di-matematica",
  "memory-it-ready-1028-nicolo-dallaporta-dalle-particelle-alle-galassie",
  "memory-it-ready-0301-nico-naldini-una-voce-autonoma-del-novecento",
];

describe("Discover daily FUR review wave 27", () => {
  it("reviews exactly the seven Italian-selected records", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 7,
      approved: 7,
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

  it("uses reviewed territorial, scientific and historical FUR forms", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("Udin");
    expect(copy).toContain("Triest");
    expect(copy).toContain("Cjasarse de Delizie");
    expect(copy).toContain("Medaie di aur al valôr militâr");
    expect(copy).toContain("astrofisic");
    expect(copy).toContain("psicanalisi");
    expect(copy).toContain("Academiuta di lenga furlana");
    expect(copy).not.toContain("Udine");
    expect(copy).not.toContain("Trieste");
    expect(copy).not.toContain("Casarsa della Delizia");
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
      ["2026-09-06", { city: "Udine", province: "UD" }, reviewedIds[1]],
      ["2026-08-19", { city: "Trieste", province: "TS" }, reviewedIds[2]],
      ["2026-10-28", { city: "Trieste", province: "TS" }, reviewedIds[5]],
    ];
    const secondaries = [
      ["2026-09-02", { city: "Trieste", province: "TS" }, reviewedIds[0]],
      ["2026-09-21", { city: "Trieste", province: "TS" }, reviewedIds[3]],
      ["2026-07-28", { city: "Trieste", province: "TS" }, reviewedIds[4]],
      ["2026-03-01", { city: "Casarsa della Delizia", province: "PN" }, reviewedIds[6]],
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
