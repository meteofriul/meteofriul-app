import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import institutionalArchive from "../../data/discover/institutionalArchive.json";
import institutionalRituals from "../../data/discover/institutionalRituals.json";
import localMemory from "../../data/discover/localMemory.json";
import review from "../../data/discover/municipalityMilestoneFurReview.ud-go-pn-enrichment-02.json";
import promotion from "../../data/discover/municipalityMilestonePromotion.ud-go-pn-enrichment-02.json";
import laterPromotion from "../../data/discover/municipalityMilestonePromotion.ud-go-pn-enrichment-03.json";
import latestPromotion from "../../data/discover/municipalityMilestonePromotion.ud-go-pn-ts-enrichment-04.json";
import pn02Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-02.json";
import goTsPromotion from "../../data/discover/municipalityMilestonePromotion.go-ts-enrichment-01.json";
import udGo02Promotion from "../../data/discover/municipalityMilestonePromotion.ud-go-enrichment-02.json";
import udPn05Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-05.json";
import ud06Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-06.json";
import udPn07Promotion from "../../data/discover/municipalityMilestonePromotion.ud-pn-enrichment-07.json";
import pn08Promotion from "../../data/discover/municipalityMilestonePromotion.pn-enrichment-08.json";
import research from "../../data/discover/municipalityMilestoneResearch.ud-go-pn-enrichment-02.json";
import ud09Promotion from "../../data/discover/municipalityMilestonePromotion.ud-enrichment-09.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import ostermannRecords from "../../data/ostermannCulturalDiscover.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import { getMunicipalityProfile } from "./municipalityProfiles";

const EXPECTED_FACTS = [
  ["gemona-palazzo-comunale-1502", 1502, "030043", "https://www.visitgemona.com/feel/percorsi/passeggiata-in-centro/"],
  ["gemona-archivio-cinema-2008", 2008, "030043", "https://www.visitgemona.com/feel/arte-e-cultura/la-cineteca-del-friuli/"],
  ["grado-stazione-cura-1892", 1892, "031009", "https://grado.it/it/cosa-fare/arte-storia-e-cultura/la-storia-di-grado/grado-dal-1892"],
  ["grado-ponte-girevole-1936", 1936, "031009", "https://grado.it/it/cosa-fare/arte-storia-e-cultura/la-storia-di-grado/grado-dal-1892"],
  ["aviano-1615-santuario-madonna-del-monte", 1615, "093004", "https://diocesi.concordia-pordenone.it/santuario-diocesano-madonna-del-monte-in-costa-di-aviano/"],
  ["aviano-1971-festival-folklore-internazionale", 1971, "093004", "https://www.prolocoaviano.it/festival-del-folklore/"],
];
const EXPECTED_PROFILES = [
  ["030043", "Gemona del Friuli", "UD", "gemona-friuli-earthquake"],
  ["031009", "Grado", "GO", "grado-late-antique-castrum"],
  ["093004", "Aviano", "PN", "aviano-century-x"],
];
const newIds = new Set(EXPECTED_FACTS.map(([id]) => id));
const candidates = research.municipalities.flatMap((municipality) => (
  municipality.candidates.map((candidate) => ({ ...candidate, istatCode: municipality.istatCode }))
));
const runtimeMilestones = municipalityProfiles.profiles.flatMap(({ milestones }) => milestones);

