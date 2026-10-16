import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import proverbs from "../../data/almanac/proverbs.json";
import reuse from "../../data/discover/traditionalSayingAlmanacReuse.json";
import research from "../../data/discover/traditionalSayingReuseWave03.json";
import dedicated from "../../data/discover/traditionalSayings.json";
import backlog from "../../data/discover/editorialExpansionBacklog.json";
import culturalRecords from "./discoverCulturalRecords";
import { getDiscoverTemporalRank, pickDiscoverTemporalRecord } from "./discoverTemporalSelection";
import { getTraditionalSayingForDate, getTraditionalSayingRecords } from "./traditionalSayings";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";

const NEW_IDS = [
  "ost1876-forment-ten-vend",
  "ost1876-prat-seat-no-scuindisi",
  "ost1876-bati-fier-cjald",
  "ost1876-dome-farine-no-pan",
  "ost1876-olei-ben-no-coste-nuje",
  "ost1876-ducj-sanc-ros",
  "ost1876-cognossi-mangja-star-sal",
  "ost1876-prometi-mantigni",
  "ost1876-gotis-spessis-forin-clap",
  "ost1876-cuatri-voi-plui-doi",
  "ost1876-mior-pleasi-scjavacasi",
  "ost1876-da-timp-al-timp",
];
const records = getTraditionalSayingRecords();
const oldRecords = records.filter(({ candidateId }) => !NEW_IDS.includes(candidateId));
const hash = (value) => createHash("sha256").update(JSON.stringify(value)).digest("hex");
const annualSelections = new Map();

function getYearSelections(year) {
  if (!annualSelections.has(year)) {
    const rows = [];
    for (let cursor = Date.UTC(year, 0, 1); cursor < Date.UTC(year + 1, 0, 1); cursor += 86400000) {
      const date = new Date(cursor).toISOString().slice(0, 10);
      rows.push({ date, record: pickDiscoverTemporalRecord(records, date, { blendBroader: true }) });
    }
    annualSelections.set(year, rows);
  }
  return annualSelections.get(year);
}

