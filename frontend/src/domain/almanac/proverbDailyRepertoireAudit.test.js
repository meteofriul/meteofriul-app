import { describe, expect, it } from "vitest";

import candidateReview from "../../data/almanac/proverbCandidateReview.json";
import proverbSources from "../../data/almanac/ostermannProverbSources.json";
import { getCandidateReviewSummary } from "./proverbCandidateReview";
import { getProverbArchiveReadiness } from "./proverbArchiveReadiness";

describe("proverb daily repertoire audit", () => {
  it("tracks the first promotion pool for daily proverbs", () => {
    const summary = getCandidateReviewSummary(candidateReview);

    expect(summary.totalReviewed).toBe(122);
    expect(summary.promotionCandidateCount).toBe(66);
    expect(summary.byRecommendation).toMatchObject({
      promote_after_fur_review: 65,
      replace_existing_after_review: 1,
      promoted_after_fur_review: 17,
      archive_only: 29,
      variant_not_selected: 10,
    });
    expect(summary.byRecommendation.hold ?? 0).toBe(0);
    expect(summary.byRecommendation.needs_context ?? 0).toBe(0);
  });

  it("tracks Ostermann pages still available for controlled extraction", () => {
    const readiness = getProverbArchiveReadiness();

    expect(readiness.candidateSourcePages).toBe(42);
    expect(readiness.extractedCandidateSourcePages).toBe(39);
    expect(readiness.discoverBacklogSourcePages).toBe(3);
    expect(readiness.closedSourcePages).toBe(42);
    expect(readiness.pendingSourcePages).toBe(0);
    expect(readiness.prioritySourcePages).toBe(36);
  });

  it("keeps web or external sources out of the first remediation step", () => {
    const candidatePages = proverbSources.candidatePages || [];
    const backlogPages = candidatePages.filter((page) => page.status === "discover_backlog_extracted");

    expect(backlogPages.map((page) => page.pdfPage)).toEqual([44, 46, 111]);
    expect(new Set(candidatePages.map((page) => page.priority))).toEqual(new Set(["P1", "P2"]));
    expect(proverbSources.source.label).toBe("Ostermann 1894");
  });

  it("tracks the controlled extraction batches from Ostermann pages", () => {
    const readiness = getProverbArchiveReadiness();
    const extractedPages = proverbSources.candidatePages
      .filter((page) => page.status === "candidate_extracted")
      .map((page) => page.pdfPage);
    const queuedPages = proverbSources.candidatePages
      .filter((page) => page.status === "to_extract")
      .map((page) => page.pdfPage);
    const discoverBacklogPages = proverbSources.candidatePages
      .filter((page) => page.status === "discover_backlog_extracted")
      .map((page) => page.pdfPage);

    expect(readiness.candidateProverbs).toBe(122);
    expect(readiness.extractedCandidateSourcePages).toBe(39);
    expect(queuedPages).toEqual([]);
    expect(discoverBacklogPages).toEqual([44, 46, 111]);
    expect(extractedPages).toEqual(
      expect.arrayContaining([29, 31, 43, 57, 58, 59, 60, 61, 62, 63, 68, 83, 87, 94, 96, 97, 99, 100, 101, 102, 104, 126, 130, 131, 132, 140, 141, 146, 189, 192, 608, 609, 674])
    );
  });
});
