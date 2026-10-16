import { JSDOM } from "jsdom";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WeatherEnvironmentOverview } from "./WeatherEnvironmentOverview";
import { getUvVisualTone } from "./uvVisualTone";

const pollenValues = [
  ["ragweed", "Ambrosia", 0.004, "<0,01"],
  ["mugwort", "Artemisia", 21.96, "21,96"],
  ["birch", "Betulla", 0.003, "<0,01"],
  ["grass", "Graminacee", 1.3, "1,3"],
  ["olive", "Olivo", 0, "<0,01"],
  ["alder", "Ontano", 0.002, "<0,01"],
].map(([id, label, value, displayValue]) => ({ id, label, value, displayValue }));

const camsModel = {
  air: {
    valid_at: "2026-09-14T18:00:00Z",
    values: {
      "particulate_matter_2.5um": 7.9,
      "particulate_matter_10um": 12.5,
      nitrogen_dioxide: 13,
      ozone: 72.2,
    },
  },
  airSampleStatus: "current",
  heading: "Pollini",
  pollenSampleStatus: "current",
  status: "available",
  units: "grani/m³",
  validAt: "2026-09-14T18:00:00Z",
  values: pollenValues,
};

function renderOverview(model = camsModel, language = "it") {
  const html = renderToStaticMarkup(<WeatherEnvironmentOverview
    camsModel={model}
    language={language}
    location={{ city: "Pordenone", lat: 45.9567, lon: 12.6605 }}
    now={new Date("2026-09-14T18:30:00Z")}
    uvPoint={{ latitude: 45.9567, longitude: 12.6605 }}
  />);

  return new JSDOM(html).window.document;
}

