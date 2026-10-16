import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave48.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave48.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 48", () => {
  it("approves all eleven Italian selections without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 11,
      approved: 11,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(11);
    expect(furReview.records.every((record) => record.status === "approved")).toBe(true);
  });

  it("covers exactly the eleven canonical records selected in Italian", () => {
    const canonicalByCandidateId = new Map(
      localMemory.records.map((record) => [record.candidateId, record]),
    );
    const selectedCanonicalIds = italianReview.keepDaily.map((record) => (
      canonicalByCandidateId.get(record.id)?.id
    ));

    expect(new Set(furReview.records.map((record) => record.id))).toEqual(
      new Set(selectedCanonicalIds),
    );
  });

  it("publishes FUR copy without changing Italian roles or priorities", () => {
    const selectedByCanonicalId = new Map(
      italianReview.keepDaily.map((selected) => {
        const canonical = localMemory.records.find((record) => record.candidateId === selected.id);
        return [canonical?.id, selected];
      }),
    );

    for (const item of furReview.records) {
      const record = localMemory.records.find((candidate) => candidate.id === item.id);
      const selected = selectedByCanonicalId.get(item.id);

      expect(record).toMatchObject({
        dailyRole: selected.dailyRole,
        priority: selected.priority,
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
        title: { fur: item.titleFur },
        summary: { fur: item.summaryFur },
      });
    }
  });

  it("keeps three primary and eight secondary memories", () => {
    const reviewedIds = new Set(furReview.records.map((record) => record.id));
    const canonicalRecords = localMemory.records.filter((record) => reviewedIds.has(record.id));
    const primary = canonicalRecords.filter((record) => record.dailyRole === "primary");
    const secondary = canonicalRecords.filter((record) => record.dailyRole === "secondary");

    expect(canonicalRecords).toHaveLength(11);
    expect(primary.map((record) => record.candidateId)).toEqual([
      "master-fvg-05-06-Q108096676",
      "master-fvg-05-10-Q3749574",
      "master-fvg-06-01-Q2718356",
    ]);
    expect(primary.map((record) => record.dateAnchors[0])).toEqual([
      "06-05",
      "10-05",
      "01-06",
    ]);
    expect(secondary).toHaveLength(8);
  });

  it("uses established territorial vocabulary and preserves uncertain toponyms", () => {
    const copy = furReview.records.map((item) => `${item.titleFur} ${item.summaryFur}`).join(" ");

    expect(copy).toContain("Triest");
    expect(copy).toContain("Monfalcon");
    expect(copy).toContain("Mugle");
    expect(copy).toContain("Codroip");
    expect(copy).toContain("Dael");
    expect(copy).toContain("Gurize");
    expect(copy).toContain("San Lorenzo Isontino");
    expect(copy).toContain("Villafredda di Tarcento");
    expect(copy).not.toContain("pending_review");
  });
});
