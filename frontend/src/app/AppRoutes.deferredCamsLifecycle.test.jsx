// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const testState = vi.hoisted(() => {
  const weather = (run, camsStatus, diagnostic = null) => ({
    city: "Pordenone",
    current: { condition: "Sereno", temperature: 20, weathercode: 0 },
    error: null,
    forecast: { daily: [], days: [], hourly: [] },
    fromCache: false,
    isStale: false,
    rawCurrent: {
      air_quality_data: camsStatus === "available" ? { values: { ozone: 1 } } : null,
      data_quality: {
        cams_diagnostic: diagnostic,
        cams_run_utc: run,
        cams_status: camsStatus === "available" ? "fresh" : "unavailable",
        status: "fresh",
      },
      pollen_data: camsStatus === "available" ? { values: { ambrosia: 1 } } : null,
      source: {
        cams: { status: camsStatus },
        icon: { status: "available" },
      },
    },
    status: "fresh",
    updatedAt: "2026-09-14T18:00:00Z",
  });

  return {
    active: weather("2026-09-13T00:00:00Z", "available"),
    events: {
      error: null,
      fromCache: false,
      isPartial: false,
      isRefreshing: false,
      items: [],
      status: "fresh",
      total: 0,
    },
    final: weather("2026-09-14T00:00:00Z", "available"),
    refreshOptions: [],
    revoked: weather("2026-09-13T00:00:00Z", "unavailable", {
      code: "RUN_DISABLED",
      stage: "family",
    }),
  };
});

vi.mock("../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(),
  getLocalWeatherPilotTestNow: () => null,
  isDefinitiveAppExperience: () => true,
  isLocalWeatherPilot: () => true,
}));

vi.mock("../features/home/homeDataController", async importOriginal => {
  const actual = await importOriginal();
  return {
    ...actual,
    hydrateHomeWeatherFromBackgroundPrefetch: () => Promise.resolve(null),
    loadHomeEvents: () => Promise.resolve(testState.events),
    loadHomeWeather: (_location, options = {}) => {
      if (!options.force) return Promise.resolve(testState.active);
      testState.refreshOptions.push(options);
      options.onCamsUpdate?.(testState.revoked, {
        lifecycle: "intermediate",
        reason: "revocation",
      });
      return Promise.resolve(testState.revoked);
    },
    readInitialHomeData: location => ({
      events: testState.events,
      location,
      ok: true,
      weather: testState.active,
    }),
  };
});

vi.mock("../features/bulletin/bulletinDataController", async importOriginal => ({
  ...await importOriginal(),
  loadBulletinData: () => Promise.resolve({ status: "fresh" }),
  readInitialBulletinData: () => null,
}));
vi.mock("../features/bulletin/bulletinViewModel", () => ({
  buildBulletinViewModel: () => ({ alert: null, days: [], status: "unavailable" }),
}));
vi.mock("../features/bulletin/bulletinLocalViewModel", () => ({
  buildBulletinLocalViewModel: () => null,
}));
vi.mock("../features/almanac/almanacViewModel", () => ({
  buildAlmanacViewModel: () => ({}),
}));
vi.mock("../features/discover/discoverViewModel", () => ({
  buildDiscoverViewModel: () => ({}),
}));
vi.mock("../features/home/homeDiscoverPreview", () => ({
  selectHomeDiscoverPreview: () => null,
}));
vi.mock("../features/home/homeDayPhase", () => ({
  subscribeToHomeSolarClock: () => () => {},
}));
vi.mock("../features/home/homeViewModel", () => ({
  buildHomeAlmanacStateFromModel: () => null,
  buildHomeViewModel: data => data,
}));
vi.mock("../features/weather/weatherForecastViewModel", () => ({
  buildWeatherForecastViewModel: state => state,
}));
vi.mock("../features/home/HomeView", () => ({
  HomeView: ({ model }) => (
    <div data-testid="cams-presentation">
      {model?.weather?.rawCurrent?.data_quality?.cams_diagnostic?.code ||
        model?.weather?.rawCurrent?.data_quality?.cams_run_utc || "empty"}
    </div>
  ),
}));
vi.mock("../features/weather/WeatherForecastView", () => ({
  WeatherForecastView: ({ model }) => (
    <div data-testid="cams-presentation">
      {model?.rawCurrent?.data_quality?.cams_diagnostic?.code ||
        model?.rawCurrent?.data_quality?.cams_run_utc || "empty"}
    </div>
  ),
}));

import { AppRoutes } from "./AppRoutes";

const LOCATION = {
  city: "Pordenone",
  municipality: { istatCode: "093033", name: "Pordenone" },
  source: "manual",
};
const COPY = {
  placeholders: {
    almanacBody: "",
    almanacTitle: "",
    homeTitle: "Home",
    weatherTitle: "Meteo",
  },
};

describe.each(["home", "weather"])("deferred CAMS lifecycle on %s", activeTab => {
  let container;
  let root;
  let settled;

  beforeEach(() => {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    testState.refreshOptions = [];
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    settled = vi.fn();
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  });

  function render(token) {
    root.render(
      <AppRoutes
        activeLocation={LOCATION}
        activeTab={activeTab}
        copy={COPY}
        labEnabled={false}
        language="it"
        onRuntimeRefreshSettled={settled}
        runtimeRefreshForce={true}
        runtimeRefreshToken={token}
      />,
    );
  }

  it("presents a revocation immediately but stays pending until the terminal replacement", async () => {
    await act(async () => {
      render(0);
      await Promise.resolve();
    });
    settled.mockClear();

    await act(async () => {
      render(1);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.querySelector('[data-testid="cams-presentation"]').textContent)
      .toBe("RUN_DISABLED");
    expect(settled.mock.calls.some(([, outcome]) => outcome.complete === true)).toBe(false);
    expect(settled.mock.calls.some(([, outcome]) => (
      outcome.complete === false && outcome.components?.cams === "pending"
    ))).toBe(true);

    const refreshOptions = testState.refreshOptions.at(-1);
    expect(refreshOptions).toBeDefined();
    await act(async () => {
      refreshOptions.onCamsUpdate(testState.final, { lifecycle: "final" });
      await Promise.resolve();
    });

    expect(container.querySelector('[data-testid="cams-presentation"]').textContent)
      .toBe("2026-09-14T00:00:00Z");
    const terminal = settled.mock.calls.find(([, outcome]) => outcome.complete === true)?.[1];
    expect(terminal).toMatchObject({
      components: { cams: "settled", icon: "settled" },
      ok: true,
    });
  });
});
