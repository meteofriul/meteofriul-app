import { describe, expect, it } from "vitest";

import {
  getProverbArchiveReadiness,
  isPromotionReadyCandidate,
  needsEncodingReview,
} from "./proverbArchiveReadiness";

describe("proverb archive readiness", () => {
  it("tracks the complete proverb archive separately from the fixed-date schedule", () => {
    const readiness = getProverbArchiveReadiness();

    expect(readiness.targetDailySlots).toBe(366);
    expect(readiness.totalProverbs).toBe(379);
    expect(readiness.candidateProverbs).toBeGreaterThanOrEqual(25);
    expect(readiness.reviewedPromotionCandidates).toBeGreaterThan(10);
    expect(readiness.promotionReadyCandidates).toBe(0);
    expect(readiness.almanacEligibleProverbs).toBe(369);
    expect(readiness.labReadyProverbs).toBe(345);
    expect(readiness.humanReviewRequiredProverbs).toBe(345);
    expect(readiness.datedSlots).toBe(33);
    expect(readiness.brokenScheduleReferences).toEqual([]);
    expect(readiness.missingDailySlots).toBe(333);
    expect(readiness.candidateSourcePages).toBeGreaterThanOrEqual(20);
    expect(readiness.extractedCandidateSourcePages).toBe(39);
    expect(readiness.discoverBacklogSourcePages).toBe(3);
    expect(readiness.closedSourcePages).toBe(42);
    expect(readiness.pendingSourcePages).toBe(0);
    expect(readiness.readyForDailyCalendar).toBe(false);
  });

  it("detects imported proverb records that still need encoding review", () => {
    expect(needsEncodingReview({ fur: "Cui grans si f\u00c3\u00a2s il st\u00c3\u00a2r." })).toBe(true);
    expect(needsEncodingReview({ fur: "Avril bagnât, la benedizion sul semenât." })).toBe(false);
    expect(needsEncodingReview({ fur: "Ros di sere, bon timp si spere." })).toBe(false);
  });

  it("keeps candidate records out of the publishable archive until review is complete", () => {
    const candidateArchive = {
      records: [
        {
          fur: "Ros di sere, bon timp si spere.",
          it: "Rosso di sera, si spera bel tempo.",
          review: { status: "candidate" },
          source: { pdfPage: 103 },
        },
        {
          fur: "Vint di mont, aghe dongje.",
          it: "Vento di monte, acqua vicina.",
          review: { status: "ready" },
          source: { pdfPage: 105 },
        },
      ],
    };

    const readiness = getProverbArchiveReadiness({
      candidateReviewArchive: {
        records: [
          {
            id: "first",
            recommendation: "promote_after_fur_review",
          },
          {
            id: "second",
            recommendation: "needs_context",
          },
        ],
      },
      candidateArchive,
      proverbItems: [],
    });

    expect(readiness.candidateProverbs).toBe(2);
    expect(readiness.reviewedPromotionCandidates).toBe(0);
    expect(readiness.promotionReadyCandidates).toBe(1);
  });

  it("reports schedule entries that point to missing proverb records", () => {
    const readiness = getProverbArchiveReadiness({
      candidateArchive: { records: [] },
      dailySchedule: {
        "01-01": "known-proverb",
        "01-02": "missing-proverb",
        default: "missing-default",
      },
      proverbItems: [
        {
          id: "known-proverb",
          fur: "Proverbi cognossût.",
          it: "Proverbio conosciuto.",
          almanacEligible: true,
        },
      ],
    });

    expect(readiness.brokenScheduleReferences).toEqual([
      { date: "01-02", proverbId: "missing-proverb" },
      { date: "default", proverbId: "missing-default" },
    ]);
  });

  it("requires clean text and source page before a candidate can be promoted", () => {
    expect(
      isPromotionReadyCandidate({
        fur: "Cui grans si f\u00c3\u00a2s il st\u00c3\u00a2r.",
        it: "Granello dopo granello si riempie lo staio.",
        review: { status: "ready" },
        source: { pdfPage: 15 },
      })
    ).toBe(false);

    expect(
      isPromotionReadyCandidate({
        fur: "Ros di sere, bon timp si spere.",
        it: "Rosso di sera, si spera bel tempo.",
        review: { status: "ready" },
        source: { pdfPage: 103 },
      })
    ).toBe(true);
  });

  it("can describe a complete curated calendar without depending on fixture size", () => {
    const proverbItems = Array.from({ length: 500 }, (_, index) => ({
      id: `p-${index + 1}`,
      fur: `Proverbi ${index + 1}`,
      it: `Proverbio ${index + 1}`,
      almanacEligible: index < 366,
    }));
    const dailySchedule = Object.fromEntries(
      Array.from({ length: 366 }, (_, index) => [
        `${String(Math.floor(index / 31) + 1).padStart(2, "0")}-${String((index % 31) + 1).padStart(2, "0")}`,
        `p-${index + 1}`,
      ])
    );

    const readiness = getProverbArchiveReadiness({
      proverbItems,
      dailySchedule,
      sourcePlan: {
        target: {
          archiveMinimum: 500,
          dailySlots: 366,
        },
      },
    });

    expect(readiness.missingDailySlots).toBe(0);
    expect(readiness.missingArchiveRecords).toBe(0);
    expect(readiness.readyForDailyCalendar).toBe(true);
  });
});
