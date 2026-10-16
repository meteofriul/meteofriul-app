import { describe, expect, it } from "vitest";

import {
  classifyConditionText,
  classifyCurrentWeather,
  classifyOsmerSymbol,
  classifyWeatherCode,
  getWeatherPresentation,
  getWindOverlay,
} from "./weatherSemantics";

describe("weatherSemantics", () => {
  it.each([
    [0, "clear", "Sun", "ClearNight"],
    [1, "mostly_sunny", "MostlySunny", "MostlyClearNight"],
    [2, "partly_cloudy", "PartlyCloudy", "PartlyCloudyNight"],
    [3, "overcast", "Overcast", "OvercastNight"],
    [45, "fog", "Fog", "Fog"],
    [48, "fog", "Fog", "Fog"],
    [51, "drizzle", "LightRain", "LightRain"],
    [53, "drizzle", "LightRain", "LightRain"],
    [55, "drizzle", "LightRain", "LightRain"],
    [56, "freezing_drizzle", "Sleet", "Sleet"],
    [57, "freezing_drizzle", "Sleet", "Sleet"],
    [61, "rain", "Rain", "Rain"],
    [63, "rain", "Rain", "Rain"],
    [65, "heavy_rain", "HeavyRain", "HeavyRain"],
    [66, "freezing_rain", "Sleet", "Sleet"],
    [67, "freezing_rain", "Sleet", "Sleet"],
    [71, "snow", "Snow", "Snow"],
    [73, "snow", "Snow", "Snow"],
    [75, "snow", "Snow", "Snow"],
    [77, "snow_grains", "Snow", "Snow"],
    [80, "showers", "Showers", "Showers"],
    [81, "showers", "Showers", "Showers"],
    [82, "showers", "Showers", "Showers"],
    [85, "snow_showers", "Snow", "Snow"],
    [86, "snow_showers", "Snow", "Snow"],
    [95, "storm", "Storm", "Storm"],
    [96, "storm_hail", "StormHail", "StormHail"],
    [99, "storm_hail", "StormHail", "StormHail"],
  ])("maps WMO/Open-Meteo code %s to canonical weather", (code, key, dayIcon, nightIcon) => {
    expect(classifyWeatherCode(code)).toMatchObject({
      key,
      meteoconType: dayIcon,
    });

    expect(classifyWeatherCode(code, { night: true })).toMatchObject({
      key,
      meteoconType: nightIcon,
      dayNightMode: "night",
    });
  });

  it("classifies condition text with specific phenomena before generic words", () => {
    expect(classifyConditionText("Temporale con grandine")).toMatchObject({
      key: "storm_hail",
      meteoconType: "StormHail",
    });
    expect(classifyConditionText("Grandine")).toMatchObject({ key: "hail" });
    expect(classifyConditionText("Temporali localmente forti")).toMatchObject({
      key: "strong_storm",
      meteoconType: "StrongStorm",
    });
    expect(classifyConditionText("Pioggia abbondante")).toMatchObject({
      key: "heavy_rain",
      meteoconType: "HeavyRain",
    });
    expect(classifyConditionText("Pioggia leggera")).toMatchObject({
      key: "drizzle",
      meteoconType: "LightRain",
    });
    expect(classifyConditionText("Sole, nebbia e nubi basse")).toMatchObject({
      key: "low_cloud_fog",
      meteoconType: "LowCloudFog",
    });
  });

  it("keeps official OSMER current text ahead of model support code", () => {
    expect(classifyCurrentWeather({ condition: "Sereno", weathercode: 2, is_day: 1 })).toMatchObject({
      key: "clear",
      meteoconType: "Sun",
      source: "current_condition",
    });

    expect(classifyCurrentWeather({ condition: "Poco nuv.", weathercode: 3, is_day: 0 })).toMatchObject({
      key: "mostly_sunny",
      meteoconType: "MostlyClearNight",
      dayNightMode: "night",
    });
  });

  it("uses measured precipitation only when no condition text is available", () => {
    expect(classifyCurrentWeather({ condition: "", precipitation: 0.8, weathercode: 3 })).toMatchObject({
      key: "rain",
      source: "current_metrics",
    });

    expect(classifyCurrentWeather({ condition: "Sereno", precipitation: 0.8, weathercode: 61 })).toMatchObject({
      key: "clear",
      source: "current_condition",
    });
  });

  it("keeps wind as overlay instead of primary weather", () => {
    expect(classifyCurrentWeather({ condition: "Sereno", weathercode: 0, wind_speed: 74 })).toMatchObject({
      key: "clear",
      meteoconType: "Sun",
      overlays: {
        wind: {
          key: "wind_overlay",
          intensity: "strong",
        },
      },
    });

    expect(classifyCurrentWeather({ condition: "Vento forte e pioggia", is_bora: true })).toMatchObject({
      key: "rain",
      meteoconType: "Rain",
      overlays: {
        wind: {
          intensity: "strong",
          isBora: true,
        },
      },
    });

    expect(classifyCurrentWeather({ condition: "Bora forte", is_bora: true })).toMatchObject({
      key: "overcast",
      overlays: {
        wind: {
          intensity: "strong",
          isBora: true,
        },
      },
    });
  });

  it.each([
    ["cielo", "sun", "clear", "Sun"],
    ["cielo", "mostly_sunny", "mostly_sunny", "MostlySunny"],
    ["cielo", "variable", "variable", "PartlyCloudy"],
    ["cielo", "cloudy", "cloudy", "Cloud"],
    ["cielo", "overcast", "overcast", "Overcast"],
    ["cielo", "sun_fog", "low_cloud_fog", "LowCloudFog"],
    ["pioggia", "light_rain", "drizzle", "LightRain"],
    ["pioggia", "moderate_rain", "rain", "Rain"],
    ["pioggia", "heavy_rain", "heavy_rain", "HeavyRain"],
    ["pioggia", "intense_rain", "intense_rain", "ExtremeRain"],
    ["pioggia", "extreme_rain", "extreme_rain", "ExtremeRain"],
    ["neve", "moderate_snow", "snow", "Snow"],
    ["neve", "heavy_snow", "snow", "Snow"],
    ["neve", "intense_snow", "snow", "Snow"],
    ["temporale", "storm", "storm", "Storm"],
    ["nebbia", "fog", "fog", "Fog"],
    ["nebbia", "mist", "mist", "Mist"],
  ])("maps OSMER %s.%s to canonical semantic", (kind, id, key, icon) => {
    expect(classifyOsmerSymbol(kind, id).semantic).toMatchObject({
      key,
      meteoconType: icon,
    });
  });

  it("maps OSMER wind symbols only to overlays", () => {
    expect(classifyOsmerSymbol("vento", "north_east_moderate")).toMatchObject({
      semantic: null,
      overlay: {
        key: "wind_overlay",
        id: "north_east_moderate",
        intensity: "moderate",
      },
    });

    expect(classifyOsmerSymbol("vento", "east_north_east_very_strong")).toMatchObject({
      semantic: null,
      overlay: {
        intensity: "very_strong",
      },
    });
  });

  it.each([
    ["sun", "clear"],
    ["variable", "variable"],
    ["overcast", "overcast"],
    ["variable_moderate_rain", "rain"],
    ["variable_heavy_rain", "heavy_rain"],
    ["variable_heavy_rain_storm", "storm"],
    ["variable_storm", "storm"],
    ["variable_moderate_rain_snow", "sleet"],
    ["variable_snow", "snow"],
    ["overcast_moderate_rain", "rain"],
    ["overcast_heavy_rain", "heavy_rain"],
    ["overcast_intense_rain", "intense_rain"],
    ["overcast_heavy_rain_storm", "storm"],
    ["overcast_storm", "storm"],
    ["overcast_heavy_rain_snow", "sleet"],
    ["overcast_snow", "snow"],
  ])("maps OSMER evolution %s", (id, key) => {
    expect(classifyOsmerSymbol("evoluzione", id).semantic).toMatchObject({ key });
  });

  it("returns presentation-only day/night details without changing the semantic key", () => {
    expect(getWeatherPresentation("clear", { night: true })).toMatchObject({
      key: "clear",
      labelKey: "conditionClearNight",
      meteoconType: "ClearNight",
      sceneVariant: "night",
      themeClass: "theme-notte",
    });

    expect(getWeatherPresentation("rain", { night: true })).toMatchObject({
      key: "rain",
      labelKey: "conditionRain",
      meteoconType: "Rain",
      sceneVariant: "rain",
      themeClass: "theme-pioggia",
    });
  });

  it.each([
    ["heavy_rain", "conditionHeavyRain", undefined],
    ["intense_rain", "conditionIntenseRain", "conditionHeavyRain"],
    ["extreme_rain", "conditionExtremeRain", "conditionIntenseRain"],
  ])("keeps rain intensity label keys distinct for %s", (key, labelKey, fallbackLabelKey) => {
    expect(getWeatherPresentation(key)).toMatchObject({
      key,
      labelKey,
      ...(fallbackLabelKey ? { fallbackLabelKey } : {}),
    });
  });

  it("normalizes current wind measurements into secondary overlays", () => {
    expect(getWindOverlay({ wind_speed: 42, wind_gusts: 20 })).toMatchObject({
      key: "wind_overlay",
      intensity: "moderate",
    });
    expect(getWindOverlay({ wind_speed: 10, wind_gusts: 90 })).toMatchObject({
      key: "wind_overlay",
      intensity: "strong",
    });
    expect(getWindOverlay({ wind_speed: 4, wind_gusts: 8 })).toBeNull();
  });
});
