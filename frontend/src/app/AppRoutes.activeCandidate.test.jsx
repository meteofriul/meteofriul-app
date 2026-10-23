// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { harness, RUN_A, RUN_B } from "../services/camsRecoveryTestFixtures";

const testState = vi.hoisted(() => ({
  baseUrl: "",
  bundleFetcher: null,
  fetchImpl: null,
  now: () => Date.now(),
  storage: null,
}));

vi.mock("../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(),
  getLocalWeatherPilotApiBase: () => testState.baseUrl,
  getLocalWeatherPilotTestNow: () => null,
  isDefinitiveAppExperience: () => true,
  isLocalWeatherPilot: () => true,
}));

vi.mock("../services/weatherApi", async importOriginal => {
  const actual = await importOriginal();
  return {
    ...actual,
    fetchWeatherBootstrap: (location, options = {}) => actual.fetchWeatherBootstrap(location, {
      ...options,
      fetchImpl: testState.fetchImpl,
      now: testState.now,
      verificationNow: testState.now,
      storage: testState.storage,
      weatherV1BaseUrl: testState.baseUrl,
      weatherV1Fetcher: testState.bundleFetcher,
    }),
    readWeatherBootstrapCache: (location, options = {}) => actual.readWeatherBootstrapCache(location, {
      ...options,
      now: testState.now,
      storage: testState.storage,
      weatherV1BaseUrl: testState.baseUrl,
    }),
  };
});

// UV has its own active/candidate runtime and suite. Keep this test focused on
// the independently persisted air/pollen family rendered by the Meteo route.
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
import {
  fetchLocalWeatherV1RuntimeBundle,
  getLocalWeatherV1BundleCacheKey,
  readLocalWeatherV1PersistedBundle,
} from "../services/localWeatherV1Runtime";

const HOUR = 3_600_000;
const PORDENONE = {
  city: "Pordenone",
  source: "manual",
  municipality: { name: "Pordenone", istatCode: "093033" },
};
const UDINE = {
  city: "Udine",
  source: "manual",
  municipality: { name: "Udine", istatCode: "030129" },
};

let root;
let container;
let settled;
let activeA;
let activeB;
let testSequence = 0;

function withEnvironmentValues(bundle, marker) {
  const result = structuredClone(bundle);
  result.current.pollen_data.values.ambrosia = marker;
  result.current.air_quality_data = {
    run_at: result.current.data_quality.cams_run_utc,
    valid_at: result.current.data_quality.cams_valid_at_utc,
    unit: "ug/m3",
    values: {
      "particulate_matter_2.5um": marker,
      "particulate_matter_10um": marker + 0.1,
      ozone: marker + 0.2,
      nitrogen_dioxide: marker + 0.3,
    },
  };
  return result;
}

function forLocation(bundle, location, marker) {
  const result = withEnvironmentValues(bundle, marker);
  const code = location.municipality.istatCode;
  result.city = location.city;
  for (const part of [result.current, result.forecast]) {
    part.city = location.city;
    part.data_quality.municipality_istat = code;
    part.source.municipality_istat = code;
    const iconEvidence = part.source.icon?.evidence;
    if (iconEvidence?.path) iconEvidence.path = iconEvidence.path.replace("093033", code);
    const camsEvidence = part.source.cams?.evidence;
    if (camsEvidence?.stages?.municipality?.path) {
      camsEvidence.stages.municipality.path = camsEvidence.stages.municipality.path.replace("093033", code);
    }
  }
  return result;
}

function pendingFrom(bundle) {
  const result = structuredClone(bundle);
  for (const part of [result.current, result.forecast]) {
    part.source.cams = { status: "pending" };
    part.data_quality.cams_status = "pending";
    part.data_quality.cams_run_utc = null;
    part.data_quality.cams_valid_at_utc = null;
  }
  result.current.air_quality_data = null;
  result.current.pollen_data = { status: "pending", values: {} };
  return result;
}

function render(location = PORDENONE, token = 0) {
  root.render(<AppRoutes
    activeLocation={location}
    activeTab="weather"
    copy={{ placeholders: { weatherTitle: "Meteo" } }}
    labEnabled={false}
    language="it"
    onRuntimeRefreshSettled={settled}
    runtimeRefreshForce={true}
    runtimeRefreshToken={token}
  />);
}

function environmentSnapshot() {
  const environment = container.querySelector(".mf-weather-environment");
  return {
    status: environment?.querySelector("[data-status]")?.getAttribute("data-status") || null,
    text: environment?.textContent || "",
  };
}

