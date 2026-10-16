// @vitest-environment jsdom
import { act, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { harness, RUN_B } from "../services/camsRecoveryTestFixtures";
import { getRuntimeRefreshCompletionOutcome } from "../domain/runtime/runtimeRefreshPolicy";
import { getPullRefreshResultState } from "../domain/runtime/pullRefreshPolicy";
import { subscribeToUvForecast, UV_CACHE_KEY, UV_FORECAST_URL } from "../features/weather/uvForecastRuntime";

// Controlled reproduction of the installed source paths, not a recording from
// the A52. In particular the request timings and alert outcomes are synthetic.
const EPISODE = Date.parse("2026-09-11T03:00:00Z");
const testState = vi.hoisted(() => ({
  harness: null, alertsDelay: 0, alertsUnavailable: false, completionValueOverride: null,
  outcomes: [], routeProgressOnly: false, supplements: [], uvFetcher: null,
}));

vi.mock("../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: () => true,
  isLocalWeatherPilot: () => true,
  getLocalWeatherPilotApiBase: () => testState.harness.options.baseUrl,
  getLocalWeatherPilotTestNow: () => null,
}));
vi.mock("./appLocation", async importOriginal => ({
  ...await importOriginal(),
  readInitialAppLocation: () => ({ city: "Pordenone", source: "manual",
    municipality: { name: "Pordenone", istatCode: "093033" }, lat: 45.9567, lon: 12.6605 }),
  readStoredAutoLocationEnabled: () => false,
}));
vi.mock("../services/officialAlertsRuntime", async importOriginal => ({
  ...await importOriginal(),
  readInitialOfficialAlertsRuntime: () => ({ payload: null }),
  loadOfficialAlertsRuntime: async () => {
    if (testState.alertsDelay) await new Promise(resolve => setTimeout(resolve, testState.alertsDelay));
    return testState.alertsUnavailable
      ? { payload: null, status: "unavailable", alertState: "unavailable" }
      : { payload: null, status: "fresh", alertState: "inactive_confirmed" };
  },
}));
vi.mock("../services/firebaseWebMessaging", async importOriginal => ({
  ...await importOriginal(),
  createWebPushRuntime: async () => ({ ok: false, reason: "not_configured" }),
  readWebPushPermission: () => "unsupported",
}));
vi.mock("../features/startup/webStartupOnboardingState", async importOriginal => ({
  ...await importOriginal(), readWebStartupOnboardingState: () => "completed",
}));
vi.mock("../features/live/liveDataController", async importOriginal => {
  const actual = await importOriginal();
  return {
    ...actual,
    loadLiveData: async () => actual.createEmptyLiveDataState(),
  };
});
vi.mock("../services/weatherApi", async importOriginal => {
  const actual = await importOriginal();
  return { ...actual, fetchWeatherBootstrap: (location, options) => {
    const h = testState.harness;
    return actual.fetchWeatherBootstrap(location, { ...options,
      weatherV1Fetcher: h.bundleFetcher, fetchImpl: h.options.fetchImpl,
      storage: h.storage, now: h.options.now, verificationNow: h.options.verificationNow,
    });
  } };
});
vi.mock("../ui/layout/AppShell", () => ({
  // Expose the same callback and force/source arguments used by AppShell's
  // touchend handler. Gesture recognition/animation is not exercised here.
  AppShell: ({ children, onRuntimeRefresh }) => <main>
    <button data-testid="manual-refresh" onClick={() => {
      void onRuntimeRefresh({ force: true, source: "pull" }).then(result => testState.outcomes.push(result));
    }}>Refresh</button>{children}
  </main>,
}));
vi.mock("./labFlags", () => ({ readUiV3LabFlag: () => false }));
vi.mock("./AppRoutes", () => ({
  AppRoutes: function WeatherRouteProbe({ activeLocation, runtimeRefreshToken, runtimeRefreshForce, onRuntimeRefreshSettled }) {
    const [weather, setWeather] = useState(null);
    const [uv, setUv] = useState(null);
    useEffect(() => subscribeToUvForecast(setUv, {
      storage: testState.harness.storage, fetchImpl: testState.uvFetcher,
      startNativeResume: () => ({ stop() {} }),
    }), []);
    useEffect(() => {
      let cancelled = false;
      let enrichedWeather = null;
      let initialWeather = null;
      let initialSettled = false;
      const completeWeather = (value) => {
        if (cancelled || !runtimeRefreshToken || testState.routeProgressOnly) return;
        const completionValue = testState.completionValueOverride
          ? testState.completionValueOverride(value)
          : value;
        onRuntimeRefreshSettled(runtimeRefreshToken, {
          ...getRuntimeRefreshCompletionOutcome([
            { status: "fulfilled", value: completionValue },
          ], ["weather"]),
          complete: true,
        });
      };
      void import("../features/home/homeDataController").then(({ loadHomeWeather }) => loadHomeWeather(activeLocation, {
        force: runtimeRefreshToken ? runtimeRefreshForce : false,
        deferCams: true, manageOfficialAlerts: false,
        onCamsUpdate: value => {
          enrichedWeather = value;
          if (!cancelled) setWeather(value);
          if (initialSettled) completeWeather(value);
        },
        onCamsFailure: () => {
          if (cancelled || !initialSettled || !runtimeRefreshToken || testState.routeProgressOnly) return;
          const completionValue = testState.completionValueOverride
            ? testState.completionValueOverride(initialWeather)
            : initialWeather;
          onRuntimeRefreshSettled(runtimeRefreshToken, {
            ...getRuntimeRefreshCompletionOutcome([
              { status: "fulfilled", value: completionValue },
              { status: "fulfilled", value: { status: "unavailable" } },
            ], ["weather", "cams"]),
            complete: true,
          });
        },
      })).then(value => {
        if (cancelled) return;
        initialWeather = value;
        initialSettled = true;
        setWeather(enrichedWeather || value);
        if (testState.routeProgressOnly) {
          onRuntimeRefreshSettled(runtimeRefreshToken, {
            complete: false,
            components: { icon: "settled", osmer: "pending" },
            ok: true,
            partial: true,
          });
        } else if (enrichedWeather) {
          completeWeather(enrichedWeather);
        } else {
          const completionValue = testState.completionValueOverride
            ? testState.completionValueOverride(value)
            : value;
          onRuntimeRefreshSettled(runtimeRefreshToken, {
            ...getRuntimeRefreshCompletionOutcome([
              {
                status: "fulfilled",
                value: { ...completionValue, runtimeRefreshPendingComponents: ["cams"] },
              },
              { status: "pending" },
            ], ["weather", "cams"]),
            complete: false,
          });
        }
      });
      return () => { cancelled = true; };
    }, [activeLocation, runtimeRefreshToken, runtimeRefreshForce, onRuntimeRefreshSettled]);
    return <>
      <button data-testid="retire-route-refresh" data-token={runtimeRefreshToken} onClick={() => {
        onRuntimeRefreshSettled(runtimeRefreshToken, { complete: true, status: "superseded" });
      }}>Retire route refresh</button>
      <output data-testid="cams-state">{weather?.rawCurrent?.data_quality?.cams_run_utc
        || weather?.rawCurrent?.data_quality?.cams_status || "initial"}</output>
      <output data-testid="uv-state">{uv?.document?.run_at || uv?.error || "initial"}</output>
    </>;
  },
}));

