import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import proverbs from "../../data/almanac/proverbs.json";
import reuse from "../../data/discover/traditionalSayingAlmanacReuse.json";
import research from "../../data/discover/traditionalSayingReuseWave04.json";
import dedicated from "../../data/discover/traditionalSayings.json";
import backlog from "../../data/discover/editorialExpansionBacklog.json";
import culturalRecords from "./discoverCulturalRecords";
import { getDiscoverTemporalRank, pickDiscoverTemporalRecord } from "./discoverTemporalSelection";
import { getTraditionalSayingForDate, getTraditionalSayingRecords } from "./traditionalSayings";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";

const NEW_IDS = [
  "ost1876-nolis-panolis",
  "ost1876-altris-timps-altris-usancis",
  "ost1876-scove-denant-puarte",
  "ost1876-pan-sudat-no-robat",
  "ost1876-cite-mani",
];
const records = getTraditionalSayingRecords();
const oldRecords = records.filter(({ candidateId }) => !NEW_IDS.includes(candidateId));
const hash = (value) => createHash("sha256").update(JSON.stringify(value)).digest("hex");
const normalize = (value) => String(value || "")
  .normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "")
  .replace(/[^a-z0-9]+/gi, " ")
  .trim()
  .toLowerCase();
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

describe("Scopri saying reuse wave 04", () => {
  it("adds five references to approved copy without adding translations or temporal claims", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      batchId: "traditional-saying-reuse-wave-04",
      snapshotDate: "2026-09-01",
      readyForUi: false,
      authoritativeCatalog: "frontend/src/data/almanac/proverbs.json",
      runtimeDescriptorCatalog: "frontend/src/data/discover/traditionalSayingAlmanacReuse.json",
      editorialDecision: {
        scope: "reuse_existing_approved_copy_only",
        independentHumanReview: false,
      },
      temporalRule: { recurrence: "always", selectionKind: "rotation" },
    });
    expect(research.records.map(({ proverbId }) => proverbId)).toEqual(NEW_IDS);
    expect(reuse.records.filter(({ proverbId }) => NEW_IDS.includes(proverbId)).map(({ proverbId }) => proverbId))
      .toEqual(NEW_IDS);
    expect(records).toHaveLength(80);
    expect(new Set(records.map(({ id }) => id)).size).toBe(80);
    expect(new Set(records.map(({ candidateId }) => candidateId)).size).toBe(80);
    expect(reuse.records).toHaveLength(69);
    expect(oldRecords).toHaveLength(75);
  });

  it("preserves the Almanacco, dedicated sayings and all 64 prior descriptors", () => {
    const priorDescriptors = reuse.records.filter(({ proverbId }) => !NEW_IDS.includes(proverbId));
    expect(hash(proverbs)).toBe("fc6d44d1636cc9c3eaa6aeb7e8fefcdba88cf35f4ba51173ef52dd15176169d6");
    expect(hash(dedicated)).toBe("2815007a540341eb22de796fa0d2ecc156da9c764c0a5bf9d41c5a9e169c7f1a");
    expect(hash(priorDescriptors)).toBe("2b689e2d09b86dd8f383a99507069d74c541a836f5f2c7b760943a7ea2d10684");
    expect(research.preservedCatalog).toEqual({ records: 379, sha256Json: hash(proverbs) });
    expect(research.preservedDedicatedCatalog).toEqual({ records: 11, sha256Json: hash(dedicated) });
    expect(research.preservedDescriptors).toEqual({ records: 64, sha256Json: hash(priorDescriptors) });
  });

  it.each(NEW_IDS)("reuses %s verbatim and inherits its existing IT/FUR approval", (proverbId) => {
    const proverb = proverbs.find(({ id }) => id === proverbId);
    const descriptor = reuse.records.find((record) => record.proverbId === proverbId);
    const candidate = research.records.find((record) => record.proverbId === proverbId);
    const matches = records.filter(({ candidateId }) => candidateId === proverbId);

    expect(proverb).toMatchObject({
      almanacEligible: true,
      normalizationStatus: "lab_ready",
      editorialReview: { it: "approved", fur: "approved" },
    });
    expect(matches).toHaveLength(1);
    expect(matches[0]).toMatchObject({
      title: { it: proverb.it, fur: proverb.fur },
      summary: { it: "", fur: "" },
      original: { it: proverb.it, fur: proverb.fur_original || proverb.fur },
      recurrence: "always",
      dateAnchors: [],
      dateRanges: [],
      months: [],
      seasons: [],
      movableDates: [],
      source: {
        label: "Ostermann 1876",
        verifiedAgainst: proverb.source,
        pdfPage: candidate.sourceReference.pdfPage,
      },
      editorialReview: { reviewedAt: proverb.editorialReview.reviewedAt },
      reusedFromAlmanac: true,
      readyForUi: true,
    });
    expect(candidate).toMatchObject({
      sourceReference: { citation: proverb.source, edition: 1876 },
      existingEditorialReviewAt: proverb.editorialReview.reviewedAt,
    });
    expect(candidate.theme.trim()).toBeTruthy();
    expect(candidate.reason.trim()).toBeTruthy();
    expect(candidate).not.toHaveProperty("title");
    expect(candidate).not.toHaveProperty("summary");
    expect(descriptor).not.toHaveProperty("it");
    expect(descriptor).not.toHaveProperty("fur");
    for (const key of ["dateAnchors", "dateRanges", "months", "seasons", "movableDates", "weatherTags", "lunarPhases", "territories"]) {
      expect(descriptor[key] || []).toEqual([]);
    }
    expect(culturalRecords.some(({ id, candidateId }) => id === proverbId || candidateId === proverbId)).toBe(false);
  });

  it("does not add an exact or normalized text duplicate of the prior repertoire", () => {
    for (const proverbId of NEW_IDS) {
      const proverb = proverbs.find(({ id }) => id === proverbId);
      expect(oldRecords.some((record) => (
        normalize(record.title.it) === normalize(proverb.it)
        || normalize(record.title.fur) === normalize(proverb.fur)
      ))).toBe(false);
    }
  });

  it.each([2026, 2027, 2028, 2029, 2030, 2031])("uses all 80 sayings in %i without displacing precise rules", (year) => {
    const rows = getYearSelections(year);
    expect(rows).toHaveLength(year === 2028 ? 366 : 365);
    expect(new Set(rows.map(({ record }) => record.id))).toEqual(new Set(records.map(({ id }) => id)));
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

  it.each(["it", "fur"])("renders every addition in %s through the actual Scopri view model", (language) => {
    const rows = getYearSelections(2028);
    for (const proverbId of NEW_IDS) {
      const proverb = proverbs.find(({ id }) => id === proverbId);
      const date = rows.find(({ record }) => record.candidateId === proverbId).date;
      const model = buildDiscoverViewModel({
        language,
        today: date,
        location: { city: "Pordenone", istatCode: "093033" },
      });
      const cards = model.sections.find(({ id }) => id === "traditional-sayings").cards;
      expect(cards).toHaveLength(1);
      expect(cards[0]).toMatchObject({
        id: `saying-almanac-${proverbId}`,
        title: proverb[language],
        text: "",
        sourceLabel: "Ostermann 1876",
        selectionKind: "rotation",
        isFurPending: false,
      });
      expect(getTraditionalSayingForDate({ language, date })).toMatchObject(cards[0]);
      const html = renderToStaticMarkup(createElement(DiscoverCard, { card: cards[0] }));
      expect(html).toContain(renderToStaticMarkup(createElement("h2", null, proverb[language])));
      expect(html).toContain("<small>Ostermann 1876</small>");
    }
  });

  it("tracks the batch and the expanded repertoire without changing exact dates", () => {
    const record = backlog.records.find(({ id }) => id === "traditional-sayings-variety");
    expect(record.currentSnapshot).toEqual({
      catalogRecords: 80,
      dedicatedDiscoverRecords: 11,
      reusedAlmanacRecords: 69,
      exactDateRecords: 8,
      daysShownIn2028: 366,
      recordsUsedIn2028: 80,
      unusedEligibleRecords: 0,
      longestConsecutiveRepeatDays: 2,
    });
    expect(record.latestEditorialBatch).toEqual({
      batchId: research.batchId,
      manifest: "frontend/src/data/discover/traditionalSayingReuseWave04.json",
      reusedRecords: 5,
      copyChanged: false,
      almanacChanged: false,
    });
  });
});
