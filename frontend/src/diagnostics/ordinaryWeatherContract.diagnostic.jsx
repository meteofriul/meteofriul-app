import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WeatherCamsCard } from "../features/weather/WeatherCamsCard";
import { buildWeatherForecastViewModel } from "../features/weather/weatherForecastViewModel";

const LOCATION = {
  city: "Pordenone",
  municipality: { istatCode: "093033", name: "Pordenone" },
};

function buildOrdinaryWeatherState(pollenData) {
  return {
    city: "Pordenone",
    current: {},
    error: null,
    forecast: {
      city: "Pordenone",
      forecast: [],
      source: { label: "Open-Meteo" },
    },
    isStale: false,
    rawCurrent: {
      city: "Pordenone",
      data_quality: { certainty: "model", status: "fresh" },
      hourly_forecast: [],
      pollen_data: pollenData,
      primary_source: "open_meteo",
      source: { active: "open_meteo" },
    },
    status: "fresh",
  };
}

function buildModel(pollenData) {
  return buildWeatherForecastViewModel(buildOrdinaryWeatherState(pollenData), {
    language: "it",
    location: LOCATION,
    now: "2026-09-12T10:00:00+02:00",
  });
}

describe("ordinary-weather pollen contracts at revision 3f517a8", () => {
  it("preserves concentrations, units, valid time and declared provider through the view models", () => {
    const model = buildModel({
      level: "Medi",
      provider: "open_meteo_air_quality",
      unit: "grani/m³",
      valid_at: "2026-09-12T08:00:00Z",
      values: { ambrosia: 0.6, artemisia: 45.1, graminacee: 29.5 },
    });

    expect.soft(model.cams.values).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: "artemisia", value: 45.1 }),
      expect.objectContaining({ id: "graminacee", value: 29.5 }),
    ]));
    expect.soft(model.cams).toMatchObject({
      provider: "open_meteo_air_quality",
      units: "grani/m³",
      validAt: "2026-09-12T08:00:00Z",
    });
  });

  it("does not claim CAMS or Copernicus when the ordinary payload has no pollen provenance", () => {
    const model = buildModel({
      level: "Medi",
      values: { artemisia: 45.1, graminacee: 29.5 },
    });
    const markup = renderToStaticMarkup(
      <WeatherCamsCard language="it" model={model.cams} />,
    );

    expect(markup).not.toMatch(/CAMS|Copernicus/i);
  });
});
