import { describe, expect, it } from "vitest";

import milestoneFurReview from "../../data/discover/municipalityMilestoneFurReview.ud-zero-02.json";
import milestonePromotion from "../../data/discover/municipalityMilestonePromotion.ud-zero-02.json";
import milestoneResearch from "../../data/discover/municipalityMilestoneResearch.ud-zero-02.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";

const EXPECTED_MUNICIPALITIES = [
  ["030029", "Comeglians"],
  ["030034", "Drenchia"],
  ["030035", "Enemonzo"],
  ["030036", "Faedis"],
  ["030037", "Fagagna"],
  ["030039", "Flaibano"],
  ["030040", "Forni Avoltri"],
  ["030041", "Forni di Sopra"],
  ["030042", "Forni di Sotto"],
];

const ALLOWED_SOURCE_TYPES = new Set([
  "official_municipality",
  "national_institution",
  "regional_institution",
  "local_public_institution",
  "cultural_institution",
  "international_institution",
]);

describe("municipality milestone UD second research staging", () => {
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

  it("documents duplicates, ambiguous dates and conflicts without promoting them", () => {
    expect(milestoneResearch.excludedClaims.length).toBeGreaterThanOrEqual(26);
    milestoneResearch.excludedClaims.forEach((claim) => {
      expect(claim.municipality).toBeTruthy();
      expect(claim.claim).toBeTruthy();
      expect(claim.reason).toBeTruthy();
    });
    expect(milestoneResearch.duplicateAudit).toMatchObject({
      status: "passed_with_thematic_overlap",
      exactDuplicates: 0,
      excludedExactDuplicates: 2,
      countingRule: "unique_facts_already_present_in_other_rubrics",
    });
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Drenchia",
      selectedValue: "Riccardo Giusto; luogo omesso dall'etichetta",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Flaibano",
      selectedValue: 1927,
      discardedValue: "16 settembre 1927",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Forni di Sopra e Forni di Sotto",
      selectedValue: 1326,
      discardedValue: "secolo XII",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      field: "furnus778ModernLocation",
      selectedValue: "esclusione della tappa",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Forni di Sotto",
      field: "1944FireAttribution",
      selectedValue: "incendio di guerra",
    }));

    const promotedText = milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => `${candidate.id} ${candidate.label.it}`)
      .join(" ")
      .toLowerCase();
    expect(promotedText).not.toContain("terremoto");
    expect(promotedText).not.toContain("leonardo zanier");
    expect(promotedText).not.toContain("furnus");
    expect(promotedText).not.toContain("1025");
    expect(promotedText).not.toContain("1027");
  });

  it("keeps the high-risk claims narrowly phrased", () => {
    const candidates = new Map(milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => [candidate.id, candidate]));

    expect(candidates.get("comeglians-pieve-san-giorgio-1305")?.evidence).toContain(
      "12 maggio 1305",
    );
    expect(candidates.get("drenchia-riccardo-giusto-1915")?.evidence).toContain(
      "24 maggio 1915",
    );
    expect(candidates.get("drenchia-riccardo-giusto-1915")?.label.it).not.toContain(
      "Solarie",
    );
    expect(candidates.get("enemonzo-prima-festa-formaggio-1974")?.evidence).toContain(
      "autunno 1974",
    );
    expect(candidates.get("faedis-refosco-sottozona-doc-2011")?.source.label).toContain(
      "Gazzetta Ufficiale",
    );
    expect(candidates.get("fagagna-cjase-cocel-museo-1994")?.evidence).toContain(
      "già nata alla fine degli anni Ottanta",
    );
    expect(candidates.get("flaibano-denominazione-1927")?.evidence).toContain(
      "senza indicare un giorno",
    );
    expect(candidates.get("forni-avoltri-forno-fucina-1328")?.evidence).toContain(
      "6 giugno 1328",
    );
    expect(candidates.get("forni-sopra-unesco-2009")?.source.type).toBe(
      "international_institution",
    );
    expect(candidates.get("forni-sopra-unesco-2009")?.supportingSources).toContainEqual(
      expect.objectContaining({
        type: "regional_institution",
        url: "https://decreti.regione.fvg.it/Storage/2024_90/ALLEGATO2%20AL%20DPREG%20090-2024.PDF",
      }),
    );
    expect(candidates.get("forni-sotto-incendio-1944")?.label.it).toContain(
      "incendio di guerra",
    );
    expect(candidates.get("forni-sotto-incendio-1944")?.label.it.toLowerCase()).not.toMatch(
      /tedesc|naz/,
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
      expect(runtimeMilestone.supportingSources).toEqual(candidate.supportingSources);
    }
  });
});
