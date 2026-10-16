import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave11.json";
import { getLocalMemoryForDate } from "./localMemory";

describe("Discover daily FUR review wave 11", () => {
  it("documents a complete FUR review for the promoted cultural and scientific batch", () => {
    expect(reviewWave.summary).toMatchObject({
      totalRecords: 11,
      approved: 11,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.every((record) => record.status === "approved")).toBe(true);
    expect(reviewWave.records.map((record) => record.id)).toEqual([
      "memory-it-ready-0122-luigi-loir-gorizia-e-l-illustrazione",
      "memory-it-ready-0111-guido-fulignot-ritratti-da-trieste",
      "memory-it-ready-0609-fabio-beltram-fisica-da-gorizia",
      "memory-it-ready-0103-roberto-car-e-la-fisica-computazionale",
      "memory-it-ready-0723-michele-vendruscolo-proteine-e-biofisica",
      "memory-it-ready-0220-vigilio-de-grassi-architettura-da-grado",
      "memory-it-ready-0202-iginio-montini-scultura-a-cividale",
      "memory-it-ready-0105-alberto-riccoboni-architettura-e-storia-dell-arte",
      "memory-it-ready-0831-enrico-de-cillia-pittura-e-carso",
      "memory-it-ready-1112-bruno-sacco-design-da-udine",
      "memory-it-ready-0601-doro-levi-archeologia-e-storia-dell-arte",
    ]);
  });

  it("publishes the reviewed records without duplicating localMemory ids", () => {
    const ids = reviewWave.records.map((record) => record.id);
    const canonicalRecords = localMemory.records.filter((record) => ids.includes(record.id));

    expect(canonicalRecords).toHaveLength(ids.length);
    expect(new Set(localMemory.records.map((record) => record.id)).size).toBe(localMemory.records.length);
    expect(canonicalRecords.every((record) => (
      record.editorialStatus === "ready_for_discover"
      && record.languageStatus.it === "approved"
      && record.languageStatus.fur === "approved"
      && record.readyForUi === true
      && record.source?.type === "verified_source"
    ))).toBe(true);
  });

  it("serves the FUR copies on primary exact dates", () => {
    expect(getLocalMemoryForDate({
      date: "2026-01-22",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-0122-luigi-loir-gorizia-e-l-illustrazione",
      title: "Luigi Loir, Gurize e la ilustrazion",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-07-23",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-0723-michele-vendruscolo-proteine-e-biofisica",
      title: "Michele Vendruscolo, proteinis e biofisiche",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-11-12",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-1112-bruno-sacco-design-da-udine",
      title: "Bruno Sacco, design di Udin",
      selectionKind: "exact_date",
    });
  });
});
