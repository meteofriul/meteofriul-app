import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave40.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave40.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 40", () => {
  it("approves every selected record without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 8,
      approved: 8,
      pendingHumanReview: 0,
    });
    expect(furReview.records).toHaveLength(8);
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

  it("uses established territorial, cultural and historical vocabulary", () => {
    const copy = furReview.records.map((item) => `${item.titleFur} ${item.summaryFur}`).join(" ");

    expect(copy).toContain("Cine");
    expect(copy).toContain("Glesie");
    expect(copy).toContain("Triest");
    expect(copy).toContain("Udin");
    expect(copy).toContain("Padue");
    expect(copy).toContain("gjeografie");
    expect(copy).toContain("fumetist antifassist");
    expect(copy).toContain("Stâts Unîts");
    expect(copy).toContain("Lubiane");
    expect(copy).toContain("circ modern");
  });

  it("keeps the two same-day secondary memories distinct and ordered", () => {
    const deciani = italianReview.keepDaily.find((record) => record.id === "master-fvg-03-08-Q3991119");
    const ieralla = italianReview.keepDaily.find((record) => record.id === "master-fvg-03-08-Q18118106");
    const furIds = new Set(furReview.records.map((record) => record.id));

    expect(deciani.dateIt).toBe("03-08");
    expect(ieralla.dateIt).toBe("03-08");
    expect(deciani.priority).toBeGreaterThan(ieralla.priority);
    expect(furIds.has("memory-it-ready-0803-tiberio-deciani-e-le-radici-del-diritto-penale-moder")).toBe(true);
    expect(furIds.has("memory-it-ready-0803-vittorio-ieralla-e-i-diritti-delle-persone-sorde")).toBe(true);
  });
});
