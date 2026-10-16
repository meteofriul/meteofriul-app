import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import review from "../../data/discover/municipalityMilestoneFurReview.ud-pn-enrichment-05.json";
import promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-05.json";
import ud06Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-06.json";
import udPn07Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-07.json";
import pn08Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-08.json";
import research from "../../data/discover/municipalityMilestoneResearch.ud-pn-enrichment-05.json";
import ud09Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_FACTS = [
  [
    "aiello-san-carlo-fair-1816",
    1816,
    "030001",
    "https://www.comune.aiellodelfriuli.ud.it/media/files/030001/attachment/Fiera_San_Carlo.pdf",
  ],
  [
    "aiello-joannis-aggregation-1931",
    1931,
    "030001",
    "https://lipari.istat.it/digibib/Censimenti%20popolazione/censpop1931/VolumeIIIFascicoliProvinciali/IST0005870Fasc26_UDINE%2BOCRottimizz.pdf",
  ],
  [
    "cividale-patriarch-callisto-seat-737",
    737,
    "030026",
    "https://comune.cividale-del-friuli.ud.it/media/files/md/030026/Elab.07_Relazione_illustrativa.pdf",
  ],
  [
    "cividale-archaeological-museum-founded-1817",
    1817,
    "030026",
    "https://cultura.gov.it/luogo/museo-archeologico-nazionale-di-cividale-del-friuli",
  ],
  [
    "san-quirino-incursion-church-fire-1499",
    1499,
    "093040",
    "https://siusa-archivi.cultura.gov.it/cgi-bin/siusa/pagina.pl?Chiave=6979&RicDimF=2&TipoPag=prodente",
  ],
  [
    "san-quirino-napoleonic-district-1807",
    1807,
    "093040",
    "https://siusa-archivi.cultura.gov.it/cgi-bin/siusa/pagina.pl?Chiave=9327&TipoPag=prodente",
  ],
];
const EXPECTED_PROFILES = [
  ["030001", "Aiello del Friuli", "UD", 1, 3, 2],
  ["030026", "Cividale del Friuli", "UD", 1, 3, 2],
  ["093040", "San Quirino", "PN", 1, 3, 2],
];
const newIds = new Set(EXPECTED_FACTS.map(([id]) => id));
const candidates = research.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone Aiello, Cividale and San Quirino enrichment", () => {
  it("keeps six source-verified facts in a hidden research snapshot", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      batchId: "ud-pn-enrichment-milestones-05",
      snapshotDate: "2026-09-01",
      runtimeIntegration: false,
      initialTotalMilestones: 445,
      editorialPolicy: {
        sourceEvidenceRequired: true,
        ambiguousDatesExcluded: true,
        readyForUi: false,
      },
    });
    expect(candidates.map(({ id, year, istatCode, source }) => [id, year, istatCode, source.url]))
      .toEqual(EXPECTED_FACTS);
    expect(new Set(candidates.map(({ id }) => id))).toHaveProperty("size", 6);
    for (const candidate of candidates) {
      expect(candidate.label.it.trim()).toBeTruthy();
      expect(candidate.label.fur).toBeNull();
      expect(candidate.evidence.trim()).toBeTruthy();
      expect(candidate.duplicateReview).toMatchObject({ exactDuplicate: false });
      expect(candidate.duplicateReview.relatedRecordIds.length).toBeGreaterThan(1);
      expect(["official_municipality", "national_institution"])
        .toContain(candidate.source.type);
      for (const source of [candidate.source, ...(candidate.supportingSources || [])]) {
        expect(new URL(source.url).protocol).toBe("https:");
        expect(source.checkedAt).toBe("2026-09-01");
      }
    }
  });

  it("preserves the 215-profile, 445-milestone baseline byte-for-byte", () => {
    const previousProfiles = municipalityProfiles.profiles.map((profile) => ({
      ...profile,
      milestones: profile.milestones.filter(({ id }) => (
        !newIds.has(id) && !ud06Promotion.recordIds.includes(id)
          && !udPn07Promotion.recordIds.includes(id)
          && !pn08Promotion.recordIds.includes(id) && !ud09Promotion.recordIds.includes(id)
      )),
    }));
    expect(createHash("sha256").update(JSON.stringify(previousProfiles)).digest("hex"))
      .toBe("5858d79e99edecd2dbe23f9c37af3c17efa7e43093a8cd192eeb898a5f0715d4");
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(previousProfiles.flatMap(({ milestones }) => milestones)).toHaveLength(445);
    expect(runtimeMilestones).toHaveLength(463);
    expect(new Set(runtimeMilestones.map(({ id }) => id))).toHaveProperty("size", 463);
  });

  it("moves all three exact municipalities from one to three chronological facts", () => {
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

  it("keeps exact dates only where the institutional source supplies them", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["aiello-joannis-aggregation-1931"].documentedDate).toBe("1931-05-18");
    expect(byId["san-quirino-incursion-church-fire-1499"].documentedDate).toBe("1499-09-30");
    for (const id of [
      "aiello-san-carlo-fair-1816",
      "cividale-patriarch-callisto-seat-737",
      "cividale-archaeological-museum-founded-1817",
      "san-quirino-napoleonic-district-1807",
    ]) {
      expect(byId[id].documentedDate).toBeUndefined();
    }
  });

  it("keeps every claim inside the documented scope", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["aiello-san-carlo-fair-1816"].label.it)
      .not.toMatch(/patron|ininterrott/iu);
    expect(byId["aiello-joannis-aggregation-1931"].label.it)
      .toMatch(/Comune.*soppresso.*aggregato/iu);
    expect(byId["cividale-patriarch-callisto-seat-737"].label.it)
      .not.toMatch(/da Aquileia/iu);
    expect(byId["cividale-archaeological-museum-founded-1817"].label.it)
      .not.toMatch(/nazionale/iu);
    expect(byId["san-quirino-incursion-church-fire-1499"].label.it)
      .not.toMatch(/vittim|distru(?:gge|zione) totale/iu);
    expect(byId["san-quirino-napoleonic-district-1807"].label.it)
      .not.toMatch(/nasce|fondat/iu);
    expect(research.excludedClaims).toHaveLength(7);
    expect(research.editorialOmissions).toHaveLength(4);
    expect(research.editorialOmissions).toEqual(expect.arrayContaining([
      expect.objectContaining({ municipality: "Cividale del Friuli", year: 1420, decision: "source_conflict_not_promoted" }),
      expect.objectContaining({ municipality: "Cividale del Friuli", year: 2011, decision: "source_verified_not_promoted" }),
    ]));
  });

  it("scopes assisted FUR approval and ARLeF references to the six IDs", () => {
    expect(review).toMatchObject({
      batchId: "ud-pn-enrichment-milestones-05-fur-review",
      sourceResearchBatchId: research.batchId,
      runtimeIntegration: false,
      reviewMethod: "assisted_standard_reference_review",
      approvalBasis: "user_delegated_assisted_editorial_review",
      reviewer: "assistant",
      independentHumanReview: false,
      summary: { totalRecords: 6, approved: 6, pendingHumanReview: 0 },
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

  it("promotes exactly the six reviewed labels with their individual sources", () => {
    expect(promotion).toMatchObject({
      researchBatchId: research.batchId,
      furReviewBatchId: review.batchId,
      totalRecords: 6,
      previousTotalMilestones: 445,
      resultingTotalMilestones: 451,
      addedMilestoneCounts: { "030001": 2, "030026": 2, "093040": 2 },
      resultingMilestoneCounts: { "030001": 3, "030026": 3, "093040": 3 },
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
      for (const foreignId of [...newIds].filter((id) => !ownNewIds.includes(id))) {
        expect(card.milestones.map(({ id }) => id)).not.toContain(foreignId);
      }
    });
  }

  it("keeps the completed batch in history while municipality work continues", () => {
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
      sourceVerifiedCandidates: 6,
      promotedCandidates: 6,
      runtimeIntegration: false,
    }));
    expect(backlog.researchProgress.batchId).toBe("ud-enrichment-milestones-09");
    expect(editorialBacklog.executionPlan).toMatchObject({
      strategy: "municipality_first_editorial_batches",
      nextFocus: "municipality-historical-milestones",
    });
  });
});