import App from "./App";

let root;
let container;
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(EPISODE);
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const Encoder = globalThis.TextEncoder;
  vi.stubGlobal("TextEncoder", class {
    encode(value) { return Uint8Array.from(new Encoder().encode(value)); }
  });
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Unexpected live network request"); }));
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  window.localStorage.clear();
  testState.harness = harness({ location: { city: "Pordenone", municipality: { istatCode: "093033" } } });
  testState.alertsDelay = 0;
  testState.alertsUnavailable = false;
  testState.completionValueOverride = null;
  testState.outcomes = [];
  testState.routeProgressOnly = false;
  testState.supplements = [];
  const adapterCall = testState.harness.bundleFetcher.getMockImplementation();
  testState.harness.bundleFetcher.mockImplementation((location, options) => adapterCall(location, {
    ...options, onCamsUpdate: bundle => {
      testState.supplements.push(bundle);
      options.onCamsUpdate?.(bundle);
    },
  }));
  const run = Date.parse("2026-09-09T00:00:00Z");
  const oldUv = { schema: "pilot-uv-v1", unit: "1", run_at: new Date(run).toISOString(), grid: [[46, 13]],
    hours: Array.from({ length: 72 }, (_, i) => ({ time: new Date(run + i * 3600000).toISOString(), values: [0] })) };
  testState.harness.storage.setItem(UV_CACHE_KEY, JSON.stringify({
    version: 1, url: UV_FORECAST_URL, savedAt: run + 36 * 3600000, document: oldUv,
  }));
  testState.uvFetcher = vi.fn(async () => ({ ok: true, json: async () => oldUv }));
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
async function mount() {
  await act(async () => { root.render(<App />); });
  await act(async () => { await vi.advanceTimersByTimeAsync(10); });
  expect(testState.harness.bundleFetcher).toHaveBeenCalledTimes(1);
  expect(container.querySelector('[data-testid="cams-state"]').textContent).toBe("unavailable");
  expect(container.querySelector('[data-testid="uv-state"]').textContent)
    .toBe("2026-09-09T00:00:00.000Z");
}
async function manualRefresh() {
  await act(async () => {
    container.querySelector('[data-testid="manual-refresh"]').click();
    await vi.advanceTimersByTimeAsync(0);
  });
}
function delayNextCams(delay) {
  const h = testState.harness;
  h.publish();
  const originalFactory = h.clientFactory.getMockImplementation();
  let signal;
  h.clientFactory.mockImplementationOnce(options => {
    const clients = originalFactory(options);
    const latest = clients.camsPollen.fetchLatest.getMockImplementation();
    clients.camsPollen.fetchLatest.mockImplementationOnce(requestSignal => {
      signal = requestSignal;
      return new Promise(resolve => setTimeout(() => resolve(latest()), delay));
    });
    return clients;
  });
  return () => signal;
}

