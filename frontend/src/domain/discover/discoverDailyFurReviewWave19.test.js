import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave19.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave19.json";
import { getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0814-giorgio-strehler-il-teatro-come-arte-pubblica",
  "memory-it-ready-1030-sergio-amidei-e-il-cinema-neorealista",
  "memory-it-ready-0905-getulio-alviani-luce-e-movimento",
  "memory-it-ready-0523-pietro-kandler-e-la-memoria-di-trieste",
  "memory-it-ready-1218-laura-mancinelli-il-medioevo-raccontato",
  "memory-it-ready-0422-carlo-caneva-e-la-stagione-coloniale-italiana",
];

describe("Discover daily FUR review wave 19", () => {
  it("reviews exactly the six Italian-selected secondary records", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 6,
      approved: 6,
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

  it("uses reviewed Friulian terminology without uncertain literal calques", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("regjie teatrâl");
    expect(copy).toContain("senegjatôr");
    expect(copy).toContain("progjetist");
    expect(copy).toContain("stagjon coloniâl");
    expect(copy).not.toMatch(/testura|vibratile|medievaliste/);
  });

  it("publishes the six records only after approved IT and FUR", () => {
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
    const triesteAugust14 = getLocalMemorySecondaryForDate({
      date: "2026-08-14",
      language: "fur",
      location: { city: "Trieste", province: "TS", region: "Friuli Venezia Giulia" },
    });

    expect(triesteAugust14.find((card) => card.id.includes("giorgio-strehler"))).toMatchObject({
      title: "Giorgio Strehler, il teatri come art publiche",
      selectionKind: "exact_date_secondary",
    });

    const pordenoneAugust14 = getLocalMemorySecondaryForDate({
      date: "2026-08-14",
      language: "fur",
      location: { city: "Pordenone", province: "PN", region: "Friuli Venezia Giulia" },
    });

    expect(pordenoneAugust14.map((card) => card.id)).not.toContain(
      "memory-it-ready-0814-giorgio-strehler-il-teatro-come-arte-pubblica",
    );
  });
});
