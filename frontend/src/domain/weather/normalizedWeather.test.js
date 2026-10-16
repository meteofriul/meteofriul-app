import { describe, expect, it } from "vitest";

import {
  getLocalizedWeatherCondition,
  getWeatherIconProps,
  normalizeWeatherData,
  readPopPercent,
  readPrecipitationAmount,
} from "./normalizedWeather";

describe("normalizedWeather", () => {
  it("preserves missing ICON precipitation channels and solar state without changing legacy defaults", () => {
    const pilot = normalizeWeatherData({
      primary_source: "icon2i_local_pilot", is_day: null,
      condition: "Sereno",
      precipitation: null, rain: null, showers: null, snowfall: null,
      snow_water_equivalent_mm: 2.3,
      hourly_forecast: [{ time: "2026-09-03T12:00Z", temperature: 21, is_day: null }],
    });
    expect(pilot).toMatchObject({
      precipitation: null, precipitationAmount: null, rain: null,
      showers: null, snowfall: null, isNight: false, isDay: false,
      feelsLike: null, popPercent: null, visibilityMeters: null,
    });
    expect(pilot.hourlyForecast[0]).toMatchObject({
      primary_source: "icon2i_local_pilot", precipitation: null,
      rain: null, showers: null, snowfall: null, isNight: false,
    });
    expect(pilot.type).not.toBe("ClearNight");
    expect(normalizeWeatherData({}).precipitationAmount).toBe(0);
    expect(normalizeWeatherData({ hourly_forecast: [{}] }).hourlyForecast[0].rain).toBe(0);
  });

  it("keeps a valid ICON zero and uses total water-equivalent precipitation only", () => {
    expect(readPrecipitationAmount({ primary_source: "icon2i_local_pilot", precipitation: 0 })).toBe(0);
    expect(readPrecipitationAmount({ primary_source: "icon2i_local_pilot", precipitation: 1, rain: 2, snowfall: 7 })).toBe(1);
  });

  it("does not reinterpret ICON WW 96 as Open-Meteo hail and localizes its semantic condition", () => {
    const weather = normalizeWeatherData({
      primary_source: "icon2i_local_pilot", weathercode: 96, condition: "Temporale forte",
      data_quality: {
        native_weather_code: 96,
        native_condition_status: "valid",
        native_condition_label: "Temporale con grandine o temporale forte",
        native_semantic_key: "strong_storm",
      },
    });
    expect(weather.weathercode).toBeNull();
    expect(getWeatherIconProps(weather)).toMatchObject({ type: "StrongStorm", semanticKey: "strong_storm" });
    expect(getLocalizedWeatherCondition(weather, { conditionStrongStorm: "Temporale forte" })).toBe("Temporale forte");
    expect(getLocalizedWeatherCondition(weather, { conditionStrongStorm: "Temporâl fuart" })).toBe("Temporâl fuart");
    expect(getLocalizedWeatherCondition({
      primary_source: "icon2i_local_pilot", condition: "",
      data_quality: { native_condition_status: "unknown" },
    }, { conditionOvercast: "Cuviert", conditionUnavailable: "Condizion no disponibile" }))
      .toBe("Condizion no disponibile");
  });

  it("does not invent apparent temperature when Open-Meteo omits it", () => {
    expect(normalizeWeatherData({ temperature: 24, feels_like: null }).feelsLike).toBeNull();
    expect(normalizeWeatherData({ temperature: 24, apparent_temperature: 0 }).feelsLike).toBe(0);
    expect(normalizeWeatherData({ current: { temperature_2m: 24, apparent_temperature: 26 } }).feelsLike).toBe(26);
  });

  it("normalizes the current backend weather payload into one shared model", () => {
    const weather = normalizeWeatherData({
      condition: "Sereno",
      weathercode: 1,
      is_day: 0,
      temperature: 23.4,
      feels_like: 25.1,
      wind_speed: 3,
      wind_gusts: 8,
      visibility: 38460,
      cloud_cover: 18,
      pop: "33%",
      precipitation: 0,
      rain: 0,
      showers: 0,
      snowfall: 0,
      hourly_next_12h: [{ weathercode: 61, precipitation: 0.4 }],
    });

    expect(weather.type).toBe("ClearNight");
    expect(weather.isNight).toBe(true);
    expect(weather.temperature).toBe(23.4);
    expect(weather.feelsLike).toBe(25.1);
    expect(weather.windSpeed).toBe(3);
    expect(weather.windGusts).toBe(8);
    expect(weather.visibilityKm).toBeCloseTo(38.46);
    expect(weather.cloudCover).toBe(18);
    expect(weather.popPercent).toBe(33);
    expect(weather.precipitationAmount).toBe(0);
    expect(weather.hourlyNext12h[0].code).toBe(61);
  });

  it("keeps the longer hourly reservoir separate from the public 12-hour window", () => {
    const weather = normalizeWeatherData({
      hourly_next_12h: [{ time: "2026-08-18T20:00+02:00", temperature: 24 }],
      hourly_forecast: [
        { time: "2026-08-18T20:00+02:00", temperature: 24 },
        { time: "2026-08-19T09:00+02:00", temperature: 22 },
      ],
    });

    expect(weather.hourlyNext12h).toHaveLength(1);
    expect(weather.hourlyForecast).toHaveLength(2);
    expect(weather.hourlyForecast[1].temperature).toBe(22);
  });

  it("keeps precipitation amount and probability separate", () => {
    expect(readPrecipitationAmount({ precipitation: 0.1, rain: 1.6, showers: 0.4 })).toBe(1.6);
    expect(readPopPercent({ pop: "70%" })).toBe(70);
    expect(readPopPercent({ pop: 45 })).toBe(45);
  });

  it("uses localized labels from the normalized weather type", () => {
    const weather = normalizeWeatherData({ condition: "Sereno", weathercode: 0, is_day: 0 });

    expect(getLocalizedWeatherCondition(weather, { conditionClearNight: "Sereno" })).toBe("Sereno");
  });

  it.each([
    ["Pioggia abbondante", "heavy_rain", "Pioggia abbondante"],
    ["Pioggia intensa", "intense_rain", "Pioggia intensa"],
    ["Pioggia molto intensa", "extreme_rain", "Pioggia molto intensa"],
  ])("uses the distinct localized rain label for %s", (condition, semanticKey, expected) => {
    const weather = normalizeWeatherData({ condition });

    expect(getLocalizedWeatherCondition(weather, {
      conditionRain: "Pioggia",
      conditionHeavyRain: "Pioggia abbondante",
      conditionIntenseRain: "Pioggia intensa",
      conditionExtremeRain: "Pioggia molto intensa",
    })).toBe(expected);
    expect(getWeatherIconProps(weather)).toMatchObject({ semanticKey });
  });

  it("keeps wind out of primary weather icons without hiding the underlying sky", () => {
    const windyClear = normalizeWeatherData({ condition: "Sereno", weathercode: 0, wind_speed: 74 });

    expect(windyClear.semantic).toMatchObject({
      key: "clear",
      overlays: {
        wind: {
          key: "wind_overlay",
          intensity: "strong",
        },
      },
    });
    expect(getLocalizedWeatherCondition(windyClear, {
      conditionSun: "Soleggiato",
      conditionWind: "Vento",
    })).toBe("Soleggiato");
    expect(getWeatherIconProps(windyClear)).toMatchObject({
      type: "Sun",
      code: 0,
      night: false,
      semanticKey: "clear",
      overlays: {
        wind: {
          key: "wind_overlay",
          intensity: "strong",
        },
      },
    });

    expect(getWeatherIconProps({ condition: "Sereno", weathercode: 0, is_day: 0, wind_speed: 74 })).toMatchObject({
      type: "ClearNight",
      code: 0,
      night: true,
    });

    expect(getWeatherIconProps({ condition: "Bora forte", is_bora: true })).toMatchObject({
      type: "Overcast",
      night: false,
    });

    expect(getWeatherIconProps({ condition: "Vento forte e pioggia", is_bora: true })).toMatchObject({
      type: "Rain",
      night: false,
    });
  });
});