describe("municipality milestone Gemona, Grado and Aviano enrichment", () => {
  it("keeps six facts in a non-runtime research snapshot with specific source evidence", () => {
    expect(research).toMatchObject({
      schemaVersion: 1, batchId: "ud-go-pn-enrichment-milestones-02",
      snapshotDate: "2026-08-31", runtimeIntegration: false, initialTotalMilestones: 421,
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
        expect(["official_municipality", "national_institution", "regional_institution", "cultural_institution"])
          .toContain(source.type);
        expect(new URL(source.url).protocol).toBe("https:");
        expect(source.label.trim()).toBeTruthy();
        expect(source.checkedAt).toBe("2026-08-31");
      }
    }
  });

  it("preserves all 215 prior profiles and 421 milestones byte-for-byte in their JSON model", () => {
    const previousProfiles = municipalityProfiles.profiles.map((profile) => ({
      ...profile, milestones: profile.milestones.filter(({ id }) => (
        !newIds.has(id) && !laterPromotion.recordIds.includes(id)
          && !latestPromotion.recordIds.includes(id) && !pn02Promotion.recordIds.includes(id)
          && !goTsPromotion.recordIds.includes(id) && !udGo02Promotion.recordIds.includes(id)
          && !udPn05Promotion.recordIds.includes(id) && !ud06Promotion.recordIds.includes(id)
          && !udPn07Promotion.recordIds.includes(id)
          && !pn08Promotion.recordIds.includes(id) && !ud09Promotion.recordIds.includes(id)
      )),
    }));
    expect(createHash("sha256").update(JSON.stringify(previousProfiles)).digest("hex"))
      .toBe("29875d96b14ed572ef67f903bff6ba677d69abb513bed21be2a36f9efada86be");
    expect(previousProfiles.flatMap(({ milestones }) => milestones)).toHaveLength(421);
    expect(municipalityProfiles.profiles).toHaveLength(215);
    expect(runtimeMilestones).toHaveLength(463);
    expect(new Set(runtimeMilestones.map(({ id }) => id)).size).toBe(463);
  });

  it("adds two facts per exact municipality without converting the old centuries into invented years", () => {
    expect(research.municipalities.map((municipality) => [
      municipality.istatCode, municipality.municipality, municipality.province, ...municipality.currentMilestoneIds,
    ])).toEqual(EXPECTED_PROFILES);
    for (const municipality of research.municipalities) {
      expect(municipality.currentMilestoneCount).toBe(1);
      expect(municipality.candidates).toHaveLength(2);
      const profile = municipalityProfiles.profiles.find(({ istatCode }) => istatCode === municipality.istatCode);
      expect(profile.milestones).toHaveLength(3);
      const years = profile.milestones.map(({ year }) => year).filter(Number.isInteger);
      expect(years).toEqual([...years].sort((a, b) => a - b));
    }
    expect(runtimeMilestones.find(({ id }) => id === "grado-late-antique-castrum"))
      .toMatchObject({ century: "VI" });
    expect(runtimeMilestones.find(({ id }) => id === "aviano-century-x"))
      .toMatchObject({ century: "X" });
    for (const id of ["grado-late-antique-castrum", "aviano-century-x"]) {
      expect(runtimeMilestones.find((record) => record.id === id).year).toBeUndefined();
    }
  });

  it("distinguishes work, archive opening, consecration and international activity from foundations", () => {
    const byId = Object.fromEntries(candidates.map((candidate) => [candidate.id, candidate]));
    expect(byId["gemona-palazzo-comunale-1502"].label.it).toBe("Cominciano i lavori per rifare il Palazzo Comunale");
    expect(byId["gemona-archivio-cinema-2008"].label.it).toBe("Si apre l’Archivio Cinema del Friuli Venezia Giulia");
    expect(byId["aviano-1615-santuario-madonna-del-monte"].label.it).toMatch(/^Consacrato il Santuario/);
    expect(byId["aviano-1971-festival-folklore-internazionale"].label.it)
      .toBe("Il Festival del Folklore diventa internazionale");
    expect(research.excludedClaims.some(({ reason }) => /1968/.test(reason) && /1969/.test(reason))).toBe(true);
  });

  it("does not turn the conflicting Grado bridge day or the newsreel date into a documented event date", () => {
    const bridge = candidates.find(({ id }) => id === "grado-ponte-girevole-1936");
    expect(bridge.year).toBe(1936);
    expect(bridge.documentedDate).toBeUndefined();
    expect(bridge.label.it).toMatch(/ponte girevole.*Grado.*terraferma/);
    expect(bridge.label.it).not.toMatch(/isolamento|primo collegamento|14|17/);
    expect(bridge.supportingSources.some(({ url }) => new URL(url).hostname.includes("archivioluce"))).toBe(true);
    expect(research.excludedClaims.some(({ reason }) => /1936/.test(reason) && /giugno/i.test(reason))).toBe(true);
    const datedCandidates = candidates.filter(({ documentedDate }) => documentedDate);
    expect(datedCandidates.map(({ id, documentedDate }) => [id, documentedDate]))
      .toEqual([["grado-stazione-cura-1892", "1892-06-25"]]);
  });

  it("scopes assisted FUR approval to six IDs without claiming certification or independent human review", () => {
    expect(review).toMatchObject({
      batchId: "ud-go-pn-enrichment-milestones-02-fur-review", sourceResearchBatchId: research.batchId,
      runtimeIntegration: false, reviewMethod: "assisted_standard_reference_review",
      approvalBasis: "user_delegated_assisted_editorial_review", reviewer: "assistant", independentHumanReview: false,
      summary: { totalRecords: 6, approved: 6, pendingHumanReview: 0 },
    });
    expect(review.records.map(({ id }) => id)).toEqual([...newIds]);
    for (const record of review.records) {
      expect(record.status).toBe("approved");
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
      batchId: research.batchId, approvalBasis: review.approvalBasis,
      independentHumanReview: false, recordIds: [...newIds],
    });
  });

  it("integrates exactly the reviewed labels and individual sources, not the staging copies", () => {
    expect(promotion).toMatchObject({
      researchBatchId: research.batchId, furReviewBatchId: review.batchId,
      approvalBasis: review.approvalBasis, independentHumanReview: false,
      totalRecords: 6, previousTotalMilestones: 421, resultingTotalMilestones: 427,
      addedMilestoneCounts: { "030043": 2, "031009": 2, "093004": 2 },
      resultingMilestoneCounts: { "030043": 3, "031009": 3, "093004": 3 }, recordIds: [...newIds],
    });
    for (const candidate of candidates) {
      const matches = runtimeMilestones.filter(({ id }) => id === candidate.id);
      const copy = review.records.find(({ id }) => id === candidate.id);
      expect(matches).toHaveLength(1);
      expect(matches[0]).toMatchObject({
        year: candidate.year, label: { it: candidate.label.it, fur: copy.labelFur }, source: candidate.source,
        languageReview: {
          it: { approvalBasis: review.approvalBasis },
          fur: { reviewBatchId: review.batchId, independentHumanReview: false },
        },
      });
      expect(matches[0].documentedDate).toBe(candidate.documentedDate);
      expect(matches[0].supportingSources || []).toEqual(candidate.supportingSources || []);
    }
    const otherRecords = [...localMemory.records, ...institutionalArchive, ...institutionalRituals, ...ostermannRecords];
    expect(otherRecords.some(({ id }) => newIds.has(id))).toBe(false);
  });

  for (const [istatCode, city] of EXPECTED_PROFILES) {
    it.each(["it", "fur"])(`renders all three ${city} facts in %s with their individual source models`, (language) => {
      const location = { city, istatCode };
      const profile = municipalityProfiles.profiles.find((record) => record.istatCode === istatCode);
      const card = getMunicipalityProfile({ language, location });
      const model = buildDiscoverViewModel({ language, location, today: "2028-08-31" });
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
      expect(getMunicipalityProfile({ language, location: { city: "Udine", istatCode } })).toEqual(card);
    });
  }

  it("keeps the completed batch in history after the next enrichment", () => {
    const backlog = editorialBacklog.records.find(({ id }) => id === "municipality-historical-milestones");
    expect(backlog.currentSnapshot).toMatchObject({
      municipalityProfiles: 215, totalMilestones: 463, profilesWithoutMilestones: 0,
      profilesWithOneMilestone: 83, profilesWithTwoMilestones: 16, profilesWithAtLeastThreeMilestones: 116,
    });
    expect(backlog.previousResearchBatches).toContainEqual(expect.objectContaining({
      batchId: research.batchId, municipalities: 3, sourceVerifiedCandidates: 6,
      promotedCandidates: 6, itDraftCandidates: 0, furDraftPendingReviewCandidates: 0,
    }));
    expect(research.initialTotalMilestones).toBe(promotion.previousTotalMilestones);
    expect(editorialBacklog.executionPlan.scope).toContain("ritual-calendar-breadth");
  });
});
