import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HomeLocalMetrics } from "./HomeLocalMetrics";

const model = {
  label: "Dati meteo locali",
  description: "Stazione OSMER Pordenone · ore 09:00 · Osservazioni ARPA FVG · Pollini CAMS",
  weatherDescription: "Previsione ICON per Pordenone · ore 09:00",
  items: [
    { id: "wind", label: "Vento", value: "3", unit: "km/h", ariaLabel: "Vento: 3 km/h" },
    { id: "humidity", label: "Umidità", value: "71", unit: "%", ariaLabel: "Umidità: 71%" },
    { id: "pressure", label: "Press.", value: "1012", unit: "hPa", ariaLabel: "Pressione: 1012 hPa" },
    { id: "precipitation", label: "Pioggia", value: "0", unit: "mm", ariaLabel: "Pioggia: 0 mm" },
    { id: "pollen", label: "Pollini", value: "Medio", unit: "", ariaLabel: "Pollini: Livello medio", tone: "medium" },
  ],
};

describe("HomeLocalMetrics", () => {
  it("renders all five compact local definitions with icons and full accessible values", () => {
    const html = renderToStaticMarkup(<HomeLocalMetrics model={model} />);

    expect(html.match(/<dt>/g)).toHaveLength(5);
    expect(html.match(/<dd /g)).toHaveLength(5);
    expect(html.match(/<svg /g)).toHaveLength(5);
    expect(html).toContain('aria-label="Pressione: 1012 hPa"');
    expect(html).toContain('aria-description="Stazione OSMER Pordenone · ore 09:00 · Osservazioni ARPA FVG · Pollini CAMS"');
    expect(html).toContain(">0</strong>");
    expect(html).toContain(">Medio</strong>");
    expect(html).toContain("Pollini");
    expect(html).not.toMatch(/<h[1-6]|<button|<a\s|<p>/);
  });

  it("keeps the CAMS pollen species and measure compact in the local strip", () => {
    const pollenModel = {
      ...model,
      items: model.items.map((item) => item.id === "pollen" ? {
        ...item,
        label: "Artemisia",
        value: "5,06",
        unit: "grani/m³",
        ariaLabel: "Artemisia: 5,06 grani/m³",
        tone: "available",
      } : item),
    };
    const html = renderToStaticMarkup(<HomeLocalMetrics model={pollenModel} />);

    expect(html).toContain("Artemisia");
    expect(html).toContain("grani/m³");
    expect(html.match(/class="mf-home-local-metric /g)).toHaveLength(5);
  });

  it.each([null, undefined, { items: [] }])("leaves no empty wrapper when the model is absent", (empty) => {
    expect(renderToStaticMarkup(<HomeLocalMetrics model={empty} />)).toBe("");
  });

  it("keeps a five-column layout with legible text and wrapping rather than another scroller", () => {
    const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");
    const grid = css.match(/^\.mf-home-local-metrics\s*\{([^}]+)\}/m)?.[1] || "";
    const value = css.match(/^\.mf-home-local-metric dd\s*\{([^}]+)\}/m)?.[1] || "";

    expect(grid).toContain("repeat(5, minmax(0, 1fr))");
    expect(grid).not.toContain("overflow-x");
    expect(grid).not.toContain("box-shadow");
    expect(value).toContain("font-size: var(--mf-text-sm)");
    expect(value).toContain("flex-wrap: wrap");
    expect(value).toContain("overflow-wrap: anywhere");
  });
});
