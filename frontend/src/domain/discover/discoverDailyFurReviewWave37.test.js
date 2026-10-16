import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave37.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave37.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 37", () => {
  it("approves the selected record without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 1,
      approved: 1,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(1);
    expect(furReview.records[0].status).toBe("approved");
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

  it("publishes the FUR copy while preserving the secondary role", () => {
    const item = furReview.records[0];
    const record = localMemory.records.find((candidate) => candidate.id === item.id);

    expect(record).toMatchObject({
      dailyRole: "secondary",
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
  });

  it("uses established FUR territorial and cultural vocabulary", () => {
    const item = furReview.records[0];
    const copy = `${item.titleFur} ${item.summaryFur}`;

    expect(copy).toContain("Gurize");
    expect(copy).toContain("piture");
    expect(copy).toContain("scuele");
    expect(copy).toContain("insegnament");
    expect(copy).toContain("citât di confin");
  });

  it("does not introduce uncertain profession labels", () => {
    const copy = furReview.records.map((record) => (
      `${record.titleFur} ${record.summaryFur}`
    )).join(" ");

    expect(copy).not.toContain("pitore");
    expect(copy).not.toContain("pitorese");
    expect(copy).not.toContain("maestre");
  });
});
