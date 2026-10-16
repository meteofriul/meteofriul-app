import { describe, expect, it } from "vitest";

import archiveResearchWave01 from "../../data/discover/archiveResearchWave01.json";
import archiveResearchWave02 from "../../data/discover/archiveResearchWave02.json";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";

const BATCH_ID = "archive-fur-review-2026-08-30-04";
const records = [...archiveResearchWave01.records, ...archiveResearchWave02.records];
const drafts = records.filter((record) => record.furDraftReview?.batchId === BATCH_ID);
const byId = new Map(drafts.map((record) => [record.id, record]));

describe("discover remaining Friulian archive drafts", () => {
  it("retains the ten complete drafts and traces their explicitly authorized promotion", () => {
    expect(drafts.map((record) => record.id)).toEqual([
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
    ]);
    drafts.forEach((record) => {
      expect(record).toMatchObject({
        editorialStatus: "promoted_to_catalog",
        reviewStatus: "promoted",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: false,
      });
      [record.title.fur, record.draftCopy.fur, record.draftAppShort.fur].forEach((copy) => {
        expect(copy.trim().length).toBeGreaterThan(8);
        expect(copy).not.toMatch(/undefined|null|TODO|\uFFFD/);
      });
      expect(record.draftCopy.fur.length).toBeLessThanOrEqual(450);
      expect(record.draftAppShort.fur.length).toBeLessThanOrEqual(150);
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

  it("preserves the assisted draft snapshot without human approval or source certification", () => {
    drafts.forEach((record) => {
      expect(record.furDraftReview).toMatchObject({
        batchId: BATCH_ID,
        reviewedAt: "2026-08-30",
        method: "assisted_standard_reference_review",
        status: "drafted_pending_human_review",
        basedOnItReview: "archive-it-review-2026-08-30-01",
        reviewDocument: "docs/operations/SCOPRI_FUR_REVIEW_2026-08-30_BATCH_04.md",
      });
      expect(record.furDraftReview.references.length).toBeGreaterThan(1);
      record.furDraftReview.references.forEach((reference) => {
        expect(new URL(reference.url).protocol).toBe("https:");
        expect(reference.note.trim().length).toBeGreaterThan(5);
      });
      expect(record.furReviewNotes.length).toBeGreaterThan(0);
      expect(record.furDraftReview.remainingWork).toEqual(
        record.itCopyReview.remainingWork.filter((step) => step !== "fur_draft"),
      );
      expect(record.furDraftReview.remainingWork).toEqual(expect.arrayContaining([
        "fur_human_review",
        "calendar_and_duplicate_audit",
      ]));
      expect(record.furDraftReview.remainingWork).not.toContain("fur_draft");
      expect(record.furDraftReview).not.toHaveProperty("approvedAt");
      expect(record.furDraftReview).not.toHaveProperty("approvalBasis");
    });
  });

  it("keeps research copies invisible even when their separate catalog entries are approved", () => {
    const identities = new Set(culturalRecords.flatMap((record) => [
      record.id,
      record.candidateId,
      record.sourceId,
      record.canonicalKey,
    ]).filter(Boolean));
    drafts.forEach((record) => {
      expect(identities.has(record.id)).toBe(true);
      expect(identities.has(record.canonicalKey)).toBe(true);
      expect(identities.has(record.promotionReview.targetRecordId)).toBe(true);
      expect(culturalRecords.some((active) => active.id === record.id)).toBe(false);
      [
        record,
        { ...record, readyForUi: true },
        { ...record, readyForUi: undefined },
        { ...record, readyForUi: true, languageStatus: { it: "approved", fur: "approved" } },
      ].forEach((candidate) => {
        expect(isCuratedDiscoverUiReady(candidate)).toBe(false);
        expect(isCuratedDiscoverPublished(candidate)).toBe(false);
      });
    });
  });

  it("does not turn historical dates or undefined seasonal practices into runtime events", () => {
    ["archive-research-bacio-croci-zuglio", "archive-research-maj-lucinico"].forEach((id) => {
      expect(byId.get(id).draftCopy.fur).toContain("1973");
      expect(byId.get(id).temporalRule.status).toBe("requires_runtime_rule");
      expect(byId.get(id).furDraftReview.remainingWork).toContain("runtime_temporal_rule");
    });
    ["archive-research-osmiza-frasco", "archive-research-toco-marano"].forEach((id) => {
      expect(byId.get(id).temporalRule.status).toBe("no_fixed_date");
      expect(byId.get(id).furDraftReview.remainingWork).toContain("runtime_temporal_rule");
    });
    drafts.forEach((record) => {
      expect(record).not.toHaveProperty("dateAnchors");
      expect(record).not.toHaveProperty("movableDates");
      expect(record).not.toHaveProperty("recurrence");
    });
  });

  it("preserves documented local names and uses verified craft and landscape vocabulary", () => {
    const osmiza = byId.get("archive-research-osmiza-frasco");
    const fishing = byId.get("archive-research-toco-marano");
    const mills = byId.get("archive-research-mulini-risorgive");
    const animals = byId.get("archive-research-animali-nomi-campanacci");
    const combs = byId.get("archive-research-pettini-osso-andreis");
    const laundry = byId.get("archive-research-bucato-ranno");
    const needle = byId.get("archive-research-ago-osso-prosciutto");

    expect(osmiza.draftCopy.fur).toContain("ramaç di elare");
    expect(osmiza.draftCopy.fur).toContain("«frasco»");
    expect(osmiza.draftCopy.fur).toContain("a ufrissin");
    expect(fishing.draftCopy.fur).toContain("«tòco»");
    expect(fishing.draftCopy.fur).toContain("gjavade a sorte");
    expect(fishing.draftCopy.fur).not.toContain("Grau");
    expect(mills.draftCopy.fur).toContain("Tra Codroip e Dael");
    expect(mills.draftCopy.fur).toContain("puartade");
    expect(mills.title.fur).toContain("risultivis");
    expect(animals.draftCopy.fur).toContain("sampogns");
    expect(animals.draftCopy.fur).toContain("soredut a chei incuiets o dominants");
    expect(animals.draftAppShort.fur).toContain("cognossi");
    expect(combs.title.fur).toContain("«sedonêrs»");
    expect(combs.draftCopy.fur).toContain("pietins di vues");
    expect(laundry.title.fur).toContain("bugade");
    expect(laundry.draftCopy.fur).toContain("lissie");
    expect(laundry.draftCopy.fur).toContain("in muel par une gnot");
    expect(needle.title.fur).toContain("gusiele");
    expect(needle.draftCopy.fur).toContain("San Denêl");
    expect(needle.draftCopy.fur).toContain("stagjonadure");
    expect(needle.draftCopy.fur).toContain("carateristichis organoletichis");
  });

  it("preserves historical draft statuses separately from all twenty catalog approvals", () => {
    expect(records).toHaveLength(20);
    expect(records.filter((record) => record.languageStatus.fur === "approved")).toHaveLength(20);
    expect(records.filter((record) => record.languageStatus.fur === "pending_human_review"))
      .toHaveLength(0);
    expect(records.every((record) => record.title.fur && record.draftCopy.fur && record.draftAppShort.fur))
      .toBe(true);
    expect(records.filter((record) => record.editorialStatus === "promotion_ready_except_fur"))
      .toHaveLength(0);
    expect(records.filter((record) => record.editorialStatus === "it_ready_for_fur_draft"))
      .toHaveLength(0);
    expect(records.filter((record) => record.promotionReview)).toHaveLength(20);
    const earlierReviewed = records.filter((record) => (
      ["archive-fur-review-2026-08-30-02", "archive-fur-review-2026-08-30-03"]
        .includes(record.furDraftReview?.batchId)
    ));
    expect(earlierReviewed).toHaveLength(7);
    expect(earlierReviewed.every((record) => (
      record.furDraftReview.status === "revised_pending_human_review"
    ))).toBe(true);
  });
});
