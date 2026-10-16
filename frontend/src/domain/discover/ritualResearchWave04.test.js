import { createHash } from "node:crypto";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import institutionalRituals from "../../data/discover/institutionalRituals.json";
import research from "../../data/discover/ritualResearchWave04.json";
import { DiscoverCard } from "../../features/discover/DiscoverView";
import { buildDiscoverViewModel } from "../../features/discover/discoverViewModel";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished, isCuratedDiscoverUiReady } from "./discoverCulturalReadiness";
import { getDiscoverTemporalRank } from "./discoverTemporalSelection";

const SAPPADA_ID = "institutional-ritual-sappada-santa-margherita";
const PIANO_ID = "institutional-ritual-piano-arta-rosario";
const PROMOTIONS = {
  "ritual-research-sappada-santa-margherita": SAPPADA_ID,
  "ritual-research-piano-arta-rosario": PIANO_ID,
};
const EXPECTED_SOURCES = {
  [SAPPADA_ID]: "https://www.plodn.info/tradizioni/",
  [PIANO_ID]: "https://www.diocesiudine.it/wd-appuntamenti/piano-darta-celebra-la-madonna-del-rosario/",
};
const OLD_NINE_DIGEST = "0dfd677b84a070d3f477a968de38fd82485d20734272c310a9a83dad3d5b132b";
const FIRST_OCTOBER_SUNDAYS = [
  [2026, "10-04"], [2027, "10-03"], [2028, "10-01"],
  [2029, "10-07"], [2030, "10-06"], [2031, "10-05"],
];
const runtimeById = new Map(institutionalRituals.map((record) => [record.id, record]));
const sappada = runtimeById.get(SAPPADA_ID);
const piano = runtimeById.get(PIANO_ID);
const location = { city: "Pordenone", province: "Pordenone", region: "Friuli Venezia Giulia" };

function ritualCard(today, language, city = location) {
  return buildDiscoverViewModel({ today, language, location: city })
    .sections.find((section) => section.id === "rituals")?.cards[0];
}

