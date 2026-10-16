import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { normalizeWeatherData } from "../../domain/weather/normalizedWeather";
import { buildBulletinLocalViewModel } from "../bulletin/bulletinLocalViewModel";
import { buildHomeViewModel } from "../home/homeViewModel";
import { PilotHourlyForecast } from "./WeatherHourlyForecast";
import { WeatherForecastCharts } from "./WeatherForecastCharts";
import { buildWeatherForecastViewModel } from "./weatherForecastViewModel";

const HOUR = 3600000;
const NOW = "2026-09-08T10:15:00Z";
const FIRST_FUTURE_HOUR = "2026-09-08T11:00:00Z";
const LOCATION = { city: "Pordenone", municipality: { istatCode: "093033", name: "Pordenone" } };

// The same canonical slot shape used by weatherForecastViewModel.test.js,
// with a separate current hero and a variable, strictly future timeline.
function stateFor(count, { start = FIRST_FUTURE_HOUR, now = NOW } = {}) {
  const slots = Array.from({ length: count }, (_, index) => {
    const timestamp = Date.parse(start) + index * HOUR;
    return {
      time: new Date(timestamp).toISOString(),
      interval_start: new Date(timestamp - HOUR).toISOString(),
      interval_end: new Date(timestamp).toISOString(),
      primary_source: "icon2i_local_pilot",
      condition: "Sereno",
      temperature: 22 + index / 10,
      feels_like: 21 + index / 10,
      humidity: 55,
      pressure: 1012,
      precipitation: index % 3 ? 0 : 0.2,
      precipitation_probability: null,
      wind_speed: 8,
      wind_direction: 45,
      wind_gusts: 15,
      cloud_cover: 20,
      is_day: 1,
    };
  });
  const rawCurrent = {
    city: LOCATION.city,
    primary_source: "icon2i_local_pilot",
    temperature: 20,
    feels_like: 19,
    condition: "Sereno",
    is_day: 1,
    hourly_forecast: slots,
    hourly_next_12h: slots.slice(0, 12),
    data_quality: {
      run_utc: new Date(Date.parse(now) - 40 * HOUR).toISOString(),
      valid_at_utc: new Date(Math.floor(Date.parse(now) / HOUR) * HOUR).toISOString(),
      status: "stale",
      cams_status: "unavailable",
      catalog_sha256: "a".repeat(64),
      municipality_istat: "093033",
    },
  };
  return {
    city: LOCATION.city,
    current: normalizeWeatherData(rawCurrent),
    rawCurrent,
    forecast: {
      city: LOCATION.city,
      forecast: [
        { date: "2026-09-08", min_temp: 18, max_temp: 33, partial_day: false },
        { date: "2026-09-09", min_temp: 19, max_temp: 31, partial_day: false },
        { date: "2026-09-10", min_temp: 20, max_temp: 30, partial_day: false },
      ],
    },
    error: null,
    status: "stale",
  };
}

function expectTimeline(items, expected) {
  const timestamps = items.map(({ timestamp }) => timestamp);
  expect(timestamps).toEqual(expected);
  expect(new Set(timestamps).size).toBe(expected.length);
  timestamps.slice(1).forEach((timestamp, index) => {
    expect(Date.parse(timestamp) - Date.parse(timestamps[index])).toBe(HOUR);
  });
}

