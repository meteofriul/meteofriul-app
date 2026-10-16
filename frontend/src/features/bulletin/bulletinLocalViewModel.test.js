import { describe, expect, it } from "vitest";

import { createBulletinLocalDataState } from "./bulletinLocalDataController";
import {
  buildBulletinLocalViewModel,
  filterHourlySlotsByDeviceHour,
} from "./bulletinLocalViewModel";

function buildCurrent(overrides = {}) {
  return {
    city: "Pordenone",
    humidity: 64,
    pressure: 1009,
    wind_speed: 2,
    wind_direction: 41,
    wind_gusts: 6,
    precipitation: 0,
    sunrise: "2026-08-02T05:53",
    sunset: "2026-08-02T20:37",
    station: {
      station: "Pordenone",
      time: "22:00",
      humidity: 64,
      pressure: 1008.9,
      wind_speed: 2,
      wind_gusts: 6,
      wind_direction: "ESE",
      precipitation: 0,
    },
    hourly_next_12h: Array.from({ length: 12 }, (_, index) => ({
      time: `2026-08-03T${String(index).padStart(2, "0")}:00`,
      temperature: 27 - index * 0.2,
      precipitation_probability: index * 3,
      weathercode: index < 6 ? 2 : 1,
    })),
    pollen_data: {
      level: "Medi",
      values: {
        ambrosia: 0.6,
        artemisia: 45.1,
        graminacee: 29.5,
      },
    },
    ...overrides,
  };
}

function buildState(current = buildCurrent(), options = {}) {
  return createBulletinLocalDataState({
    city: "Pordenone",
    current,
    updatedAt: "2026-08-02T21:05:00.000Z",
  }, options);
}

