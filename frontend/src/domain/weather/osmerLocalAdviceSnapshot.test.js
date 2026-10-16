import { describe, expect, it } from "vitest";

import {
  buildOsmerLocalAdviceSnapshot,
  getOsmerLocalAreaId,
} from "./osmerLocalAdviceSnapshot";

const NONE = Object.freeze({ code: 100, id: "none", label: "" });

function symbols(overrides = {}) {
  return {
    cielo: { code: 3, id: "cloudy", label: "nuvoloso" },
    nebbia: NONE,
    neve: NONE,
    pioggia: NONE,
    temporale: NONE,
    vento: NONE,
    ...overrides,
  };
}

function dayFor(areaId = "A5", symbolOverrides = {}) {
  return {
    areas9: {
      [areaId]: {
        id: areaId,
        source_kind: "structured_xml",
        symbols: symbols(symbolOverrides),
        text: "ALLERTA E TEMPORALI FINO A SERA: testo narrativo da non interpretare.",
        valid_date: "2026-09-17",
      },
    },
    osmer_structured_source: {
      data_emissione: "2026-09-17T08:23:00Z",
      id_emissione: "PW26091710",
      is_stale: false,
      raw_hash: "sha256-a5-20260917",
      source_status: "normalized",
    },
    source_kind: "structured_xml",
    valid_date: "2026-09-17",
  };
}

describe("osmerLocalAdviceSnapshot", () => {
  it.each([
    ["Pordenone", "A5"],
    [{ city: "Udine" }, "A6"],
    ["Gorizia", "A7"],
    ["Lignano", "A8"],
    ["Lignano Sabbiadoro", "A8"],
    ["Trieste", "A9"],
  ])("maps the exact local OSMER point %j to %s", (location, areaId) => {
    expect(getOsmerLocalAreaId(location)).toBe(areaId);
  });

  it.each([
    "Cordenons",
    "Pordenone (PN)",
    "Comune di Pordenone",
    "Lignano Riviera",
    { name: "Pordenone" },
    null,
  ])("rejects a locality that is not an exact supported OSMER point: %j", (location) => {
    expect(getOsmerLocalAreaId(location)).toBeNull();
  });

  it("builds an atomic rainy snapshot only from structured symbols and per-day provenance", () => {
    const day = dayFor("A5", {
      pioggia: { code: 7, id: "moderate_rain", label: "moderata" },
    });

    expect(buildOsmerLocalAdviceSnapshot(day, { city: "Pordenone" })).toEqual({
      advice: {
        group: "rain",
        label: "Ombrello consigliato",
        umbrellaLevel: "needed",
      },
      areaId: "A5",
      headline: "Nuvoloso con piogge",
      icon: expect.objectContaining({ type: "Rain" }),
      isStale: false,
      issuedAt: "2026-09-17T08:23:00Z",
      snapshotKey: "osmer:PW26091710:2026-09-17T08:23:00Z:sha256-a5-20260917:2026-09-17:A5",
      validDate: "2026-09-17",
    });
  });

  it("never interprets narrative bulletin or alert wording when symbols only say cloudy", () => {
    const snapshot = buildOsmerLocalAdviceSnapshot(dayFor(), "Pordenone");

    expect(snapshot).toMatchObject({
      advice: null,
      headline: "Nuvoloso",
      icon: { type: "Cloud" },
    });
    expect(JSON.stringify(snapshot)).not.toMatch(/allerta|rettifica|sera|temporali/iu);
  });

  it.each([
    ["storm", { temporale: { code: 13, id: "storm", label: "temporale" } }, "storm", "Prudenza durante i temporali", "Storm"],
    ["snow", { neve: { code: 10, id: "moderate_snow", label: "moderata" } }, "snow", "Prudenza in presenza di neve", "Snow"],
    ["fog", { nebbia: { code: 14, id: "fog", label: "nebbia" } }, "fog", "Prudenza per la visibilità ridotta", "Fog"],
    ["wind", { vento: { code: 25, id: "north_strong", intensity: "strong" } }, "wind", "Prudenza per vento forte", "Cloud"],
  ])("derives %s advice from structured symbols without temporal claims", (_name, overrides, group, label, iconType) => {
    const snapshot = buildOsmerLocalAdviceSnapshot(dayFor("A5", overrides), "Pordenone");

    expect(snapshot.advice).toMatchObject({ group, label });
    expect(snapshot.icon.type).toBe(iconType);
    expect(snapshot.advice.label).not.toMatch(/fino|mattin|pomerig|sera|allerta|rettifica/iu);
  });

  it("does not turn an OSMER breeze symbol into a warning", () => {
    const snapshot = buildOsmerLocalAdviceSnapshot(dayFor("A5", {
      vento: { code: 35, id: "breeze", intensity: "breeze" },
    }), "Pordenone");

    expect(snapshot).toMatchObject({ advice: null, headline: "Nuvoloso" });
  });

  it.each([
    ["mixed day", (day) => { day.source_kind = "mixed"; }],
    ["projected day", (day) => { day.source_kind = "official_projected"; }],
    ["mixed area", (day) => { day.areas9.A5.source_kind = "mixed"; }],
    ["healed area", (day) => { day.areas9.A5.healed_from_previous_snapshot = true; }],
    ["healed day", (day) => { day.healed_missing_areas = ["A5"]; }],
    ["mixed quality", (day) => { day.quality = { source_mix: true }; }],
    ["stale provenance", (day) => { day.osmer_structured_source.is_stale = true; }],
    ["unknown freshness", (day) => { delete day.osmer_structured_source.is_stale; }],
    ["missing emission id", (day) => { delete day.osmer_structured_source.id_emissione; }],
    ["missing emission date", (day) => { delete day.osmer_structured_source.data_emissione; }],
    ["missing raw hash", (day) => { delete day.osmer_structured_source.raw_hash; }],
    ["invalid emission date", (day) => { day.osmer_structured_source.data_emissione = "oggi"; }],
    ["wrong area date", (day) => { day.areas9.A5.valid_date = "2026-09-16"; }],
  ])("fails closed for %s", (_name, mutate) => {
    const day = dayFor();
    mutate(day);

    expect(buildOsmerLocalAdviceSnapshot(day, "Pordenone")).toBeNull();
  });

  it.each([
    ["missing symbols", (day) => { delete day.areas9.A5.symbols.pioggia; }],
    ["unknown symbol", (day) => { day.areas9.A5.symbols.pioggia = { code: 77, id: "possibly_rain" }; }],
    ["incoherent none", (day) => { day.areas9.A5.symbols.pioggia = { code: 7, id: "none" }; }],
  ])("fails closed for malformed structured evidence: %s", (_name, mutate) => {
    const day = dayFor();
    mutate(day);

    expect(buildOsmerLocalAdviceSnapshot(day, "Pordenone")).toBeNull();
  });
});
