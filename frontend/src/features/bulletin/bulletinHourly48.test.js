import { describe, expect, it } from "vitest";

import { createBulletinLocalDataState } from "./bulletinLocalDataController";
import { buildBulletinLocalViewModel } from "./bulletinLocalViewModel";

const HOUR_MS = 60 * 60 * 1000;
const FIRST_HOUR = "2026-08-30T10:00:00+02:00";
const NOW = "2026-08-30T10:37:00+02:00";

function buildSlots(start = FIRST_HOUR, count = 48) {
  const firstMs = new Date(start).getTime();

  return Array.from({ length: count }, (_, index) => ({
    time: new Date(firstMs + index * HOUR_MS).toISOString(),
    temperature: 20 + index,
    precipitation_probability: index,
    weathercode: 1,
  }));
}

function buildState(current = {}, options = {}) {
  return createBulletinLocalDataState({
    city: "Pordenone",
    updatedAt: FIRST_HOUR,
    current: {
      city: "Pordenone",
      temperature: 24,
      sunrise: "2026-08-30T06:25:00+02:00",
      sunset: "2026-08-30T19:50:00+02:00",
      ...current,
    },
  }, options);
}

function buildModel(slots = buildSlots(), options = {}) {
  return buildBulletinLocalViewModel(buildState({ hourly_forecast: slots }), {
    hourlyHours: 48,
    language: "it",
    now: NOW,
    ...options,
  });
}

