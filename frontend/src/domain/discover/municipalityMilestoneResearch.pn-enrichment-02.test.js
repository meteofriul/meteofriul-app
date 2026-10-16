import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import review from "../../data/discover/municipalityMilestoneFurReview.pn-enrichment-02.json";
import promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-02.json";
import goTsPromotion from "../../data/discover/municipalityMilestonePromotion.go-ts-enrichment-01.json";
import udGo02Promotion from "../../data/discover/municipalityMilestonePromotion.ud-go-enrichment-02.json";
import udPn05Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-05.json";
import ud06Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-06.json";
import udPn07Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-07.json";
import pn08Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-08.json";
import research from "../../data/discover/municipalityMilestoneResearch.pn-enrichment-02.json";
import ud09Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_FACTS = [
  [
    "budoia-opere-idrauliche-dardago-1670",
    1670,
    "093008",
    "https://turismo.comune.budoia.pn.it/contenuti/430923/storia",
  ],
  [
    "budoia-scuola-femminile-1870",
    1870,
    "093008",
    "https://turismo.comune.budoia.pn.it/contenuti/430923/storia",
  ],
  [
    "fiume-veneto-predicato-1911",
    1911,
    "093021",
    "https://www.comune.fiumeveneto.pn.it/it/cultura-23021/la-storia-26125",
  ],
  [
    "sesto-al-reghena-abbazia-distrutta-899",
    899,
    "093043",
    "https://www.comune.sesto-al-reghena.pn.it/labbazia/",
  ],
];
const EXPECTED_PROFILES = [
  ["093008", "Budoia", "PN", 1, 3, 2],
  ["093021", "Fiume Veneto", "PN", 2, 3, 1],
  ["093043", "Sesto al Reghena", "PN", 2, 3, 1],
];
const newIds = new Set(EXPECTED_FACTS.map(([id]) => id));
const candidates = research.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone Budoia, Fiume Veneto and Sesto al Reghena enrichment", () => {
  it("keeps four source-verified facts in a hidden research snapshot", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      batchId: "pn-enrichment-milestones-02",
      snapshotDate: "2026-09-01",
      runtimeIntegration: false,
      initialTotalMilestones: 434,
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
      expect(candidate.source.type).toBe("official_municipality");
      expect(new URL(candidate.source.url).protocol).toBe("https:");
      expect(candidate.source.checkedAt).toBe("2026-09-01");
    }
  });

  it("preserves the 215-profile, 434-milestone baseline byte-for-byte", () => {
    const previousProfiles = municipalityProfiles.profiles.map((profile) => ({
      ...profile,
      milestones: profile.milestones.filter(({ id }) => (
        !newIds.has(id) && !goTsPromotion.recordIds.includes(id)
          && !udGo02Promotion.recordIds.includes(id) && !udPn05Promotion.recordIds.includes(id)
          && !ud06Promotion.recordIds.includes(id)
          && !udPn07Promotion.recordIds.includes(id)
          && !pn08Promotion.recordIds.includes(id) && !ud09Promotion.recordIds.includes(id)
      )),
    }));
    expect(createHash("sha256").update(JSON.stringify(previousProfiles)).digest("hex"))
      .toBe("6499a3c60a8b4e2d0bb063faecc2cbdc959e530c06e1f49efa20c01586cc5b0c");
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(previousProfiles.flatMap(({ milestones }) => milestones)).toHaveLength(434);
    expect(runtimeMilestones).toHaveLength(463);
    expect(new Set(runtimeMilestones.map(({ id }) => id))).toHaveProperty("size", 463);
  });

  it("moves the three exact municipalities to three documented facts", () => {
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

  it("keeps every claim inside the official source evidence", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["budoia-opere-idrauliche-dardago-1670"].label.it)
      .not.toMatch(/primo|prima.*Friuli/iu);
    expect(byId["budoia-scuola-femminile-1870"].label.it)
      .not.toMatch(/parità|uguaglianza/iu);
    expect(byId["fiume-veneto-predicato-1911"].label.it)
      .not.toMatch(/nasce|fondat/iu);
    expect(byId["sesto-al-reghena-abbazia-distrutta-899"].label.it).toMatch(/abbazia/iu);
    expect(byId["sesto-al-reghena-abbazia-distrutta-899"].label.it)
      .not.toMatch(/ricostru/iu);
    expect(research.excludedClaims).toHaveLength(4);
    expect(research.excludedClaims.map(({ municipality }) => municipality))
      .toEqual(["Budoia", "Budoia", "Fiume Veneto", "Sesto al Reghena"]);
  });

  it("scopes assisted FUR approval and ARLeF references to the four IDs", () => {
    expect(review).toMatchObject({
      batchId: "pn-enrichment-milestones-02-fur-review",
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

  it("promotes exactly the four reviewed labels with their individual sources", () => {
    expect(promotion).toMatchObject({
      researchBatchId: research.batchId,
      furReviewBatchId: review.batchId,
      totalRecords: 4,
      previousTotalMilestones: 434,
      resultingTotalMilestones: 438,
      addedMilestoneCounts: { "093008": 2, "093021": 1, "093043": 1 },
      resultingMilestoneCounts: { "093008": 3, "093021": 3, "093043": 3 },
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

  it("keeps the completed PN batch in history while municipality work continues", () => {
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
      municipalities: 3,
      sourceVerifiedCandidates: 4,
      promotedCandidates: 4,
      runtimeIntegration: false,
    }));
    expect(backlog.previousResearchBatches.at(-1).batchId)
      .toBe("pn-enrichment-milestones-08");
    expect(editorialBacklog.executionPlan.nextFocus).toBe("municipality-historical-milestones");
  });
});
