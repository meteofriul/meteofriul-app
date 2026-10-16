import { describe, expect, it } from "vitest";

import milestoneFurReview from "../../data/discover/municipalityMilestoneFurReview.ud-zero-06.json";
import milestonePromotion from "../../data/discover/municipalityMilestonePromotion.ud-zero-06.json";
import milestoneResearch from "../../data/discover/municipalityMilestoneResearch.ud-zero-06.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";

const EXPECTED_MUNICIPALITIES = [
  ["030111", "Stregna"],
  ["030112", "Sutrio"],
  ["030117", "Tarvisio"],
  ["030122", "Torreano"],
  ["030132", "Verzegnis"],
  ["030137", "Forgaria nel Friuli"],
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

describe("municipality milestone UD final research staging", () => {
  it("keeps the audit immutable and connects promotion to the final empty profiles", () => {
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
    expect(Object.values(expectedCounts).reduce((total, count) => total + count, 0)).toBe(18);
    expect(milestonePromotion.totalRecords).toBe(18);
  });

  it("records eighteen sourced, datable and uniquely keyed candidates", () => {
    const candidates = getCandidates();
    const ids = candidates.map(({ id }) => id);
    const labels = candidates.map(({ label }) => label.it);

    expect(candidates).toHaveLength(18);
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

  it("records conflicts and published duplicates instead of choosing silently", () => {
    expect(milestoneResearch.excludedClaims).toHaveLength(10);
    expect(milestoneResearch.sourceConflicts).toHaveLength(4);
    expect(milestoneResearch.duplicateAudit).toMatchObject({
      status: "passed_with_thematic_overlap",
      exactDuplicates: 0,
      excludedExactDuplicates: 4,
      countingRule: "unique_facts_already_present_in_other_rubrics",
    });
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Tarvisio",
      field: "annexationToItalyYear",
      selectedValue: "esclusione della tappa",
      discardedValue: "1918 oppure 1919",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Tarvisio",
      field: "railwayOpeningYear",
      discardedValue: "1872 oppure 1879",
    }));
    expect(milestoneResearch.sourceConflicts).toContainEqual(expect.objectContaining({
      municipality: "Verzegnis",
      field: "possessionEventsYear",
      discardedValue: "1878 oppure 1879",
    }));

    const promotedText = getCandidates()
      .map((candidate) => `${candidate.id} ${candidate.label.it}`)
      .join(" ")
      .toLowerCase();
    expect(promotedText).not.toContain("1797");
    expect(promotedText).not.toContain("1809");
    expect(promotedText).not.toContain("mondiali juniores");
    expect(promotedText).not.toContain("anton kasutnik");
    expect(promotedText).not.toContain("terremoto");
    expect(promotedText).not.toContain("indemoniate");
  });

  it("keeps the highest-risk labels inside the evidence boundary", () => {
    const candidates = new Map(getCandidates().map((candidate) => [candidate.id, candidate]));

    expect(candidates.get("sutrio-decreto-comune-1807")?.label.it).toContain("inserito");
    expect(candidates.get("sutrio-decreto-comune-1807")?.label.it).not.toContain("Nasce");
    expect(candidates.get("tarvisio-lussari-1924")?.label.it).toContain("ricostruito");
    expect(candidates.get("torreano-scavi-landri-1921")?.summaryOverlap).toBe(
      "dated_research_detail",
    );
    expect(candidates.get("verzegnis-stato-cosacco-1944-1945")).toMatchObject({
      century: "1944-1945",
    });
    expect(candidates.get("verzegnis-crist-val-2002")?.label.it).toContain("documenta");
    expect(candidates.get("verzegnis-crist-val-2002")?.label.it).not.toMatch(
      /mesolit|preistor/i,
    );
    expect(candidates.get("forgaria-progetto-grifone-1987")?.label.it).toContain("progetto");
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
        totalRecords: 18,
        approved: 18,
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
      totalRecords: 18,
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

  it("leaves no reviewed municipality profile without a historical timeline", () => {
    const emptyProfiles = municipalityProfiles.profiles.filter((profile) => (
      !profile.milestones?.length
    ));

    expect(emptyProfiles).toEqual([]);
  });
});
