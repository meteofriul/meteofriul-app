import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import archiveResearchWave01 from "../../data/discover/archiveResearchWave01.json";
import archiveResearchWave02 from "../../data/discover/archiveResearchWave02.json";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";

const records = [...archiveResearchWave01.records, ...archiveResearchWave02.records];
const editedBatch = records.filter((record) => record.furCopyEditReview);
const approvedCohort = records.filter((record) => (
  record.languageReview?.fur?.approvalBasis === "user_explicit_assisted_review_approval"
));
const REVIEW_DOCUMENT = "docs/operations/SCOPRI_FUR_REVIEW_2026-08-31.md";

describe("discover Friulian archive copy edit", () => {
  it("records a second assisted reading for only the ten fourth-batch drafts", () => {
    expect(editedBatch.map((record) => record.id)).toEqual([
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
    editedBatch.forEach((record) => {
      expect(record.furCopyEditReview).toMatchObject({
        reviewedAt: "2026-08-31",
        method: "assisted_standard_reference_review",
        status: "revised_pending_human_review",
        basedOnDraftBatch: "archive-fur-review-2026-08-30-04",
        reviewDocument: REVIEW_DOCUMENT,
        scope: ["title.fur", "draftCopy.fur", "draftAppShort.fur"],
      });
      expect(record.furCopyEditReview.findings.length).toBeGreaterThan(0);
      expect(record.furCopyEditReview.references.length).toBeGreaterThan(0);
      record.furCopyEditReview.references.forEach((reference) => {
        expect(new URL(reference.url).protocol).toBe("https:");
        expect(new URL(reference.url).hostname).toMatch(/(^|\.)arlef\.it$/);
        expect(reference.note.length).toBeGreaterThan(10);
      });
      expect(record.furDraftReview).toMatchObject({
        reviewedAt: "2026-08-30",
        status: "drafted_pending_human_review",
      });
      expect(record.furCopyEditReview).not.toHaveProperty("approvedAt");
      expect(record.furCopyEditReview).not.toHaveProperty("approvalBasis");
    });
  });

  it("distinguishes the single agreement correction from the single stylistic edit", () => {
    const changes = editedBatch.flatMap((record) => record.furCopyEditReview.changes
      .map((change) => ({ id: record.id, ...change })));
    expect(changes.map(({ id, field, from, to, kind }) => ({ id, field, from, to, kind }))).toEqual([
      {
        id: "archive-research-maj-lucinico", field: "draftCopy.fur",
        from: "La gnot e lave indenant", to: "A passavin la gnot", kind: "style",
      },
      {
        id: "archive-research-bucato-ranno", field: "draftCopy.fur",
        from: "in aghe corint,", to: "in aghe corinte,", kind: "grammar",
      },
    ]);
    changes.forEach((change) => {
      const record = records.find((candidate) => candidate.id === change.id);
      expect(record.draftCopy.fur).toContain(change.to);
      expect(record.draftCopy.fur).not.toContain(change.from);
      expect(change.reason.length).toBeGreaterThan(20);
    });
    expect(editedBatch.filter((record) => record.furCopyEditReview.changes.length === 0))
      .toHaveLength(8);
  });

  it("preserves attested constructions and the factual boundaries of the two revised texts", () => {
    const maj = records.find((record) => record.id === "archive-research-maj-lucinico");
    const laundry = records.find((record) => record.id === "archive-research-bucato-ranno");
    expect(maj.draftCopy.fur).toContain("ai 5 e ai 6 di Mai dal 1973");
    expect(maj.draftCopy.fur).toContain("flôrs e jerbis lassâts sui soiârs");
    expect(laundry.draftCopy.fur).toContain("si le tratave");
    expect(laundry.draftCopy.fur).toContain("si le resentave in aghe corinte");
    expect(laundry.draftCopy.fur).toContain("lassantle in muel par une gnot");
    expect(laundry.draftCopy.fur).toContain("freantle e batintle sui lavadôrs");
    expect(laundry.draftCopy.fur).not.toMatch(/canis|condotis/);
    expect(records.find((record) => record.id === "archive-research-mulini-risorgive").draftCopy.fur)
      .toContain("i imprescj");
    expect(records.find((record) => record.id === "archive-research-ago-osso-prosciutto").draftCopy.fur)
      .toContain("si conservin");
  });

  it("traces the seventeen explicit approvals while keeping the research copies hidden", () => {
    expect(approvedCohort).toHaveLength(17);
    expect(records.filter((record) => record.languageStatus.fur === "approved")).toHaveLength(20);
    approvedCohort.forEach((record) => {
      expect(record.languageReview.fur).toMatchObject({
        approvalBasis: "user_explicit_assisted_review_approval",
        reviewMethod: "assisted_standard_reference_review",
        approvedAt: "2026-08-31",
      });
      expect(record.promotionReview).toMatchObject({
        decision: "promoted", promotedAt: "2026-08-31", remainingBlockers: [],
      });
      expect(record.readyForUi).toBe(false);
      expect(isCuratedDiscoverUiReady(record)).toBe(false);
      expect(isCuratedDiscoverPublished(record)).toBe(false);
      expect(culturalRecords.some((active) => active.id === record.promotionReview.targetRecordId))
        .toBe(true);
      expect(culturalRecords.some((active) => active.id === record.id)).toBe(false);
    });
  });

  it("keeps the consolidated review copy aligned with the seventeen explicitly approved records", () => {
    const document = readFileSync(new URL(`../../../../${REVIEW_DOCUMENT}`, import.meta.url), "utf8");
    expect(document.match(/^### \d+\. /gm)).toHaveLength(17);
    expect(approvedCohort).toHaveLength(17);
    approvedCohort.forEach((record) => {
      expect(document).toContain(`Identità: ${record.id}`);
      expect(document).toContain(`**IT · ${record.title.it}**`);
      expect(document).toContain(`**FUR · ${record.title.fur}**`);
      expect(document).toContain(record.draftCopy.it);
      expect(document).toContain(record.draftCopy.fur);
      expect(document).toContain(`Anteprima IT: ${record.draftAppShort.it}`);
      expect(document).toContain(`Anteprima FUR: ${record.draftAppShort.fur}`);
    });
    expect(document).toContain("Approvazione editoriale esplicita dell'utente");
    expect(document).toContain("17 schede integrate nel catalogo locale");
  });
});
