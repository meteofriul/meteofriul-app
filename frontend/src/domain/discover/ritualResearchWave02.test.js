import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";

import institutionalRituals from "../../data/discover/institutionalRituals.json";
import research from "../../data/discover/ritualResearchWave02.json";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getDiscoverTemporalRank } from "./discoverTemporalSelection";

const MATAJUR_ID = "institutional-ritual-matajur-rogazione-maggiore";
const MISSUS_ID = "institutional-ritual-missus-novena";
const PROMOTIONS = {
  "ritual-research-matajur-rogazione-maggiore": MATAJUR_ID,
  "ritual-research-missus-novena": MISSUS_ID,
};
const EXPECTED_SOURCES = {
  [MATAJUR_ID]: {
    url: "https://www.diocesiudine.it/in-prossimita-della-festa-di-san-marco-tornano-gli-antichi-riti-delle-rogazioni/",
    publishedAt: "2023-04-19",
  },
  [MISSUS_ID]: {
    url: "https://www.diocesiudine.it/missus-est-il-canto-dellannunciazione-illumina-le-sere-della-novena-del-natale-in-friuli/",
    publishedAt: "2022-12-14",
  },
};

// Baseline captured before wave 02: preserves the complete five existing records,
// not merely their count or titles. Intentional later revisions need explicit review.
const ORIGINAL_RECORD_DIGESTS = {
  "institutional-ritual-cidulis-cercivento": "5d6753992f2ada6b750eaf325004136f530855039e6db5c0909355ec9f637dd0",
  "institutional-ritual-carnival-masks": "a28c0c7f57f441d6c4e66bd62ad2f61829d84f823cda63b85260f054d8965e6d",
  "institutional-ritual-resian-carnival": "35703cd09d445453d46e393a5a1900301f05ae17c35188cfa5b6af292c3cd9e8",
  "institutional-ritual-craceles-holy-week": "debee019bc8cd32ebb6afcf2d024f2d24ecfb462e647c24b8c0aaae9d1361c98",
  "institutional-ritual-winter-gift-bearers": "529cab302fce59f32e6eec8dfbff7319af0f08144a732b3c50c965c77590e1b1",
};

const runtimeById = new Map(institutionalRituals.map((record) => [record.id, record]));
const matajur = runtimeById.get(MATAJUR_ID);
const missus = runtimeById.get(MISSUS_ID);
const location = { city: "Pordenone", province: "Pordenone", region: "Friuli Venezia Giulia" };

function ritualCard(today, language, city = location) {
  return buildDiscoverViewModel({ today, language, location: city })
    .sections.find((section) => section.id === "rituals")?.cards[0];
}

