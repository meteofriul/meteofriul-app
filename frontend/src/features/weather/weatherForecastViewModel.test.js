import { describe, expect, it } from "vitest";

import { buildWeatherForecastViewModel } from "./weatherForecastViewModel";

const HOUR_MS = 60 * 60 * 1000;
const NOW = "2026-08-30T10:00:00+02:00";
const FIRST_HOUR = "2026-08-30T10:00:00+02:00";
const CATALOG_SHA = "a".repeat(64);

function buildSlots({ count = 48, precipitation = 1, start = FIRST_HOUR } = {}) {
  const firstMs = Date.parse(start);
  return Array.from({ length: count }, (_, index) => {
    const timeMs = firstMs + index * HOUR_MS;
    return {
      cloud_cover: 20 + index % 60,
      condition: index % 3 ? "Sereno" : "Poco nuvoloso",
      feels_like: 19 + index / 10,
      humidity: 55 + index % 20,
      interval_end: new Date(timeMs).toISOString(),
      interval_start: new Date(timeMs - HOUR_MS).toISOString(),
      is_day: index % 24 < 12 ? 1 : 0,
      precipitation,
      precipitation_probability: null,
      pressure: 1010 + index / 10,
      primary_source: "icon2i_local_pilot",
      temperature: 20 + index / 10,
      time: new Date(timeMs).toISOString(),
      wind_direction: 45,
      wind_gusts: 15 + index / 10,
      wind_speed: 8 + index / 10,
    };
  });
}

function buildState({
  cache = {},
  camsStatus = "unavailable",
  city = "Pordenone",
  forecast = null,
  generatedAt = null,
  primarySource = "icon2i_local_pilot",
  run = "2026-08-30T06:00:00Z",
  slots = buildSlots(),
  source = null,
} = {}) {
  return {
    city,
    current: {},
    error: null,
    forecast: {
      city,
      forecast: forecast || [
        { date: "2026-08-30", min_temp: null, max_temp: null, partial_day: true },
        { date: "2026-08-31", min_temp: 8, max_temp: 24, partial_day: false },
      ],
    },
    isStale: false,
    rawCurrent: {
      cache,
      city,
      data_quality: {
        cams_status: camsStatus,
        catalog_sha256: CATALOG_SHA,
        generated_at: generatedAt,
        municipality_istat: "093033",
        run_utc: run,
        status: "fresh",
        valid_at_utc: slots[0]?.time,
      },
      hourly_forecast: slots,
      primary_source: primarySource,
      ...(source ? { source } : {}),
    },
    status: "fresh",
  };
}

const LOCATION = {
  city: "Pordenone",
  municipality: { istatCode: "093033", name: "Pordenone" },
};

