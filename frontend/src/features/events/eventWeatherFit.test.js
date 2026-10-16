import { describe, expect, it } from "vitest";

import {
  getEventWeatherFit,
  getEventWeatherSensitivity,
  getHomeWeatherFitScoreDelta,
  isLikelyIndoorEvent,
} from "./eventWeatherFit";

describe("eventWeatherFit", () => {
  it("keeps the fit neutral when weather is missing", () => {
    const fit = getEventWeatherFit({ title: "Mercato", category: "mercato" }, null);

    expect(fit).toMatchObject({
      level: "neutral",
      reasonCode: "no_weather",
      score: 50,
      sensitivity: "high",
    });
    expect(getHomeWeatherFitScoreDelta(fit)).toBe(0);
  });

  it("detects indoor cultural events as low sensitivity", () => {
    const event = { title: "Mostra fotografica", category: "cultura" };

    expect(isLikelyIndoorEvent(event)).toBe(true);
    expect(getEventWeatherSensitivity(event)).toBe("low");
  });

  it("favours protected cultural events during rain", () => {
    const fit = getEventWeatherFit(
      { title: "Mostra al museo", category: "cultura" },
      { condition: "Pioggia", precipitation: 2, weathercode: 61, temperature: 17 },
    );

    expect(fit).toMatchObject({
      level: "indoor",
      reasonCode: "protected_activity",
      score: 82,
      weatherGroup: "rain",
    });
    expect(getHomeWeatherFitScoreDelta(fit)).toBeGreaterThan(0);
  });

  it("penalizes outdoor high-sensitivity events during stormy weather", () => {
    const fit = getEventWeatherFit(
      { title: "Sagra in piazza", category: "sagra" },
      { condition: "Temporale con grandine", weathercode: 96, temperature: 19 },
    );

    expect(fit).toMatchObject({
      level: "risky",
      reasonCode: "severe_weather",
      score: 34,
      sensitivity: "high",
    });
    expect(getHomeWeatherFitScoreDelta(fit)).toBeLessThan(0);
  });

  it("uses wind overlays without turning the event page into a weather warning", () => {
    const fit = getEventWeatherFit(
      { title: "Mercato in centro", category: "mercato" },
      { condition: "Bora forte", is_bora: true, wind_speed: 74, temperature: 20 },
    );

    expect(fit).toMatchObject({
      level: "watch",
      reasonCode: "wind_exposure",
      weatherGroup: "wind",
    });
  });
});
