import { describe, expect, it } from "vitest";

import { buildPilotDiscoverCulture } from "./pilotDiscoverSections";

const saying = {
  id: "saying-almanac-proverb-one", contentKey: "proverb-one",
  title: "Con il tempo e con la paglia maturano le nespole.", text: "",
  type: "detto_popolare", typeLabel: "Detto popolare", selectionKind: "rotation",
  sourceLabel: "Ostermann 1876", sourceNote: "Citazione verificata.",
};
const ritual = {
  id: "rite-one", contentKey: "cultural-one", title: "Fuochi rituali",
  text: "Un rito documentato nel comune, nella data della ricorrenza.",
  type: "rito", typeLabel: "Rito", seasonLabel: "Estate", selectionKind: "exact_date",
  sourceLabel: "Archivio istituzionale", sourceNote: "Rilevamento locale verificato.",
};

function calendar(overrides = {}) {
  return {
    proverb: { title: "Proverbio", body: saying.title },
    tradition: { label: "Fuochi rituali", body: "Riassunto breve del rito.", source: ritual.sourceLabel },
    earth: { title: "Consiglio della terra", items: ["Raccogli i semi maturi e conservali all'asciutto."] },
    raw: {
      date: new Date(2026, 8, 8, 12),
      proverb: { id: "proverb-one", source: "Ostermann 1876, p. 91", category: "saggezza" },
      tradition: {
        id: "almanac-rite", candidateId: "cultural-one", type: "rito", recurrence: "fixed_date",
        dateAnchors: ["09-08"], source: { label: ritual.sourceLabel, note: ritual.sourceNote },
      },
    },
    ...overrides,
  };
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.values(value).forEach(deepFreeze);
  return Object.freeze(value);
}

