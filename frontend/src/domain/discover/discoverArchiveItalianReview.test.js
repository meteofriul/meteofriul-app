import { describe, expect, it } from "vitest";

import archiveResearchWave01 from "../../data/discover/archiveResearchWave01.json";
import archiveResearchWave02 from "../../data/discover/archiveResearchWave02.json";
import culturalRecords from "./discoverCulturalRecords";
import {
  isCuratedDiscoverPublished,
  isCuratedDiscoverUiReady,
} from "./discoverCulturalReadiness";

const REVIEWED_IDS = [
  "archive-research-bacio-croci-zuglio",
  "archive-research-maj-lucinico",
  "archive-research-cramars-carnia",
  "archive-research-osmiza-frasco",
  "archive-research-toco-marano",
  "archive-research-mulini-risorgive",
  "archive-research-animali-nomi-campanacci",
  "archive-research-pettini-osso-andreis",
  "archive-research-bucato-ranno",
  "archive-research-ago-osso-prosciutto",
];
const records = [...archiveResearchWave01.records, ...archiveResearchWave02.records];
const reviewed = records.filter((record) => record.itCopyReview);
const byId = new Map(reviewed.map((record) => [record.id, record]));

describe("discover archive Italian copy review", () => {
  it("preserves the completed Italian copy and traces the separate explicit approval", () => {
    expect(reviewed.map((record) => record.id)).toEqual(REVIEWED_IDS);
    reviewed.forEach((record) => {
      expect(record).toMatchObject({
        reviewStatus: "promoted",
        editorialStatus: "promoted_to_catalog",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: false,
      });
      [record.title.it, record.draftCopy.it, record.draftAppShort.it].forEach((copy) => {
        expect(copy.trim().length).toBeGreaterThan(8);
      });
      expect(record.draftAppShort.it.length).toBeLessThanOrEqual(140);
      expect(record.draftCopy.it.length).toBeLessThanOrEqual(420);
      expect(record.promotionReview).toMatchObject({
        decision: "promoted",
        promotedAt: "2026-08-31",
        targetSection: "archivio_tradizioni",
        remainingBlockers: [],
      });
      expect(record.languageReview.fur).toMatchObject({
        approvalBasis: "user_explicit_assisted_review_approval",
        reviewMethod: "assisted_standard_reference_review",
        approvedAt: "2026-08-31",
      });
    });
  });

  it("preserves the Italian review snapshot separately from later integration metadata", () => {
    reviewed.forEach((record) => {
      expect(record.source.checkedAt).toBe("2026-08-28");
      expect(record.itCopyReview).toMatchObject({
        batchId: "archive-it-review-2026-08-30-01",
        reviewedAt: "2026-08-30",
        sourceRecheckedAt: "2026-08-30",
        method: "assisted_primary_source_review",
        status: "approved_for_fur_drafting",
        reviewDocument: "docs/operations/SCOPRI_IT_REVIEW_2026-08-30.md",
      });
      expect(record.itCopyReview.references.length).toBeGreaterThan(0);
      expect(record.itCopyReview.references[0].url).toBe(record.source.url);
      record.itCopyReview.references.forEach((reference) => {
        expect(reference.url).toMatch(/^https:\/\//);
        expect(reference.note.trim()).not.toBe("");
      });
      expect(record.itCopyReview.notes.length).toBeGreaterThan(0);
      expect(record.itCopyReview.remainingWork).toEqual(expect.arrayContaining([
        "fur_draft",
        "fur_human_review",
        "calendar_and_duplicate_audit",
      ]));
    });
  });

  it("keeps the research copies hidden while their separate catalog identities are active", () => {
    const activeIdentities = new Set(culturalRecords.flatMap((record) => [
      record.id,
      record.sourceId,
      record.candidateId,
      record.canonicalKey,
    ]).filter(Boolean));

    reviewed.forEach((record) => {
      expect(activeIdentities.has(record.id)).toBe(true);
      expect(activeIdentities.has(record.canonicalKey)).toBe(true);
      expect(activeIdentities.has(record.promotionReview.targetRecordId)).toBe(true);
      expect(culturalRecords.some((active) => active.id === record.id)).toBe(false);
      [record, { ...record, readyForUi: true }, { ...record, readyForUi: undefined }]
        .forEach((candidate) => {
          expect(isCuratedDiscoverUiReady(candidate)).toBe(false);
          expect(isCuratedDiscoverPublished(candidate)).toBe(false);
        });
    });
  });

  it("does not treat historical recordings as current events or invent dates", () => {
    const crosses = byId.get("archive-research-bacio-croci-zuglio");
    const mayTree = byId.get("archive-research-maj-lucinico");
    const osmiza = byId.get("archive-research-osmiza-frasco");
    const fishing = byId.get("archive-research-toco-marano");

    expect(crosses.draftCopy.it).toContain("Ascensione del 1973");
    expect(crosses.draftCopy.it).toContain("comunità della valle");
    expect(crosses.temporalRule).toEqual({
      type: "movable_feast",
      anchor: "ascension",
      status: "requires_runtime_rule",
    });
    expect(mayTree.draftCopy.it).toContain("5 e 6 maggio 1973");
    expect(mayTree.draftCopy.it).toContain("fiori ed erbe lasciati sugli usci");
    expect(mayTree.draftCopy.it).not.toContain("raccolta rituale");
    expect(mayTree.temporalRule).toEqual({
      type: "nth_weekday",
      month: 5,
      weekday: "sunday",
      ordinal: 1,
      status: "requires_runtime_rule",
    });
    expect(osmiza.temporalRule).toEqual({ type: "seasonal_opening", status: "no_fixed_date" });
    expect(fishing.temporalRule).toEqual({ type: "seasonal_assignment", status: "no_fixed_date" });
    [crosses, mayTree, osmiza, fishing].forEach((record) => {
      expect(record.itCopyReview.remainingWork).toContain("runtime_temporal_rule");
      expect(record).not.toHaveProperty("dateAnchors");
      expect(record).not.toHaveProperty("movableDates");
    });
  });

  it("retains only documented details and the territorial scope", () => {
    const traders = byId.get("archive-research-cramars-carnia");
    const osmiza = byId.get("archive-research-osmiza-frasco");
    const fishing = byId.get("archive-research-toco-marano");
    const animals = byId.get("archive-research-animali-nomi-campanacci");
    const combs = byId.get("archive-research-pettini-osso-andreis");
    const laundry = byId.get("archive-research-bucato-ranno");
    const needle = byId.get("archive-research-ago-osso-prosciutto");

    expect(traders.draftCopy.it).toContain("a piedi e con carri");
    expect(traders.draftCopy.it).toContain("partenze autunnali e i rientri primaverili");
    expect(traders.draftCopy.it).not.toContain("nuovi contatti culturali");
    expect(osmiza.draftCopy.it).toContain("tradizione del Carso");
    expect(osmiza.draftCopy.it).toContain("ramo d'edera");
    expect(osmiza.source.rightsNote).toContain("testi, fotografie o impaginazione");
    expect(fishing.draftCopy.it).toContain("sorteggio");
    expect(fishing.draftCopy.it).not.toMatch(/Grado|semplicemente occupate|proprietà/);
    expect(animals.draftCopy.it).toContain("cavalli e bovini");
    expect(animals.draftCopy.it).toContain("soprattutto irrequieti o dominanti");
    expect(animals.draftCopy.it).not.toContain("ogni animale");
    expect(combs.draftCopy.it).toContain("pettini d'osso");
    expect(combs.draftCopy.it).not.toContain("tabacchiere");
    expect(laundry.title.it).toContain("poteva");
    expect(laundry.draftCopy.it).toContain("ammollo per una notte");
    expect(laundry.draftCopy.it).toContain("Seguiva il risciacquo");
    expect(needle.draftCopy.it).toContain("osso di cavallo");
  });

  it("distinguishes the original three approvals from the seventeen explicit approvals", () => {
    expect(records).toHaveLength(20);
    expect(records.filter((record) => record.languageStatus.it === "approved")).toHaveLength(20);
    expect(records.filter((record) => record.editorialStatus === "bilingual_draft_pending_review"))
      .toHaveLength(0);
    expect(records.filter((record) => record.editorialStatus === "promotion_ready_except_fur"))
      .toHaveLength(0);
    expect(records.filter((record) => record.reviewStatus === "promoted")).toHaveLength(20);
    expect(records.filter((record) => record.promotionReview)).toHaveLength(20);
    const earlierRecords = records.filter((record) => !REVIEWED_IDS.includes(record.id));
    expect(earlierRecords).toHaveLength(10);
    expect(earlierRecords.every((record) => !record.itCopyReview)).toBe(true);
    expect(earlierRecords.filter((record) => (
      record.languageReview.fur.approvalBasis === "user_conditional_standard_reference_review"
    )))
      .toHaveLength(3);
    expect(earlierRecords.filter((record) => (
      record.languageReview.fur.approvalBasis === "user_explicit_assisted_review_approval"
    ))).toHaveLength(7);
  });
});
