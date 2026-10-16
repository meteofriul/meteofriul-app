import { describe, expect, it } from "vitest";

import {
  getDailyHistoryMemoryFurReview,
  getDailyHistoryMemoryFurReviewIds,
  getDailyHistoryMemoryFurReviewSummary,
} from "./dailyHistoryMemoryFurReview";
import { getDailyHistoryMemoryFinalReviewIds } from "./dailyHistoryMemoryFinalReview";

describe("daily history memory FUR review", () => {
  it("mirrors the final review queue without publishing records", () => {
    expect(getDailyHistoryMemoryFurReviewIds()).toEqual(getDailyHistoryMemoryFinalReviewIds());
  });

  it("approves reviewed primary and secondary FUR drafts", () => {
    const summary = getDailyHistoryMemoryFurReviewSummary();

    expect(summary).toEqual({
      totalRecords: 36,
      bySurface: {
        archive: 16,
        daily_primary: 9,
        daily_secondary: 11,
      },
      byFurReviewStatus: {
        approved: 20,
        pending_human_review: 16,
      },
      recordsWithReviewQuestions: 16,
      furApproved: 20,
      readyForUi: 20,
    });
  });

  it("keeps publication blockers explicit for unpublished candidates", () => {
    const records = getDailyHistoryMemoryFurReview();
    const unpublishedRecords = records.filter((record) => record.furReviewStatus !== "approved");

    expect(unpublishedRecords.every((record) => (
      record.publicationBlockers.includes("fur_human_review") &&
      record.publicationBlockers.includes("ready_for_discover_status") &&
      record.publicationBlockers.includes("ready_for_ui_flag")
    ))).toBe(true);
    expect(records.filter((record) => record.furReviewStatus === "approved").every((record) => (
      record.publicationBlockers.length === 0
    ))).toBe(true);
  });

  it("keeps the reviewed daily primary FUR drafts explicit", () => {
    const records = getDailyHistoryMemoryFurReview();
    const kanizsa = records.find((record) => record.id === "memory-copy-0818-gaetano-kanizsa");
    const giovanni = records.find((record) => record.id === "memory-copy-1015-giovanni-da-udine");
    const maniacco = records.find((record) => record.id === "memory-copy-0121-tito-maniacco");
    const spacal = records.find((record) => record.id === "memory-copy-0615-lojze-spacal");

    expect(kanizsa.summary.furDraft).toContain("psicolog e pitôr");
    expect(giovanni.title.furDraft).toBe("Zuan di Udin, boteghis e Rinassiment");
    expect(maniacco.summary.furDraft).toContain("racont civîl");
    expect(spacal.summary.furDraft).toContain("piere, segns e paisaç");
  });

  it("keeps the reviewed daily secondary FUR drafts explicit", () => {
    const records = getDailyHistoryMemoryFurReview();
    const bassi = records.find((record) => record.id === "memory-copy-0603-giovanni-battista-bassi");
    const fior = records.find((record) => record.id === "memory-copy-0902-adalgiso-fior");
    const rogers = records.find((record) => record.id === "memory-copy-0316-ernesto-nathan-rogers");
    const geiringer = records.find((record) => record.id === "memory-copy-0225-eugenio-geiringer");

    expect(bassi.summary.furDraft).toContain("storie urbane di Pordenon");
    expect(fior.summary.furDraft).toContain("Al mûr a Udin Adalgiso Fior");
    expect(rogers.summary.furDraft).toContain("progetâ nol è dome costruî");
    expect(geiringer.summary.furDraft).toContain("une citât e cambie muse");
  });

  it("keeps the reviewed archive FUR drafts explicit without making them daily cards", () => {
    const records = getDailyHistoryMemoryFurReview();
    const cozzi = records.find((record) => record.id === "memory-copy-0205-napoleone-cozzi");
    const pilutti = records.find((record) => record.id === "memory-copy-0318-eugenio-pilutti");
    const spaini = records.find((record) => record.id === "memory-copy-0706-alberto-spaini");
    const voghera = records.find((record) => record.id === "memory-copy-1111-giorgio-voghera");

    expect(cozzi.summary.furDraft).toContain("Al nas a Triest Napoleone Cozzi");
    expect(pilutti.summary.furDraft).toContain("Al mûr a Triest Eugenio Pilutti");
    expect(spaini.summary.furDraft).toContain("Al nas a Triest Alberto Spaini");
    expect(voghera.summary.furDraft).toContain("Al mûr a Triest Giorgio Voghera");
    expect([cozzi, pilutti, spaini, voghera].every((record) => record.surface === "archive")).toBe(true);
  });
});
