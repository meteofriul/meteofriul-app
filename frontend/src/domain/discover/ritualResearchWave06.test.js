import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import institutionalRituals from "../../data/discover/institutionalRituals.json";
import localMemory from "../../data/discover/localMemory.json";
import research from "../../data/discover/ritualResearchWave06.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getDiscoverTemporalRank } from "./discoverTemporalSelection";

const EXPECTED = [
  [
    "ritual-research-grado-perdon-barbana",
    "institutional-ritual-grado-perdon-barbana",
    { month: 7, weekday: 0, ordinal: 1 },
    "https://grado.it/it/eventi-ed-escursioni/grandi-eventi/sabo-grando-e-perdon-di-barbana",
  ],
  [
    "ritual-research-fagagna-trebbiatura",
    "institutional-ritual-fagagna-trebbiatura",
    { month: 7, weekday: 0, ordinal: 2 },
    "https://www.prolocofagagna.it/festa-della-rebbiatura/",
  ],
];
const JULY_SUNDAYS = [
  [2026, "07-05", "07-12"],
  [2027, "07-04", "07-11"],
  [2028, "07-02", "07-09"],
  [2029, "07-01", "07-08"],
  [2030, "07-07", "07-14"],
  [2031, "07-06", "07-13"],
];
const records = EXPECTED.map(([, id]) => institutionalRituals.find((record) => record.id === id));
const location = { city: "Pordenone", province: "Pordenone", region: "Friuli Venezia Giulia" };

function ritualCard(today, language, city = location) {
  return buildDiscoverViewModel({ today, language, location: city })
    .sections.find((section) => section.id === "rituals")?.cards[0];
}

