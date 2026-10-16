import { describe, expect, it } from "vitest";

import milestoneFurReview from "../../data/discover/municipalityMilestoneFurReview.ud-zero-01.json";
import milestonePromotion from "../../data/discover/municipalityMilestonePromotion.ud-zero-01.json";
import milestoneResearch from "../../data/discover/municipalityMilestoneResearch.ud-zero-01.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";

const EXPECTED_MUNICIPALITIES = [
  ["030002", "Amaro"],
  ["030005", "Arta Terme"],
  ["030009", "Basiliano"],
  ["030012", "Bordano"],
  ["030014", "Buttrio"],
  ["030018", "Carlino"],
  ["030020", "Castions di Strada"],
  ["030022", "Cercivento"],
  ["030023", "Cervignano del Friuli"],
];

const ALLOWED_SOURCE_TYPES = new Set([
  "official_municipality",
  "national_institution",
  "regional_institution",
  "local_public_institution",
  "cultural_institution",
]);

describe("municipality milestone UD first research staging", () => {
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

    for (const [istatCode] of EXPECTED_MUNICIPALITIES) {
      const runtimeProfile = municipalityProfiles.profiles.find((profile) => (
        profile.istatCode === istatCode
      ));
      expect(runtimeProfile?.milestones).toHaveLength(
        milestonePromotion.municipalityCounts[istatCode],
      );
    }
  });

  it("records twenty-six sourced, datable and uniquely keyed candidates without forcing Amaro", () => {
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
        municipality.istatCode === "030002" ? 2 : 3,
      );

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

    expect(milestoneResearch.municipalities.find(({ istatCode }) => (
      istatCode === "030002"
    ))).toMatchObject({
      candidateCountDecision: "only_two_strong_candidates_no_forcing",
    });
  });

  it("documents duplicates, ambiguous dates and source distinctions", () => {
    expect(milestoneResearch.excludedClaims.length).toBeGreaterThanOrEqual(17);
    milestoneResearch.excludedClaims.forEach((claim) => {
      expect(claim.municipality).toBeTruthy();
      expect(claim.claim).toBeTruthy();
      expect(claim.reason).toBeTruthy();
    });
    expect(milestoneResearch.duplicateAudit).toMatchObject({
      status: "passed_with_thematic_overlap",
      exactDuplicates: 0,
      excludedExactDuplicates: 4,
      countingRule: "unique_facts_already_present_in_other_rubrics",
    });
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Amaro",
      selectedValue: 1807,
      discardedValue: 1806,
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Cercivento",
      selectedValue: 1806,
      discardedValue: 1805,
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Castions di Strada",
      selectedValue: 1031,
      discardedValue: 967,
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Cervignano del Friuli",
      selectedValue: 1036,
      discardedValue: 912,
    }));

    const promotedText = milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => `${candidate.id} ${candidate.label.it}`)
      .join(" ")
      .toLowerCase();
    expect(promotedText).not.toContain("terremoto");
    expect(promotedText).not.toContain("fucilazione");
    expect(promotedText).not.toContain("gervasutti");
    expect(promotedText).not.toContain("dardi");
    expect(promotedText).not.toContain("morassi");
  });

  it("keeps the high-risk claims narrowly phrased", () => {
    const candidates = new Map(milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => [candidate.id, candidate]));

    expect(candidates.get("amaro-comune-napoleonico-1807")?.evidence).toContain("22 dicembre 1807");
    expect(candidates.get("arta-primo-stabilimento-termale-1870")?.source.label).toContain(
      "Università di Udine",
    );
    expect(candidates.get("basiliano-prima-menzione-1149")?.evidence).toContain("nome personale");
    expect(candidates.get("buttrio-placito-1015")?.label.it).not.toContain("Prima attestazione");
    expect(candidates.get("buttrio-placito-1015")?.label.it).toContain("diritto al placito");
    expect(candidates.get("buttrio-fiera-vini-1933")?.source.url).toBe(
      "https://patrimonioculturale.regione.fvg.it/wp-content/uploads/2017/06/BUT_Brochure-museo-A5_02.pdf",
    );
    expect(candidates.get("carlino-chiamana-scoperta-1970")?.evidence).toContain("1971");
    expect(candidates.get("castions-capitolo-aquileia-1031")?.evidence).toContain("1046");
    expect(candidates.has("castions-chiesa-aquileiese-967")).toBe(false);
    expect(candidates.has("castions-san-martino-1535")).toBe(false);
    expect(candidates.get("cercivento-comune-1806")?.label.it).not.toContain("entra nel Regno");
    expect(candidates.get("cercivento-comune-1806")?.evidence).toContain("avvenuto nel 1805");
    expect(candidates.get("cercivento-comune-1806")?.source.url).not.toContain("RicLin=en");
    expect(candidates.get("cervignano-castrum-cirviganum-1036")?.evidence).toContain("912");
    expect(candidates.get("cervignano-castrum-cirviganum-1036")?.label.it).toContain("originale");
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
    }
  });
});
