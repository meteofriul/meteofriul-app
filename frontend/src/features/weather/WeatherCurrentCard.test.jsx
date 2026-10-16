import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { WeatherCurrentCard } from "./WeatherCurrentCard";

const CASES = [
  {
    language: "it",
    change: "Cambia",
    condition: "Sereno",
    feelsLabel: "Percepita",
    location: "Pordenone",
    updated: "Aggiornato 5 minuti fa",
  },
  {
    language: "fur",
    change: "Cambie",
    condition: "Seren",
    feelsLabel: "Percepide",
    location: "Pordenon",
    updated: "Inzornât 5 minûts indaûr",
  },
];

function renderCase(entry, { interactive = true } = {}) {
  return renderToStaticMarkup(
    <WeatherCurrentCard
      changeLocationLabel={entry.change}
      icon={{ type: "Sun" }}
      locationTitle={entry.location}
      onChangeLocation={interactive ? vi.fn() : undefined}
      weather={{
        conditionLabel: entry.condition,
        feelsLike: { label: entry.feelsLabel, value: "27°C" },
        status: "fresh",
        statusTone: "fresh",
        temperature: { label: "24°C", unit: "°C", value: "24" },
        updatedLabel: entry.updated,
      }}
    />,
  );
}

describe("WeatherCurrentCard", () => {
  it.each(CASES)("shows localized current data in $language without the Home scene", (entry) => {
    const markup = renderCase(entry);

    expect(markup).toContain('class="mf-weather-current-card"');
    expect(markup).toContain(`>${entry.location}</strong>`);
    expect(markup).toContain(`>${entry.condition}</h2>`);
    expect(markup).toContain(`>${entry.feelsLabel}</span>`);
    expect(markup).toContain(`>${entry.updated}</span>`);
    expect(markup).toContain("mf-weather-current-card__icon");
    expect(markup).not.toContain("mf-home-hero");
    expect(markup).not.toContain("mf-home-eagle");
    expect(markup).not.toContain("mf-home-scene");
  });

  it("connects the heading, update status, temperature and location action accessibly", () => {
    const markup = renderCase(CASES[0]);

    expect(markup).toContain('aria-describedby="weather-current-updated"');
    expect(markup).toContain('aria-labelledby="weather-current-condition"');
    expect(markup).toContain('<h2 id="weather-current-condition">Sereno</h2>');
    expect(markup).toContain('aria-label="24°C"');
    expect(markup).toContain('id="weather-current-updated" role="status"');
    expect(markup).toContain('aria-haspopup="dialog"');
    expect(markup).toContain(">Cambia</span></button>");
    expect(markup).toMatch(/<img[^>]*alt=""[^>]*aria-hidden="true"/);
  });

  it("does not expose a dead location control when no action is available", () => {
    const markup = renderCase(CASES[0], { interactive: false });

    expect(markup).not.toContain("mf-weather-current-card__change");
    expect(markup).not.toContain("<button");
  });

  it("uses the localized unavailable label instead of a double dash", () => {
    const markup = renderToStaticMarkup(
      <WeatherCurrentCard
        locationTitle="Pordenone"
        weather={{
          conditionLabel: "Meteo non disponibile",
          temperature: { label: "Dati non disponibili", unit: "", value: null },
        }}
      />,
    );

    expect(markup).toContain(">Dati non disponibili</strong>");
    expect(markup).not.toContain("--");
  });
});