function observeEnvironmentFrames() {
  const frames = [environmentSnapshot()];
  const observer = new MutationObserver(() => frames.push(environmentSnapshot()));
  observer.observe(container, { childList: true, subtree: true, characterData: true, attributes: true });
  return { frames, stop: () => observer.disconnect() };
}

function expectAvailable(marker) {
  const snapshot = environmentSnapshot();
  expect(snapshot.status).toBe("available");
  expect(snapshot.text).toContain("Qualità dell’aria");
  expect(snapshot.text).toContain("Pollini");
  expect(snapshot.text).toContain(String(marker).replace(".", ","));
  expect(snapshot.text).not.toContain("Dati non disponibili");
}

function expectNoUnavailableFrame(frames) {
  expect(frames.filter(frame => frame.text)).toEqual(expect.not.arrayContaining([
    expect.objectContaining({ status: "unavailable" }),
  ]));
  expect(frames.some(frame => frame.text.includes("Dati non disponibili"))).toBe(false);
}

async function seed(location, bundle) {
  const seedFetcher = vi.fn().mockResolvedValue(bundle);
  await fetchLocalWeatherV1RuntimeBundle(location, {
    baseUrl: testState.baseUrl,
    bundleFetcher: seedFetcher,
    fetchImpl: testState.fetchImpl,
    force: true,
    now: testState.now,
    storage: testState.storage,
    verificationNow: testState.now,
  });
  return seedFetcher;
}

async function buildRunFixtures() {
  const source = harness({ available: true, location: PORDENONE });
  const first = await source.bundleFetcher(PORDENONE, source.options);
  expect(first.current.data_quality.cams_run_utc).toBe(RUN_A);
  source.publish();
  const second = await source.bundleFetcher(PORDENONE, source.options);
  expect(second.current.data_quality.cams_run_utc).toBe(RUN_B);
  return {
    first: forLocation(first, PORDENONE, 1.2),
    second: forLocation(second, PORDENONE, 7.2),
  };
}

beforeEach(async () => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse("2026-09-10T01:15:00Z"));
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const Encoder = globalThis.TextEncoder;
  vi.stubGlobal("TextEncoder", class {
    encode(value) { return Uint8Array.from(new Encoder().encode(value)); }
  });
  testState.baseUrl = `/active-candidate-route-${++testSequence}`;
  testState.fetchImpl = vi.fn(() => { throw new Error("Unexpected provider network request"); });
  testState.now = () => Date.now();
  window.localStorage.clear();
  testState.storage = window.localStorage;
  ({ first: activeA, second: activeB } = await buildRunFixtures());
  testState.bundleFetcher = vi.fn().mockResolvedValue(activeA);
  await seed(PORDENONE, activeA);
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  settled = vi.fn();
});

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  container?.remove();
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function mountActive() {
  await act(async () => render());
  await act(async () => vi.advanceTimersByTimeAsync(1));
  expectAvailable(1.2);
}

