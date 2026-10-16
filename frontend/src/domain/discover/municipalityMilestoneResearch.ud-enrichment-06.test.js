import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import review from "../../data/discover/municipalityMilestoneFurReview.ud-enrichment-06.json";
import promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-06.json";
import udPn07Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-07.json";
import pn08Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-08.json";
import research from "../../data/discover/municipalityMilestoneResearch.ud-enrichment-06.json";
import ud09Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_FACTS = [
  [
    "lignano-first-bathing-establishment-1903",
    1903,
    "030049",
    "https://comune.lignano-sabbiadoro.ud.it/amministrazione/documenti-e-dati/amministrazione-trasparente/pianificazione-e-governo-del-territorio/varianti-al-prgc-1/variante-n-66-trasposizione-dello-strumento-urbanistico-su-nuovo-supporto-cartografico/relazione.pdf/@@download/file_principale",
  ],
  [
    "tolmezzo-torre-picotta-1477-1479",
    "1477-1479",
    "030121",
    "https://www.comune.tolmezzo.ud.it/localita-di-tolmezzo/",
  ],
  [
    "zuglio-first-systematic-forum-excavations",
    "inizio XIX",
    "030136",
    "https://patrimonioculturale.regione.fvg.it/museo/?s_id=440628",
  ],
];
const EXPECTED_PROFILES = [
  ["030049", "Lignano Sabbiadoro", "UD", [
    "lignano-first-bathing-establishment-1903",
    "lignano-pineta-spiral-plan",
    "lignano-municipal-autonomy",
  ]],
  ["030121", "Tolmezzo", "UD", [
    "tolmezzo-first-record",
    "tolmezzo-torre-picotta-1477-1479",
    "tolmezzo-linussio",
  ]],
  ["030136", "Zuglio", "UD", [
    "zuglio-iulium-carnicum",
    "zuglio-first-systematic-forum-excavations",
    "zuglio-museum",
  ]],
];
const newIds = new Set(EXPECTED_FACTS.map(([id]) => id));
const candidates = research.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone Lignano, Tolmezzo and Zuglio enrichment", () => {
  it("keeps three source-verified facts in a hidden research snapshot", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      batchId: "ud-enrichment-milestones-06",
      snapshotDate: "2026-09-01",
      runtimeIntegration: false,
      initialTotalMilestones: 451,
      editorialPolicy: {
        sourceEvidenceRequired: true,
        ambiguousDatesExcluded: true,
        readyForUi: false,
      },
    });
    expect(candidates.map(({ id, year, century, istatCode, source }) => [
      id,
      year ?? century,
      istatCode,
      source.url,
    ])).toEqual(EXPECTED_FACTS);
    expect(new Set(candidates.map(({ id }) => id))).toHaveProperty("size", 3);
    for (const candidate of candidates) {
      expect(candidate.label.it.trim()).toBeTruthy();
      expect(candidate.label.fur).toBeNull();
      expect(candidate.evidence.trim()).toBeTruthy();
      expect(candidate.duplicateReview).toMatchObject({ exactDuplicate: false });
      expect(candidate.duplicateReview.relatedRecordIds).toHaveLength(2);
      expect(["official_municipality", "regional_institution"])
        .toContain(candidate.source.type);
      for (const source of [candidate.source, ...(candidate.supportingSources || [])]) {
        expect(new URL(source.url).protocol).toBe("https:");
        expect(source.checkedAt).toBe("2026-09-01");
      }
    }
  });

  it("preserves the 215-profile, 451-milestone baseline byte-for-byte", () => {
    const previousProfiles = municipalityProfiles.profiles.map((profile) => ({
      ...profile,
      milestones: profile.milestones.filter(({ id }) => (
        !newIds.has(id) && !udPn07Promotion.recordIds.includes(id)
          && !pn08Promotion.recordIds.includes(id) && !ud09Promotion.recordIds.includes(id)
      )),
    }));
    expect(createHash("sha256").update(JSON.stringify(previousProfiles)).digest("hex"))
      .toBe("c2dc702e5c14103987d0652e39649ff95e5f9b87996de4f6416c944b3bd5f3d4");
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(previousProfiles.flatMap(({ milestones }) => milestones)).toHaveLength(451);
    expect(runtimeMilestones).toHaveLength(463);
    expect(new Set(runtimeMilestones.map(({ id }) => id))).toHaveProperty("size", 463);
  });

  it("moves the three exact municipalities from two to three ordered facts", () => {
    for (const [istatCode, city, province, expectedIds] of EXPECTED_PROFILES) {
      const municipality = research.municipalities.find((record) => record.istatCode === istatCode);
      const profile = municipalityProfiles.profiles.find((record) => record.istatCode === istatCode);
      expect(municipality).toMatchObject({
        municipality: city,
        province,
        currentMilestoneCount: 2,
      });
      expect(municipality.currentMilestoneIds).toHaveLength(2);
      expect(municipality.candidates).toHaveLength(1);
      expect(profile.milestones.map(({ id }) => id)).toEqual(expectedIds);
    }
  });

  it("keeps intervals when institutions do not provide one exact year", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["lignano-first-bathing-establishment-1903"]).toMatchObject({ year: 1903 });
    expect(byId["lignano-first-bathing-establishment-1903"].century).toBeUndefined();
    expect(byId["tolmezzo-torre-picotta-1477-1479"]).toMatchObject({ century: "1477-1479" });
    expect(byId["tolmezzo-torre-picotta-1477-1479"].year).toBeUndefined();
    expect(byId["zuglio-first-systematic-forum-excavations"])
      .toMatchObject({ century: "inizio XIX" });
    expect(byId["zuglio-first-systematic-forum-excavations"].year).toBeUndefined();
  });

  it("keeps every claim inside the documented scope", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["lignano-first-bathing-establishment-1903"].label.it)
      .not.toMatch(/apre|autonomia/iu);
    expect(byId["tolmezzo-torre-picotta-1477-1479"].label.it)
      .not.toMatch(/complet|respinge|battaglia/iu);
    expect(byId["zuglio-first-systematic-forum-excavations"].label.it)
      .toMatch(/primi scavi sistematici.*Foro/iu);
    expect(byId["zuglio-first-systematic-forum-excavations"].label.it)
      .not.toMatch(/1800/iu);
    expect(research.excludedClaims).toHaveLength(6);
    expect(research.editorialOmissions).toEqual(expect.arrayContaining([
      expect.objectContaining({ municipality: "Lignano Sabbiadoro", year: 1905, decision: "source_verified_not_promoted" }),
      expect.objectContaining({ municipality: "Tolmezzo", year: 1752, decision: "source_verified_not_promoted" }),
      expect.objectContaining({ municipality: "Zuglio", year: 1820, decision: "source_verified_not_promoted" }),
    ]));
  });

  it("scopes assisted FUR approval and ARLeF references to the three IDs", () => {
    expect(review).toMatchObject({
      batchId: "ud-enrichment-milestones-06-fur-review",
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
        expect(new URL(reference.url).hostname).toBe("superdizionari.arlef.it");
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
      previousTotalMilestones: 451,
      resultingTotalMilestones: 454,
      addedMilestoneCounts: { "030049": 1, "030121": 1, "030136": 1 },
      resultingMilestoneCounts: { "030049": 3, "030121": 3, "030136": 3 },
      recordIds: [...newIds],
    });
    for (const candidate of candidates) {
      const match = runtimeMilestones.find(({ id }) => id === candidate.id);
      const copy = review.records.find(({ id }) => id === candidate.id);
      expect(match).toMatchObject({
        label: { it: candidate.label.it, fur: copy.labelFur },
        source: candidate.source,
        languageReview: {
          it: { approvalBasis: review.approvalBasis },
          fur: { reviewBatchId: review.batchId, independentHumanReview: false },
        },
      });
      expect(match.year).toBe(candidate.year);
      expect(match.century).toBe(candidate.century);
      expect(match.supportingSources || []).toEqual(candidate.supportingSources || []);
    }
  });

  for (const [istatCode, city, , expectedIds] of EXPECTED_PROFILES) {
    it.each(["it", "fur"])(`renders all ${city} facts in %s without cross-location leakage`, (language) => {
      const location = { city, istatCode };
      const profile = municipalityProfiles.profiles.find((record) => record.istatCode === istatCode);
      const ownNewIds = profile.milestones.filter(({ id }) => newIds.has(id)).map(({ id }) => id);
      const card = getMunicipalityProfile({ language, location });
      const model = buildDiscoverViewModel({ language, location, today: "2028-09-01" });
      expect(model.focus).toMatchObject(card);
      expect(card.milestones).toHaveLength(3);
      expect(card.milestones.map(({ id }) => id)).toEqual(expectedIds);
      expect(ownNewIds).toHaveLength(1);
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
