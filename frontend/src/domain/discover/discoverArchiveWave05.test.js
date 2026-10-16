import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import wave01 from "../../data/discover/archiveResearchWave01.json";
import wave02 from "../../data/discover/archiveResearchWave02.json";
import wave03 from "../../data/discover/archiveResearchWave03.json";
import wave04 from "../../data/discover/archiveResearchWave04.json";
import research from "../../data/discover/archiveResearchWave05.json";
import archive from "../../data/discover/institutionalArchive.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverEditorialCalendarAudit } from "../../features/discover/discoverEditorialCalendarAudit";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getDiscoverTemporalRank } from "./discoverTemporalSelection";

const OSMER = "institutional-archive-osmer-previsioni-fax-1991";
const ALPEGGIO = "institutional-archive-carnia-alpeggio-fieno-inverno";
const GHIACCIAIE = "institutional-archive-carso-ghiacciaie-pietra";
const IDS = [OSMER, ALPEGGIO, GHIACCIAIE];
const SOURCES = {
  [OSMER]: "https://www.arpa.fvg.it/temi/temi/meteo-e-clima/ultimi-approfondimenti-pubblicati/losservatorio-meteorologico-regionale-di-arpa-fvg-evoluzione-dei-servizi-e-della-comunicazione-in-ambito-meteo-climatico/",
  [ALPEGGIO]: "https://museocarnico.it/it/esplora/la-malga/alpeggio/",
  [GHIACCIAIE]: "https://comune.duino-aurisina.ts.it/media/files/032001/attachment/Living_Landscape_Manuale_per_la_gestione_ed_il_recupero_del_paesaggio_cult..._Carso.pdf",
};
const PRESERVED_DIGEST = "3ed64fd1dc30322cd96d8805bceb75485760ecf1ed384d65de541b3179e64914";
const runtimeById = new Map(archive.map((record) => [record.id, record]));

