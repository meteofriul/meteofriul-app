import { describe, expect, it } from "vitest";

import italianWave from "../../data/discover/discoverDailyItalianReviewWave33.json";
import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave33.json";
import { getLocalMemorySecondaryForDate } from "./localMemory";

const approvedId = "memory-it-ready-0714-mario-maranzana-e-il-teatro-della-memoria-triestina";

describe("Discover daily FUR review wave 33", () => {
  it("reviews only the Italian-selected record", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 1,
      approved: 1,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records).toHaveLength(1);
    expect(reviewWave.records[0]).toMatchObject({
      id: approvedId,
      status: "approved",
    });

    const canonicalIdsByCandidate = new Map(
      localMemory.records
        .filter((record) => record.candidateId)
        .map((record) => [record.candidateId, record.id]),
    );
    expect(italianWave.keepDaily.map((record) => canonicalIdsByCandidate.get(record.id))).toEqual([
      approvedId,
    ]);
  });

  it("publishes the record only after approved IT and FUR", () => {
    const record = localMemory.records.find((candidate) => candidate.id === approvedId);

    expect(record).toMatchObject({
      editorialStatus: "ready_for_discover",
      languageStatus: {
        it: "approved",
        fur: "approved",
      },
      readyForUi: true,
      source: {
        type: "verified_source",
      },
    });
  });

  it("uses approved FUR copy without unresolved placeholders", () => {
    const record = reviewWave.records[0];
    const copy = `${record.titleFur} ${record.summaryFur}`;

    expect(copy).toContain("Ai 14 di Lui dal 1930");
    expect(copy).toContain("Triest");
    expect(copy).toContain("Atôr");
    expect(copy).toContain("regjist");
    expect(copy).toContain("dramaturc");
    expect(copy).toContain("al met in sene");
    expect(copy).not.toContain("pending_review");
    expect(copy).not.toContain("?");
  });

  it("serves Maranzana as a secondary memory without replacing Slataper", () => {
    const records = getLocalMemorySecondaryForDate({
      date: "2026-07-14",
      language: "fur",
      location: {
        city: "Trieste",
        province: "TS",
        region: "Friuli Venezia Giulia",
      },
    });

    expect(records.map((record) => record.id)).toContain(approvedId);
    expect(records.find((record) => record.id === approvedId)).toMatchObject({
      selectionKind: "exact_date_secondary",
    });
  });
});
