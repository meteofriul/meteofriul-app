import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import institutionalRituals from "../../data/discover/institutionalRituals.json";
import localMemory from "../../data/discover/localMemory.json";
import research from "../../data/discover/ritualResearchWave07.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getDiscoverTemporalRank } from "./discoverTemporalSelection";

const EXPECTED = [
  [
    "ritual-research-pignano-immacolata",
    "institutional-ritual-pignano-immacolata",
    "12-08",
    "https://www.diocesiudine.it/wd-appuntamenti/a-pignano-di-ragogna-da-111-anni-si-celebra-limmacolata/",
  ],
  [
    "ritual-research-paularo-femenate",
    "institutional-ritual-paularo-femenate",
    "01-05",
    "https://www.ecomuseomistirs.it/la-femenate/",
  ],
];
const records = EXPECTED.map(([, id]) => institutionalRituals.find((record) => record.id === id));
const location = { city: "Pordenone", province: "Pordenone", region: "Friuli Venezia Giulia" };

function ritualCard(today, language, city = location) {
  return buildDiscoverViewModel({ today, language, location: city })
    .sections.find((section) => section.id === "rituals")?.cards[0];
}

function adjacentDate(year, monthDay, offset) {
  const date = new Date(`${year}-${monthDay}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}

describe("ritual research wave 07", () => {
  it("preserves the fifteen earlier records and appends exactly the two reviewed winter traditions", () => {
    expect(createHash("sha256").update(JSON.stringify(institutionalRituals.slice(0, 15))).digest("hex"))
      .toBe("09b7449604db932977e1c31436e238d58ce8476b0e87d024d66754141cb43ad6");
    expect(institutionalRituals.slice(15, 17).map(({ id }) => id)).toEqual(EXPECTED.map(([, id]) => id));
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

    EXPECTED.forEach(([candidateId, id, date], index) => {
      const candidate = research.records[index];
      const record = records[index];
      expect(candidate).toMatchObject({
        id: candidateId,
        promotedRecordId: id,
        rubric: "riti_credenze_popolari",
        reviewStatus: "promoted",
        readyForUi: false,
        currentEventScheduleVerified: false,
        temporalRule: { type: "fixed_date", date },
        editorialWindow: { type: "fixed_date", date },
      });
      expect(record).toMatchObject({
        id,
        candidateId,
        sourceId: candidateId,
        canonicalKey: candidate.canonicalKey,
        section: "riti_credenze_popolari",
        recurrence: "fixed_date",
        dateAnchors: [date],
        dateRanges: [],
        movableDates: [],
        movableDateRanges: [],
        weatherTags: [],
        editorialStatus: "ready_it",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
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

  it("keeps Pignano distinct from the Gemona memory on the same date", () => {
    const gemona = localMemory.records.find(({ id }) => (
      id === "memory-it-ready-1208-a-gemona-l-immacolata-ricorda-un-grande-incendio"
    ));
    expect(gemona).toBeTruthy();
    expect(research.records[0].duplicateReview).toMatchObject({
      status: "distinct",
      comparedRecordIds: [gemona.id],
    });
    expect(records[0].canonicalKey).not.toBe(gemona.canonicalKey);
    expect(records[0].source.url).not.toBe(gemona.source.url);
    expect(records[0].text.it).not.toMatch(/Gemona|incendio|1448/);
  });

  it.each([2026, 2027, 2028, 2029, 2030, 2031])("matches both records only on their fixed date in %i", (year) => {
    records.forEach((record, index) => {
      const date = `${year}-${EXPECTED[index][2]}`;
      expect(getDiscoverTemporalRank(record, date)).toBe(0);
      expect(getDiscoverTemporalRank(record, adjacentDate(year, EXPECTED[index][2], -1))).toBeNull();
      expect(getDiscoverTemporalRank(record, adjacentDate(year, EXPECTED[index][2], 1))).toBeNull();
    });
  });

  it.each(EXPECTED.flatMap((entry, index) => (
    ["it", "fur"].map((language) => [index, entry[2], language])
  )))("renders tradition %i on its exact date in %s", (index, monthDay, language) => {
    const record = records[index];
    const card = ritualCard(`2028-${monthDay}`, language);
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

  it("keeps both cultural claims within the documented scope", () => {
    const [pignano, femenate] = records;
    expect(pignano.text.it).toMatch(/1904/);
    expect(pignano.text.it).toMatch(/120ª edizione/);
    expect(pignano.sourceNote).toMatch(/Borc di Sot|Borc di Sore/);
    expect(femenate.text.it).toMatch(/Femenàtes/);
    expect(femenate.text.it).toMatch(/Fumo e faville/);
    expect(femenate.sourceNote).toMatch(/non viene esteso|previsioni attendibili/);
    expect(JSON.stringify([femenate.title, femenate.text, femenate.appShort, femenate.sourceNote]))
      .not.toMatch(/origine celtica certa|previsione meteorologica|funziona davvero|avverrà/i);
  });

  it.each(["it", "fur"])("does not reinterpret the cultural areas as the user's location in %s", (language) => {
    const trieste = { city: "Trieste", province: "Trieste", region: "Friuli Venezia Giulia" };
    EXPECTED.forEach(([, , date]) => {
      expect(ritualCard(`2028-${date}`, language, trieste)).toEqual(ritualCard(`2028-${date}`, language));
    });
  });
});
