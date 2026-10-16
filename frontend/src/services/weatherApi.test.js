import { afterEach, describe, expect, it, vi } from "vitest";

import { API_BASE } from "./apiConfig";
import * as localWeatherPilot from "./localWeatherPilot";
import { LOCAL_WEATHER_V1_CATALOG } from "./localWeatherV1Adapter";
import { clearNationalWeatherV2CamsRuntime } from "./nationalWeatherV2Cams";
import { loadHomeWeather } from "../features/home/homeDataController";

import {
  buildWeatherBootstrapUrl,
  fetchWeatherBootstrap,
  normalizeWeatherBootstrapPayload,
  readWeatherBootstrapCache,
} from "./weatherApi";

const RUN_AT = "2026-09-03T00:00:00Z";
const VALID_AT = "2026-09-03T10:00:00Z";
const modelNow = () => Date.parse(VALID_AT);

function memoryStorage() {
  const values = new Map();
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  };
}

function verifiedIconBundle({ camsStatus = "unavailable" } = {}) {
  const camsAvailable = camsStatus === "fresh";
  const source = {
    active: "icon2i_local_pilot",
    primary_source: "icon2i_local_pilot",
    municipality_istat: "030129",
    catalog: LOCAL_WEATHER_V1_CATALOG,
    icon: {
      status: "available",
      evidence: { path: "runs/20260903T000000Z/municipalities/030129.json", etag: '"icon-1"' },
    },
    cams: {
      status: camsAvailable ? "available" : camsStatus,
      evidence: camsAvailable ? {
        family: { revision: 1, published_at: "2026-09-03T02:00:00Z", active_run_id: "20260903T000000Z", disabled_run_ids: [] },
        stages: {
          latest: { path: "families/cams/runs/20260903T000000Z/release.json#pollen", etag: '"cams-1"' },
          manifest: { path: "runs/20260903T000000Z/manifest.json" },
          municipality: { path: "runs/20260903T000000Z/municipalities/030129.json" },
        },
      } : null,
    },
  };
  const dataQuality = {
    mode: "local_contract_v1",
    catalog_version: LOCAL_WEATHER_V1_CATALOG.version,
    catalog_sha256: LOCAL_WEATHER_V1_CATALOG.sha256,
    municipality_istat: "030129",
    run_utc: RUN_AT,
    valid_at_utc: VALID_AT,
    cams_status: camsStatus,
    cams_run_utc: camsAvailable ? RUN_AT : null,
    cams_valid_at_utc: camsAvailable ? VALID_AT : null,
    flags: [],
  };
  return {
    city: "Udine",
    current: {
      city: "Udine", temperature: 15, primary_source: "icon2i_local_pilot", source,
      data_quality: dataQuality,
      hourly_forecast: Array.from({ length: 48 }, (_, index) => ({
        time: new Date(modelNow() + (index + 1) * 3600000).toISOString(), temperature: 15,
      })),
      pollen_data: { status: camsAvailable ? "experimental_model_snapshot" : camsStatus },
    },
    forecast: {
      city: "Udine", daily: [], daily_extrema_version: 2,
      primary_source: "icon2i_local_pilot", source, data_quality: { ...dataQuality },
    },
  };
}

