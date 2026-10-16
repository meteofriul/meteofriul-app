import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import wave01 from "../../data/discover/archiveResearchWave01.json";
import wave02 from "../../data/discover/archiveResearchWave02.json";
import wave03 from "../../data/discover/archiveResearchWave03.json";
import research from "../../data/discover/archiveResearchWave04.json";
import archive from "../../data/discover/institutionalArchive.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverEditorialCalendarAudit } from "../../features/discover/discoverEditorialCalendarAudit";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getDiscoverTemporalRank } from "./discoverTemporalSelection";

const MANIAGO = "institutional-archive-maniago-maglio-ascolto";
const PESARIIS = "institutional-archive-pesariis-orologi-portici";
const OPICINA = "institutional-archive-opicina-tram-funicolare";
const IDS = [MANIAGO, PESARIIS, OPICINA];
const SOURCES = {
  [MANIAGO]: "https://patrimonioculturale.regione.fvg.it/patrimonio-scientifico-tecnologico/?s_id=597151",
  [PESARIIS]: "https://cultura.gov.it/luogo/museo-dell-orologeria-pesarina",
  [OPICINA]: "https://tplfvg.it/it/servizi/tramopicina/",
};
const PRESERVED_DIGEST = "a33c0a3cfd40008ebe12ca8763c22ecfc23ef5ddb485ebd2e602e73d4ff08bfe";
const runtimeById = new Map(archive.map((record) => [record.id, record]));

describe("discover archive wave 04", () => {
  it("appends three distinct material-culture cards without changing the first 23", () => {
    expect(createHash("sha256").update(JSON.stringify(archive.slice(0, 23))).digest("hex"))
      .toBe(PRESERVED_DIGEST);
    expect(archive.slice(23, 26).map(({ id }) => id)).toEqual(IDS);
    expect(research.preservedCatalog).toEqual({ records: 23, sha256Json: PRESERVED_DIGEST });
    expect(new Set(culturalRecords.map(({ id }) => id)).size).toBe(culturalRecords.length);
    const prior = [...wave01.records, ...wave02.records, ...wave03.records];
    research.records.forEach((candidate) => {
      expect(prior.some(({ id, canonicalKey }) => (
        id === candidate.id || canonicalKey === candidate.canonicalKey
      ))).toBe(false);
      expect(culturalRecords.filter(({ canonicalKey }) => canonicalKey === candidate.canonicalKey))
        .toHaveLength(1);
      expect(candidate.duplicateReview).toMatchObject({ status: "distinct", note: expect.any(String) });
      expect(candidate.duplicateReview.comparedCatalogs).toEqual(expect.arrayContaining([
        "ostermannCulturalDiscover", "institutionalRituals", "institutionalArchive",
        "localMemory", "municipalityProfiles", "archiveResearchWave03",
      ]));
    });
  });

  it("keeps the research manifest hidden and the bilingual copy in the runtime catalog only", () => {
    expect(research).toMatchObject({
      schemaVersion: 1, snapshotDate: "2026-08-31", readyForUi: false,
      runtimeCatalog: "frontend/src/data/discover/institutionalArchive.json",
    });
    expect(research.records.map(({ promotedRecordId }) => promotedRecordId)).toEqual(IDS);
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      expect(candidate).toMatchObject({
        rubric: "archive_traditions", reviewStatus: "promoted", readyForUi: false,
        promotedAt: "2026-08-31",
      });
      expect(runtime).toMatchObject({
        sourceId: candidate.id, candidateId: candidate.id, canonicalKey: candidate.canonicalKey,
        section: "archivio_tradizioni", type: "vita_quotidiana", priority: 8,
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

  it("retains primary source identity, checked HTML access and original text without media reuse", () => {
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      expect(candidate.source).toMatchObject({
        url: SOURCES[runtime.id], checkedAt: "2026-08-31",
      });
      expect(["direct_html", "direct_http_html"]).toContain(candidate.source.accessMethod);
      expect(runtime.source).toMatchObject({
        url: candidate.source.url, label: expect.any(String), checkedAt: "2026-08-31",
      });
      expect(runtime.source.rightsNote).toMatch(/nessuna immagine/i);
      expect(runtime.sourceStatus).toBe("controllato");
      expect(runtime.sourceNote).toBeTruthy();
      ["imageUrl", "videoUrl", "media"].forEach((field) => expect(runtime).not.toHaveProperty(field));
    });
    expect(runtimeById.get(MANIAGO).source.type).toBe("institutional_catalogue");
    expect(runtimeById.get(PESARIIS).source.type).toBe("institutional_museum");
    expect(runtimeById.get(OPICINA).source).toMatchObject({
      type: "public_transport_operator", label: "TPL FVG · Tram di Opicina",
    });
  });

  it("records assisted language review without claiming ARLeF certification or human approval", () => {
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
        independentHumanReview: false, approvedAt: "2026-08-31",
      });
      expect(review.approvalNote).toMatch(/non approvazione dell'utente frase per frase/i);
      expect(review.approvalNote).toMatch(/non certificazione ARLeF/i);
      expect(review.references.length).toBeGreaterThan(0);
      review.references.forEach((reference) => {
        expect(new URL(reference.url).hostname).toBe("superdizionari.arlef.it");
        expect(reference.accessMethod).toBe("direct_http_html");
        expect(new URL(reference.url).protocol).toBe("https:");
      });
    });
  });

  it("keeps the mechanics and historical use specific, without invented anniversaries or timetables", () => {
    const maniago = runtimeById.get(MANIAGO);
    const pesariis = runtimeById.get(PESARIIS);
    const opicina = runtimeById.get(OPICINA);
    expect(maniago.areas).toEqual(["maniago"]);
    expect(maniago.text.it).toMatch(/lamina si rompeva/);
    expect(maniago.text.it).toMatch(/rumore/);
    expect(pesariis.areas).toEqual(["prato_carnico", "pesariis", "carnia"]);
    expect(pesariis.text.it).toContain("alcune famiglie");
    expect(pesariis.text.it).toContain("Seicento");
    expect(pesariis.text.it).toContain("lavori agricoli");
    expect(opicina.areas).toEqual(["trieste", "opicina", "carso"]);
    expect(opicina.text.it).toContain("circa 800 metri");
    expect(opicina.text.it).toContain("spinte o trattenute");
    expect(opicina.text.fur).toContain("«carri-scudo»");
    expect(opicina.text.it).not.toMatch(/\b(?:unico|riapert\w*|riattivat\w*|2025|1902|bigliett\w*|orari)\b/i);
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      expect(candidate.temporalRule).toEqual({ type: "annual_rotation" });
      expect(runtime).toMatchObject({
        recurrence: "always", seasons: ["all"], weatherTags: [],
        dateAnchors: [], dateRanges: [], movableDates: [], movableDateRanges: [],
      });
      ["2028-01-01", "2028-02-29", "2028-07-01", "2028-12-31"].forEach((date) => {
        expect(getDiscoverTemporalRank(runtime, date)).toBe(4);
      });
    });
  });

  it.each(["it", "fur"])("renders the three cards and sources in the actual 2028 %s rotation", (language) => {
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
  }, 15_000); // Two complete annual simulations per language, also during parallel full-suite runs.
});
