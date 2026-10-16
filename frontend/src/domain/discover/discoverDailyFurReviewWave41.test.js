import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave41.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave41.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 41", () => {
  it("approves every selected record without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 12,
      approved: 12,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(12);
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

  it("publishes FUR copy while preserving each primary role and priority", () => {
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
        dailyRole: "primary",
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

  it("uses established territorial, cultural and scientific vocabulary", () => {
    const copy = furReview.records.map((item) => `${item.titleFur} ${item.summaryFur}`).join(" ");
    const normalizedCopy = copy.toLocaleLowerCase("it");

    expect(copy).toContain("Triest");
    expect(copy).toContain("Gurize");
    expect(copy).toContain("Pordenon");
    expect(copy).toContain("Udin");
    expect(normalizedCopy).toContain("fumetist");
    expect(normalizedCopy).toContain("tradutôr");
    expect(normalizedCopy).toContain("filolic");
    expect(normalizedCopy).toContain("ricercje biomediche");
    expect(normalizedCopy).toContain("dirit penâl");
    expect(normalizedCopy).toContain("editorie taliane");
  });

  it("does not promote the three candidates held for uncertain dates", () => {
    const heldCandidateIds = new Set(italianReview.hold.map((record) => record.id));
    const canonicalCandidateIds = new Set(localMemory.records.map((record) => record.candidateId));

    for (const candidateId of heldCandidateIds) {
      expect(canonicalCandidateIds.has(candidateId)).toBe(false);
    }
  });
});
