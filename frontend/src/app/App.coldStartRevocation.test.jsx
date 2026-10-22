// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { harness, RUN_A, RUN_B, START } from "../services/camsRecoveryTestFixtures";

const testState = vi.hoisted(() => ({
  baseUrl: "",
  bundleFetcher: null,
  events: [],
  fetchImpl: null,
  journalKey: "",
  now: () => Date.now(),
  storage: null,
  trackStorage: false,
  weatherBootstrapReads: [],
}));

// Controlled environment seam: pilot build identity and its endpoint.
// App, AppShell, AppRoutes, the Home controllers, weather runtime and journal
// implementation remain real in this test.
vi.mock("../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(),
  getLocalWeatherPilotApiBase: () => testState.baseUrl,
  getLocalWeatherPilotTestNow: () => null,
  isDefinitiveAppExperience: () => true,
  isLocalWeatherPilot: () => true,
}));

// Controlled app-state seam: the municipality already selected on the device.
vi.mock("./appLocation", async importOriginal => ({
  ...await importOriginal(),
  readInitialAppLocation: () => ({
    city: "Pordenone",
    lat: 45.9567,
    lon: 12.6605,
    municipality: { name: "Pordenone", istatCode: "093033" },
    source: "manual",
  }),
  readStoredAutoLocationEnabled: () => false,
}));

// Unrelated external boundaries are kept neutral so that they cannot decide
// the weather presentation observed here.
vi.mock("../services/officialAlertsRuntime", async importOriginal => ({
  ...await importOriginal(),
  loadOfficialAlertsRuntime: async () => ({
    alertState: "inactive_confirmed",
    payload: null,
    status: "fresh",
  }),
  readInitialOfficialAlertsRuntime: () => ({ payload: null }),
}));

vi.mock("../services/firebaseWebMessaging", async importOriginal => ({
  ...await importOriginal(),
  createWebPushRuntime: async () => ({ ok: false, reason: "not_configured" }),
  readWebPushPermission: () => "unsupported",
}));

vi.mock("../features/startup/webStartupOnboardingState", async importOriginal => ({
  ...await importOriginal(),
  readWebStartupOnboardingState: () => "completed",
}));

vi.mock("./labFlags", () => ({ readUiV3LabFlag: () => false }));

// Dependency injection only: both exported functions still execute their real
// implementation with a controlled storage and a never-settling transport.
vi.mock("../services/weatherApi", async importOriginal => {
  const actual = await importOriginal();
  return {
    ...actual,
    fetchWeatherBootstrap: (location, options = {}) => actual.fetchWeatherBootstrap(location, {
      ...options,
      fetchImpl: testState.fetchImpl,
      now: testState.now,
      storage: testState.storage,
      verificationNow: testState.now,
      weatherV1BaseUrl: testState.baseUrl,
      weatherV1Fetcher: testState.bundleFetcher,
    }),
    readWeatherBootstrapCache: (location, options = {}) => {
      const result = actual.readWeatherBootstrapCache(location, {
        ...options,
        now: testState.now,
        storage: testState.storage,
        weatherV1BaseUrl: testState.baseUrl,
      });
      const current = result?.current || null;
      const airValues = current?.air_quality_data?.values || null;
      const pollenValues = current?.pollen_data?.values || {};
      const dataQuality = current?.data_quality || null;
      const eventIndex = testState.events.push("weather-cache:observed") - 1;

      // Snapshot primitives immediately: return the original object untouched
      // and do not retain mutable runtime references as test evidence.
      testState.weatherBootstrapReads.push({
        airQuality: current?.air_quality_data
          ? { pm25: airValues?.["particulate_matter_2.5um"] ?? null }
          : null,
        dataQuality: {
          camsDiagnosticCode: dataQuality?.cams_diagnostic?.code ?? null,
          camsDiagnosticStage: dataQuality?.cams_diagnostic?.stage ?? null,
          camsRunUtc: dataQuality?.cams_run_utc ?? null,
          camsStatus: dataQuality?.cams_status ?? null,
          iconRunUtc: dataQuality?.run_utc ?? null,
        },
        eventIndex,
        hourlyForecastLength: Array.isArray(current?.hourly_forecast)
          ? current.hourly_forecast.length
          : 0,
        istatCode: String(location?.municipality?.istatCode || ""),
        pollen: {
          ambrosia: pollenValues.ambrosia ?? null,
          status: current?.pollen_data?.status ?? null,
          valueCount: Object.keys(pollenValues).length,
        },
        present: Boolean(result),
        primarySource: current?.primary_source ?? null,
      });
      return result;
    },
  };
});

