import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyFurReviewWave17.json";

const reviewedIds = [
  "memory-it-ready-0703-l-osservatore-triestino-e-la-storia-della-stampa",
  "memory-it-ready-1104-elettra-trieste-citta-della-scienza",
  "memory-it-ready-1216-la-cooperativa-lavoratori-uniti-e-i-diritti",
  "memory-it-ready-1026-il-ritorno-di-trieste-all-italia",
  "memory-it-ready-0628-gabriele-foschiatti-e-l-antifascismo-giuliano",
  "memory-it-ready-0708-edo-mihevc-architettura-e-confine",
  "memory-it-ready-0718-geppino-micheletti-il-medico-di-vergarolla",
  "memory-it-ready-0619-nasce-il-parco-zoo-punta-verde",
  "memory-it-ready-0516-giuseppe-caprin-storia-e-paesaggi-giuliani",
  "memory-it-ready-1130-pre-checo-placerean-e-la-lingua-friulana",
  "memory-it-ready-0910-il-litorale-adriatico-sotto-occupazione-tedesca",
];

describe("Discover daily FUR review wave 17", () => {
  it("reviews the remaining Italian-approved Discover records", () => {
    expect(reviewWave.summary).toEqual({
      totalRecords: 11,
      approved: 11,
      pendingHumanReview: 0,
    });
    expect(reviewWave.records.map((record) => record.id)).toEqual(reviewedIds);
    expect(reviewWave.records.every((record) => record.status === "approved")).toBe(true);
  });

  it("keeps each FUR copy non-empty and linked to an existing canonical record", () => {
    const recordsById = new Map(localMemory.records.map((record) => [record.id, record]));

    for (const review of reviewWave.records) {
      const record = recordsById.get(review.id);
      expect(record).toBeTruthy();
      expect(record.primaryUse).toBe("discover");
      expect(record.editorialStatus).toBe("ready_for_discover");
      expect(record.languageStatus).toMatchObject({
        it: "approved",
        fur: "approved",
      });
      expect(record.readyForUi).toBe(true);
      expect(review.titleFur).not.toContain("pending_review");
      expect(review.summaryFur.length).toBeGreaterThan(80);
    }
  });
});