describe("Meteo route active + candidate integration", () => {
  it("never renders an unavailable air/pollen frame while a candidate is pending or fails", async () => {
    await mountActive();
    const pending = pendingFrom(activeA);
    testState.bundleFetcher.mockImplementation((_location, options) => {
      setTimeout(() => options.onCamsFailure?.(new Error("controlled CAMS failure")), 1_500);
      return pending;
    });
    const observed = observeEnvironmentFrames();

    await act(async () => {
      render(PORDENONE, 1);
      await vi.advanceTimersByTimeAsync(10);
    });
    expectAvailable(1.2);
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    observed.stop();

    expectAvailable(1.2);
    expectNoUnavailableFrame(observed.frames);
    expect(readLocalWeatherV1PersistedBundle(PORDENONE, {
      baseUrl: testState.baseUrl,
      now: testState.now,
      storage: testState.storage,
    }).current.data_quality.cams_run_utc).toBe(RUN_A);
  });

  it("replaces a fully saved candidate without a blank frame and reopens it offline", async () => {
    await mountActive();
    const pending = pendingFrom(activeA);
    testState.bundleFetcher.mockImplementation((_location, options) => {
      setTimeout(() => options.onCamsUpdate?.(activeB), 1_500);
      return pending;
    });
    const observed = observeEnvironmentFrames();

    await act(async () => {
      render(PORDENONE, 1);
      await vi.advanceTimersByTimeAsync(10);
    });
    expectAvailable(1.2);
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    observed.stop();
    expectAvailable(7.2);
    expectNoUnavailableFrame(observed.frames);

    const key = getLocalWeatherV1BundleCacheKey(PORDENONE, { baseUrl: testState.baseUrl });
    expect(JSON.parse(testState.storage.getItem(key)).bundle.current.data_quality.cams_run_utc).toBe(RUN_B);

    await act(async () => root.unmount());
    root = createRoot(container);
    vi.setSystemTime(Date.now() + 11 * 60_000);
    testState.bundleFetcher = vi.fn().mockRejectedValue(new Error("offline after reopen"));
    const reopenedFrames = observeEnvironmentFrames();
    await act(async () => {
      render();
      await vi.advanceTimersByTimeAsync(10);
    });
    reopenedFrames.stop();
    expectAvailable(7.2);
    expectNoUnavailableFrame(reopenedFrames.frames);
    expect(testState.bundleFetcher).toHaveBeenCalled();
  });

  it("keeps the rendered and durable active data when candidate persistence is interrupted", async () => {
    await mountActive();
    const activeKey = getLocalWeatherV1BundleCacheKey(PORDENONE, { baseUrl: testState.baseUrl });
    const storedActive = window.localStorage.getItem(activeKey);
    const pending = pendingFrom(activeA);
    testState.storage = {
      getItem: key => window.localStorage.getItem(key),
      removeItem: key => window.localStorage.removeItem(key),
      setItem: (key, value) => {
        if (key.endsWith(":candidate")) throw new Error("controlled interrupted candidate write");
        window.localStorage.setItem(key, value);
      },
    };
    testState.bundleFetcher.mockImplementation((_location, options) => {
      setTimeout(() => options.onCamsUpdate?.(activeB), 1_500);
      return pending;
    });
    const observed = observeEnvironmentFrames();

    await act(async () => {
      render(PORDENONE, 1);
      await vi.advanceTimersByTimeAsync(10);
    });
    expectAvailable(1.2);
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    observed.stop();

    expectAvailable(1.2);
    expectNoUnavailableFrame(observed.frames);
    expect(window.localStorage.getItem(activeKey)).toBe(storedActive);
    expect(readLocalWeatherV1PersistedBundle(PORDENONE, {
      baseUrl: testState.baseUrl,
      now: testState.now,
      storage: testState.storage,
    }).current.data_quality.cams_run_utc).toBe(RUN_A);
  });

  it("remounts for another ISTAT, ignores the old callback and retains both location caches", async () => {
    await mountActive();
    const udine = forLocation(activeB, UDINE, 8.2);
    const pending = pendingFrom(activeA);
    testState.bundleFetcher.mockImplementation((location, options) => {
      if (location.municipality.istatCode === PORDENONE.municipality.istatCode) {
        setTimeout(() => options.onCamsUpdate?.(activeB), 2_000);
        return pending;
      }
      return udine;
    });

    await act(async () => {
      render(PORDENONE, 1);
      await vi.advanceTimersByTimeAsync(10);
    });
    expectAvailable(1.2);
    const afterLocationChange = observeEnvironmentFrames();
    await act(async () => {
      render(UDINE, 1);
      await vi.advanceTimersByTimeAsync(10);
    });
    expectAvailable(8.2);
    await act(async () => vi.advanceTimersByTimeAsync(2_000));
    afterLocationChange.stop();

    expectAvailable(8.2);
    // The observer's explicit first snapshot is the still-current Pordenone
    // view taken before React receives the new location. Every committed frame
    // after that point must be either loading/empty or Udine, never Pordenone.
    expect(afterLocationChange.frames.slice(1).some(frame => frame.text.includes("1,2"))).toBe(false);
    const pordenoneCache = readLocalWeatherV1PersistedBundle(PORDENONE, {
      baseUrl: testState.baseUrl, now: testState.now, storage: testState.storage,
    });
    const udineCache = readLocalWeatherV1PersistedBundle(UDINE, {
      baseUrl: testState.baseUrl, now: testState.now, storage: testState.storage,
    });
    expect(pordenoneCache.current.data_quality.municipality_istat).toBe("093033");
    expect(udineCache.current.data_quality.municipality_istat).toBe("030129");
    expect(getLocalWeatherV1BundleCacheKey(PORDENONE, { baseUrl: testState.baseUrl }))
      .not.toBe(getLocalWeatherV1BundleCacheKey(UDINE, { baseUrl: testState.baseUrl }));
  });
});
