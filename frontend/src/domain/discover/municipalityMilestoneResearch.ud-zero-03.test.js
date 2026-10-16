import { describe, expect, it } from "vitest";

import milestoneFurReview from "../../data/discover/municipalityMilestoneFurReview.ud-zero-03.json";
import milestonePromotion from "../../data/discover/municipalityMilestonePromotion.ud-zero-03.json";
import milestoneResearch from "../../data/discover/municipalityMilestoneResearch.ud-zero-03.json";
import ud09Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";

const EXPECTED_MUNICIPALITIES = [
  ["030045", "Grimacco"],
  ["030046", "Latisana"],
  ["030051", "Lusevera"],
  ["030052", "Magnano in Riviera"],
  ["030055", "Manzano"],
  ["030058", "Mereto di Tomba"],
  ["030061", "Montenars"],
  ["030063", "Moruzzo"],
  ["030064", "Muzzana del Turgnano"],
];

const ALLOWED_SOURCE_TYPES = new Set([
  "official_municipality",
  "national_institution",
  "regional_institution",
  "cultural_institution",
]);

describe("municipality milestone UD third research staging", () => {
  it("keeps research immutable and connects promotion to the nine intended profiles", () => {
    expect(milestoneResearch).toMatchObject({
      runtimeIntegration: false,
      editorialPolicy: {
        noForcedMilestoneCount: true,
        readyForUi: false,
      },
    });
    expect(milestoneResearch.municipalities.map(({ istatCode, municipality }) => (
      [istatCode, municipality]
    ))).toEqual(EXPECTED_MUNICIPALITIES);

    const expectedCounts = Object.fromEntries(milestoneResearch.municipalities.map((record) => (
      [record.istatCode, record.candidates.length]
    )));
    expect(milestonePromotion.municipalityCounts).toEqual(expectedCounts);
    expect(Object.values(expectedCounts).reduce((total, count) => total + count, 0)).toBe(
      milestonePromotion.totalRecords,
    );

    for (const [istatCode] of EXPECTED_MUNICIPALITIES) {
      const researchRecord = milestoneResearch.municipalities.find((record) => (
        record.istatCode === istatCode
      ));
      const runtimeProfile = municipalityProfiles.profiles.find((profile) => (
        profile.istatCode === istatCode
      ));
      expect(runtimeProfile?.milestones.filter(({ id }) => !ud09Promotion.recordIds.includes(id)).map(({ id }) => id)).toEqual(
        researchRecord.candidates.map(({ id }) => id),
      );
    }
  });

  it("records twenty-six sourced, datable and uniquely keyed candidates without forcing Magnano", () => {
    const candidates = milestoneResearch.municipalities.flatMap((record) => record.candidates);
    const ids = candidates.map((candidate) => candidate.id);
    const labels = candidates.map((candidate) => candidate.label.it);

    expect(candidates).toHaveLength(26);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(labels).size).toBe(labels.length);

    for (const municipality of milestoneResearch.municipalities) {
      expect(municipality.currentMilestoneCount).toBe(0);
      expect(municipality.decision).toBe("source_verified_it_fur_pending");
      expect(municipality.candidates).toHaveLength(
        municipality.istatCode === "030052" ? 2 : 3,
      );

      for (const candidate of municipality.candidates) {
        const hasValidYear = Number.isInteger(candidate.year);
        const hasValidCentury = typeof candidate.century === "string"
          && candidate.century.trim().length > 0;
        expect(hasValidYear !== hasValidCentury).toBe(true);
        expect(candidate.label.it).toBeTruthy();
        expect(candidate.label.fur).toBeNull();
        expect(candidate.evidence).toBeTruthy();

        const sources = [candidate.source, ...(candidate.supportingSources ?? [])];
        expect(new Set(sources.map(({ url }) => url)).size).toBe(sources.length);
        for (const source of sources) {
          expect(ALLOWED_SOURCE_TYPES.has(source.type)).toBe(true);
          expect(source.label).toBeTruthy();
          expect(source.url).toMatch(/^https:\/\//);
        }
      }
    }

    const magnano = milestoneResearch.municipalities.find(({ istatCode }) => (
      istatCode === "030052"
    ));
    expect(magnano).toMatchObject({
      candidateCountDecision: "only_two_strong_candidates_no_forcing",
    });
  });

  it("documents duplicates and conflicting dates instead of silently promoting them", () => {
    expect(milestoneResearch.excludedClaims).toHaveLength(24);
    expect(milestoneResearch.sourceConflicts).toHaveLength(5);
    expect(new Set(milestoneResearch.excludedClaims.map((claim) => (
      `${claim.municipality}\u0000${claim.claim}`
    ))).size).toBe(milestoneResearch.excludedClaims.length);
    milestoneResearch.excludedClaims.forEach((claim) => {
      expect(claim.municipality).toBeTruthy();
      expect(claim.claim).toBeTruthy();
      expect(claim.reason).toBeTruthy();
    });
    expect(milestoneResearch.duplicateAudit).toMatchObject({
      status: "passed_with_thematic_overlap",
      exactDuplicates: 0,
      excludedExactDuplicates: 5,
      countingRule: "unique_facts_already_present_in_other_rubrics",
    });
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Latisana",
      field: "firstPortMention",
      selectedValue: "esclusione della tappa portuale",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Latisana e Lignano Sabbiadoro",
      field: "lignanoMunicipalAutonomyYear",
      selectedValue: "esclusione e verifica separata",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Magnano in Riviera",
      field: "pramperoCastleFirstDate",
      discardedValue: "1025, 1025-1121, 1225 oppure 1265",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Mereto di Tomba",
      field: "tumbareExcavationDate",
      selectedValue: 2008,
      discardedValue: "intervallo 2006-2008",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Muzzana del Turgnano",
      field: "mucianoDiplomaAct",
      selectedValue: "attestazione di Villa Muciano nel 824",
    }));

    const promotedText = milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => `${candidate.id} ${candidate.label.it}`)
      .join(" ")
      .toLowerCase();
    expect(promotedText).not.toContain("terremoto");
    expect(promotedText).not.toContain("doc friuli latisana");
    expect(promotedText).not.toContain("caterina percoto");
    expect(promotedText).not.toContain("placerean");
    expect(promotedText).not.toContain("lignano");
  });

  it("keeps the high-risk claims narrowly phrased and independently supported", () => {
    const candidates = new Map(milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => [candidate.id, candidate]));

    expect(candidates.get("latisana-citazione-1072")?.evidence).toContain("Marquardo");
    expect(candidates.get("latisana-citazione-1072")?.label.it.toLowerCase()).not.toContain(
      "porto",
    );
    expect(candidates.has("magnano-castello-prampero-1025")).toBe(false);
    expect(candidates.get("magnano-afro-prampero-1961")?.evidence).toContain("1961-1976");
    expect(candidates.get("mereto-scavo-tumbare-2008")?.supportingSources).toHaveLength(2);
    expect(candidates.get("mereto-scavo-tumbare-2008")?.evidence).toContain(
      "terza campagna del 2008",
    );
    expect(candidates.has("montenars-terremoto-1976")).toBe(false);
    expect(candidates.has("montenars-aggregazione-artegna-1928")).toBe(true);
    expect(candidates.has("moruzzo-donazione-762")).toBe(false);
    expect(candidates.has("moruzzo-diploma-983")).toBe(false);
    expect(candidates.get("muzzana-villa-muciano-824")?.supportingSources).toHaveLength(1);
    expect(candidates.get("muzzana-villa-muciano-824")?.label.it).toBe(
      "Villa Muciano è attestata in un diploma di Ludovico il Pio",
    );
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
        totalRecords: 26,
        approved: 26,
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
      totalRecords: 26,
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
      expect(Number.isInteger(runtimeMilestone.year) !== (
        typeof runtimeMilestone.century === "string"
        && runtimeMilestone.century.trim().length > 0
      )).toBe(true);
      expect(runtimeMilestone.supportingSources).toEqual(candidate.supportingSources);
    }
  });
});
