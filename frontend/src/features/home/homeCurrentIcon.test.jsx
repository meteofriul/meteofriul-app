import clearDay from "@meteocons/svg/fill/clear-day.svg";
import clearNight from "@meteocons/svg/fill/clear-night.svg";
import rain from "@meteocons/svg/fill/rain.svg";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getHomeStaticViewModel } from "./homeFixture";
import { HomeView } from "./HomeView";

const SOLAR_CONTEXT = {
  latitude: 45.9567,
  longitude: 12.6605,
  sunrise: "2026-08-12T06:02",
  sunset: "2026-08-12T20:21",
  timeZone: "Europe/Rome",
};

function renderHome({
  weather = {},
  bulletin = {},
  officialAlert = null,
  language = "it",
  weatherNow,
} = {}) {
  const model = getHomeStaticViewModel(language);

  return renderToStaticMarkup(
    <HomeView
      language={language}
      model={{
        ...model,
        weather: {
          ...model.weather,
          alertSummary: null,
          solarContext: SOLAR_CONTEXT,
          ...weather,
        },
        bulletin: { ...model.bulletin, ...bulletin },
        officialAlert,
      }}
      onNavigate={() => {}}
      weatherNow={weatherNow}
    />,
  );
}

function getIconMarkup(markup, className) {
  const match = markup.match(
    new RegExp(`<span\\b[^>]*class="${className}(?:\\s[^"]*)?"[^>]*>([\\s\\S]*?)</span>`),
  );

  expect(match, `Expected the ${className} icon container`).not.toBeNull();
  return match[1];
}

function getImageSource(markup) {
  const match = markup.match(/<img\b[^>]*\bsrc="([^"]+)"/);

  expect(match, "Expected the current-weather image").not.toBeNull();
  return match[1]
    .replaceAll("&#x27;", "'")
    .replaceAll("&quot;", '"')
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&amp;", "&");
}

function expectCurrentWeatherIcon(markup, currentAsset) {
  const heroIcon = getIconMarkup(markup, "mf-home-flight-scene__weather-icon");
  expect(getImageSource(heroIcon)).toBe(currentAsset);
  expect(markup).not.toContain("mf-home-bulletin-card__icon--weather");
}

afterEach(() => {
  vi.useRealTimers();
});

describe("Home current-weather icon and bulletin layout", () => {
  it.each([
    {
      name: "daylight corrects a night icon only in the current-weather scene",
      now: "2026-08-12T10:00:00.000Z",
      icon: { type: "ClearNight", night: true },
      phase: "midday",
      asset: clearDay,
    },
    {
      name: "night corrects a day icon only in the current-weather scene",
      now: "2026-08-12T21:00:00.000Z",
      icon: { type: "Sun", night: false },
      phase: "night",
      asset: clearNight,
    },
    {
      name: "the Lab night override affects only the current-weather scene",
      now: "2026-08-12T10:00:00.000Z",
      icon: { type: "Sun", night: false },
      scenePhaseOverride: "night",
      phase: "night",
      asset: clearNight,
    },
    {
      name: "the Lab daylight override affects only the current-weather scene",
      now: "2026-08-12T21:00:00.000Z",
      icon: { type: "ClearNight", night: true },
      scenePhaseOverride: "afternoon",
      phase: "afternoon",
      asset: clearDay,
    },
  ])("$name", ({ now, icon, scenePhaseOverride, phase, asset }) => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(now));

    const markup = renderHome({ weather: { icon, scenePhaseOverride } });

    expect(markup).toContain(`data-day-phase="${phase}"`);
    expectCurrentWeatherIcon(markup, asset);
  });

  it("uses the shared pilot instant for the Home scene instead of the device clock", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-12T10:00:00.000Z"));

    const markup = renderHome({
      weather: { icon: { type: "Sun", night: false } },
      weatherNow: new Date("2026-08-12T21:00:00.000Z"),
    });

    expect(markup).toContain('data-day-phase="night"');
    expectCurrentWeatherIcon(markup, clearNight);
  });

  it.each(["it", "fur"])("keeps current rain separate from the bulletin text in %s", (language) => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-12T10:00:00.000Z"));
    const headline = language === "it" ? "Domani sole e cielo sereno" : "Doman soreli e cîl seren";
    const markup = renderHome({
      language,
      weather: { icon: { type: "Rain" }, weatherVariant: "rain" },
      bulletin: {
        headline,
        body: "Previsione del bollettino, distinta dalle condizioni attuali.",
        icon: { type: "Sun" },
      },
    });

    expect(markup).toContain(headline);
    expectCurrentWeatherIcon(markup, rain);
    expect(markup).toContain("mf-home-bulletin--summary");
  });

  it.each(["yellow", "orange", "red"])("keeps the official %s alert above the current-weather icon", (tone) => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-12T10:00:00.000Z"));
    const markup = renderHome({
      weather: {
        icon: { type: "Rain" },
      },
      officialAlert: {
        action: { anchor: "official-alerts", tab: "bulletin", type: "tab-anchor" },
        isOfficial: true,
        label: `Allerta ${tone}`,
        meta: "Protezione Civile FVG",
        text: "Fenomeno previsto.",
        tone,
        validityLabel: "Valida fino alle 18:00",
      },
    });
    const bulletinIcon = getIconMarkup(markup, "mf-home-bulletin-card__icon");

    expect(getImageSource(getIconMarkup(markup, "mf-home-flight-scene__weather-icon"))).toBe(rain);
    expect(bulletinIcon).toContain("lucide-triangle-alert");
    expect(bulletinIcon).not.toContain("<img");
    expect(bulletinIcon).not.toContain("mf-home-meteocon-icon");
    expect(bulletinIcon).not.toContain("mf-home-bulletin-card__icon--weather");
    expect(markup).toContain(`mf-home-bulletin-card__icon--${tone}`);
    expect(markup).toContain(`Apri nel bollettino: Allerta ${tone}`);
  });
});
