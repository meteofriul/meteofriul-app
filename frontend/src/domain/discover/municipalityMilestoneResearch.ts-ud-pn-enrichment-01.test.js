import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import institutionalArchive from "../../data/discover/institutionalArchive.json";
import institutionalRituals from "../../data/discover/institutionalRituals.json";
import localMemory from "../../data/discover/localMemory.json";
import milestoneFurReview from "../../data/discover/municipalityMilestoneFurReview.ts-ud-pn-enrichment-01.json";
import milestonePromotion from "../../data/discover/municipalityMilestonePromotion.ts-ud-pn-enrichment-01.json";
import milestoneResearch from "../../data/discover/municipalityMilestoneResearch.ts-ud-pn-enrichment-01.json";
import laterPromotion from "../../data/discover/municipalityMilestonePromotion.ud-go-pn-enrichment-02.json";
import newestPromotion from "../../data/discover/municipalityMilestonePromotion.ud-go-pn-enrichment-03.json";
import latestPromotion from "../../data/discover/municipalityMilestonePromotion.ud-go-pn-ts-enrichment-04.json";
import pn02Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-02.json";
import goTsPromotion from "../../data/discover/municipalityMilestonePromotion.go-ts-enrichment-01.json";
import udGo02Promotion from "../../data/discover/municipalityMilestonePromotion.ud-go-enrichment-02.json";
import udPn05Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-05.json";
import ud06Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-06.json";
import udPn07Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-07.json";
import pn08Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-08.json";
import ud09Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import ostermannRecords from "../../data/ostermannCulturalDiscover.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_FACTS = [
  ["muggia-venetian-sovereignty", 1420, "032003", "https://siusa-archivi.cultura.gov.it/cgi-bin/siusa/pagina.pl?Chiave=9188&TipoPag=prodente"],
  ["muggia-ugo-cara-museum-opening", 2006, "032003", "https://patrimonioculturale.regione.fvg.it/museo/?s_id=440670"],
  ["artegna-castello-savorgnan-1384", 1384, "030006", "https://sabapfvg.cultura.gov.it/artegna/"],
  ["artegna-banda-mattiussi-1878", 1878, "030006", "https://www.anbimafvg.it/index.php/2018/03/31/artegna/"],
  ["san-vito-al-tagliamento-1369-ospedale-battuti", 1369, "093041", "https://guidartefvg.it/elenco/la-chiesa-dei-battuti-san-vito-al-tagliamento/"],
  ["san-vito-al-tagliamento-1973-circuito-ert", 1973, "093041", "https://ertfvg.it/teatri/san-vito-al-tagliamento/"],
];
const EXPECTED_PROFILES = [
  ["032003", "Muggia", "TS", "muggia-medieval-municipality"],
  ["030006", "Artegna", "UD", "artegna-san-martino-inscription"],
  ["093041", "San Vito al Tagliamento", "PN", "san-vito-al-tagliamento-1420"],
];
const newIds = new Set(EXPECTED_FACTS.map(([id]) => id));
const candidates = milestoneResearch.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone TS/UD/PN enrichment", () => {
  it("keeps six specific source facts in a non-runtime research snapshot", () => {
    expect(milestoneResearch).toMatchObject({
      schemaVersion: 1,
      batchId: "ts-ud-pn-enrichment-milestones-01",
      snapshotDate: "2026-08-31",
      runtimeIntegration: false,
      initialTotalMilestones: 415,
      editorialPolicy: { sourceEvidenceRequired: true, ambiguousDatesExcluded: true, readyForUi: false },
    });
    expect(candidates.map(({ id, year, istatCode, source }) => [id, year, istatCode, source.url]))
      .toEqual(EXPECTED_FACTS);
    expect(new Set(candidates.map(({ id }) => id)).size).toBe(6);
    for (const candidate of candidates) {
      expect(candidate.label.it.trim()).toBeTruthy();
      expect(candidate.label.fur).toBeNull();
      expect(candidate.evidence.trim()).toBeTruthy();
      expect(candidate.duplicateReview).toMatchObject({ exactDuplicate: false });
      expect(candidate.duplicateReview.note.trim()).toBeTruthy();
      for (const source of [candidate.source, ...(candidate.supportingSources || [])]) {
        expect(["national_institution", "regional_institution", "cultural_institution"]).toContain(source.type);
        expect(new URL(source.url).protocol).toBe("https:");
        expect(source.label.trim()).toBeTruthy();
        expect(source.checkedAt).toBe("2026-08-31");
      }
    }
  });

  it("preserves all 215 prior profiles, including existing text, dates and source metadata", () => {
    // Reconstruct this historical snapshot without rewriting its original digest.
    const addedSinceSnapshot = new Set([
      ...newIds, ...laterPromotion.recordIds, ...newestPromotion.recordIds, ...latestPromotion.recordIds,
      ...pn02Promotion.recordIds, ...goTsPromotion.recordIds, ...udGo02Promotion.recordIds,
      ...udPn05Promotion.recordIds, ...ud06Promotion.recordIds, ...udPn07Promotion.recordIds, ...pn08Promotion.recordIds, ...ud09Promotion.recordIds,
    ]);
    const withoutNewMilestones = municipalityProfiles.profiles.map((profile) => ({
      ...profile, milestones: profile.milestones.filter(({ id }) => !addedSinceSnapshot.has(id)),
    }));
    expect(createHash("sha256").update(JSON.stringify(withoutNewMilestones)).digest("hex"))
      .toBe("aa49209bdba6b16d738ec5bba61c9a79fb198aa400ed5d7f43e035fb88163ce7");
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(runtimeMilestones).toHaveLength(463);
    expect(new Set(runtimeMilestones.map(({ id }) => id)).size).toBe(463);
  });

  it("adds two milestones to each exact municipality, without inventing a numeric date for Muggia's century", () => {
    expect(milestoneResearch.municipalities.map((municipality) => [
      municipality.istatCode, municipality.municipality, municipality.province, ...municipality.currentMilestoneIds,
    ])).toEqual(EXPECTED_PROFILES);
    for (const municipality of milestoneResearch.municipalities) {
      expect(municipality.currentMilestoneCount).toBe(1);
      expect(municipality.candidates).toHaveLength(2);
      const profile = municipalityProfiles.profiles.find(({ istatCode }) => istatCode === municipality.istatCode);
      expect(profile.milestones).toHaveLength(3);
      const years = profile.milestones.map(({ year }) => year).filter(Number.isInteger);
      expect(years).toEqual([...years].sort((a, b) => a - b));
    }
    const muggia = municipalityProfiles.profiles.find(({ istatCode }) => istatCode === "032003");
    expect(muggia.milestones[0]).toMatchObject({ id: "muggia-medieval-municipality", century: "XIII" });
    expect(muggia.milestones[0].year).toBeUndefined();
    const artegna = municipalityProfiles.profiles.find(({ istatCode }) => istatCode === "030006");
    expect(artegna.milestones[0]).toMatchObject({ id: "artegna-san-martino-inscription", year: 1005 });
  });

  it("does not confuse attestations, ownership changes or ERT activity with foundations", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["muggia-venetian-sovereignty"].label.it).toMatch(/sovranità.*Venezia/);
    expect(byId["muggia-ugo-cara-museum-opening"].label.it).toMatch(/inaugurato.*Museo.*Ugo Carà/);
    expect(byId["artegna-castello-savorgnan-1384"].label.it).toBe("Il castello inferiore passa alla famiglia Savorgnan");
    expect(byId["artegna-banda-mattiussi-1878"].label.it).toMatch(/Nasce la banda musicale.*guidata da Luigi Mattiussi/);
    expect(byId["artegna-banda-mattiussi-1878"].label.it).not.toMatch(/intitolata|denominata/);
    expect(byId["san-vito-al-tagliamento-1369-ospedale-battuti"].label.it).toBe("È documentato l’Ospedale dei Battuti");
    expect(byId["san-vito-al-tagliamento-1973-circuito-ert"]).toMatchObject({
      documentedDate: "1973-03-21", label: { it: "Primo spettacolo ERT al Teatro Cinema Italia" },
    });
  });

  it("scopes assisted FUR approval to these six IDs without changing the human-review policy", () => {
    expect(milestoneFurReview).toMatchObject({
      batchId: "ts-ud-pn-enrichment-milestones-01-fur-review",
      sourceResearchBatchId: milestoneResearch.batchId,
      runtimeIntegration: false,
      reviewMethod: "assisted_standard_reference_review",
      approvalBasis: "user_delegated_assisted_editorial_review",
      reviewer: "assistant", independentHumanReview: false,
      summary: { totalRecords: 6, approved: 6, pendingHumanReview: 0 },
    });
    expect(milestoneFurReview.records.map(({ id }) => id)).toEqual([...newIds]);
    for (const review of milestoneFurReview.records) {
      expect(review.status).toBe("approved");
      expect(review.labelFur.trim()).toBeTruthy();
      expect(review.notes.trim()).toBeTruthy();
      expect(review.references.length).toBeGreaterThan(0);
      for (const reference of review.references) {
        expect(["superdizionari.arlef.it", "arlef.it"]).toContain(new URL(reference.url).hostname);
        expect(reference.note.trim()).toBeTruthy();
      }
    }
    expect(municipalityProfiles.editorialPolicy.furRequiresHumanReview).toBe(true);
    expect(municipalityProfiles.editorialPolicy.furAssistedReviewExceptions).toContainEqual({
      batchId: milestoneResearch.batchId, approvalBasis: milestoneFurReview.approvalBasis,
      independentHumanReview: false, recordIds: [...newIds],
    });
  });

  it("promotes exactly six entries with their reviewed copy and individual sources", () => {
    expect(milestonePromotion).toMatchObject({
      researchBatchId: milestoneResearch.batchId, furReviewBatchId: milestoneFurReview.batchId,
      approvalBasis: milestoneFurReview.approvalBasis, independentHumanReview: false,
      totalRecords: 6, previousTotalMilestones: 415, resultingTotalMilestones: 421,
      addedMilestoneCounts: { "032003": 2, "030006": 2, "093041": 2 },
      resultingMilestoneCounts: { "032003": 3, "030006": 3, "093041": 3 },
      recordIds: [...newIds],
    });
    for (const candidate of candidates) {
      const matches = runtimeMilestones.filter(({ id }) => id === candidate.id);
      const review = milestoneFurReview.records.find(({ id }) => id === candidate.id);
      expect(matches).toHaveLength(1);
      expect(matches[0]).toMatchObject({
        year: candidate.year, label: { it: candidate.label.it, fur: review.labelFur },
        source: candidate.source,
        languageReview: {
          it: { approvalBasis: milestoneFurReview.approvalBasis },
          fur: { reviewBatchId: milestoneFurReview.batchId, independentHumanReview: false },
        },
      });
      expect(matches[0].documentedDate).toBe(candidate.documentedDate);
      expect(matches[0].supportingSources || []).toEqual(candidate.supportingSources || []);
    }
    const otherRecords = [...localMemory.records, ...institutionalArchive, ...institutionalRituals, ...ostermannRecords];
    expect(otherRecords.some(({ id }) => newIds.has(id))).toBe(false);
  });

  for (const [istatCode, city] of EXPECTED_PROFILES) {
    it.each(["it", "fur"])(`renders all three ${city} milestones in %s with their correct source model`, (language) => {
      const location = { city, istatCode };
      const profile = municipalityProfiles.profiles.find((record) => record.istatCode === istatCode);
      const model = buildDiscoverViewModel({ language, location, today: "2028-08-31" });
      const card = getMunicipalityProfile({ language, location });
      expect(model.focus).toMatchObject(card);
      expect(card.milestones).toHaveLength(3);
      const html = renderToStaticMarkup(createElement(DiscoverCard, {
        card: model.focus, municipalityMilestonesTitle: model.copy.municipalityMilestonesTitle,
      }));
      for (const milestone of profile.milestones) {
        const visible = card.milestones.find(({ id }) => id === milestone.id);
        expect(visible).toMatchObject({
          label: milestone.label[language], source: milestone.source || profile.source,
          supportingSources: milestone.supportingSources || [],
        });
        expect(html).toContain(renderToStaticMarkup(createElement("span", null, visible.label)));
        expect(html).toContain(renderToStaticMarkup(createElement("time", null, visible.period)));
      }
      if (istatCode === "032003") {
        expect(card.milestones[0].period).toBe(language === "it" ? "13° sec." : "Secul 13");
      }
      expect(getMunicipalityProfile({ language, location: { city: "Udine", istatCode } })).toEqual(card);
    });
  }

  it("keeps current backlog counts distinct from the earlier promotion snapshots", () => {
    const backlog = editorialBacklog.records.find(({ id }) => id === "municipality-historical-milestones");
    expect(backlog.currentSnapshot).toMatchObject({
      municipalityProfiles: 215, totalMilestones: runtimeMilestones.length, profilesWithoutMilestones: 0,
      profilesWithOneMilestone: municipalityProfiles.profiles.filter(({ milestones }) => milestones.length === 1).length,
      profilesWithTwoMilestones: municipalityProfiles.profiles.filter(({ milestones }) => milestones.length === 2).length,
      profilesWithAtLeastThreeMilestones: municipalityProfiles.profiles.filter(({ milestones }) => milestones.length >= 3).length,
    });
    expect(backlog.previousResearchBatches.find(({ batchId }) => batchId === milestoneResearch.batchId)).toMatchObject({
      batchId: milestoneResearch.batchId, municipalities: 3, sourceVerifiedCandidates: 6,
      promotedCandidates: 6, itDraftCandidates: 0, furDraftPendingReviewCandidates: 0,
    });
    expect(backlog.previousResearchBatches.map(({ batchId }) => batchId)).toEqual([
      "pn-enrichment-milestones-01", "ud-go-enrichment-milestones-01", milestoneResearch.batchId,
      "ud-go-pn-enrichment-milestones-02", "ud-go-pn-enrichment-milestones-03",
      "ud-go-pn-ts-enrichment-milestones-04", "pn-enrichment-milestones-02",
      "go-ts-enrichment-milestones-01", "ud-go-enrichment-milestones-02",
      "ud-pn-enrichment-milestones-05",
      "ud-enrichment-milestones-06",
      "ud-pn-enrichment-milestones-07",
      "pn-enrichment-milestones-08",
    ]);
    expect(milestoneResearch.initialTotalMilestones).toBe(milestonePromotion.previousTotalMilestones);
  });
});