describe("ritual research wave 02", () => {
  it("adds only the two scoped promotions while preserving all five original records", () => {
    expect(institutionalRituals.slice(0, 7).map((record) => record.id)).toEqual([
      ...Object.keys(ORIGINAL_RECORD_DIGESTS), MATAJUR_ID, MISSUS_ID,
    ]);
    Object.entries(ORIGINAL_RECORD_DIGESTS).forEach(([id, digest]) => {
      expect(createHash("sha256").update(JSON.stringify(runtimeById.get(id))).digest("hex"))
        .toBe(digest);
    });
    expect(new Set(culturalRecords.map((record) => record.id)).size).toBe(culturalRecords.length);
  });

  it("keeps the dossier hidden and traces each original bilingual copy to one runtime record", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      snapshotDate: "2026-08-31",
      readyForUi: false,
    });
    expect(research.records.map((record) => record.id)).toEqual(Object.keys(PROMOTIONS));
    expect(new Set(research.records.map((record) => record.canonicalKey)).size).toBe(2);

    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(PROMOTIONS[candidate.id]);
      expect(candidate).toMatchObject({
        reviewStatus: "promoted",
        editorialStatus: "promoted_to_catalog",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: false,
        promotedRecordId: runtime.id,
        promotionReview: {
          decision: "promoted",
          targetRecordId: runtime.id,
          targetSection: "riti_credenze_popolari",
          remainingBlockers: [],
        },
      });
      expect(runtime).toMatchObject({
        sourceId: candidate.id,
        candidateId: candidate.id,
        canonicalKey: candidate.canonicalKey,
        section: "riti_credenze_popolari",
        editorialStatus: "ready_it",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
        ...candidate.promotionReview.runtimeTemporal,
      });
      expect(runtime.title).toEqual(candidate.title);
      expect(runtime.text).toEqual(candidate.draftCopy);
      expect(runtime.appShort).toEqual(candidate.draftAppShort);
      expect(runtime.areas).toEqual(candidate.geographicScope);
      expect(runtime.languageReview).toEqual(candidate.languageReview);
      expect(isCuratedDiscoverUiReady(candidate)).toBe(false);
      expect(isCuratedDiscoverPublished(runtime)).toBe(true);
      expect(culturalRecords.filter((record) => record.sourceId === candidate.id)).toHaveLength(1);
      expect(culturalRecords.some((record) => record.id === candidate.id)).toBe(false);
      [runtime.title, runtime.text, runtime.appShort].forEach((copy) => {
        expect(copy.it).toBeTruthy();
        expect(copy.fur).toBeTruthy();
        expect(copy.it).not.toBe(copy.fur);
      });
    });
  });

  it("records assisted editorial judgment without implying certification or a human phrase-by-phrase approval", () => {
    expect(research.editorialDecision).toMatchObject({
      basis: "user_delegated_assisted_editorial_review",
      reviewer: "assistant",
      independentHumanReview: false,
      scope: Object.keys(PROMOTIONS),
    });
    research.records.forEach((candidate) => {
      const review = candidate.languageReview.fur;
      expect(review).toMatchObject({
        approvalBasis: "user_delegated_assisted_editorial_review",
        reviewMethod: "assisted_standard_reference_review",
        reviewer: "assistant",
        independentHumanReview: false,
        approvedAt: "2026-08-31",
      });
      expect(review.approvalNote).toMatch(/non approvazione dell'utente frase per frase/i);
      expect(review.approvalNote).toMatch(/non certificazione ARLeF/i);
      expect(review.references.length).toBeGreaterThan(0);
      review.references.forEach((reference) => {
        expect(new URL(reference.url).protocol).toBe("https:");
        expect(new URL(reference.url).hostname).toMatch(/(^|\.)arlef\.it$/);
        if (reference.url.endsWith(".pdf")) {
          expect(reference.accessMethod).toBe("indexed_pdf_text_not_visual_audit");
          expect(reference.note).toMatch(/testo indicizzato.*senza audit visivo/i);
        } else {
          expect(reference.accessMethod).toBe("direct_http_html");
        }
      });
    });
  });

  it("preserves the two verified institutional HTML sources without introducing reused media", () => {
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      const expected = EXPECTED_SOURCES[runtime.id];
      expect(candidate.source).toMatchObject({
        ...expected,
        type: "institutional_publication",
        checkedAt: "2026-08-31",
        accessMethod: "direct_html",
      });
      expect(runtime.source).toMatchObject({ ...expected, auditStatus: "source_and_scope_verified" });
      expect(candidate.source.rightsNote).toMatch(/senza riuso di immagini/);
      expect(runtime.source.rightsNote).toMatch(/nessuna immagine/);
      [candidate, runtime].forEach((record) => {
        expect(record).not.toHaveProperty("image");
        expect(record).not.toHaveProperty("imageUrl");
        expect(record).not.toHaveProperty("videoUrl");
        expect(record).not.toHaveProperty("media");
      });
    });
  });

  it("keeps the Matajur source as a historical description rather than a current program", () => {
    expect(matajur.areas).toEqual(["tercimonte", "matajur", "valli_del_natisone"]);
    expect(matajur.text.it).toMatch(/^Nel 2023 .* era descritta/);
    expect(matajur.text.fur).toMatch(/^Tal 2023 .* e jere descrite/);
    expect(matajur.appShort.it).toMatch(/^Nel 2023 .* era descritta/);
    expect(matajur.appShort.fur).toMatch(/^Tal 2023 .* e jere descrite/);
    [matajur.text.it, matajur.text.fur].forEach((copy) => {
      expect(copy).toContain("Tercimonte");
      expect(copy).toContain("Matajur");
      expect(copy).not.toMatch(/Zuglio|Zui|Ascensione|Sense|\b2026\b|\d{1,2}:\d{2}/);
    });
    expect(matajur.sourceNote).toContain("non ne prova l'effettivo svolgimento");
    expect(research.records[0].documentedTraditionCalendar).toEqual({
      dateAnchors: ["04-25"], evidenceYear: 2023, currentEventScheduleVerified: false,
    });
  });

  it("separates the nine-evening Missus tradition from its three-day editorial window", () => {
    expect(missus.text.it).toContain("Dal 15 al 23 dicembre");
    expect(missus.text.fur).toContain("Dai 15 ai 23 di Dicembar");
    expect(missus.title.it).toContain("nove sere");
    expect(missus.title.fur).toContain("nûf seris");
    expect(missus.dateRanges).toEqual(["12-15..12-17"]);
    expect(missus.sourceNote).toMatch(/nove sere.*15 al 23 dicembre/);
    expect(missus.sourceNote).toContain("15–17 dicembre");
    expect(research.records[1].documentedTraditionCalendar).toEqual({
      dateRanges: ["12-15..12-23"], evenings: 9, currentEventScheduleVerified: false,
    });
    expect(research.records[1].temporalRule.purpose).toBe("editorial_first_three_evenings");
  });

  it("keeps the two rites distinct from Zuglio, winter gifts and the Natisone Devetica", () => {
    const zuglio = culturalRecords.find((record) => record.id === "institutional-archive-bacio-croci-zuglio");
    const gifts = runtimeById.get("institutional-ritual-winter-gift-bearers");
    expect(zuglio).toBeTruthy();
    expect(gifts).toBeTruthy();
    expect(matajur.canonicalKey).not.toBe(zuglio.canonicalKey);
    expect(matajur.source.url).not.toBe(zuglio.source.url);
    expect(missus.source.url).not.toBe(gifts.source.url);
    expect(missus.areas).toEqual(["arcidiocesi_udine", "comunita_di_tradizione_friulana"]);
    expect(missus.text.it).toContain("nelle comunità friulane che custodiscono questa usanza");
    expect(missus.text.fur).toContain("tes comunitâts furlanis che a conservin cheste usance");
    expect(missus.source.note).toContain("non si canta il Missus");
    expect(research.records[1].nonEquivalentTraditions).toEqual(["devetica_bozicna_valli_natisone"]);
    [matajur, missus].forEach((record) => {
      expect(culturalRecords.filter((entry) => entry.canonicalKey === record.canonicalKey)).toHaveLength(1);
      expect(JSON.stringify(record.text)).not.toMatch(/nel tuo paese|qui vicino|nel tuo comune|tal to paîs/);
    });
    research.records.forEach((candidate) => {
      expect(candidate.duplicateReview.status).toBe("distinct");
      expect(candidate.duplicateReview.comparedCatalogs).toEqual(expect.arrayContaining([
        "institutionalRituals", "institutionalArchive", "ostermannCulturalDiscover",
      ]));
    });
  });

  it.each([2026, 2027, 2028])("enforces exact date boundaries in %s without a seasonal spillover", (year) => {
    expect(getDiscoverTemporalRank(matajur, `${year}-04-24`)).toBeNull();
    expect(getDiscoverTemporalRank(matajur, `${year}-04-25`)).toBe(0);
    expect(getDiscoverTemporalRank(matajur, `${year}-04-26`)).toBeNull();
    expect(getDiscoverTemporalRank(missus, `${year}-12-14`)).toBeNull();
    [15, 16, 17].forEach((day) => {
      expect(getDiscoverTemporalRank(missus, `${year}-12-${day}`)).toBe(2);
    });
    [18, 23, 24, 25, 31].forEach((day) => {
      expect(getDiscoverTemporalRank(missus, `${year}-12-${day}`)).toBeNull();
    });
  });

  it.each(["it", "fur"])("renders both in %s only on their editorial dates with the verified source", (language) => {
    [["2028-04-25", matajur], ...[15, 16, 17].map((day) => [`2028-12-${day}`, missus])]
      .forEach(([date, record]) => {
        expect(ritualCard(date, language)).toMatchObject({
          id: record.id,
          title: record.title[language],
          text: record.text[language],
          sourceLabel: record.source.label,
          isFurPending: false,
        });
      });
    ["2028-04-24", "2028-04-26", "2028-12-14", "2028-12-18", "2028-12-23"]
      .forEach((date) => {
        expect([MATAJUR_ID, MISSUS_ID]).not.toContain(ritualCard(date, language)?.id);
      });
  });

  it.each(["it", "fur"])("treats geography as cultural scope, not a nearby-event promise, in %s", (language) => {
    ["2028-04-25", "2028-12-15"].forEach((date) => {
      const trieste = { city: "Trieste", province: "Trieste", region: "Friuli Venezia Giulia" };
      expect(ritualCard(date, language, trieste)).toEqual(ritualCard(date, language, location));
    });
  });
});