describe("buildPilotDiscoverCulture", () => {
  it("keeps exactly the curated daily saying, including its title-only quotation", () => {
    const result = buildPilotDiscoverCulture({
      calendar: calendar(),
      sections: [{ id: "traditional-sayings", cards: [saying, { ...saying, id: "second", contentKey: "second" }] }],
      copy: { traditionalSayingsTitle: "Si diceva che..." },
    });
    expect(result.sayings).toEqual({ id: "traditional-sayings", title: "Si diceva che...", cards: [saying] });
    expect(result.sayings.cards[0]).not.toBe(saying);
  });

  it("does not add a second almanac proverb even when it is a different record", () => {
    const data = calendar();
    data.raw.proverb.id = "another-proverb";
    data.proverb.body = "Un altro proverbio valido, scelto dal calendario annuale.";
    const result = buildPilotDiscoverCulture({ calendar: data, sections: [{ id: "traditional-sayings", cards: [saying] }] });
    expect(result.sayings.cards).toEqual([saying]);
  });

  it("uses the selected almanac proverb as fallback with its real identity and source", () => {
    const result = buildPilotDiscoverCulture({ calendar: calendar() });
    expect(result.sayings.cards).toEqual([expect.objectContaining({
      id: "proverb-one", contentKey: "proverb-one", text: saying.title,
      sourceLabel: "Ostermann 1876, p. 91", type: "saggezza",
    })]);
  });

  it("excludes the same proverb through its raw identity, even when summaries differ", () => {
    const result = buildPilotDiscoverCulture({
      calendar: calendar(), excludedCards: [{ id: "memory-proverb", contentKey: "proverb-one", text: "Altra sintesi." }],
      sections: [{ id: "traditional-sayings", cards: [saying] }],
    });
    expect(result.sayings.cards).toEqual([]);
  });

  it("deduplicates a title-only saying against an equivalent complete excluded text", () => {
    const result = buildPilotDiscoverCulture({
      calendar: calendar({ proverb: { body: "" } }),
      sections: [{ id: "traditional-sayings", cards: [saying] }],
      excludedCards: [{ id: "another-source", title: "Una memoria", text: saying.title.toUpperCase() }],
    });
    expect(result.sayings.cards).toEqual([]);
  });

  it("merges a short almanac tradition and full Discover version by candidateId", () => {
    const result = buildPilotDiscoverCulture({ calendar: calendar(), sections: [{ id: "rituals", cards: [ritual] }] });
    expect(result.traditions.cards).toEqual([ritual]);
  });

  it("preserves different ritual/archive records, metadata and source notes", () => {
    const archive = { ...ritual, id: "archive-one", contentKey: "archive-one", text: "Un documento diverso sulla vita nel paese.", type: "vita_quotidiana", selectionKind: "rotation", sourceLabel: "ERPAC FVG" };
    const result = buildPilotDiscoverCulture({
      calendar: calendar(), sections: [{ id: "rituals", cards: [ritual] }, { id: "archive", cards: [archive] }],
    });
    expect(result.traditions.cards).toEqual([ritual, archive]);
  });

  it("does not collapse stories just because their short title is identical", () => {
    const result = buildPilotDiscoverCulture({
      sections: [{ id: "archive", cards: [
        { id: "one", title: "La luna", text: "Una credenza sui raccolti raccontata in questo paese." },
        { id: "two", title: "La luna", text: "Un documento sui lunari con una provenienza differente." },
      ] }],
    });
    expect(result.traditions.cards).toHaveLength(2);
  });

  it("does not repeat an existing card id under a different contentKey", () => {
    const result = buildPilotDiscoverCulture({ sections: [
      { id: "rituals", cards: [ritual] },
      { id: "archive", cards: [{ ...ritual, contentKey: "another-alias", text: "Un riassunto alternativo dello stesso record." }] },
    ] });
    expect(result.traditions.cards).toEqual([ritual]);
  });

  it("does not treat even a long common heading as a duplicate when full bodies differ", () => {
    const title = "Il ciclo della luna e i racconti tramandati nelle comunità del Friuli";
    const result = buildPilotDiscoverCulture({ sections: [{ id: "archive", cards: [
      { id: "one", title, text: "Una testimonianza diversa sui raccolti nel primo paese." },
      { id: "two", title, text: "Un documento autonomo relativo ai lunari del secondo paese." },
    ] }] });
    expect(result.traditions.cards).toHaveLength(2);
  });

  it("deduplicates significant equivalent full bodies without fuzzy theme matching", () => {
    const result = buildPilotDiscoverCulture({
      sections: [{ id: "archive", cards: [
        ritual,
        { ...ritual, id: "different-id", contentKey: "different-id", text: ritual.text.toUpperCase().replaceAll(" ", "  ") },
        { ...ritual, id: "related-id", contentKey: "related-id", text: "Un altro rito documentato in un comune diverso, nella data della ricorrenza." },
      ] }],
    });
    expect(result.traditions.cards.map(card => card.id)).toEqual([ritual.id, "related-id"]);
  });

  it("deduplicates against both the focus and memories but leaves unrelated cards out of culture", () => {
    const result = buildPilotDiscoverCulture({
      calendar: calendar(), excludedCards: [ritual],
      sections: [
        { id: "rituals", cards: [ritual] },
        { id: "today-memory", cards: [{ id: "memory", title: "Una memoria" }] },
        { id: "territory-stories", cards: [{ id: "local", title: "Un paese" }] },
      ],
    });
    expect(result.traditions.cards).toEqual([]);
  });

  it("maps the raw tradition metadata without creating new selections", () => {
    const result = buildPilotDiscoverCulture({ calendar: calendar() });
    expect(result.traditions.cards).toEqual([expect.objectContaining({
      id: "almanac-rite", contentKey: "cultural-one", type: "rito", recurrence: "fixed_date",
      selectionKind: "exact_date", sourceLabel: ritual.sourceLabel, sourceNote: ritual.sourceNote,
    })]);
  });

  it.each([
    ["it", "Tradizioni del Friûl", "Si diceva che..."],
    ["fur", "Tradizions dal Friûl", "Si diseve che..."],
  ])("uses %s headings and the already-localized almanac text", (language, title, sayingsTitle) => {
    const data = calendar();
    data.proverb.body = language === "fur" ? "Cul timp e cu la pae si madressin i gnespui." : saying.title;
    const result = buildPilotDiscoverCulture({ calendar: data, language, copy: { traditionalSayingsTitle: sayingsTitle } });
    expect(result.traditions.title).toBe(title);
    expect(result.sayings.title).toBe(sayingsTitle);
    expect(result.sayings.cards[0].text).toBe(data.proverb.body);
  });

  it("retains all distinct tips in one separate list without invented attribution", () => {
    const data = calendar();
    data.earth.items = [saying.title, saying.title.toUpperCase(), "Proteggi le piante delicate dal freddo.", " ", null];
    const result = buildPilotDiscoverCulture({ calendar: data, sections: [{ id: "traditional-sayings", cards: [saying] }] });
    expect(result.earth).toEqual({ title: "Consiglio della terra", items: [saying.title, "Proteggi le piante delicate dal freddo."] });
    expect(result.sayings.cards).toHaveLength(1);
    expect(result.earth).not.toHaveProperty("sourceLabel");
  });

  it("returns empty groups instead of invented questions, moon lore or placeholder cards", () => {
    expect(buildPilotDiscoverCulture()).toEqual({
      sayings: { id: "traditional-sayings", title: "Si diceva che...", cards: [] },
      traditions: { id: "traditions", title: "Tradizioni del Friûl", cards: [] },
      earth: { title: "", items: [] },
    });
    expect(buildPilotDiscoverCulture({ calendar: { moon: { phase: "Luna nuova" }, proverb: { title: "Proverbio", body: "" } } }).traditions.cards).toEqual([]);
  });

  it("does not mutate either shared model, including deeply frozen inputs", () => {
    const input = { calendar: calendar(), sections: [{ id: "rituals", cards: [ritual] }], excludedCards: [], copy: { traditionalSayingsTitle: "Titolo esistente" } };
    const before = JSON.stringify(input);
    deepFreeze(input);
    const result = buildPilotDiscoverCulture(input);
    expect(JSON.stringify(input)).toBe(before);
    expect(result.traditions.cards[0]).not.toBe(ritual);
    expect(result.earth.items).not.toBe(input.calendar.earth.items);
  });
});
