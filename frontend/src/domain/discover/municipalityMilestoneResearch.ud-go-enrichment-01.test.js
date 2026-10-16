import { describe, expect, it } from "vitest";

import ostermannRecords from "../../data/ostermannCulturalDiscover.json";
import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import institutionalArchive from "../../data/discover/institutionalArchive.json";
import institutionalRituals from "../../data/discover/institutionalRituals.json";
import localMemory from "../../data/discover/localMemory.json";
import milestoneFurReview from "../../data/discover/municipalityMilestoneFurReview.ud-go-enrichment-01.json";
import milestonePromotion from "../../data/discover/municipalityMilestonePromotion.ud-go-enrichment-01.json";
import milestoneResearch from "../../data/discover/municipalityMilestoneResearch.ud-go-enrichment-01.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_MUNICIPALITIES = [
  ["030008", "Bagnaria Arsa", "UD", ["bagnaria-arsa-name"], 2],
  ["030114", "Talmassons", "UD", ["talmassons-plebs-flambri", "talmassons-sanvidotto"], 1],
  ["031012", "Monfalcone", "GO", ["monfalcone-return-to-italy", "monfalcone-osimo-border-ratification"], 1],
];
const EXPECTED_FACTS = [
  ["bagnaria-arsa-censimento-1375", 1375, "030008"],
  ["bagnaria-arsa-necropoli-1990", 1990, "030008"],
  ["talmassons-feudo-bojani-1339", 1339, "030114"],
  ["monfalcone-cantiere-navale-1908", 1908, "031012"],
];
const candidates = milestoneResearch.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone UD/GO enrichment", () => {
  it("keeps four dated source facts in a separate immutable research stage", () => {
    expect(milestoneResearch).toMatchObject({
      schemaVersion: 1,
      batchId: "ud-go-enrichment-milestones-01",
      snapshotDate: "2026-08-31",
      runtimeIntegration: false,
      initialTotalMilestones: 411,
      editorialPolicy: {
        sourceEvidenceRequired: true,
        ambiguousDatesExcluded: true,
        italianCopyStatus: "editorial_draft",
        friulianCopyStatus: "pending_assisted_review",
        readyForUi: false,
      },
    });
    expect(candidates.map(({ id, year, istatCode }) => [id, year, istatCode])).toEqual(EXPECTED_FACTS);
    expect(new Set(candidates.map(({ id }) => id)).size).toBe(4);
    expect(new Set(candidates.map(({ label }) => label.it)).size).toBe(4);
    for (const candidate of candidates) {
      expect(candidate.label.it.trim()).toBeTruthy();
      expect(candidate.label.fur).toBeNull();
      expect(candidate.century).toBeUndefined();
      expect(candidate.evidence.trim()).toBeTruthy();
      expect(candidate.duplicateReview.exactDuplicate).toBe(false);
      expect(candidate.duplicateReview.note.trim()).toBeTruthy();
      expect(["official_municipality", "cultural_institution"]).toContain(candidate.source.type);
      expect(new URL(candidate.source.url).protocol).toBe("https:");
      expect(candidate.source.label.trim()).toBeTruthy();
      expect(candidate.source.checkedAt).toBe("2026-08-31");
    }
  });

  it("preserves the existing milestones of the exact three municipalities and stays within three", () => {
    expect(milestoneResearch.municipalities.map((municipality) => [
      municipality.istatCode, municipality.municipality, municipality.province,
      municipality.currentMilestoneIds, municipality.candidates.length,
    ])).toEqual(EXPECTED_MUNICIPALITIES);
    for (const municipality of milestoneResearch.municipalities) {
      const profile = municipalityProfiles.profiles.find(({ istatCode }) => istatCode === municipality.istatCode);
      expect(profile).toMatchObject({ municipality: municipality.municipality, province: municipality.province });
      expect(profile.milestones.filter(({ id }) => municipality.currentMilestoneIds.includes(id))
        .map(({ id }) => id)).toEqual(municipality.currentMilestoneIds);
      expect(municipality.currentMilestoneCount).toBe(municipality.currentMilestoneIds.length);
      expect(profile.milestones).toHaveLength(municipality.currentMilestoneCount + municipality.candidates.length);
      expect(profile.milestones).toHaveLength(3);
      expect(profile.milestones.map(({ year }) => year))
        .toEqual([...profile.milestones.map(({ year }) => year)].sort((a, b) => a - b));
    }
  });

  it("distinguishes the discovery date, the medieval census and the Monfalcone shipyard", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["bagnaria-arsa-censimento-1375"].label.it).toMatch(/censimento.*nomi.*età.*mestieri/);
    expect(byId["bagnaria-arsa-necropoli-1990"].label.it).toMatch(/rinvenute undici tombe.*altomedievale/);
    expect(byId["bagnaria-arsa-necropoli-1990"].evidence).toMatch(/1990.*VII secolo/);
    expect(byId["talmassons-feudo-bojani-1339"].source.url)
      .toBe("https://www.comune.talmassons.ud.it/informazioni-sul-comune/storia/");
    expect(byId["monfalcone-cantiere-navale-1908"]).toMatchObject({
      documentedDate: "1908-04-03",
      istatCode: "031012",
      source: { url: "https://www.mucamonfalcone.it/storia-del-cantiere/" },
    });
    expect(byId["monfalcone-cantiere-navale-1908"].label.it).toMatch(/Cosulich.*Monfalcone.*Cantiere Navale Triestino/);
    expect(milestoneResearch.excludedClaims).toEqual(expect.arrayContaining([
      expect.objectContaining({ claim: expect.stringContaining("Tutte le undici tombe") }),
      expect.objectContaining({ claim: expect.stringContaining("primo censimento") }),
    ]));
  });

  it("records assisted FUR approval without claiming an independent or certified translation", () => {
    expect(milestoneFurReview).toMatchObject({
      batchId: "ud-go-enrichment-milestones-01-fur-review",
      sourceResearchBatchId: milestoneResearch.batchId,
      runtimeIntegration: false,
      reviewMethod: "assisted_standard_reference_review",
      approvalBasis: "user_delegated_assisted_editorial_review",
      reviewer: "assistant",
      independentHumanReview: false,
      summary: { totalRecords: 4, approved: 4, pendingHumanReview: 0 },
    });
    expect(milestoneFurReview.records.map(({ id }) => id)).toEqual(candidates.map(({ id }) => id));
    for (const review of milestoneFurReview.records) {
      expect(review.status).toBe("approved");
      expect(review.labelFur.trim()).toBeTruthy();
      expect(review.notes.trim()).toBeTruthy();
      expect(review.references.length).toBeGreaterThan(0);
      for (const reference of review.references) {
        expect(new URL(reference.url).protocol).toBe("https:");
        expect(new URL(reference.url).hostname).toBe("superdizionari.arlef.it");
        expect(reference.note.trim()).toBeTruthy();
      }
    }
  });

  it("promotes only these four records with their own sources and a scoped review exception", () => {
    expect(milestonePromotion).toMatchObject({
      researchBatchId: milestoneResearch.batchId,
      furReviewBatchId: milestoneFurReview.batchId,
      approvalBasis: milestoneFurReview.approvalBasis,
      independentHumanReview: false,
      totalRecords: 4,
      previousTotalMilestones: 411,
      resultingTotalMilestones: 415,
      addedMilestoneCounts: { "030008": 2, "030114": 1, "031012": 1 },
      resultingMilestoneCounts: { "030008": 3, "030114": 3, "031012": 3 },
    });
    expect(milestonePromotion.previousTotalMilestones + milestonePromotion.totalRecords)
      .toBe(milestonePromotion.resultingTotalMilestones);
    expect(milestonePromotion.recordIds).toEqual(candidates.map(({ id }) => id));
    expect(runtimeMilestones.filter(({ id }) => milestonePromotion.recordIds.includes(id))).toHaveLength(4);
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(municipalityProfiles.profiles.every(({ milestones }) => milestones.length <= 3)).toBe(true);
    expect(municipalityProfiles.editorialPolicy.furRequiresHumanReview).toBe(true);
    expect(municipalityProfiles.editorialPolicy.furAssistedReviewExceptions).toContainEqual({
      batchId: milestoneResearch.batchId,
      approvalBasis: milestonePromotion.approvalBasis,
      independentHumanReview: false,
      recordIds: milestonePromotion.recordIds,
    });
    for (const candidate of candidates) {
      const matches = runtimeMilestones.filter(({ id }) => id === candidate.id);
      const review = milestoneFurReview.records.find(({ id }) => id === candidate.id);
      expect(matches).toHaveLength(1);
      expect(matches[0]).toMatchObject({
        year: candidate.year,
        label: { it: candidate.label.it, fur: review.labelFur },
        source: candidate.source,
        languageReview: {
          it: { approvalBasis: milestonePromotion.approvalBasis },
          fur: { reviewBatchId: milestoneFurReview.batchId, independentHumanReview: false },
        },
      });
      expect(matches[0].documentedDate).toBe(candidate.documentedDate);
    }
    const otherRecords = [...localMemory.records, ...institutionalArchive, ...institutionalRituals, ...ostermannRecords];
    expect(otherRecords.some(({ id }) => milestonePromotion.recordIds.includes(id))).toBe(false);
  });

  it("serves both languages with the specific new source and the fallback for existing milestones", () => {
    for (const municipality of milestoneResearch.municipalities) {
      const profile = municipalityProfiles.profiles.find(({ istatCode }) => istatCode === municipality.istatCode);
      for (const language of ["it", "fur"]) {
        const card = getMunicipalityProfile({
          language, location: { city: municipality.municipality, istatCode: municipality.istatCode },
        });
        expect(card.milestones).toHaveLength(3);
        for (const milestone of profile.milestones) {
          expect(card.milestones.find(({ id }) => id === milestone.id)).toMatchObject({
            period: milestone.year,
            label: milestone.label[language],
            source: milestone.source || profile.source,
            supportingSources: [],
          });
        }
      }
    }
  });

  it("updates the current backlog while preserving the pre-promotion baseline", () => {
    const backlog = editorialBacklog.records.find(({ id }) => id === "municipality-historical-milestones");
    expect(backlog.currentSnapshot).toMatchObject({
      municipalityProfiles: municipalityProfiles.profiles.length,
      totalMilestones: runtimeMilestones.length, profilesWithoutMilestones: 0,
      profilesWithOneMilestone: municipalityProfiles.profiles.filter(({ milestones }) => milestones.length === 1).length,
      profilesWithTwoMilestones: municipalityProfiles.profiles.filter(({ milestones }) => milestones.length === 2).length,
      profilesWithAtLeastThreeMilestones: municipalityProfiles.profiles.filter(({ milestones }) => milestones.length >= 3).length,
    });
    expect(backlog.previousResearchBatches.find(({ batchId }) => batchId === milestoneResearch.batchId)).toMatchObject({
      batchId: milestoneResearch.batchId, sourceVerifiedCandidates: 4, promotedCandidates: 4,
      itDraftCandidates: 0, furDraftPendingReviewCandidates: 0,
    });
    expect(milestoneResearch.initialTotalMilestones).toBe(milestonePromotion.previousTotalMilestones);
  });
});
