import { describe, expect, it } from "vitest";

import {
  buildHomeWeatherVariantPreviewModel,
  getHomeWeatherVariantPreviewOptions,
} from "./homeVariantPreview";

const PREVIEW_NOW = new Date("2026-08-12T12:00:00+02:00");

function getDetailValue(model, detailId) {
  return model.weather.details.find((detail) => detail.id === detailId)?.value;
}

describe("home weather variant preview", () => {
  it("exposes the lab variant options without changing their stable ids", () => {
    expect(getHomeWeatherVariantPreviewOptions("it").map((option) => option.id)).toEqual([
      "clear",
      "partly",
      "cloud",
      "rain",
      "storm",
      "snow",
      "fog",
      "night",
      "cloud-night",
      "rain-night",
      "storm-night",
      "snow-night",
    ]);
  });

  it("builds a coherent rain preview model for the Home hero", () => {
    const model = buildHomeWeatherVariantPreviewModel("it", "rain");

    expect(model.weather.weatherVariant).toBe("rain");
    expect(model.weather.scenePhaseOverride).toBe("midday");
    expect(model.weather.conditionLabel).toBe("Pioggia");
    expect(model.weather.icon).toMatchObject({
      night: false,
      semanticFamily: "rain",
      semanticKey: "rain",
      type: "Rain",
    });
    expect(model.weather.temperature.value).toBe("16");
    expect(model.weather.feelsLike.value).toMatch(/^16/);
    expect(getDetailValue(model, "precipitation")).toBe("6 mm");
    expect(getDetailValue(model, "humidity")).toBe("88%");
  });

  it("keeps the night preview explicit and transversal", () => {
    const model = buildHomeWeatherVariantPreviewModel("it", "night");

    expect(model.weather.weatherVariant).toBe("night");
    expect(model.weather.scenePhaseOverride).toBe("night");
    expect(model.weather.icon).toMatchObject({
      night: true,
      semanticFamily: "clear",
      semanticKey: "night",
      type: "ClearNight",
    });
  });

  it("builds a dedicated snow night preview model", () => {
    const model = buildHomeWeatherVariantPreviewModel("it", "snow-night");

    expect(model.weather.weatherVariant).toBe("snow-night");
    expect(model.weather.conditionLabel).toBe("Neve");
    expect(model.weather.icon).toMatchObject({
      night: true,
      semanticFamily: "snow",
      semanticKey: "snow-night",
      type: "Snow",
    });
    expect(model.weather.temperature.value).toBe("-1");
    expect(model.weather.feelsLike.value).toMatch(/^-4/);
    expect(getDetailValue(model, "precipitation")).toBe("5 mm");
  });

  it("keeps daytime snow temperature and perceived temperature coherent", () => {
    const model = buildHomeWeatherVariantPreviewModel("it", "snow");

    expect(model.weather.temperature.value).toBe("1");
    expect(model.weather.feelsLike.value).toMatch(/^-1/);
  });

  it("restores the moon phase and event image in the Lab preview", () => {
    const model = buildHomeWeatherVariantPreviewModel("it", "clear", { now: PREVIEW_NOW });

    expect(model.almanac.moon).toEqual({
      cycleProgress: 97,
      phase: "Luna nuova",
    });
    expect(model.almanac.dateLabel).toBe("Mercoledì 12 agosto");
    expect(model.bulletin.dateLabel).toBe("Mercoledì 12 agosto");
    expect(model.almanac.body).not.toContain("Ireneo");
    expect(model.events.items[0].image).toBe("/municipalities/photos/030129-photo.webp");
  });

  it("localizes the current Lab date and moon phase in Furlan", () => {
    const model = buildHomeWeatherVariantPreviewModel("fur", "clear", { now: PREVIEW_NOW });

    expect(model.almanac.dateLabel).toBe("Miercus 12 Avost");
    expect(model.bulletin.dateLabel).toBe("Miercus 12 Avost");
    expect(model.almanac.moon.phase).toBe("Lune gnove");
  });
});