import App from "./App";
import { LOCAL_WEATHER_V1_CATALOG } from "../services/localWeatherV1Adapter";
import {
  getLocalWeatherV1BundleCacheKey,
  getLocalWeatherV1CamsFamilyDecisionCacheKey,
} from "../services/localWeatherV1Runtime";
import { canonicalJsonStringify, sha256Hex } from "../services/weatherV1Client";

const PORDENONE = {
  city: "Pordenone",
  lat: 45.9567,
  lon: 12.6605,
  municipality: { name: "Pordenone", istatCode: "093033" },
  source: "manual",
};
const NOW = START + 11 * 60_000;
const AIR_MARKER = 91.7;
const POLLEN_MARKER = 92.7;
let root;
let container;

function sourceRunId(runAt) {
  return runAt.replaceAll("-", "").replaceAll(":", "");
}

function createTrackedStorage() {
  const values = new Map();
  return {
    get length() { return values.size; },
    getItem(key) {
      if (testState.trackStorage) {
        if (key === testState.journalKey) testState.events.push("storage:journal:get");
        if (key === getLocalWeatherV1BundleCacheKey(PORDENONE, { baseUrl: testState.baseUrl })) {
          testState.events.push("storage:active:get");
        }
      }
      return values.get(key) ?? null;
    },
    key(index) {
      return [...values.keys()][index] ?? null;
    },
    removeItem(key) {
      values.delete(key);
    },
    setItem(key, value) {
      values.set(key, String(value));
    },
  };
}

function writeDurableRevocation(storage) {
  const payload = {
    kind: "meteofriul.weather.cams_family_decision",
    version: 1,
    scope_sha256: sha256Hex(testState.baseUrl),
    catalog_sha256: LOCAL_WEATHER_V1_CATALOG.sha256,
    revision: 2,
    published_at: "2026-09-10T01:20:00Z",
    active_run_id: sourceRunId(RUN_B),
    disabled_run_ids: [sourceRunId(RUN_A)],
  };
  const record = {
    ...payload,
    sha256: sha256Hex(canonicalJsonStringify(payload)),
  };
  storage.setItem(testState.journalKey, JSON.stringify(record));
}

async function buildOldActive() {
  const source = harness({ available: true, location: PORDENONE });
  testState.baseUrl = source.options.baseUrl;
  const active = await source.bundleFetcher(PORDENONE, source.options);
  expect(active.current.data_quality.cams_run_utc).toBe(RUN_A);

  active.current.air_quality_data = {
    run_at: active.current.data_quality.cams_run_utc,
    valid_at: active.current.data_quality.cams_valid_at_utc,
    unit: "ug/m3",
    values: {
      "particulate_matter_2.5um": AIR_MARKER,
      "particulate_matter_10um": 91.8,
      ozone: 91.9,
      nitrogen_dioxide: 92,
    },
  };
  active.current.pollen_data.values.ambrosia = POLLEN_MARKER;
  active.current.source.cams.evidence.family = {
    revision: 1,
    published_at: "2026-09-09T01:00:00Z",
    active_run_id: sourceRunId(RUN_A),
    disabled_run_ids: [],
  };
  active.forecast.source.cams.evidence.family = {
    ...active.current.source.cams.evidence.family,
  };
  return active;
}

