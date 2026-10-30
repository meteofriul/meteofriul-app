// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  weather: { status: "fresh", current: null, forecast: null },
  events: { status: "fresh", items: [], total: 0, loadedLimit: 100 },
  loadWeather: vi.fn(),
  loadEvents: vi.fn(),
  loadHomeEvents: vi.fn(),
  loadLive: vi.fn(),
  buildAlmanac: vi.fn(),
  buildDiscover: vi.fn(),
}));

vi.mock("../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(), isDefinitiveAppExperience: () => true, isLocalWeatherPilot: () => true,
  getLocalWeatherPilotTestNow: () => null,
}));
vi.mock("../features/home/homeDataController", async importOriginal => ({
  ...await importOriginal(),
  hydrateHomeWeatherFromBackgroundPrefetch: async () => null,
  readInitialHomeData: () => null,
  loadHomeWeather: (...args) => state.loadWeather(...args),
  loadHomeEvents: (...args) => state.loadHomeEvents(...args),
}));
vi.mock("../features/events/eventsDataController", async importOriginal => ({
  ...await importOriginal(),
  readInitialEventsData: () => null,
  loadEventsData: (...args) => state.loadEvents(...args),
}));
// Market refreshes have their own integration coverage; keep this fixture
// focused on ownership of the weather/live/events runtime refresh token.
vi.mock("../features/markets/useMarketsCatalogue", async () => {
  const { MARKET_CATALOGUE } = await import("../features/markets/marketsCatalog");
  return { useMarketsCatalogue: () => ({ catalogue: MARKET_CATALOGUE, status: "bootstrap" }) };
});
vi.mock("../features/live/liveDataController", async importOriginal => ({
  ...await importOriginal(),
  readInitialLiveData: () => null,
  loadLiveData: (...args) => state.loadLive(...args),
}));
vi.mock("../features/home/HomeView", () => ({ HomeView: () => <div>Home</div> }));
vi.mock("../features/events/EventsView", () => ({ EventsView: () => <div>Events</div> }));
vi.mock("../features/live/LiveView", () => ({ LiveView: ({ model }) => (
  <div data-webcam-update>{model.webcams.sourceUpdatedAt}</div>
) }));
vi.mock("../features/weather/WeatherForecastView", () => ({ WeatherForecastView: () => <div>Weather</div> }));
vi.mock("../features/almanac/almanacViewModel", async importOriginal => {
  const actual = await importOriginal();
  return { ...actual, buildAlmanacViewModel: (...args) => {
    state.buildAlmanac(...args);
    return actual.buildAlmanacViewModel(...args);
  } };
});
vi.mock("../features/discover/discoverViewModel", async importOriginal => {
  const actual = await importOriginal();
  return { ...actual, buildDiscoverViewModel: (...args) => {
    state.buildDiscover(...args);
    return actual.buildDiscoverViewModel(...args);
  } };
});

import { AppRoutes } from "./AppRoutes";

const location = { city: "Pordenone", lat: 45.9567, lon: 12.6605,
  municipality: { name: "Pordenone", istatCode: "093033" } };
const secondLocation = { city: "Udine", lat: 46.0633, lon: 13.2357,
  municipality: { name: "Udine", istatCode: "030129" } };
const editorialContext = { focusLocation: location };
const productScope = {
  community: { read: true, write: false },
  sources: { forecast: { status: "enabled" }, osmer: { status: "disabled" },
    radar: { status: "disabled" }, webcams: { status: "enabled" } },
};
const settled = vi.fn();
let root;
let container;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Unexpected network request"); }));
  window.localStorage.clear();
  settled.mockReset();
  state.buildAlmanac.mockClear();
  state.buildDiscover.mockClear();
  state.loadWeather.mockReset().mockImplementation(async (_location, options = {}) => {
    options.onCamsFailure?.(new Error("No supplemental data in this fixture"));
    return state.weather;
  });
  state.loadEvents.mockReset().mockResolvedValue(state.events);
  state.loadHomeEvents.mockReset().mockResolvedValue(state.events);
  state.loadLive.mockReset().mockResolvedValue({ status: "ready", items: [],
    community: { status: "fresh", payload: { reports: [], map_groups: [] } },
    webcams: { status: "fresh", payload: { ok: true, webcams: [] } },
  });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function render(
  tab,
  token = 0,
  activeLocation = location,
  force = true,
  scope = productScope,
) {
  await act(async () => {
    root.render(<AppRoutes activeTab={tab} activeLocation={activeLocation}
      editorialContext={editorialContext} language="it" productScope={scope}
      copy={{ placeholders: { homeTitle: "Home", weatherTitle: "Weather" } }}
      runtimeRefreshToken={token} runtimeRefreshForce={force}
      onRuntimeRefreshSettled={settled} />);
  });
}

