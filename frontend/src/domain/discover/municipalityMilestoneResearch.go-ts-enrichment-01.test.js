import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import review from "../../data/discover/municipalityMilestoneFurReview.go-ts-enrichment-01.json";
import promotion from "../../data/discover/municipalityMilestonePromotion.go-ts-enrichment-01.json";
import udGo02Promotion from "../../data/discover/municipalityMilestonePromotion.ud-go-enrichment-02.json";
import udPn05Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-05.json";
import ud06Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-06.json";
import udPn07Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-07.json";
import pn08Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-08.json";
import research from "../../data/discover/municipalityMilestoneResearch.go-ts-enrichment-01.json";
import ud09Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_FACTS = [
  [
    "doberdo-prima-attestazione-1179",
    1179,
    "031003",
    "https://www.comune.doberdo.go.it/it/vivere-il-comune-96560/luoghi-96561/storia-156637",
  ],
  [
    "doberdo-comunita-zupa-1524",
    1524,
    "031003",
    "https://www.comune.doberdo.go.it/it/vivere-il-comune-96560/luoghi-96561/storia-156637",
  ],
  [
    "sgonico-grotta-gigante-apertura-1908",
    1908,
    "032005",
    "https://catastogrotte.regione.fvg.it/scheda/2-Grotta_Gigante",
  ],
];
const EXPECTED_PROFILES = [
  ["031003", "Doberdò del Lago", "GO", 1, 3, 2],
  ["032005", "Sgonico", "TS", 2, 3, 1],
];
const newIds = new Set(EXPECTED_FACTS.map(([id]) => id));
const candidates = research.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone Doberdò del Lago and Sgonico enrichment", () => {
  it("keeps three source-verified facts in a hidden research snapshot", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      batchId: "go-ts-enrichment-milestones-01",
      snapshotDate: "2026-09-01",
      runtimeIntegration: false,
      initialTotalMilestones: 438,
      editorialPolicy: {
        sourceEvidenceRequired: true,
        ambiguousDatesExcluded: true,
        readyForUi: false,
      },
    });
    expect(candidates.map(({ id, year, istatCode, source }) => [id, year, istatCode, source.url]))
      .toEqual(EXPECTED_FACTS);
    expect(new Set(candidates.map(({ id }) => id))).toHaveProperty("size", 3);
    for (const candidate of candidates) {
      expect(candidate.label.it.trim()).toBeTruthy();
      expect(candidate.label.fur).toBeNull();
      expect(candidate.evidence.trim()).toBeTruthy();
      expect(candidate.duplicateReview).toMatchObject({ exactDuplicate: false });
      expect(["official_municipality", "regional_institution"]).toContain(candidate.source.type);
      for (const source of [candidate.source, ...(candidate.supportingSources || [])]) {
        expect(new URL(source.url).protocol).toBe("https:");
        expect(source.checkedAt).toBe("2026-09-01");
      }
    }
    expect(candidates.find(({ id }) => id === "sgonico-grotta-gigante-apertura-1908"))
      .toMatchObject({ documentedDate: "1908-07-05" });
  });

  it("preserves the 215-profile, 438-milestone baseline byte-for-byte", () => {
    const previousProfiles = municipalityProfiles.profiles.map((profile) => ({
      ...profile,
      milestones: profile.milestones.filter(({ id }) => (
        !newIds.has(id) && !udGo02Promotion.recordIds.includes(id)
          && !udPn05Promotion.recordIds.includes(id)
          && !ud06Promotion.recordIds.includes(id)
          && !udPn07Promotion.recordIds.includes(id)
          && !pn08Promotion.recordIds.includes(id) && !ud09Promotion.recordIds.includes(id)
      )),
    }));
    expect(createHash("sha256").update(JSON.stringify(previousProfiles)).digest("hex"))
      .toBe("6bc8dcc31532aeac0e6b1c8029b73aa2e581ba33aa3ce4eb9473b95d6db39c67");
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(previousProfiles.flatMap(({ milestones }) => milestones)).toHaveLength(438);
    expect(runtimeMilestones).toHaveLength(463);
    expect(new Set(runtimeMilestones.map(({ id }) => id))).toHaveProperty("size", 463);
  });

  it("moves both exact municipalities to three chronological facts", () => {
    for (const [istatCode, city, province, previousCount, resultingCount, addedCount]
      of EXPECTED_PROFILES) {
      const municipality = research.municipalities.find((record) => record.istatCode === istatCode);
      const profile = municipalityProfiles.profiles.find((record) => record.istatCode === istatCode);
      expect(municipality).toMatchObject({
        municipality: city,
        province,
        currentMilestoneCount: previousCount,
      });
      expect(municipality.currentMilestoneIds).toHaveLength(previousCount);
      expect(municipality.candidates).toHaveLength(addedCount);
      expect(profile.milestones).toHaveLength(resultingCount);
      const years = profile.milestones.map(({ year }) => year).filter(Number.isInteger);
      expect(years).toEqual([...years].sort((a, b) => a - b));
    }
  });

  it("keeps the claims inside their documented scope", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["doberdo-prima-attestazione-1179"].label.it)
      .not.toMatch(/Comune.*nasce|etimolog/iu);
    expect(byId["doberdo-comunita-zupa-1524"].label.it).toMatch(/župa/u);
    expect(byId["doberdo-comunita-zupa-1524"].label.it)
      .not.toMatch(/Comune moderno|municipalità/iu);
    expect(byId["sgonico-grotta-gigante-apertura-1908"].label.it)
      .not.toMatch(/Comune.*inaugura|inaugurata dal Comune/iu);
    expect(research.excludedClaims).toHaveLength(3);
    expect(research.excludedClaims.map(({ municipality }) => municipality))
      .toEqual(["Doberdò del Lago", "Doberdò del Lago", "Sgonico"]);
  });

  it("scopes assisted FUR approval and ARLeF references to the three IDs", () => {
    expect(review).toMatchObject({
      batchId: "go-ts-enrichment-milestones-01-fur-review",
      sourceResearchBatchId: research.batchId,
      runtimeIntegration: false,
      reviewMethod: "assisted_standard_reference_review",
      approvalBasis: "user_delegated_assisted_editorial_review",
      reviewer: "assistant",
      independentHumanReview: false,
      summary: { totalRecords: 3, approved: 3, pendingHumanReview: 0 },
    });
    expect(review.records.map(({ id }) => id)).toEqual([...newIds]);
    expect(review.approvalNote).toMatch(/non certificano|non certificazione/iu);
    for (const record of review.records) {
      expect(record).toMatchObject({ status: "approved" });
      expect(record.labelFur.trim()).toBeTruthy();
      expect(record.notes.trim()).toBeTruthy();
      expect(record.references.length).toBeGreaterThan(0);
      for (const reference of record.references) {
        expect(["superdizionari.arlef.it", "arlef.it"])
          .toContain(new URL(reference.url).hostname);
      }
    }
    expect(municipalityProfiles.editorialPolicy.furAssistedReviewExceptions).toContainEqual({
      batchId: research.batchId,
      approvalBasis: review.approvalBasis,
      independentHumanReview: false,
      recordIds: [...newIds],
    });
  });

  it("promotes exactly the three reviewed labels with their individual sources", () => {
    expect(promotion).toMatchObject({
      researchBatchId: research.batchId,
      furReviewBatchId: review.batchId,
      totalRecords: 3,
      previousTotalMilestones: 438,
      resultingTotalMilestones: 441,
      addedMilestoneCounts: { "031003": 2, "032005": 1 },
      resultingMilestoneCounts: { "031003": 3, "032005": 3 },
      recordIds: [...newIds],
    });
    for (const candidate of candidates) {
      const match = runtimeMilestones.find(({ id }) => id === candidate.id);
      const copy = review.records.find(({ id }) => id === candidate.id);
      expect(match).toMatchObject({
        year: candidate.year,
        label: { it: candidate.label.it, fur: copy.labelFur },
        source: candidate.source,
        languageReview: {
          it: { approvalBasis: review.approvalBasis },
          fur: { reviewBatchId: review.batchId, independentHumanReview: false },
        },
      });
      expect(match.documentedDate).toBe(candidate.documentedDate);
      expect(match.supportingSources || []).toEqual(candidate.supportingSources || []);
    }
  });

  for (const [istatCode, city, , , resultingCount, addedCount] of EXPECTED_PROFILES) {
    it.each(["it", "fur"])(`renders all ${city} facts in %s without cross-location leakage`, (language) => {
      const location = { city, istatCode };
      const profile = municipalityProfiles.profiles.find((record) => record.istatCode === istatCode);
      const ownNewIds = profile.milestones.filter(({ id }) => newIds.has(id)).map(({ id }) => id);
      const card = getMunicipalityProfile({ language, location });
      const model = buildDiscoverViewModel({ language, location, today: "2028-09-01" });
      expect(model.focus).toMatchObject(card);
      expect(card.milestones).toHaveLength(resultingCount);
      expect(ownNewIds).toHaveLength(addedCount);
      expect(card.milestones.filter(({ id }) => newIds.has(id))).toHaveLength(addedCount);
      const html = renderToStaticMarkup(createElement(DiscoverCard, {
        card: model.focus,
        municipalityMilestonesTitle: model.copy.municipalityMilestonesTitle,
      }));
      for (const milestone of card.milestones) {
        expect(html).toContain(renderToStaticMarkup(createElement("span", null, milestone.label)));
        expect(html).toContain(renderToStaticMarkup(createElement("time", null, milestone.period)));
      }
      for (const id of ownNewIds) {
        expect(card.milestones.some((milestone) => milestone.id === id)).toBe(true);
      }
    });
  }

  it("tracks 99 underfilled profiles and keeps municipality work active", () => {
    const backlog = editorialBacklog.records.find(({ id }) => id === "municipality-historical-milestones");
    expect(backlog.currentSnapshot).toMatchObject({
      municipalityProfiles: 215,
      totalMilestones: 463,
      profilesWithoutMilestones: 0,
      profilesWithOneMilestone: 83,
      profilesWithTwoMilestones: 16,
      profilesWithAtLeastThreeMilestones: 116,
    });
    expect(backlog.currentSnapshot.profilesWithOneMilestone
      + backlog.currentSnapshot.profilesWithTwoMilestones).toBe(99);
    expect(backlog.previousResearchBatches).toContainEqual(expect.objectContaining({
      batchId: research.batchId,
      municipalities: 2,
      sourceVerifiedCandidates: 3,
      promotedCandidates: 3,
      runtimeIntegration: false,
    }));
    expect(backlog.researchProgress.batchId).toBe("ud-enrichment-milestones-09");
    expect(backlog.previousResearchBatches.at(-1).batchId)
      .toBe("pn-enrichment-milestones-08");
    expect(editorialBacklog.executionPlan).toMatchObject({
      strategy: "municipality_first_editorial_batches",
      nextFocus: "municipality-historical-milestones",
    });
  });
});