async function prepareScenario({ revoked }) {
  const active = await buildOldActive();
  testState.storage = createTrackedStorage();
  testState.journalKey = getLocalWeatherV1CamsFamilyDecisionCacheKey({
    baseUrl: testState.baseUrl,
  });
  const bundleKey = getLocalWeatherV1BundleCacheKey(PORDENONE, {
    baseUrl: testState.baseUrl,
  });
  const record = JSON.stringify({
    version: 4,
    municipality: "istat:093033",
    verifiedAt: START,
    camsVerifiedAt: START,
    bundle: active,
  });

  // Both runtime archives deliberately still contain the old run before App
  // starts. The journal, not archive cleanup, must decide presentation.
  testState.storage.setItem(bundleKey, record);
  testState.storage.setItem(`${bundleKey}:candidate`, record);
  if (revoked) writeDurableRevocation(testState.storage);

  const archivedActive = JSON.parse(testState.storage.getItem(bundleKey));
  const archivedCandidate = JSON.parse(testState.storage.getItem(`${bundleKey}:candidate`));
  expect(archivedActive.bundle.current.data_quality.cams_run_utc).toBe(RUN_A);
  expect(archivedCandidate.bundle.current.data_quality.cams_run_utc).toBe(RUN_A);
  expect(archivedActive.bundle.current.air_quality_data.values["particulate_matter_2.5um"])
    .toBe(AIR_MARKER);

  // No replacement can arrive during the observation window.
  testState.bundleFetcher = vi.fn(() => {
    testState.events.push("transport:pending");
    return new Promise(() => {});
  });
  testState.fetchImpl = vi.fn(() => new Promise(() => {}));
  testState.events = [];
  testState.trackStorage = true;
}

function observeDom() {
  const snapshots = [];
  const observer = new MutationObserver(() => {
    const route = container.querySelector(".mf-tab-page--home")
      ? "home"
      : container.querySelector(".mf-tab-page--weather")
        ? "weather"
        : "other";
    const text = container.textContent || "";
    snapshots.push({ route, text });
    testState.events.push(`dom:${route}:${text}`);
  });
  observer.observe(container, {
    attributes: true,
    characterData: true,
    childList: true,
    subtree: true,
  });
  return { snapshots, stop: () => observer.disconnect() };
}

async function mountOrdinaryAppOnHome() {
  const observed = observeDom();
  expect(window.location.search).toBe("");
  expect(testState.events).toEqual([]);
  testState.events.push("app:render");
  await act(async () => {
    root.render(<App />);
    await Promise.resolve();
  });
  await vi.waitFor(() => {
    expect(container.querySelector(".mf-tab-page--home")).not.toBeNull();
    expect(observed.snapshots.some(snapshot => snapshot.route === "home")).toBe(true);
  });

  const journalRead = testState.events.indexOf("storage:journal:get");
  const activeRead = testState.events.indexOf("storage:active:get");
  const firstHomeSnapshot = testState.events.findIndex(event => event.startsWith("dom:home:"));
  const initialWeather = getObservedInitialWeather(firstHomeSnapshot);
  expect(journalRead).toBeGreaterThan(testState.events.indexOf("app:render"));
  expect(activeRead).toBeGreaterThan(journalRead);
  expect(initialWeather.eventIndex).toBeGreaterThan(activeRead);
  expect(activeRead).toBeLessThan(firstHomeSnapshot);
  expect(journalRead).toBeLessThan(firstHomeSnapshot);
  await vi.waitFor(() => expect(testState.events).toContain("transport:pending"));
  expect(container.querySelector('.mf-bottom-nav-item[aria-current="page"]')?.textContent)
    .toContain("Home");
  expect(container.querySelector(".mf-home-view")).not.toBeNull();
  const homeTemperature = container.querySelector(".mf-home-temperature")?.textContent || "";
  expect(homeTemperature).not.toContain("--");
  expect(homeTemperature).toMatch(/\d/u);
  return { ...observed, initialWeather };
}

async function navigateToWeather() {
  const weatherButton = [...container.querySelectorAll(".mf-bottom-nav-item")]
    .find(button => button.textContent.includes("Meteo"));
  expect(weatherButton).toBeTruthy();
  await act(async () => {
    weatherButton.click();
    await Promise.resolve();
  });
  await vi.waitFor(() => {
    expect(container.querySelector(".mf-tab-page--weather")).not.toBeNull();
    expect(container.querySelector(".mf-weather-environment")).not.toBeNull();
  });
  expect(container.querySelector('.mf-bottom-nav-item[aria-current="page"]')?.textContent)
    .toContain("Meteo");
}

