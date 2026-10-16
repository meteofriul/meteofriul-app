import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import review from "../../data/discover/municipalityMilestoneFurReview.ud-enrichment-09.json";
import promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import research from "../../data/discover/municipalityMilestoneResearch.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_FACTS = [
  [
    "magnano-prampero-document-1107",
    1107,
    "030052",
    "https://consorziocastelli.it/biblioteca/pubblicazioni/notiziario/anno-2006/107.pdf"
  ],
  [
    "taipana-platischis-renaming-decree-1931",
    1931,
    "030113",
    "https://www.gazzettaufficiale.it/eli/id/1931/11/21/031U1382/sg"
  ],
  [
    "tavagnacco-fuluto-madonna-cavalicco-1512",
    1512,
    "030118",
    "https://agenda.comune.tavagnacco.ud.it/Luoghi/Chiesa-antica-di-Cavalicco"
  ]
];
const EXPECTED_PROFILES = [
  [
    "030052",
    "Magnano in Riviera",
    "UD",
    [
      "magnano-prampero-document-1107",
      "magnano-comune-1827",
      "magnano-afro-prampero-1961"
    ]
  ],
  [
    "030113",
    "Taipana",
    "UD",
    [
      "taipana-slavic-settlement",
      "taipana-italy",
      "taipana-platischis-renaming-decree-1931"
    ]
  ],
  [
    "030118",
    "Tavagnacco",
    "UD",
    [
      "tavagnacco-fuluto-madonna-cavalicco-1512",
      "tavagnacco-aggregations",
      "tavagnacco-pagnacco-restored"
    ]
  ]
];
const newIds = new Set(EXPECTED_FACTS.map(([id]) => id));
const candidates = research.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone Magnano, Taipana and Tavagnacco enrichment", () => {
  it("keeps three source-verified facts in a hidden research snapshot", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      batchId: "ud-enrichment-milestones-09",
      snapshotDate: "2026-09-02",
      runtimeIntegration: false,
      initialTotalMilestones: 460,
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
      expect(["cultural_institution", "national_institution", "official_municipality"])
        .toContain(candidate.source.type);
      for (const source of [candidate.source, ...(candidate.supportingSources || [])]) {
        expect(new URL(source.url).protocol).toBe("https:");
        expect(source.checkedAt).toBe("2026-09-02");
      }
    }
  });

  it("preserves the 215-profile, 460-milestone baseline byte-for-byte", () => {
    const previousProfiles = municipalityProfiles.profiles.map((profile) => ({
      ...profile,
      milestones: profile.milestones.filter(({ id }) => !newIds.has(id)),
    }));
    expect(createHash("sha256").update(JSON.stringify(previousProfiles)).digest("hex"))
      .toBe("5622265a21acd1996e195304e1e02a5af888769dcc7c7b33b16c50a00c3f3d27");
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(previousProfiles.flatMap(({ milestones }) => milestones)).toHaveLength(460);
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

  it("separates documentary dates, decree stages and the dated fresco", () => {
    const [prampero, taipana, cavalicco] = candidates;
    expect(prampero).toMatchObject({ year: 1107 });
    expect(prampero.label.it).toBe("Il castello di Prampero è documentato per iscritto");
    expect(prampero.label.it).not.toMatch(/fondato|costruito|prima/iu);
    expect(prampero.verificationNote).toMatch(/ud-zero-milestones-03/);
    expect(taipana).toMatchObject({ year: 1931 });
    expect(taipana.label.it).toBe("Il Comune di Platischis viene autorizzato a chiamarsi Taipana");
    expect(taipana.evidence).toMatch(/15 ottobre 1931/);
    expect(taipana.evidence).toMatch(/21 novembre 1931/);
    expect(taipana.evidence).toMatch(/6 dicembre 1931/);
    expect(cavalicco).toMatchObject({ year: 1512 });
    expect(cavalicco.label.it).toBe("Pietro Fuluto dipinge la Madonna in trono a Cavalicco");
    for (const candidate of candidates) expect(candidate.documentedDate).toBeUndefined();
  });

  it("keeps excluded claims and verified omissions outside the three promoted facts", () => {
    expect(research.excludedClaims).toHaveLength(6);
    expect(research.editorialOmissions).toEqual(expect.arrayContaining([
      expect.objectContaining({ municipality: "Magnano in Riviera", year: 1131, decision: "source_verified_not_promoted" }),
      expect.objectContaining({ municipality: "Taipana", year: 1930, decision: "source_verified_not_promoted" }),
      expect.objectContaining({ municipality: "Tavagnacco", year: 1261, decision: "source_verified_not_promoted" }),
    ]));
    expect(candidates.map(({ year }) => year)).not.toContain(1025);
    expect(candidates.map(({ year }) => year)).not.toContain(1506);
    expect(candidates[2].label.it).not.toMatch(/tutti|Osais/iu);
  });

  it("scopes assisted FUR approval and ARLeF references to the three IDs", () => {
    expect(review).toMatchObject({
      batchId: "ud-enrichment-milestones-09-fur-review",
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
      "Il cjistiel di Prampar al è documentât par scrit",
      "Il Comun di Platiscjis al ven autorizât a clamâsi Taipane",
      "Pietro Fuluto al piture la Madone in tron a Cjavalì"
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
      previousTotalMilestones: 460,
      resultingTotalMilestones: 463,
      addedMilestoneCounts: { "030052": 1, "030113": 1, "030118": 1 },
      resultingMilestoneCounts: { "030052": 3, "030113": 3, "030118": 3 },
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
      batchId: research.batchId,
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
