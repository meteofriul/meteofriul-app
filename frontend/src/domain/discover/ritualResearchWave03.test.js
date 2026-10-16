import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import institutionalRituals from "../../data/discover/institutionalRituals.json";
import research from "../../data/discover/ritualResearchWave03.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getDiscoverTemporalRank } from "./discoverTemporalSelection";

const TITIANO_ID = "institutional-ritual-titiano-madonna-neve";
const CASTELMONTE_ID = "institutional-ritual-castelmonte-otto-settembre";
const PROMOTIONS = {
  "ritual-research-titiano-madonna-neve": TITIANO_ID,
  "ritual-research-castelmonte-otto-settembre": CASTELMONTE_ID,
};
const EXPECTED_SOURCES = {
  [TITIANO_ID]: "https://www.atlantedeiluoghirivierafriulana.it/",
  [CASTELMONTE_ID]: "https://www.diocesiudine.it/la-chiesa-udinese-si-affida-a-maria-in-pellegrinaggio-a-castelmonte-chiesa-giubilare/",
};

// Freeze the complete seven pre-wave-03 records, including Matajur and Missus.
// Later additions may append without weakening preservation of earlier copy.
const PRESERVED_DIGESTS = {
  "institutional-ritual-cidulis-cercivento": "5d6753992f2ada6b750eaf325004136f530855039e6db5c0909355ec9f637dd0",
  "institutional-ritual-carnival-masks": "a28c0c7f57f441d6c4e66bd62ad2f61829d84f823cda63b85260f054d8965e6d",
  "institutional-ritual-resian-carnival": "35703cd09d445453d46e393a5a1900301f05ae17c35188cfa5b6af292c3cd9e8",
  "institutional-ritual-craceles-holy-week": "debee019bc8cd32ebb6afcf2d024f2d24ecfb462e647c24b8c0aaae9d1361c98",
  "institutional-ritual-winter-gift-bearers": "529cab302fce59f32e6eec8dfbff7319af0f08144a732b3c50c965c77590e1b1",
  "institutional-ritual-matajur-rogazione-maggiore": "ff6c4d52f2cefacba57ec3b1b961e1d030451f7e737f4b24a2d1aeafbde9869f",
  "institutional-ritual-missus-novena": "2a6b9f02ad449a602babfbcdb730a9c64bc5e0a1f0b5e29b28a5fe322ee1bb1c",
};

const runtimeById = new Map(institutionalRituals.map((record) => [record.id, record]));
const titiano = runtimeById.get(TITIANO_ID);
const castelmonte = runtimeById.get(CASTELMONTE_ID);
const location = { city: "Pordenone", province: "Pordenone", region: "Friuli Venezia Giulia" };

function ritualCard(today, language, city = location) {
  return buildDiscoverViewModel({ today, language, location: city })
    .sections.find((section) => section.id === "rituals")?.cards[0];
}

