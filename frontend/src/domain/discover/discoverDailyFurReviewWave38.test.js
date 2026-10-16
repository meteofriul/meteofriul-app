import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave38.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave38.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 38", () => {
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

  it("publishes the FUR copy while preserving role and priority", () => {
    const item = furReview.records[0];
    const record = localMemory.records.find((candidate) => candidate.id === item.id);

    expect(record).toMatchObject({
      dailyRole: "secondary",
      priority: 95,
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

  it("uses established FUR territorial, historical and institutional vocabulary", () => {
    const item = furReview.records[0];
    const copy = `${item.titleFur} ${item.summaryFur}`;

    expect(copy).toContain("Sacîl");
    expect(copy).toContain("leçs ecezionâls");
    expect(copy).toContain("fassisim");
    expect(copy).toContain("Assemblee Costituente");
    expect(copy).toContain("senatôr");
  });

  it("keeps the historical-present construction internally consistent", () => {
    const copy = furReview.records[0].summaryFur;

    expect(copy).toContain("al nas");
    expect(copy).toContain("al vote");
    expect(copy).toContain("al torne");
    expect(copy).toContain("al ven elet");
    expect(copy).toContain("al devente");
  });
});
