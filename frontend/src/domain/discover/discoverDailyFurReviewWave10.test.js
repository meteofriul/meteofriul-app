import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave10.json";
import { getLocalMemoryForDate } from "./localMemory";

describe("Discover daily FUR review wave 10", () => {
  it("documents a complete FUR review for the promoted cultural batch", () => {
    expect(reviewWave.summary).toMatchObject({
      totalRecords: 12,
      approved: 12,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.every((record) => record.status === "approved")).toBe(true);
    expect(reviewWave.records.map((record) => record.id)).toEqual([
      "memory-it-ready-0719-aquileia-e-il-sacco-di-attila",
      "memory-it-ready-1227-pietro-zorutti-poesia-friulana",
      "memory-it-ready-0418-luigi-spazzapan-pittura-di-frontiera",
      "memory-it-ready-1007-armando-pizzinato-pittura-e-impegno",
      "memory-it-ready-1110-marco-salvador-medioevo-raccontato",
      "memory-it-ready-0311-miroslav-kosuta-poesia-slovena-da-trieste",
      "memory-it-ready-0616-giuseppe-bernardino-bison-pittura-da-palmanova",
      "memory-it-ready-0222-peter-butkovic-parole-di-confine",
      "memory-it-ready-0130-francesco-chiarottini-arte-da-cividale",
      "memory-it-ready-0228-antonio-rotta-pittura-da-gorizia",
      "memory-it-ready-1211-alfonso-canciani-scultura-dal-collio",
      "memory-it-ready-0802-viktor-sulcic-architettura-oltre-l-adriatico",
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
      date: "2026-07-19",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-0719-aquileia-e-il-sacco-di-attila",
      title: "Aquilee e il sac di Atile",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-12-27",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-1227-pietro-zorutti-poesia-friulana",
      title: "Pietro Zorutti, poesie furlane",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2026-06-16",
      language: "fur",
    })).toMatchObject({
      id: "memory-it-ready-0616-giuseppe-bernardino-bison-pittura-da-palmanova",
      title: "Giuseppe Bernardino Bison, piture di Palmanove",
      selectionKind: "exact_date",
    });
  });
});
