// @vitest-environment jsdom
import { act, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { harness, MINUTE, RUN_B, START } from "../services/camsRecoveryTestFixtures";

const testState = vi.hoisted(() => ({ harness: null, requests: [] }));

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
  loadOfficialAlertsRuntime: async () => ({ payload: null, status: "fresh", alertState: "inactive_confirmed" }),
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
    testState.requests.push(options);
    const h = testState.harness;
    return actual.fetchWeatherBootstrap(location, { ...options,
      weatherV1Fetcher: h.bundleFetcher, fetchImpl: h.options.fetchImpl,
      storage: h.storage, now: h.options.now, verificationNow: h.options.verificationNow,
    });
  } };
});
vi.mock("../ui/layout/AppShell", () => ({ AppShell: ({ children }) => <main>{children}</main> }));
vi.mock("./labFlags", () => ({ readUiV3LabFlag: () => false }));
vi.mock("./AppRoutes", () => ({
  // Only the visual route is substituted. This uses the real controller/API,
  // runtime and adapter; App itself installs and handles the actual DOM events.
  AppRoutes: function WeatherRouteProbe({ activeLocation, runtimeRefreshToken, runtimeRefreshForce, onRuntimeRefreshSettled }) {
    const [weather, setWeather] = useState(null);
    useEffect(() => {
      let cancelled = false;
      void import("../features/home/homeDataController").then(({ loadHomeWeather }) => loadHomeWeather(activeLocation, {
        force: runtimeRefreshToken ? runtimeRefreshForce : false,
        deferCams: true, manageOfficialAlerts: false,
        onCamsUpdate: value => { if (!cancelled) setWeather(value); },
      })).then(value => {
        if (cancelled) return;
        setWeather(value);
        onRuntimeRefreshSettled(runtimeRefreshToken, { ok: true });
      });
      return () => { cancelled = true; };
    }, [activeLocation, runtimeRefreshToken, runtimeRefreshForce, onRuntimeRefreshSettled]);
    return <output data-testid="cams-state">{weather?.rawCurrent?.data_quality?.cams_run_utc
      || weather?.rawCurrent?.data_quality?.cams_status || "initial"}</output>;
  },
}));

import App from "./App";

let root;
let container;
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(START);
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  // jsdom has a separate typed-array realm from Node's TextEncoder. Preserve
  // the real UTF-8 encoding and return its bytes in the browser test realm.
  const Encoder = globalThis.TextEncoder;
  vi.stubGlobal("TextEncoder", class {
    encode(value) { return Uint8Array.from(new Encoder().encode(value)); }
  });
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Unexpected live network request"); }));
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  window.localStorage.clear();
  testState.harness = harness({ location: { city: "Pordenone", municipality: { istatCode: "093033" } } });
  testState.requests = [];
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

async function mountWithDelayedNegativeResult() {
  const h = testState.harness;
  const originalFactory = h.clientFactory.getMockImplementation();
  h.clientFactory.mockImplementationOnce(options => {
    const clients = originalFactory(options);
    clients.camsPollen.fetchLatest.mockImplementationOnce(() => new Promise((_resolve, reject) => {
      setTimeout(() => reject(Object.assign(new Error("controlled outage"), { code: "TRANSPORT_FAILURE" })), 4000);
    }));
    return clients;
  });
  await act(async () => {
    root.render(<App />);
  });
  await act(async () => {
    window.dispatchEvent(new Event("focus"));
    await vi.advanceTimersByTimeAsync(4010);
  });
  expect(h.bundleFetcher).toHaveBeenCalledTimes(1);
  expect(h.saved().camsVerifiedAt).toBeNull();
  expect(container.textContent).toContain("unavailable");
  return h;
}

describe("App CAMS recovery with its mounted DOM event gate", () => {
  it("recovers at the first ten-minute tick, coalescing focus/online and the route without manual refresh", async () => {
    const h = await mountWithDelayedNegativeResult();
    const iconVerifiedAt = h.saved().verifiedAt;
    h.publish();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10 * MINUTE - 4010);
      window.dispatchEvent(new Event("focus"));
      window.dispatchEvent(new Event("online"));
      document.dispatchEvent(new Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(h.bundleFetcher).toHaveBeenCalledTimes(2);
    // The opportunity lands exactly on the ten-minute ICON verification
    // boundary, so one normal ICON revalidation is expected. The coincident
    // focus/online/visibility events must still coalesce into that one request.
    expect(h.observed[1].icon2i.fetchLatest).toHaveBeenCalledTimes(1);
    expect(h.observed[1].icon2i.fetchManifest).toHaveBeenCalledTimes(1);
    expect(h.observed[1].icon2i.fetchMunicipality).toHaveBeenCalledTimes(1);
    expect(h.observed[1].camsPollen.fetchLatest).toHaveBeenCalledTimes(1);
    expect(h.saved().verifiedAt).toBeGreaterThan(iconVerifiedAt);
    expect(h.saved().camsVerifiedAt).toBeGreaterThanOrEqual(START + 10 * MINUTE);
    expect(container.textContent).toContain(RUN_B);
    expect(testState.requests.filter(request => request.retryUnavailableCams)).toHaveLength(2);
    expect(testState.requests.every(request => request.force === false)).toBe(true);
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("uses an existing foreground/network opportunity after the gate, with no automatic timer on cache expiry", async () => {
    const h = await mountWithDelayedNegativeResult();
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    h.publish();
    await act(async () => { await vi.advanceTimersByTimeAsync(11 * MINUTE); });
    expect(h.bundleFetcher).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
    await act(async () => {
      window.dispatchEvent(new Event("online"));
      window.dispatchEvent(new Event("focus"));
      document.dispatchEvent(new Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(h.bundleFetcher).toHaveBeenCalledTimes(2);
    expect(h.observed[1].camsPollen.fetchLatest).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain(RUN_B);
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});
