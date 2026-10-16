import { describe, expect, it } from "vitest";

import almanacProverbs from "../../data/almanac/proverbs.json";
import archiveResearchWave01 from "../../data/discover/archiveResearchWave01.json";
import almanacReuse from "../../data/discover/traditionalSayingAlmanacReuse.json";
import culturalRecords from "./discoverCulturalRecords";
import { getTraditionalSayingRecords } from "./traditionalSayings";

const NEW_SAYING_IDS = [
  "ostermann-mulinars",
  "ostermann-barbe-mus",
  "ost1876-cjase-braide-prat",
  "ost1876-ogni-vit-so-pal",
  "ost1876-troi-batit-no-jerbe",
  "ost1876-rive-prin-mulin",
  "ost1876-roste-denant-aghe",
  "ost1876-no-comede-picule-buse",
  "ost1876-cjar-cence-tamon-fossal",
  "ost1876-ogni-pais-so-usance",
];

const PREPARED_IDS = new Set([
  "archive-research-bacio-croci-zuglio",
  "archive-research-coscritti-alesso",
  "archive-research-maj-lucinico",
  "archive-research-cramars-carnia",
  "archive-research-tacamenti-cavazzo",
  "archive-research-cesti-vimini",
  "archive-research-latteria-sociale",
  "archive-research-osmiza-frasco",
  "archive-research-toco-marano",
  "archive-research-caffe-storici-trieste",
]);

const FIRST_PROMOTED_IDS = new Set([
  "archive-research-cesti-vimini",
  "archive-research-latteria-sociale",
]);

describe("discover daily editorial research wave 01", () => {
  it("preserves ten research records and traces their approved catalog promotions", () => {
    const records = archiveResearchWave01.records;
    const publishedIds = new Set(culturalRecords.flatMap((record) => [
      record.id,
      record.sourceId,
      record.candidateId,
    ]).filter(Boolean));

    expect(records).toHaveLength(10);
    expect(new Set(records.map((record) => record.id)).size).toBe(records.length);
    expect(new Set(records.map((record) => record.canonicalKey)).size).toBe(records.length);

    records.forEach((record) => {
      expect(record.rubric).toBe("archive_traditions");
      const firstPromotion = FIRST_PROMOTED_IDS.has(record.id);
      expect(record.reviewStatus).toBe("promoted");
      expect(record.editorialStatus).toBe("promoted_to_catalog");
      expect(record.languageStatus).toEqual({
        it: "approved",
        fur: "approved",
      });
      expect(record.readyForUi).toBe(false);
      expect(record.title.it.length).toBeGreaterThan(8);
      expect(record.title.fur).toBeTruthy();
      expect(record.draftCopy.it.length).toBeGreaterThan(80);
      expect(record.draftCopy.fur).toBeTruthy();
      expect(record.evidenceSummary.length).toBeGreaterThan(40);
      expect(record.temporalRule.type).toBeTruthy();
      expect(record.geographicScope.length).toBeGreaterThan(0);
      expect(record.source.url).toMatch(/^https:\/\//);
      expect(record.source.checkedAt).toBe("2026-08-28");
      expect(record.source.rightsNote).toBeTruthy();
      expect(record.duplicateReview.status).toBeTruthy();
      expect(publishedIds.has(record.id)).toBe(true);
      expect(publishedIds.has(record.canonicalKey)).toBe(false);

      expect(record.draftAppShort.it).toBeTruthy();
      expect(record.draftAppShort.fur).toBeTruthy();
      expect(record.furReviewNotes.length).toBeGreaterThan(0);
      expect(record.promotionReview).toMatchObject({
        decision: "promoted",
        promotedAt: firstPromotion ? "2026-08-30" : "2026-08-31",
        targetSection: "archivio_tradizioni",
        remainingBlockers: [],
      });
      expect(record.languageReview.fur).toMatchObject({
        approvalBasis: firstPromotion
          ? "user_conditional_standard_reference_review"
          : "user_explicit_assisted_review_approval",
        reviewMethod: "assisted_standard_reference_review",
        approvedAt: firstPromotion ? "2026-08-30" : "2026-08-31",
      });
      if (record.furDraftReview?.batchId === "archive-fur-review-2026-08-30-04") {
        expect(record.itCopyReview.status).toBe("approved_for_fur_drafting");
        expect(record.furDraftReview.status).toBe("drafted_pending_human_review");
      }
    });
  });

  it("promotes all ten records while keeping the research copies hidden", () => {
    const prepared = archiveResearchWave01.records.filter((record) => record.promotionReview);

    expect(prepared.map((record) => record.id)).toEqual([...PREPARED_IDS]);
    expect(new Set(prepared.map((record) => record.promotionReview.targetRecordId)).size).toBe(10);
    expect(prepared.every((record) => record.readyForUi === false)).toBe(true);
    expect(prepared.filter((record) => record.promotionReview.decision === "hold_for_fur_review"))
      .toHaveLength(0);
    expect(prepared.filter((record) => record.promotionReview.decision === "promoted"))
      .toHaveLength(10);
  });

  it("adds ten sayings only by reusing already approved Almanacco copy", () => {
    const proverbsById = new Map(almanacProverbs.map((record) => [record.id, record]));
    const reuseById = new Map(almanacReuse.records.map((record) => [record.proverbId, record]));
    const discoverByCandidateId = new Map(
      getTraditionalSayingRecords().map((record) => [record.candidateId, record]),
    );

    expect(NEW_SAYING_IDS).toHaveLength(10);
    expect(new Set(NEW_SAYING_IDS).size).toBe(10);

    NEW_SAYING_IDS.forEach((id) => {
      const proverb = proverbsById.get(id);
      const descriptor = reuseById.get(id);
      const discoverRecord = discoverByCandidateId.get(id);

      expect(descriptor).toBeTruthy();
      expect(proverb).toMatchObject({
        almanacEligible: true,
        editorialReview: { it: "approved", fur: "approved" },
      });
      expect(proverb.it).toBeTruthy();
      expect(proverb.fur).toBeTruthy();
      expect(discoverRecord).toMatchObject({
        candidateId: id,
        reusedFromAlmanac: true,
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
      expect(discoverRecord.title).toEqual({ it: proverb.it, fur: proverb.fur });
    });
  });
});
