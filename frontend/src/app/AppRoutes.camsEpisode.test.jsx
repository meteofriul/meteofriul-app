// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { harness } from "../services/camsRecoveryTestFixtures";

const state = vi.hoisted(() => ({ harness: null, delay: 0 }));
vi.mock("../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(), isDefinitiveAppExperience: () => true, isLocalWeatherPilot: () => true,
  getLocalWeatherPilotApiBase: () => state.harness.options.baseUrl,
  getLocalWeatherPilotTestNow: () => null,
}));
vi.mock("../services/weatherApi", async importOriginal => {
  const actual = await importOriginal();
  return { ...actual, fetchWeatherBootstrap: (location, options) => {
    const h = state.harness;
    return actual.fetchWeatherBootstrap(location, { ...options,
      weatherV1Fetcher: h.bundleFetcher, fetchImpl: h.options.fetchImpl,
      storage: h.storage, now: h.options.now, verificationNow: h.options.verificationNow,
    });
  } };
});
// These independent cards are not part of the air/pollen route-state check.
vi.mock("../features/weather/WeatherUvCard", () => ({
  UvCurve: () => null,
  WeatherUvCard: () => null,
  WeatherUvContent: () => null,
}));
vi.mock("../features/weather/useWeatherUvCardState", () => ({
  useWeatherUvCardState: () => ({ error: null, forecastDate: "", model: null, saved: false }),
}));
vi.mock("../features/weather/WeatherSkyCard", () => ({ WeatherSkyCard: () => null }));

import { AppRoutes } from "./AppRoutes";
import { loadHomeWeather } from "../features/home/homeDataController";

let root;
let container;
let settled;
const location = { city: "Pordenone", source: "manual", lat: 45.9567, lon: 12.6605,
  municipality: { name: "Pordenone", istatCode: "093033" } };
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-11T03:22:44Z"));
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const Encoder = globalThis.TextEncoder;
  vi.stubGlobal("TextEncoder", class { encode(value) { return Uint8Array.from(new Encoder().encode(value)); } });
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Unexpected live request"); }));
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  window.localStorage.clear();
  state.harness = harness({ location });
  state.delay = 0;
  const factory = state.harness.clientFactory.getMockImplementation();
  state.harness.clientFactory.mockImplementation(options => {
    const clients = factory(options);
    const payload = clients.camsPollen.fetchMunicipality.getMockImplementation();
    clients.camsPollen.fetchMunicipality.mockImplementation(async (...args) => {
      if (state.delay) await new Promise(resolve => setTimeout(resolve, state.delay));
      const pollen = await payload(...args);
      // Provider responses are controlled fixture ports, not network/contract
      // evidence. Both products explicitly have stale (but usable) freshness.
      const ids = ["particulate_matter_2.5um", "particulate_matter_10um", "ozone", "nitrogen_dioxide"];
      return { ...pollen, freshness: { ...pollen.freshness, status: "stale" },
        airResult: { ...pollen, freshness: { ...pollen.freshness, status: "stale" },
          document: { ...pollen.document, provider: "cams_europe",
            variables: ids.map(id => ({ id, category: "air_quality" })),
            hourly: pollen.document.hourly.map(row => ({ ...row,
              values: Object.fromEntries(ids.map((id, index) => [id, index + 1.2])),
            })),
          },
        },
      };
    });
    return clients;
  });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  settled = vi.fn();
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
function render(token = 0) {
  root.render(<AppRoutes activeTab="weather" activeLocation={location} language="it"
    copy={{ placeholders: { weatherTitle: "Meteo" } }} labEnabled={false}
    runtimeRefreshToken={token} runtimeRefreshForce={true} onRuntimeRefreshSettled={settled} />);
}
function assertCamsShown() {
  expect(container.querySelector('.mf-weather-environment [data-status="available"]')).not.toBeNull();
  expect(container.textContent).toContain("PM2.5");
  expect(container.textContent).toContain("1,2");
  expect(container.textContent).not.toContain("Dati dell’aria non disponibili");
  expect(state.harness.saved().bundle.current.data_quality.cams_status).toBe("stale");
}

describe("real Meteo route state with a 27h CAMS run and fast repeated supplements", () => {
  it("commits air and pollen after the initial rendering, including the warm-up/manual-route coalescing", async () => {
    await act(async () => { render(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    expect(container.querySelector('.mf-weather-environment [data-status="unavailable"]')).not.toBeNull();
    state.harness.publish();
    state.delay = 1500;
    for (let token = 1; token <= 4; token += 1) {
      await act(async () => {
        // The same warm-up call made by App.requestRuntimeRefresh before it
        // updates the route token; the real route registers its own callback.
        void loadHomeWeather(location, { force: true, deferCams: true,
          manageOfficialAlerts: false, retryUnavailableCams: true });
        render(token);
        await vi.advanceTimersByTimeAsync(10);
      });
      await act(async () => { await vi.advanceTimersByTimeAsync(1510); });
      // The provider completion deliberately hands the verified supplement to
      // observers on a separate task, so a consumer exception cannot poison it.
      await act(async () => {
        const providerRequest = state.harness.observed.at(-1)?.camsPollen
          .fetchMunicipality.mock.results.at(-1)?.value;
        if (providerRequest) await providerRequest;
      });
      await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      assertCamsShown();
      expect(settled.mock.calls.filter(([observedToken]) => observedToken === token))
        .toEqual([
          [token, {
            complete: false,
            components: {
              cams: "pending",
              icon: "settled",
            },
            ok: true,
            partial: true,
          }],
          [token, {
            complete: true,
            components: {
              cams: "retained",
              icon: "settled",
            },
            ok: true,
            partial: true,
          }],
        ]);
      expect(state.harness.bundleFetcher).toHaveBeenCalledTimes(token + 1);
    }
    expect(globalThis.fetch).not.toHaveBeenCalled();
  }, 15_000);

  it("keeps ICON successful when the deferred CAMS failure callback closes separately", async () => {
    await act(async () => { render(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    settled.mockClear();
    const retained = structuredClone(state.harness.saved().bundle);
    state.harness.bundleFetcher.mockImplementationOnce((_location, options) => {
      setTimeout(() => options.onCamsFailure?.(
        new Error("controlled deferred CAMS failure"),
      ), 100);
      return Promise.resolve(retained);
    });

    await act(async () => {
      render(1);
      await vi.advanceTimersByTimeAsync(10);
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });

    expect(settled.mock.calls.filter(([observedToken]) => observedToken === 1))
      .toEqual([
        [1, {
          complete: false,
          components: {
            cams: "pending",
            icon: "settled",
          },
          ok: true,
          partial: true,
        }],
        [1, {
          complete: true,
          components: {
            cams: "unavailable",
            icon: "settled",
          },
          ok: true,
          partial: true,
        }],
      ]);
    expect(container.querySelector('.mf-weather-environment [data-status="unavailable"]'))
      .not.toBeNull();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});
