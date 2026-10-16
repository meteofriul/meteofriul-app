import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

const routeFixtures = vi.hoisted(() => ({
  bulletinData: undefined,
  homeData: undefined,
  nationalAlertsData: undefined,
}));

vi.mock("../features/bulletin/bulletinDataController", async (importOriginal) => {
  const actual = await importOriginal();

  return {
    ...actual,
    readInitialBulletinData: (...args) => (
      routeFixtures.bulletinData === undefined
        ? actual.readInitialBulletinData(...args)
        : routeFixtures.bulletinData
    ),
  };
});

vi.mock("../features/home/homeDataController", async (importOriginal) => {
  const actual = await importOriginal();

  return {
    ...actual,
    readInitialHomeData: (...args) => (
      routeFixtures.homeData === undefined
        ? actual.readInitialHomeData(...args)
        : routeFixtures.homeData
    ),
  };
});

vi.mock("../features/bulletin/nationalOfficialAlertsDataController", async (importOriginal) => {
  const actual = await importOriginal();

  return {
    ...actual,
    readInitialNationalOfficialAlerts: (...args) => (
      routeFixtures.nationalAlertsData === undefined
        ? actual.readInitialNationalOfficialAlerts(...args)
        : routeFixtures.nationalAlertsData
    ),
  };
});

import { AppRoutes } from "./AppRoutes";
import { resolveWeatherRouteNow } from "./weatherRouteClock";

afterEach(() => {
  routeFixtures.bulletinData = undefined;
  routeFixtures.homeData = undefined;
  routeFixtures.nationalAlertsData = undefined;
});

describe("AppRoutes shared weather clock", () => {
  it("uses the declared pilot instant only for weather presentation", () => {
    const deviceNow = new Date("2026-09-06T01:10:00+02:00");
    const laterDeviceNow = new Date("2026-09-06T02:10:00+02:00");
    const pilotNow = "2026-09-04T21:00:00Z";

    expect(resolveWeatherRouteNow(deviceNow, pilotNow))
      .toEqual(new Date("2026-09-04T21:00:00Z"));
    expect(resolveWeatherRouteNow(laterDeviceNow, pilotNow))
      .toEqual(resolveWeatherRouteNow(deviceNow, pilotNow));
    expect(resolveWeatherRouteNow(deviceNow)).toBe(deviceNow);
  });
});

describe("AppRoutes settings location controls", () => {
  it("forwards the installed release identity to Settings without substituting the Web version", () => {
    const html = renderToStaticMarkup(
      <AppRoutes
        activeTab="settings"
        appVersion={{ platform: "android", version: "1.0.1+300012" }}
        copy={{ placeholders: {} }}
        language="it"
      />,
    );

    expect(html).toMatch(/<footer[^>]*class="mf-settings-version"[^>]*>1\.0\.1<\/footer>/);
    expect(html).not.toContain("300012");
  });

  it("forwards automatic mode with the approved compact position copy", () => {
    const html = renderToStaticMarkup(
      <AppRoutes
        activeLocation={{ city: "Pordenone", source: "browser_geolocation" }}
        activeTab="settings"
        autoLocationEnabled
        copy={{ placeholders: {} }}
        deviceLocationStatus={{ status: "success", city: "Pordenone" }}
        language="it"
        onAutomaticLocationChange={vi.fn()}
      />,
    );

    expect(html).toContain('aria-label="Disattiva Posizione"');
    expect(html).toContain(">Attiva<");
    expect(html).not.toContain("Automatica: Pordenone");
    expect(html).not.toContain('aria-label="Aggiorna posizione"');
  });
});

const routeCopy = {
  placeholders: {
    almanacBody: "",
    almanacTitle: "Almanacco",
    bulletinTitle: "Bollettino",
    homeTitle: "Home",
    liveTitle: "Live",
    weatherTitle: "Meteo",
  },
};

const activeOfficialAlert = {
  action: { anchor: "official-alerts", tab: "bulletin", type: "tab-anchor" },
  label: "Allerta arancione",
  meta: "Protezione Civile FVG",
  paragraphs: [
    "Temporali forti e criticita idrogeologica su tutta la regione.",
    "Seguire gli aggiornamenti della Protezione Civile FVG.",
  ],
  text: "Temporali forti e criticita idrogeologica su tutta la regione.",
  tone: "orange",
  validityLabel: "Valida fino alle 23:59",
};

const legacyOfficialAlerts = {
  active: true,
  alerts: [
    {
      id: "legacy-yellow",
      level: "gialla",
      official_text: "ALLERTA GIALLA LEGACY PER TEMPORALI SU TUTTA LA REGIONE",
      valid_to: "2099-09-06T23:59:00+02:00",
    },
  ],
  source_mode: "github_actions_official_page",
};