describe("48-hour Home evolution", () => {
  it("keeps all 48 complete hourly slots in chronological order without two-hour sampling", () => {
    const slots = buildSlots();
    const model = buildModel([...slots].reverse());

    expect(model.evolutionLabel).toBe("Prossime 48 ore");
    expect(model.hourlySourceLabel).toBe("Evoluzione Open-Meteo");
    expect(model.hourly).toHaveLength(48);
    expect(model.hourly.map((slot) => slot.timestamp)).toEqual(slots.map((slot) => slot.time));
    expect(model.hourly.map((slot) => slot.temperature)).toEqual(slots.map((slot) => `${slot.temperature}°`));
    expect(model.hourly.map((slot) => slot.precipitationProbability)).toEqual(slots.map((slot) => slot.precipitation_probability));
    expect(model.hourly[0]).toMatchObject({ time: "10:00", dayLabel: "Oggi" });
    expect(model.hourly[47]).toMatchObject({ time: "09:00", dayLabel: "01/09" });
    expect(model.hourly.every((slot) => slot.icon && slot.ariaLabel && slot.dateKey)).toBe(true);
  });

  it("keeps the ICON-ready details attached to the hour they describe", () => {
    const slots = buildSlots(FIRST_HOUR, 2);
    Object.assign(slots[0], {
      cloud_cover: 42,
      feels_like: 19.4,
      humidity: 64,
      interval_end: FIRST_HOUR,
      interval_start: "2026-08-30T09:00:00+02:00",
      precipitation: 0.4,
      pressure: 1012.4,
      wind_direction: 45,
      wind_gusts: 16.2,
      wind_speed: 8.4,
    });
    const model = buildModel(slots);

    expect(model.hourly[0]).toMatchObject({
      precipitationAmount: "0,4 mm",
      details: {
        apparentTemperature: "19°",
        cloudCover: "42%",
        humidity: "64%",
        intervalLabel: "09:00–10:00",
        precipitation: "0,4 mm",
        pressure: "1012 hPa",
        windDirection: "NE",
        windGusts: "16 km/h",
        windSpeed: "8 km/h",
      },
    });
    expect(model.hourly[0].ariaLabel).toContain("Precipitazioni 0,4 mm");
    expect(model.hourly[1].details.precipitation).toBe("0 mm");
  });

  it("derives the preceding one-hour interval for cached ICON pilot slots", () => {
    const slots = buildSlots(FIRST_HOUR, 2);
    Object.assign(slots[1], {
      precipitation: 0.4,
      wind_gusts: 16.2,
    });
    const model = buildBulletinLocalViewModel(buildState({
      hourly_forecast: slots,
      primary_source: "icon2i_local_pilot",
    }), {
      hourlyHours: 48,
      language: "it",
      now: NOW,
    });

    expect(model.hourly).toHaveLength(1);
    expect(model.hourly[0].timestamp).toBe(slots[1].time);
    expect(Date.parse(model.hourly[0].timestamp)).toBeGreaterThanOrEqual(Date.parse(NOW));
    expect(model.hourly[0].details.intervalLabel).toBe("10:00–11:00");
    expect(model.hourly[0].details.precipitation).toBe("0,4 mm");
  });

  it("includes the current hour and excludes the instant exactly 48 hours later", () => {
    const slots = buildSlots("2026-08-30T09:00:00+02:00", 51);
    const model = buildModel(slots);

    expect(model.hourly).toHaveLength(48);
    expect(model.hourly[0].timestamp).toBe("2026-08-30T08:00:00.000Z");
    expect(model.hourly[47].timestamp).toBe("2026-09-01T07:00:00.000Z");
    expect(model.hourly.some((slot) => slot.timestamp === "2026-09-01T08:00:00.000Z")).toBe(false);
    expect(model.hourly.some((slot) => slot.timestamp === "2026-08-30T07:00:00.000Z")).toBe(false);
  });

  it("removes malformed times and missing temperatures without losing a genuine zero", () => {
    const slots = buildSlots(FIRST_HOUR, 7);
    slots[0].temperature = 0;
    slots[1].temperature = null;
    delete slots[2].temperature;
    slots[3].temperature = "";
    slots[4].temperature = "invalid";
    slots[5].time = "not-a-date";
    delete slots[6].time;
    const model = buildModel(slots);

    expect(model.hourly).toHaveLength(1);
    expect(model.hourly[0]).toMatchObject({ temperature: "0°", time: "10:00" });
    expect(model.evolutionLabel).toBe("Evoluzione oraria");
  });

  it("deduplicates identical instants even when their textual UTC offsets differ", () => {
    const slots = buildSlots(FIRST_HOUR, 2);
    const model = buildModel([
      slots[1],
      slots[0],
      { ...slots[0], time: "2026-08-30T10:00:00+02:00" },
      { ...slots[1] },
    ]);

    expect(model.hourly).toHaveLength(2);
    expect(model.hourly.map((slot) => slot.time)).toEqual(["10:00", "11:00"]);
    expect(new Set(model.hourly.map((slot) => new Date(slot.timestamp).getTime())).size).toBe(2);
  });

  it("shows only the remaining old-cache hours with an honest partial title", () => {
    const state = buildState({ hourly_forecast: buildSlots() }, { fromCache: true, isStale: true });
    const model = buildBulletinLocalViewModel(state, {
      hourlyHours: 48,
      now: "2026-08-30T23:15:00+02:00",
    });

    expect(model.hourly).toHaveLength(35);
    expect(model.hourly[0]).toMatchObject({ time: "23:00", dayLabel: "Oggi" });
    expect(model.hourly[34]).toMatchObject({ time: "09:00", dayLabel: "01/09" });
    expect(model.evolutionLabel).toBe("Evoluzione oraria");
  });

  it.each([undefined, []])("uses a partial legacy reservoir when hourly_forecast is %s", (forecast) => {
    const legacy = buildSlots(FIRST_HOUR, 12);
    const model = buildBulletinLocalViewModel(buildState({
      hourly_forecast: forecast,
      hourly_next_12h: legacy,
    }), { hourlyHours: 48, now: NOW });

    expect(model.hourly).toHaveLength(12);
    expect(model.hourly.map((slot) => slot.timestamp)).toEqual(legacy.map((slot) => slot.time));
    expect(model.evolutionLabel).toBe("Evoluzione oraria");
  });

  it("does not invent future hours after the entire cached horizon has expired", () => {
    const model = buildModel(buildSlots(), { now: "2026-09-01T10:00:00+02:00" });

    expect(model.hourly).toEqual([]);
    expect(model.evolutionLabel).toBe("Evoluzione oraria");
    expect(model.hourlySourceLabel).toBe("");
  });

  it("localizes the full and partial titles and today's group in Friulian", () => {
    const full = buildModel(buildSlots(), { language: "fur" });
    const partial = buildModel(buildSlots(FIRST_HOUR, 12), { language: "fur" });

    expect(full.evolutionLabel).toBe("Prossimis 48 oris");
    expect(full.hourlySourceLabel).toBe("Evoluzion Open-Meteo");
    expect(full.hourly[0].dayLabel).toBe("Vuê");
    expect(full.hourly[0].ariaLabel).toContain("grâts");
    expect(partial.evolutionLabel).toBe("Evoluzion orarie");
  });

  it("changes day groups at Italian midnight, not UTC midnight", () => {
    const slots = buildSlots("2026-08-30T23:00:00+02:00", 3);
    slots[0].weathercode = 1;
    slots[1].weathercode = 2;
    slots[2].weathercode = 3;
    const model = buildModel(slots, {
      now: "2026-08-30T23:45:00+02:00",
    });

    expect(model.hourly.map((slot) => slot.time)).toEqual(["23:00", "00:00", "01:00"]);
    expect(model.hourly.map((slot) => slot.dayLabel)).toEqual(["Oggi", "31/08", "31/08"]);
    expect(model.hourly[0].dateKey).not.toBe(model.hourly[1].dateKey);
    expect(model.hourly[1].dateKey).toBe(model.hourly[2].dateKey);
    expect(model.hourly[1].ariaLabel).toContain("31/08, 00:00");
    expect(model.hourly.map((slot) => slot.icon)).toEqual([
      expect.objectContaining({ night: true, type: "MostlyClearNight" }),
      expect.objectContaining({ night: true, type: "PartlyCloudyNight" }),
      expect.objectContaining({ night: true, type: "OvercastNight" }),
    ]);
  });

  it("keeps both autumn 02:00 hours as separate instants in order", () => {
    const times = [
      "2026-10-25T01:00+02:00",
      "2026-10-25T02:00+02:00",
      "2026-10-25T02:00+01:00",
      "2026-10-25T03:00+01:00",
    ];
    const slots = times.map((time, index) => ({ time, temperature: 10 + index }));
    const model = buildModel([...slots].reverse(), { now: "2026-10-25T01:45+02:00" });

    expect(model.hourly.map((slot) => slot.timestamp)).toEqual(times);
    expect(model.hourly.map((slot) => slot.time)).toEqual(["01:00", "02:00", "02:00", "03:00"]);
    expect(model.hourly[1].timestamp).not.toBe(model.hourly[2].timestamp);
    expect(model.hourly.map((slot) => slot.temperature)).toEqual(["10°", "11°", "12°", "13°"]);
    expect(model.hourly.every((slot) => slot.dayLabel === "Oggi")).toBe(true);
  });

  it("filters the first autumn 02:00 while retaining the current second 02:00", () => {
    const slots = [
      { time: "2026-10-25T02:00+02:00", temperature: 10 },
      { time: "2026-10-25T02:00+01:00", temperature: 11 },
      { time: "2026-10-25T03:00+01:00", temperature: 12 },
    ];
    const model = buildModel(slots, { now: "2026-10-25T02:30+01:00" });

    expect(model.hourly.map((slot) => slot.timestamp)).toEqual(slots.slice(1).map((slot) => slot.time));
    expect(model.hourly.map((slot) => slot.time)).toEqual(["02:00", "03:00"]);
  });

  it("crosses the spring DST gap without inventing a 02:00 slot", () => {
    const times = ["2026-03-29T01:00+01:00", "2026-03-29T03:00+02:00", "2026-03-29T04:00+02:00"];
    const model = buildModel(times.map((time) => ({ time, temperature: 10 })), {
      now: "2026-03-29T01:30+01:00",
    });

    expect(model.hourly.map((slot) => slot.timestamp)).toEqual(times);
    expect(model.hourly.map((slot) => slot.time)).toEqual(["01:00", "03:00", "04:00"]);
    expect(model.hourly.every((slot) => slot.dayLabel === "Oggi")).toBe(true);
  });

  it("keeps the original six-slot 12-hour bulletin behavior unless opted into 48 hours", () => {
    const model = buildBulletinLocalViewModel(buildState({ hourly_forecast: buildSlots() }), { now: NOW });

    expect(model.hourly).toHaveLength(6);
    expect(model.evolutionLabel).toBe("Prossime 12 ore");
    expect(model.hourly.every((slot) => slot.timestamp === undefined)).toBe(true);
  });
});
