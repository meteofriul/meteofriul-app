import { describe, expect, it } from "vitest";

import milestoneFurReview from "../../data/discover/municipalityMilestoneFurReview.ud-zero-04.json";
import milestonePromotion from "../../data/discover/municipalityMilestonePromotion.ud-zero-04.json";
import milestoneResearch from "../../data/discover/municipalityMilestoneResearch.ud-zero-04.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";

const EXPECTED_MUNICIPALITIES = [
  ["030065", "Nimis"],
  ["030068", "Pagnacco"],
  ["030069", "Palazzolo dello Stella"],
  ["030071", "Paluzza"],
  ["030073", "Paularo"],
  ["030075", "Pocenia"],
  ["030078", "Povoletto"],
  ["030081", "Prato Carnico"],
  ["030083", "Premariacco"],
];

const ALLOWED_SOURCE_TYPES = new Set([
  "official_municipality",
  "national_institution",
  "regional_institution",
  "cultural_institution",
  "local_public_institution",
]);

describe("municipality milestone UD fourth research staging", () => {
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
      expect(runtimeProfile?.milestones.map(({ id }) => id)).toEqual(
        researchRecord.candidates.map(({ id }) => id),
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
  });

  it("documents duplicates and conflicting dates instead of silently promoting them", () => {
    expect(milestoneResearch.excludedClaims).toHaveLength(27);
    expect(milestoneResearch.sourceConflicts).toHaveLength(9);
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
      excludedExactDuplicates: 4,
      countingRule: "unique_facts_already_present_in_other_rubrics",
    });
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Nimis",
      field: "cergneuDonation1170",
      selectedValue: "esistenza documentata del castello dal 1170",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Pagnacco",
      field: "firstToponymMention",
      selectedValue: "documento patriarcale del 1262 senza qualificarlo come prima attestazione",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Palazzolo dello Stella",
      field: "firstToponymMention",
      selectedValue: 762,
      discardedValue: 1349,
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Pocenia",
      field: "stellaTorsaParkEstablishmentYear",
      selectedValue: 2000,
      discardedValue: "1996 oppure 2004",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Povoletto",
      field: "mottaCastleFirstMention",
      discardedValue: "921 oppure 922",
    }));

    const promotedText = milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => `${candidate.id} ${candidate.label.it}`)
      .join(" ")
      .toLowerCase();
    expect(promotedText).not.toContain("terremoto");
    expect(promotedText).not.toContain("gae aulenti");
    expect(promotedText).not.toContain("flos duellatorum");
    expect(promotedText).not.toContain("palette");
  });

  it("keeps high-risk claims narrow and uses the exact regional park act", () => {
    const candidates = new Map(milestoneResearch.municipalities
      .flatMap((record) => record.candidates)
      .map((candidate) => [candidate.id, candidate]));

    expect(candidates.get("nimis-castello-cergneu-1170")?.label.it).not.toMatch(
      /Voldarico|Ulrico|donazione/i,
    );
    expect(candidates.get("pagnacco-paniaco-1262")?.label.it.toLowerCase()).not.toContain(
      "prima",
    );
    expect(candidates.get("pagnacco-fontanabona-lascito-1969")?.summaryOverlap).toBe(
      "thematic_distinct",
    );
    expect(candidates.get("pocenia-motta-incastellata-xiii")).toMatchObject({
      century: "XIII",
    });
    expect(candidates.get("pocenia-motta-incastellata-xiii")?.label.it).not.toContain(
      "castello",
    );
    expect(candidates.get("pocenia-parco-stella-torsa-2000")?.evidence).toContain(
      "014/Pres",
    );
    expect(candidates.get("povoletto-scavi-motta-1997")?.evidence).toContain("1996");
    expect(candidates.get("premariacco-rocca-bernarda-1567")?.label.it).not.toContain(
      "Giovanni da Udine",
    );

    const pagnacco = municipalityProfiles.profiles.find(({ istatCode }) => istatCode === "030068");
    const palazzolo = municipalityProfiles.profiles.find(({ istatCode }) => istatCode === "030069");
    expect(pagnacco?.summary.fur).toContain("Fontanebuine");
    expect(pagnacco?.summary.fur).not.toContain("Fontanabona");
    expect(palazzolo?.title.fur).toBe("Palaçûl, sul percors de Vie Anie");
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
      expect(Number.isInteger(runtimeMilestone.year) !== (
        typeof runtimeMilestone.century === "string"
        && runtimeMilestone.century.trim().length > 0
      )).toBe(true);
      expect(runtimeMilestone.supportingSources).toEqual(candidate.supportingSources);
    }
  });
});