const legacyBulletinData = {
  city: "Pordenone",
  error: null,
  forecast: {
    official: {
      it: {
        forecasts: [
          {
            date: "2099-09-06",
            date_label: "domenica 6 settembre",
            text: "Bollettino OSMER legacy.",
          },
        ],
      },
    },
  },
  fromCache: true,
  isStale: false,
  officialAlerts: legacyOfficialAlerts,
  osmerAudit: null,
  status: "cache",
  updatedAt: "2026-09-06T06:00:00Z",
};

const legacyHomeData = {
  events: {
    error: null,
    fromCache: true,
    isPartial: false,
    isRefreshing: false,
    items: [],
    loadedLimit: 0,
    retry: 0,
    shouldRetry: false,
    status: "cache",
    total: 0,
  },
  location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
  ok: true,
  weather: {
    city: "Pordenone",
    current: null,
    error: null,
    forecast: null,
    fromCache: true,
    isStale: false,
    officialAlerts: legacyOfficialAlerts,
    osmerAudit: null,
    rawCurrent: null,
    status: "empty",
    updatedAt: "2026-09-06T06:00:00Z",
  },
};

function renderWeatherRoute(activeTab, props = {}) {
  return renderToStaticMarkup(
    <AppRoutes
      activeLocation={{
        city: "Pordenone",
        countryCode: "IT",
        lat: 45.9567,
        lon: 12.6605,
        regionCode: "IT-36",
      }}
      activeTab={activeTab}
      copy={routeCopy}
      language="it"
      onNavigate={vi.fn()}
      {...props}
    />,
  );
}

function getWeatherNavigation(markup) {
  return markup.match(/<nav aria-label="Sezioni meteo"[\s\S]*?<\/nav>/)?.[0] || "";
}

