import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave6.json";
import { getLocalMemoryForDate } from "./localMemory";

describe("Discover daily FUR review wave 6", () => {
  it("documents a complete FUR review for the promoted backlog records", () => {
    expect(reviewWave.summary).toMatchObject({
      totalRecords: 2,
      approved: 2,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.every((record) => record.status === "approved")).toBe(true);
    expect(reviewWave.records.map((record) => record.id)).toEqual([
      "memory-backlog-0714-scipio-slataper",
      "memory-backlog-0229-pietro-blaserna",
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

  it("serves the FUR copies on their exact dates", () => {
    expect(getLocalMemoryForDate({
      date: "2026-07-14",
      language: "fur",
    })).toMatchObject({
      id: "memory-backlog-0714-scipio-slataper",
      title: "Scipio Slataper, Triest e il Cjars",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({
      date: "2028-02-29",
      language: "fur",
    })).toMatchObject({
      id: "memory-backlog-0229-pietro-blaserna",
      title: "Pietro Blaserna, science intun dì râr",
      selectionKind: "exact_date",
    });
  });
});
