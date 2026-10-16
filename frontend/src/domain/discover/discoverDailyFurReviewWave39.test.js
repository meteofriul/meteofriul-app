import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave39.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave39.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 39", () => {
  it("approves every selected record without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 4,
      approved: 4,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(4);
    expect(furReview.records.every((record) => record.status === "approved")).toBe(true);
  });

  it("covers exactly the Italian selection", () => {
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

  it("publishes FUR copy while preserving each role and priority", () => {
    const italianByCanonicalId = new Map(
      italianReview.keepDaily.map((selected) => {
        const canonical = localMemory.records.find((record) => record.candidateId === selected.id);
        return [canonical?.id, selected];
      }),
    );

    for (const item of furReview.records) {
      const record = localMemory.records.find((candidate) => candidate.id === item.id);
      const selected = italianByCanonicalId.get(item.id);

      expect(record).toMatchObject({
        dailyRole: selected.dailyRole,
        priority: selected.priority,
        editorialStatus: "ready_for_discover",
        languageStatus: {
          it: "approved",
          fur: "approved",
        },
        readyForUi: true,
        title: {
          fur: item.titleFur,
        },
        summary: {
          fur: item.summaryFur,
        },
      });
      expect(JSON.stringify(record)).not.toContain("pending_review");
      expect(JSON.stringify(record)).not.toContain("human_review_needed");
    }
  });

  it("uses established territorial and historical vocabulary", () => {
    const copy = furReview.records.map((item) => `${item.titleFur} ${item.summaryFur}`).join(" ");

    expect(copy).toContain("Spilimberc");
    expect(copy).toContain("Vignesie");
    expect(copy).toContain("Resistencje");
    expect(copy).toContain("ricostruzion");
    expect(copy).toContain("taramot");
    expect(copy).toContain("Stâts Unîts");
    expect(copy).toContain("Risiera di San Sabba");
  });

  it("keeps gender and historical-present constructions internally consistent", () => {
    const gherbez = furReview.records.find((record) => record.id.includes("gabriella-gherbez"));
    const oblath = furReview.records.find((record) => record.id.includes("elody-oblath"));

    expect(gherbez.summaryFur).toContain("e nas");
    expect(gherbez.summaryFur).toContain("Partigjane");
    expect(gherbez.summaryFur).toContain("e cjape part");
    expect(gherbez.summaryFur).toContain("e promôf");
    expect(oblath.summaryFur).toContain("e nas");
    expect(oblath.summaryFur).toContain("e scrîf");
    expect(oblath.summaryFur).toContain("e ven internade");
  });
});
