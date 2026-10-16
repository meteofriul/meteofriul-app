import { describe, expect, it } from "vitest";

import { getThemeClassFromWeather, getWeatherType } from "./weatherClassification";

describe("weatherClassification", () => {
  it.each([
    [{ weathercode: 0, condition: "Sereno" }, "Sun", "theme-sole"],
    [{ weathercode: 3, condition: "Coperto" }, "Overcast", "theme-nuvoloso"],
    [{ weathercode: 61, condition: "Pioggia" }, "Rain", "theme-pioggia"],
    [{ weathercode: 95, condition: "Temporale" }, "Storm", "theme-temporale"],
    [{ weathercode: 71, condition: "Neve" }, "Snow", "theme-neve"],
  ])("maps current weather code %o to a coherent icon and scene theme", (data, type, theme) => {
    expect(getWeatherType(data)).toBe(type);
    expect(getThemeClassFromWeather(data)).toBe(theme);
  });

  it("uses condition text when the provider does not send a weather code", () => {
    expect(getWeatherType({ condition: "Temporale con rovesci" })).toBe("Storm");
    expect(getWeatherType({ condition: "Temporali localmente forti" })).toBe("StrongStorm");
    expect(getWeatherType({ condition: "Temporale con grandine" })).toBe("StormHail");
    expect(getWeatherType({ condition: "Grandine" })).toBe("Hail");
    expect(getWeatherType({ condition: "Pioggia leggera" })).toBe("LightRain");
    expect(getWeatherType({ condition: "Piogge abbondanti" })).toBe("HeavyRain");
    expect(getWeatherType({ condition: "Nevischio" })).toBe("Sleet");
    expect(getWeatherType({ condition: "Foschia" })).toBe("Mist");
    expect(getWeatherType({ condition: "Sole, nebbia e nubi basse" })).toBe("LowCloudFog");
    expect(getThemeClassFromWeather({ condition: "Neve debole" })).toBe("theme-neve");
    expect(getThemeClassFromWeather({ condition: "Pioggia leggera" })).toBe("theme-pioggia");
  });

  it("trusts OSMER current condition abbreviations over model support codes", () => {
    expect(getWeatherType({ condition: "Poco nuv.", weathercode: 3, cloud_cover: 92 })).toBe("MostlySunny");
    expect(getThemeClassFromWeather({ condition: "Poco nuv.", weathercode: 3, cloud_cover: 92 })).toBe("theme-sole");
  });

  it("uses measured precipitation signals instead of falling back to cloudy", () => {
    expect(getThemeClassFromWeather({ precipitation: 0.8, condition: "" })).toBe("theme-pioggia");
    expect(getThemeClassFromWeather({ snowfall: 0.2, condition: "" })).toBe("theme-neve");
  });

  it("respects the provider day/night flag for clear and partly cloudy evening states", () => {
    expect(getWeatherType({ weathercode: 0, condition: "Sereno", is_day: 0 })).toBe("ClearNight");
    expect(getThemeClassFromWeather({ weathercode: 0, condition: "Sereno", is_day: 0 })).toBe("theme-notte");
    expect(getWeatherType({ weathercode: 1, condition: "Poco nuvoloso", is_day: 0 })).toBe("MostlyClearNight");
    expect(getWeatherType({ weathercode: 2, condition: "Parzialmente nuvoloso", is_day: 0 })).toBe("PartlyCloudyNight");
    expect(getWeatherType({ weathercode: 3, condition: "Coperto", is_day: 0 })).toBe("OvercastNight");
  });

  it("uses canonical WMO corrections for severe or mixed codes even with generic backend text", () => {
    expect(getWeatherType({ weathercode: 65, condition: "Pioggia" })).toBe("HeavyRain");
    expect(getWeatherType({ weathercode: 56, condition: "Coperto" })).toBe("Sleet");
    expect(getWeatherType({ weathercode: 57, condition: "Coperto" })).toBe("Sleet");
    expect(getWeatherType({ weathercode: 66, condition: "Coperto" })).toBe("Sleet");
    expect(getWeatherType({ weathercode: 67, condition: "Coperto" })).toBe("Sleet");
    expect(getWeatherType({ weathercode: 96, condition: "Temporale" })).toBe("StormHail");
    expect(getWeatherType({ weathercode: 99, condition: "Temporale" })).toBe("StormHail");
  });

  it("keeps the scene inside the five weather bases even when wind is severe", () => {
    expect(getWeatherType({ weathercode: 0, wind_speed: 74 })).toBe("Wind");
    expect(getThemeClassFromWeather({ weathercode: 0, wind_speed: 74 })).toBe("theme-nuvoloso");
  });
});