describe("ritual research wave 03", () => {
  it("appends the two new rites without altering any of the seven earlier records", () => {
    expect(institutionalRituals.slice(0, 9).map((record) => record.id)).toEqual([
      ...Object.keys(PRESERVED_DIGESTS), TITIANO_ID, CASTELMONTE_ID,
    ]);
    Object.entries(PRESERVED_DIGESTS).forEach(([id, digest]) => {
      expect(createHash("sha256").update(JSON.stringify(runtimeById.get(id))).digest("hex"))
        .toBe(digest);
    });
    expect(new Set(culturalRecords.map((record) => record.id)).size).toBe(culturalRecords.length);
  });

  it("keeps a compact hidden manifest linked to the only two runtime promotions", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      snapshotDate: "2026-08-31",
      readyForUi: false,
      runtimeCatalog: "frontend/src/data/discover/institutionalRituals.json",
    });
    expect(research.records.map((record) => record.id)).toEqual(Object.keys(PROMOTIONS));
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(PROMOTIONS[candidate.id]);
      expect(candidate).toMatchObject({
        promotedRecordId: runtime.id,
        rubric: "riti_credenze_popolari",
        reviewStatus: "promoted",
        readyForUi: false,
        currentEventScheduleVerified: false,
      });
      expect(runtime).toMatchObject({
        sourceId: candidate.id,
        candidateId: candidate.id,
        canonicalKey: candidate.canonicalKey,
        section: "riti_credenze_popolari",
        editorialStatus: "ready_it",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
        recurrence: "fixed_date",
        dateAnchors: [candidate.temporalRule.date],
        dateRanges: [],
        movableDates: [],
        movableDateRanges: [],
      });
      expect(candidate.editorialWindow).toEqual(candidate.temporalRule);
      expect(candidate.geographicScope).toEqual(runtime.areas);
      expect(candidate).not.toHaveProperty("draftCopy");
      expect(candidate).not.toHaveProperty("text");
      expect(isCuratedDiscoverUiReady(candidate)).toBe(false);
      expect(isCuratedDiscoverPublished(runtime)).toBe(true);
      expect(culturalRecords.filter((record) => record.sourceId === candidate.id)).toHaveLength(1);
      expect(culturalRecords.some((record) => record.id === candidate.id)).toBe(false);
      [runtime.title, runtime.text, runtime.appShort].forEach((copy) => {
        expect(copy.it).toBeTruthy();
        expect(copy.fur).toBeTruthy();
        expect(copy.fur).not.toBe(copy.it);
      });
    });
  });

  it("retains verified primary HTML sources, calendar support and no reused media", () => {
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      expect(candidate.source).toMatchObject({
        url: EXPECTED_SOURCES[runtime.id], accessMethod: "direct_html", checkedAt: "2026-08-31",
      });
      expect(runtime.source).toMatchObject({
        url: candidate.source.url, confidence: "alta", auditStatus: "source_and_scope_verified",
      });
      expect(runtime.source.rightsNote).toMatch(/nessuna immagine/);
      expect(runtime).not.toHaveProperty("imageUrl");
      expect(runtime).not.toHaveProperty("videoUrl");
      expect(runtime).not.toHaveProperty("media");
    });
    expect(titiano.supportingSources).toEqual(expect.arrayContaining([
      expect.objectContaining({ url: "https://www.stellaboschilaguna.it/it/town/precenicco/" }),
    ]));
    expect(castelmonte.source.publishedAt).toBe("2025-08-28");
    expect(titiano.source.note).toContain("Non è un programma attuale");
  });

  it("traces assisted language review without claiming certification or independent human approval", () => {
    expect(research.editorialDecision).toMatchObject({
      basis: "user_delegated_assisted_editorial_review",
      reviewer: "assistant",
      independentHumanReview: false,
      scope: Object.keys(PROMOTIONS),
    });
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      expect(candidate.languageReview).toMatchObject({
        approvalBasis: "user_delegated_assisted_editorial_review",
        reviewer: "assistant",
        independentHumanReview: false,
        referencesLocation: `${runtime.id}.languageReview.fur.references`,
      });
      const review = runtime.languageReview.fur;
      expect(review).toMatchObject({
        approvalBasis: "user_delegated_assisted_editorial_review",
        reviewMethod: "assisted_standard_reference_review",
        reviewer: "assistant",
        independentHumanReview: false,
      });
      expect(review.approvalNote).toMatch(/non approvazione dell'utente frase per frase/i);
      expect(review.approvalNote).toMatch(/non certificazione ARLeF/i);
      expect(review.references.length).toBeGreaterThan(0);
      review.references.forEach((reference) => {
        expect(new URL(reference.url).hostname).toMatch(/(^|\.)arlef\.it$/);
        expect(new URL(reference.url).protocol).toBe("https:");
        expect(["direct_html", "direct_http_html"]).toContain(reference.accessMethod);
        expect(reference.url).not.toMatch(/\.pdf(?:$|\?)/);
      });
    });
    expect(titiano.languageReview.fur.references.some((reference) => (
      reference.url === "https://arlef.it/in-memoria-di-bertrando/"
    ))).toBe(true);
  });

  it("keeps Titiano's boat journey and subsequent arrival at the chapel distinct", () => {
    expect(titiano.areas).toEqual(["precenicco", "titiano", "fiume_stella"]);
    expect(titiano.text.it).toContain("in barca da Precenicco fino a Titiano e poi alla chiesetta");
    expect(titiano.text.fur).toContain("in barcje di Prissinins fin a Titiano e po ae gleseute");
    expect(titiano.text.it).not.toMatch(/apparizion|miracol|Grado|Barbana/);
    expect(titiano.text.fur).not.toMatch(/aparizion|miracul|Grau|Barbana/);
  });

  it("dates only the diocesan pilgrimage to 1976, not the sanctuary or all pilgrimages", () => {
    expect(castelmonte.areas).toEqual(["castelmonte", "prepotto", "arcidiocesi_udine"]);
    expect(castelmonte.text.it).toContain("pellegrinaggio diocesano dell'8 settembre");
    expect(castelmonte.text.fur).toContain("pelegrinaç de Glesie di Udin dai 8 di Setembar");
    expect(castelmonte.text.it).toContain("dopo il terremoto del 1976");
    expect(castelmonte.text.fur).toContain("daspò dal taramot dal 1976");
    expect(castelmonte.appShort.it).toContain("diocesano");
    expect(castelmonte.appShort.fur).toContain("de Glesie di Udin");
    expect(castelmonte.sourceNote).toContain("non la nascita del santuario");
  });

  it("preserves distinct cultural identities and avoids current-event promises or directions", () => {
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      expect(candidate.duplicateReview.status).toBe("distinct");
      expect(candidate.duplicateReview.comparedCatalogs).toEqual(expect.arrayContaining([
        "ostermannCulturalDiscover", "institutionalRituals", "institutionalArchive", "localMemory",
      ]));
      expect(culturalRecords.filter((record) => record.canonicalKey === runtime.canonicalKey)).toHaveLength(1);
      expect(JSON.stringify([runtime.title, runtime.text, runtime.appShort]))
        .not.toMatch(/\b2026\b|\d{1,2}:\d{2}|prenota|partecipa|nel tuo paese|qui vicino|tal to paîs/i);
    });
  });

  it.each([2026, 2027, 2028])("keeps both exact dates isolated from adjacent days in %s", (year) => {
    [[titiano, "08-04", "08-05", "08-06"], [castelmonte, "09-07", "09-08", "09-09"]]
      .forEach(([record, before, exact, after]) => {
        expect(getDiscoverTemporalRank(record, `${year}-${before}`)).toBeNull();
        expect(getDiscoverTemporalRank(record, `${year}-${exact}`)).toBe(0);
        expect(getDiscoverTemporalRank(record, `${year}-${after}`)).toBeNull();
      });
  });

  it.each([2026, 2027, 2028].flatMap((year) => ["it", "fur"].map((language) => [year, language])))(
    "renders both cards and sources on their sole dates in %s %s", (year, language) => {
      [["08-05", titiano], ["09-08", castelmonte]].forEach(([date, record]) => {
        const card = ritualCard(`${year}-${date}`, language);
        expect(card).toMatchObject({
          id: record.id,
          title: record.title[language],
          text: record.text[language],
          sourceLabel: record.source.label,
          isFurPending: false,
          selectionKind: "exact_date",
        });
        const html = renderToStaticMarkup(createElement(DiscoverCard, { card }));
        expect(html).toContain(renderToStaticMarkup(createElement("h2", null, record.title[language])));
        expect(html).toContain(renderToStaticMarkup(createElement("p", null, record.text[language])));
        expect(html).toContain(renderToStaticMarkup(createElement("small", null, record.source.label)));
      });
      ["08-04", "08-06", "09-07", "09-09"].forEach((date) => {
        expect([TITIANO_ID, CASTELMONTE_ID]).not.toContain(ritualCard(`${year}-${date}`, language)?.id);
      });
    },
  );

  it.each(["it", "fur"])("does not reinterpret cultural areas as the user's town in %s", (language) => {
    const trieste = { city: "Trieste", province: "Trieste", region: "Friuli Venezia Giulia" };
    ["2028-08-05", "2028-09-08"].forEach((date) => {
      expect(ritualCard(date, language, trieste)).toEqual(ritualCard(date, language, location));
    });
  });
});
