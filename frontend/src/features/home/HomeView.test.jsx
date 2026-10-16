import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getHomeStaticViewModel } from "./homeFixture";
import { HomeView } from "./HomeView";
import { isLocalWeatherPilot } from "../../services/localWeatherPilot";

const experience = vi.hoisted(() => vi.fn(() => false));

vi.mock("../../services/localWeatherPilot", async (importOriginal) => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: experience,
  isLocalWeatherPilot: experience,
}));

afterEach(() => vi.mocked(isLocalWeatherPilot).mockReturnValue(false));

describe("HomeView card style", () => {
  it.each(["it", "fur"])("omits only the duplicate metrics strip in the %s pilot Home", (language) => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    const model = getHomeStaticViewModel(language);
    const markup = renderToStaticMarkup(
      <HomeView language={language} model={{ ...model, weather: { ...model.weather, alertSummary: null } }} />,
    );

    expect(markup).not.toContain("mf-home-local-metrics");
    expect(markup).toContain("mf-home-hero");
    expect(markup).toContain("mf-home-bulletin-card");
    expect(markup.match(/class="mf-home-quick-card /g)).toHaveLength(4);
    expect(markup.indexOf("mf-home-bulletin-card")).toBeGreaterThan(markup.indexOf("mf-home-hero"));
    expect(markup.indexOf("mf-home-bulletin-card")).toBeLessThan(markup.indexOf("mf-home-quick-grid"));
  });

  it("preserves the official-alert card when removing pilot Home metrics", () => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    const markup = renderToStaticMarkup(<HomeView model={{
      ...getHomeStaticViewModel("it"),
      officialAlert: {
        action: { anchor: "official-alerts", tab: "bulletin", type: "tab-anchor" },
        label: "Allerta arancione", tone: "orange", text: "Temporali forti sulla regione.",
      },
    }} onNavigate={() => {}} />);

    expect(markup).not.toContain("mf-home-local-metrics");
    expect(markup).toContain('data-alert-tone="orange"');
    expect(markup).toContain("Apri nel bollettino: Allerta arancione");
    expect(markup.indexOf("mf-home-bulletin-card")).toBeLessThan(markup.indexOf("mf-home-quick-grid"));
  });

  it("keeps stale-data diagnostics out of the definitive Home", () => {
    vi.mocked(isLocalWeatherPilot).mockReturnValue(true);
    const model = getHomeStaticViewModel("it");
    const markup = renderToStaticMarkup(
      <HomeView model={{
        ...model,
        weather: {
          ...model.weather,
          showStatus: true,
          updatedLabel: "Dati non aggiornati",
        },
      }} />,
    );

    expect(markup).not.toContain("mf-home-updated-text");
    expect(markup).not.toContain("Dati non aggiornati");
  });

  it.each(["it", "fur"])("keeps the rejected report shortcut out of the %s Home", (language) => {
    const markup = renderToStaticMarkup(<HomeView language={language} />);

    expect(markup).not.toContain("mf-home-report-link");
    expect(markup).not.toContain("Segnala cosa vedi");
    expect(markup).not.toContain("Segnale ce che tu viodis");
  });

  it("promotes the clean quick grid to the real Home by default", () => {
    const markup = renderToStaticMarkup(<HomeView language="it" />);

    expect(markup).toContain('class="mf-home-view mf-home-card-style"');
    expect(markup).toContain('data-card-style="texture"');
    expect(markup).toContain("mf-home-bulletin-card");
    expect(markup).toContain("mf-home-quick-grid");
    expect(markup.match(/class="mf-home-quick-card /g)).toHaveLength(4);
    expect(markup).not.toContain("mf-home-hourly");
    expect(markup).not.toContain("mf-home-almanac-card");
    expect(markup).not.toContain("mf-home-events-card");
  });

  it.each(["current", "underline", "texture"])(
    "keeps the %s option available to the Lab comparator",
    (cardStyle) => {
      const markup = renderToStaticMarkup(<HomeView cardStyle={cardStyle} language="it" />);

      expect(markup).toContain(`data-card-style="${cardStyle}"`);
    },
  );

  it("previews the first three hours from the same complete forecast timeline", () => {
    const hourlyItems = Array.from({ length: 48 }, (_, index) => ({
      ariaLabel: `Ora ${index}`,
      icon: { type: "Sun" },
      temperature: `${index}°`,
      time: `${String(index % 24).padStart(2, "0")}:00`,
      dayLabel: index < 24 ? "Oggi" : "31/08",
      timestamp: `2026-08-${index < 24 ? "30" : "31"}T${String(index % 24).padStart(2, "0")}:00:00Z`,
    }));
    const markup = renderToStaticMarkup(
      <HomeView
        language="it"
        model={{
          ...getHomeStaticViewModel("it"),
          hourly: {
            items: hourlyItems,
            title: "Prossime 48 ore",
            scrollLabel: "Previsioni orarie",
            sourceLabel: "ICON-2I",
          },
        }}
      />,
    );

    expect(markup).not.toContain("mf-home-hourly");
    expect(markup).toContain(">Evoluzione oraria<");
    expect(markup.match(/class="mf-home-quick-forecast__slot"/g)).toHaveLength(3);
    expect(markup).toContain('aria-label="Ora 0"');
    expect(markup).toContain('aria-label="Ora 1"');
    expect(markup).toContain('aria-label="Ora 2"');
    expect(markup).not.toContain('aria-label="Ora 24"');
  });

  it("places five local metrics below the hero and uses the daily-memory rubric in the quick grid", () => {
    const localMetrics = {
      label: "Dati meteo locali",
      items: [
        { id: "wind", label: "Vento", value: "3", unit: "km/h" },
        { id: "humidity", label: "Umidità", value: "71", unit: "%" },
        { id: "pressure", label: "Press.", value: "1012", unit: "hPa" },
        { id: "precipitation", label: "Pioggia", value: "0", unit: "mm" },
        { id: "pollen", label: "Artemisia", value: "5,06", unit: "grani/m³", tone: "available" },
      ],
    };
    const markup = renderToStaticMarkup(
      <HomeView
        model={{
          ...getHomeStaticViewModel("it"),
          localMetrics,
          territory: {
            anchor: "discover-card-memory-0906",
            heading: "Memoria del giorno",
            metaLabel: "Scienza e territorio · 6 settembre",
            title: "Francesco Maria Franceschinis, matematica e insegnamento",
            text: "Una storia friulana legata alla data di oggi.",
          },
        }}
        language="it"
      />,
    );

    const metricsStart = markup.indexOf('class="mf-home-local-metrics"');
    const quickGridStart = markup.indexOf('class="mf-home-quick-grid"');
    expect(metricsStart).toBeGreaterThan(markup.indexOf("mf-home-hero"));
    expect(metricsStart).toBeLessThan(quickGridStart);
    expect(markup.match(/class="mf-home-local-metric /g)).toHaveLength(5);
    expect(markup).toContain(">Artemisia<");
    expect(markup).toContain(">5,06</strong>");
    expect(markup).toContain(">grani/m³</span>");
    expect(markup).toContain("mf-home-quick-card--territory");
    expect(markup).toContain("Memoria del giorno");
    expect(markup).toContain("Francesco Maria Franceschinis, matematica e insegnamento");
    expect(markup).not.toContain("Pordenone, città del Noncello");
  });

  it("replaces the OSMER summary with a distinct official-alert card in the stable slot", () => {
    const model = getHomeStaticViewModel("it");
    const markup = renderToStaticMarkup(
      <HomeView
        language="it"
        model={{
          ...model,
          bulletin: null,
          officialAlert: {
            action: { anchor: "official-alerts", tab: "bulletin", type: "tab-anchor" },
            label: "Allerta arancione",
            meta: "Protezione Civile FVG",
            text: "Temporali forti sulla regione.",
            tone: "orange",
            validityLabel: "Valida fino alle 18:00 del 6 settembre",
          },
        }}
        onNavigate={() => {}}
      />,
    );

    const metricsStart = markup.indexOf('class="mf-home-local-metrics"');
    const bulletinStart = markup.indexOf("mf-home-bulletin-card");
    expect(bulletinStart).toBeGreaterThan(metricsStart);
    expect(bulletinStart).toBeLessThan(markup.indexOf("mf-home-quick-grid"));
    expect(markup.match(/class="mf-home-bulletin-card /g)).toHaveLength(1);
    expect(markup).toContain('data-alert-tone="orange"');
    expect(markup).toContain("mf-home-bulletin-card__icon--alert");
    expect(markup).toContain(">Allerta arancione</strong>");
    expect(markup).toContain("Protezione Civile FVG");
    expect(markup).toContain("Temporali forti sulla regione.");
    expect(markup).toContain("Valida fino alle 18:00 del 6 settembre");
    expect(markup).toContain("Apri nel bollettino: Allerta arancione");
    expect(markup).not.toContain(model.bulletin.headline);
  });

  it("keeps the regular OSMER summary full-width after metrics and before the quick grid", () => {
    const model = getHomeStaticViewModel("it");
    const markup = renderToStaticMarkup(
      <HomeView
        language="it"
        model={{ ...model, weather: { ...model.weather, alertSummary: null } }}
      />,
    );

    const bulletinStart = markup.indexOf("mf-home-bulletin-card");
    expect(bulletinStart).toBeGreaterThan(markup.indexOf('class="mf-home-local-metrics"'));
    expect(bulletinStart).toBeLessThan(markup.indexOf("mf-home-quick-grid"));
    expect(markup).not.toContain("mf-home-bulletin-card__icon--alert");
    expect(markup).toContain("mf-home-bulletin-card__icon--weather");
    expect(markup).not.toContain("Protezione Civile FVG");
    expect(markup).toMatch(/mf-home-bulletin-card__icon[^>]*><img[^>]*mf-home-meteocon-icon/);
  });

  it("keeps the bulletin slot white in light themes without changing the dark-theme surface", () => {
    const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");
    const lightRule = css.match(/\.mf-home-bulletin \{([^}]+)\}/)?.[1];
    const darkRule = css.match(/html\[data-theme="dark"\] \.mf-home-bulletin \{([^}]+)\}/)?.[1];

    expect(lightRule).toContain("--mf-home-bulletin-card-bg: #ffffff");
    expect(darkRule).toContain("--mf-home-bulletin-card-bg: #18273e");
    expect(darkRule).toContain("--mf-home-bulletin-card-border: rgba(255, 255, 255, 0.08)");
    expect(css).toMatch(/\.mf-home-bulletin-card::before \{\s*display: none;/);
  });

  it("lifts dark Home cards above the app canvas with one quiet light border", () => {
    const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");
    const homeView = css.match(/html\[data-theme="dark"\] \.mf-home-view\s*\{([^}]+)\}/)?.[1] || "";
    const quickCard = css.match(/html\[data-theme="dark"\] \.mf-home-quick-card\s*\{([^}]+)\}/)?.[1] || "";

    expect(homeView).toContain("--mf-neutral-surface: #18273e");
    expect(homeView).toContain("--mf-neutral-border: rgba(255, 255, 255, 0.08)");
    expect(quickCard).toContain("background: #18273e");
    expect(quickCard).toContain("border-color: rgba(255, 255, 255, 0.08)");
  });

  it("uses vivid coordinated squircles for the weather and events quick cards", () => {
    const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");
    const forecastIcon = css.match(/\.mf-home-quick-card--forecast \.mf-home-quick-card__icon\s*\{([^}]+)\}/)?.[1] || "";
    const eventsIcon = css.match(/\.mf-home-quick-card--events \.mf-home-quick-card__icon\s*\{([^}]+)\}/)?.[1] || "";

    expect(forecastIcon).toContain("linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)");
    expect(forecastIcon).toContain("color: #fff");
    expect(eventsIcon).toContain("linear-gradient(135deg, #10b981 0%, #059669 100%)");
    expect(eventsIcon).toContain("color: #fff");
  });

  it("keeps compact quick-card headings on word boundaries", () => {
    const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");
    const heading = css.match(/\.mf-home-quick-card__header h2\s*\{([^}]+)\}/)?.[1] || "";

    expect(heading).toContain("overflow-wrap: normal");
    expect(heading).toContain("word-break: normal");
    expect(heading).not.toContain("overflow-wrap: anywhere");
  });

  it("keeps compact hourly icons vivid without individual tiles in either theme", () => {
    const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");
    const surface = css.match(/\.mf-home-quick-forecast__icon-surface\s*\{([^}]+)\}/)?.[1] || "";
    const nightSurface = css.match(/\.mf-home-quick-forecast__icon-surface\[data-phase="night"\]\s*\{([^}]+)\}/)?.[1] || "";
    const asset = css.match(/\.mf-home-quick-forecast__icon-surface \.mf-home-meteocon-icon\s*\{([^}]+)\}/)?.[1] || "";
    const darkSurface = css.match(/html\[data-theme="dark"\] \.mf-home-quick-forecast__icon-surface\s*\{([^}]+)\}/)?.[1] || "";

    expect(surface).toContain("background: transparent");
    expect(surface).toContain("border: 0");
    expect(surface).toContain("box-shadow: none");
    expect(surface).toContain("overflow: visible");
    expect(surface).toContain("height: 40px");
    expect(surface).toContain("width: 40px");
    expect(nightSurface).toContain("background: transparent");
    expect(nightSurface).toContain("box-shadow: none");
    expect(asset).toContain("height: 44px");
    expect(asset).toContain("saturate(1.18)");
    expect(darkSurface).toContain("background: transparent");
    expect(darkSurface).toContain("box-shadow: none");
  });

  it("lifts the summary weather asset with a scoped vivid surface in both themes", () => {
    const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");
    const weatherIcon = css.match(/\.mf-home-bulletin-card__icon--weather\s*\{([^}]+)\}/)?.[1] || "";
    const weatherAsset = css.match(/\.mf-home-bulletin-card__icon--weather \.mf-home-meteocon-icon\s*\{([^}]+)\}/)?.[1] || "";
    const darkWeatherIcon = css.match(/html\[data-theme="dark"\] \.mf-home-bulletin-card__icon--weather\s*\{([^}]+)\}/)?.[1] || "";

    expect(weatherIcon).toContain("linear-gradient(135deg, #38bdf8 0%, #0284c7 62%, #0369a1 100%)");
    expect(weatherIcon).toContain("border-color: rgba(255, 255, 255, 0.36)");
    expect(weatherAsset).toContain("drop-shadow(0 4px 7px rgba(3, 55, 88, 0.32))");
    expect(weatherAsset).toContain("transform: scale(1.08)");
    expect(darkWeatherIcon).toContain("linear-gradient(135deg, #0ea5e9 0%, #0369a1 62%, #0f3f6a 100%)");
  });

  it("keeps the event count neutral while the green remains on the icon", () => {
    const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");
    const count = css.match(/\.mf-home-quick-events__count strong\s*\{([^}]+)\}/)?.[1] || "";
    const caption = css.match(/\.mf-home-quick-events__count span\s*\{([^}]+)\}/)?.[1] || "";

    expect(count).toContain("color: var(--mf-ink)");
    expect(count).not.toContain("var(--mf-home-quick-accent)");
    expect(caption).toContain("color: var(--mf-muted)");
    expect(caption).toContain("font-size: var(--mf-text-xs)");
    expect(caption).toContain("font-weight: 600");
  });

  it("uses a fixed top-centered poster banner without changing quick-card geometry", () => {
    const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");
    const eventCard = css.match(/\.mf-home-quick-card--events\s*\{([^}]+)\}/)?.[1] || "";
    const grid = css.match(/\.mf-home-quick-grid\s*\{([^}]+)\}/)?.[1] || "";
    const banner = css.match(/\.mf-home-quick-events__banner\s*\{([^}]+)\}/)?.[1] || "";
    const image = css.match(/\.mf-home-quick-events__banner > img\s*\{([^}]+)\}/)?.[1] || "";

    expect(eventCard).toContain("gap: 8px");
    expect(grid).toContain("align-items: stretch");
    expect(banner).toContain("flex: 0 0 64px");
    expect(banner).toContain("height: 64px");
    expect(banner).toContain("border-radius: 10px");
    expect(image).toContain("object-fit: cover");
    expect(image).toContain("object-position: 50% 24%");
    expect(css).not.toContain(".mf-home-quick-events__count--overlay");
  });

  it("does not render a decorative segmented bar above the Home weather hero", () => {
    const css = readFileSync(new URL("./home.css", import.meta.url), "utf8");

    expect(css).not.toContain(".mf-home-hero::before");
  });
});
