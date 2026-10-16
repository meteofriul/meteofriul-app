import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave22.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave22.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0928-la-torbiera-cichinot-diventa-biotopo-regionale",
  "memory-it-ready-0918-l-inaugurazione-del-sacrario-di-redipuglia",
  "memory-it-ready-0227-i-mondiali-juniores-di-sci-sulle-montagne-friulane",
  "memory-it-ready-0923-gli-europei-di-pallavolo-arrivano-a-gorizia",
  "memory-it-ready-0527-trieste-ospita-il-mondiale-di-calcio-del-1934",
  "memory-it-ready-0131-il-mondiale-di-ciclocross-a-corva",
  "memory-it-ready-1018-la-prima-partita-allo-stadio-nereo-rocco",
  "memory-it-ready-1222-giorgio-oberweger-il-primo-podio-olimpico-italiano-n",
  "memory-it-ready-1019-mario-foschiani-e-la-resistenza-friulana",
];

describe("Discover daily FUR review wave 22", () => {
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

  it("uses reviewed territorial, naturalistic and sports forms", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("Cjassà");
    expect(copy).toContain("Redipuie");
    expect(copy).toContain("Tarvis");
    expect(copy).toContain("Nevee");
    expect(copy).toContain("Scluse");
    expect(copy).toContain("Ravasclêt");
    expect(copy).toContain("Gurize");
    expect(copy).toContain("bale a svol");
    expect(copy).toContain("Daçan di Pordenon");
    expect(copy).toContain("Cussignà");
    expect(copy).toContain("Udin");
    expect(copy).not.toContain("volei");
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

  it("serves a primary FUR memory and the reviewed secondary on their exact dates", () => {
    expect(getLocalMemoryForDate({
      date: "2026-10-19",
      language: "fur",
      location: { city: "Udine", province: "UD", region: "Friuli Venezia Giulia" },
    })).toMatchObject({
      id: "memory-it-ready-1019-mario-foschiani-e-la-resistenza-friulana",
      title: "Mario Foschiani e la Resistencje furlane",
      selectionKind: "exact_date",
    });

    expect(getLocalMemorySecondaryForDate({
      date: "2026-09-18",
      language: "fur",
      location: { city: "Fogliano Redipuglia", province: "GO", region: "Friuli Venezia Giulia" },
    }).map((record) => record.id)).toContain(
      "memory-it-ready-0918-l-inaugurazione-del-sacrario-di-redipuglia",
    );
  });
});
