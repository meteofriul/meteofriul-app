import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import institutionalRituals from "../../data/discover/institutionalRituals.json";
import research from "../../data/discover/ritualResearchWave05.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getDiscoverTemporalRank } from "./discoverTemporalSelection";

const EXPECTED = [
  ["ritual-research-pasian-prato-maria", "institutional-ritual-pasian-prato-maria", "05-31",
    "https://www.diocesiudine.it/wd-appuntamenti/pasian-di-prato-con-maria-in-cammino-fino-a-la-nostra-famiglia/"],
  ["ritual-research-moggio-madonna-salute", "institutional-ritual-moggio-madonna-salute", "11-21",
    "https://www.diocesiudine.it/wd-appuntamenti/moggio-udinese-messa-e-processione-per-la-madonna-della-salute/"],
];
const records = EXPECTED.map(([, id]) => institutionalRituals.find((record) => record.id === id));
const location = { city: "Pordenone", province: "Pordenone", region: "Friuli Venezia Giulia" };

function ritualCard(today, language, city = location) {
  return buildDiscoverViewModel({ today, language, location: city })
    .sections.find((section) => section.id === "rituals")?.cards[0];
}

describe("ritual research wave 05", () => {
  it("preserves all eleven earlier institutional rites and appends exactly two different traditions", () => {
    expect(createHash("sha256").update(JSON.stringify(institutionalRituals.slice(0, 11))).digest("hex"))
      .toBe("69c3ff377ad63fa00dcef3d7445a204603f315edc7e826e738f0ff2ed69777b6");
    expect(institutionalRituals.slice(11, 13).map(({ id }) => id)).toEqual(EXPECTED.map(([, id]) => id));
    expect(new Set(culturalRecords.map(({ id }) => id)).size).toBe(culturalRecords.length);
    for (const record of records) {
      expect(culturalRecords.filter(({ canonicalKey }) => canonicalKey === record.canonicalKey)).toHaveLength(1);
      expect(culturalRecords.filter(({ sourceId }) => sourceId === record.sourceId)).toHaveLength(1);
    }
  });

  it("keeps research hidden and bilingual copy only in the reviewed runtime catalog", () => {
    expect(research).toMatchObject({
      schemaVersion: 1, snapshotDate: "2026-08-31", readyForUi: false,
      runtimeCatalog: "frontend/src/data/discover/institutionalRituals.json",
    });
    expect(research.records.map(({ id, promotedRecordId }) => [id, promotedRecordId]))
      .toEqual(EXPECTED.map(([candidateId, id]) => [candidateId, id]));
    EXPECTED.forEach(([candidateId, id, date], index) => {
      const candidate = research.records[index];
      const record = records[index];
      expect(candidate).toMatchObject({
        id: candidateId, promotedRecordId: id, rubric: "riti_credenze_popolari",
        reviewStatus: "promoted", readyForUi: false, currentEventScheduleVerified: false,
        temporalRule: { type: "fixed_date", date }, editorialWindow: { type: "fixed_date", date },
      });
      expect(record).toMatchObject({
        id, candidateId, sourceId: candidateId, canonicalKey: candidate.canonicalKey,
        section: "riti_credenze_popolari", recurrence: "fixed_date", dateAnchors: [date],
        editorialStatus: "ready_it", languageStatus: { it: "approved", fur: "approved" }, readyForUi: true,
        dateRanges: [], movableDates: [], movableDateRanges: [], weatherTags: [],
      });
      expect(record).not.toHaveProperty("nthWeekdayDates");
      expect(record.areas).toEqual(candidate.geographicScope);
      expect(isCuratedDiscoverUiReady(candidate)).toBe(false);
      expect(isCuratedDiscoverPublished(record)).toBe(true);
      for (const key of ["title", "text", "appShort", "draftCopy"]) expect(candidate).not.toHaveProperty(key);
      for (const copy of [record.title, record.text, record.appShort]) {
        expect(copy.it.trim()).toBeTruthy();
        expect(copy.fur.trim()).toBeTruthy();
        expect(copy.fur).not.toBe(copy.it);
      }
    });
  });

  it("retains direct primary evidence and a scoped assisted FUR review without certification claims", () => {
    expect(research.editorialDecision).toMatchObject({
      basis: "user_delegated_assisted_editorial_review", reviewer: "assistant",
      independentHumanReview: false, scope: EXPECTED.map(([id]) => id),
    });
    EXPECTED.forEach(([, , , url], index) => {
      const candidate = research.records[index];
      const record = records[index];
      expect(candidate.source).toMatchObject({ url, checkedAt: "2026-08-31" });
      expect(["direct_html", "direct_http_html"]).toContain(candidate.source.accessMethod);
      expect(record.source).toMatchObject({
        url, type: "institutional_publication", confidence: "alta", auditStatus: "source_and_scope_verified",
      });
      expect(record.source.rightsNote).toMatch(/nessuna immagine/);
      expect(record.supportingSources.length).toBeGreaterThan(0);
      expect(candidate.duplicateReview.status).toBe("distinct");
      expect(candidate.languageReview).toMatchObject({
        approvalBasis: "user_delegated_assisted_editorial_review", independentHumanReview: false,
        referencesLocation: `${record.id}.languageReview.fur.references`,
      });
      expect(record.languageReview.fur).toMatchObject({
        approvalBasis: "user_delegated_assisted_editorial_review", reviewMethod: "assisted_standard_reference_review",
        reviewer: "assistant", independentHumanReview: false,
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
        .not.toMatch(/\b2026\b|\d{1,2}:\d{2}|prenota|partecipa!|nel tuo paese|qui vicino|tal to paîs/i);
    });
  });

  it("does not turn an edition's route or an uncertain origin into a timeless fact", () => {
    const [pasian, moggio] = records;
    expect(pasian.text.it).toContain("31 maggio");
    expect(pasian.text.fur).toContain("31 di Mai");
    expect(pasian.text.it).toContain("collega");
    expect(pasian.text.it).not.toMatch(/partendo|parte da|giunge fino|40°|70°/);
    for (const language of ["it", "fur"]) {
      expect(pasian.text[language]).toContain("La Nostra Famiglia");
      expect(pasian.text[language]).toContain("San Giacomo");
    }
    expect(moggio.text.it).toContain("21 novembre");
    expect(moggio.text.fur).toContain("21 di Novembar");
    expect(moggio.text.it).toContain("pompieri volontari");
    expect(moggio.text.fur).toContain("pompîrs volontaris");
    expect(moggio.text.it).not.toMatch(/origini antiche|millenari|fondata|nacque|guarisce|protegge dal colera/);
    expect(`${pasian.sourceNote} ${research.records[0].scopeNote}`).toMatch(/1.*giugno|01\/06|01-06/);
    expect(`${moggio.sourceNote} ${research.records[1].scopeNote}`).toMatch(/22.*novembre|22\/11|11-22/i);
  });

  it.each([2026, 2027, 2028, 2029, 2030, 2031])("allows only the documented dates in %s, not the following CMS dates", (year) => {
    records.forEach((record, index) => {
      const dates = [];
      for (const day = new Date(Date.UTC(year, 0, 1)); day.getUTCFullYear() === year; day.setUTCDate(day.getUTCDate() + 1)) {
        const date = day.toISOString().slice(0, 10);
        if (getDiscoverTemporalRank(record, date) !== null) dates.push(date);
      }
      expect(dates).toEqual([`${year}-${EXPECTED[index][2]}`]);
      expect(getDiscoverTemporalRank(record, dates[0])).toBe(0);
    });
  });

  it.each([2026, 2027, 2028, 2029, 2030, 2031].flatMap((year) => ["it", "fur"].map((language) => [year, language])))(
    "renders both local traditions with source labels in %s (%s)", (year, language) => {
      records.forEach((record, index) => {
        const card = ritualCard(`${year}-${EXPECTED[index][2]}`, language);
        expect(card).toMatchObject({
          id: record.id, title: record.title[language], text: record.text[language],
          sourceLabel: record.source.label, isFurPending: false, selectionKind: "exact_date",
        });
        const html = renderToStaticMarkup(createElement(DiscoverCard, { card }));
        expect(html).toContain(renderToStaticMarkup(createElement("h2", null, record.title[language])));
        expect(html).toContain(renderToStaticMarkup(createElement("p", null, record.text[language])));
        expect(html).toContain(renderToStaticMarkup(createElement("small", null, record.source.label)));
      });
      expect(ritualCard(`${year}-06-01`, language)?.id).not.toBe(records[0].id);
      expect(ritualCard(`${year}-11-22`, language)?.id).not.toBe(records[1].id);
    },
  );

  it.each(["it", "fur"])("keeps geographic context independent of the reader's municipality in %s", (language) => {
    const trieste = { city: "Trieste", province: "Trieste", region: "Friuli Venezia Giulia" };
    for (const [, , date] of EXPECTED) {
      expect(ritualCard(`2028-${date}`, language, trieste)).toEqual(ritualCard(`2028-${date}`, language));
    }
  });
});
