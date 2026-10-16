import { describe, expect, it } from "vitest";

import archiveResearchWave01 from "../../data/discover/archiveResearchWave01.json";
import archiveResearchWave02 from "../../data/discover/archiveResearchWave02.json";
import { getDiscoverTypeLabel } from "../../copy/discoverCopy";
import { buildDiscoverEditorialCalendarAudit } from "../../features/discover/discoverEditorialCalendarAudit";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";

function getPreparedRecords() {
  return [...archiveResearchWave01.records, ...archiveResearchWave02.records]
    .filter((record) => record.promotionReview);
}

describe("discover archive promotion readiness", () => {
  it("records explicit assisted approval of the remaining seventeen without publishing research snapshots", () => {
    const records = getPreparedRecords().filter((record) => record.promotionReview.promotedAt === "2026-08-31");

    expect(records).toHaveLength(17);
    records.forEach((record) => {
      expect(record).toMatchObject({
        reviewStatus: "promoted",
        editorialStatus: "promoted_to_catalog",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: false,
        promotionReview: {
          decision: "promoted",
          targetSection: "archivio_tradizioni",
          remainingBlockers: [],
        },
      });
      expect(record.title.it).toBeTruthy();
      expect(record.title.fur).toBeTruthy();
      expect(record.draftCopy.it).toBeTruthy();
      expect(record.draftCopy.fur).toBeTruthy();
      expect(record.draftAppShort.it).toBeTruthy();
      expect(record.draftAppShort.fur).toBeTruthy();
      expect(record.furReviewNotes.length).toBeGreaterThan(0);
      expect(record.languageReview.fur).toMatchObject({
        approvalBasis: "user_explicit_assisted_review_approval",
        reviewMethod: "assisted_standard_reference_review",
        approvedAt: "2026-08-31",
        reviewDocument: "docs/operations/SCOPRI_FUR_REVIEW_2026-08-31.md",
        approvalDocument: "docs/operations/SCOPRI_ARCHIVE_PROMOTION_2026-08-31.md",
      });
      expect(isCuratedDiscoverUiReady(record)).toBe(false);
    });
  });

  it("maps all prepared records uniquely and separates active from future identities", () => {
    const records = getPreparedRecords();
    const activeIds = new Set(culturalRecords.map((record) => record.id));
    const targetIds = records.map((record) => record.promotionReview.targetRecordId);

    expect(records).toHaveLength(20);
    expect(new Set(targetIds).size).toBe(records.length);
    expect(new Set(records.map((record) => record.canonicalKey)).size).toBe(records.length);
    expect(targetIds.every((id) => id.startsWith("institutional-archive-"))).toBe(true);
    records.forEach((record) => {
      expect(activeIds.has(record.promotionReview.targetRecordId)).toBe(
        record.promotionReview.decision === "promoted",
      );
      const targetType = record.promotionReview.targetType;
      expect(getDiscoverTypeLabel(targetType, "it")).not.toBe("Almanacco");
      expect(getDiscoverTypeLabel(targetType, "fur")).not.toBe("Almanac");
    });
  });

  it("preserves the first FUR corrections and records the user's conditional approval honestly", () => {
    const records = new Map(getPreparedRecords().map((record) => [record.id, record]));
    const baskets = records.get("archive-research-cesti-vimini");
    const dairy = records.get("archive-research-latteria-sociale");
    const postcards = records.get("archive-research-cartoline-lignano");

    expect(baskets.draftCopy.fur).toMatch(/^I zeis /);
    expect(baskets.draftAppShort.fur).toContain("dai zeis");
    expect(baskets.draftCopy.fur).toContain("al lavadôr");
    expect(dairy.title.fur).toMatch(/^La latarie /);
    expect(dairy.draftCopy.fur).toMatch(/^Lis latariis /);
    expect(postcards.draftAppShort.fur).toContain("a contin ");
    expect(postcards.draftAppShort.fur).not.toContain("a contìn");
    expect(postcards.title.fur).toBe("Lis cartulinis a contin Lignan");

    [baskets, dairy, postcards].forEach((record) => {
      expect(record.furReviewNotes.some((note) => note.includes("2026-08-30"))).toBe(true);
      expect(record.languageStatus).toEqual({ it: "approved", fur: "approved" });
      expect(record.promotionReview).toMatchObject({
        decision: "promoted",
        promotedAt: "2026-08-30",
        remainingBlockers: [],
      });
      expect(record.languageReview.fur).toMatchObject({
        approvalBasis: "user_conditional_standard_reference_review",
        reviewMethod: "assisted_standard_reference_review",
        approvedAt: "2026-08-30",
      });
      expect(record.readyForUi).toBe(false);
      expect(isCuratedDiscoverUiReady(record)).toBe(false);
    });
  });

  it("preserves second-batch corrections and historical draft review after explicit approval", () => {
    const secondBatch = getPreparedRecords().filter((record) => (
      record.furDraftReview?.batchId === "archive-fur-review-2026-08-30-02"
    ));
    expect(secondBatch.map((record) => record.id)).toEqual([
      "archive-research-coscritti-alesso",
      "archive-research-tacamenti-cavazzo",
      "archive-research-caffe-storici-trieste",
    ]);
    const [alesso, weaving, cafes] = secondBatch;

    expect(alesso.title.fur).toBe("Il Prin dal an dai coscrits a Dalès");
    expect(alesso.draftCopy.fur).toContain("i cjapiei inflorâts");
    expect(alesso.draftCopy.fur).not.toContain("infiorâts");
    expect(weaving.title.fur).toBe("Un cuader par tiessi: i «tacamenti»");
    expect(weaving.draftCopy.fur).toContain("dissens pal telâr");
    expect(weaving.draftCopy.fur).toContain("Il «Libro dei Tacamenti»");
    expect(weaving.draftAppShort.fur).toMatch(/^Un manuscrit /);
    expect(weaving.draftAppShort.fur).toContain("di un tiessidôr");
    expect(cafes.title.fur).toBe("I cafês tant che tinei di Triest");
    expect(cafes.draftCopy.fur).toContain("comunitâts greghe e todescje");
    expect(cafes.draftAppShort.fur).toContain("i cafês storics di Triest");

    secondBatch.forEach((record) => {
      expect(record.furDraftReview).toMatchObject({
        reviewedAt: "2026-08-30",
        method: "assisted_standard_reference_review",
        status: "revised_pending_human_review",
      });
      expect(record.furDraftReview.references.length).toBeGreaterThan(0);
      expect(record.languageStatus).toEqual({ it: "approved", fur: "approved" });
      expect(record.languageReview.fur.approvalBasis).toBe("user_explicit_assisted_review_approval");
      expect(record.promotionReview.remainingBlockers).toEqual([]);
      expect(record.promotionReview.decision).toBe("promoted");
      expect(record.readyForUi).toBe(false);
      expect(culturalRecords.some((active) => active.id === record.promotionReview.targetRecordId))
        .toBe(true);
    });
  });

  it("preserves four third-batch review snapshots separately from subsequent approval", () => {
    const thirdBatch = getPreparedRecords().filter((record) => (
      record.furDraftReview?.batchId === "archive-fur-review-2026-08-30-03"
    ));
    expect(thirdBatch.map((record) => record.id)).toEqual([
      "archive-research-lippa-regole-locali",
      "archive-research-secchi-rame-arconcello",
      "archive-research-ciavedal-alare",
      "archive-research-teche-racconti-popolari",
    ]);
    const [lippa, buckets, hearth, stories] = thirdBatch;

    expect(lippa.draftCopy.fur).toContain("zuiâ di lipe");
    expect(lippa.draftCopy.fur).not.toContain("zuiâ ae lipe");
    expect(buckets.title.fur).toBe("La aghe puartade cul buinç");
    expect(buckets.draftCopy.fur).toContain("i cjaldîrs di ram");
    expect(buckets.draftCopy.fur).toContain("cuntun rimpin par bande par belançâ il pês");
    expect(hearth.title.fur).toBe("Il cjavedâl, plui di un imprest dal fogolâr");
    expect(hearth.draftCopy.fur).toContain("Passât di pari in fi");
    expect(hearth.draftAppShort.fur).toContain("memorie e lustri de famee");
    [hearth.title.fur, hearth.draftCopy.fur, hearth.draftAppShort.fur].forEach((copy) => {
      expect(copy).not.toContain("alâr");
      expect(copy).not.toContain("prestiç");
    });
    expect(stories.draftCopy.fur).toMatch(/^L'archivi Teche Friulane al met dongje /);
    expect(stories.draftCopy.fur).toContain("informadôrs: liendis, flabis");
    expect(stories.draftCopy.fur).not.toContain("leiendis");
    expect(stories.draftCopy.fur).toContain("filastrocjis, trascrits");
    [stories.title.fur, stories.draftCopy.fur, stories.draftAppShort.fur].forEach((copy) => {
      expect(copy.toLowerCase()).toContain("plui di 2.300");
    });

    thirdBatch.forEach((record) => {
      expect(record.furDraftReview).toMatchObject({
        reviewedAt: "2026-08-30",
        sourceRecheckedAt: "2026-08-30",
        method: "assisted_standard_reference_review",
        status: "revised_pending_human_review",
        reviewDocument: "docs/operations/SCOPRI_FUR_REVIEW_2026-08-30_BATCH_03.md",
      });
      expect(record.furDraftReview.references.length).toBeGreaterThan(0);
      expect(record.furDraftReview.references.every((reference) => (
        reference.url.startsWith("https://") && reference.note.length > 0
      ))).toBe(true);
      expect(record.languageStatus).toEqual({ it: "approved", fur: "approved" });
      expect(record.languageReview.fur.approvalBasis).toBe("user_explicit_assisted_review_approval");
      expect(record.promotionReview.remainingBlockers).toEqual([]);
      expect(record.promotionReview.decision).toBe("promoted");
      expect(record.readyForUi).toBe(false);
      expect(culturalRecords.some((active) => active.id === record.promotionReview.targetRecordId))
        .toBe(true);
    });
    const previouslyRevised = getPreparedRecords().filter((record) => (
      ["archive-fur-review-2026-08-30-02", "archive-fur-review-2026-08-30-03"]
        .includes(record.furDraftReview?.batchId)
    ));
    expect(previouslyRevised).toHaveLength(7);
    expect(previouslyRevised.every((record) => (
      record.furDraftReview?.status === "revised_pending_human_review"
    ))).toBe(true);
  });

  it("normalizes temporal rules to formats already supported by Scopri", () => {
    const records = getPreparedRecords();
    const temporalRules = records.map((record) => record.promotionReview.runtimeTemporal);
    const newYear = records.find((record) => record.id === "archive-research-coscritti-alesso");
    const lignano = records.find((record) => record.id === "archive-research-cartoline-lignano");

    temporalRules.forEach((rule) => {
      expect(["always", "seasonal", "date_range"]).toContain(rule.recurrence);
      expect(rule.dateAnchors).toEqual(expect.any(Array));
      expect(rule.dateRanges).toEqual(expect.any(Array));
      expect(rule.movableDates).toEqual(expect.any(Array));
      expect(rule.movableDateRanges).toEqual(expect.any(Array));
      expect(rule.seasons).toEqual(expect.any(Array));
      expect(rule.weatherTags).toEqual(expect.any(Array));
    });
    expect(newYear.promotionReview.runtimeTemporal).toMatchObject({
      recurrence: "date_range",
      dateRanges: ["12-31..01-01"],
      seasons: ["inverno"],
    });
    expect(lignano.promotionReview.runtimeTemporal).toMatchObject({
      recurrence: "seasonal",
      seasons: ["estate"],
    });
  });

  it.each([2026, 2027, 2028, 2029, 2030, 2031])(
    "uses all twenty promoted records in the actual collision-free calendar in %i",
    (year) => {
      const targetIds = getPreparedRecords().map((record) => record.promotionReview.targetRecordId);
      expect(targetIds).toHaveLength(20);
      expect(new Set(culturalRecords.map((record) => record.id)).size).toBe(culturalRecords.length);

      ["it", "fur"].forEach((language) => {
        const audit = buildDiscoverEditorialCalendarAudit({ year, language });

        expect(audit.summary.visibleCollisions).toEqual([]);
        expect(audit.summary.exactDatePrecedenceViolations).toEqual([]);
        expect(audit.summary.archive.eligibleIds).toEqual(expect.arrayContaining(targetIds));
        expect(audit.summary.archive.usedIds).toEqual(expect.arrayContaining(targetIds));
        expect(audit.summary.archive.longestConsecutiveRepeat.days).toBeLessThanOrEqual(2);
      });
    },
    10_000,
  );
});
