import { describe, expect, it } from "vitest";

import milestoneFurReview from "../../data/discover/municipalityMilestoneFurReview.ud-zero-05.json";
import milestonePromotion from "../../data/discover/municipalityMilestonePromotion.ud-zero-05.json";
import milestoneResearch from "../../data/discover/municipalityMilestoneResearch.ud-zero-05.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";

const EXPECTED_MUNICIPALITIES = [
  ["030084", "Preone"],
  ["030086", "Pulfero"],
  ["030087", "Ragogna"],
  ["030088", "Ravascletto"],
  ["030089", "Raveo"],
  ["030090", "Reana del Rojale"],
  ["030093", "Resiutta"],
  ["030098", "Ruda"],
  ["030107", "Sauris"],
];

const ALLOWED_SOURCE_TYPES = new Set([
  "official_municipality",
  "national_institution",
  "regional_institution",
  "cultural_institution",
]);

const getCandidates = () => milestoneResearch.municipalities.flatMap((record) => (
  record.candidates.map((candidate) => ({ ...candidate, istatCode: record.istatCode }))
));

describe("municipality milestone UD fifth research staging", () => {
  it("keeps the audit immutable and connects promotion to the intended profiles", () => {
    expect(milestoneResearch).toMatchObject({
      runtimeIntegration: false,
      editorialPolicy: {
        ambiguousDatesExcluded: true,
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
    expect(Object.values(expectedCounts).reduce((total, count) => total + count, 0)).toBe(27);
    expect(milestonePromotion.totalRecords).toBe(27);
  });

  it("records twenty-seven sourced, datable and uniquely keyed candidates", () => {
    const candidates = getCandidates();
    const ids = candidates.map(({ id }) => id);
    const labels = candidates.map(({ label }) => label.it);

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

  it("records conflicts and duplicates instead of choosing silently", () => {
    expect(milestoneResearch.excludedClaims).toHaveLength(12);
    expect(milestoneResearch.sourceConflicts).toHaveLength(5);
    expect(milestoneResearch.duplicateAudit).toMatchObject({
      status: "passed_with_thematic_overlap",
      exactDuplicates: 0,
      excludedExactDuplicates: 2,
      countingRule: "unique_facts_already_present_in_other_rubrics",
    });
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Preone",
      field: "municipalitySuppressionYear",
      selectedValue: "esclusione dell'intero passaggio amministrativo",
      discardedValue: "1920 oppure 1928",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Reana del Rojale",
      field: "municipalityNameChangeYear",
      selectedValue: "esclusione della tappa",
      discardedValue: "1866 oppure 18 agosto 1867",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Sauris",
      field: "damAndLakeYear",
      selectedValue: "1948, creazione del Lago di Sauris",
    }));

    const promotedText = getCandidates()
      .map((candidate) => `${candidate.id} ${candidate.label.it}`)
      .join(" ")
      .toLowerCase();
    expect(promotedText).not.toContain("terremoto");
    expect(promotedText).not.toContain("campionati mondiali juniores");
    expect(promotedText).not.toContain("castello di torre");
    expect(promotedText).not.toContain("1928");
    expect(promotedText).not.toContain("1866");
    expect(promotedText).not.toContain("1867");
  });

  it("keeps the highest-risk labels inside the evidence boundary", () => {
    const candidates = new Map(getCandidates().map((candidate) => [candidate.id, candidate]));

    expect(candidates.get("pulfero-antro-opera-1477")?.label.it).toContain("opera");
    expect(candidates.get("pulfero-antro-opera-1477")?.label.it).not.toMatch(/nasce|sorge/i);
    expect(candidates.get("ravascletto-funivia-zoncolan-1975")?.label.it).toContain("stazione");
    expect(candidates.get("raveo-prime-menzioni-xiv")).toMatchObject({ century: "XIV" });
    expect(candidates.get("reana-decreto-comune-1807")?.label.it).toContain("citata");
    expect(candidates.get("reana-decreto-comune-1807")?.label.it).not.toContain("Nasce");
    expect(candidates.get("ruda-amideria-1865")?.supportingSources).toHaveLength(1);
    expect(candidates.get("sauris-santosvaldo-1300-1328")).toMatchObject({
      century: "1300-1328",
    });
    expect(candidates.get("sauris-lago-1948")?.label.it).toContain("Lago");
    expect(candidates.get("sauris-lago-1948")?.label.it).not.toMatch(/termina|completa/i);
  });

  it("reviews every staged candidate in FUR without changing the research file", () => {
    const candidateIds = getCandidates().map(({ id }) => id).sort();
    const reviewIds = milestoneFurReview.records.map(({ id }) => id).sort();

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

  it("promotes exactly the sourced and reviewed records into the runtime catalog", () => {
    const candidates = getCandidates();
    const reviews = new Map(milestoneFurReview.records.map((record) => [record.id, record]));

    expect(milestonePromotion).toMatchObject({
      researchBatchId: milestoneResearch.batchId,
      furReviewBatchId: milestoneFurReview.batchId,
      totalRecords: 27,
    });
    expect([...milestonePromotion.recordIds].sort()).toEqual(
      candidates.map(({ id }) => id).sort(),
    );

    for (const candidate of candidates) {
      const runtimeProfile = municipalityProfiles.profiles.find(({ istatCode }) => (
        istatCode === candidate.istatCode
      ));
      const runtimeMilestone = runtimeProfile?.milestones.find(({ id }) => id === candidate.id);
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
