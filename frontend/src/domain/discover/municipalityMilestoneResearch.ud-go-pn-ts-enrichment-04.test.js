import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import review from "../../data/discover/municipalityMilestoneFurReview.ud-go-pn-ts-enrichment-04.json";
import promotion from "../../data/discover/municipalityMilestonePromotion.ud-go-pn-ts-enrichment-04.json";
import pn02Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-02.json";
import goTsPromotion from "../../data/discover/municipalityMilestonePromotion.go-ts-enrichment-01.json";
import udGo02Promotion from "../../data/discover/municipalityMilestonePromotion.ud-go-enrichment-02.json";
import udPn05Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-05.json";
import ud06Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-06.json";
import udPn07Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-07.json";
import pn08Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-08.json";
import research from "../../data/discover/municipalityMilestoneResearch.ud-go-pn-ts-enrichment-04.json";
import ud09Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_FACTS = [
  [
    "palmanova-terza-cinta-1806",
    1806,
    "030070",
    "https://www.comune.palmanova.ud.it/it/territorio-2802/storia-della-fortezza-3654",
  ],
  [
    "medea-truppe-italiane-1915",
    1915,
    "031011",
    "https://www.comune.medea.go.it/it/turismo-e-informazioni-7829/la-storia-17930",
  ],
  [
    "sgonico-carsiana-apertura-1978",
    1978,
    "032005",
    "https://giardinobotanicocarsiana.it/it/giardino/storia.html",
  ],
  [
    "spilimbergo-scuola-mosaico-1922",
    1922,
    "093044",
    "https://scuolamosaicistifriuli.it/storia-e-attualita/",
  ],
];
const EXPECTED_PROFILES = [
  ["030070", "Palmanova", "UD", 2, 3],
  ["031011", "Medea", "GO", 2, 3],
  ["032005", "Sgonico", "TS", 1, 3],
  ["093044", "Spilimbergo", "PN", 2, 3],
];
const newIds = new Set(EXPECTED_FACTS.map(([id]) => id));
const candidates = research.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone Palmanova, Medea, Sgonico and Spilimbergo enrichment", () => {
  it("keeps four source-verified facts in a hidden research snapshot", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      batchId: "ud-go-pn-ts-enrichment-milestones-04",
      snapshotDate: "2026-09-01",
      runtimeIntegration: false,
      initialTotalMilestones: 430,
      editorialPolicy: {
        sourceEvidenceRequired: true,
        ambiguousDatesExcluded: true,
        readyForUi: false,
      },
    });
    expect(candidates.map(({ id, year, istatCode, source }) => [id, year, istatCode, source.url]))
      .toEqual(EXPECTED_FACTS);
    expect(new Set(candidates.map(({ id }) => id))).toHaveProperty("size", 4);
    for (const candidate of candidates) {
      expect(candidate.label.it.trim()).toBeTruthy();
      expect(candidate.label.fur).toBeNull();
      expect(candidate.evidence.trim()).toBeTruthy();
      expect(candidate.documentedDate).toBeUndefined();
      expect(candidate.duplicateReview).toMatchObject({ exactDuplicate: false });
      for (const source of [candidate.source, ...(candidate.supportingSources || [])]) {
        expect(["official_municipality", "cultural_institution"]).toContain(source.type);
        expect(new URL(source.url).protocol).toBe("https:");
        expect(source.checkedAt).toBe("2026-09-01");
      }
    }
  });

  it("preserves the 215-profile, 430-milestone baseline byte-for-byte", () => {
    const previousProfiles = municipalityProfiles.profiles.map((profile) => ({
      ...profile,
      milestones: profile.milestones.filter(({ id }) => (
        !newIds.has(id) && !pn02Promotion.recordIds.includes(id) && !goTsPromotion.recordIds.includes(id)
          && !udGo02Promotion.recordIds.includes(id) && !udPn05Promotion.recordIds.includes(id)
          && !ud06Promotion.recordIds.includes(id)
          && !udPn07Promotion.recordIds.includes(id)
          && !pn08Promotion.recordIds.includes(id) && !ud09Promotion.recordIds.includes(id)
      )),
    }));
    expect(createHash("sha256").update(JSON.stringify(previousProfiles)).digest("hex"))
      .toBe("0361b363e89e64ffd80b894aca6a32e5a2c0c470064b33716b849e020e8d7dea");
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(previousProfiles.flatMap(({ milestones }) => milestones)).toHaveLength(430);
    expect(runtimeMilestones).toHaveLength(463);
    expect(new Set(runtimeMilestones.map(({ id }) => id))).toHaveProperty("size", 463);
  });

  it("keeps the four exact municipalities at their current documented counts", () => {
    for (const [istatCode, city, province, previousCount, resultingCount] of EXPECTED_PROFILES) {
      const municipality = research.municipalities.find((record) => record.istatCode === istatCode);
      const profile = municipalityProfiles.profiles.find((record) => record.istatCode === istatCode);
      expect(municipality).toMatchObject({
        municipality: city,
        province,
        currentMilestoneCount: previousCount,
      });
      expect(municipality.currentMilestoneIds).toHaveLength(previousCount);
      expect(municipality.candidates).toHaveLength(1);
      expect(profile.milestones).toHaveLength(resultingCount);
      const years = profile.milestones.map(({ year }) => year).filter(Number.isInteger);
      expect(years).toEqual([...years].sort((a, b) => a - b));
    }
  });

  it("keeps every claim inside the source evidence", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["palmanova-terza-cinta-1806"].label.it).toMatch(/^Inizia/);
    expect(byId["palmanova-terza-cinta-1806"].label.it).not.toMatch(/complet/iu);
    expect(byId["medea-truppe-italiane-1915"].label.it).not.toMatch(/annession|liberazion/iu);
    expect(byId["sgonico-carsiana-apertura-1978"].label.it).toMatch(/apre al pubblico/iu);
    expect(byId["sgonico-carsiana-apertura-1978"].label.it).not.toMatch(/fondat/iu);
    expect(byId["spilimbergo-scuola-mosaico-1922"].label.it).not.toMatch(/prima in Italia|primato/iu);
    expect(research.excludedClaims).toHaveLength(4);
    expect(research.excludedClaims.map(({ municipality }) => municipality))
      .toEqual(["Palmanova", "Medea", "Sgonico", "Spilimbergo"]);
  });

  it("scopes assisted FUR approval and ARLeF references to the four IDs", () => {
    expect(review).toMatchObject({
      batchId: "ud-go-pn-ts-enrichment-milestones-04-fur-review",
      sourceResearchBatchId: research.batchId,
      runtimeIntegration: false,
      reviewMethod: "assisted_standard_reference_review",
      approvalBasis: "user_delegated_assisted_editorial_review",
      reviewer: "assistant",
      independentHumanReview: false,
      summary: { totalRecords: 4, approved: 4, pendingHumanReview: 0 },
    });
    expect(review.records.map(({ id }) => id)).toEqual([...newIds]);
    expect(review.approvalNote).toMatch(/non certificano|non certificazione/iu);
    for (const record of review.records) {
      expect(record).toMatchObject({ status: "approved" });
      expect(record.labelFur.trim()).toBeTruthy();
      expect(record.notes.trim()).toBeTruthy();
      expect(record.references.length).toBeGreaterThan(0);
      for (const reference of record.references) {
        expect(["superdizionari.arlef.it", "arlef.it"]).toContain(new URL(reference.url).hostname);
      }
    }
    expect(municipalityProfiles.editorialPolicy.furAssistedReviewExceptions).toContainEqual({
      batchId: research.batchId,
      approvalBasis: review.approvalBasis,
      independentHumanReview: false,
      recordIds: [...newIds],
    });
  });

  it("promotes exactly the four reviewed labels with their individual sources", () => {
    expect(promotion).toMatchObject({
      researchBatchId: research.batchId,
      furReviewBatchId: review.batchId,
      totalRecords: 4,
      previousTotalMilestones: 430,
      resultingTotalMilestones: 434,
      addedMilestoneCounts: { "030070": 1, "031011": 1, "032005": 1, "093044": 1 },
      resultingMilestoneCounts: { "030070": 3, "031011": 3, "032005": 2, "093044": 3 },
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
      expect(match.supportingSources || []).toEqual(candidate.supportingSources || []);
    }
  });

  for (const [istatCode, city, , , resultingCount] of EXPECTED_PROFILES) {
    it.each(["it", "fur"])(`renders all ${city} facts in %s without cross-location leakage`, (language) => {
      const location = { city, istatCode };
      const profile = municipalityProfiles.profiles.find((record) => record.istatCode === istatCode);
      const ownNewId = profile.milestones.find(({ id }) => newIds.has(id)).id;
      const card = getMunicipalityProfile({ language, location });
      const model = buildDiscoverViewModel({ language, location, today: "2028-09-01" });
      expect(model.focus).toMatchObject(card);
      expect(card.milestones).toHaveLength(resultingCount);
      expect(card.milestones.some(({ id }) => id === ownNewId)).toBe(true);
      expect(card.milestones.filter(({ id }) => newIds.has(id))).toHaveLength(1);
      const html = renderToStaticMarkup(createElement(DiscoverCard, {
        card: model.focus,
        municipalityMilestonesTitle: model.copy.municipalityMilestonesTitle,
      }));
      for (const milestone of card.milestones) {
        expect(html).toContain(renderToStaticMarkup(createElement("span", null, milestone.label)));
        expect(html).toContain(renderToStaticMarkup(createElement("time", null, milestone.period)));
      }
    });
  }

  it("tracks 99 underfilled profiles while municipality work continues", () => {
    const backlog = editorialBacklog.records.find(({ id }) => id === "municipality-historical-milestones");
    expect(backlog.currentSnapshot).toMatchObject({
      municipalityProfiles: 215,
      totalMilestones: 463,
      profilesWithoutMilestones: 0,
      profilesWithOneMilestone: 83,
      profilesWithTwoMilestones: 16,
      profilesWithAtLeastThreeMilestones: 116,
    });
    expect(backlog.currentSnapshot.profilesWithOneMilestone + backlog.currentSnapshot.profilesWithTwoMilestones)
      .toBe(99);
    expect(backlog.previousResearchBatches).toContainEqual(expect.objectContaining({
      batchId: research.batchId,
      municipalities: 4,
      sourceVerifiedCandidates: 4,
      promotedCandidates: 4,
    }));
    expect(backlog.previousResearchBatches).toContainEqual(expect.objectContaining({
      batchId: "ud-go-pn-enrichment-milestones-03",
      promotedCandidates: 3,
    }));
    expect(editorialBacklog.executionPlan.nextFocus).toBe("municipality-historical-milestones");
  });
});