describe("refresh ownership across route navigation", () => {
  it("does not load or replay FVG events while the active location is outside FVG", async () => {
    const urbino = {
      city: "Urbino",
      countryCode: "IT",
      lat: 43.7263,
      lon: 12.6363,
      region: "Marche",
      regionCode: "IT-57",
    };
    const outsideFvgScope = {
      ...productScope,
      sources: {
        ...productScope.sources,
        events: { status: "unsupported" },
      },
    };
    const fvgScope = {
      ...productScope,
      sources: {
        ...productScope.sources,
        events: { status: "enabled" },
      },
    };

    await render("events", 0, urbino, true, outsideFvgScope);
    expect(container.textContent).toContain("Eventi disponibili solo in FVG");
    expect(container.textContent).toContain("La località attiva è Urbino");
    expect(container.textContent).not.toContain("Pordenone");
    expect(state.loadEvents).not.toHaveBeenCalled();

    await render("events", 9, urbino, true, outsideFvgScope);
    expect(state.loadEvents).not.toHaveBeenCalled();
    expect(settled).toHaveBeenCalledWith(9, expect.objectContaining({
      complete: true,
      components: ["events"],
    }));

    await render("events", 9, location, true, fvgScope);
    expect(container.textContent).toContain("Events");
    expect(state.loadEvents).toHaveBeenCalledTimes(1);
  });

  it("does not request Home events while the active location is outside FVG", async () => {
    const urbino = {
      city: "Urbino",
      countryCode: "IT",
      lat: 43.7263,
      lon: 12.6363,
      region: "Marche",
      regionCode: "IT-57",
    };
    const outsideFvgScope = {
      ...productScope,
      sources: {
        ...productScope.sources,
        events: { status: "unsupported" },
      },
    };

    await render("home", 0, urbino, true, outsideFvgScope);
    expect(state.loadHomeEvents).not.toHaveBeenCalled();
  });

  it("loads Events for the active FVG location instead of the editorial focus", async () => {
    await render("events", 0, secondLocation);

    expect(state.loadEvents).toHaveBeenCalledTimes(1);
    expect(state.loadEvents).toHaveBeenCalledWith(expect.objectContaining({
      city: "Udine",
      eventsRadius: 20,
      lat: secondLocation.lat,
      lon: secondLocation.lon,
    }));
  });

  it("loads the Home events teaser for the active FVG location", async () => {
    await render("home", 0, secondLocation);

    expect(state.loadHomeEvents).toHaveBeenCalledTimes(1);
    expect(state.loadHomeEvents).toHaveBeenCalledWith(secondLocation);
  });

  it("does not replay a completed refresh when Live or Events mounts, including return navigation", async () => {
    await render("weather");
    await render("weather", 1);
    expect(state.loadWeather.mock.calls.filter(([, options]) => options.force)).toHaveLength(1);

    await render("live", 1);
    expect(state.loadLive).toHaveBeenCalledTimes(1);
    expect(state.loadLive.mock.calls[0][0].force).not.toBe(true);
    await render("events", 1);
    expect(state.loadEvents).toHaveBeenCalledTimes(1);
    await render("weather", 1);
    expect(state.loadWeather.mock.calls.filter(([, options]) => options.force)).toHaveLength(1);
    await render("live", 1);
    expect(state.loadLive).toHaveBeenCalledTimes(2);
    expect(state.loadLive.mock.calls.every(([options]) => !options.force)).toBe(true);
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("accepts new manual and resume refreshes on the active view after navigation", async () => {
    await render("weather");
    await render("weather", 1);
    await render("events", 1);
    await render("events", 2);
    expect(state.loadEvents).toHaveBeenCalledTimes(2);
    expect(state.loadEvents.mock.calls[1][1]).toMatchObject({ force: true });
    expect(settled).toHaveBeenCalledWith(2, expect.objectContaining({ complete: true }));

    await render("weather", 2);
    const beforeResume = state.loadWeather.mock.calls.length;
    await render("weather", 3, location, false);
    expect(state.loadWeather).toHaveBeenCalledTimes(beforeResume + 1);
    expect(state.loadWeather.mock.calls.at(-1)[1]).toMatchObject({ force: false });
    expect(settled).toHaveBeenCalledWith(3, expect.objectContaining({ complete: true }));
  });

  it("does not inherit the previous municipality's refresh when a location change remounts Home", async () => {
    await render("home");
    await render("home", 1);
    const homeEventsCalls = state.loadHomeEvents.mock.calls.length;
    const forcedWeatherCalls = state.loadWeather.mock.calls.filter(([, options]) => options.force).length;
    await render("home", 1, secondLocation);
    expect(state.loadHomeEvents).toHaveBeenCalledTimes(homeEventsCalls + 1);
    expect(state.loadWeather.mock.calls.filter(([, options]) => options.force)).toHaveLength(forcedWeatherCalls);
  });

  it("does not reissue refreshes after an ordinary render of the same view", async () => {
    await render("weather");
    await render("weather", 1);
    const before = state.loadWeather.mock.calls.length;
    const settledBefore = settled.mock.calls.length;
    await render("weather", 1);
    expect(state.loadWeather).toHaveBeenCalledTimes(before);
    expect(settled).toHaveBeenCalledTimes(settledBefore);
  });

  it("reuses Home cultural projections when independent data refreshes with unchanged cultural inputs", async () => {
    await render("home");
    expect(state.buildDiscover).toHaveBeenCalledTimes(1);
    expect(state.buildAlmanac).toHaveBeenCalledTimes(1);
    await render("home", 1);
    expect(state.loadHomeEvents).toHaveBeenCalledTimes(2);
    expect(state.buildDiscover).toHaveBeenCalledTimes(1);
    expect(state.buildAlmanac).toHaveBeenCalledTimes(1);
  });

  it("retires the pending refresh on navigation without transferring it to the new view", async () => {
    const loads = [];
    state.loadLive.mockImplementation(options => new Promise(resolve => loads.push({ options, resolve })));
    await render("live");
    await render("live", 1);
    expect(settled).not.toHaveBeenCalledWith(1, expect.objectContaining({ complete: true }));
    await render("events", 1);
    expect(settled).toHaveBeenCalledWith(1, { complete: true, status: "superseded" });
    expect(state.loadEvents).toHaveBeenCalledTimes(1);
    const callCount = settled.mock.calls.length;
    await act(async () => loads.forEach(load => load.resolve({ status: "ready", items: [] })));
    expect(settled).toHaveBeenCalledTimes(callCount);
  });

  it("shows progressive Live data and ignores partial or final responses from superseded loads", async () => {
    const loads = [];
    state.loadLive.mockImplementation(options => new Promise(resolve => loads.push({ options, resolve })));
    const snapshot = generatedAt => ({ status: "ready", items: [],
      community: { status: "fresh", payload: { reports: [], map_groups: [] } },
      webcams: { status: "fresh", payload: { ok: true, webcams: [], generated_at: generatedAt } },
    });
    await render("live");
    await act(async () => loads[0].options.onUpdate(snapshot("first partial")));
    expect(container.querySelector("[data-webcam-update]").textContent).toBe("first partial");
    await render("live", 1);
    expect(loads).toHaveLength(2);
    await act(async () => loads[1].options.onUpdate(snapshot("new partial")));
    expect(settled).not.toHaveBeenCalledWith(1, expect.objectContaining({ complete: true }));
    await act(async () => {
      loads[0].options.onUpdate(snapshot("old partial"));
      loads[0].resolve(snapshot("old final"));
    });
    expect(container.querySelector("[data-webcam-update]").textContent).toBe("new partial");
    await act(async () => loads[1].resolve(snapshot("new final")));
    expect(container.querySelector("[data-webcam-update]").textContent).toBe("new final");
    expect(settled).toHaveBeenCalledWith(1, expect.objectContaining({ complete: true }));
  });
});
