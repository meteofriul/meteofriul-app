import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave44.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave44.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 44", () => {
  it("approves the ten Italian selections without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 10,
      approved: 10,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(10);
    expect(furReview.records.every((record) => record.status === "approved")).toBe(true);
  });

  it("covers exactly the ten canonical records selected in Italian", () => {
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

  it("keeps two primary memories and eight secondary ones", () => {
    const reviewedIds = new Set(furReview.records.map((record) => record.id));
    const canonicalRecords = localMemory.records.filter((record) => reviewedIds.has(record.id));

    expect(canonicalRecords.filter((record) => record.dailyRole === "primary")).toHaveLength(2);
    expect(canonicalRecords.filter((record) => record.dailyRole === "secondary")).toHaveLength(8);
  });

  it("uses established territorial and subject vocabulary", () => {
    const copy = furReview.records.map((item) => `${item.titleFur} ${item.summaryFur}`).join(" ");

    expect(copy).toContain("Triest");
    expect(copy).toContain("Udin");
    expect(copy).toContain("Pordenon");
    expect(copy).toContain("palacanestri");
    expect(copy).toContain("canotaç");
    expect(copy).toContain("marce atletiche");
    expect(copy).not.toContain("pending_review");
  });
});
