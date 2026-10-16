import { describe, expect, it } from "vitest";

import archiveResearchWave01 from "../../data/discover/archiveResearchWave01.json";
import archiveResearchWave02 from "../../data/discover/archiveResearchWave02.json";
import culturalRecords from "./discoverCulturalRecords";

const EXPECTED_SOURCES = {
  "archive-research-lippa-regole-locali": "https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=597653",
  "archive-research-secchi-rame-arconcello": "https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=821677",
  "archive-research-ciavedal-alare": "https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=821676",
  "archive-research-mulini-risorgive": "https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=819778",
  "archive-research-animali-nomi-campanacci": "https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=597659",
  "archive-research-pettini-osso-andreis": "https://www.parcodolomitifriulane.it/i-paesi-del-parco/andreis/",
  "archive-research-bucato-ranno": "https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=597655",
  "archive-research-ago-osso-prosciutto": "https://patrimonioculturale.regione.fvg.it/museo/?s_id=440505&s_tab=f",
  "archive-research-teche-racconti-popolari": "https://www.techefriulane.it/biblioteca-digitale/racconti-popolari",
  "archive-research-cartoline-lignano": "https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=597660",
};

const FIRST_PROMOTED_IDS = new Set(["archive-research-cartoline-lignano"]);

describe("discover archive research wave 02", () => {
  it("preserves ten source-verified research records and traces all catalog promotions", () => {
    const records = archiveResearchWave02.records;

    expect(archiveResearchWave02).toMatchObject({
      schemaVersion: 1,
      snapshotDate: "2026-08-28",
    });
    expect(records.map((record) => record.id)).toEqual(Object.keys(EXPECTED_SOURCES));
    expect(new Set(records.map((record) => record.id)).size).toBe(10);
    expect(new Set(records.map((record) => record.canonicalKey)).size).toBe(10);

    records.forEach((record) => {
      const firstPromotion = FIRST_PROMOTED_IDS.has(record.id);
      expect(record).toMatchObject({
        rubric: "archive_traditions",
        reviewStatus: "promoted",
        editorialStatus: "promoted_to_catalog",
        languageStatus: {
          it: "approved",
          fur: "approved",
        },
        readyForUi: false,
      });
      expect(record.title.it).toBeTruthy();
      expect(record.title.fur).toBeTruthy();
      expect(record.draftCopy.it).toBeTruthy();
      expect(record.draftCopy.fur).toBeTruthy();
      expect(record.evidenceSummary).toBeTruthy();
      expect(record.geographicScope.length).toBeGreaterThan(0);
      expect(record.source).toMatchObject({
        url: EXPECTED_SOURCES[record.id],
        checkedAt: "2026-08-28",
      });
      expect(record.source.url.startsWith("https://")).toBe(true);
      expect(record.source.label).toBeTruthy();
      expect(record.source.type).toBeTruthy();
      expect(record.source.rightsNote).toBeTruthy();
      expect(["distinct", "partial_theme_overlap"]).toContain(record.duplicateReview.status);
      expect(record.duplicateReview.note).toBeTruthy();

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
    const prepared = archiveResearchWave02.records.filter((record) => record.promotionReview);

    expect(prepared.map((record) => record.id)).toEqual(Object.keys(EXPECTED_SOURCES));
    expect(new Set(prepared.map((record) => record.promotionReview.targetRecordId)).size).toBe(10);
    expect(prepared.every((record) => record.readyForUi === false)).toBe(true);
    expect(prepared.filter((record) => record.promotionReview.decision === "hold_for_fur_review"))
      .toHaveLength(0);
    expect(prepared.filter((record) => record.promotionReview.decision === "promoted"))
      .toHaveLength(10);
  });

  it("does not collide with earlier research or the active cultural catalog", () => {
    const wave01Ids = new Set(archiveResearchWave01.records.map((record) => record.id));
    const wave01Keys = new Set(archiveResearchWave01.records.map((record) => record.canonicalKey));
    const activeIds = new Set(culturalRecords.map((record) => record.id));
    const activeKeys = new Set(culturalRecords.map((record) => record.canonicalKey).filter(Boolean));

    archiveResearchWave02.records.forEach((record) => {
      expect(wave01Ids.has(record.id)).toBe(false);
      expect(wave01Keys.has(record.canonicalKey)).toBe(false);
      expect(activeIds.has(record.id)).toBe(false);
      expect(activeKeys.has(record.canonicalKey)).toBe(true);
    });
  });

  it("keeps only the Lignano postcard candidate seasonally constrained", () => {
    archiveResearchWave02.records.forEach((record) => {
      if (record.id === "archive-research-cartoline-lignano") {
        expect(record.temporalRule).toEqual({
          type: "seasonal_range",
          seasons: ["estate"],
        });
      } else {
        expect(record.temporalRule).toEqual({ type: "annual_rotation" });
      }
    });
  });

  it("preserves the source cautions on animals and Andreis", () => {
    const animals = archiveResearchWave02.records.find((record) => (
      record.id === "archive-research-animali-nomi-campanacci"
    ));
    const andreis = archiveResearchWave02.records.find((record) => (
      record.id === "archive-research-pettini-osso-andreis"
    ));

    expect(animals.draftCopy.it).toContain("animali da controllare");
    expect(animals.draftCopy.it).not.toContain("ogni animale aveva un campanaccio");
    expect(andreis.draftCopy.it).toContain("pettini d'osso");
    expect(andreis.draftCopy.it).not.toContain("tabacchiere");
  });
});