describe("Scopri saying reuse wave 03", () => {
  it("adds only twelve references to approved copy, not new translations or calendar claims", () => {
    expect(research).toMatchObject({
      schemaVersion: 1, batchId: "traditional-saying-reuse-wave-03", snapshotDate: "2026-08-31",
      readyForUi: false, authoritativeCatalog: "frontend/src/data/almanac/proverbs.json",
      runtimeDescriptorCatalog: "frontend/src/data/discover/traditionalSayingAlmanacReuse.json",
      editorialDecision: { scope: "reuse_existing_approved_copy_only", independentHumanReview: false },
      temporalRule: { recurrence: "always", selectionKind: "rotation" },
    });
    expect(research.records.map(({ proverbId }) => proverbId)).toEqual(NEW_IDS);
    expect(reuse.records.filter(({ proverbId }) => NEW_IDS.includes(proverbId)).map(({ proverbId }) => proverbId))
      .toEqual(NEW_IDS);
    expect(new Set(records.map(({ candidateId }) => candidateId)).size).toBe(records.length);
    expect(reuse.records.filter(({ proverbId }) => NEW_IDS.includes(proverbId))).toHaveLength(12);
    expect(oldRecords).toHaveLength(records.length - NEW_IDS.length);
    for (const candidate of research.records) {
      const proverb = proverbs.find(({ id }) => id === candidate.proverbId);
      expect(candidate.theme.trim()).toBeTruthy();
      expect(candidate.reason.trim()).toBeTruthy();
      expect(candidate.sourceReference).toMatchObject({ citation: proverb.source, edition: 1876 });
      expect(candidate.existingEditorialReviewAt).toBe(proverb.editorialReview.reviewedAt);
      expect(candidate).not.toHaveProperty("title");
      expect(candidate).not.toHaveProperty("summary");
      expect(candidate).not.toHaveProperty("labelFur");
    }
  });

  it("preserves the full Almanacco catalog, all dedicated sayings and the original 52 descriptors", () => {
    expect(hash(proverbs)).toBe("fc6d44d1636cc9c3eaa6aeb7e8fefcdba88cf35f4ba51173ef52dd15176169d6");
    expect(hash(dedicated)).toBe("2815007a540341eb22de796fa0d2ecc156da9c764c0a5bf9d41c5a9e169c7f1a");
    const priorDescriptors = reuse.records.slice(0, research.preservedDescriptors.records);
    expect(hash(priorDescriptors)).toBe("894c51de12d2051dd7e172604b803debc312419469935aaf4007a8a41074b449");
    expect(research.preservedCatalog).toMatchObject({ records: 379, sha256Json: hash(proverbs) });
    expect(research.preservedDescriptors).toMatchObject({ records: 52, sha256Json: hash(priorDescriptors) });
  });

  it.each(NEW_IDS)("reuses %s verbatim, with inherited approval and no invented temporal context", (proverbId) => {
    const proverb = proverbs.find(({ id }) => id === proverbId);
    const matches = records.filter(({ candidateId }) => candidateId === proverbId);
    const descriptor = reuse.records.find((record) => record.proverbId === proverbId);
    expect(matches).toHaveLength(1);
    expect(proverb).toMatchObject({ almanacEligible: true, editorialReview: { it: "approved", fur: "approved" } });
    expect(matches[0]).toMatchObject({
      title: { it: proverb.it, fur: proverb.fur }, summary: { it: "", fur: "" },
      original: { it: proverb.it, fur: proverb.fur_original || proverb.fur },
      recurrence: "always", dateAnchors: [], dateRanges: [], months: [], seasons: [], movableDates: [],
      source: { label: "Ostermann 1876", verifiedAgainst: proverb.source },
      editorialReview: { reviewedAt: proverb.editorialReview.reviewedAt },
      reusedFromAlmanac: true, readyForUi: true,
    });
    for (const key of ["dateAnchors", "dateRanges", "months", "monthAnchors", "seasons", "movableFeasts", "weatherTags", "lunarPhases"]) {
      expect(proverb[key] || []).toEqual([]);
      expect(descriptor[key] || []).toEqual([]);
    }
    expect(descriptor).not.toHaveProperty("it");
    expect(descriptor).not.toHaveProperty("fur");
    expect(culturalRecords.some(({ id, candidateId }) => id === proverbId || candidateId === proverbId)).toBe(false);
    expect(getDiscoverTemporalRank(matches[0], "2028-01-01")).toBe(4);
    expect(getDiscoverTemporalRank(matches[0], "2028-07-01")).toBe(4);
    expect(matches[0].source.pdfPage).toBe(research.records.find((record) => record.proverbId === proverbId).sourceReference.pdfPage);
  });

  it.each([2026, 2027, 2028, 2029, 2030, 2031])("uses the full repertoire in %i without displacing exact or movable dates", (year) => {
    const rows = getYearSelections(year);
    expect(rows).toHaveLength(year === 2028 ? 366 : 365);
    const used = new Set(rows.map(({ record }) => record.id));
    expect(used).toEqual(new Set(records.map(({ id }) => id)));
    let lastId = null;
    let consecutive = 0;
    for (const { date, record } of rows) {
      expect(record).toBeTruthy();
      consecutive = record.id === lastId ? consecutive + 1 : 1;
      expect(consecutive).toBeLessThanOrEqual(2);
      lastId = record.id;
      const before = pickDiscoverTemporalRecord(oldRecords, date, { blendBroader: true });
      if (getDiscoverTemporalRank(before, date) < 2) expect(record.id).toBe(before.id);
    }
  });

  it.each(["it", "fur"])("renders every addition in %s through the actual daily view model", (language) => {
    const rows = getYearSelections(2028);
    for (const proverbId of NEW_IDS) {
      const proverb = proverbs.find(({ id }) => id === proverbId);
      const date = rows.find(({ record }) => record.candidateId === proverbId).date;
      const model = buildDiscoverViewModel({ language, today: date, location: { city: "Pordenone", istatCode: "093033" } });
      const cards = model.sections.find(({ id }) => id === "traditional-sayings").cards;
      expect(cards).toHaveLength(1);
      expect(cards[0]).toMatchObject({
        id: `saying-almanac-${proverbId}`, title: proverb[language], text: "", sourceLabel: "Ostermann 1876",
        selectionKind: "rotation", isFurPending: false,
      });
      expect(getTraditionalSayingForDate({ language, date })).toMatchObject(cards[0]);
      const html = renderToStaticMarkup(createElement(DiscoverCard, { card: cards[0] }));
      expect(html).toContain(renderToStaticMarkup(createElement("h2", null, proverb[language])));
      expect(html).toContain("<small>Ostermann 1876</small>");
    }
  });

  it("shows the corrected 1894 credit in the actual card, not just internal metadata", () => {
    const card = getTraditionalSayingForDate({ date: "2028-09-01", language: "fur" });
    expect(card).toMatchObject({ id: "saying-almanac-ostermann-063-sant-egidi-color-mes", sourceLabel: "Ostermann 1894" });
    expect(renderToStaticMarkup(createElement(DiscoverCard, { card }))).toContain("<small>Ostermann 1894</small>");
  });

  it("keeps the historical batch trace after later expansions", () => {
    const record = backlog.records.find(({ id }) => id === "traditional-sayings-variety");
    expect(record.currentSnapshot.exactDateRecords).toBe(8);
    expect(record.precedingEditorialBatch).toEqual({
      batchId: research.batchId, manifest: "frontend/src/data/discover/traditionalSayingReuseWave03.json",
      reusedRecords: 12, copyChanged: false, almanacChanged: false,
    });
  });
});