afterEach(() => {
  clearNationalWeatherV2CamsRuntime();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("weather api service", () => {
  it("keeps the default API unchanged outside the local pilot", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    expect(buildWeatherBootstrapUrl("Udine")).toBe(`${API_BASE}/weather/bootstrap?city=Udine`);
  });

  it("routes only the omitted API base to the pilot and preserves explicit injection", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    expect(buildWeatherBootstrapUrl("Udine")).toBe("/__local-weather-pilot/weather/bootstrap?city=Udine");
    expect(buildWeatherBootstrapUrl("Udine", { apiBase: "/api" })).toBe("/api/weather/bootstrap?city=Udine");
    expect(buildWeatherBootstrapUrl("Udine", { apiBase: "/test-api" })).toBe("/test-api/weather/bootstrap?city=Udine");
  });

  it("delegates the pilot to weather v1 and never calls the ordinary API", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const fetchImpl = vi.fn();
    const storage = memoryStorage();
    const now = vi.fn().mockReturnValue(123);
    const weatherV1Fetcher = vi.fn().mockRejectedValue(new Error("v1 unavailable"));

    await expect(fetchWeatherBootstrap("Udine", {
      fetchImpl, now, storage, weatherV1Fetcher,
    })).rejects.toThrow("v1 unavailable");
    expect(weatherV1Fetcher).toHaveBeenCalledWith("Udine", {
      baseUrl: "/__local-weather-pilot",
      fetchImpl,
      force: false,
      now,
      onCamsFamilyLatest: expect.any(Function),
      onIconLatest: expect.any(Function),
      storage,
    });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("rejects Roma without making an Open-Meteo request while the autonomous pilot is active", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const roma = {
      city: "Roma",
      countryCode: "IT",
      region: "Lazio",
      regionCode: "IT-62",
      lat: 41.8933,
      lon: 12.4829,
    };
    const fetchImpl = vi.fn();
    const weatherV1Fetcher = vi.fn();

    await expect(fetchWeatherBootstrap(roma, {
      fetchImpl,
      weatherV1Fetcher,
    })).rejects.toMatchObject({ code: "weather_provider_location_not_enabled" });
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(weatherV1Fetcher).not.toHaveBeenCalled();
  });

  it("uses national v2 as the pilot primary for both FVG and the rest of Italy", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    vi.spyOn(localWeatherPilot, "isLocalWeatherNationalPilot").mockReturnValue(true);
    vi.spyOn(localWeatherPilot, "getLocalWeatherNationalApiBase")
      .mockReturnValue("http://127.0.0.1:8782");
    const nationalFetcher = vi.fn(async location => {
      const bundle = verifiedIconBundle();
      bundle.current.source.municipality_istat = location.city === "Roma" ? "058091" : "030129";
      return bundle;
    });
    const nationalCamsFetcher = vi.fn().mockResolvedValue({
      municipality_istat: "030129", catalog: LOCAL_WEATHER_V1_CATALOG, available: false, status: "unavailable",
    });
    const weatherV1Fetcher = vi.fn();
    const fetchImpl = vi.fn();
    const locations = [
      { city: "Udine", countryCode: "IT", regionCode: "IT-36", province: "UD" },
      { city: "Roma", countryCode: "IT", regionCode: "IT-62", province: "RM" },
    ];

    for (const location of locations) {
      await expect(fetchWeatherBootstrap(location, {
        fetchImpl,
        nationalFetcher,
        nationalCamsFetcher,
        weatherV1Fetcher,
        nationalBaseUrl: "http://127.0.0.1:8782",
        storage: null,
      })).resolves.toMatchObject({ current: { primary_source: "icon2i_local_pilot" } });
    }
    expect(nationalFetcher).toHaveBeenCalledTimes(2);
    expect(nationalFetcher).toHaveBeenCalledWith(locations[1], expect.objectContaining({
      baseUrl: "http://127.0.0.1:8782",
      fetchImpl,
      force: false,
      storage: null,
    }));
    expect(weatherV1Fetcher).not.toHaveBeenCalled();
    expect(nationalCamsFetcher).toHaveBeenCalledTimes(1);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("passes late national/FVG CAMS through Home normalization and the national cache reader", async () => {
    vi.useFakeTimers();
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    vi.spyOn(localWeatherPilot, "isLocalWeatherNationalPilot").mockReturnValue(true);
    vi.spyOn(localWeatherPilot, "getLocalWeatherPilotApiBase").mockReturnValue("https://meteofriul-weather-49007668366.europe-west1.run.app");
    const national = verifiedIconBundle();
    national.current.data_quality.mode = "national_contract_v2";
    national.current.data_quality.catalog_sha256 = "national-catalog";
    national.current.source.contract = "weather/v2/icon2i";
    const location = { city: "Udine", countryCode: "IT", province: "UD", municipality: { istatCode: "030129" } };
    let complete;
    const nationalCamsFetcher = vi.fn(() => new Promise(resolve => { complete = resolve; }));
    const fetchImpl = vi.fn();
    const options = { fetchImpl, now: modelNow, verificationNow: modelNow,
      nationalFetcher: vi.fn().mockResolvedValue(national), nationalCamsFetcher, storage: null };
    const onCamsUpdate = vi.fn();
    const weatherCacheWriter = vi.fn();
    const first = await loadHomeWeather(location, {
      now: modelNow, storage: null, deferCams: true, manageOfficialAlerts: false, onCamsUpdate,
      weatherCacheReader: vi.fn().mockReturnValue(null), weatherCacheWriter,
      weatherFetcher: (selected, opts) => fetchWeatherBootstrap(selected, { ...options, ...opts }),
    });
    expect(first.rawCurrent.temperature).toBe(15);
    expect(first.rawCurrent.data_quality.cams_status).toBe("pending");
    complete({ municipality_istat: "030129", catalog: LOCAL_WEATHER_V1_CATALOG, available: true, status: "fresh",
      source: { status: "available", provider: "cams_europe_pollen" },
      pollen_data: { status: "experimental_model_snapshot", valid_at_utc: VALID_AT, run_utc: RUN_AT,
        values: { graminacee: 1.35 } },
      air_quality_data: { valid_at: VALID_AT, values: { ozone: 85.3 } },
      fresh_until_utc: "2026-09-04T00:00:00Z", usable_until_utc: "2026-09-04T06:00:00Z" });
    await vi.runAllTimersAsync();
    expect(onCamsUpdate).toHaveBeenCalledTimes(1);
    expect(onCamsUpdate.mock.calls[0][0].rawCurrent).toMatchObject({ temperature: 15,
      pollen_data: { values: { graminacee: 1.35 } }, air_quality_data: { values: { ozone: 85.3 } },
      source: { contract: "weather/v2/icon2i" }, data_quality: { mode: "national_contract_v2", catalog_sha256: "national-catalog" } });
    expect(weatherCacheWriter.mock.calls.at(-1)[1].current.data_quality.cams_status).toBe("fresh");
    expect(readWeatherBootstrapCache(location, { now: modelNow, verificationNow: modelNow,
      storage: null, nationalBundleReader: () => national })).toMatchObject({
      current: { data_quality: { cams_status: "fresh" }, air_quality_data: { values: { ozone: 85.3 } } },
    });
    expect(nationalCamsFetcher).toHaveBeenCalledWith(expect.objectContaining({ municipality: { istatCode: "030129", name: "Udine" } }),
      expect.objectContaining({ baseUrl: "https://meteofriul-weather-49007668366.europe-west1.run.app" }));
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("does not replace failed national ICON with regional or official weather", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    vi.spyOn(localWeatherPilot, "isLocalWeatherNationalPilot").mockReturnValue(true);
    const fetchImpl = vi.fn();
    const weatherV1Fetcher = vi.fn();
    const nationalCamsFetcher = vi.fn();
    await expect(fetchWeatherBootstrap({ city: "Pordenone", province: "PN" }, {
      fetchImpl, weatherV1Fetcher, nationalCamsFetcher,
      nationalFetcher: vi.fn().mockRejectedValue(new Error("national unavailable")),
    })).rejects.toThrow("national unavailable");
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(weatherV1Fetcher).not.toHaveBeenCalled();
    expect(nationalCamsFetcher).not.toHaveBeenCalled();
  });

  it("uses the declared pilot clock only for the autonomous model data", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    vi.spyOn(localWeatherPilot, "getLocalWeatherPilotTestNow")
      .mockReturnValue("2026-09-04T05:00:00Z");
    vi.spyOn(localWeatherPilot, "getLocalWeatherPilotNow")
      .mockReturnValue(Date.parse("2026-09-04T05:00:00Z"));
    const requestClock = vi.fn().mockReturnValue(999);
    const weatherV1Fetcher = vi.fn().mockRejectedValue(new Error("stop after options"));

    await expect(fetchWeatherBootstrap("Udine", {
      now: requestClock,
      weatherV1Fetcher,
    })).rejects.toThrow("stop after options");

    const modelClock = weatherV1Fetcher.mock.calls[0][1].now;
    expect(modelClock).not.toBe(requestClock);
    expect(modelClock()).toBe(Date.parse("2026-09-04T05:00:00Z"));
    expect(requestClock).not.toHaveBeenCalled();
  });

  it("routes an autonomous production configuration to weather v1 with no provider fallback", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    const fetchImpl = vi.fn();
    const weatherV1Fetcher = vi.fn().mockRejectedValue(new Error("autonomous v1 offline"));

    await expect(fetchWeatherBootstrap("Udine", {
      fetchImpl,
      providerConfig: { primary: "autonomous" },
      storage: null,
      weatherV1BaseUrl: "https://weather.example.test/data",
      weatherV1Fetcher,
    })).rejects.toThrow("autonomous v1 offline");
    expect(weatherV1Fetcher).toHaveBeenCalledWith("Udine", expect.objectContaining({
      baseUrl: "https://weather.example.test/data",
      fetchImpl,
      storage: null,
    }));
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("fails closed without throwing when the cached-read provider is invalid", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    const runtimeBundleReader = vi.fn();

    expect(readWeatherBootstrapCache("Udine", {
      providerConfig: { primary: "invalid-provider" },
      runtimeBundleReader,
    })).toBeNull();
    expect(runtimeBundleReader).not.toHaveBeenCalled();
  });

  it("fails closed without reading the cache when the autonomous base URL is invalid", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    const runtimeBundleReader = vi.fn();

    expect(readWeatherBootstrapCache("Udine", {
      providerConfig: { primary: "autonomous" },
      runtimeBundleReader,
      weatherV1BaseUrl: "https://weather.example.test/data?invalid=1",
    })).toBeNull();
    expect(runtimeBundleReader).not.toHaveBeenCalled();
  });

  it("fails closed without throwing when the persisted runtime reader fails", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    const runtimeBundleReader = vi.fn(() => {
      throw new Error("persisted cache unavailable");
    });

    expect(readWeatherBootstrapCache("Udine", {
      providerConfig: { primary: "autonomous" },
      runtimeBundleReader,
      weatherV1BaseUrl: "https://weather.example.test/data",
    })).toBeNull();
    expect(runtimeBundleReader).toHaveBeenCalledOnce();
  });

  it("uses the autonomous build configuration in the real bootstrap request", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    vi.stubEnv("VITE_WEATHER_PROVIDER_PRIMARY", "autonomous");
    vi.stubEnv("VITE_WEATHER_V1_BASE_URL", "https://weather.example.test/v1-data");
    const fetchImpl = vi.fn();
    const weatherV1Fetcher = vi.fn().mockResolvedValue(verifiedIconBundle());

    await expect(fetchWeatherBootstrap("Udine", {
      fetchImpl,
      now: modelNow,
      storage: null,
      weatherV1Fetcher,
    })).resolves.toMatchObject({
      city: "Udine",
      current: { temperature: 15 },
    });
    expect(weatherV1Fetcher).toHaveBeenCalledWith("Udine", expect.objectContaining({
      baseUrl: "https://weather.example.test/v1-data",
    }));
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("honors the explicit current Open-Meteo operator setting", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        city: "Udine",
        current: { temperature: 12 },
        forecast: { daily: [] },
      }),
    });
    const weatherV1Fetcher = vi.fn();

    await fetchWeatherBootstrap("Udine", {
      apiBase: "/api",
      fetchImpl,
      providerConfig: {
        primary: "open_meteo",
        operatorOverride: "open_meteo",
      },
      weatherV1Fetcher,
    });

    expect(fetchImpl).toHaveBeenCalledWith("/api/weather/bootstrap?city=Udine", {
      cache: "default",
    });
    expect(weatherV1Fetcher).not.toHaveBeenCalled();
  });

  it("does not permit an implicit Open-Meteo selection", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    const fetchImpl = vi.fn();
    const weatherV1Fetcher = vi.fn();

    await expect(fetchWeatherBootstrap("Udine", {
      fetchImpl,
      providerConfig: { primary: "open_meteo" },
      weatherV1Fetcher,
    })).rejects.toMatchObject({
      code: "weather_provider_open_meteo_requires_operator_override",
    });
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(weatherV1Fetcher).not.toHaveBeenCalled();
  });

  it("normalizes v1 bootstrap without synthesizing official fields", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const weatherV1Fetcher = vi.fn().mockResolvedValue(verifiedIconBundle());

    const result = await fetchWeatherBootstrap("Udine", {
      fetchImpl: vi.fn(),
      now: modelNow,
      storage: memoryStorage(),
      weatherV1Fetcher,
    });
    expect(result.current.primary_source).toBe("icon2i_local_pilot");
    expect(result.officialAlerts).toBeNull();
    expect(result.osmerAudit).toBeNull();
  });

  it("espone subito il bootstrap locale defer e normalizza il supplemento CAMS", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    let publishCams;
    let publishCamsFailure;
    const weatherV1Fetcher = vi.fn((_location, options) => {
      publishCams = options.onCamsUpdate;
      publishCamsFailure = options.onCamsFailure;
      return verifiedIconBundle({ camsStatus: "pending" });
    });
    const onCamsUpdate = vi.fn();
    const onCamsFailure = vi.fn();

    const initial = await fetchWeatherBootstrap("Udine", {
      deferCams: true,
      fetchImpl: vi.fn(),
      now: modelNow,
      onCamsUpdate,
      onCamsFailure,
      storage: memoryStorage(),
      weatherV1Fetcher,
    });

    expect(initial.current.data_quality.cams_status).toBe("pending");
    expect(weatherV1Fetcher).toHaveBeenCalledWith("Udine", expect.objectContaining({
      deferCams: true,
      onCamsFailure: expect.any(Function),
      onCamsUpdate: expect.any(Function),
    }));
    publishCams(verifiedIconBundle({ camsStatus: "fresh" }));

    await vi.waitFor(() => expect(onCamsUpdate).toHaveBeenCalledOnce());
    expect(onCamsUpdate.mock.calls[0][0]).toMatchObject({
      city: "Udine",
      current: { data_quality: { cams_status: "fresh" } },
      officialAlerts: null,
      osmerAudit: null,
    });
    const durabilityError = Object.assign(new Error("journal non persistito"), {
      code: "CAMS_REVOCATION_PERSIST_FAILED",
    });
    publishCamsFailure(durabilityError);
    expect(onCamsFailure).toHaveBeenCalledWith(durabilityError);
  });

  it("propaga il refresh forzato al runtime locale v1", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const weatherV1Fetcher = vi.fn().mockResolvedValue(verifiedIconBundle());
    await fetchWeatherBootstrap("Udine", {
      fetchImpl: vi.fn(),
      force: true,
      now: modelNow,
      storage: null,
      weatherV1Fetcher,
    });

    expect(weatherV1Fetcher).toHaveBeenCalledWith(
      "Udine",
      expect.objectContaining({ force: true, storage: null }),
    );
  });

  it("continues the local v1 request when the global localStorage getter is blocked", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const descriptor = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
    const weatherV1Fetcher = vi.fn().mockResolvedValue(verifiedIconBundle());
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      get() {
        throw new Error("storage denied");
      },
    });
    try {
      await expect(fetchWeatherBootstrap("Udine", {
        fetchImpl: vi.fn(),
        now: modelNow,
        weatherV1Fetcher,
      })).resolves.toMatchObject({ city: "Udine" });
      expect(weatherV1Fetcher).toHaveBeenCalledWith(
        "Udine",
        expect.objectContaining({ storage: null }),
      );
    } finally {
      if (descriptor) Object.defineProperty(globalThis, "localStorage", descriptor);
      else delete globalThis.localStorage;
    }
  });

  it("keeps the municipality in the API query while using locality coordinates", () => {
    const url = buildWeatherBootstrapUrl(
      {
        city: "Fontanafredda",
        displayName: "Vigonovo",
        lat: 45.9892,
        lon: 12.5473,
        locality: { id: "irdat:vigonovo", name: "Vigonovo" },
        municipality: { istatCode: "093022", name: "Fontanafredda" },
      },
      { apiBase: "/api" },
    );

    expect(url).toBe("/api/weather/bootstrap?city=Fontanafredda&lat=45.9892&lon=12.5473");
  });

  it("adds a cache buster and no-store mode when forced", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        city: "Udine",
        current: { temperature: 12 },
        forecast: { daily: [] },
      }),
    });

    await fetchWeatherBootstrap("Udine", {
      apiBase: "/api",
      fetchImpl,
      force: true,
      now: () => 123,
      providerConfig: {
        primary: "open_meteo",
        operatorOverride: "open_meteo",
      },
    });

    expect(fetchImpl).toHaveBeenCalledWith("/api/weather/bootstrap?city=Udine&_=123", {
      cache: "no-store",
    });
  });

  it("normalizes bootstrap payload fields used by the app", () => {
    const payload = normalizeWeatherBootstrapPayload(
      {
        city: "Pordenone",
        current: { weathercode: 3 },
        forecast: { daily: [] },
        official_alerts: [{ id: "alert-1" }],
        osmer_audit: { storage_active: "firestore" },
      },
      { fallbackCity: "Fallback" },
    );

    expect(payload.city).toBe("Pordenone");
    expect(payload.officialAlerts).toEqual([{ id: "alert-1" }]);
    expect(payload.osmerAudit).toEqual({ storage_active: "firestore" });
  });

  it("rejects missing or incomplete weather data", () => {
    expect(() => normalizeWeatherBootstrapPayload({ current: {}, forecast: null })).toThrow(
      "Dati meteo mancanti",
    );

    expect(() =>
      normalizeWeatherBootstrapPayload({
        current: { humidity: 80 },
        forecast: { daily: [] },
      }),
    ).toThrow("Dati meteo incompleti");
  });

  it("can relax current completeness for bulletin-only bootstrap reads", () => {
    const payload = normalizeWeatherBootstrapPayload(
      {
        current: { official: { it: { forecasts: [{ text: "Sole" }] } } },
        forecast: { daily: [] },
      },
      { requireCompleteCurrent: false },
    );

    expect(payload.current.official.it.forecasts[0].text).toBe("Sole");
  });
});
