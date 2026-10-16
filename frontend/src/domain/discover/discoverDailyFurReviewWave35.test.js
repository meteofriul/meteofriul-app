import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave35.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave35.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 35", () => {
  it("approves all seven selected records without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 7,
      approved: 7,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(7);
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

  it("uses official FUR toponyms and preserves Slovene diacritics", () => {
    const cernic = furReview.records.find((record) => record.id.includes("matej-cernic"));
    const micheletto = furReview.records.find((record) => record.id.includes("giovanni-micheletto"));
    const mian = furReview.records.find((record) => record.id.includes("michele-mian"));

    expect(cernic.titleFur).toContain("Savogne dal Lusinç");
    expect(cernic.summaryFur).toContain("Matej Černič");
    expect(cernic.summaryFur).toContain("Polisportiva Soča");
    expect(micheletto.titleFur).toContain("Sacîl");
    expect(mian.summaryFur).toContain("Aquilee");
  });

  it("avoids the two unsafe Italian metaphors in FUR titles", () => {
    const titles = furReview.records.map((record) => record.titleFur).join(" ");

    expect(titles).not.toContain("tet dal mont");
    expect(titles).not.toContain(" al arint olimpic");
    expect(titles).toContain("medaie di arint olimpiche");
  });
});
