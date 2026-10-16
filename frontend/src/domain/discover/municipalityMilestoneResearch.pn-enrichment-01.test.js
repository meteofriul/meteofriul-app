import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import milestoneFurReview from "../../data/discover/municipalityMilestoneFurReview.pn-enrichment-01.json";
import milestonePromotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-01.json";
import milestoneResearch from "../../data/discover/municipalityMilestoneResearch.pn-enrichment-01.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_MUNICIPALITIES = [
  ["093001", "Andreis", ["andreis-1949"], 1],
  ["093014", "Cimolais", ["cimolais-1902"], 2],
  ["093037", "Sacile", ["sacile-796", "sacile-1420"], 1],
];

const EXPECTED_FACTS = [
  ["andreis-museo-1981", 1981, "093001"],
  ["cimolais-rifugio-pordenone-1930", 1930, "093014"],
  ["cimolais-stambecco-1985", 1985, "093014"],
  ["sacile-liberta-comunali-1190", 1190, "093037"],
];

const ALLOWED_SOURCE_TYPES = new Set([
  "official_municipality",
  "regional_institution",
  "cultural_institution",
]);

const candidates = milestoneResearch.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({
    ...candidate,
    istatCode: municipality.istatCode,
  }))
));

describe("municipality milestone PN enrichment research staging", () => {
  it("keeps the initial research snapshot separate from the promoted runtime copy", () => {
    expect(milestoneResearch).toMatchObject({
      schemaVersion: 1,
      batchId: "pn-enrichment-milestones-01",
      snapshotDate: "2026-08-31",
      runtimeIntegration: false,
      editorialPolicy: {
        sourceEvidenceRequired: true,
        ambiguousDatesExcluded: true,
        italianCopyStatus: "editorial_draft",
        friulianCopyStatus: "pending_human_review",
        readyForUi: false,
      },
    });
    expect(candidates.map(({ id, year, istatCode }) => [id, year, istatCode]))
      .toEqual(EXPECTED_FACTS);
    expect(new Set(candidates.map(({ id }) => id)).size).toBe(4);
    expect(new Set(candidates.map(({ label }) => label.it)).size).toBe(4);

    for (const candidate of candidates) {
      expect(Number.isInteger(candidate.year)).toBe(true);
      expect(candidate.century).toBeUndefined();
      expect(candidate.label.it.trim()).toBeTruthy();
      expect(candidate.label.fur).toBeNull();
      expect(candidate.evidence.trim()).toBeTruthy();
      expect(candidate.duplicateReview).toMatchObject({ exactDuplicate: false });
      expect(candidate.duplicateReview.note.trim()).toBeTruthy();
    }
  });

  it("enriches exactly three existing PN municipalities without forcing three milestones", () => {
    expect(milestoneResearch.municipalities.map((municipality) => [
      municipality.istatCode,
      municipality.municipality,
      municipality.currentMilestoneIds,
      municipality.candidates.length,
    ])).toEqual(EXPECTED_MUNICIPALITIES);

    for (const municipality of milestoneResearch.municipalities) {
      const profile = municipalityProfiles.profiles.find(({ istatCode }) => (
        istatCode === municipality.istatCode
      ));
      expect(profile).toMatchObject({
        municipality: municipality.municipality,
        province: "PN",
      });
      expect(municipality.province).toBe("PN");
      expect(municipality.decision).toBe("source_verified_it_fur_pending");
      const initialMilestones = profile.milestones.filter(({ id }) => (
        municipality.currentMilestoneIds.includes(id)
      ));
      expect(municipality.currentMilestoneCount).toBe(initialMilestones.length);
      expect(municipality.currentMilestoneIds).toEqual(
        initialMilestones.map(({ id }) => id),
      );
      expect(profile.milestones.length).toBe(
        municipality.currentMilestoneCount + municipality.candidates.length,
      );
      expect(profile.milestones.length).toBeLessThanOrEqual(3);
    }
  });

  it("retains explicit HTTPS evidence and independently attributable supporting sources", () => {
    for (const candidate of candidates) {
      const sources = [candidate.source, ...(candidate.supportingSources ?? [])];
      expect(new Set(sources.map(({ url }) => url)).size).toBe(sources.length);
      for (const source of sources) {
        expect(ALLOWED_SOURCE_TYPES.has(source.type)).toBe(true);
        expect(source.label.trim()).toBeTruthy();
        expect(new URL(source.url).protocol).toBe("https:");
        expect(source.checkedAt).toBe("2026-08-31");
      }
    }
  });

  it("distinguishes the refuge inauguration from planning dates and its municipal location", () => {
    const refuge = candidates.find(({ id }) => id === "cimolais-rifugio-pordenone-1930");
    expect(refuge).toMatchObject({
      year: 1930,
      documentedDate: "1930-05-25",
      istatCode: "093014",
    });
    expect(refuge.label.it).toMatch(/inaugurato.*Val Cimoliana/);
    expect(refuge.supportingSources).toHaveLength(2);
    expect(refuge.source.url).toBe("https://caipordenone.it/chi-siamo/storia/");
    expect(refuge.supportingSources.map(({ url }) => url)).toContain(
      "https://caipordenone.it/strutture/rifugio-pordenone/",
    );
    expect(milestoneResearch.excludedClaims).toEqual(expect.arrayContaining([
      expect.objectContaining({ municipality: "Cimolais", claim: expect.stringContaining("1928") }),
      expect.objectContaining({ municipality: "Cimolais", claim: expect.stringContaining("Comune di Pordenone") }),
      expect.objectContaining({ municipality: "Sacile", claim: expect.stringContaining("Stato indipendente") }),
    ]));
    expect(candidates.find(({ id }) => id === "cimolais-stambecco-1985").label.it)
      .toMatch(/Val Cimoliana.*reintrodotto.*stambecco/);
    expect(candidates.find(({ id }) => id === "sacile-liberta-comunali-1190").label.it)
      .toMatch(/privilegio di borghesia.*libertà comunali/);
    expect(candidates.find(({ id }) => id === "andreis-museo-1981").duplicateReview.relatedRecordIds)
      .toEqual(["institutional-archive-pettini-osso-andreis"]);
  });

  it("records delegated assisted approval without claiming independent human review", () => {
    expect(milestoneFurReview).toMatchObject({
      schemaVersion: 1,
      batchId: "pn-enrichment-milestones-01-fur-review",
      sourceResearchBatchId: milestoneResearch.batchId,
      reviewedAt: "2026-08-31",
      runtimeIntegration: false,
      reviewMethod: "assisted_standard_reference_review",
      approvalBasis: "user_delegated_assisted_editorial_review",
      reviewer: "assistant",
      independentHumanReview: false,
      summary: { totalRecords: 4, approved: 4, pendingHumanReview: 0 },
    });
    expect(milestoneFurReview.records.map(({ id }) => id).sort())
      .toEqual(candidates.map(({ id }) => id).sort());
    expect(new Set(milestoneFurReview.records.map(({ id }) => id)).size).toBe(4);

    for (const review of milestoneFurReview.records) {
      expect(review.status).toBe("approved");
      expect(review.labelFur.trim()).toBeTruthy();
      expect(review.notes.trim()).toBeTruthy();
      expect(review.references.length).toBeGreaterThan(0);
      for (const reference of review.references) {
        expect(new URL(reference.url).protocol).toBe("https:");
        expect(reference.note.trim()).toBeTruthy();
      }
    }
  });

  it("promotes exactly four reviewed facts while preserving their individual sources", () => {
    const researchIds = new Set(candidates.map(({ id }) => id));
    const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);
    expect(runtimeMilestones.filter(({ id }) => researchIds.has(id))).toHaveLength(4);
    expect(milestonePromotion).toMatchObject({
      researchBatchId: milestoneResearch.batchId,
      furReviewBatchId: milestoneFurReview.batchId,
      approvalBasis: milestoneFurReview.approvalBasis,
      independentHumanReview: false,
      totalRecords: 4,
      addedMilestoneCounts: { "093001": 1, "093014": 2, "093037": 1 },
      resultingMilestoneCounts: { "093001": 2, "093014": 3, "093037": 3 },
    });
    expect([...milestonePromotion.recordIds].sort()).toEqual([...researchIds].sort());
    expect(municipalityProfiles.editorialPolicy.furRequiresHumanReview).toBe(true);
    expect(municipalityProfiles.editorialPolicy.furAssistedReviewExceptions).toContainEqual({
      batchId: milestoneResearch.batchId,
      approvalBasis: milestonePromotion.approvalBasis,
      independentHumanReview: false,
      recordIds: milestonePromotion.recordIds,
    });

    for (const candidate of candidates) {
      const runtime = runtimeMilestones.find(({ id }) => id === candidate.id);
      const review = milestoneFurReview.records.find(({ id }) => id === candidate.id);
      expect(runtime).toMatchObject({
        id: candidate.id,
        year: candidate.year,
        label: { it: candidate.label.it, fur: review.labelFur },
        source: candidate.source,
        languageReview: {
          it: { approvalBasis: milestonePromotion.approvalBasis },
          fur: { approvalBasis: milestonePromotion.approvalBasis, independentHumanReview: false },
        },
      });
      expect(runtime.supportingSources).toEqual(candidate.supportingSources);
    }

    for (const municipality of milestoneResearch.municipalities) {
      for (const language of ["it", "fur"]) {
        const card = getMunicipalityProfile({
          language,
          location: { city: municipality.municipality, istatCode: municipality.istatCode },
        });
        expect(card).not.toBeNull();
        expect(card.milestones).toHaveLength(
          milestonePromotion.resultingMilestoneCounts[municipality.istatCode],
        );
        const expectedYears = [...card.milestones.map(({ period }) => period)].sort((a, b) => a - b);
        expect(card.milestones.map(({ period }) => period)).toEqual(expectedYears);
        for (const candidate of municipality.candidates) {
          const review = milestoneFurReview.records.find(({ id }) => id === candidate.id);
          expect(card.milestones.find(({ id }) => id === candidate.id)).toMatchObject({
            source: candidate.source,
            label: language === "fur" ? review.labelFur : candidate.label.it,
            supportingSources: candidate.supportingSources || [],
          });
        }
      }
    }
  });

  it("updates runtime counts without rewriting the initial research snapshot", () => {
    const backlog = editorialBacklog.records.find(({ id }) => (
      id === "municipality-historical-milestones"
    ));
    const profiles = municipalityProfiles.profiles;
    expect(backlog.currentSnapshot).toEqual({
      municipalityProfiles: profiles.length,
      totalMilestones: profiles.reduce((sum, profile) => sum + profile.milestones.length, 0),
      profilesWithoutMilestones: profiles.filter(({ milestones }) => milestones.length === 0).length,
      profilesWithOneMilestone: profiles.filter(({ milestones }) => milestones.length === 1).length,
      profilesWithTwoMilestones: profiles.filter(({ milestones }) => milestones.length === 2).length,
      profilesWithAtLeastThreeMilestones: profiles.filter(({ milestones }) => milestones.length >= 3).length,
      pordenoneMilestones: profiles.find(({ istatCode }) => istatCode === "093033").milestones.length,
    });
    expect(backlog.previousResearchBatches.find(({ batchId }) => batchId === milestoneResearch.batchId)).toEqual({
      batchId: milestoneResearch.batchId,
      snapshotDate: milestoneResearch.snapshotDate,
      municipalities: milestoneResearch.municipalities.length,
      sourceVerifiedCandidates: candidates.length,
      itDraftCandidates: 0,
      furDraftPendingReviewCandidates: 0,
      promotedCandidates: candidates.length,
      runtimeIntegration: false,
    });
  });
});
