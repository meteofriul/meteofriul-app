import { describe, expect, it } from "vitest";

import { normalizeWeatherData } from "./normalizedWeather";
import { buildIconLocalAdvice } from "./iconLocalAdvice";

const NOW = "2026-09-26T17:30:00Z";

function buildState(slots, overrides = {}) {
  const rawCurrent = {
    primary_source: "icon2i_local_pilot",
    hourly_forecast: slots,
  };

  return {
    current: normalizeWeatherData(rawCurrent),
    isStale: false,
    rawCurrent,
    status: "fresh",
    ...overrides,
  };
}

function slot(hour, overrides = {}) {
  return {
    condition: "Sereno",
    precipitation: 0,
    temperature: 20,
    time: `2026-09-26T${String(hour).padStart(2, "0")}:00:00Z`,
    wind_gusts: 10,
    wind_speed: 5,
    ...overrides,
  };
}

describe("buildIconLocalAdvice", () => {
  it("builds a branded stable-weather suggestion from the next ICON hours", () => {
    const advice = buildIconLocalAdvice(buildState([
      slot(18, { temperature: 21 }),
      slot(19, { temperature: 20 }),
      slot(20, { temperature: 19 }),
    ]), { language: "it", now: NOW });

    expect(advice).toEqual({
      group: "stable",
      label: "Il tempo tiene: una buona occasione per stare all’aperto.",
      source: "icon2i",
      title: "Consigliato",
      windowHours: 12,
    });
  });

  it("uses the first available ICON slot when no reference clock is supplied", () => {
    const advice = buildIconLocalAdvice(buildState([
      slot(18, { temperature: 21 }),
      slot(19, { temperature: 20 }),
    ]));

    expect(advice).toMatchObject({ group: "stable", source: "icon2i" });
  });

  it("prioritizes a structured storm slot over rain without reading bulletin prose", () => {
    const advice = buildIconLocalAdvice(buildState([
      slot(18, { condition: "Pioggia", precipitation: 1.2 }),
      slot(19, { condition: "Temporale", precipitation: 0.4 }),
      slot(20),
    ]), { language: "it", now: NOW });

    expect(advice).toMatchObject({
      group: "storm",
      label: "Se il cielo brontola, niente attese: cerca subito riparo.",
      source: "icon2i",
    });
  });

  it("localizes the branded suggestion in Friulian", () => {
    const advice = buildIconLocalAdvice(buildState([
      slot(18, { condition: "Pioggia", precipitation: 0.8 }),
    ]), { language: "fur", now: NOW });

    expect(advice).toMatchObject({
      group: "rain",
      label: "Ombrele a puartade di man: tes prossimis oris e podarès coventâ.",
      title: "Conseât",
    });
  });

  it.each([
    ["stale snapshot", { isStale: true }],
    ["stale state", { status: "stale" }],
  ])("refuses a %s", (_label, overrides) => {
    expect(buildIconLocalAdvice(buildState([slot(18)], overrides), { now: NOW })).toBeNull();
  });

  it("refuses forecasts from providers other than ICON", () => {
    const state = buildState([slot(18)]);
    state.rawCurrent.primary_source = "open_meteo";

    expect(buildIconLocalAdvice(state, { now: NOW })).toBeNull();
  });
});
