import { describe, expect, it } from "vitest";

import normalizedFixture from "../../tests/fixtures/PW20260606.normalized.json";
import {
  buildStructuredOsmerZones,
  mapOsmerAreaToCondition,
  mergeForecastWithOsmer,
  OSMER_AREA_TO_MAP_ZONE_ID,
} from "./osmerAdapter";

const fixtureDay = normalizedFixture.days[0];

describe("OSMER structured forecast adapter", () => {
  it("maps the official A1-A9 nodes onto the app map zones", () => {
    expect(OSMER_AREA_TO_MAP_ZONE_ID).toEqual({
      A1: "carnia",
      A2: "giulie",
      A3: "pedemontana-ovest",
      A4: "pedemontana-est",
      A5: "pordenonese",
      A6: "friuli",
      A7: "gorizia",
      A8: "laguna",
      A9: "carso",
    });
  });

  it("resolves the real 07/06 fixture without spreading Carnic rain to plains and coast", () => {
    expect(mapOsmerAreaToCondition(fixtureDay.areas9.A1)).toMatchObject({
      condition: "pioggia debole",
      emphasis: "loaded",
      lightning: false,
    });
    expect(mapOsmerAreaToCondition(fixtureDay.areas9.A3)).toMatchObject({
      condition: "pioggia debole",
      emphasis: "loaded",
      lightning: false,
    });
    expect(mapOsmerAreaToCondition(fixtureDay.areas9.A5)).toMatchObject({
      condition: "poco nuvoloso",
      emphasis: "light",
      lightning: false,
    });

    for (const areaId of ["A6", "A7", "A8", "A9"]) {
      expect(mapOsmerAreaToCondition(fixtureDay.areas9[areaId]).condition).not.toMatch(/pioggia|temporale|rovesc/);
    }
  });

  it("builds nine app zones from the structured fixture", () => {
    const mapZones = Object.values(OSMER_AREA_TO_MAP_ZONE_ID).map((id) => ({
      id,
      label: id,
      area: "fixture",
      x: 0,
      y: 0,
    }));
    const zones = buildStructuredOsmerZones(fixtureDay.areas9, mapZones);

    expect(zones).toHaveLength(9);
    expect(zones.find((zone) => zone.id === "carnia")).toMatchObject({
      osmerAreaId: "A1",
      condition: "pioggia debole",
      source: "osmer_structured",
    });
    expect(zones.find((zone) => zone.id === "pordenonese")).toMatchObject({
      osmerAreaId: "A5",
      condition: "poco nuvoloso",
      source: "osmer_structured",
    });
  });

  it("keeps official projected marker conditions distinct from native XML symbols", () => {
    expect(mapOsmerAreaToCondition({
      source_kind: "official_projected",
      projected_condition: "temporale variabile",
      symbols: {
        temporale: { id: "storm", code: 13 },
      },
    })).toMatchObject({
      condition: "temporale variabile",
      emphasis: "storm",
      lightning: true,
      source: "official_projected",
    });

    expect(mapOsmerAreaToCondition({
      source_kind: "official_projected",
      projected_condition: "pioggia intensa",
      symbols: {
        pioggia: { id: "intense_rain", code: 9 },
      },
    })).toMatchObject({
      condition: "pioggia intensa",
      emphasis: "loaded",
      lightning: false,
      source: "official_projected",
    });
  });

  it.each([
    ["heavy_rain", "pioggia abbondante"],
    ["intense_rain", "pioggia intensa"],
    ["extreme_rain", "pioggia molto intensa"],
  ])("keeps OSMER rain intensity %s visible in the marker condition", (rainId, condition) => {
    expect(mapOsmerAreaToCondition({
      source_kind: "structured_xml",
      symbols: {
        cielo: { id: "overcast", code: 4 },
        pioggia: { id: rainId },
        neve: { id: "none", code: 100 },
        temporale: { id: "none", code: 100 },
        nebbia: { id: "none", code: 100 },
      },
    })).toMatchObject({
      condition,
      emphasis: "loaded",
      lightning: false,
      source: "osmer_structured",
    });
  });

  it("keeps the sky marker when OSMER reports thunderstorm without rain symbol", () => {
    expect(mapOsmerAreaToCondition({
      source_kind: "structured_xml",
      symbols: {
        cielo: { id: "mostly_sunny", code: 1 },
        pioggia: { id: "none", code: 100 },
        neve: { id: "none", code: 100 },
        temporale: { id: "storm", code: 13 },
        nebbia: { id: "none", code: 100 },
      },
    })).toMatchObject({
      condition: "poco nuvoloso",
      emphasis: "light",
      lightning: true,
      source: "osmer_structured",
    });
  });

  it("keeps official projected wind out of the primary weather marker", () => {
    expect(mapOsmerAreaToCondition({
      source_kind: "official_projected",
      projected_condition: "vento con cielo sereno",
      wind_alert: true,
      symbols: {
        vento: { id: "wind", code: 15 },
      },
    })).toMatchObject({
      condition: "sereno",
      emphasis: "light",
      lightning: false,
      source: "official_projected",
    });
  });

  it("falls back to the sky symbol for official projected wind-only text", () => {
    expect(mapOsmerAreaToCondition({
      source_kind: "official_projected",
      projected_condition: "Vento",
      wind_alert: false,
      symbols: {
        cielo: { id: "mostly_sunny", code: 1 },
        vento: { id: "wind", code: 15 },
      },
    })).toMatchObject({
      condition: "poco nuvoloso",
      emphasis: "light",
      lightning: false,
      source: "official_projected",
    });
  });

  it("attaches structured days by valid_date, not by array index", () => {
    const forecastDays = [
      { date: "2026-06-08", label: "Lunedi" },
    ];
    const osmerStructured = {
      days: [
        { valid_date: "2026-06-07", areas9: { A1: { marker: "oggi" } } },
        { valid_date: "2026-06-08", areas9: { A1: { marker: "domani" } } },
      ],
    };

    const merged = mergeForecastWithOsmer(forecastDays, osmerStructured);

    expect(merged[0].osmer_structured_day.valid_date).toBe("2026-06-08");
    expect(merged[0].osmer_structured_day.areas9.A1.marker).toBe("domani");
  });
});
