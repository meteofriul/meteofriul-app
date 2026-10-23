import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";
import { expect, it } from "vitest";
import { WeatherCamsCard } from "./WeatherCamsCard";

const DETAIL_MODEL = {
  air: {
    run_at: "2026-09-14T00:00:00Z",
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
  runAt: "2026-09-14T00:00:00Z",
  status: "available",
  units: "grani/m³",
  validAt: "2026-09-14T18:00:00Z",
  values: [
    { id: "ragweed", label: "Ambrosia", displayValue: "0,4", value: 0.4 },
    { id: "mugwort", label: "Artemisia", displayValue: "21,96", value: 21.96 },
  ],
};

function renderDocument(element) {
  return new JSDOM(renderToStaticMarkup(element)).window.document;
}

it("keeps pollen and all four air measurements fully visible", () => {
  const html = renderToStaticMarkup(<WeatherCamsCard model={{
    heading: "CAMS · Pollini", status: "available", units: "grani/m³",
    values: [{ id: "grass", label: "Graminacee", displayValue: "2", value: 2 }],
    air: { valid_at: "2026-09-04T21:00:00Z", values: {
      "particulate_matter_2.5um": 0, particulate_matter_10um: 12.34, ozone: null,
    } },
  }} />);
  expect(html).not.toContain("<details");
  expect(html).not.toContain("Dettaglio aria");
  expect(html).toContain("Concentrazioni previste da modello");
  expect(html).not.toContain("non misure di una centralina");
  expect(html).toContain("Ozono");
  expect(html).toContain("Biossido di azoto");
  expect(html).toContain("12,3");
  expect(html).toContain("PM2.5");
  expect(html).toContain("µg/m³");
  expect(html).toContain("04/09");
  expect(html).toContain("Graminacee");
  expect(html).not.toContain("Tutti i pollini");
  expect(html).not.toContain("Ultimo dato verificato");
});

it.each([
  ["it", "Ultimo dato verificato · 04/09/2026, 23:00"],
  ["fur", "Ultin dât verificât · 04/09/2026, 23:00"],
])("marks retained air and pollen values as last verified in %s", (language, label) => {
  const html = renderToStaticMarkup(<WeatherCamsCard language={language} model={{
    heading: language === "fur" ? "Polins" : "Pollini",
    status: "available",
    units: "grani/m³",
    values: [{ id: "grass", label: "Graminacee", displayValue: "2", value: 2 }],
    pollenSampleStatus: "last_known",
    pollenLastKnownLabel: label,
    airSampleStatus: "last_known",
    airLastKnownLabel: label,
    air: {
      sample_status: "last_known",
      valid_at: "2026-09-04T21:00:00Z",
      values: { "particulate_matter_2.5um": 1.2 },
    },
  }} />);

  expect(html.match(new RegExp(label, "g"))).toHaveLength(2);
  expect(html.match(/role="status"/g)).toHaveLength(2);
  expect(html).toContain("1,2");
  expect(html).toContain("Graminacee");
  expect(html).not.toContain("Concentrazioni modellistiche disponibili");
});

it.each(["air", "pollen"])("keeps one shared last-verified status hook in the %s detail", (section) => {
  const label = "Ultimo dato verificato · 14/09/2026, 20:00";
  const model = {
    ...DETAIL_MODEL,
    airSampleStatus: "last_known",
    airLastKnownLabel: label,
    pollenSampleStatus: "last_known",
    pollenLastKnownLabel: label,
  };
  const document = renderDocument(<WeatherCamsCard detailMode model={model} section={section} />);
  const statuses = document.querySelectorAll("p.mf-weather-cams-card__status[role=status]");

  expect(statuses).toHaveLength(1);
  expect(statuses[0].textContent).toBe(label);
});

it.each([
  ["air", "Stima modellistica su griglia: non sostituisce i rilievi delle centraline al suolo."],
  ["pollen", "Modello matematico a larga scala: non sostituisce i campionatori aerobiologici ARPA."],
])("separates Italian CAMS traceability from the %s methodological note", (section, methodology) => {
  const document = renderDocument(<WeatherCamsCard detailMode model={DETAIL_MODEL} section={section} />);
  const footer = document.querySelector(".mf-weather-cams-card__footer");

  expect(footer).not.toBeNull();
  expect(footer.classList.contains("mf-weather-cams-card__footer--detail")).toBe(true);
  expect([...footer.children].map((child) => child.className)).toEqual([
    "mf-weather-cams-card__trace",
    "mf-weather-cams-card__method-note",
  ]);
  expect(footer.querySelector(".mf-weather-cams-card__trace").textContent)
    .toBe("Fonte: Copernicus CAMS · Riferito alle 20:00 (agg. 02:00)");
  expect(footer.querySelector(".mf-weather-cams-card__method-note").textContent).toBe(methodology);
  expect(footer.querySelector(".mf-weather-cams-card__method-note svg")?.getAttribute("aria-hidden"))
    .toBe("true");

  if (section === "air") {
    expect(document.body.textContent).toContain("PM2.5");
    expect(document.body.textContent).toContain("Biossido di azoto");
  } else {
    expect(document.body.textContent).toContain("Ambrosia");
    expect(document.body.textContent).toContain("Artemisia");
  }
});

it.each([
  ["air", "Stime modelistiche su gridele: no sostituìs lis rilevazions des centralinis a tiere."],
  ["pollen", "Model matematic su largje scjale: no sostituìs i campionadôrs aerobiologjics ARPA."],
])("uses the concise Friulian CAMS trace and the specific %s note", (section, methodology) => {
  const model = { ...DETAIL_MODEL, heading: "Polins" };
  const document = renderDocument(<WeatherCamsCard detailMode language="fur" model={model} section={section} />);
  const footer = document.querySelector(".mf-weather-cams-card__footer");

  expect(footer.querySelector(".mf-weather-cams-card__trace").textContent)
    .toBe("Font: Copernicus CAMS · Riferît aes 20:00 (inz. 02:00)");
  expect(footer.querySelector(".mf-weather-cams-card__method-note").textContent).toBe(methodology);
});

it("preserves both calendar dates when the valid sample and model run fall on different local days", () => {
  const model = {
    ...DETAIL_MODEL,
    air: {
      ...DETAIL_MODEL.air,
      run_at: "2026-09-13T22:00:00Z",
      valid_at: "2026-09-14T23:00:00Z",
    },
    runAt: "2026-09-13T22:00:00Z",
    validAt: "2026-09-14T23:00:00Z",
  };

  for (const section of ["air", "pollen"]) {
    const document = renderDocument(<WeatherCamsCard detailMode model={model} section={section} />);
    const trace = document.querySelector(".mf-weather-cams-card__trace").textContent;

    expect(trace).toContain("15/09");
    expect(trace).toContain("14/09");
    expect(trace).toContain("01:00");
    expect(trace).toContain("00:00");
  }
});

it("keeps the calendar date visible for a retained last-known sample from one model day", () => {
  const model = {
    ...DETAIL_MODEL,
    airSampleStatus: "last_known",
  };
  const document = renderDocument(<WeatherCamsCard detailMode model={model} section="air" />);

  expect(document.querySelector(".mf-weather-cams-card__trace").textContent)
    .toBe("Fonte: Copernicus CAMS · Riferito al 14/09, 20:00 (agg. 14/09, 02:00)");
});

it("leaves the non-detail legacy footer and copy unchanged", () => {
  const document = renderDocument(<WeatherCamsCard model={DETAIL_MODEL} />);
  const footers = [...document.querySelectorAll(".mf-weather-cams-card__footer")];

  expect(footers).toHaveLength(2);
  expect(document.querySelector(".mf-weather-cams-card__trace")).toBeNull();
  expect(document.querySelector(".mf-weather-cams-card__method-note")).toBeNull();
  expect(footers[0].textContent).toBe("Fonte: CAMS / Copernicus · Dato valido 14/09, 20:00");
  expect(footers[1].textContent).toBe("Fonte: CAMS / Copernicus");
  expect(document.body.textContent).not.toContain("Stima modellistica su griglia");
  expect(document.body.textContent).not.toContain("Modello matematico a larga scala");
});


it("shows the waiting update label on both CAMS cards while preserving run and validity", () => {
  const continuityLabel = "Previsione della corsa precedente · aggiornamento in attesa";
  const document = renderDocument(<WeatherCamsCard detailMode model={{ ...DETAIL_MODEL, continuityLabel,
    validAt: "2026-09-15T09:00:00Z", air: { ...DETAIL_MODEL.air, valid_at: "2026-09-15T09:00:00Z" } }} />);
  expect([...document.querySelectorAll(".mf-weather-cams-card__status")].map(row => row.textContent))
    .toEqual([continuityLabel, continuityLabel]);
  expect(document.body.textContent).toContain("14/09");
  expect(document.body.textContent).not.toContain("Ultimo dato verificato");
});


it.each([
  ["it", "Caricamento…", "Dati non disponibili"],
  ["fur", "In cjariament…", "Dâts no disponibii"],
])("uses the same pending and unavailable text in both %s detail sheets", (language, loading, unavailable) => {
  for (const section of ["air", "pollen"]) {
    for (const [status, expected] of [["pending", loading], ["unavailable", unavailable]]) {
      const model = { ...DETAIL_MODEL, air: { values: { ozone: null } }, airStatus: status, status, values: [] };
      const document = renderDocument(<WeatherCamsCard detailMode language={language} model={model} section={section} />);
      expect(document.querySelector('[role="status"]').textContent.trim()).toBe(expected);
      expect(document.querySelector("dl")).toBeNull();
    }
  }
});
