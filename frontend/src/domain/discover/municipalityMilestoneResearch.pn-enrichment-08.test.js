import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import review from "../../data/discover/municipalityMilestoneFurReview.pn-enrichment-08.json";
import promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-08.json";
import research from "../../data/discover/municipalityMilestoneResearch.pn-enrichment-08.json";
import ud09Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_FACTS = [
  [
    "casarsa-academiuta-founded-1945",
    1945,
    "093010",
    "https://www.pasolinibibliografiafriulana.it/opere/academiuta-di-lenga-furlana_2728"
  ],
  [
    "montereale-archaeological-museum-opening-2011",
    2011,
    "093027",
    "https://museoarcheologicocividale.beniculturali.it/wp-content/uploads/2021/03/Forum-Iulii-XXXV-Notiziari.compressed.pdf"
  ],
  [
    "pinzano-pordenone-madonna-san-martino-1525",
    1525,
    "093030",
    "https://www.turismofvg.it/it/71917/chiesa-di-san-martino-vescovo"
  ]
];
const EXPECTED_PROFILES = [
  [
    "093010",
    "Casarsa della Delizia",
    "PN",
    [
      "casarsa-della-delizia-1942",
      "casarsa-della-delizia-1943",
      "casarsa-academiuta-founded-1945"
    ]
  ],
  [
    "093027",
    "Montereale Valcellina",
    "PN",
    [
      "montereale-valcellina-1905",
      "montereale-valcellina-2006",
      "montereale-archaeological-museum-opening-2011"
    ]
  ],
  [
    "093030",
    "Pinzano al Tagliamento",
    "PN",
    [
      "pinzano-pordenone-madonna-san-martino-1525",
      "pinzano-al-tagliamento-1906",
      "pinzano-al-tagliamento-1970"
    ]
  ]
];
const newIds = new Set(EXPECTED_FACTS.map(([id]) => id));
const candidates = research.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone Casarsa, Montereale and Pinzano enrichment", () => {
  it("keeps three source-verified facts in a hidden research snapshot", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      batchId: "pn-enrichment-milestones-08",
      snapshotDate: "2026-09-02",
      runtimeIntegration: false,
      initialTotalMilestones: 457,
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
      expect(["cultural_institution", "national_institution", "regional_institution"])
        .toContain(candidate.source.type);
      for (const source of [candidate.source, ...(candidate.supportingSources || [])]) {
        expect(new URL(source.url).protocol).toBe("https:");
        expect(source.checkedAt).toBe("2026-09-02");
      }
    }
  });

  it("preserves the 215-profile, 457-milestone baseline byte-for-byte", () => {
    const previousProfiles = municipalityProfiles.profiles.map((profile) => ({
      ...profile,
      milestones: profile.milestones.filter(({ id }) => !newIds.has(id) && !ud09Promotion.recordIds.includes(id)),
    }));
    expect(createHash("sha256").update(JSON.stringify(previousProfiles)).digest("hex"))
      .toBe("53e0b3f47edd861cb93209f2793207d4a241d6781a5bfbfc602a5382deab385e");
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(previousProfiles.flatMap(({ milestones }) => milestones)).toHaveLength(457);
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

  it("preserves the exact Academy date without inventing days for the other events", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["casarsa-academiuta-founded-1945"])
      .toMatchObject({ year: 1945, documentedDate: "1945-02-18" });
    expect(byId["montereale-archaeological-museum-opening-2011"])
      .toMatchObject({ year: 2011 });
    expect(byId["montereale-archaeological-museum-opening-2011"].evidence).toMatch(/marzo 2011/);
    expect(byId["montereale-archaeological-museum-opening-2011"].documentedDate).toBeUndefined();
    expect(byId["pinzano-pordenone-madonna-san-martino-1525"])
      .toMatchObject({ year: 1525 });
    expect(byId["pinzano-pordenone-madonna-san-martino-1525"].documentedDate).toBeUndefined();
  });

  it("keeps the Academy, archaeological museum and individual fresco distinct", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["casarsa-academiuta-founded-1945"].label.it)
      .toBe("A Versuta nasce l'Academiuta di lenga furlana");
    expect(byId["montereale-archaeological-museum-opening-2011"].label.it)
      .toMatch(/Museo archeologico/);
    expect(byId["montereale-archaeological-museum-opening-2011"].label.it)
      .not.toMatch(/energia|Pitter/iu);
    expect(byId["pinzano-pordenone-madonna-san-martino-1525"].label.it)
      .toMatch(/Madonna col Bambino nella chiesa di San Martino/);
    expect(byId["pinzano-pordenone-madonna-san-martino-1525"].label.it)
      .not.toMatch(/tutti|Valeriano|Battuti/iu);
    expect(research.excludedClaims).toHaveLength(6);
    expect(research.editorialOmissions).toEqual(expect.arrayContaining([
      expect.objectContaining({ municipality: "Casarsa della Delizia", year: 1945, decision: "source_verified_not_promoted" }),
      expect.objectContaining({ municipality: "Montereale Valcellina", year: 1991, decision: "source_verified_not_promoted" }),
      expect.objectContaining({ municipality: "Pinzano al Tagliamento", century: "XVIII", decision: "source_verified_not_promoted" }),
    ]));
  });

  it("scopes assisted FUR approval and ARLeF references to the three IDs", () => {
    expect(review).toMatchObject({
      batchId: "pn-enrichment-milestones-08-fur-review",
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
    expect(review.records.map(({ labelFur }) => labelFur)).toEqual([
      "A Versute e nas la Academiuta di lenga furlana",
      "Al ven inaugurât il Museu archeologjic di Montreâl",
      "Il Pordenone al piture la Madone cul Frutin te glesie di sant Martin",
    ]);
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
      previousTotalMilestones: 457,
      resultingTotalMilestones: 460,
      addedMilestoneCounts: { "093010": 1, "093027": 1, "093030": 1 },
      resultingMilestoneCounts: { "093010": 3, "093027": 3, "093030": 3 },
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
      expect(match.documentedDate).toBe(candidate.documentedDate);
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
      const model = buildDiscoverViewModel({ language, location, today: "2028-09-02" });
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
    expect(backlog.previousResearchBatches).toContainEqual(expect.objectContaining({
      batchId: research.batchId, promotedCandidates: 3,
    }));
    expect(backlog.previousResearchBatches.at(-1).batchId)
      .toBe("pn-enrichment-milestones-08");
    expect(editorialBacklog.executionPlan).toMatchObject({
      strategy: "municipality_first_editorial_batches",
      nextFocus: "municipality-historical-milestones",
    });
  });
});