describe.each(["it", "fur"])("ICON variable future-window consumers (%s)", (language) => {
  it.each([12, 24, 36, 48])("preserves all %i real future hours through normalization, bulletin, forecast and Home", (count) => {
    const state = stateFor(count);
    const original = JSON.stringify(state);
    const expected = state.rawCurrent.hourly_forecast.map(({ time }) => time);
    const options = { language, location: LOCATION, now: NOW };
    const bulletin = buildBulletinLocalViewModel(state, { ...options, hourlyHours: 48 });
    const forecast = buildWeatherForecastViewModel(state, options);
    const home = buildHomeViewModel({
      location: LOCATION,
      weather: state,
      localWeather: bulletin,
      hourly: { items: bulletin.hourly, title: bulletin.evolutionLabel },
    }, options);

    expect(state.current.hourlyForecast).toHaveLength(count);
    expect(state.current.hourlyNext12h).toHaveLength(12);
    expectTimeline(bulletin.hourly, expected);
    expectTimeline(forecast.hourly.items, expected);
    expectTimeline(home.hourly.items, expected);
    expectTimeline(forecast.hourly.groups.flatMap(({ items }) => items), expected);
    expect(forecast.hourly.summaries.map(({ dateKey }) => dateKey)).toEqual(
      forecast.hourly.groups.map(({ dateKey }) => dateKey),
    );
    expect(forecast.hourly.items.every(({ values }) => Number.isFinite(values.temperature))).toBe(true);
    expect(forecast.hourly.retainedValuesLabel).toBe("");
    expect(forecast.hourly.title).toBe(bulletin.evolutionLabel);
    expect(home.hourly.title).toBe(bulletin.evolutionLabel);
    expect(forecast.hourly.title).toBe(count === 48
      ? (language === "fur" ? "Prossimis 48 oris" : "Prossime 48 ore")
      : (language === "fur" ? "Evoluzion orarie" : "Evoluzione oraria"));
    expect(home.weather.temperature.value).toBe("20");
    expect(forecast.hourly.items[0].values.temperature).toBe(22);
    expect(forecast.hourly.summaries[0]).toMatchObject({ fullDayMinTemperature: "18°", fullDayMaxTemperature: "33°" });
    expect(JSON.stringify(state)).toBe(original);
  });

  it.each([12, 24, 36, 48])("renders %i pilot hour cards and safe chart windows without a JSX change", (count) => {
    const state = stateFor(count);
    const { hourly } = buildWeatherForecastViewModel(state, { language, location: LOCATION, now: NOW });
    const markup = renderToStaticMarkup(createElement(PilotHourlyForecast, { model: hourly, language }));
    expect(markup.match(/aria-haspopup="dialog"/g)).toHaveLength(count);
    expect(markup.match(/data-day=/g)).toHaveLength(count);
    expect(markup).not.toMatch(/NaN|undefined|Infinity/);
    for (const item of [hourly.items[0], hourly.items.at(-1)]) {
      expect(markup).toContain(`dateTime="${item.timestamp}"`);
      const chart = renderToStaticMarkup(createElement(WeatherForecastCharts, {
        items: hourly.items, language, selectedKey: item.timestamp,
      }));
      expect(chart.match(/data-testid="forecast-chart-cursor"/g)).toHaveLength(3);
      expect(chart).not.toMatch(/NaN|undefined|Infinity/);
      expect(chart).toContain(item.time);
    }
  });
});

describe("variable ICON window boundaries", () => {
  it("excludes the elapsed 10:00 card at 10:15 without losing any of the 12 future hours", () => {
    const state = stateFor(13, { start: "2026-09-08T10:00:00Z" });
    const model = buildWeatherForecastViewModel(state, { location: LOCATION, now: NOW });
    const expected = state.rawCurrent.hourly_forecast.slice(1).map(({ time }) => time);
    expectTimeline(model.hourly.items, expected);
    expect(model.hourly.items.every(({ timestamp }) => Date.parse(timestamp) >= Date.parse(NOW))).toBe(true);
  });

  it("keeps a sample exactly at the current timestamp and leaves Legacy hour-floor filtering unchanged", () => {
    const exact = "2026-09-08T10:00:00Z";
    const state = stateFor(12, { start: exact, now: exact });
    const expected = state.rawCurrent.hourly_forecast.map(({ time }) => time);
    expectTimeline(buildWeatherForecastViewModel(state, { location: LOCATION, now: exact }).hourly.items, expected);

    state.rawCurrent.primary_source = "open_meteo";
    state.current = normalizeWeatherData(state.rawCurrent);
    const legacy = buildBulletinLocalViewModel(state, { location: LOCATION, now: NOW, hourlyHours: 48 });
    expectTimeline(legacy.hourly, expected);
  });

  it.each([
    ["spring DST", "2026-03-29T00:30:00Z", "2026-03-29T01:00:00Z"],
    ["autumn DST", "2026-10-24T23:30:00Z", "2026-10-25T00:00:00Z"],
  ])("keeps 12 consecutive UTC timestamps across %s", (_label, now, start) => {
    const state = stateFor(12, { start, now });
    const model = buildWeatherForecastViewModel(state, { location: LOCATION, now });
    expectTimeline(model.hourly.items, state.rawCurrent.hourly_forecast.map(({ time }) => time));
    expect(model.hourly.groups.flatMap(({ items }) => items)).toHaveLength(12);
  });

  it("shrinks a previously full window without resurrecting removed future cards", () => {
    const options = { location: LOCATION, now: NOW };
    const previousModel = buildWeatherForecastViewModel(stateFor(48), options);
    const smaller = stateFor(12);
    const next = buildWeatherForecastViewModel(smaller, { ...options, previousModel });
    expectTimeline(next.hourly.items, smaller.rawCurrent.hourly_forecast.map(({ time }) => time));
    expect(next.hourly.retainedValuesLabel).toBe("");
  });
});
