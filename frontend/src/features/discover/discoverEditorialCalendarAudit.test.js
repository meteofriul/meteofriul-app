import { describe, expect, it } from "vitest";

import { buildDiscoverEditorialCalendarAudit } from "./discoverEditorialCalendarAudit";
import weatherContextReview from "../../data/discover/weatherContextReview.json";

// Catalog-only audits are read-only and reused by several assertions in this file.
// Keep custom-source audits independent instead of repeating six full years per test.
const annualAudits = new Map();
function getAnnualAudit(year, language = "it") {
  const key = `${year}:${language}`;
  if (!annualAudits.has(key)) {
    annualAudits.set(key, buildDiscoverEditorialCalendarAudit({ year, language }));
  }
  return annualAudits.get(key);
}

describe("buildDiscoverEditorialCalendarAudit", () => {
  it("simulates a complete leap year and preserves the editorial hierarchy", () => {
    const audit = getAnnualAudit(2028);
    expect(audit.days).toBe(366);
    expect(audit.rows[0].date).toBe("2028-01-01");
    expect(audit.rows.at(-1).date).toBe("2028-12-31");
    expect(audit.summary.memory.daysShown).toBe(366);
    expect(audit.summary.saying.daysShown).toBe(366);
    expect(audit.summary.archive.daysShown).toBe(366);
    expect(audit.summary.ritual.daysShown).toBe(48);
    expect(audit.summary.ritual.uniqueUsed).toBe(22);
    expect(audit.summary.ritual.usedIds).toEqual(expect.arrayContaining([
      "institutional-ritual-carnival-masks",
      "institutional-ritual-cidulis-cercivento",
      "institutional-ritual-craceles-holy-week",
      "institutional-ritual-resian-carnival",
      "institutional-ritual-winter-gift-bearers",
      "institutional-ritual-matajur-rogazione-maggiore",
      "institutional-ritual-missus-novena",
      "institutional-ritual-titiano-madonna-neve",
      "institutional-ritual-castelmonte-otto-settembre",
      "institutional-ritual-sappada-santa-margherita",
      "institutional-ritual-piano-arta-rosario",
      "institutional-ritual-pasian-prato-maria",
      "institutional-ritual-moggio-madonna-salute",
      "institutional-ritual-grado-perdon-barbana",
      "institutional-ritual-fagagna-trebbiatura",
      "institutional-ritual-pignano-immacolata",
      "institutional-ritual-paularo-femenate",
    ]));
    expect(audit.summary.ritual.longestConsecutiveRepeat.days).toBeLessThanOrEqual(6);
    expect(audit.summary.visibleCollisions).toEqual([]);
    expect(audit.summary.exactDatePrecedenceViolations).toEqual([]);
    expect(audit.summary.saying.unusedEligibleIds).toEqual([]);
    expect(audit.summary.saying.longestConsecutiveRepeat.days).toBeLessThanOrEqual(2);
    expect(audit.summary.archive.unusedEligibleIds).toEqual([
      "ost-0051-san-barnaba-vite",
      "ost-0052-sant-ermacora-grandini-bufere",
    ]);
    expect(audit.summary.archive.longestConsecutiveRepeat.days).toBeLessThanOrEqual(2);
    expect(audit.summary.exactDateCoveredByHigherRubric).toHaveLength(2);
  });

  it("keeps rituals conditional instead of using them as everyday filler", () => {
    const audit = getAnnualAudit(2028);
    const ordinaryDay = audit.rows.find((row) => row.date === "2028-02-01");

    expect(ordinaryDay.ritual).toBeNull();
    expect(ordinaryDay.memory).not.toBeNull();
    expect(ordinaryDay.saying).not.toBeNull();
    expect(ordinaryDay.archive).not.toBeNull();
  });

  it.each([2026, 2027, 2028, 2029, 2030, 2031].flatMap((year) => (
    ["it", "fur"].map((language) => [year, language])
  )))(
    "preserves archive and saying variety and exact local ritual dates in %i (%s)",
    (year, language) => {
      const audit = getAnnualAudit(year, language);

      expect(audit.summary.saying.daysShown).toBe(audit.days);
      expect(audit.summary.saying.uniqueUsed).toBe(80);
      expect(audit.summary.saying.unusedEligibleIds).toEqual([]);
      expect(audit.summary.saying.longestConsecutiveRepeat.days).toBeLessThanOrEqual(2);
      expect(audit.summary.archive.daysShown).toBe(audit.days);
      expect(audit.summary.archive.longestConsecutiveRepeat.days).toBeLessThanOrEqual(2);
      expect(audit.summary.archive.usedIds).toEqual(expect.arrayContaining([
        "institutional-archive-arrotini-bicicletta-stolvizza",
        "institutional-archive-torcitoio-seta-gorizia",
        "institutional-archive-casoni-porta-ovest-grado",
        "institutional-archive-maniago-maglio-ascolto",
        "institutional-archive-pesariis-orologi-portici",
        "institutional-archive-opicina-tram-funicolare",
        "institutional-archive-osmer-previsioni-fax-1991",
        "institutional-archive-carnia-alpeggio-fieno-inverno",
        "institutional-archive-carso-ghiacciaie-pietra",
        ...weatherContextReview.editorialDecision.recordIds,
      ]));
      expect(audit.summary.ritual.daysShown).toBe(48);
      expect(audit.summary.ritual.longestConsecutiveRepeat.days).toBeLessThanOrEqual(6);
      expect(audit.rows.find((row) => row.date === `${year}-08-05`).ritual?.id)
        .toBe("institutional-ritual-titiano-madonna-neve");
      expect(audit.rows.find((row) => row.date === `${year}-09-08`).ritual?.id)
        .toBe("institutional-ritual-castelmonte-otto-settembre");
      expect(audit.rows.filter((row) => row.ritual?.id === "institutional-ritual-sappada-santa-margherita")
        .map((row) => row.date)).toEqual([`${year}-07-20`]);
      const octoberDate = { 2026: "04", 2027: "03", 2028: "01", 2029: "07", 2030: "06", 2031: "05" }[year];
      const rosarioRows = audit.rows.filter((row) => row.ritual?.id === "institutional-ritual-piano-arta-rosario");
      expect(rosarioRows.map((row) => row.date)).toEqual([`${year}-10-${octoberDate}`]);
      expect(rosarioRows[0].ritual).toMatchObject({ temporalRank: 1, selectionKind: "movable_date" });
      for (const [id, date] of [
        ["institutional-ritual-paularo-femenate", "01-05"],
        ["institutional-ritual-pasian-prato-maria", "05-31"],
        ["institutional-ritual-moggio-madonna-salute", "11-21"],
        ["institutional-ritual-pignano-immacolata", "12-08"],
      ]) {
        expect(audit.rows.filter((row) => row.ritual?.id === id).map((row) => row.date))
          .toEqual([`${year}-${date}`]);
      }
      const julySundays = {
        2026: ["05", "12"], 2027: ["04", "11"], 2028: ["02", "09"],
        2029: ["01", "08"], 2030: ["07", "14"], 2031: ["06", "13"],
      }[year];
      for (const [id, day] of [
        ["institutional-ritual-grado-perdon-barbana", julySundays[0]],
        ["institutional-ritual-fagagna-trebbiatura", julySundays[1]],
      ]) {
        expect(audit.rows.filter((row) => row.ritual?.id === id).map((row) => row.date))
          .toEqual([`${year}-07-${day}`]);
      }
      expect(audit.summary.exactDatePrecedenceViolations).toEqual([]);
      expect(audit.summary.visibleCollisions).toEqual([]);
    },
  );

  it("uses every calendar-eligible ritual across the six-year rotation", () => {
    const audits = [2026, 2027, 2028, 2029, 2030, 2031]
      .map((year) => getAnnualAudit(year));
    const eligible = new Set(audits.flatMap((audit) => audit.summary.ritual.eligibleIds));
    const used = new Set(audits.flatMap((audit) => audit.summary.ritual.usedIds));

    expect(eligible.size).toBe(27);
    expect(used).toEqual(eligible);
  }, 30_000); // Also allow the six-year test to run alone with an empty cache.

  it("excludes explicitly blocked curated records from the annual audit", () => {
    const audit = buildDiscoverEditorialCalendarAudit({
      year: 2028,
      localMemorySource: { records: [] },
      sourceRecords: [{
        id: "blocked-ready-record",
        section: "archivio_tradizioni",
        type: "tradizione",
        recurrence: "always",
        seasons: ["all"],
        priority: 1,
        editorialStatus: "ready_it",
        languageStatus: { fur: "approved" },
        readyForUi: false,
        title: { it: "Non visibile", fur: "No visibil" },
        text: { it: "Non deve apparire.", fur: "No à di comparî." },
      }],
      traditionalSayingsSource: { records: [] },
    });

    expect(audit.summary.archive.eligibleIds).toEqual([]);
    expect(audit.summary.archive.daysShown).toBe(0);
  });

});
