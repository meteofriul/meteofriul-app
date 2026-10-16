import { describe, expect, it } from "vitest";

import {
  getDailyHistoryMemoryPromotionQueue,
  getDailyHistoryMemoryPromotionReview,
  getDailyHistoryMemoryPromotionReviewSummary,
} from "./dailyHistoryMemoryPromotionReview";

describe("daily history memory promotion review", () => {
  it("keeps the promotion review trace while marking the published primary and secondary tranches", () => {
    const records = getDailyHistoryMemoryPromotionReview();
    const summary = getDailyHistoryMemoryPromotionReviewSummary();

    expect(records).toHaveLength(36);
    expect(summary).toMatchObject({
      totalRecords: 36,
      highestPriorityId: "memory-copy-0818-gaetano-kanizsa",
      reviewCoversAllPromotionTrackRecords: false,
      missingFromReview: [],
      extraInReview: [
        "memory-copy-0120-luca-carlevarijs",
        "memory-copy-0121-tito-maniacco",
        "memory-copy-0205-napoleone-cozzi",
        "memory-copy-0225-eugenio-geiringer",
        "memory-copy-0304-afro-basaldella",
        "memory-copy-0316-ernesto-nathan-rogers",
        "memory-copy-0409-stefan-kociancic",
        "memory-copy-0410-claudio-magris",
        "memory-copy-0411-matteo-pertsch",
        "memory-copy-0429-valentin-stanic",
        "memory-copy-0504-lojzka-bratuz",
        "memory-copy-0603-giovanni-battista-bassi",
        "memory-copy-0615-lojze-spacal",
        "memory-copy-0629-biagio-marin",
        "memory-copy-0708-lelio-luttazzi",
        "memory-copy-0813-lella-vignelli",
        "memory-copy-0818-gaetano-kanizsa",
        "memory-copy-0820-enrico-rava",
        "memory-copy-0826-novella-cantarutti",
        "memory-copy-0902-adalgiso-fior",
        "memory-copy-1001-pierluigi-cappello",
        "memory-copy-1005-giorgio-pressburger",
        "memory-copy-1007-giovanni-battista-brusin",
        "memory-copy-1015-giovanni-da-udine",
        "memory-copy-1017-carlo-michelstaedter",
        "memory-copy-1111-giorgio-voghera",
        "memory-copy-1122-silvio-benco",
      ],
      recordsWithoutNeeds: [
        "memory-copy-0603-giovanni-battista-bassi",
        "memory-copy-0504-lojzka-bratuz",
        "memory-copy-0429-valentin-stanic",
        "memory-copy-1005-giorgio-pressburger",
        "memory-copy-0120-luca-carlevarijs",
        "memory-copy-0411-matteo-pertsch",
        "memory-copy-0902-adalgiso-fior",
        "memory-copy-0316-ernesto-nathan-rogers",
        "memory-copy-0409-stefan-kociancic",
        "memory-copy-0225-eugenio-geiringer",
        "memory-copy-1017-carlo-michelstaedter",
      ],
      primaryQueueReadyForPublish: 10,
    });
    expect(summary.byRecommendation).toEqual({
      primary_promotion_candidate: 10,
      secondary_promotion_candidate: 17,
      archive_only_candidate: 9,
    });
  });

  it("keeps the primary promotion tranche explicit and ordered", () => {
    const primaryIds = getDailyHistoryMemoryPromotionQueue()
      .map((record) => record.id);

    expect(primaryIds).toEqual([
      "memory-copy-0818-gaetano-kanizsa",
      "memory-copy-1015-giovanni-da-udine",
      "memory-copy-0121-tito-maniacco",
      "memory-copy-0615-lojze-spacal",
      "memory-copy-0410-claudio-magris",
      "memory-copy-0304-afro-basaldella",
      "memory-copy-0629-biagio-marin",
      "memory-copy-0826-novella-cantarutti",
      "memory-copy-1001-pierluigi-cappello",
      "memory-copy-1017-carlo-michelstaedter",
    ]);
  });

  it("keeps promoted records at the front of the queue with no remaining blockers", () => {
    const queue = getDailyHistoryMemoryPromotionQueue({ limit: 3 });

    expect(queue).toEqual([
      expect.objectContaining({
        id: "memory-copy-0818-gaetano-kanizsa",
        title: expect.objectContaining({ it: "Gaetano Kanizsa e la percezione" }),
        dateAnchors: ["08-18"],
        blockers: [],
      }),
      expect.objectContaining({
        id: "memory-copy-1015-giovanni-da-udine",
        dateAnchors: ["10-15"],
        blockers: [],
      }),
      expect.objectContaining({
        id: "memory-copy-0121-tito-maniacco",
        dateAnchors: ["01-21"],
        blockers: [],
      }),
    ]);
    expect(queue.every((record) => record.blockers.length === 0)).toBe(true);
  });

  it("keeps weaker or lighter records out of the first promotion tranche", () => {
    const archiveIds = getDailyHistoryMemoryPromotionReview()
      .filter((record) => record.recommendation === "archive_only_candidate")
      .map((record) => record.id);

    expect(archiveIds).toEqual([
      "memory-copy-0507-gianni-bisiach",
      "memory-copy-0412-gillo-dorfles",
      "memory-copy-0705-flavio-paulin",
      "memory-copy-0318-eugenio-pilutti",
      "memory-copy-0708-lelio-luttazzi",
      "memory-copy-0706-alberto-spaini",
      "memory-copy-0709-aldo-stellita",
      "memory-copy-1111-giorgio-voghera",
      "memory-copy-0325-giulio-camagni",
    ]);
  });

  it("documents that generic notoriety is not enough for the main daily card", () => {
    const review = getDailyHistoryMemoryPromotionReview();
    const dorfles = review.find((record) => record.id === "memory-copy-0412-gillo-dorfles");
    const stellita = review.find((record) => record.id === "memory-copy-0709-aldo-stellita");
    const bisiach = review.find((record) => record.id === "memory-copy-0507-gianni-bisiach");

    expect([dorfles, stellita, bisiach].map((record) => record.recommendation)).toEqual([
      "archive_only_candidate",
      "archive_only_candidate",
      "archive_only_candidate",
    ]);
    expect(dorfles.reason).toContain("non deve occupare la memoria principale solo per notorieta");
    expect(stellita.reason).toContain("non abbastanza solida come scheda del giorno");
    expect(bisiach.reason).toContain("non abbastanza centrale");
  });
});
