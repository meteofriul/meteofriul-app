import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import review from "../../data/discover/municipalityMilestoneFurReview.ud-go-enrichment-02.json";
import promotion from "../../data/discover/municipalityMilestonePromotion.ud-go-enrichment-02.json";
import udPn05Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-05.json";
import ud06Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-06.json";
import udPn07Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-07.json";
import pn08Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-08.json";
import research from "../../data/discover/municipalityMilestoneResearch.ud-go-enrichment-02.json";
import ud09Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_FACTS = [
  [
    "san-daniele-consorzio-prosciutto-1961",
    1961,
    "030099",
    "https://prosciuttosandaniele.it/il-consorzio/il-consorzio/",
  ],
  [
    "san-daniele-prosciutto-dop-1996",
    1996,
    "030099",
    "https://prosciuttosandaniele.it/il-consorzio/il-consorzio/",
  ],
  [
    "staranzano-comune-amministrativo-1848",
    1848,
    "031023",
    "https://www.comune.staranzano.go.it/it/novita-76815/notizie-76816/staranzano-storia-e-territorio-del-paese-82839",
  ],
  [
    "staranzano-autonomia-comunale-1907",
    1907,
    "031023",
    "https://www.comune.staranzano.go.it/it/novita-76815/notizie-76816/staranzano-storia-e-territorio-del-paese-82839",
  ],
];
const EXPECTED_PROFILES = [
  ["030099", "San Daniele del Friuli", "UD", 1, 3, 2],
  ["031023", "Staranzano", "GO", 1, 3, 2],
];
const newIds = new Set(EXPECTED_FACTS.map(([id]) => id));
const candidates = research.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone San Daniele del Friuli and Staranzano enrichment", () => {
  it("keeps four source-verified facts in a hidden research snapshot", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      batchId: "ud-go-enrichment-milestones-02",
      snapshotDate: "2026-09-01",
      runtimeIntegration: false,
      initialTotalMilestones: 441,
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
      expect(["cultural_institution", "official_municipality"])
        .toContain(candidate.source.type);
      for (const source of [candidate.source, ...(candidate.supportingSources || [])]) {
        expect(new URL(source.url).protocol).toBe("https:");
        expect(source.checkedAt).toBe("2026-09-01");
      }
    }
  });

  it("preserves the 215-profile, 441-milestone baseline byte-for-byte", () => {
    const previousProfiles = municipalityProfiles.profiles.map((profile) => ({
      ...profile,
      milestones: profile.milestones.filter(({ id }) => (
        !newIds.has(id) && !udPn05Promotion.recordIds.includes(id)
          && !ud06Promotion.recordIds.includes(id)
          && !udPn07Promotion.recordIds.includes(id)
          && !pn08Promotion.recordIds.includes(id) && !ud09Promotion.recordIds.includes(id)
      )),
    }));
    expect(createHash("sha256").update(JSON.stringify(previousProfiles)).digest("hex"))
      .toBe("4b9a93f8a2dd34876be23e9c95aa8c9822fb73392f9a85079ef15904193ce43f");
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(previousProfiles.flatMap(({ milestones }) => milestones)).toHaveLength(441);
    expect(runtimeMilestones).toHaveLength(463);
    expect(new Set(runtimeMilestones.map(({ id }) => id))).toHaveProperty("size", 463);
  });

  it("moves both exact municipalities from one to three chronological facts", () => {
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

  it("keeps every claim inside the source evidence", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["san-daniele-consorzio-prosciutto-1961"].label.it)
      .not.toMatch(/nasce.*prosciutto|primo consorzio/iu);
    expect(byId["san-daniele-prosciutto-dop-1996"].label.it).toMatch(/DOP/u);
    expect(byId["staranzano-comune-amministrativo-1848"].label.it)
      .not.toMatch(/1817|1820/iu);
    expect(byId["staranzano-autonomia-comunale-1907"].label.it)
      .not.toMatch(/1867/iu);
    expect(research.excludedClaims).toHaveLength(4);
    expect(research.editorialOmissions).toContainEqual(expect.objectContaining({
      municipality: "San Daniele del Friuli",
      year: 1970,
      decision: "source_verified_not_promoted",
    }));
  });

  it("scopes assisted FUR approval and ARLeF references to the four IDs", () => {
    expect(review).toMatchObject({
      batchId: "ud-go-enrichment-milestones-02-fur-review",
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
      previousTotalMilestones: 441,
      resultingTotalMilestones: 445,
      addedMilestoneCounts: { "030099": 2, "031023": 2 },
      resultingMilestoneCounts: { "030099": 3, "031023": 3 },
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
    });
  }

  it("tracks the new batch while municipality work continues", () => {
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
    expect(backlog.researchProgress).toMatchObject({
      batchId: "ud-enrichment-milestones-09",
      municipalities: 3,
      sourceVerifiedCandidates: 3,
      promotedCandidates: 3,
      runtimeIntegration: false,
    });
    expect(backlog.previousResearchBatches.at(-1).batchId)
      .toBe("pn-enrichment-milestones-08");
    expect(editorialBacklog.executionPlan).toMatchObject({
      strategy: "municipality_first_editorial_batches",
      nextFocus: "municipality-historical-milestones",
    });
  });
});
