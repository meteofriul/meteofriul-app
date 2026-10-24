// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { harness } from "../services/camsRecoveryTestFixtures";

const state = vi.hoisted(() => ({ harness: null, delay: 0, iconDelay: 0 }));
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
  state.iconDelay = 0;
  const factory = state.harness.clientFactory.getMockImplementation();
  state.harness.clientFactory.mockImplementation(options => {
    const clients = factory(options);
    const iconPayload = clients.icon2i.fetchMunicipality.getMockImplementation();
    clients.icon2i.fetchMunicipality.mockImplementation(async (...args) => {
      if (state.iconDelay) await new Promise(resolve => setTimeout(resolve, state.iconDelay));
      return iconPayload(...args);
    });
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
function render(token = 0, language = "it") {
  root.render(<AppRoutes activeTab="weather" activeLocation={location} language={language}
    copy={{ placeholders: { weatherTitle: "Meteo" } }} labEnabled={false}
    runtimeRefreshToken={token} runtimeRefreshForce={true} onRuntimeRefreshSettled={settled} />);
}
function assertCamsShown() {
  expect(container.querySelector('.mf-weather-environment [data-status="available"]')).not.toBeNull();
  expect(container.textContent).toContain("PM2.5");
  expect(container.textContent).toContain("1,2");
  expect(container.textContent).not.toContain("Dati non disponibili");
  expect(state.harness.saved().bundle.current.data_quality.cams_status).toBe("stale");
}

describe("real Meteo route state with a 27h CAMS run and fast repeated supplements", () => {
  it.each(["it", "fur"])("keeps CAMS loading through delayed recovery in %s", async (language) => {
    await act(async () => { render(0, language); });
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
        render(token, language);
        await vi.advanceTimersByTimeAsync(10);
      });
      // While a new supplement is in flight, an old unavailable snapshot is
      // not the result of that request. Keep verified values or show loading.
      expect(container.textContent).not.toContain(language === "fur" ? "Dâts no disponibii" : "Dati non disponibili");
      if (token === 1) expect(container.textContent).toContain(language === "fur" ? "In cjariament…" : "Caricamento…");
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

  it.each(["it", "fur"])("shows loading before the first ICON response during a CAMS retry in %s", async language => {
    await act(async () => { render(0, language); });
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    expect([...container.querySelectorAll('.mf-weather-environment [role="status"]')].filter(e => e.textContent === (language === "fur" ? "Dâts no disponibii" : "Dati non disponibili"))).toHaveLength(2);
    state.harness.publish();
    state.iconDelay = 1000;
    state.delay = 2000;
    await act(async () => { render(1, language); await vi.advanceTimersByTimeAsync(1); });
    expect(settled).not.toHaveBeenCalled();
    expect([...container.querySelectorAll('.mf-weather-environment [role="status"]')].filter(e => e.textContent === (language === "fur" ? "In cjariament…" : "Caricamento…"))).toHaveLength(2);
    expect(container.textContent).toContain(language === "fur" ? "In cjariament…" : "Caricamento…");
    expect(container.textContent).not.toContain(language === "fur" ? "Dâts no disponibii" : "Dati non disponibili");
    await act(async () => { await vi.advanceTimersByTimeAsync(1100); });
    expect([...container.querySelectorAll('.mf-weather-environment [role="status"]')].filter(e => e.textContent === (language === "fur" ? "In cjariament…" : "Caricamento…"))).toHaveLength(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    await act(async () => {
      await state.harness.observed.at(-1)?.camsPollen.fetchMunicipality.mock.results.at(-1)?.value;
      await vi.advanceTimersByTimeAsync(1);
    });
    assertCamsShown();
    expect(settled.mock.calls.at(-1)?.[1].complete).toBe(true);
  });

  it.each(["it", "fur"])("finishes loading when the entire retry fails before a CAMS callback in %s", async language => {
    await act(async () => { render(0, language); });
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    state.harness.bundleFetcher.mockImplementationOnce(async () => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      throw new Error("controlled whole forecast failure");
    });
    await act(async () => { render(1, language); await vi.advanceTimersByTimeAsync(1); });
    expect([...container.querySelectorAll('.mf-weather-environment [role="status"]')].filter(e => e.textContent === (language === "fur" ? "In cjariament…" : "Caricamento…"))).toHaveLength(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(1100); });
    expect([...container.querySelectorAll('.mf-weather-environment [role="status"]')].filter(e => e.textContent === (language === "fur" ? "In cjariament…" : "Caricamento…"))).toHaveLength(0);
    expect(container.textContent).toContain(language === "fur" ? "Dâts no disponibii" : "Dati non disponibili");
    expect(settled.mock.calls.at(-1)?.[1].complete).toBe(true);
  });

  it("keeps ICON successful when the deferred CAMS failure callback closes separately", async () => {
    await act(async () => { render(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    settled.mockClear();
    const retained = structuredClone(state.harness.saved().bundle);
    retained.current.data_quality.cams_status = "pending";
    retained.current.data_quality.cams_diagnostic = null;
    retained.current.pollen_data = { status: "pending" };
    retained.current.source.cams = { status: "pending" };
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