function getObservedInitialWeather(firstHomeSnapshot) {
  const observation = testState.weatherBootstrapReads.find(read => (
    read.present
    && read.istatCode === PORDENONE.municipality.istatCode
    && read.eventIndex < firstHomeSnapshot
  ));
  expect(observation).toBeTruthy();
  return observation;
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const Encoder = globalThis.TextEncoder;
  vi.stubGlobal("TextEncoder", class {
    encode(value) {
      return Uint8Array.from(new Encoder().encode(value));
    }
  });
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  window.history.replaceState({}, "", "/");
  window.localStorage.clear();
  testState.baseUrl = "";
  testState.bundleFetcher = null;
  testState.events = [];
  testState.fetchImpl = null;
  testState.journalKey = "";
  testState.now = () => NOW;
  testState.storage = null;
  testState.trackStorage = false;
  testState.weatherBootstrapReads = [];
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  container?.remove();
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ordinary App cold start through Home and Meteo", () => {
  it("keeps revoked CAMS quarantined from default Home startup through navigation to Meteo", async () => {
    await prepareScenario({ revoked: true });
    const observed = await mountOrdinaryAppOnHome();

    const { initialWeather } = observed;
    expect(initialWeather.airQuality).toBeNull();
    expect(initialWeather.pollen).toEqual({
      ambrosia: null,
      status: "unavailable",
      valueCount: 0,
    });
    expect(initialWeather.dataQuality).toEqual({
      camsDiagnosticCode: "RUN_DISABLED",
      camsDiagnosticStage: "family",
      camsRunUtc: null,
      camsStatus: "unavailable",
      iconRunUtc: RUN_B,
    });
    expect(initialWeather.primarySource).toBe("icon2i_local_pilot");
    expect(initialWeather.hourlyForecastLength).toBeGreaterThan(0);

    await navigateToWeather();
    observed.stop();

    expect(container.querySelector(".mf-weather-hourly-card")).not.toBeNull();
    expect(container.querySelector(".mf-weather-environment [data-status]")?.getAttribute("data-status"))
      .toBe("unavailable");
    expect(container.querySelector(".mf-weather-environment-tile--air").textContent).toContain("Dati non disponibili");
    expect(container.querySelector(".mf-weather-environment-tile--pollen").textContent).toContain("Dati non disponibili");
    expect(container.textContent).not.toContain("91,7");
    expect(container.textContent).not.toContain("92,7");
    expect(observed.snapshots.some(snapshot => (
      snapshot.text.includes("91,7") || snapshot.text.includes("92,7")
    ))).toBe(false);
    expect(observed.snapshots.some(snapshot => snapshot.route === "home")).toBe(true);
    expect(observed.snapshots.some(snapshot => snapshot.route === "weather")).toBe(true);
  });

  it("presents otherwise identical valid CAMS after default Home startup when no revocation exists", async () => {
    await prepareScenario({ revoked: false });
    const observed = await mountOrdinaryAppOnHome();

    const { initialWeather } = observed;
    expect(initialWeather.dataQuality).toMatchObject({
      camsRunUtc: RUN_A,
      iconRunUtc: RUN_B,
    });
    expect(initialWeather.primarySource).toBe("icon2i_local_pilot");
    expect(initialWeather.hourlyForecastLength).toBeGreaterThan(0);
    expect(initialWeather.airQuality?.pm25).toBe(AIR_MARKER);
    expect(initialWeather.pollen.ambrosia).toBe(POLLEN_MARKER);

    await navigateToWeather();
    observed.stop();

    expect(container.querySelector(".mf-weather-hourly-card")).not.toBeNull();
    expect(container.querySelector(".mf-weather-environment [data-status]")?.getAttribute("data-status"))
      .toBe("available");
    expect(container.textContent).toContain("91,7");
    expect(container.textContent).toContain("92,7");
    expect(observed.snapshots.some(snapshot => snapshot.route === "weather"
      && snapshot.text.includes("91,7"))).toBe(true);
  });
});
