import { JSDOM } from "jsdom";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const pilotHarness = vi.hoisted(() => ({
  enabled: vi.fn(() => false),
}));

vi.mock("../../services/localWeatherPilot", async (importOriginal) => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: pilotHarness.enabled,
  isLocalWeatherPilot: pilotHarness.enabled,
}));

import { WeatherForecastView } from "./WeatherForecastView";

function buildItem(index) {
  const timestamp = new Date(Date.parse("2026-09-14T00:00:00Z") + index * 60 * 60 * 1000).toISOString();
  return {
    ariaLabel: `Oggi, ${2 + index}:00, Sereno, ${19 + index} gradi, Precipitazioni 0 mm`,
    conditionLabel: "Sereno",
    dateKey: "2026-09-14",
    dayLabel: "Oggi",
    details: {
      apparentTemperature: `${18 + index}°`,
      cloudCover: "10%",
      humidity: "62%",
      intervalLabel: `${1 + index}:00–${2 + index}:00`,
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
    temperature: `${19 + index}°`,
    time: `${String(2 + index).padStart(2, "0")}:00`,
    timestamp,
    values: {
      apparentTemperature: 18 + index,
      cloudCover: 10,
      humidity: 62,
      precipitation: 0,
      pressure: 1014,
      temperature: 19 + index,
      windDirection: 45,
      windGusts: 18,
      windSpeed: 9,
    },
  };
}

function buildModel({ withHours = true } = {}) {
  const items = withHours ? [buildItem(0), buildItem(1)] : [];
  return {
    cams: { status: "unavailable" },
    changeLocationLabel: "Cambia",
    header: {
      compactRunLabel: "13/09 · 14:00",
      compactSourceLabel: "Modello ICON-2I",
      dateKey: "2026-09-14",
      dateLabel: "Lunedì 14 set",
      locationTitle: "Pordenone",
      runAt: "2026-09-13T12:00:00Z",
      sourceTimingLabel: "ICON-2I · aggiornamento modello 13/09/2026, 14:00",
      statusLabel: "Dati verificati",
      statusTone: "fresh",
    },
    hourly: {
      groups: items.length ? [{ dateKey: "2026-09-14", label: "Oggi", items }] : [],
      items,
      retainedValuesLabel: "",
      scrollLabel: "Prossime 48 ore",
      summaries: items.length ? [{
        dateKey: "2026-09-14",
        fullDayMaxTemperature: "25°",
        fullDayMinTemperature: "15°",
        icon: { type: "Sun" },
        id: "today",
        label: "Oggi",
        maxTemperature: "25°",
        minTemperature: "19°",
      }] : [],
      title: "Prossime 48 ore",
    },
    weather: {},
  };
}

function renderDocument(model) {
  const html = renderToStaticMarkup(
    <WeatherForecastView
      location={{ city: "Pordenone", lat: 45.9567, lon: 12.6605 }}
      model={model}
      showLocationHeader={false}
      weatherNow={new Date("2026-09-14T12:00:00Z")}
    />,
  );
  return new JSDOM(html).window.document;
}

beforeEach(() => {
  pilotHarness.enabled.mockReset();
  pilotHarness.enabled.mockReturnValue(false);
});

describe("WeatherForecastView pilot forecast-card layout", () => {
  it("embeds truthful consultation and run metadata before the pilot day and hourly controls", () => {
    pilotHarness.enabled.mockReturnValue(true);
    const document = renderDocument(buildModel());
    const view = document.querySelector(".mf-weather-forecast-view");
    const card = view.querySelector(".mf-weather-hourly-card--ribbon");
    const header = card.querySelector(".mf-weather-hourly-card__pilot-header");
    const dayPicker = card.querySelector(".mf-weather-day-picker");
    const ribbon = card.querySelector(".mf-weather-hour-ribbon");
    const environment = view.querySelector(".mf-weather-environment-grid");

    expect(Array.from(view.children).some((child) => child.classList.contains("mf-weather-forecast-header"))).toBe(false);
    expect(card.firstElementChild).toBe(header);
    expect(header.nextElementSibling).toBe(dayPicker);
    expect(Array.from(card.children).indexOf(dayPicker)).toBeLessThan(Array.from(card.children).indexOf(ribbon));
    expect(header.querySelector('time[datetime="2026-09-14"]')?.textContent).toBe("Lunedì 14 set");
    expect(header.querySelector('time[datetime="2026-09-13T12:00:00Z"]')?.textContent).toBe("13/09 · 14:00");
    expect(header.querySelector(".mf-weather-hourly-card__pilot-model")?.textContent).toContain("Modello ICON-2I");
    expect(header.querySelector(".mf-weather-hourly-card__pilot-model")?.getAttribute("aria-label"))
      .toBe("ICON-2I · aggiornamento modello 13/09/2026, 14:00");
    expect((document.body.textContent.match(/Lunedì 14 set/g) || [])).toHaveLength(1);

    const dayButtons = Array.from(dayPicker.querySelectorAll("button"));
    expect(dayButtons.filter((button) => button.getAttribute("aria-pressed") === "true")).toHaveLength(1);
    expect(dayButtons.every((button) => button.type === "button")).toBe(true);

    const hourButtons = Array.from(ribbon.querySelectorAll("button"));
    expect(hourButtons).toHaveLength(2);
    expect(ribbon.getAttribute("data-has-selection")).toBe("false");
    expect(hourButtons.every((button) => button.getAttribute("aria-haspopup") === "dialog")).toBe(true);
    expect(hourButtons.every((button) => button.querySelector("time[datetime]") && button.getAttribute("aria-label"))).toBe(true);
    expect(hourButtons[0].getAttribute("aria-current")).toBe("time");
    expect(hourButtons[1].hasAttribute("aria-current")).toBe(false);
    expect(environment).not.toBeNull();
    expect(environment.querySelectorAll(":scope > .mf-weather-environment-tile")).toHaveLength(4);
    expect(environment.querySelector("dialog")).toBeNull();
  });

  it("keeps future day labels compact without losing their full accessible name", () => {
    pilotHarness.enabled.mockReturnValue(true);
    const model = buildModel();
    const future = {
      ...buildItem(48),
      dateKey: "2026-09-16",
      timestamp: "2026-09-16T00:00:00.000Z",
    };
    model.hourly.items = [model.hourly.items[0], future];
    model.hourly.groups = [
      { dateKey: "2026-09-14", label: "Oggi", items: [model.hourly.items[0]] },
      { dateKey: "2026-09-16", label: "Mercoledì 16 set", items: [future] },
    ];
    model.hourly.summaries.push({
      dateKey: "2026-09-16",
      fullDayMaxTemperature: "24°",
      fullDayMinTemperature: "13°",
      icon: { type: "Sun" },
    });

    const document = renderDocument(model);
    const buttons = document.querySelectorAll(".mf-weather-day-picker button");
    expect(buttons[1].querySelector("strong")?.textContent).toBe("Mer 16 set");
    expect(buttons[1].getAttribute("aria-label")).toBe("Mercoledì 16 set 13° / 24°");
    expect(buttons[1].querySelector("strong")?.getAttribute("title")).toBe("Mercoledì 16 set");
  });

  it("makes every ribbon night explicit while reserving the large moon for clear sky", () => {
    pilotHarness.enabled.mockReturnValue(true);
    const model = buildModel();
    model.hourly.items = [buildItem(0), buildItem(1), buildItem(2), buildItem(3)];
    model.hourly.items[0].icon = { night: true, type: "ClearNight" };
    model.hourly.items[1].icon = { night: true, type: "OvercastNight" };
    model.hourly.items[2].icon = { night: true, type: "Rain" };
    model.hourly.items[3].icon = { night: false, type: "Cloud" };
    const document = renderDocument(model);
    const hourButtons = document.querySelectorAll(".mf-weather-hour-ribbon > button");

    expect(hourButtons).toHaveLength(4);
    expect(document.querySelectorAll('.mf-weather-hour-ribbon__icon-frame[data-phase="night"]')).toHaveLength(3);
    expect(document.querySelectorAll('.mf-weather-hour-ribbon__icon-frame[data-phase="day"]')).toHaveLength(1);
    expect(hourButtons[0].querySelector("svg.mf-weather-hour-ribbon__moon")).not.toBeNull();
    expect(hourButtons[0].querySelector(".mf-home-meteocon-icon")).toBeNull();
    [hourButtons[1], hourButtons[2]].forEach((button) => {
      expect(button.querySelector("svg.mf-weather-hour-ribbon__moon")).toBeNull();
      expect(button.querySelector("svg.mf-weather-hour-ribbon__night-crescent")).not.toBeNull();
      expect(button.querySelector(".mf-home-meteocon-icon")).not.toBeNull();
    });
    expect(hourButtons[3].querySelector("svg.mf-weather-hour-ribbon__moon")).toBeNull();
    expect(hourButtons[3].querySelector("svg.mf-weather-hour-ribbon__night-crescent")).toBeNull();
    expect(hourButtons[3].querySelector(".mf-home-meteocon-icon")).not.toBeNull();
    expect(document.querySelector(".mf-weather-day-picker .mf-weather-hour-ribbon__icon-frame")).toBeNull();
    expect(document.querySelector(".mf-weather-day-picker .mf-weather-hour-ribbon__night-crescent")).toBeNull();
    expect(Array.from(hourButtons).some(button => button.getAttribute("aria-pressed") === "true")).toBe(false);
  });

  it("reserves the precipitation row when the hourly value is absent", () => {
    pilotHarness.enabled.mockReturnValue(true);
    const model = buildModel();
    model.hourly.items[0].details.precipitation = null;
    const document = renderDocument(model);
    const hourButtons = document.querySelectorAll(".mf-weather-hour-ribbon > button");
    const emptyPrecipitation = hourButtons[0].querySelector("small");
    const populatedPrecipitation = hourButtons[1].querySelector("small");

    expect(emptyPrecipitation).not.toBeNull();
    expect(emptyPrecipitation.classList.contains("mf-weather-hour-ribbon__precipitation--empty")).toBe(true);
    expect(emptyPrecipitation.getAttribute("aria-hidden")).toBe("true");
    expect(populatedPrecipitation.textContent).toBe("0 mm");
    expect(populatedPrecipitation.hasAttribute("aria-hidden")).toBe(false);
  });

  it("keeps the ordinary build on its standalone full metadata header and legacy forecast list", () => {
    const document = renderDocument(buildModel());
    const view = document.querySelector(".mf-weather-forecast-view");
    const directHeader = Array.from(view.children).find((child) => child.classList.contains("mf-weather-forecast-header"));
    const card = view.querySelector(".mf-weather-hourly-card");

    expect(view.firstElementChild).toBe(directHeader);
    expect(directHeader.textContent).toContain("Lunedì 14 set");
    expect(directHeader.textContent).toContain("ICON-2I · aggiornamento modello 13/09/2026, 14:00");
    expect(card.querySelector(".mf-weather-hourly-card__pilot-header")).toBeNull();
    expect(card.querySelector(".mf-weather-day-picker")).toBeNull();
    expect(card.querySelector(".mf-weather-hour-ribbon")).toBeNull();
    expect(card.querySelector(".mf-weather-hourly-list")).not.toBeNull();
    expect(view.querySelector(".mf-weather-environment-grid")).toBeNull();
    expect(view.querySelector(".mf-weather-environment")).not.toBeNull();
  });

  it("retains standalone metadata in the pilot when no hourly card can host it", () => {
    pilotHarness.enabled.mockReturnValue(true);
    const document = renderDocument(buildModel({ withHours: false }));
    const view = document.querySelector(".mf-weather-forecast-view");
    const directHeader = Array.from(view.children).find((child) => child.classList.contains("mf-weather-forecast-header"));

    expect(directHeader).not.toBeNull();
    expect(directHeader.textContent).toContain("Lunedì 14 set");
    expect(directHeader.textContent).toContain("ICON-2I · aggiornamento modello 13/09/2026, 14:00");
    expect(view.querySelector(".mf-weather-hourly-card__pilot-header")).toBeNull();
    expect(view.textContent).toContain("Previsioni non disponibili");
  });
});
