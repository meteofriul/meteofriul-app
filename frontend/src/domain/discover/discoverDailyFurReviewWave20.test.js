import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave20.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave20.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0219-caterina-percoto-le-storie-del-friuli",
  "memory-it-ready-0328-ermes-di-colloredo-e-la-poesia-friulana",
  "memory-it-ready-0112-amedeo-giacomini-lingua-e-poesia",
  "memory-it-ready-1105-federico-tavan-la-voce-di-andreis",
  "memory-it-ready-0804-celso-macor-il-confine-come-incontro",
  "memory-it-ready-0211-pre-antoni-beline-scrivere-in-friulano",
  "memory-it-ready-0723-giuseppe-marchetti-e-la-cultura-friulana",
  "memory-it-ready-0612-margherita-hack-trieste-e-le-stelle",
  "memory-it-ready-0126-fulvio-tomizza-scrivere-il-confine",
  "memory-it-ready-0305-pasolini-casarsa-e-la-poesia-friulana",
];

describe("Discover daily FUR review wave 20", () => {
  it("reviews exactly the ten Italian-selected records", () => {
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

  it("uses the reviewed Friulian names and territorial forms", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("San Lurinç di Soleschian");
    expect(copy).toContain("Colorêt di Montalban");
    expect(copy).toContain("Vildivar");
    expect(copy).toContain("Viarsa");
    expect(copy).toContain("Vençon");
    expect(copy).toContain("pre Antoni Beline");
    expect(copy).toContain("Glemone Josef Marchet");
    expect(copy).toContain("Cjasarse");
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
    ))).toBe(true);
  });

  it("serves a new primary memory on its exact date", () => {
    const pasolini = getLocalMemoryForDate({
      date: "2026-03-05",
      language: "fur",
    });

    expect(pasolini).toMatchObject({
      id: "memory-it-ready-0305-pasolini-casarsa-e-la-poesia-friulana",
      title: "Pasolini, Cjasarse e la poesie furlane",
      selectionKind: "exact_date",
    });
  });

  it("serves same-date secondary memories only when they match the location", () => {
    const triesteJune12 = getLocalMemorySecondaryForDate({
      date: "2026-06-12",
      language: "fur",
      location: { city: "Trieste", province: "TS", region: "Friuli Venezia Giulia" },
    });

    expect(triesteJune12.find((card) => card.id.includes("margherita-hack"))).toMatchObject({
      title: "Margherita Hack, Triest e lis stelis",
      selectionKind: "exact_date_secondary",
    });

    const pordenoneJune12 = getLocalMemorySecondaryForDate({
      date: "2026-06-12",
      language: "fur",
      location: { city: "Pordenone", province: "PN", region: "Friuli Venezia Giulia" },
    });

    expect(pordenoneJune12.map((card) => card.id)).not.toContain(
      "memory-it-ready-0612-margherita-hack-trieste-e-le-stelle",
    );
  });
});
