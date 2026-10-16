import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import researchWave01 from "../../data/discover/archiveResearchWave01.json";
import researchWave02 from "../../data/discover/archiveResearchWave02.json";
import research from "../../data/discover/archiveResearchWave03.json";
import archive from "../../data/discover/institutionalArchive.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverEditorialCalendarAudit } from "../../features/discover/discoverEditorialCalendarAudit";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getDiscoverTemporalRank } from "./discoverTemporalSelection";

const ARROTINI_ID = "institutional-archive-arrotini-bicicletta-stolvizza";
const TORCITOIO_ID = "institutional-archive-torcitoio-seta-gorizia";
const CASONI_ID = "institutional-archive-casoni-porta-ovest-grado";
const PROMOTIONS = {
  "archive-research-arrotini-bicicletta-stolvizza": ARROTINI_ID,
  "archive-research-torcitoio-seta-gorizia": TORCITOIO_ID,
  "archive-research-casoni-porta-ovest-grado": CASONI_ID,
};
const EXPECTED_SOURCES = {
  [ARROTINI_ID]: "https://cultura.gov.it/luogo/museo-dell-arrotino",
  [TORCITOIO_ID]: "https://www.go2025.eu/it/imports/poi/erpac/museo-della-moda-e-delle-arti-applicate",
  [CASONI_ID]: "https://grado.it/it/cosa-fare/natura/la-laguna-di-grado/i-casoni",
};
const PRESERVED_DIGEST = "fcf05f6cb692cb18f9ed3c5abe7ad2532a56e52da0bdec1fbfb2fecff1930aef";
const runtimeById = new Map(archive.map((record) => [record.id, record]));
const arrotini = runtimeById.get(ARROTINI_ID);
const torcitoio = runtimeById.get(TORCITOIO_ID);
const casoni = runtimeById.get(CASONI_ID);