describe("AppRoutes weather section navigation", () => {
  it("keeps Roma weather unavailable until national ICON-2I is ready", () => {
    const activeLocation = {
      city: "Roma",
      countryCode: "IT",
      region: "Lazio",
      regionCode: "IT-62",
      lat: 41.9028,
      lon: 12.4964,
    };

    const markup = renderWeatherRoute("weather", { activeLocation });

    expect(markup).toContain("Previsioni nazionali in preparazione");
    expect(markup).toContain("Non usiamo Open-Meteo come ripiego");
    expect(markup).not.toContain("Modello ICON-2I");
  });

  it("does not rehydrate cached Open-Meteo data on the Roma Home", () => {
    const activeLocation = {
      city: "Roma",
      countryCode: "IT",
      region: "Lazio",
      regionCode: "IT-62",
      lat: 41.9028,
      lon: 12.4964,
    };
    routeFixtures.homeData = {
      ...legacyHomeData,
      location: activeLocation,
      weather: {
        ...legacyHomeData.weather,
        city: "Roma",
        current: { primary_source: "open_meteo", temperature: 27, weathercode: 0 },
        status: "cache",
      },
    };

    const markup = renderWeatherRoute("home", { activeLocation });

    expect(markup).toContain("Previsioni nazionali in preparazione");
    expect(markup).not.toContain(">27<");
  });

  it("routes an exact Italian municipality to national DPC alerts outside FVG", () => {
    const activeLocation = {
      city: "Roma",
      countryCode: "IT",
      istatCode: "058091",
      region: "Lazio",
      lat: 41.9028,
      lon: 12.4964,
    };
    routeFixtures.bulletinData = legacyBulletinData;

    const markup = renderWeatherRoute("bulletin", {
      activeLocation,
    });

    expect(markup).toContain("Verifica delle allerte in corso");
    expect(markup).not.toContain("Allerte nazionali in preparazione");
    expect(markup).not.toContain("Bollettino OSMER legacy");
  });

  it("shows a verified local DPC alert on national Home but never for a different municipality", () => {
    const urbino = {
      city: "Urbino",
      countryCode: "IT",
      municipality: { istatCode: "041067", name: "Urbino" },
      regionCode: "IT-57",
    };
    routeFixtures.nationalAlertsData = {
      data: {
        active: true,
        complete: true,
        contract: "meteofriul.official_alerts.location.v1",
        expires_at: "2099-09-27T23:59:59+02:00",
        municipality: { istat: "041067", name: "Urbino" },
        records: [{
          forecast_day: "2099-09-26",
          level: "yellow",
          risk: "thunderstorm",
          transmission_status: "transmitted",
          valid_to: "2099-09-27T23:59:59+02:00",
        }],
        schema_version: 1,
        standalone_display_allowed: true,
        zones: ["DPC:Marc-2"],
      },
    };

    const urbinoHome = renderWeatherRoute("home", { activeLocation: urbino });
    const romaHome = renderWeatherRoute("home", {
      activeLocation: {
        city: "Roma",
        countryCode: "IT",
        municipality: { istatCode: "058091", name: "Roma" },
        regionCode: "IT-62",
      },
    });
    const fvgHome = renderWeatherRoute("home");

    expect(urbinoHome).toContain("Allerta gialla");
    expect(urbinoHome).toContain("Urbino: temporali");
    expect(urbinoHome).toContain("Dipartimento della Protezione Civile");
    expect(romaHome).not.toContain("Allerta gialla");
    expect(romaHome).not.toContain("Urbino: temporali");
    expect(fvgHome).not.toContain("Urbino: temporali");
  });

  it("does not present planned Italian alerts for a foreign location", () => {
    const markup = renderWeatherRoute("bulletin", {
      activeLocation: {
        city: "Lubiana",
        countryCode: "SI",
        region: "Osrednjeslovenska",
        regionCode: "SI-061",
        lat: 46.0569,
        lon: 14.5058,
      },
    });

    expect(markup).toContain("Località fuori copertura");
    expect(markup).toContain("Le allerte italiane non vengono richieste");
    expect(markup).not.toContain("Allerte nazionali in preparazione");
  });

  it("keeps FVG on the existing regional bulletin branch", () => {
    routeFixtures.bulletinData = legacyBulletinData;
    const markup = renderWeatherRoute("bulletin", {
      activeLocation: {
        city: "Pordenone",
        countryCode: "IT",
        istatCode: "093033",
        regionCode: "IT-36",
      },
    });

    expect(markup).toContain("Bollettino OSMER legacy");
    expect(markup).not.toContain("mf-national-alerts");
    expect(markup).not.toContain("Verifica delle allerte in corso");
  });

  it("hides the FVG event catalogue when the active weather location is outside FVG", () => {
    const activeLocation = {
      city: "Urbino",
      countryCode: "IT",
      region: "Marche",
      regionCode: "IT-57",
      lat: 43.7262,
      lon: 12.6363,
    };
    const markup = renderWeatherRoute("events", {
      activeLocation,
      editorialContext: {
        focusLocation: {
          city: "Pordenone",
          countryCode: "IT",
          region: "Friuli Venezia Giulia",
          regionCode: "IT-36",
        },
      },
    });

    expect(markup).toContain("Eventi disponibili solo in FVG");
    expect(markup).toContain("La località attiva è Urbino");
    expect(markup).not.toContain(">Pordenone<");
    expect(markup).not.toContain("mf-events-filters");
    expect(markup).not.toContain("mf-events-card");
  });

  it("does not delay an accepted community vote while refreshing the public feed", () => {
    const source = readFileSync(new URL("./AppRoutes.jsx", import.meta.url), "utf8");

    expect(source).toContain(
      "void loadAndCommitLiveData({ forceCommunity: true }).catch(() => undefined);",
    );
    expect(source).not.toContain(
      "await loadAndCommitLiveData({ forceCommunity: true });",
    );
  });

  it("guards radar and community reads with the resolved territory capabilities", () => {
    const source = readFileSync(new URL("./AppRoutes.jsx", import.meta.url), "utf8");

    expect(source).toContain(
      "const communityEnabled = communityReadable && !communityReportInteractive;",
    );
    expect(source).toContain("if (radarEnabled) {");
    expect(source).toContain("enabled: radarEnabled");
  });

  it("enables the compact Territorio layout only through the local-pilot guard", () => {
    const source = readFileSync(new URL("./AppRoutes.jsx", import.meta.url), "utf8");

    expect(source).toContain("compactLayout={isDefinitiveAppExperience()}");
  });

  it("shows the weather sub-navigation and a localized loading state on Forecasts", () => {
    const markup = renderWeatherRoute("weather");
    const navigation = getWeatherNavigation(markup);

    expect(navigation).toMatch(/<button[^>]*aria-current="page"[^>]*>Previsioni<\/button>/);
    expect(markup).toContain('class="mf-tab-page mf-tab-page--weather"');
    expect(markup).toContain("Dati meteo in arrivo");
    expect(markup).toContain("Mostreremo le previsioni appena il dato verificato sarà disponibile.");
  });

  it.each([
    ["bulletin", "Bollettino"],
    ["live", "Tempo reale"],
  ])("marks %s as the active weather section", (activeTab, label) => {
    const navigation = getWeatherNavigation(renderWeatherRoute(activeTab));

    expect(navigation).toMatch(
      new RegExp(`<button[^>]*aria-current="page"[^>]*>${label}<\\/button>`),
    );
  });

  it("disables all three weather section controls while report submission locks navigation", () => {
    const navigation = getWeatherNavigation(
      renderWeatherRoute("live", { reportSubmissionLocked: true }),
    );

    expect(navigation.match(/disabled=""/g)).toHaveLength(3);
  });
});

