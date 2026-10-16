import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import institutionalArchive from "../../data/discover/institutionalArchive.json";
import institutionalRituals from "../../data/discover/institutionalRituals.json";
import localMemory from "../../data/discover/localMemory.json";
import review from "../../data/discover/municipalityMilestoneFurReview.ud-go-pn-enrichment-03.json";
import promotion from "../../data/discover/municipalityMilestonePromotion.ud-go-pn-enrichment-03.json";
import laterPromotion from "../../data/discover/municipalityMilestonePromotion.ud-go-pn-ts-enrichment-04.json";
import pn02Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-02.json";
import goTsPromotion from "../../data/discover/municipalityMilestonePromotion.go-ts-enrichment-01.json";
import udGo02Promotion from "../../data/discover/municipalityMilestonePromotion.ud-go-enrichment-02.json";
import udPn05Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-05.json";
import ud06Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-06.json";
import udPn07Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-07.json";
import pn08Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-08.json";
import research from "../../data/discover/municipalityMilestoneResearch.ud-go-pn-enrichment-03.json";
import ud09Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import ostermannRecords from "../../data/ostermannCulturalDiscover.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_FACTS = [
  [
    "aquileia-unesco-inscription-1998",
    1998,
    "030004",
    "https://unesco.cultura.gov.it/projects/archaeological-area-and-the-patriarchal-basilica-of-aquileia/",
  ],
  [
    "gradisca-episcopal-seat-1788",
    1788,
    "031008",
    "https://www.comune.gradiscadisonzo.go.it/it/novita-232939/avvisi-232942/la-citta-48177",
  ],
  [
    "cordenons-1902-giardino-villa-raetz",
    1902,
    "093017",
    "https://patrimonioculturale.regione.fvg.it/parchi-e-giardini/?s_id=749704",
  ],
];
const EXPECTED_PROFILES = [
  ["030004", "Aquileia", "UD", "aquileia-roman-foundation", "aquileia-attila-sack"],
  ["031008", "Gradisca d'Isonzo", "GO", "gradisca-venetian-walls", "gradisca-habsburg-rule"],
  ["093017", "Cordenons", "PN", "cordenons-897", "cordenons-1814"],
];
const newIds = new Set(EXPECTED_FACTS.map(([id]) => id));
const candidates = research.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone Aquileia, Gradisca and Cordenons enrichment", () => {
  it("keeps three source-verified facts in a hidden research snapshot", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      batchId: "ud-go-pn-enrichment-milestones-03",
      snapshotDate: "2026-09-01",
      runtimeIntegration: false,
      initialTotalMilestones: 427,
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
      expect(candidate.documentedDate).toBeUndefined();
      expect(candidate.duplicateReview).toMatchObject({ exactDuplicate: false });
      expect(candidate.duplicateReview.note.trim()).toBeTruthy();
      for (const source of [candidate.source, ...(candidate.supportingSources || [])]) {
        expect([
          "official_municipality",
          "national_institution",
          "regional_institution",
          "cultural_institution",
          "international_institution",
        ]).toContain(source.type);
        expect(new URL(source.url).protocol).toBe("https:");
        expect(source.label.trim()).toBeTruthy();
        expect(source.checkedAt).toBe("2026-09-01");
      }
    }
  });

  it("preserves the 215-profile, 427-milestone baseline byte-for-byte", () => {
    const previousProfiles = municipalityProfiles.profiles.map((profile) => ({
      ...profile,
      milestones: profile.milestones.filter(({ id }) => (
        !newIds.has(id) && !laterPromotion.recordIds.includes(id)
          && !pn02Promotion.recordIds.includes(id) && !goTsPromotion.recordIds.includes(id)
          && !udGo02Promotion.recordIds.includes(id) && !udPn05Promotion.recordIds.includes(id)
          && !ud06Promotion.recordIds.includes(id)
          && !udPn07Promotion.recordIds.includes(id)
          && !pn08Promotion.recordIds.includes(id) && !ud09Promotion.recordIds.includes(id)
      )),
    }));
    expect(createHash("sha256").update(JSON.stringify(previousProfiles)).digest("hex"))
      .toBe("b71aeec4fbaeab24c29cf74a1147ceabd6e0421c42c425377cdd36e0716a3b98");
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(previousProfiles.flatMap(({ milestones }) => milestones)).toHaveLength(427);
    expect(runtimeMilestones).toHaveLength(463);
    expect(new Set(runtimeMilestones.map(({ id }) => id))).toHaveProperty("size", 463);
  });

  it("moves the three exact municipalities from two to three chronologically sorted milestones", () => {
    expect(research.municipalities.map((municipality) => [
      municipality.istatCode,
      municipality.municipality,
      municipality.province,
      ...municipality.currentMilestoneIds,
    ])).toEqual(EXPECTED_PROFILES);
    for (const municipality of research.municipalities) {
      expect(municipality.currentMilestoneCount).toBe(2);
      expect(municipality.candidates).toHaveLength(1);
      const profile = municipalityProfiles.profiles.find(({ istatCode }) => istatCode === municipality.istatCode);
      expect(profile.milestones).toHaveLength(3);
      const years = profile.milestones.map(({ year }) => year).filter(Number.isInteger);
      expect(years).toEqual([...years].sort((a, b) => a - b));
    }
  });

  it("keeps the three claims within the evidence and does not invent precise dates", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["aquileia-unesco-inscription-1998"].label.it)
      .toBe("L’area archeologica e la Basilica patriarcale entrano nel Patrimonio mondiale UNESCO");
    expect(byId["aquileia-unesco-inscription-1998"].label.it).not.toMatch(/fondazione|tutela|città/i);
    expect(byId["gradisca-episcopal-seat-1788"]).toMatchObject({
      year: 1788,
      label: { it: "Gradisca diventa sede vescovile", fur: null },
    });
    expect(byId["gradisca-episcopal-seat-1788"].evidence).toMatch(/1788.*1791/);
    expect(byId["gradisca-episcopal-seat-1788"].label.it).not.toMatch(/1647|1754/);
    expect(byId["cordenons-1902-giardino-villa-raetz"]).toMatchObject({
      year: 1902,
      label: { it: "Viene creato il giardino di Villa Raetz", fur: null },
    });
    expect(byId["cordenons-1902-giardino-villa-raetz"].label.it)
      .not.toMatch(/cotonificio|villa padronale|fondazione/i);
    const excludedByMunicipality = Object.fromEntries(
      research.excludedClaims.map((claim) => [claim.municipality, `${claim.claim} ${claim.reason}`]),
    );
    expect(excludedByMunicipality.Aquileia).toMatch(/non la fondazione|non.*fondazione/i);
    expect(excludedByMunicipality["Gradisca d'Isonzo"]).toMatch(/1647.*1754/);
    expect(excludedByMunicipality.Cordenons).toMatch(/disegno del giardino.*non estende/i);
  });

  it("scopes assisted FUR approval and ARLeF references to the three IDs", () => {
    expect(review).toMatchObject({
      batchId: "ud-go-pn-enrichment-milestones-03-fur-review",
      sourceResearchBatchId: research.batchId,
      runtimeIntegration: false,
      reviewMethod: "assisted_standard_reference_review",
      approvalBasis: "user_delegated_assisted_editorial_review",
      reviewer: "assistant",
      independentHumanReview: false,
      summary: { totalRecords: 3, approved: 3, pendingHumanReview: 0 },
    });
    expect(review.approvalNote).toMatch(/non certificano|non certificazione/i);
    expect(review.records.map(({ id }) => id)).toEqual([...newIds]);
    for (const record of review.records) {
      expect(record).toMatchObject({ status: "approved" });
      expect(record.labelFur.trim()).toBeTruthy();
      expect(record.notes.trim()).toBeTruthy();
      expect(record.references.length).toBeGreaterThan(0);
      for (const reference of record.references) {
        expect(["superdizionari.arlef.it", "arlef.it"]).toContain(new URL(reference.url).hostname);
        expect(reference.note.trim()).toBeTruthy();
      }
    }
    expect(municipalityProfiles.editorialPolicy.furRequiresHumanReview).toBe(true);
    expect(municipalityProfiles.editorialPolicy.furAssistedReviewExceptions).toContainEqual({
      batchId: research.batchId,
      approvalBasis: review.approvalBasis,
      independentHumanReview: false,
      recordIds: [...newIds],
    });
  });

  it("promotes exactly three reviewed labels with their individual source models", () => {
    expect(promotion).toMatchObject({
      researchBatchId: research.batchId,
      furReviewBatchId: review.batchId,
      approvalBasis: review.approvalBasis,
      independentHumanReview: false,
      totalRecords: 3,
      previousTotalMilestones: 427,
      resultingTotalMilestones: 430,
      addedMilestoneCounts: { "030004": 1, "031008": 1, "093017": 1 },
      resultingMilestoneCounts: { "030004": 3, "031008": 3, "093017": 3 },
      recordIds: [...newIds],
    });
    for (const candidate of candidates) {
      const matches = runtimeMilestones.filter(({ id }) => id === candidate.id);
      const copy = review.records.find(({ id }) => id === candidate.id);
      expect(matches).toHaveLength(1);
      expect(matches[0]).toMatchObject({
        year: candidate.year,
        label: { it: candidate.label.it, fur: copy.labelFur },
        source: candidate.source,
        languageReview: {
          it: { approvalBasis: review.approvalBasis },
          fur: { reviewBatchId: review.batchId, independentHumanReview: false },
        },
      });
      expect(Object.hasOwn(matches[0], "source")).toBe(true);
      expect(matches[0].documentedDate).toBeUndefined();
      expect(matches[0].supportingSources || []).toEqual(candidate.supportingSources || []);
    }
    const otherRecords = [...localMemory.records, ...institutionalArchive, ...institutionalRituals, ...ostermannRecords];
    expect(otherRecords.some(({ id }) => newIds.has(id))).toBe(false);
  });

  for (const [istatCode, city] of EXPECTED_PROFILES) {
    it.each(["it", "fur"])(`renders all three ${city} facts in %s without cross-location leakage`, (language) => {
      const location = { city, istatCode };
      const profile = municipalityProfiles.profiles.find((record) => record.istatCode === istatCode);
      const profileIds = new Set(profile.milestones.map(({ id }) => id));
      const card = getMunicipalityProfile({ language, location });
      const model = buildDiscoverViewModel({ language, location, today: "2028-09-01" });
      expect(model.focus).toMatchObject(card);
      expect(card.milestones).toHaveLength(3);
      expect(card.milestones.map(({ id }) => id)).toEqual(profile.milestones.map(({ id }) => id));
      expect([...newIds].filter((id) => profileIds.has(id))).toHaveLength(1);
      const html = renderToStaticMarkup(createElement(DiscoverCard, {
        card: model.focus,
        municipalityMilestonesTitle: model.copy.municipalityMilestonesTitle,
      }));
      for (const milestone of profile.milestones) {
        const visible = card.milestones.find(({ id }) => id === milestone.id);
        expect(visible).toMatchObject({
          label: milestone.label[language],
          source: milestone.source || profile.source,
          supportingSources: milestone.supportingSources || [],
        });
        expect(html).toContain(renderToStaticMarkup(createElement("span", null, visible.label)));
        expect(html).toContain(renderToStaticMarkup(createElement("time", null, visible.period)));
      }
      for (const foreignId of [...newIds].filter((id) => !profileIds.has(id))) {
        expect(card.milestones.some(({ id }) => id === foreignId)).toBe(false);
      }
      expect(getMunicipalityProfile({ language, location: { city: "Udine", istatCode } })).toEqual(card);
    });
  }

  it("keeps the completed batch in history after the next enrichment", () => {
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
      municipalities: 3,
      sourceVerifiedCandidates: 3,
      promotedCandidates: 3,
      itDraftCandidates: 0,
      furDraftPendingReviewCandidates: 0,
    }));
    expect(research.initialTotalMilestones).toBe(promotion.previousTotalMilestones);
    expect(editorialBacklog.executionPlan.scope).toContain("ritual-calendar-breadth");
  });
});