function adjacentDate(today, offset) {
  const date = new Date(`${today}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}

describe("ritual research wave 04", () => {
  it("preserves the complete nine earlier records and appends the two distinct promotions", () => {
    expect(createHash("sha256").update(JSON.stringify(institutionalRituals.slice(0, 9))).digest("hex"))
      .toBe(OLD_NINE_DIGEST);
    expect(institutionalRituals.slice(9, 11).map((record) => record.id)).toEqual([SAPPADA_ID, PIANO_ID]);
    expect(new Set(culturalRecords.map((record) => record.id)).size).toBe(culturalRecords.length);
    [sappada, piano].forEach((runtime) => {
      expect(culturalRecords.filter((record) => record.canonicalKey === runtime.canonicalKey)).toHaveLength(1);
      expect(culturalRecords.filter((record) => record.sourceId === runtime.sourceId)).toHaveLength(1);
    });
  });

  it("keeps the research hidden and stores bilingual copy only in the approved runtime records", () => {
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
        dateRanges: [],
        movableDates: [],
        movableDateRanges: [],
        weatherTags: [],
      });
      expect(candidate.editorialWindow).toEqual(candidate.temporalRule);
      expect(candidate.geographicScope).toEqual(runtime.areas);
      ["title", "text", "appShort", "draftCopy"].forEach((key) => expect(candidate).not.toHaveProperty(key));
      expect(isCuratedDiscoverUiReady(candidate)).toBe(false);
      expect(isCuratedDiscoverPublished(runtime)).toBe(true);
      expect(culturalRecords.some((record) => record.id === candidate.id)).toBe(false);
      [runtime.title, runtime.text, runtime.appShort].forEach((copy) => {
        expect(copy.it).toBeTruthy();
        expect(copy.fur).toBeTruthy();
        expect(copy.fur).not.toBe(copy.it);
      });
    });
  });

  it("retains primary HTML evidence without reused media or current event promises", () => {
    research.records.forEach((candidate) => {
      const runtime = runtimeById.get(candidate.promotedRecordId);
      expect(candidate.source).toMatchObject({ url: EXPECTED_SOURCES[runtime.id], checkedAt: "2026-08-31" });
      expect(["direct_html", "direct_http_html"]).toContain(candidate.source.accessMethod);
      expect(new URL(candidate.source.url).protocol).toBe("https:");
      expect(runtime.source).toMatchObject({
        url: candidate.source.url, confidence: "alta", auditStatus: "source_and_scope_verified",
      });
      expect(runtime.source.rightsNote).toMatch(/nessuna immagine/);
      ["imageUrl", "videoUrl", "media"].forEach((key) => expect(runtime).not.toHaveProperty(key));
      expect(candidate.duplicateReview).toMatchObject({ status: "distinct" });
      expect(candidate.duplicateReview.comparedCatalogs).toEqual([
        "ostermannCulturalDiscover", "institutionalRituals", "institutionalArchive", "localMemory", "municipalityProfiles",
      ]);
      expect(JSON.stringify([runtime.title, runtime.text, runtime.appShort]))
        .not.toMatch(/\b2026\b|\d{1,2}:\d{2}|prenota|partecipa|nel tuo paese|qui vicino|tal to paîs/i);
    });
    expect(sappada.source.type).toBe("local_cultural_association");
    expect(research.records[0].source.authorityUrl).toBe("https://www.plodn.info/associazione-plodar/");
    expect(piano.source.publishedAt).toBe("2014-09-30");
  });

  it("makes the scoped assisted review explicit without human or ARLeF certification claims", () => {
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
      expect(runtime.languageReview.fur).toMatchObject({
        approvalBasis: "user_delegated_assisted_editorial_review",
        reviewMethod: "assisted_standard_reference_review",
        reviewer: "assistant",
        independentHumanReview: false,
      });
      expect(runtime.languageReview.fur.approvalNote).toMatch(/non approvazione dell'utente frase per frase/i);
      expect(runtime.languageReview.fur.approvalNote).toMatch(/non certificazione ARLeF/i);
      expect(runtime.languageReview.fur.references.length).toBeGreaterThan(0);
      runtime.languageReview.fur.references.forEach((reference) => {
        expect(new URL(reference.url).hostname).toMatch(/(^|\.)arlef\.it$/);
        expect(new URL(reference.url).protocol).toBe("https:");
        expect(reference.accessMethod).toBe("direct_http_html");
        expect(reference.url).not.toMatch(/\.pdf(?:$|\?)/);
      });
    });
  });

  it("keeps the Sappada feast date separate from the general summer processions", () => {
    expect(sappada).toMatchObject({ recurrence: "fixed_date", dateAnchors: ["07-20"], areas: ["sappada"] });
    expect(sappada).not.toHaveProperty("nthWeekdayDates");
    expect(sappada.text.it).toContain("Il 20 luglio");
    expect(sappada.text.it).toContain("Nelle processioni estive i ragazzi coscritti");
    expect(sappada.text.fur).toContain("Ai 20 di Lui");
    expect(sappada.text.fur).toContain("Tes processions d'istât i fantats coscrits");
    ["it", "fur"].forEach((language) => {
      expect(sappada.text[language]).toContain("Sappada/Plodn");
      expect(sappada.appShort[language]).toContain("Sappada/Plodn");
    });
    expect(sappada.sourceNote).toContain("non come usanze esclusive di quella data");
  });

  it("dates Piano's recurring feast by ordinal weekday and attributes the preparations to 2014", () => {
    expect(piano).toMatchObject({
      recurrence: "movable_date",
      dateAnchors: [],
      nthWeekdayDates: [{ month: 10, weekday: 0, ordinal: 1 }],
      areas: ["piano_arta", "arta_terme"],
    });
    expect(research.records[1].temporalRule).toEqual({ type: "nth_weekday", month: 10, weekday: 0, ordinal: 1 });
    expect(piano.text.it).toContain("prima domenica di ottobre");
    expect(piano.text.fur).toContain("prime domenie di Otubar");
    [piano.text, piano.appShort].forEach((copy) => {
      expect(copy.it).toContain("2014");
      expect(copy.fur).toContain("2014");
    });
    expect(piano.text.it).toContain("Mercatino artigianale");
    expect(piano.text.fur).toContain("Mercatino artigianale");
  });

  it.each(FIRST_OCTOBER_SUNDAYS)("selects each rite on exactly one day of %s", (year, octoberDate) => {
    [[sappada, "07-20", 0], [piano, octoberDate, 1]].forEach(([record, date, rank]) => {
      const exact = `${year}-${date}`;
      expect(getDiscoverTemporalRank(record, exact)).toBe(rank);
      expect(getDiscoverTemporalRank(record, adjacentDate(exact, -1))).toBeNull();
      expect(getDiscoverTemporalRank(record, adjacentDate(exact, 1))).toBeNull();
      const eligibleDates = [];
      for (const day = new Date(Date.UTC(year, 0, 1)); day.getUTCFullYear() === year; day.setUTCDate(day.getUTCDate() + 1)) {
        const isoDate = day.toISOString().slice(0, 10);
        if (getDiscoverTemporalRank(record, isoDate) !== null) eligibleDates.push(isoDate);
      }
      expect(eligibleDates).toEqual([exact]);
    });
  });

  it.each(FIRST_OCTOBER_SUNDAYS.flatMap(([year, date]) => ["it", "fur"].map((language) => [year, date, language])))(
    "renders both rites with readable sources for %s (%s) in %s", (year, octoberDate, language) => {
      [[sappada, "07-20", "exact_date"], [piano, octoberDate, "movable_date"]].forEach(([record, date, kind]) => {
        const exact = `${year}-${date}`;
        const card = ritualCard(exact, language);
        expect(card).toMatchObject({
          id: record.id,
          title: record.title[language],
          text: record.text[language],
          sourceLabel: record.source.label,
          isFurPending: false,
          selectionKind: kind,
        });
        const html = renderToStaticMarkup(createElement(DiscoverCard, { card }));
        expect(html).toContain(renderToStaticMarkup(createElement("h2", null, record.title[language])));
        expect(html).toContain(renderToStaticMarkup(createElement("p", null, record.text[language])));
        expect(html).toContain(renderToStaticMarkup(createElement("small", null, record.source.label)));
        [-1, 1].forEach((offset) => expect(ritualCard(adjacentDate(exact, offset), language)?.id).not.toBe(record.id));
      });
    },
  );

  it.each(["it", "fur"])("does not reinterpret a ritual's cultural area as the user's location in %s", (language) => {
    const trieste = { city: "Trieste", province: "Trieste", region: "Friuli Venezia Giulia" };
    ["2028-07-20", "2028-10-01"].forEach((date) => {
      expect(ritualCard(date, language, trieste)).toEqual(ritualCard(date, language, location));
    });
  });
});
