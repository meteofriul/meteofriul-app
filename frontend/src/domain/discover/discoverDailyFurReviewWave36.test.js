import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave36.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave36.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 36", () => {
  it("approves all four selected records without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 4,
      approved: 4,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(4);
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

  it("publishes approved FUR copy while preserving primary and secondary roles", () => {
    const roleByCanonicalId = new Map(
      italianReview.keepDaily.map((selected) => {
        const canonical = localMemory.records.find((record) => record.candidateId === selected.id);
        return [canonical.id, selected.dailyRole];
      }),
    );

    for (const item of furReview.records) {
      const record = localMemory.records.find((candidate) => candidate.id === item.id);

      expect(record).toBeDefined();
      expect(record).toMatchObject({
        dailyRole: roleByCanonicalId.get(item.id),
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

  it("uses established FUR toponyms and controlled historical vocabulary", () => {
    const tarlao = furReview.records.find((record) => record.id.includes("aldo-tarlao"));
    const arena = furReview.records.find((record) => record.id.includes("arena-di-pola"));
    const barzilai = furReview.records.find((record) => record.id.includes("salvatore-barzilai"));

    expect(tarlao.titleFur).toContain("Grau");
    expect(tarlao.summaryFur).toContain("Cjaudistrie");
    expect(arena.summaryFur).toContain("Triest");
    expect(arena.summaryFur).toContain("Gurize");
    expect(barzilai.summaryFur).toContain("irredentisim triestin");
  });

  it("avoids unreviewed specialist sport terms", () => {
    const copy = furReview.records.map((record) => (
      `${record.titleFur} ${record.summaryFur}`
    )).join(" ");

    expect(copy).not.toContain("canotîr");
    expect(copy).not.toContain("farfale");
    expect(copy).not.toContain("pavee");
  });
});
