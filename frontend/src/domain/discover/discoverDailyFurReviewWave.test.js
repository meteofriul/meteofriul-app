import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave.json";
import localMemory from "../../data/discover/localMemory.json";
import { getLocalMemoryForDate } from "./localMemory";

describe("Discover daily FUR review wave", () => {
  it("keeps the reviewed corpus complete and explicitly split", () => {
    expect(furReview.records).toHaveLength(12);
    expect(furReview.records.filter((record) => record.status === "approved")).toHaveLength(12);
    expect(furReview.records.filter((record) => record.status === "pending_human_review")).toHaveLength(0);
    expect(new Set(furReview.records.map((record) => record.id)).size).toBe(12);
  });

  it("publishes only records with approved FUR", () => {
    const canonicalById = new Map(localMemory.records.map((record) => [record.id, record]));

    for (const review of furReview.records) {
      const record = canonicalById.get(review.id);
      expect(record).toBeTruthy();

      if (review.status === "approved") {
        expect(record).toMatchObject({
          title: { fur: review.titleFur },
          summary: { fur: review.summaryFur },
          editorialStatus: "ready_for_discover",
          languageStatus: { it: "approved", fur: "approved" },
          readyForUi: true,
        });
      } else {
        expect(record).toMatchObject({
          title: { fur: "pending_review" },
          summary: { fur: "pending_review" },
          editorialStatus: "source_verified",
          languageStatus: { it: "approved", fur: "human_review_needed" },
          readyForUi: false,
        });
        expect(review.blockers?.length).toBeGreaterThan(0);
      }
    }
  });

  it("returns approved FUR on the reviewed dates", () => {
    expect(getLocalMemoryForDate({ date: "2026-04-04", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0404-giani-stuparich-e-la-trieste-del-novecento",
      title: "Giani Stuparich e la Triest dal Nûfcent",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-04-23", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0423-l-eccidio-di-via-ghega",
      title: "La stragje di vie Ghega",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-04-03", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0403-l-eccidio-di-opicina",
      title: "La stragje di Opicina",
      selectionKind: "exact_date",
    });
    expect(getLocalMemoryForDate({ date: "2026-08-04", language: "fur" })).toMatchObject({
      id: "memory-it-ready-0804-l-attentato-al-deposito-costiero-siot",
      title: "L'atentât al dipuesit costîr SIOT",
      selectionKind: "exact_date",
    });
  });
});