describe("discover archive wave 03", () => {
  it("appends the three cards while preserving all twenty previous records byte-for-byte as JSON", () => {
    expect(createHash("sha256").update(JSON.stringify(archive.slice(0, 20))).digest("hex"))
      .toBe(PRESERVED_DIGEST);
    expect(archive.slice(20, 23).map((record) => record.id)).toEqual(Object.values(PROMOTIONS));
    expect(research.preservedCatalog).toEqual({ records: 20, sha256Json: PRESERVED_DIGEST });
    expect(new Set(culturalRecords.map((record) => record.id)).size).toBe(culturalRecords.length);
  });

  it("traces exactly three promotions in a compact manifest without duplicating visible copy", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      snapshotDate: "2026-08-31",
      readyForUi: false,
      runtimeCatalog: "frontend/src/data/discover/institutionalArchive.json",
    });
    expect(research.records.map((record) => record.id)).toEqual(Object.keys(PROMOTIONS));
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(PROMOTIONS[candidate.id]);
      expect(candidate).toMatchObject({
        promotedRecordId: runtime.id,
        rubric: "archive_traditions",
        reviewStatus: "promoted",
        readyForUi: false,
        promotedAt: "2026-08-31",
      });
      expect(runtime).toMatchObject({
        sourceId: candidate.id,
        candidateId: candidate.id,
        canonicalKey: candidate.canonicalKey,
        section: "archivio_tradizioni",
        type: "vita_quotidiana",
        priority: 8,
        editorialStatus: "ready_it",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
      expect(candidate.geographicScope).toEqual(runtime.areas);
      expect(candidate).not.toHaveProperty("draftCopy");
      expect(candidate).not.toHaveProperty("text");
      expect(candidate).not.toHaveProperty("title");
      expect(isCuratedDiscoverUiReady(candidate)).toBe(false);
      expect(isCuratedDiscoverPublished(runtime)).toBe(true);
      expect(culturalRecords.filter((record) => record.sourceId === candidate.id)).toHaveLength(1);
      expect(culturalRecords.some((record) => record.id === candidate.id)).toBe(false);
      [runtime.title, runtime.text, runtime.appShort].forEach((copy) => {
        expect(copy.it).toBeTruthy();
        expect(copy.fur).toBeTruthy();
        expect(copy.fur).not.toBe(copy.it);
      });
      expect(runtime.text.it.split(/\s+/).length).toBeGreaterThanOrEqual(30);
      expect(runtime.text.it.split(/\s+/).length).toBeLessThanOrEqual(55);
    });
  });

  it("retains exact primary HTML sources and identifies the Grado consortium honestly", () => {
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      expect(candidate.source).toMatchObject({
        url: EXPECTED_SOURCES[runtime.id], accessMethod: "direct_html", checkedAt: "2026-08-31",
      });
      expect(runtime.source).toMatchObject({
        url: candidate.source.url, label: expect.any(String), checkedAt: "2026-08-31",
      });
      expect(new URL(runtime.source.url).protocol).toBe("https:");
      expect(runtime.source.rightsNote).toMatch(/nessuna immagine/);
      expect(runtime.sourceStatus).toBe("controllato");
      expect(runtime.sourceNote).toBeTruthy();
      expect(runtime).not.toHaveProperty("imageUrl");
      expect(runtime).not.toHaveProperty("videoUrl");
      expect(runtime).not.toHaveProperty("media");
    });
    expect(casoni.source).toMatchObject({
      label: "Consorzio Grado Turismo · I casoni", type: "local_tourism_consortium",
    });
    expect(torcitoio.supportingSources).toEqual(expect.arrayContaining([
      expect.objectContaining({
        url: "https://cultura.gov.it/luogo/museo-della-moda-e-delle-arti-applicate",
      }),
    ]));
  });

  it("documents the assisted review without claiming human sentence approval or certification", () => {
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
        approvedAt: "2026-08-31",
      });
      expect(review.approvalNote).toMatch(/non approvazione dell'utente frase per frase/i);
      expect(review.approvalNote).toMatch(/non certificazione ARLeF/i);
      expect(review.references.length).toBeGreaterThan(0);
      review.references.forEach((reference) => {
        expect(new URL(reference.url).hostname).toMatch(/(^|\.)arlef\.it$/);
        expect(new URL(reference.url).protocol).toBe("https:");
        expect(reference.accessMethod).toBe("direct_http_html");
        expect(reference.url).not.toMatch(/\.pdf(?:$|\?)/);
      });
    });
    expect(torcitoio.text.fur).toContain("«torcitoio»");
    expect(casoni.text.fur).toContain("«casoni»");
    expect(casoni.text.fur).not.toContain("cjasament");
    expect(arrotini.text.fur).toContain("Val Resie");
  });

  it("keeps each material story specific, without a forced date or fabricated weather trigger", () => {
    expect(arrotini.areas).toEqual(["resia", "stolvizza"]);
    expect(arrotini.text.it).toContain("ferma sui cavalletti");
    expect(arrotini.text.it).toContain("con i pedali");
    expect(arrotini.text.it).not.toMatch(/motore|motorizzat|elettric/i);
    expect(torcitoio.areas).toEqual(["gorizia"]);
    expect(torcitoio.text.it).toContain("Settecento");
    expect(torcitoio.text.it).toContain("camminando all'indietro");
    expect(torcitoio.text.it).not.toMatch(/più antico|unico|primato/i);
    expect(casoni.areas).toEqual(["grado", "laguna_di_grado"]);
    expect(casoni.text.it).toContain("porta rivolta a Ovest");
    expect(casoni.text.it).toContain("venti orientali");
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

  it("avoids previous research identities and records the cross-catalog editorial distinction", () => {
    const earlierResearch = [...researchWave01.records, ...researchWave02.records];
    const earlierIds = new Set(earlierResearch.map((record) => record.id));
    const earlierKeys = new Set(earlierResearch.map((record) => record.canonicalKey));
    research.records.forEach((candidate) => {
      expect(earlierIds.has(candidate.id)).toBe(false);
      expect(earlierKeys.has(candidate.canonicalKey)).toBe(false);
      expect(culturalRecords.filter((record) => record.canonicalKey === candidate.canonicalKey))
        .toHaveLength(1);
      expect(candidate.duplicateReview).toMatchObject({ status: "distinct", note: expect.any(String) });
      expect(candidate.duplicateReview.comparedCatalogs).toEqual(expect.arrayContaining([
        "ostermannCulturalDiscover", "institutionalRituals", "institutionalArchive", "localMemory",
        "municipalityProfiles", "archiveResearchWave01", "archiveResearchWave02",
      ]));
    });
  });

  it.each(["it", "fur"])("renders all three cards and their source in the 2028 %s rotation", (language) => {
    const audit = buildDiscoverEditorialCalendarAudit({ year: 2028, language });
    expect(audit.summary.archive.usedIds).toEqual(expect.arrayContaining(Object.values(PROMOTIONS)));
    expect(audit.summary.archive.daysShown).toBe(366);
    expect(audit.summary.archive.longestConsecutiveRepeat.days).toBeLessThanOrEqual(2);
    expect(audit.summary.visibleCollisions).toEqual([]);
    expect(audit.summary.exactDatePrecedenceViolations).toEqual([]);
    Object.values(PROMOTIONS).forEach((id) => {
      const runtime = runtimeById.get(id);
      const selectedDay = audit.rows.find((row) => row.archive?.id === id);
      expect(selectedDay).toBeTruthy();
      const model = buildDiscoverViewModel({
        language,
        location: { city: "Pordenone", province: "Pordenone", region: "Friuli Venezia Giulia" },
        today: selectedDay.date,
      });
      const card = model.sections.find((section) => section.id === "archive").cards[0];
      expect(card).toMatchObject({
        id, title: runtime.title[language], text: runtime.text[language],
        sourceLabel: runtime.source.label, isFurPending: false,
      });
      const html = renderToStaticMarkup(createElement(DiscoverCard, { card }));
      expect(html).toContain(renderToStaticMarkup(createElement("h2", null, runtime.title[language])));
      expect(html).toContain(renderToStaticMarkup(createElement("p", null, runtime.text[language])));
      expect(html).toContain(renderToStaticMarkup(createElement("small", null, runtime.source.label)));
    });
  });
});