describe("pilot environmental overview", () => {
  it.each([
    [0.6, "low"],
    [3, "moderate"],
    [6, "high"],
    [9, "very-high"],
    [12, "extreme"],
    [null, "unavailable"],
  ])("maps UV %s to the %s compact-card tone", (value, expected) => {
    expect(getUvVisualTone(value === null ? null : { current: { value } })).toBe(expected);
  });

  it("summarizes four independent cards without inventing air or pollen classes", () => {
    const document = renderOverview();
    const grid = document.querySelector(".mf-weather-environment-grid");
    const buttons = Array.from(grid.querySelectorAll(":scope > button"));

    expect(buttons).toHaveLength(4);
    expect(buttons.map((button) => button.querySelector(".mf-weather-environment-tile__header strong")?.textContent))
      .toEqual(["Sole e Luna", "Indice UV", "Qualità dell’aria", "Pollini"]);
    expect(buttons.every((button) => button.getAttribute("aria-haspopup") === "dialog")).toBe(true);
    expect(new Set(buttons.map((button) => button.getAttribute("aria-controls"))).size).toBe(1);
    expect(buttons.every((button) => button.getAttribute("aria-expanded") === "false")).toBe(true);

    const air = buttons[2].textContent;
    expect(air).toContain("PM2.5");
    expect(air).toContain("7,9µg/m³");
    expect(air).toContain("PM10: 12,5 µg/m³");
    expect(air).not.toContain("O₃ e NO₂ disponibili");
    expect(air).toContain("Dati Copernicus CAMS");
    expect(air).not.toContain("Valido 20:00");

    const pollen = buttons[3].textContent;
    expect(pollen).toContain("Artemisia");
    expect(pollen).toContain("21,96grani/m³");
    expect(pollen).toContain("6 specie · 2 attive");
    expect(pollen).not.toContain("specie monitorate");
    expect(pollen).not.toContain("con valore <0,01");
    expect(pollen).toContain("Previsione modellistica CAMS");

    expect(grid.textContent).not.toMatch(/\bAQI\b|\bottima\b|pollini:\s*bassi|soglia rilevabile/i);
    expect(grid.querySelector(".mf-weather-environment-tile__action")).toBeNull();
    expect(document.querySelector("dialog")).toBeNull();
  });

  it("treats a real zero PM2.5 as data and falls back to PM10 only when PM2.5 is missing", () => {
    const zero = renderOverview({
      ...camsModel,
      air: { ...camsModel.air, values: { ...camsModel.air.values, "particulate_matter_2.5um": 0 } },
    }).querySelector(".mf-weather-environment-tile--air").textContent;
    expect(zero).toContain("PM2.5");
    expect(zero).toContain("0µg/m³");

    const fallback = renderOverview({
      ...camsModel,
      air: { ...camsModel.air, values: { "particulate_matter_10um": 12.5 } },
    }).querySelector(".mf-weather-environment-tile--air").textContent;
    expect(fallback).toContain("PM10");
    expect(fallback).toContain("12,5µg/m³");
    expect(fallback).not.toContain("PM2.5");
  });

  it("does not select an arbitrary dominant pollen when all modeled values are zero", () => {
    const document = renderOverview({
      ...camsModel,
      values: pollenValues.map((entry) => ({ ...entry, displayValue: "0", value: 0 })),
    });
    const pollen = document.querySelector(".mf-weather-environment-tile--pollen").textContent;

    expect(pollen).toContain("Nessun valore sopra 0");
    expect(pollen).toContain("6 specie · 0 attive");
    expect(pollen).not.toContain("Artemisia:");
  });

  it("counts the objective display threshold as an active pollen value", () => {
    const document = renderOverview({
      ...camsModel,
      values: pollenValues.map((entry, index) => index === 0
        ? { ...entry, displayValue: "0,01", value: 0.01 }
        : entry),
    });

    expect(document.querySelector(".mf-weather-environment-tile--pollen").textContent)
      .toContain("6 specie · 3 attive");
  });

  it("marks retained CAMS families directly on both compact cards", () => {
    const document = renderOverview({
      ...camsModel,
      airSampleStatus: "last_known",
      pollenSampleStatus: "last_known",
    });

    expect(document.querySelector(".mf-weather-environment-tile--air").textContent).toContain("Ultimo dato CAMS");
    expect(document.querySelector(".mf-weather-environment-tile--pollen").textContent).toContain("Ultimo dato CAMS");
  });

  it("keeps air and pollen availability independent and never promotes a gas to particulate", () => {
    const airOnly = renderOverview({
      ...camsModel,
      note: "Pollini non disponibili",
      status: "unavailable",
      values: [],
    });
    expect(airOnly.querySelector(".mf-weather-environment-tile--air").textContent).toContain("PM2.5");
    expect(airOnly.querySelector(".mf-weather-environment-tile--pollen").textContent).toContain("Pollini non disponibili");
    expect(airOnly.querySelector(".mf-weather-environment-tile--pollen").textContent).not.toContain("0 specie monitorate");

    const pollenOnly = renderOverview({ ...camsModel, air: null });
    expect(pollenOnly.querySelector(".mf-weather-environment-tile--air").textContent).toContain("Dati dell’aria non disponibili");
    expect(pollenOnly.querySelector(".mf-weather-environment-tile--pollen").textContent).toContain("Artemisia");

    const gasOnly = renderOverview({
      ...camsModel,
      air: {
        ...camsModel.air,
        values: { nitrogen_dioxide: 13, ozone: 72.2 },
      },
    }).querySelector(".mf-weather-environment-tile--air").textContent;
    expect(gasOnly).toContain("PM2.5 e PM10 non disponibili");
    expect(gasOnly).not.toContain("O₃ e NO₂ disponibili");
    expect(gasOnly).toContain("Dati Copernicus CAMS");
    expect(gasOnly).not.toMatch(/Ozono|72,2/);
  });

  it("keeps the compact status and provenance localized in Furlan", () => {
    const document = renderOverview(camsModel, "fur");
    const air = document.querySelector(".mf-weather-environment-tile--air").textContent;
    const pollen = document.querySelector(".mf-weather-environment-tile--pollen").textContent;

    expect(air).toContain("Cualitât de arie");
    expect(air).toContain("Dâts Copernicus CAMS");
    expect(air).not.toContain("disponibii");
    expect(air).not.toContain("Valit 20:00");
    expect(pollen).toContain("Polins");
    expect(pollen).toContain("6 speciis · 2 ativis");
    expect(pollen).toContain("Prevision modelistiche CAMS");
  });
});
