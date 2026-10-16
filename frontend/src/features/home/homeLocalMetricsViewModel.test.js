import { describe, expect, it } from "vitest";

import { createBulletinLocalDataState } from "../bulletin/bulletinLocalDataController";
import { buildBulletinLocalViewModel } from "../bulletin/bulletinLocalViewModel";
import { buildHomeLocalMetricsViewModel } from "./homeLocalMetricsViewModel";

function buildLocalWeather(overrides = {}) {
  return {
    currentDataLabel: "Dati meteo locali",
    observationLabel: "Stazione OSMER Pordenone · ore 22:00",
    detailsSourceLabel: "Osservazioni ARPA FVG · Pollini CAMS",
    sourceLabel: "Osservazioni ARPA FVG · Evoluzione Open-Meteo · Pollini CAMS",
    metrics: [
      { id: "humidity", label: "Umidità", source: "osmer", value: "71%" },
      { id: "pressure", label: "Pressione", source: "osmer", value: "1012 hPa" },
      { id: "wind", label: "Vento", source: "osmer", value: "3 km/h", detail: "ESE · raffiche 6 km/h" },
      { id: "precipitation", label: "Pioggia", source: "osmer", value: "0 mm", tone: "inactive" },
    ],
    pollen: {
      available: true,
      label: "Pollini",
      level: "Livello medio",
      tone: "medium",
      detail: "Artemisia · Graminacee",
      strongestLabel: "Prevalenti",
    },
    ...overrides,
  };
}

