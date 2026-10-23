// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({ cached: null, request: null, options: null }));
vi.mock("../features/home/homeDataController", async importOriginal => ({
  ...await importOriginal(),
  readInitialHomeData: () => ({ weather: state.cached }),
  hydrateHomeWeatherFromBackgroundPrefetch: async () => null,
  loadHomeWeather: (_location, options) => { state.options = options; return state.request; },
}));
vi.mock("../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: () => true,
  isLocalWeatherPilot: () => true,
}));
vi.mock("../features/weather/WeatherSkyCard", () => ({ WeatherSkyCard: () => null }));
vi.mock("../features/weather/WeatherUvCard", () => ({ UvCurve: () => null, WeatherUvCard: () => null, WeatherUvContent: () => null }));
vi.mock("../features/weather/useWeatherUvCardState", () => ({ useWeatherUvCardState: () => ({ model: null }) }));

import { AppRoutes } from "./AppRoutes";
const LOCATION = { city: "Pordenone", municipality: { istatCode: "093033", name: "Pordenone" }, source: "manual" };
const NOW = new Date("2026-10-23T06:00:00Z");
const COPY = { placeholders: { weatherTitle: "Meteo", homeTitle: "Home" } };
function weather(status, fromCache = false) {
  return {
    city: "Pordenone", current: {}, forecast: { daily: [], days: [], hourly: [] },
    error: null, status: "fresh", fromCache,
    rawCurrent: {
      primary_source: "icon2i_local_pilot",
      data_quality: { cams_status: status, cams_diagnostic: null },
      air_quality_data: status === "fresh" ? { values: { "particulate_matter_2.5um": 0 } } : null,
      pollen_data: status === "fresh"
        ? { status: "experimental_model_snapshot", values: { ambrosia: 2 } }
        : { status, values: {} },
    },
  };
}
let root, container;
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  container = document.createElement("div"); document.body.append(container);
  root = createRoot(container);
  state.cached = weather("unavailable", true);
  state.options = null;
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals(); });
function render(language, present = true) {
  root.render(present ? <AppRoutes activeTab="weather" activeLocation={LOCATION} copy={COPY} language={language} weatherNow={NOW} /> : null);
}
function cardTexts() {
  return [...container.querySelectorAll('.mf-weather-environment-tile')].slice(-2).map(node => node.textContent);
}

it.each([
  ["it", "Caricamento…", "Dati non disponibili"],
  ["fur", "In cjariament…", "Dâts no disponibii"],
])("never flashes cached unavailability on forecast re-entry in %s; keeps terminal outcomes honest", async (language, loading, unavailable) => {
  // First visit has settled; only the synchronous persisted snapshot lacks CAMS.
  state.request = Promise.resolve(weather("fresh"));
  await act(async () => render(language));
  expect(cardTexts()).toHaveLength(2);
  expect(cardTexts().join(" ")).toContain("PM2.5");
  await act(async () => render(language, false));
  let resolveWeather;
  state.request = new Promise(resolve => { resolveWeather = resolve; });
  await act(async () => render(language));
  expect(cardTexts().every(text => text.includes(loading))).toBe(true);
  expect(cardTexts().join(" ")).not.toContain(unavailable);

  // The weather part settles first; CAMS continues independently.
  await act(async () => resolveWeather(weather("pending")));
  expect(cardTexts().every(text => text.includes(loading))).toBe(true);
  await act(async () => state.options.onCamsUpdate(weather("fresh")));
  expect(cardTexts().join(" ")).toContain("PM2.5");
  expect(cardTexts().join(" ")).not.toContain(loading);
  expect(cardTexts().join(" ")).not.toContain(unavailable);

  // A later request actually fails: the cached unknown is no longer loading.
  await act(async () => render(language, false));
  state.request = Promise.resolve({ ...weather("unavailable", true), error: "offline" });
  await act(async () => render(language));
  expect(cardTexts().every(text => text.includes(unavailable))).toBe(true);
  expect(cardTexts().join(" ")).not.toContain(loading);
});