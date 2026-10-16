import { describe, expect, it } from "vitest";

import milestoneFurReview from "../../data/discover/municipalityMilestoneFurReview.go-zero-01.json";
import milestonePromotion from "../../data/discover/municipalityMilestonePromotion.go-zero-01.json";
import milestoneResearch from "../../data/discover/municipalityMilestoneResearch.go-zero-01.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";

const EXPECTED_MUNICIPALITIES = [
  ["031001", "Capriva del Friuli"],
  ["031002", "Cormons"],
  ["031004", "Dolegna del Collio"],
  ["031005", "Farra d'Isonzo"],
  ["031006", "Fogliano Redipuglia"],
  ["031013", "Moraro"],
  ["031018", "San Canzian d'Isonzo"],
  ["031021", "San Pier d'Isonzo"],
  ["031025", "Villesse"],
];

const ALLOWED_SOURCE_TYPES = new Set([
  "official_municipality",
  "national_institution",
  "regional_institution",
  "local_public_institution",
  "cultural_institution",
]);

describe("municipality milestone GO research staging", () => {
  it("keeps research immutable and connects promotion to the nine intended profiles", () => {
    expect(milestoneResearch).toMatchObject({
      runtimeIntegration: false,
      editorialPolicy: { readyForUi: false },
    });
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

  it("records twenty-seven sourced, datable and uniquely keyed candidates", () => {
    const candidates = milestoneResearch.municipalities.flatMap((record) => record.candidates);
    const ids = candidates.map((candidate) => candidate.id);
    const labels = candidates.map((candidate) => candidate.label.it);

    expect(candidates).toHaveLength(27);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(labels).size).toBe(labels.length);

    for (const municipality of milestoneResearch.municipalities) {
      expect(municipality.currentMilestoneCount).toBe(0);
      expect(municipality.decision).toBe("source_verified_it_fur_pending");
      expect(municipality.candidates).toHaveLength(3);

      for (const candidate of municipality.candidates) {
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

  it("documents duplicates, ambiguities and the Villesse date conflict", () => {
    expect(milestoneResearch.excludedClaims.length).toBeGreaterThanOrEqual(9);
    milestoneResearch.excludedClaims.forEach((claim) => {
      expect(claim.municipality).toBeTruthy();
      expect(claim.claim).toBeTruthy();
      expect(claim.reason).toBeTruthy();
    });
    expect(milestoneResearch.duplicateAudit).toMatchObject({
      status: "passed_with_thematic_overlap",
      exactDuplicates: 0,
      excludedExactDuplicates: 4,
    });
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Villesse",
      field: "aggregationYear",
      selectedValue: 1928,
      discardedValue: 1929,
    }));

    const promotedText = milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => `${candidate.id} ${candidate.label.it}`)
      .join(" ")
      .toLowerCase();
    expect(promotedText).not.toContain("armistizio");
    expect(promotedText).not.toContain("zorutti");
    expect(promotedText).not.toContain("sacrario");
    expect(promotedText).not.toContain("invitti");
  });

  it("keeps the three corrected high-risk claims narrowly phrased", () => {
    const candidates = new Map(milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => [candidate.id, candidate]));

    expect(candidates.get("cormons-sede-patriarcato-628")?.evidence).toContain("628 al 737");
    expect(candidates.get("moraro-autonomia-1955")?.label.it).not.toContain("definitivamente");
    expect(candidates.get("san-canzian-scavi-archeologici-1960")).toMatchObject({
      label: { it: expect.stringContaining("Università di Trieste") },
      source: { type: "regional_institution" },
    });
    expect(candidates.get("san-canzian-scavi-archeologici-1960")?.evidence).toContain("1950");
  });

  it("reviews every staged candidate in FUR without promoting it implicitly", () => {
    const candidateIds = milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => candidate.id)
      .sort();
    const reviewIds = milestoneFurReview.records.map((record) => record.id).sort();

    expect(reviewIds).toEqual(candidateIds);
    expect(new Set(reviewIds).size).toBe(reviewIds.length);
    expect(milestoneFurReview).toMatchObject({
      sourceResearchBatchId: milestoneResearch.batchId,
      runtimeIntegration: false,
      summary: {
        totalRecords: 27,
        approved: 27,
        pendingHumanReview: 0,
      },
    });

    for (const record of milestoneFurReview.records) {
      expect(record.status).toBe("approved");
      expect(record.labelFur).toBeTruthy();
      expect(record.labelFur).not.toMatch(/\.$/);
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
      totalRecords: 27,
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
