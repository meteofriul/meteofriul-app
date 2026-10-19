import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WeatherForecastView } from "./WeatherForecastView";
import { WeatherForecastCharts } from "./WeatherForecastCharts";

function buildItem(index, overrides = {}) {
  const timestamp = new Date(Date.parse("2026-09-06T10:00:00Z") + index * 60 * 60 * 1000).toISOString();
  return {
    ariaLabel: `Oggi, ${12 + index}:00, Sereno, ${24 + index} gradi, Precipitazioni 0 mm`,
    conditionLabel: "Sereno",
    dateKey: "2026-09-06",
    dayLabel: "Oggi",
    details: {
      apparentTemperature: `${25 + index}°`,
      cloudCover: "10%",
      humidity: "62%",
      intervalLabel: `${11 + index}:00–${12 + index}:00`,
      precipitation: "0 mm",
      pressure: "1014 hPa",
      windDirection: "NE",
      windGusts: "18 km/h",
      windSpeed: "9 km/h",
    },
    icon: { type: "Sun" },
    intervalEnd: timestamp,
    intervalStart: new Date(Date.parse(timestamp) - 60 * 60 * 1000).toISOString(),
    precipitationAmount: "0 mm",
    precipitationProbability: null,
    retainedFields: [],
    temperature: `${24 + index}°`,
    time: `${12 + index}:00`,
    timestamp,
    values: {
      apparentTemperature: 25 + index,
      cloudCover: 10,
      humidity: 62,
      precipitation: 0,
      pressure: 1014,
      temperature: 24 + index,
      windDirection: 45,
      windGusts: 18,
      windSpeed: 9,
    },
    ...overrides,
  };
}

function buildModel({ language = "it" } = {}) {
  const items = [buildItem(0), buildItem(1)];
  const title = language === "fur" ? "Prossimis 48 oris" : "Prossime 48 ore";
  return {
    cams: {
      heading: language === "fur" ? "Polins" : "Pollini",
      note: language === "fur"
        ? "Concentrazions di model disponibii"
        : "Concentrazioni modellistiche disponibili",
      status: "available",
      units: "grani/m³",
      validLabel: language === "fur" ? "Dât valit aes 12:00" : "Dato valido alle 12:00",
      values: [{ id: "graminacee", label: "Graminacee", displayValue: "2,5", value: 2.5 }],
    },
    changeLocationLabel: language === "fur" ? "Cambie" : "Cambia",
    header: {
      locationTitle: language === "fur" ? "Pordenon" : "Pordenone",
      sourceTimingLabel: "ICON-2I · aggiornamento modello 06:00",
      statusLabel: language === "fur" ? "Dâts verificâts" : "Dati verificati",
      statusTone: "fresh",
    },
    hourly: {
      groups: [{ dateKey: "2026-09-06", label: language === "fur" ? "Vuê" : "Oggi", items }],
      items,
      retainedValuesLabel: "",
      scrollLabel: title,
      summaries: [{
        ariaLabel: language === "fur" ? "Vuê, di cheste ore indenant" : "Oggi, da quest'ora",
        conditionLabel: "Sereno",
        coverageLabel: language === "fur" ? "Di cheste ore indenant" : "Da quest'ora",
        dateKey: "2026-09-06",
        firstItemKey: items[0].timestamp,
        gustLabel: "18 km/h",
        gustsLabel: language === "fur" ? "Rafiche massime" : "Raffica max",
        icon: { type: "Sun" },
        id: "today",
        label: language === "fur" ? "Vuê" : "Oggi",
        maxTemperature: "25°",
        minTemperature: "24°",
        precipitationLabel: "0 mm",
        precipitationTitle: language === "fur" ? "Precipitazions" : "Precipitazioni",
      }],
      title,
    },
    weather: {},
  };
}

