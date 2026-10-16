import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import italianWave from "../../data/discover/discoverDailyItalianReviewWave21.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave21.json";
import { getLocalMemoryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0430-trieste-l-insurrezione-e-la-corsa-per-la-citta",
  "memory-it-ready-0306-l-atto-istitutivo-dell-universita-di-udine",
  "memory-it-ready-0524-la-consacrazione-del-cimitero-degli-invitti",
  "memory-it-ready-0808-nasce-l-universita-di-trieste",
  "memory-it-ready-1226-a-trieste-nascono-le-assicurazioni-generali",
  "memory-it-ready-0817-tina-modotti-fotografia-e-impegno-civile",
  "memory-it-ready-0212-irene-camber-il-primo-oro-della-scherma-italiana",
  "memory-it-ready-0923-gino-paoli-una-voce-della-canzone-d-autore",
  "memory-it-ready-0604-fedora-barbieri-la-voce-triestina-dell-opera",
  "memory-it-ready-0904-leo-castelli-e-l-arte-americana-del-dopoguerra",
  "memory-it-ready-0517-fausto-cleva-da-trieste-al-metropolitan",
  "memory-it-ready-0917-tullio-kezich-raccontare-il-cinema-italiano",
  "memory-it-ready-1123-sigmund-zois-scienza-e-cultura-dell-illuminismo",
  "memory-it-ready-0926-enzo-bearzot-il-friuli-campione-del-mondo",
  "memory-it-ready-1102-cesare-rubini-campione-in-due-sport",
];

describe("Discover daily FUR review wave 21", () => {
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

  it("uses reviewed territorial and institutional forms", () => {
    const copy = reviewWave.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(copy).toContain("Universitât di Udin");
    expect(copy).toContain("Redipuie");
    expect(copy).toContain("Monfalcon");
    expect(copy).toContain("Dael");
    expect(copy).toContain("Campionât dal mont");
    expect(copy).toContain("Assicurazioni Generali Austro-Italiche");
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

  it("serves the Friulian memory on its exact date", () => {
    expect(getLocalMemoryForDate({
      date: "2026-09-26",
      language: "fur",
      location: { city: "Aiello del Friuli", province: "UD", region: "Friuli Venezia Giulia" },
    })).toMatchObject({
      id: "memory-it-ready-0926-enzo-bearzot-il-friuli-campione-del-mondo",
      title: "Enzo Bearzot, il Friûl campion dal mont",
      selectionKind: "exact_date",
    });
  });
});
