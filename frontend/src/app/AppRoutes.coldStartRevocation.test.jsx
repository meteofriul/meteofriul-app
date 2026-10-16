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
  initialHomeReads: [],
  journalKey: "",
  nativeObject: null,
  now: () => Date.now(),
  storage: null,
  trackJournal: false,
}));

vi.mock("../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(),
  getLocalWeatherPilotApiBase: () => testState.baseUrl,
  getLocalWeatherPilotTestNow: () => null,
  isDefinitiveAppExperience: () => true,
  isLocalWeatherPilot: () => true,
}));

vi.mock("../services/pilotWeatherPrefetch", async importOriginal => ({
  ...await importOriginal(),
  getPilotWeatherPrefetchReader: () => {
    testState.events.push("native:reader-ready");
    return async () => {
      testState.events.push("native:object-read");
      return testState.nativeObject;
    };
  },
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

vi.mock("../features/weather/WeatherSkyCard", () => ({ WeatherSkyCard: () => null }));
vi.mock("../features/weather/WeatherUvCard", () => ({
  UvCurve: () => null,
  WeatherUvCard: () => null,
  WeatherUvContent: () => null,
}));
vi.mock("../features/weather/useWeatherUvCardState", () => ({
  useWeatherUvCardState: () => ({ error: null, forecastDate: "", model: null, saved: false }),
}));

// Keep the Home-route proof focused on the weather presentation boundary.
// Events and the regional bulletin have independent startup paths and may
// legitimately remain pending while the first Home frame is inspected.
vi.mock("../features/bulletin/bulletinDataController", async importOriginal => ({
  ...await importOriginal(),
  loadBulletinData: () => new Promise(() => {}),
  readInitialBulletinData: () => null,
}));

vi.mock("../features/home/homeDataController", async importOriginal => {
  const actual = await importOriginal();
  return {
    ...actual,
    loadHomeEvents: () => new Promise(() => {}),
    readInitialHomeData: (...args) => {
      const result = actual.readInitialHomeData(...args);
      testState.initialHomeReads.push(result);
      testState.events.push("home-data:initial-read");
      return result;
    },
  };
});

import { AppRoutes } from "./AppRoutes";
import { fetchLocalWeatherV1Bootstrap, LOCAL_WEATHER_V1_CATALOG } from "../services/localWeatherV1Adapter";
import {
  getLocalWeatherV1BundleCacheKey,
  getLocalWeatherV1CamsFamilyDecisionCacheKey,
} from "../services/localWeatherV1Runtime";
import { canonicalJsonStringify, sha256Hex } from "../services/weatherV1Client";

const PORDENONE = {
  city: "Pordenone",
  source: "manual",
  municipality: { name: "Pordenone", istatCode: "093033" },
};
const NOW = START + 11 * 60_000;
const REVOKED_AIR_MARKER = 91.7;
const REVOKED_POLLEN_MARKER = 92.7;
let sequence = 0;
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
      if (testState.trackJournal && key === testState.journalKey) {
        testState.events.push("journal:get");
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

function writeDurableRevocation(storage, baseUrl) {
  const payload = {
    kind: "meteofriul.weather.cams_family_decision",
    version: 1,
    scope_sha256: sha256Hex(baseUrl),
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
  testState.journalKey = getLocalWeatherV1CamsFamilyDecisionCacheKey({ baseUrl });
  storage.setItem(testState.journalKey, JSON.stringify(record));
}

async function buildRevokedActive() {
  const source = harness({ available: true, location: PORDENONE });
  const active = await source.bundleFetcher(PORDENONE, source.options);
  expect(active.current.data_quality.cams_run_utc).toBe(RUN_A);
  active.current.air_quality_data = {
    run_at: active.current.data_quality.cams_run_utc,
    valid_at: active.current.data_quality.cams_valid_at_utc,
    unit: "ug/m3",
    values: {
      "particulate_matter_2.5um": REVOKED_AIR_MARKER,
      "particulate_matter_10um": 91.8,
      ozone: 91.9,
      nitrogen_dioxide: 92,
    },
  };
  active.current.pollen_data.values.ambrosia = REVOKED_POLLEN_MARKER;
  return active;
}

function renderRoute(activeTab) {
  root.render(<AppRoutes
    activeLocation={PORDENONE}
    activeTab={activeTab}
    copy={{ placeholders: { homeTitle: "Home", weatherTitle: "Meteo" } }}
    labEnabled={false}
    language="it"
  />);
}

async function observeColdStart(activeTab) {
  const frames = [];
  const observer = new MutationObserver(() => {
    const text = container.textContent || "";
    frames.push(text);
    testState.events.push(`dom:${text}`);
  });
  observer.observe(container, {
    attributes: true,
    characterData: true,
    childList: true,
    subtree: true,
  });

  expect(testState.events).toEqual([]);
  testState.events.push("render:invoke");
  await act(async () => {
    renderRoute(activeTab);
    await Promise.resolve();
  });
  await vi.waitFor(() => {
    expect(testState.events).toContain("native:object-read");
    expect(frames.some(Boolean)).toBe(true);
  });
  observer.disconnect();

  return frames;
}

function expectJournalBeforePresentation(frames) {
  const journalRead = testState.events.indexOf("journal:get");
  const nativeRead = testState.events.indexOf("native:object-read");
  const firstDomFrame = testState.events.findIndex(event => event.startsWith("dom:") && event !== "dom:");
  expect(journalRead).toBeGreaterThan(testState.events.indexOf("render:invoke"));
  expect(journalRead).toBeLessThan(firstDomFrame);
  expect(journalRead).toBeLessThan(nativeRead);

  for (const frame of frames) {
    expect(frame).not.toContain("91,7");
    expect(frame).not.toContain("92,7");
  }
}

beforeEach(async () => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const Encoder = globalThis.TextEncoder;
  vi.stubGlobal("TextEncoder", class {
    encode(value) {
      return Uint8Array.from(new Encoder().encode(value));
    }
  });
  testState.baseUrl = `/cold-start-revocation-${++sequence}`;
  testState.events = [];
  testState.fetchImpl = vi.fn();
  testState.initialHomeReads = [];
  testState.now = () => NOW;
  testState.storage = createTrackedStorage();
  testState.trackJournal = false;

  const active = await buildRevokedActive();
  active.current.source.cams.evidence.family = {
    revision: 1,
    published_at: "2026-09-09T01:00:00Z",
    active_run_id: sourceRunId(RUN_A),
    disabled_run_ids: [],
  };
  active.forecast.source.cams.evidence.family = {
    ...active.current.source.cams.evidence.family,
  };
  const bundleKey = getLocalWeatherV1BundleCacheKey(PORDENONE, {
    baseUrl: testState.baseUrl,
  });
  testState.storage.setItem(bundleKey, JSON.stringify({
    version: 4,
    municipality: "istat:093033",
    verifiedAt: START,
    camsVerifiedAt: START,
    bundle: active,
  }));
  writeDurableRevocation(testState.storage, testState.baseUrl);

  // The adapter receives a native reader, then waits on an immutable object.
  // This keeps the post-render refresh open while the first frame is inspected.
  testState.nativeObject = new Promise(() => {});
  testState.bundleFetcher = (location, options) => fetchLocalWeatherV1Bootstrap(location, {
    ...options,
    clientFactory: clientOptions => ({
      icon2i: {
        fetchLatest: async () => {
          await clientOptions.readPrefetchedObject({
            provider: "icon2i",
            path: "runs/20260910T000000Z/municipalities/093033.json",
            sha256: "a".repeat(64),
          });
          return new Promise(() => {});
        },
      },
    }),
  });

  testState.events = [];
  testState.trackJournal = true;
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

describe("localPilot cold-start revocation presentation boundary", () => {
  it("applies the durable journal before the first Meteo frame and before native objects can be read", async () => {
    const frames = await observeColdStart("weather");

    expectJournalBeforePresentation(frames);

    expect(container.querySelector(".mf-weather-hourly-card")).not.toBeNull();
    expect(container.querySelector(".mf-weather-environment [data-status]")?.getAttribute("data-status"))
      .toBe("unavailable");
    expect(container.textContent).toContain("Dati dell’aria non disponibili");
    expect(container.textContent).toContain("Dati pollinici non disponibili");
  });

  it("applies the durable journal before the first Home landing frame and native object read", async () => {
    const frames = await observeColdStart("home");

    expectJournalBeforePresentation(frames);
    const journalRead = testState.events.indexOf("journal:get");
    const initialHomeRead = testState.events.indexOf("home-data:initial-read");
    const firstDomFrame = testState.events.findIndex(event => event.startsWith("dom:") && event !== "dom:");
    expect(journalRead).toBeLessThan(initialHomeRead);
    expect(initialHomeRead).toBeLessThan(firstDomFrame);

    const initialCurrent = testState.initialHomeReads[0]?.weather?.rawCurrent;
    expect(initialCurrent?.air_quality_data).toBeNull();
    expect(initialCurrent?.pollen_data).toMatchObject({ status: "unavailable" });
    expect(initialCurrent?.pollen_data?.values).toEqual({});
    expect(initialCurrent?.data_quality).toMatchObject({
      cams_diagnostic: { code: "RUN_DISABLED", stage: "family" },
      cams_run_utc: null,
      cams_status: "unavailable",
    });
    expect(container.querySelector(".mf-tab-page--home")).not.toBeNull();
    expect(container.querySelector(".mf-home-view")).not.toBeNull();
    expect(container.querySelector(".mf-home-hero")).not.toBeNull();
    expect(container.querySelector(".mf-home-temperature")).not.toBeNull();
  });
});