describe("11 September manual refresh: controlled installed-source mechanisms, not phone evidence", () => {
  it("releases an abandoned route refresh immediately so the next view can refresh", async () => {
    await mount();
    delayNextCams(12000);
    testState.alertsDelay = 9000;
    await manualRefresh();
    expect(testState.outcomes).toEqual([]);
    await act(async () => container.querySelector('[data-testid="retire-route-refresh"]').click());
    expect(testState.outcomes).toEqual([{ status: "superseded", token: 1 }]);
    await manualRefresh();
    expect(container.querySelector('[data-testid="retire-route-refresh"]').dataset.token).toBe("2");
    expect(testState.outcomes).not.toContainEqual({ status: "skipped" });
  });

  it("reports only slow alerts as pending at 8s while CAMS remains active and commits at 12s", async () => {
    await mount();
    const signal = delayNextCams(12000);
    testState.alertsDelay = 9000;
    await manualRefresh();
    await act(async () => { await vi.advanceTimersByTimeAsync(8000); });
    expect(testState.outcomes).toEqual([{
      components: {
        cams: "pending",
        icon: "settled",
        officialAlerts: "pending",
      },
      status: "partial",
      token: 1,
    }]);
    expect(getPullRefreshResultState({ result: testState.outcomes[0] }).state).toBe("partial");
    expect(signal().aborted).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(4010); });
    expect(container.querySelector('[data-testid="cams-state"]').textContent).toBe(RUN_B);
    expect(testState.harness.saved().camsVerifiedAt).not.toBeNull();
    expect(testState.outcomes).toHaveLength(1);
    expect(testState.harness.bundleFetcher).toHaveBeenCalledTimes(2);
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("reports CAMS pending at 8s, then really aborts it at 20s rather than the UI deadline", async () => {
    await mount();
    const signal = delayNextCams(21000);
    await manualRefresh();
    expect(testState.outcomes).toEqual([]);
    await act(async () => { await vi.advanceTimersByTimeAsync(8000); });
    expect(testState.outcomes).toEqual([{
      components: {
        cams: "pending",
        icon: "settled",
        officialAlerts: "settled",
      },
      status: "partial",
      token: 1,
    }]);
    expect(signal().aborted).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(11999); });
    expect(signal().aborted).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(11); });
    expect(signal().aborted).toBe(true);
    expect(testState.harness.saved().camsVerifiedAt).toBeNull();
    expect(testState.supplements.at(-1).current.data_quality.cams_diagnostic)
      .toMatchObject({ stage: "timeout", code: "CAMS_TIMEOUT" });
    // Equal-rank unavailable bundles retain the earlier diagnostic; a cache
    // snapshot alone therefore cannot timestamp the latest transport failure.
    expect(testState.harness.saved().bundle.current.data_quality.cams_diagnostic)
      .toMatchObject({ stage: "latest", code: "TRANSPORT_FAILURE" });
    await act(async () => { await vi.advanceTimersByTimeAsync(1100); });
    expect(container.querySelector('[data-testid="cams-state"]').textContent).toBe("unavailable");
    expect(testState.outcomes).toHaveLength(1);
  });

  it("reports a partial result when official alerts are unavailable while CAMS succeeds", async () => {
    await mount();
    testState.harness.publish();
    testState.alertsUnavailable = true;
    await manualRefresh();
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    expect(testState.outcomes).toEqual([{
      components: {
        cams: "settled",
        icon: "settled",
        officialAlerts: "unavailable",
      },
      status: "partial",
      token: 1,
    }]);
    expect(getPullRefreshResultState({ result: testState.outcomes[0] }).state)
      .toBe("partial");
    expect(container.querySelector('[data-testid="cams-state"]').textContent).toBe(RUN_B);
  });

  it("keeps a completed service successful when another route service is still pending at 8s", async () => {
    await mount();
    testState.routeProgressOnly = true;
    testState.alertsDelay = 1000;
    await manualRefresh();
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(testState.outcomes).toEqual([]);
    await act(async () => { await vi.advanceTimersByTimeAsync(7000); });

    expect(testState.outcomes).toEqual([{
      components: {
        icon: "settled",
        officialAlerts: "settled",
        osmer: "pending",
      },
      status: "partial",
      token: 1,
    }]);
    expect(getPullRefreshResultState({ result: testState.outcomes[0] }).state)
      .toBe("partial");
    expect(container.querySelector('[data-testid="cams-state"]').textContent)
      .not.toBe("initial");
  });

  it("keeps last-known UV independent while the valid 27h CAMS supplement succeeds", async () => {
    const cachedUv = testState.harness.storage.getItem(UV_CACHE_KEY);
    await mount();
    testState.harness.publish();
    await manualRefresh();
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    expect(testState.outcomes).toEqual([{
      components: {
        cams: "settled",
        icon: "settled",
        officialAlerts: "settled",
      },
      status: "settled",
      token: 1,
    }]);
    expect(container.querySelector('[data-testid="cams-state"]').textContent).toBe(RUN_B);
    expect(container.querySelector('[data-testid="uv-state"]').textContent)
      .toBe("2026-09-09T00:00:00.000Z");
    expect(testState.uvFetcher).toHaveBeenCalledTimes(1);
    expect(testState.harness.storage.getItem(UV_CACHE_KEY)).toBe(cachedUv);
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("reports failed when ICON candidate persistence fails while old weather remains visible", async () => {
    await mount();
    testState.completionValueOverride = value => ({
      ...value,
      rawCurrent: {
        ...value.rawCurrent,
        cache: {
          ...value.rawCurrent?.cache,
          runtime_fallback: true,
          runtime_fallback_source: "candidate_not_committed",
          runtime_fallback_code: "CACHE_PERSIST_FAILED",
        },
      },
    });

    await manualRefresh();
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });

    expect(testState.outcomes).toEqual([{
      components: {
        cams: "unavailable",
        icon: "failed",
        officialAlerts: "settled",
      },
      status: "failed",
      token: 1,
    }]);
    expect(getPullRefreshResultState({ result: testState.outcomes[0] }).state).toBe("failed");
    expect(container.querySelector('[data-testid="cams-state"]').textContent)
      .toBe("unavailable");
  });

  it("maps an overlapping manual gesture to skipped/failed without starting another weather request", async () => {
    await mount();
    delayNextCams(12000);
    testState.alertsDelay = 9000;
    await manualRefresh();
    await manualRefresh();
    expect(testState.outcomes).toEqual([{ status: "skipped" }]);
    expect(getPullRefreshResultState({ result: testState.outcomes[0] }).state).toBe("failed");
    expect(testState.harness.bundleFetcher).toHaveBeenCalledTimes(2);
  });
});
