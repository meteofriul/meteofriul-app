import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HomeWeatherHero } from "./HomeWeatherHero";

function buildWeather(overrides = {}) {
  return {
    alertSummary: null,
    conditionLabel: "Soleggiato",
    feelsLike: { label: "Percepita", value: "25°C" },
    icon: { condition: "Soleggiato", type: "Sun" },
    showStatus: false,
    temperature: { severity: "mild", unit: "°C", value: "24" },
    updatedLabel: "Aggiornato ora",
    weatherVariant: "clear",
    ...overrides,
  };
}

describe("HomeWeatherHero", () => {
  it("keeps fresh weather compact without metrics or update text", () => {
    const markup = renderToStaticMarkup(
      <HomeWeatherHero
        locationTitle="Pordenone"
        sceneNow={new Date("2026-08-12T10:00:00.000Z")}
        weather={buildWeather()}
      />,
    );

    expect(markup).toContain("Soleggiato");
    expect(markup).toContain("Percepita");
    expect(markup).not.toContain("mf-home-hero-metrics");
    expect(markup).not.toContain("Dati meteo principali");
    expect(markup).not.toContain("Aggiornato ora");
    expect(markup).not.toContain("mf-home-hero__insights");
    expect(markup).toContain("mf-home-meteocon-icon");
    expect(markup.match(/mf-home-meteocon-icon/g)).toHaveLength(1);
    expect(markup).toContain('data-scene-environment="plain"');
    expect(markup).toContain('data-day-phase="midday"');
    expect(markup).not.toContain("data-orb");
    expect(markup).toContain("mf-home-eagle");
    expect(markup).toContain("home-eagle-kling-3.png");
    expect(markup).toContain("home-eagle-still.webp");
    expect(markup).toContain('data-atmosphere-active="false"');
  });

  it("adapts the landscape to the selected locality", () => {
    const markup = renderToStaticMarkup(
      <HomeWeatherHero locationTitle="Trieste" weather={buildWeather()} />,
    );

    expect(markup).toContain('data-scene-environment="coast"');
  });

  it("keeps a long automatic location name in the responsive heading", () => {
    const markup = renderToStaticMarkup(
      <HomeWeatherHero
        changeLocationLabel="Cambia"
        locationTitle="San Giovanni in Persiceto"
        onChangeLocation={() => {}}
        weather={buildWeather()}
      />,
    );

    expect(markup).toContain('class="mf-home-location__name"');
    expect(markup).toContain("San Giovanni in Persiceto");
  });

  it("uses a neutral phase-aware weather card without scenery outside FVG", () => {
    const markup = renderToStaticMarkup(
      <HomeWeatherHero
        locationTitle="Bologna"
        sceneMode="neutral"
        sceneNow={new Date("2026-08-12T10:00:00.000Z")}
        weather={buildWeather()}
      />,
    );

    expect(markup).toContain('data-scene-mode="neutral"');
    expect(markup).toContain('data-scene-environment="neutral"');
    expect(markup).toContain('data-day-phase="midday"');
    expect(markup).toContain("mf-home-meteocon-icon");
    expect(markup).not.toContain("mf-home-flight-scene__landscape");
    expect(markup).not.toContain("mf-home-flight-scene__cloud");
    expect(markup).not.toContain("mf-home-eagle");
  });

  it("uses local sunrise and sunset to select the precise scene phase", () => {
    const solarContext = {
      latitude: 45.9567,
      longitude: 12.6605,
      sunrise: "2026-08-12T06:02",
      sunset: "2026-08-12T20:21",
      timeZone: "Europe/Rome",
    };
    const dawnMarkup = renderToStaticMarkup(
      <HomeWeatherHero
        locationTitle="Pordenone"
        sceneNow={new Date("2026-08-12T04:15:00.000Z")}
        weather={buildWeather({ solarContext })}
      />,
    );
    const afternoonMarkup = renderToStaticMarkup(
      <HomeWeatherHero
        locationTitle="Pordenone"
        sceneNow={new Date("2026-08-12T15:00:00.000Z")}
        weather={buildWeather({
          icon: { condition: "Sereno", night: true, type: "ClearNight" },
          solarContext,
          weatherVariant: "clear-night",
        })}
      />,
    );
    const nightMarkup = renderToStaticMarkup(
      <HomeWeatherHero
        locationTitle="Pordenone"
        sceneNow={new Date("2026-08-12T19:30:00.000Z")}
        weather={buildWeather({ solarContext, weatherVariant: "clear-night" })}
      />,
    );

    expect(dawnMarkup).toContain('data-day-phase="dawn"');
    expect(dawnMarkup).toContain("mf-home-flight-scene--phase-dawn");
    expect(afternoonMarkup).toContain('data-day-phase="afternoon"');
    expect(afternoonMarkup).toContain("mf-home-flight-scene--phase-afternoon");
    expect(afternoonMarkup).toContain("clear-day");
    expect(nightMarkup).toContain('data-day-phase="night"');
    expect(nightMarkup).toContain("mf-home-flight-scene--phase-night");
    expect(nightMarkup).toContain("mf-home-flight-scene--clear");
    expect(nightMarkup).not.toContain("mf-home-flight-scene--clear-night");
  });

  it("keeps an explicit Lab phase deterministic regardless of the real clock", () => {
    const markup = renderToStaticMarkup(
      <HomeWeatherHero
        locationTitle="Udine"
        sceneNow={new Date("2026-08-12T10:00:00.000Z")}
        weather={buildWeather({
          icon: { condition: "Sereno", night: true, type: "ClearNight" },
          scenePhaseOverride: "night",
          weatherVariant: "night",
        })}
      />,
    );

    expect(markup).toContain('data-day-phase="night"');
    expect(markup).toContain("mf-home-flight-scene--phase-night");
    expect(markup).toContain("clear-night");
  });

  it("shows update age only when the weather is stale", () => {
    const markup = renderToStaticMarkup(
      <HomeWeatherHero
        locationTitle="Pordenone"
        weather={buildWeather({ showStatus: true, updatedLabel: "Aggiornato 3 ore fa" })}
      />,
    );

    expect(markup).toContain("mf-home-hero__insights");
    expect(markup).toContain("mf-home-updated-text");
    expect(markup).toContain("lucide-clock-3");
    expect(markup).toContain("Aggiornato 3 ore fa");
  });

  it("shows rain only for current reliable weather", () => {
    const freshMarkup = renderToStaticMarkup(
      <HomeWeatherHero
        locationTitle="Pordenone"
        weather={buildWeather({
          icon: { condition: "Pioggia", type: "Rain" },
          weatherVariant: "rain",
        })}
      />,
    );
    const staleMarkup = renderToStaticMarkup(
      <HomeWeatherHero
        locationTitle="Pordenone"
        weather={buildWeather({
          icon: { condition: "Pioggia", type: "Rain" },
          isStale: true,
          weatherVariant: "rain",
        })}
      />,
    );

    expect(freshMarkup).toContain("mf-home-atmosphere--rain");
    expect(freshMarkup).toContain('data-atmosphere-active="true"');
    expect(staleMarkup).not.toContain("mf-home-atmosphere--rain");
    expect(staleMarkup).toContain('data-atmosphere-active="false"');
  });
});