describe("AppRoutes official alert hierarchy", () => {
  it("starts the Home advice slot in pending state without exposing OSMER detail", () => {
    routeFixtures.bulletinData = {
      ...legacyBulletinData,
      forecast: {
        official: {
          it: {
            forecasts: [{
              date: "2099-09-06",
              date_label: "domenica 6 settembre",
              text: "Cielo variabile. Dettaglio OSMER da mostrare solo se ICON non è disponibile.",
            }],
          },
        },
      },
      officialAlerts: null,
    };
    routeFixtures.homeData = legacyHomeData;

    const markup = renderWeatherRoute("home", { officialAlert: null });

    expect(markup).toContain('data-advice-status="pending"');
    expect(markup).not.toContain("Dettaglio OSMER da mostrare");
  });

  it("uses the independent active alert instead of the Home bulletin card", () => {
    const markup = renderWeatherRoute("home", { officialAlert: activeOfficialAlert });

    expect(markup).toContain('class="mf-home-section mf-home-bulletin mf-home-official-alert"');
    expect(markup).toContain("Allerta arancione");
    expect(markup).toContain("Valida fino alle 23:59");
    expect(markup).not.toContain('aria-labelledby="home-bulletin-title"');
  });

  it.each(["weather", "live"])(
    "shows the active alert as a compact bulletin link in %s",
    (activeTab) => {
      const markup = renderWeatherRoute(activeTab, { officialAlert: activeOfficialAlert });

      expect(markup).toContain('class="mf-official-alert-compact"');
      expect(markup).toContain('data-alert-tone="orange"');
      expect(markup).toContain("Allerta arancione");
      expect(markup).toContain("Apri nel bollettino");
      expect(markup).not.toContain('class="mf-bulletin-alert"');
    },
  );

  it("renders the independently supplied alert as full content in Bulletin", () => {
    const markup = renderWeatherRoute("bulletin", { officialAlert: activeOfficialAlert });

    expect(markup).toContain('class="mf-bulletin-alert"');
    expect(markup).toContain('id="official-alerts"');
    expect(markup).toContain("Allerta arancione");
    expect(markup).toContain("Temporali forti e criticita idrogeologica su tutta la regione.");
    expect(markup).toContain("Seguire gli aggiornamenti della Protezione Civile FVG.");
    expect(markup).not.toContain('class="mf-official-alert-compact"');
  });

  it("shows no alert card or manual-check prompt for an unverified alert response", () => {
    const markup = renderWeatherRoute("bulletin", {
      officialAlert: null,
      officialAlertsRuntime: {
        active: false,
        payload: [],
        status: "unavailable",
      },
    });

    expect(markup).not.toContain("Controlla le allerte ufficiali");
    expect(markup).not.toContain("Apri il sito ufficiale");
    expect(markup).not.toContain('id="official-alerts"');
    expect(markup).not.toContain("non disponibile");
    expect(markup).not.toContain("Nessuna allerta");
    expect(markup).not.toContain('class="mf-bulletin-alert"');
  });

  it.each(["weather", "live"])(
    "does not reserve compact alert UI in %s when there is no active alert",
    (activeTab) => {
      const markup = renderWeatherRoute(activeTab, { officialAlert: null });

      expect(markup).not.toContain('class="mf-official-alert-compact"');
    },
  );

  it.each([
    ["home", 'class="mf-home-section mf-home-bulletin mf-home-official-alert"'],
    ["bulletin", 'class="mf-bulletin-alert"'],
  ])(
    "treats explicit null as authoritative inactivity in %s while preserving omitted-prop compatibility",
    (activeTab, alertMarker) => {
      routeFixtures.bulletinData = legacyBulletinData;
      routeFixtures.homeData = legacyHomeData;

      const compatibleMarkup = renderWeatherRoute(activeTab);
      const inactiveMarkup = renderWeatherRoute(activeTab, { officialAlert: null });

      expect(compatibleMarkup).toContain(alertMarker);
      expect(compatibleMarkup).toContain("Allerta gialla");
      expect(inactiveMarkup).not.toContain(alertMarker);
      expect(inactiveMarkup).not.toContain("ALLERTA GIALLA LEGACY");
    },
  );
});
