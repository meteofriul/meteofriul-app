import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave34.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave34.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 34", () => {
  it("approves all six selected records without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 6,
      approved: 6,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(6);
    expect(furReview.records.every((record) => record.status === "approved")).toBe(true);
  });

  it("covers exactly the Italian selections", () => {
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

  it("publishes approved FUR copy without pending placeholders", () => {
    for (const item of furReview.records) {
      const record = localMemory.records.find((candidate) => candidate.id === item.id);

      expect(record).toBeDefined();
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
    }
  });

  it("keeps proper names and institutional abbreviations stable", () => {
    const zannier = furReview.records.find((record) => record.id.includes("lamberto-zannier"));
    const navarria = furReview.records.find((record) => record.id.includes("mara-navarria"));
    const rizzi = furReview.records.find((record) => record.id.includes("giulia-rizzi"));

    expect(zannier.summaryFur).toContain("ONU");
    expect(zannier.summaryFur).toContain("OSCE");
    expect(zannier.summaryFur).toContain("Feagne");
    expect(navarria.summaryFur).toContain("Mara Navarria");
    expect(rizzi.summaryFur).toContain("Associazione Sportiva Udinese");
  });
});