describe("ritual research wave 06", () => {
  it("preserves the thirteen earlier records and appends exactly the two reviewed July traditions", () => {
    expect(createHash("sha256").update(JSON.stringify(institutionalRituals.slice(0, 13))).digest("hex"))
      .toBe("7aa488140d0b7bbf25a6432640a355646adec0facd2935ab05028d5759ae1e79");
    expect(institutionalRituals.slice(13, 15).map(({ id }) => id)).toEqual(EXPECTED.map(([, id]) => id));
    expect(new Set(culturalRecords.map(({ id }) => id)).size).toBe(culturalRecords.length);
    for (const record of records) {
      expect(culturalRecords.filter(({ canonicalKey }) => canonicalKey === record.canonicalKey)).toHaveLength(1);
      expect(culturalRecords.filter(({ sourceId }) => sourceId === record.sourceId)).toHaveLength(1);
    }
  });

  it("keeps research hidden and bilingual copy only in the promoted runtime catalog", () => {
    expect(research).toMatchObject({
      schemaVersion: 1,
      snapshotDate: "2026-09-01",
      readyForUi: false,
      runtimeCatalog: "frontend/src/data/discover/institutionalRituals.json",
    });
    expect(research.records.map(({ id, promotedRecordId }) => [id, promotedRecordId]))
      .toEqual(EXPECTED.map(([candidateId, id]) => [candidateId, id]));
    EXPECTED.forEach(([candidateId, id, rule], index) => {
      const candidate = research.records[index];
      const record = records[index];
      expect(candidate).toMatchObject({
        id: candidateId,
        promotedRecordId: id,
        rubric: "riti_credenze_popolari",
        reviewStatus: "promoted",
        readyForUi: false,
        currentEventScheduleVerified: false,
        temporalRule: { type: "nth_weekday", ...rule },
        editorialWindow: { type: "nth_weekday", ...rule },
      });
      expect(record).toMatchObject({
        id,
        candidateId,
        sourceId: candidateId,
        canonicalKey: candidate.canonicalKey,
        section: "riti_credenze_popolari",
        recurrence: "movable_date",
        nthWeekdayDates: [rule],
        editorialStatus: "ready_it",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
        dateAnchors: [],
        dateRanges: [],
        movableDates: [],
        movableDateRanges: [],
        weatherTags: [],
      });
      expect(record.areas).toEqual(candidate.geographicScope);
      expect(isCuratedDiscoverUiReady(candidate)).toBe(false);
      expect(isCuratedDiscoverPublished(record)).toBe(true);
      for (const key of ["title", "text", "appShort", "draftCopy"]) expect(candidate).not.toHaveProperty(key);
      for (const copy of [record.title, record.text, record.appShort]) {
        expect(copy.it.trim()).toBeTruthy();
        expect(copy.fur.trim()).toBeTruthy();
      }
    });
  });

  it("retains direct primary evidence and a scoped assisted FUR review without certification claims", () => {
    expect(research.editorialDecision).toMatchObject({
      basis: "user_delegated_assisted_editorial_review",
      reviewer: "assistant",
      independentHumanReview: false,
      scope: EXPECTED.map(([id]) => id),
    });
    EXPECTED.forEach(([, , , url], index) => {
      const candidate = research.records[index];
      const record = records[index];
      expect(candidate.source).toMatchObject({ url, checkedAt: "2026-09-01", accessMethod: "direct_http_html" });
      expect(record.source).toMatchObject({
        url,
        confidence: "alta",
        auditStatus: "source_and_scope_verified",
      });
      expect(record.source.rightsNote).toMatch(/nessuna immagine/);
      expect(record.supportingSources.length).toBeGreaterThan(0);
      expect(candidate.languageReview).toMatchObject({
        approvalBasis: "user_delegated_assisted_editorial_review",
        independentHumanReview: false,
        referencesLocation: `${record.id}.languageReview.fur.references`,
      });
      expect(record.languageReview.fur).toMatchObject({
        approvalBasis: "user_delegated_assisted_editorial_review",
        reviewMethod: "assisted_standard_reference_review",
        reviewer: "assistant",
        independentHumanReview: false,
      });
      expect(record.languageReview.fur.approvalNote).toMatch(/non certificazione ARLeF/i);
      expect(record.languageReview.fur.references.length).toBeGreaterThan(0);
      for (const reference of record.languageReview.fur.references) {
        expect(new URL(reference.url).hostname).toMatch(/(^|\.)arlef\.it$/);
        expect(new URL(reference.url).protocol).toBe("https:");
        expect(reference.url).not.toMatch(/\.pdf(?:$|\?)/);
      }
      for (const key of ["imageUrl", "videoUrl", "media"]) expect(record).not.toHaveProperty(key);
      expect(JSON.stringify([record.title, record.text, record.appShort]))
        .not.toMatch(/\d{1,2}:\d{2}|prenota|partecipa!|nel tuo paese|qui vicino|tal to paîs/i);
    });
  });

  it("recovers the hidden Barbana draft without publishing or duplicating it", () => {
    const hiddenDraft = localMemory.records.find(({ id }) => id === "memory-draft-grado-perdon-barbana");
    expect(hiddenDraft).toMatchObject({
      readyForUi: false,
      editorialStatus: "source_candidate",
      languageStatus: { it: "source_candidate", fur: "pending_review" },
    });
    expect(hiddenDraft).not.toHaveProperty("supersededBy");
    expect(hiddenDraft.editorialReview.note).toMatch(/non pubblicare/i);
    expect(research.records[0].duplicateReview).toMatchObject({
      status: "supersedes_hidden_draft",
      supersededRecordId: hiddenDraft.id,
    });
    expect(culturalRecords.some(({ id }) => id === hiddenDraft.id)).toBe(false);
    expect(institutionalRituals.filter(({ canonicalKey }) => (
      canonicalKey === "grado-perdon-barbana-prima-domenica-luglio"
    ))).toHaveLength(1);
  });

  it.each(JULY_SUNDAYS)("matches only the first and second July Sundays in %i", (year, first, second) => {
    const expectedDates = [first, second];
    records.forEach((record, index) => {
      const dates = [];
      for (let day = 1; day <= 31; day += 1) {
        const date = `${year}-07-${String(day).padStart(2, "0")}`;
        if (getDiscoverTemporalRank(record, date) !== null) dates.push(date);
      }
      expect(dates).toEqual([`${year}-${expectedDates[index]}`]);
      expect(getDiscoverTemporalRank(record, dates[0])).toBe(1);
    });
  });

  it.each(JULY_SUNDAYS.flatMap(([year, first, second]) => (
    ["it", "fur"].map((language) => [year, first, second, language])
  )))("renders both traditions on their exact ordinal Sundays in %i (%s)", (year, first, second, language) => {
    [first, second].forEach((date, index) => {
      const record = records[index];
      const card = ritualCard(`${year}-${date}`, language);
      expect(card).toMatchObject({
        id: record.id,
        title: record.title[language],
        text: record.text[language],
        sourceLabel: record.source.label,
        isFurPending: false,
        selectionKind: "movable_date",
      });
      const html = renderToStaticMarkup(createElement(DiscoverCard, { card }));
      expect(html).toContain(renderToStaticMarkup(createElement("h2", null, record.title[language])));
      expect(html).toContain(renderToStaticMarkup(createElement("p", null, record.text[language])));
      expect(html).toContain(renderToStaticMarkup(createElement("small", null, record.source.label)));
    });
  });

  it("keeps the historical claim and museum reconstruction within the documented scope", () => {
    const [barbana, trebbiatura] = records;
    expect(barbana.text.it).toMatch(/tradizione.*1237/);
    expect(barbana.text.it).not.toMatch(/certamente|documentato dal 1237|ininterrottamente/);
    expect(barbana.sourceNote).toMatch(/Sabo Grando|pescatori/);
    expect(trebbiatura.text.it).toMatch(/fa rivivere/);
    expect(trebbiatura.sourceNote).toMatch(/rievocazione museale/);
    expect(trebbiatura.text.it).not.toMatch(/mai interrotta|ancora oggi i contadini|rito millenario/);
  });
});