describe("WeatherForecastView", () => {
  it.each([
    ["it", "Dati meteo in arrivo", "Le previsioni saranno mostrate appena i dati saranno disponibili."],
    ["fur", "Dâts meteo in rivade", "O mostrarìn lis previsions a pene che il dât verificât al sarà disponibil."],
  ])("renders verified-data loading copy in %s", (language, title, body) => {
    const markup = renderToStaticMarkup(<WeatherForecastView language={language} model={null} />);

    expect(markup).toContain('aria-live="polite"');
    expect(markup).toContain(title);
    expect(markup).toContain(body);
  });

  it("renders a compact consultation header without the illustrated Home scene", () => {
    const markup = renderToStaticMarkup(
      <WeatherForecastView model={buildModel()} onChangeLocation={() => {}} />,
    );

    expect(markup).toContain("mf-weather-forecast-header");
    expect(markup).toContain("Pordenone");
    expect(markup).toContain("ICON-2I · aggiornamento modello 06:00");
    expect(markup).not.toContain("dato valido");
    expect(markup).not.toContain("mf-home-hero");
    expect(markup).not.toContain("mf-home-eagle");
  });

  it("can delegate the location row while retaining forecast date and source metadata", () => {
    const model = buildModel();
    model.header.dateKey = "2026-09-06";
    model.header.dateLabel = "Domenica 6 set";
    const markup = renderToStaticMarkup(
      <WeatherForecastView
        model={model}
        onChangeLocation={() => {}}
        showLocationHeader={false}
      />,
    );

    expect(markup).not.toContain("mf-weather-forecast-header__location");
    expect(markup).not.toContain(">Cambia<");
    expect(markup).toContain("Domenica 6 set");
    expect(markup).toContain("ICON-2I · aggiornamento modello 06:00");
  });

  it("places the compact official alert between the header and ICON consultation", () => {
    const markup = renderToStaticMarkup(
      <WeatherForecastView
        model={buildModel()}
        officialAlert={{
          label: "Allerta gialla",
          meta: "Protezione Civile FVG",
          tone: "yellow",
          validityLabel: "Valida fino alle 18:00",
        }}
        onOfficialAlertOpen={() => {}}
      />,
    );

    expect(markup.indexOf("mf-weather-forecast-header")).toBeLessThan(markup.indexOf("mf-official-alert-compact"));
    expect(markup.indexOf("mf-official-alert-compact")).toBeLessThan(markup.indexOf("mf-weather-hourly-card"));
    expect(markup).toContain("Allerta gialla");
  });

  it("renders compact rows with only the first hour expandable and initially closed", () => {
    const markup = renderToStaticMarkup(<WeatherForecastView model={buildModel()} />);

    expect(markup).toContain("mf-weather-hourly-list");
    expect(markup).toContain("mf-weather-hourly-row");
    expect(markup).toContain("Evoluzione oraria");
    expect(markup).not.toContain('aria-expanded="true"');
    expect(markup.match(/aria-expanded="false"/g)).toHaveLength(1);
    expect(markup).not.toContain('role="region"');
    expect(markup).toContain("Dettaglio e grafici");
    expect(markup).toContain("0 mm");
    expect(markup).not.toContain("mf-weather-hourly-timeline__grid");
    expect(markup).not.toContain("Probabilit");
  });

  it("renders three labelled SVG charts with a synchronized cursor", () => {
    const items = buildModel().hourly.items;
    const markup = renderToStaticMarkup(<WeatherForecastCharts items={items} selectedKey={items[0].timestamp} />);

    expect(markup).toContain("Andamento");
    expect(markup).toContain("forecast-temperature-chart-title");
    expect(markup).toContain("forecast-precipitation-chart-title");
    expect(markup).toContain("forecast-wind-chart-title");
    expect(markup.match(/viewBox="0 0 640 184"/g)).toHaveLength(3);
    expect(markup.match(/data-testid="forecast-chart-cursor"/g)).toHaveLength(3);
    expect(markup).toContain('data-style="dashed"');
  });

  it("does not turn missing chart values into invented zeroes", () => {
    const model = buildModel();
    model.hourly.items.forEach((item) => {
      item.values = {
        apparentTemperature: null,
        precipitation: null,
        temperature: null,
        windGusts: null,
        windSpeed: null,
      };
    });

    const markup = renderToStaticMarkup(<WeatherForecastCharts items={model.hourly.items} selectedKey={model.hourly.items[0].timestamp} />);

    expect(markup.match(/Dati insufficienti per il grafico/g)).toHaveLength(3);
    expect(markup).not.toContain('class="mf-weather-chart__bar"');
    expect(markup).not.toContain('class="mf-weather-chart__line"');
  });

  it("keeps CAMS in its own card after the ICON hourly list and never renders dash placeholders", () => {
    const markup = renderToStaticMarkup(<WeatherForecastView model={buildModel()} />);

    expect(markup.indexOf("mf-weather-hourly-card")).toBeLessThan(markup.indexOf("mf-weather-cams-card"));
    expect(markup).toContain("<h2>Pollini</h2>");
    expect(markup).toContain("Concentrazioni modellistiche disponibili");
    expect(markup.match(/Previsione sperimentale/g)).toHaveLength(1);
    expect(markup).toContain("2,5");
    expect(markup).not.toContain("--");
    expect(markup).not.toContain("—");
  });

  it("localizes the list, details and CAMS separation in Friulian", () => {
    const markup = renderToStaticMarkup(
      <WeatherForecastView language="fur" model={buildModel({ language: "fur" })} />,
    );

    expect(markup).toContain("Prossimis 48 oris");
    expect(markup).not.toContain("Vierç la prime ore");
    expect(markup).toContain("Evoluzion par ore");
    expect(markup).toContain("Precipitazions");
    expect(markup).toContain("Detai e grafics");
    expect(markup).toContain("<h2>Polins</h2>");
  });
  it("shows every third hour with a single expandable row", () => {
    const model = buildModel();
    const items = Array.from({ length: 24 }, (_, index) => buildItem(index));
    model.hourly.items = items;
    model.hourly.groups[0].items = items;
    const markup = renderToStaticMarkup(<WeatherForecastView model={model} />);
    expect(markup.match(/class="mf-weather-hourly-row"/g)).toHaveLength(8);
    expect(markup.match(/aria-expanded=/g)).toHaveLength(1);
    expect(markup).not.toContain("Mostra le successive");
    expect(markup).not.toContain("fasce · ogni 3 ore");
    expect(markup).not.toContain("mf-weather-hourly-card__instruction");
    expect(markup).not.toContain("mf-weather-rain-preview");
    expect(markup).toContain("mf-weather-hourly-row__rain");
  });
});