describe("discover archive wave 05", () => {
  it("appends three climate-and-work stories without changing the first 26 records", () => {
    expect(createHash("sha256").update(JSON.stringify(archive.slice(0, 26))).digest("hex"))
      .toBe(PRESERVED_DIGEST);
    expect(archive.slice(26, 29).map(({ id }) => id)).toEqual(IDS);
    expect(research.preservedCatalog).toEqual({ records: 26, sha256Json: PRESERVED_DIGEST });
    expect(new Set(culturalRecords.map(({ id }) => id)).size).toBe(culturalRecords.length);
    const prior = [...wave01.records, ...wave02.records, ...wave03.records, ...wave04.records];
    research.records.forEach((candidate) => {
      expect(prior.some(({ id, canonicalKey }) => (
        id === candidate.id || canonicalKey === candidate.canonicalKey
      ))).toBe(false);
      expect(culturalRecords.filter(({ canonicalKey }) => canonicalKey === candidate.canonicalKey))
        .toHaveLength(1);
      expect(candidate.duplicateReview).toMatchObject({ status: "distinct", note: expect.any(String) });
      expect(candidate.duplicateReview.comparedCatalogs).toEqual(expect.arrayContaining([
        "ostermannCulturalDiscover", "institutionalRituals", "institutionalArchive",
        "localMemory", "municipalityProfiles", "archiveResearchWave04",
      ]));
    });
  });

  it("keeps research metadata hidden and bilingual copy only in the runtime catalog", () => {
    expect(research).toMatchObject({
      schemaVersion: 1, snapshotDate: "2026-09-01", readyForUi: false,
      runtimeCatalog: "frontend/src/data/discover/institutionalArchive.json",
    });
    expect(research.records.map(({ promotedRecordId }) => promotedRecordId)).toEqual(IDS);
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      expect(candidate).toMatchObject({
        rubric: "archive_traditions", reviewStatus: "promoted", readyForUi: false,
        promotedAt: "2026-09-01",
      });
      expect(runtime).toMatchObject({
        sourceId: candidate.id, candidateId: candidate.id, canonicalKey: candidate.canonicalKey,
        section: "archivio_tradizioni", priority: 8,
        editorialStatus: "ready_it", languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true, areas: candidate.geographicScope,
      });
      ["title", "text", "draftCopy"].forEach((field) => expect(candidate).not.toHaveProperty(field));
      expect(isCuratedDiscoverUiReady(candidate)).toBe(false);
      expect(isCuratedDiscoverPublished(runtime)).toBe(true);
      expect(culturalRecords.filter(({ sourceId }) => sourceId === candidate.id)).toHaveLength(1);
      expect(culturalRecords.some(({ id }) => id === candidate.id)).toBe(false);
      [runtime.title, runtime.text, runtime.appShort].forEach((copy) => {
        expect(copy.it).toBeTruthy();
        expect(copy.fur).toBeTruthy();
        expect(copy.fur).not.toBe(copy.it);
      });
      ["it", "fur"].forEach((language) => {
        expect(runtime.text[language].split(/\s+/).length).toBeLessThanOrEqual(55);
      });
    });
  });

  it("retains the three primary sources and reuses no source media", () => {
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      expect(candidate.source).toMatchObject({
        url: SOURCES[runtime.id], checkedAt: "2026-09-01",
      });
      expect(["direct_html", "search_cached_primary_html", "direct_pdf_text_page_53"])
        .toContain(candidate.source.accessMethod);
      expect(runtime.source).toMatchObject({
        url: candidate.source.url, label: expect.any(String), checkedAt: "2026-09-01",
      });
      expect(runtime.source.rightsNote).toMatch(/nessuna/i);
      expect(runtime.sourceStatus).toBe("controllato");
      expect(runtime.sourceNote).toBeTruthy();
      ["imageUrl", "videoUrl", "media"].forEach((field) => expect(runtime).not.toHaveProperty(field));
    });
    expect(runtimeById.get(OSMER).source.type).toBe("institutional_publication");
    expect(runtimeById.get(ALPEGGIO).source.type).toBe("institutional_museum");
    expect(runtimeById.get(GHIACCIAIE).source.type).toBe("institutional_publication");
  });

  it("records assisted FUR review without claiming certification or independent approval", () => {
    expect(research.editorialDecision).toMatchObject({
      basis: "user_delegated_assisted_editorial_review", reviewer: "assistant",
      independentHumanReview: false, scope: research.records.map(({ id }) => id),
    });
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      expect(candidate.languageReview).toMatchObject({
        approvalBasis: "user_delegated_assisted_editorial_review", reviewer: "assistant",
        independentHumanReview: false, referencesLocation: `${runtime.id}.languageReview.fur.references`,
      });
      const review = runtime.languageReview.fur;
      expect(review).toMatchObject({
        approvalBasis: "user_delegated_assisted_editorial_review",
        reviewMethod: "assisted_standard_reference_review", reviewer: "assistant",
        independentHumanReview: false, approvedAt: "2026-09-01",
      });
      expect(review.approvalNote).toMatch(/non approvazione dell'utente frase per frase/i);
      expect(review.approvalNote).toMatch(/non certificazione ARLeF/i);
      expect(review.references.length).toBeGreaterThanOrEqual(8);
      review.references.forEach((reference) => {
        expect(new URL(reference.url).hostname).toBe("superdizionari.arlef.it");
        expect(reference.accessMethod).toBe("direct_http_html");
      });
    });
  });

  it("keeps historical climate context distinct from current weather, visits and anniversaries", () => {
    const osmer = runtimeById.get(OSMER);
    const alpeggio = runtimeById.get(ALPEGGIO);
    const ghiacciaie = runtimeById.get(GHIACCIAIE);
    expect(osmer).toMatchObject({ type: "storia_locale", areas: ["friuli_venezia_giulia"] });
    expect(osmer.text.it).toMatch(/25 giugno 1991/);
    expect(osmer.text.it).toMatch(/Centro Meteorologico dell’ERSA, predecessore dell’OSMER/);
    expect(osmer.text.it).toMatch(/disegnate a mano/);
    expect(alpeggio).toMatchObject({ type: "vita_quotidiana", areas: ["carnia"] });
    expect(alpeggio.text.it).toMatch(/risorsa comunitaria/);
    expect(alpeggio.text.it).toMatch(/fieno/);
    expect(ghiacciaie).toMatchObject({
      type: "vita_quotidiana", areas: ["carso", "carso_triestino"],
    });
    expect(ghiacciaie.text.it).toMatch(/strutture in pietra/);
    expect(ghiacciaie.text.it).toMatch(/terreni privati/);
    expect(ghiacciaie.sourceNote).toMatch(/non invita a entrare/i);
    IDS.forEach((id) => {
      const runtime = runtimeById.get(id);
      expect(runtime).toMatchObject({
        recurrence: "always", seasons: ["all"], weatherTags: [],
        dateAnchors: [], dateRanges: [], movableDates: [], movableDateRanges: [],
      });
      ["2028-01-01", "2028-02-29", "2028-06-25", "2028-12-31"].forEach((date) => {
        expect(getDiscoverTemporalRank(runtime, date)).toBe(4);
      });
    });
  });

  it.each(["it", "fur"])("renders every wave-05 card in the actual 2028 %s rotation", (language) => {
    const audit = buildDiscoverEditorialCalendarAudit({ year: 2028, language });
    const previousAudit = buildDiscoverEditorialCalendarAudit({
      year: 2028, language, sourceRecords: culturalRecords.filter(({ id }) => !IDS.includes(id)),
    });
    const otherRubrics = (row) => ({
      date: row.date, memory: row.memory, secondaryMemories: row.secondaryMemories,
      ritual: row.ritual, saying: row.saying,
    });
    expect(audit.rows.map(otherRubrics)).toEqual(previousAudit.rows.map(otherRubrics));
    expect(audit.summary.archive.usedIds).toEqual(expect.arrayContaining(IDS));
    expect(audit.summary.archive.daysShown).toBe(366);
    expect(audit.summary.archive.longestConsecutiveRepeat.days).toBeLessThanOrEqual(2);
    expect(audit.summary.visibleCollisions).toEqual([]);
    expect(audit.summary.exactDatePrecedenceViolations).toEqual([]);
    IDS.forEach((id) => {
      const runtime = runtimeById.get(id);
      const day = audit.rows.find((row) => row.archive?.id === id);
      expect(day).toBeTruthy();
      const model = buildDiscoverViewModel({
        language, today: day.date,
        location: { city: "Pordenone", province: "Pordenone", region: "Friuli Venezia Giulia" },
      });
      const card = model.sections.find(({ id: sectionId }) => sectionId === "archive").cards[0];
      expect(card).toMatchObject({
        id, title: runtime.title[language], text: runtime.text[language],
        sourceLabel: runtime.source.label, isFurPending: false,
      });
      const html = renderToStaticMarkup(createElement(DiscoverCard, { card }));
      expect(html).toContain(renderToStaticMarkup(createElement("h2", null, runtime.title[language])));
      expect(html).toContain(renderToStaticMarkup(createElement("p", null, runtime.text[language])));
      expect(html).toContain(renderToStaticMarkup(createElement("small", null, runtime.source.label)));
    });
  }, 15_000);
});