describe("weather forecast view model", () => {
  it("uses Friulian weekdays independently of browser locale support", () => {
    const now = "2026-09-07T21:00:00+02:00";
    const model = buildWeatherForecastViewModel(buildState({ slots: buildSlots({ start: now }) }), {
      language: "fur", location: LOCATION, now,
    });
    expect(model.hourly.groups.map(({ label }) => label)).toEqual(["Vuê", "Doman", "Miercus 9 set"]);
    expect(model.hourly.groups.map(({ shortLabel }) => shortLabel)).toEqual(["Vuê", "Doman", "Miercus"]);
    expect(model.hourly.groups[2].dateLabel).toBe("Miercus 9 setembar");
    expect(model.header.dateLabel).toBe("Lunis 7 setembar");
  });
  it("builds a continuous grouped list and honest Oggi/Domani summaries", () => {
    const model = buildWeatherForecastViewModel(buildState(), {
      language: "it",
      location: LOCATION,
      now: NOW,
    });

    expect(model.header).toMatchObject({
      locationTitle: "Pordenone",
      source: "ICON-2I",
      statusLabel: "Dati verificati",
    });
    expect(model.hourly.items).toHaveLength(48);
    expect(model.hourly.groups.map(({ label }) => label)).toEqual(["Oggi", "Domani", "Martedì 1 set"]);
    expect(model.hourly.groups.map(({ shortLabel }) => shortLabel)).toEqual(["Oggi", "Domani", "Martedì"]);
    expect(model.hourly.groups[2].dateLabel).toBe("Martedì 1 settembre");
    expect(model.header.dateLabel).toBe("Domenica 30 agosto");
    expect(model.hourly.summaries[0]).toMatchObject({
      id: "today",
      label: "Oggi",
      coverageLabel: "Da quest'ora",
    });
    expect(model.hourly.summaries[1]).toMatchObject({
      id: "tomorrow",
      label: "Domani",
      coverageLabel: "Giornata completa",
      minTemperature: "8°",
      maxTemperature: "24°",
      precipitationLabel: "24 mm",
    });
  });

  it.each([
    ["it", "Modello ICON-2I", "08:00", "ICON-2I · aggiornamento modello 30/08/2026, 08:00"],
    ["fur", "Model ICON-2I", "08:00", "ICON-2I · inzornament dal model 30/08/2026, 08:00"],
  ])("builds truthful compact model metadata in %s for a same-day run", (
    language,
    compactSourceLabel,
    compactRunLabel,
    sourceTimingLabel,
  ) => {
    const model = buildWeatherForecastViewModel(buildState(), {
      language,
      location: LOCATION,
      now: NOW,
    });

    expect(model.header).toMatchObject({
      compactRunLabel,
      compactSourceLabel,
      runAt: "2026-08-30T06:00:00Z",
      sourceTimingLabel,
    });
  });

  it("keeps provider attribution distinct between national Open-Meteo and autonomous FVG", () => {
    const roma = buildWeatherForecastViewModel(buildState({
      city: "Roma",
      generatedAt: "2026-08-30T08:15:00Z",
      primarySource: "open_meteo",
      run: null,
      source: {
        active: "open_meteo",
        priority: [{ id: "open_meteo", name: "Open-Meteo" }],
      },
    }), {
      language: "it",
      location: { city: "Roma", lat: 41.9028, lon: 12.4964 },
      now: NOW,
    });
    const pordenone = buildWeatherForecastViewModel(buildState(), {
      language: "it",
      location: LOCATION,
      now: NOW,
    });

    expect(roma.header).toMatchObject({
      compactRunLabel: "10:15",
      compactSourceLabel: "Modello Open-Meteo",
      providerId: "open_meteo",
      source: "Open-Meteo",
      sourceTimingLabel: "Open-Meteo · dati aggiornati 30/08/2026, 10:15",
    });
    expect(roma.header.sourceTimingLabel).not.toContain("ICON");
    expect(pordenone.header).toMatchObject({
      compactSourceLabel: "Modello ICON-2I",
      providerId: "icon2i_local_pilot",
      source: "ICON-2I",
      sourceTimingLabel: "ICON-2I · aggiornamento modello 30/08/2026, 08:00",
    });
  });

  it("keeps the run date visible in compact metadata when the ICON run is from the previous day", () => {
    const model = buildWeatherForecastViewModel(buildState({
      run: "2026-08-29T18:00:00Z",
    }), {
      language: "it",
      location: LOCATION,
      now: NOW,
    });

    expect(model.header).toMatchObject({
      compactRunLabel: "29/08 · 20:00",
      compactSourceLabel: "Modello ICON-2I",
      sourceTimingLabel: "ICON-2I · aggiornamento modello 29/08/2026, 20:00",
    });
  });

  it("does not invent compact run metadata when the source has no run timestamp", () => {
    const model = buildWeatherForecastViewModel(buildState({ run: null }), {
      language: "it",
      location: LOCATION,
      now: NOW,
    });

    expect(model.header.compactRunLabel).toBe("");
    expect(model.header.sourceTimingLabel).toBe("ICON-2I");
  });

  it("does not count an already-ended interval in the Oggi total", () => {
    const slots = buildSlots();
    slots[0].precipitation = 99;
    const model = buildWeatherForecastViewModel(buildState({ slots }), {
      location: LOCATION,
      now: NOW,
    });

    expect(model.hourly.summaries[0].precipitationLabel).toBe("14 mm");
  });

  it("keeps precipitation probability absent instead of deriving it from millimetres", () => {
    const model = buildWeatherForecastViewModel(buildState(), {
      location: LOCATION,
      now: NOW,
    });

    expect(model.hourly.items.every((item) => item.precipitationProbability === null)).toBe(true);
    expect(model.hourly.items.every((item) => !item.ariaLabel.includes("%"))).toBe(true);
  });

  it("retains a missing field only for the same UTC timestamp and preserves its origin", () => {
    const first = buildWeatherForecastViewModel(buildState(), {
      location: LOCATION,
      now: NOW,
    });
    const nextSlots = buildSlots();
    nextSlots[2].temperature = null;
    nextSlots[2].humidity = null;
    const second = buildWeatherForecastViewModel(buildState({
      run: "2026-08-30T09:00:00Z",
      slots: nextSlots,
    }), {
      location: LOCATION,
      now: NOW,
      previousModel: first,
    });
    const third = buildWeatherForecastViewModel(buildState({
      run: "2026-08-30T10:00:00Z",
      slots: nextSlots,
    }), {
      location: LOCATION,
      now: NOW,
      previousModel: second,
    });

    expect(second.hourly.items).toHaveLength(48);
    expect(second.hourly.items[2]).toMatchObject({
      retainedFields: ["humidity", "temperature"],
      temperature: "20°",
      values: { humidity: 57, temperature: 20.2 },
    });
    expect(second.hourly.items[2].retainedOrigins).toEqual({
      humidity: "2026-08-30T06:00:00Z",
      temperature: "2026-08-30T06:00:00Z",
    });
    expect(third.hourly.items[2].retainedOrigins).toEqual(second.hourly.items[2].retainedOrigins);
    expect(nextSlots[2]).toMatchObject({ humidity: null, temperature: null });
  });

  it("does not retain fields across a different municipality scope", () => {
    const first = buildWeatherForecastViewModel(buildState(), {
      location: LOCATION,
      now: NOW,
    });
    const slots = buildSlots();
    slots[0].temperature = null;
    const state = buildState({ city: "Udine", slots });
    state.rawCurrent.data_quality.municipality_istat = "030129";
    const second = buildWeatherForecastViewModel(state, {
      location: { city: "Udine", municipality: { istatCode: "030129", name: "Udine" } },
      now: NOW,
      previousModel: first,
    });

    expect(second.hourly.items[0].temperature).toBeNull();
    expect(second.hourly.items[0].retainedFields).toEqual([]);
  });

  it("expires retained presentation values after the ICON usability age", () => {
    const first = buildWeatherForecastViewModel(buildState({ run: "2026-08-29T06:00:00Z" }), {
      location: LOCATION,
      now: "2026-08-29T10:00:00Z",
    });
    const slots = buildSlots();
    slots[0].temperature = null;
    const second = buildWeatherForecastViewModel(buildState({ slots }), {
      location: LOCATION,
      now: "2026-08-30T06:00:01Z",
      previousModel: first,
    });

    expect(second.hourly.items[0].temperature).toBeNull();
    expect(second.hourly.items[0].retainedFields).toEqual([]);
  });

  it("keeps both autumn 02:00 instants as different rows", () => {
    const times = [
      "2026-10-25T00:00:00Z",
      "2026-10-25T01:00:00Z",
      "2026-10-25T02:00:00Z",
    ];
    const slots = times.map((time, index) => ({
      ...buildSlots({ count: 1 })[0],
      interval_end: time,
      interval_start: new Date(Date.parse(time) - HOUR_MS).toISOString(),
      temperature: 10 + index,
      time,
    }));
    const model = buildWeatherForecastViewModel(buildState({ slots }), {
      location: LOCATION,
      now: "2026-10-25T01:30:00+02:00",
    });

    expect(model.hourly.items.map(({ time }) => time)).toEqual(["02:00", "02:00", "03:00"]);
    expect(new Set(model.hourly.items.map(({ timestamp }) => timestamp)).size).toBe(3);
  });

  it("marks a verified runtime fallback as the last available update", () => {
    const model = buildWeatherForecastViewModel(buildState({
      cache: { runtime_fallback: true },
    }), {
      location: LOCATION,
      now: NOW,
    });

    expect(model.header).toMatchObject({
      statusLabel: "Ultimo aggiornamento disponibile",
      statusTone: "warning",
    });
  });

  it("keeps CAMS as a separate snapshot and removes unavailable values", () => {
    const state = buildState({ camsStatus: "fresh" });
    state.rawCurrent.pollen_data = {
      status: "experimental_model_snapshot",
      run_utc: "2026-08-30T00:00:00Z",
      valid_at_utc: "2026-08-30T08:00:00Z",
      values: { ambrosia: null, graminacee: 2.5 },
    };
    const model = buildWeatherForecastViewModel(state, {
      location: LOCATION,
      now: NOW,
    });

    expect(model.cams).toMatchObject({
      heading: "Pollini",
      note: "Concentrazioni modellistiche disponibili",
      status: "available",
      validLabel: "Dato valido alle 10:00",
    });
    expect(model.cams.values).toEqual([
      expect.objectContaining({ id: "graminacee", value: 2.5 }),
    ]);
    expect(model.cams).toMatchObject({ airSampleStatus: "current", pollenSampleStatus: "current" });
  });

  it.each([
    ["it", "family", "Ultimo dato verificato · 30/08/2026, 10:00"],
    ["it", "components", "Ultimo dato verificato · 30/08/2026, 10:00"],
    ["fur", "family", "Ultin dât verificât · 30/08/2026, 10:00"],
    ["fur", "components", "Ultin dât verificât · 30/08/2026, 10:00"],
  ])("labels retained CAMS samples in %s from %s status fields", (language, statusSource, label) => {
    const state = buildState({ camsStatus: "stale" });
    if (statusSource === "family") state.rawCurrent.data_quality.cams_sample_status = "last_known";
    state.rawCurrent.data_quality.cams_valid_at_utc = "2026-08-30T08:00:00Z";
    state.rawCurrent.pollen_data = {
      ...(statusSource === "components" ? { sample_status: "last_known" } : {}),
      status: "experimental_model_snapshot",
      run_utc: "2026-08-30T00:00:00Z",
      valid_at_utc: "2026-08-30T08:00:00Z",
      values: { ambrosia: 1.5, graminacee: 2.5 },
    };
    state.rawCurrent.air_quality_data = {
      run_at: "2026-08-30T00:00:00Z",
      ...(statusSource === "components" ? { sample_status: "last_known" } : {}),
      valid_at: "2026-08-30T08:00:00Z",
      values: { ozone: 42 },
    };
    const model = buildWeatherForecastViewModel(state, { language, location: LOCATION, now: NOW });

    expect(model.cams).toMatchObject({
      airLastKnownLabel: label,
      airSampleStatus: "last_known",
      pollenLastKnownLabel: label,
      pollenSampleStatus: "last_known",
      status: "available",
    });
  });
});


