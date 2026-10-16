import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave13.json";
import { getLocalMemoryForDate, getLocalMemorySecondaryForDate } from "./localMemory";

const reviewedIds = [
  "memory-it-ready-0901-egidio-feruglio-geologia-ed-esplorazione",
  "memory-it-ready-0310-harry-bertoia-arte-e-design-da-arzene",
  "memory-it-ready-0417-giusto-gervasutti-e-l-alpinismo",
  "memory-it-ready-1008-giandomenico-picco-diplomazia-senza-armi",
  "memory-it-ready-1008-pietro-ellero-diritto-e-criminologia",
  "memory-it-ready-0328-giovanni-boaga-matematica-e-cartografia",
  "memory-it-ready-0730-livio-gratton-astrofisica-da-trieste",
  "memory-it-ready-1027-irene-di-spilimbergo-pittura-e-poesia",
  "memory-it-ready-0116-rodolfo-lipizer-violino-e-musica-da-gorizia",
  "memory-it-ready-1212-milko-kos-storia-tra-gorizia-e-il-mondo-sloveno",
  "memory-it-ready-0727-samuele-romanin-il-mestiere-dello-storico",
  "memory-it-ready-0525-ireneo-della-croce-cronache-di-trieste",
  "memory-it-ready-0528-vincenzo-joppi-libri-e-memoria-di-udine",
  "memory-it-ready-1128-costantino-dardi-architettura-e-progetto",
  "memory-it-ready-0722-maria-tore-barbina-una-voce-poetica",
];

describe("Discover daily FUR review wave 13", () => {
  it("contains a complete FUR review for all selected records", () => {
    expect(reviewWave.summary).toMatchObject({
      totalRecords: 15,
      approved: 15,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.every((record) => record.status === "approved")).toBe(true);
    expect(reviewWave.records.map((record) => record.id)).toEqual(reviewedIds);
  });

  it("publishes the reviewed records without duplicating canonical ids", () => {
    const canonicalRecords = localMemory.records.filter((record) => reviewedIds.includes(record.id));

    expect(canonicalRecords).toHaveLength(reviewedIds.length);
    expect(new Set(localMemory.records.map((record) => record.id)).size).toBe(localMemory.records.length);
    expect(canonicalRecords.every((record) => (
      record.editorialStatus === "ready_for_discover"
      && record.languageStatus.it === "approved"
      && record.languageStatus.fur === "approved"
      && record.readyForUi === true
      && record.source?.type === "verified_source"
    ))).toBe(true);
  });

  it("serves representative FUR copies on their exact dates", () => {
    expect(getLocalMemoryForDate({
      date: "2026-03-10",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-0310-harry-bertoia-arte-e-design-da-arzene",
      title: "Harry Bertoia, art e design di Arzin",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-10-27",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-1027-irene-di-spilimbergo-pittura-e-poesia",
      title: "Irene di Spilimbergo, piture e poesie",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-12-12",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-1212-milko-kos-storia-tra-gorizia-e-il-mondo-sloveno",
      title: "Milko Kos, storie tra Gurize e il mont sloven",
      selectionKind: "exact_date",
    });
  });

  it("serves Ellero as a local secondary memory for Pordenone", () => {
    expect(getLocalMemorySecondaryForDate({
      date: "2026-10-08",
      language: "fur",
      location: { city: "Pordenone", region: "Friuli Venezia Giulia" },
    })).toEqual([
      expect.objectContaining({
        id: "memory-it-ready-1008-pietro-ellero-diritto-e-criminologia",
        title: "Pietro Ellero, dirit e criminologjie",
        dailyRole: "secondary",
        selectionKind: "exact_date_secondary",
      }),
    ]);
  });
});
