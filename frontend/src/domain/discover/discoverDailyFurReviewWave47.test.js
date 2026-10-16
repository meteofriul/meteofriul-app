import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave47.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave47.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 47", () => {
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

  it("keeps one primary and ten secondary memories", () => {
    const reviewedIds = new Set(furReview.records.map((record) => record.id));
    const canonicalRecords = localMemory.records.filter((record) => reviewedIds.has(record.id));
    const primary = canonicalRecords.filter((record) => record.dailyRole === "primary");
    const secondary = canonicalRecords.filter((record) => record.dailyRole === "secondary");

    expect(canonicalRecords).toHaveLength(11);
    expect(primary).toHaveLength(1);
    expect(primary[0]).toMatchObject({
      candidateId: "master-fvg-23-09-Q3907862",
      dateAnchors: ["09-13"],
    });
    expect(secondary).toHaveLength(10);
  });

  it("uses established territorial vocabulary and preserves proper names", () => {
    const copy = furReview.records.map((item) => `${item.titleFur} ${item.summaryFur}`).join(" ");

    expect(copy).toContain("Udin");
    expect(copy).toContain("Triest");
    expect(copy).toContain("Roncjis dai Legionaris");
    expect(copy).toContain("Cjars");
    expect(copy).toContain("Alps Juliis");
    expect(copy).toContain("Neanderthal");
    expect(copy).toContain("Last Minute Market");
    expect(copy).toContain("Ferruccio Busoni");
    expect(copy).not.toContain("pending_review");
  });
});
