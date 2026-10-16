import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave42.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave42.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 42", () => {
  it("approves the complete Italian selection", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 12,
      approved: 12,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(12);
    expect(furReview.records.every((record) => record.status === "approved")).toBe(true);
  });

  it("covers exactly the canonical records selected in Italian", () => {
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

  it("preserves roles and priorities while publishing the FUR copy", () => {
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

  it("uses the established territorial vocabulary", () => {
    const copy = furReview.records.map((item) => `${item.titleFur} ${item.summaryFur}`).join(" ");

    expect(copy).toContain("Friûl");
    expect(copy).toContain("Udin");
    expect(copy).toContain("Triest");
    expect(copy).toContain("Gurize");
    expect(copy).toContain("Glemone");
    expect(copy).toContain("San Vît dal Tiliment");
    expect(copy).not.toContain("pending_review");
  });
});
