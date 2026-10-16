import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { BulletinLocalCard } from "./BulletinLocalCard";

function buildModel() {
  return {
    changeLabel: "Cambia",
    currentDataLabel: "Dati meteo locali",
    detailsSourceLabel: "Osservazioni ARPA FVG · Pollini CAMS",
    evolutionLabel: "Prossime 12 ore",
    hourly: [
      {
        ariaLabel: "00:00, 27 gradi, 10%",
        icon: { type: "PartlyCloudy", night: true },
        precipitationProbability: 10,
        temperature: "27°",
        temperatureTone: "warm",
        time: "00:00",
      },
    ],
    metrics: [
      { id: "humidity", label: "Umidità", value: "64%" },
      { id: "pressure", label: "Pressione", value: "1009 hPa" },
      { id: "precipitation", label: "Pioggia", tone: "inactive", value: "0 mm" },
    ],
    observationLabel: "Stazione OSMER Pordenone · ore 22:00",
    pollen: {
      detail: "Artemisia · Graminacee",
      label: "Pollini",
      level: "Livello medio",
      strongestLabel: "Prevalenti",
      tone: "medium",
    },
    sourceLabel: "osservazioni ARPA FVG · evoluzione Open-Meteo · pollini CAMS",
    title: "A Pordenone",
  };
}

describe("BulletinLocalCard", () => {
  it("renders pilot pollen concentrations without turning missing values or traces into zero", () => {
    const model = buildModel();
    model.pollen = { ...model.pollen, level: "Previsione sperimentale", tone: "available", detail: "", units: "grani/m³",
      values: [
        { id: "ontano", label: "Ontano", value: 0, displayValue: "0" },
        { id: "betulla", label: "Betulla", value: 1e-9, displayValue: "<0,01" },
        { id: "olivo", label: "Olivo", value: null, displayValue: "—" },
      ] };
    const markup = renderToStaticMarkup(<BulletinLocalCard model={model} />);
    expect(markup).toContain("Concentrazioni polliniche CAMS (grani/m³)");
    expect(markup).toContain('title="0">0 grani/m³');
    expect(markup).toContain('title="1e-9">&lt;0,01 grani/m³');
    expect(markup).toContain('title="Dato non disponibile">—');
    expect(markup).not.toContain("Livello medio");
  });

  it("keeps observed details and pollen without duplicating the Home evolution", () => {
    const markup = renderToStaticMarkup(
      <BulletinLocalCard model={buildModel()} onChangeLocation={() => {}} />,
    );

    expect(markup).toContain("A Pordenone");
    expect(markup).not.toContain("mf-bulletin-local-card__eyebrow");
    expect(markup).toContain("Stazione OSMER Pordenone");
    expect(markup).not.toContain("Prossime 12 ore");
    expect(markup).toContain("Livello medio");
    expect(markup).toContain("Pollini CAMS");
    expect(markup).toContain("mf-bulletin-local-metric--precipitation-inactive");
    expect(markup).toContain("mf-bulletin-local-pollen--medium");
    expect(markup).toContain("<button");
    expect(markup).not.toContain("mf-bulletin-context-item");
    expect((markup.match(/<section/g) || [])).toHaveLength(1);
  });

  it("renders nothing when the local model is unavailable", () => {
    expect(renderToStaticMarkup(<BulletinLocalCard model={null} />)).toBe("");
  });
});