describe("home local metrics view model", () => {
  it("returns exactly five compact cells in Home order using the formatted local values", () => {
    const model = buildHomeLocalMetricsViewModel(buildLocalWeather());

    expect(model.items).toEqual([
      { id: "wind", label: "Vento", value: "3", unit: "km/h", ariaLabel: "Vento: 3 km/h, ESE · raffiche 6 km/h" },
      { id: "humidity", label: "Umidità", value: "71", unit: "%", ariaLabel: "Umidità: 71%" },
      { id: "pressure", label: "Press.", value: "1012", unit: "hPa", ariaLabel: "Pressione: 1012 hPa" },
      { id: "precipitation", label: "Pioggia", value: "0", unit: "mm", ariaLabel: "Pioggia: 0 mm", tone: "inactive" },
      { id: "pollen", label: "Pollini", value: "Medio", unit: "", ariaLabel: "Pollini: Livello medio, Prevalenti: Artemisia · Graminacee", tone: "medium" },
    ]);
    expect(model.label).toBe("Dati meteo locali");
    expect(model.weatherDescription).toBe("Stazione OSMER Pordenone · ore 22:00");
    expect(model.description).toBe("Stazione OSMER Pordenone · ore 22:00 · Osservazioni ARPA FVG · Pollini CAMS");
    expect(Object.keys(model)).toEqual(["label", "description", "weatherDescription", "items"]);
  });

  it("retains source and observation metadata only in the description", () => {
    const model = buildHomeLocalMetricsViewModel(buildLocalWeather({ detailsSourceLabel: "" }));

    expect(model.description).toContain("Stazione OSMER Pordenone · ore 22:00");
    expect(model.description).toContain("Evoluzione Open-Meteo");
    expect(model.items.every((item) => !Object.hasOwn(item, "source"))).toBe(true);
    expect(buildHomeLocalMetricsViewModel({}).description).toBe("");
  });

  it("does not manufacture a strip when no local model exists", () => {
    expect(buildHomeLocalMetricsViewModel(null)).toBeNull();
    expect(buildHomeLocalMetricsViewModel(undefined)).toBeNull();
  });

  it.each([undefined, null, "", "   ", "—", Number.NaN, Infinity])(
    "represents a missing metric value %s as a dash without inventing zero",
    (value) => {
      const model = buildHomeLocalMetricsViewModel({
        metrics: [{ id: "wind", value }],
      });

      expect(model.items).toHaveLength(5);
      expect(model.items.every((item) => item.value === "—" && item.unit === "")).toBe(true);
      expect(model.items[0].ariaLabel).toBe("Vento: Dato non disponibile");
      expect(model.items[4]).toMatchObject({ tone: "unavailable", ariaLabel: "Pollini: Dati pollinici non disponibili" });
    },
  );

  it("keeps supplied zero values for every numeric cell", () => {
    const model = buildHomeLocalMetricsViewModel({
      metrics: [
        { id: "wind", value: "0 km/h" },
        { id: "humidity", value: "0%" },
        { id: "pressure", value: 0 },
        { id: "precipitation", value: "0 mm" },
      ],
    });

    expect(model.items.slice(0, 4).map((item) => item.value)).toEqual(["0", "0", "0", "0"]);
    expect(model.items[3].ariaLabel).toBe("Pioggia: 0 mm");
  });

  it("preserves decimals and unsupported units instead of converting or rounding", () => {
    const model = buildHomeLocalMetricsViewModel({
      metrics: [
        { id: "wind", value: "3.25 km/h" },
        { id: "humidity", value: "71,5%" },
        { id: "pressure", value: "29.91 inHg" },
        { id: "precipitation", value: "0,7 mm" },
      ],
    });

    expect(model.items.slice(0, 4).map(({ value, unit }) => ({ value, unit }))).toEqual([
      { value: "3.25", unit: "km/h" },
      { value: "71,5", unit: "%" },
      { value: "29.91 inHg", unit: "" },
      { value: "0,7", unit: "mm" },
    ]);
    expect(model.items[3].ariaLabel).toBe("Pioggia: 0,7 mm");
  });

  it.each([
    ["low", "Basso", "Bas"],
    ["medium", "Medio", "Medi"],
    ["high", "Alto", "Alt"],
    ["very-high", "Molto alto", "Une vore alt"],
    ["available", "Dati", "Dâts"],
    ["unavailable", "—", "—"],
  ])("maps the existing %s pollen tone to short Italian and Friulian labels", (tone, italian, friulian) => {
    const localWeather = { pollen: { tone, available: tone !== "unavailable" } };

    expect(buildHomeLocalMetricsViewModel(localWeather).items[4]).toMatchObject({ value: italian, tone });
    expect(buildHomeLocalMetricsViewModel(localWeather, { language: "fur" }).items[4]).toMatchObject({
      label: "Polins", value: friulian, tone,
    });
  });

  it.each([null, {}, { tone: "unknown" }, { available: false, tone: "low", level: "Livello basso" }])(
    "never assumes low pollen when pollen is missing or unavailable: %j",
    (pollen) => {
      expect(buildHomeLocalMetricsViewModel({ pollen }).items[4]).toMatchObject({
        value: "—", tone: "unavailable", ariaLabel: "Pollini: Dati pollinici non disponibili",
      });
    },
  );

  it("uses available without guessing a severity when pollen has data but no known tone", () => {
    expect(buildHomeLocalMetricsViewModel({ pollen: { available: true, tone: "unknown" } }).items[4])
      .toMatchObject({ value: "Dati", tone: "available" });
  });

  it("shows the prevailing CAMS species and its concentration without inventing a health level", () => {
    const pollen = {
      available: true,
      status: "experimental_model_snapshot",
      tone: "available",
      units: "grani/m³",
      values: [
        { id: "graminacee", label: "Graminacee", value: 2.97, displayValue: "2,97" },
        { id: "artemisia", label: "Artemisia", value: 5.06, displayValue: "5,06" },
        { id: "ambrosia", label: "Ambrosia", value: 0.62, displayValue: "0,62" },
      ],
    };

    expect(buildHomeLocalMetricsViewModel({ pollen }).items[4]).toEqual({
      id: "pollen",
      label: "Artemisia",
      value: "5,06",
      unit: "grani/m³",
      ariaLabel: "Artemisia: 5,06 grani/m³",
      tone: "available",
    });
  });

  it("localizes a numeric CAMS pollen value and keeps the species visible in Friulian", () => {
    const pollen = {
      available: true,
      status: "experimental_model_snapshot",
      units: "grani/m³",
      values: [{ label: "Artemisie", value: 5.06, displayValue: "5,06" }],
    };

    expect(buildHomeLocalMetricsViewModel({ pollen }, { language: "fur" }).items[4]).toMatchObject({
      label: "Artemisie",
      value: "5,06",
      unit: "grani/m³",
      ariaLabel: "Artemisie: 5,06 grani/m³",
    });
  });

  it("does not name an arbitrary prevailing species when concentrations are tied", () => {
    const pollen = {
      available: true,
      status: "experimental_model_snapshot",
      units: "grani/m³",
      values: [
        { label: "Artemisia", value: 5.06, displayValue: "5,06" },
        { label: "Graminacee", value: 5.06, displayValue: "5,06" },
      ],
    };

    expect(buildHomeLocalMetricsViewModel({ pollen }).items[4]).toEqual({
      id: "pollen",
      label: "Pollini",
      value: "5,06",
      unit: "grani/m³",
      ariaLabel: "Pollini: 5,06 grani/m³",
      tone: "available",
    });
  });

  it("shows a measured zero without naming an arbitrary prevailing species", () => {
    const pollen = {
      available: true,
      status: "experimental_model_snapshot",
      units: "grani/m³",
      values: [
        { label: "Ontano", value: 0, displayValue: "0" },
        { label: "Betulla", value: 0, displayValue: "0" },
      ],
    };

    expect(buildHomeLocalMetricsViewModel({ pollen }).items[4]).toMatchObject({
      label: "Pollini",
      value: "0",
      unit: "grani/m³",
      ariaLabel: "Pollini: 0 grani/m³",
    });
  });

  it.each([
    ["pending", true, "In arrivo", "pending", "Pollini: Dati pollinici in arrivo"],
    ["unavailable", true, "—", "unavailable", "Pollini: Dati pollinici non disponibili"],
    ["experimental_model_snapshot", false, "—", "unavailable", "Pollini: Dati pollinici non disponibili"],
  ])("keeps terminal %s pollen state ahead of stale numeric values", (
    status, available, value, tone, ariaLabel,
  ) => {
    const pollen = {
      available,
      status,
      values: [{ label: "Artemisia", value: 5.06, displayValue: "5,06" }],
    };

    expect(buildHomeLocalMetricsViewModel({ pollen }).items[4]).toMatchObject({
      value, tone, ariaLabel,
    });
  });

  it.each([null, undefined, "", "   "])(
    "does not turn a missing pollen concentration %j into a measured zero",
    (value) => {
      const pollen = {
        available: true,
        status: "experimental_model_snapshot",
        tone: "available",
        values: [{ label: "Artemisia", value }],
      };

      expect(buildHomeLocalMetricsViewModel({ pollen }).items[4]).toMatchObject({
        value: "Dati",
        unit: "",
        tone: "available",
      });
    },
  );

  it("localizes missing-data labels and full pressure aria text in Friulian", () => {
    const model = buildHomeLocalMetricsViewModel({}, { language: "fur" });

    expect(model.label).toBe("Dâts meteo locâi");
    expect(model.items.map((item) => item.label)).toEqual(["Vint", "Umiditât", "Press.", "Pluie", "Polins"]);
    expect(model.items[2].ariaLabel).toBe("Pression: Dât no disponibil");
    expect(model.items[4].ariaLabel).toBe("Polins: Dâts sui polins no disponibii");
    expect(buildHomeLocalMetricsViewModel({}, { language: "en" }).label).toBe("Dati meteo locali");
  });

  it("reuses the source's localized labels", () => {
    const model = buildHomeLocalMetricsViewModel({
      currentDataLabel: "Dâts meteo locâi",
      metrics: [{ id: "wind", label: "Vint", value: "3 km/h" }],
      pollen: { label: "Polins", tone: "medium", level: "Nivel medi" },
    }, { language: "fur" });

    expect(model.items[0]).toMatchObject({ label: "Vint", ariaLabel: "Vint: 3 km/h" });
    expect(model.items[4]).toMatchObject({ label: "Polins", ariaLabel: "Polins: Nivel medi" });
  });

  it("preserves the bulletin model's station priority and model fallback", () => {
    const state = createBulletinLocalDataState({
      city: "Pordenone",
      current: {
        humidity: 50,
        pressure: 1005,
        wind_speed: 10,
        precipitation: 4,
        station: {
          station: "Pordenone",
          time: "22:00",
          humidity: 71,
          pressure: null,
          wind_speed: 3,
          precipitation: 0,
        },
        pollen_data: { level: "Molto alto", values: { graminacee: 1 } },
      },
    });
    const localWeather = buildBulletinLocalViewModel(state);
    const model = buildHomeLocalMetricsViewModel(localWeather);

    expect(localWeather.metrics.find((metric) => metric.id === "wind").source).toBe("osmer");
    expect(localWeather.metrics.find((metric) => metric.id === "pressure").source).toBe("open-meteo");
    expect(model.items.map((item) => item.value)).toEqual(["3", "71", "1005", "0", "Molto alto"]);
    expect(model.description).toContain("Stazione OSMER Pordenone · ore 22:00");
    expect(model.description).toContain("Osservazioni ARPA FVG · Evoluzione Open-Meteo · Pollini CAMS");
  });

  it("does not mutate the shared local model or its metric ordering", () => {
    const localWeather = buildLocalWeather();
    const original = structuredClone(localWeather);
    localWeather.metrics.forEach(Object.freeze);
    Object.freeze(localWeather.metrics);
    Object.freeze(localWeather.pollen);
    Object.freeze(localWeather);

    buildHomeLocalMetricsViewModel(localWeather);

    expect(localWeather).toEqual(original);
  });
});
