import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave12.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

describe("Discover daily FUR review wave 12", () => {
  it("documents a complete FUR review for the promoted scientific and cultural records", () => {
    expect(reviewWave.summary).toMatchObject({
      totalRecords: 15,
      approved: 15,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.every((record) => record.status === "approved")).toBe(true);
    expect(reviewWave.records.map((record) => record.id)).toEqual([
      "memory-it-ready-0117-carlo-marchesetti-archeologia-e-botanica-da-trieste",
      "memory-it-ready-0201-fausto-romitelli-musica-contemporanea-da-gorizia",
      "memory-it-ready-0203-giovanni-battista-benardelli-pittura-e-fotografia",
      "memory-it-ready-0207-ugo-morin-matematica-e-antifascismo",
      "memory-it-ready-0213-guido-horn-d-arturo-astronomia-da-trieste",
      "memory-it-ready-0320-bruno-cester-fisica-e-astronomia",
      "memory-it-ready-0505-alessandro-lustig-medicina-da-trieste",
      "memory-it-ready-0610-roberto-bazlen-libri-e-scoperte-editoriali",
      "memory-it-ready-0710-filosseno-luzzatto-studi-e-lingue",
      "memory-it-ready-0827-giacomo-ciamician-chimica-e-sole",
      "memory-it-ready-1030-giusto-fontanini-storia-e-archeologia",
      "memory-it-ready-1114-antonio-taramelli-archeologia-da-udine",
      "memory-it-ready-1126-ugo-cara-scultura-e-design-a-muggia",
      "memory-it-ready-0410-vittorio-cadel-poesia-e-pittura-da-fanna",
      "memory-it-ready-1013-bindo-chiurlo-critica-e-poesia",
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
      date: "2026-01-17",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-0117-carlo-marchesetti-archeologia-e-botanica-da-trieste",
      title: "Carlo Marchesetti, archeologjie e botaniche di Triest",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-08-27",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-0827-giacomo-ciamician-chimica-e-sole",
      title: "Giacomo Ciamician, chimiche e soreli",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-11-14",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-1114-antonio-taramelli-archeologia-da-udine",
      title: "Antonio Taramelli, archeologjie di Udin",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-10-13",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-1013-bindo-chiurlo-critica-e-poesia",
      title: "Bindo Chiurlo, critiche leterarie e poesie",
      dailyRole: "primary",
      selectionKind: "exact_date",
    });
  });

  it("serves the reviewed FUR secondary memory only for its local province", () => {
    expect(getLocalMemorySecondaryForDate({
      date: "2026-04-10",
      language: "fur",
      location: { city: "Pordenone", region: "Friuli Venezia Giulia" },
    })).toEqual([
      expect.objectContaining({
        id: "memory-it-ready-0410-vittorio-cadel-poesia-e-pittura-da-fanna",
        title: "Vittorio Cadel, poesie e piture di Fanna",
        dailyRole: "secondary",
        selectionKind: "exact_date_secondary",
      }),
    ]);
  });
});
