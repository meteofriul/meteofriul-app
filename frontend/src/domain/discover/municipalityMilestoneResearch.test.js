import { describe, expect, it } from "vitest";

import milestoneFurReview from "../../data/discover/municipalityMilestoneFurReview.pn-zero-01.json";
import milestonePromotion from "../../data/discover/municipalityMilestonePromotion.pn-zero-01.json";
import milestoneResearch from "../../data/discover/municipalityMilestoneResearch.pn-zero-01.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";

const EXPECTED_MUNICIPALITIES = [
  ["093016", "Clauzetto"],
  ["093020", "Fanna"],
  ["093026", "Meduno"],
  ["093045", "Tramonti di Sopra"],
  ["093046", "Tramonti di Sotto"],
];

const ALLOWED_SOURCE_TYPES = new Set([
  "official_municipality",
  "national_institution",
  "regional_institution",
  "local_public_institution",
  "cultural_institution",
]);

describe("municipality milestone research staging", () => {
  it("keeps the original research batch immutable and promotes it only through a manifest", () => {
    expect(milestoneResearch.runtimeIntegration).toBe(false);
    expect(milestoneResearch.editorialPolicy.readyForUi).toBe(false);
    expect(milestoneResearch.municipalities.map(({ istatCode, municipality }) => (
      [istatCode, municipality]
    ))).toEqual(EXPECTED_MUNICIPALITIES);

    for (const [istatCode] of EXPECTED_MUNICIPALITIES) {
      const runtimeProfile = municipalityProfiles.profiles.find((profile) => (
        profile.istatCode === istatCode
      ));
      expect(runtimeProfile?.milestones).toHaveLength(
        milestonePromotion.municipalityCounts[istatCode],
      );
    }
  });

  it("records only sourced, datable and uniquely keyed candidates", () => {
    const candidates = milestoneResearch.municipalities.flatMap((record) => record.candidates);
    const ids = candidates.map((candidate) => candidate.id);
    const runtimeIds = new Set(municipalityProfiles.profiles.flatMap((profile) => (
      profile.milestones.map((milestone) => milestone.id)
    )));

    expect(candidates).toHaveLength(14);
    expect(new Set(ids).size).toBe(ids.length);

    for (const municipality of milestoneResearch.municipalities) {
      expect(municipality.currentMilestoneCount).toBe(0);
      expect(municipality.decision).toBe("source_verified_it_fur_pending");
      expect(municipality.candidates.length).toBeGreaterThanOrEqual(2);
      expect(municipality.candidates.length).toBeLessThanOrEqual(3);

      for (const candidate of municipality.candidates) {
        expect(runtimeIds.has(candidate.id)).toBe(true);
        expect((candidate.year !== undefined) !== Boolean(candidate.century)).toBe(true);
        expect(candidate.label.it).toBeTruthy();
        expect(candidate.label.fur).toBeNull();
        expect(candidate.evidence).toBeTruthy();
        expect(ALLOWED_SOURCE_TYPES.has(candidate.source.type)).toBe(true);
        expect(candidate.source.label).toBeTruthy();
        expect(candidate.source.url).toMatch(/^https:\/\//);
      }
    }
  });

  it("documents discarded ambiguous claims instead of silently using them", () => {
    expect(milestoneResearch.excludedClaims).toHaveLength(2);
    milestoneResearch.excludedClaims.forEach((claim) => {
      expect(claim.municipality).toBeTruthy();
      expect(claim.claim).toBeTruthy();
      expect(claim.reason).toBeTruthy();
    });
  });

  it("reviews every staged candidate in FUR without promoting it implicitly", () => {
    const candidateIds = milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => candidate.id)
      .sort();
    const reviewIds = milestoneFurReview.records
      .map((record) => record.id)
      .sort();

    expect(milestoneFurReview).toMatchObject({
      sourceResearchBatchId: milestoneResearch.batchId,
      runtimeIntegration: false,
      summary: {
        totalRecords: 14,
        approved: 14,
        pendingHumanReview: 0,
      },
    });
    expect(reviewIds).toEqual(candidateIds);
    expect(new Set(reviewIds).size).toBe(reviewIds.length);

    for (const record of milestoneFurReview.records) {
      expect(record.status).toBe("approved");
      expect(record.labelFur).toBeTruthy();
      expect(record.notes).toBeTruthy();
    }
  });

  it("promotes exactly the sourced and linguistically reviewed records", () => {
    const candidates = milestoneResearch.municipalities.flatMap((record) => (
      record.candidates.map((candidate) => ({
        ...candidate,
        istatCode: record.istatCode,
      }))
    ));
    const reviews = new Map(milestoneFurReview.records.map((record) => [record.id, record]));
    const promotedIds = [...milestonePromotion.recordIds].sort();

    expect(milestonePromotion).toMatchObject({
      researchBatchId: milestoneResearch.batchId,
      furReviewBatchId: milestoneFurReview.batchId,
      totalRecords: 14,
    });
    expect(promotedIds).toEqual(candidates.map(({ id }) => id).sort());
    expect(new Set(promotedIds).size).toBe(promotedIds.length);

    for (const candidate of candidates) {
      const runtimeProfile = municipalityProfiles.profiles.find((profile) => (
        profile.istatCode === candidate.istatCode
      ));
      const runtimeMilestone = runtimeProfile?.milestones.find((milestone) => (
        milestone.id === candidate.id
      ));
      const review = reviews.get(candidate.id);

      expect(runtimeMilestone).toMatchObject({
        id: candidate.id,
        label: {
          it: candidate.label.it,
          fur: review.labelFur,
        },
        source: candidate.source,
      });
      expect(runtimeMilestone.year ?? runtimeMilestone.century).toBe(
        candidate.year ?? candidate.century,
      );
    }
  });
});