describe("bulletin local view model", () => {
  it("shows ICON sources and all six zero CAMS concentrations without inventing a health level", () => {
    const raw = buildCurrent({
      primary_source: "icon2i_local_pilot", precipitation: null, humidity: 45,
      data_quality: {
        run_utc: "2026-09-03T00:00:00Z", valid_at_utc: "2026-09-03T16:00:00Z",
        cams_run_utc: "2026-09-03T00:00:00Z", cams_valid_at_utc: "2026-09-03T16:00:00Z",
      },
      pollen_data: { status: "experimental_model_snapshot", level: "Alto",
        values: { ontano: 0, betulla: 0, graminacee: 0, artemisia: 0, olivo: 0, ambrosia: 0 } },
    });
    const model = buildBulletinLocalViewModel(buildState(raw));
    expect(model.metrics).toContainEqual(expect.objectContaining({ id: "humidity", source: "icon2i", value: "45%" }));
    expect(model.metrics.some((metric) => metric.id === "precipitation")).toBe(false);
    expect(model.hourlySourceLabel).toBe("ICON-2I · snapshot locale");
    expect(model.sourceLabel).not.toMatch(/Open-Meteo|Osservazioni/);
    expect(model.observationLabel).toContain("03/09/26");
    expect(model.observationLabel).not.toContain("Aggiornato alle");
    expect(model.pollen).toMatchObject({
      available: true,
      status: "experimental_model_snapshot",
      tone: "available",
      level: "Previsione sperimentale · nessun livello sanitario",
    });
    expect(model.pollen.values).toHaveLength(6);
    expect(model.pollen.values.every((entry) => entry.value === 0 && entry.displayValue === "0")).toBe(true);
    expect(model.localPilot.run_utc).toBe("2026-09-03T00:00:00Z");
  });

  it("keeps the ICON source truthful and removes CAMS claims in degraded local-pilot data", () => {
    const diagnostic = { provider: "cams_europe", status: "unavailable", code: "HTTP_ERROR" };
    const raw = buildCurrent({
      primary_source: "icon2i_local_pilot",
      station: null,
      data_quality: {
        run_utc: "2026-09-03T00:00:00Z",
        valid_at_utc: "2026-09-03T16:00:00Z",
        cams_status: "unavailable",
        cams_run_utc: null,
        cams_valid_at_utc: null,
        cams_diagnostic: diagnostic,
      },
      pollen_data: {
        status: "unavailable",
        values: {},
        diagnostic,
      },
    });
    const model = buildBulletinLocalViewModel(buildState(raw));

    expect(model.hourlySourceLabel).toBe("ICON-2I · snapshot locale");
    expect(model.sourceLabel).toBe("ICON-2I · snapshot locale");
    expect(model.detailsSourceLabel).toBe("ICON-2I · snapshot locale");
    expect(model.pollen).toMatchObject({
      available: false, status: "unavailable", tone: "unavailable", values: [],
    });
    expect(model.localPilot).toMatchObject({
      cams_available: false,
      cams_status: "unavailable",
      cams_diagnostic: diagnostic,
    });
    expect(JSON.stringify(model)).not.toMatch(/Open-Meteo|CAMS · previsione sperimentale/);
  });

  it("keeps missing pollen missing and small positive traces distinct from zero", () => {
    const current = buildCurrent({ primary_source: "icon2i_local_pilot", station: null, precipitation: 0,
      pollen_data: { status: "experimental_model_snapshot", level: null,
        values: { ontano: null, betulla: 1e-9, graminacee: -1, artemisia: 0 } } });
    const model = buildBulletinLocalViewModel(buildState(current));
    expect(model.metrics).toContainEqual(expect.objectContaining({ id: "precipitation", label: "Precipitazioni", source: "icon2i", value: "0 mm" }));
    expect(model.pollen.values.find((entry) => entry.id === "betulla")).toMatchObject({ value: 1e-9, displayValue: "<0,01" });
    expect(model.pollen.values.find((entry) => entry.id === "ontano")).toMatchObject({ value: null, displayValue: "—" });
    expect(model.pollen.values.find((entry) => entry.id === "graminacee")).toMatchObject({ value: null, displayValue: "—" });
    current.pollen_data.values = { ontano: null, betulla: null };
    expect(buildBulletinLocalViewModel(buildState(current)).pollen).toMatchObject({ available: false, tone: "unavailable", values: [] });
  });

  it("separates observed metrics, model evolution and pollen estimate", () => {
    const model = buildBulletinLocalViewModel(buildState(), {
      language: "it",
      location: { city: "Pordenone" },
    });

    expect(model.title).toBe("A Pordenone");
    expect(model.observationLabel).toBe("Stazione OSMER Pordenone · ore 22:00");
    expect(model.metrics).toEqual([
      expect.objectContaining({ id: "humidity", source: "osmer", value: "64%" }),
      expect.objectContaining({ id: "pressure", source: "osmer", value: "1009 hPa" }),
      expect.objectContaining({ id: "wind", detail: "ESE · raffiche 6 km/h", value: "2 km/h" }),
      expect.objectContaining({ id: "precipitation", source: "osmer", tone: "inactive", value: "0 mm" }),
    ]);
    expect(model.hourly).toHaveLength(6);
    expect(model.hourlySourceLabel).toBe("Evoluzione Open-Meteo");
    expect(model.hourly.map((slot) => slot.time)).toEqual(["00:00", "02:00", "04:00", "06:00", "08:00", "10:00"]);
    expect(model.hourly.every((slot) => slot.temperatureTone === "warm")).toBe(true);
    expect(model.pollen).toMatchObject({
      detail: "Artemisia · Graminacee",
      level: "Livello medio",
      tone: "medium",
    });
    expect(model.sourceLabel).toBe(
      "Osservazioni ARPA FVG · Evoluzione Open-Meteo · Pollini CAMS",
    );
    expect(model.detailsSourceLabel).toBe("Osservazioni ARPA FVG · Pollini CAMS");
  });

  it("drops past cache slots using the device hour before sampling the evolution", () => {
    const firstHour = new Date(2026, 7, 18, 19, 0, 0);
    const current = buildCurrent({
      hourly_next_12h: Array.from({ length: 12 }, (_, index) => {
        const slotTime = new Date(firstHour.getTime() + index * 60 * 60 * 1000);
        const year = slotTime.getFullYear();
        const month = String(slotTime.getMonth() + 1).padStart(2, "0");
        const day = String(slotTime.getDate()).padStart(2, "0");
        const hour = String(slotTime.getHours()).padStart(2, "0");

        return {
          time: `${year}-${month}-${day}T${hour}:00`,
          temperature: 28 - index * 0.2,
          precipitation_probability: index,
          weathercode: 1,
        };
      }),
    });

    const model = buildBulletinLocalViewModel(buildState(current), {
      language: "it",
      now: new Date(2026, 7, 18, 20, 18, 0),
    });

    expect(model.hourly.map((slot) => slot.time)).toEqual([
      "20:00",
      "22:00",
      "00:00",
      "02:00",
      "04:00",
      "06:00",
    ]);
  });

  it("fills the evolution from the cached hourly reservoir on the next morning", () => {
    const firstHour = new Date(2026, 7, 18, 20, 0, 0);
    const current = buildCurrent({
      hourly_forecast: Array.from({ length: 48 }, (_, index) => {
        const slotTime = new Date(firstHour.getTime() + index * 60 * 60 * 1000);
        const year = slotTime.getFullYear();
        const month = String(slotTime.getMonth() + 1).padStart(2, "0");
        const day = String(slotTime.getDate()).padStart(2, "0");
        const hour = String(slotTime.getHours()).padStart(2, "0");

        return {
          time: `${year}-${month}-${day}T${hour}:00`,
          temperature: 22 + index * 0.1,
          precipitation_probability: index,
          weathercode: 1,
        };
      }),
    });

    const model = buildBulletinLocalViewModel(buildState(current), {
      language: "it",
      now: new Date(2026, 7, 19, 9, 3, 0),
    });

    expect(model.hourly.map((slot) => slot.time)).toEqual([
      "09:00",
      "11:00",
      "13:00",
      "15:00",
      "17:00",
      "19:00",
    ]);
  });

  it("distinguishes the repeated hour when daylight-saving time ends", () => {
    const slots = [
      { time: "2026-10-25T02:00+02:00" },
      { time: "2026-10-25T02:00+01:00" },
      { time: "2026-10-25T03:00+01:00" },
    ];

    const result = filterHourlySlotsByDeviceHour(slots, {
      now: new Date("2026-10-25T02:30:00+01:00"),
    });

    expect(result).toEqual(slots.slice(1));
  });

  it("keeps pollen visible with an explicit unavailable state", () => {
    const current = buildCurrent({ pollen_data: null });
    const model = buildBulletinLocalViewModel(buildState(current), { language: "it" });

    expect(model.pollen).toMatchObject({
      available: false,
      level: "Dati pollinici non disponibili",
      tone: "unavailable",
    });
    expect(model.detailsSourceLabel).toBe("Osservazioni ARPA FVG");
  });

  it("shows the locality while keeping the observed station separate", () => {
    const model = buildBulletinLocalViewModel(buildState(), {
      language: "it",
      location: {
        city: "Fontanafredda",
        displayName: "Vigonovo",
        locality: { id: "irdat:vigonovo", name: "Vigonovo" },
        municipality: { istatCode: "093022", name: "Fontanafredda" },
      },
    });

    expect(model.city).toBe("Vigonovo");
    expect(model.title).toBe("A Vigonovo");
    expect(model.observationLabel).toBe("Stazione OSMER Pordenone · ore 22:00");
  });

  it("distinguishes active rain and severe pollen without changing their values", () => {
    const base = buildCurrent();
    const current = buildCurrent({
      station: { ...base.station, precipitation: 2.4 },
      pollen_data: { level: "Alto", values: { graminacee: 78 } },
    });
    const model = buildBulletinLocalViewModel(buildState(current), { language: "it" });

    expect(model.metrics.find((metric) => metric.id === "precipitation")).toMatchObject({
      tone: "active",
      value: "2 mm",
    });
    expect(model.pollen).toMatchObject({ level: "Livello alto", tone: "high" });
  });

  it("marks fallback metrics as model data when no station value exists", () => {
    const current = buildCurrent({
      station: {
        station: "Udine",
        time: "00:00",
        condition: "Variabile",
      },
    });
    const model = buildBulletinLocalViewModel(buildState(current), { language: "it" });

    expect(model.metrics.every((metric) => metric.source === "open-meteo")).toBe(true);
    expect(model.observationLabel).toContain("Aggiornato alle");
    expect(model.observationLabel).not.toContain("Stazione OSMER");
    expect(model.sourceLabel).toContain("Evoluzione Open-Meteo");
    expect(model.sourceLabel).not.toContain("Osservazioni ARPA FVG");
  });

  it("uses concise Friulian presentation copy without Italian fallback", () => {
    const model = buildBulletinLocalViewModel(buildState(), {
      language: "fur",
      location: { city: "Pordenone" },
    });

    expect(model.changeLabel).toBe("Cambie");
    expect(model.city).toBe("Pordenon");
    expect(model.title).toContain("Pordenon");
    expect(model.observationLabel).toContain("Pordenon");
    expect(model.evolutionLabel).toBe("Prossimis 12 oris");
    expect(model.metrics.map((metric) => metric.label)).toEqual([
      "Umiditât",
      "Pression",
      "Vint",
      "Pluie",
    ]);
    expect(model.pollen).toMatchObject({
      detail: "Artemisie · Graminaceis",
      level: "Nivel medi",
    });
  });

  it("labels a fallback snapshot discreetly instead of showing an error card", () => {
    const model = buildBulletinLocalViewModel(buildState(buildCurrent(), {
      error: new Error("network_error"),
      fromCache: true,
      isStale: true,
    }), { language: "it" });

    expect(model.observationLabel).toContain("Ultimo dato disponibile");
    expect(model.title).toBe("A Pordenone");
  });

  it("omits the entire supplementary card when no useful local data survives", () => {
    expect(buildBulletinLocalViewModel({ current: null }, { language: "it" })).toBeNull();
  });
});