it.each([
  ["it", "Caricamento…", "Dati non disponibili"],
  ["fur", "In cjariament…", "Dâts no disponibii"],
])("keeps initial and deferred CAMS loading separate from terminal unavailability in %s", (language, pendingLabel, unavailableLabel) => {
  const options = { language, location: LOCATION, now: NOW };
  const empty = { status: "empty", rawCurrent: null, current: null, forecast: null };
  expect(buildWeatherForecastViewModel(empty, { ...options, loading: true }).cams)
    .toMatchObject({ airStatus: "pending", status: "pending", note: pendingLabel });
  expect(buildWeatherForecastViewModel({ ...empty, error: "Network unavailable" }, options).cams)
    .toMatchObject({ airStatus: "unavailable", status: "unavailable", note: unavailableLabel });
  expect(buildWeatherForecastViewModel(buildState({ camsStatus: "pending" }), options).cams)
    .toMatchObject({ airStatus: "pending", status: "pending", note: pendingLabel });
  expect(buildWeatherForecastViewModel(buildState({ camsStatus: "unavailable" }), { ...options, loading: true }).cams)
    .toMatchObject({ airStatus: "unavailable", status: "unavailable", note: unavailableLabel });
});

it("preserves verified zero values during refresh and treats air and pollen independently", () => {
  const state = buildState({ camsStatus: "pending" });
  state.rawCurrent.air_quality_data = { values: { "particulate_matter_2.5um": 0 } };
  const options = { location: LOCATION, now: NOW, loading: true };
  expect(buildWeatherForecastViewModel(state, options).cams)
    .toMatchObject({ airStatus: "available", status: "pending" });
  state.rawCurrent.pollen_data = { status: "experimental_model_snapshot", values: { graminacee: 0 } };
  const both = buildWeatherForecastViewModel(state, options).cams;
  expect(both).toMatchObject({ airStatus: "available", status: "available" });
  expect(both.values).toEqual([expect.objectContaining({ value: 0 })]);
  state.rawCurrent.air_quality_data = null;
  expect(buildWeatherForecastViewModel(state, options).cams)
    .toMatchObject({ airStatus: "pending", status: "available" });
});
