import { afterEach, describe, expect, it, vi } from "vitest";

import { API_BASE } from "./apiConfig";
import * as localWeatherPilot from "./localWeatherPilot";
import { LOCAL_WEATHER_V1_CATALOG } from "./localWeatherV1Adapter";

import {
  buildLocalConditionsUrl,
  fetchLocalConditions,
  normalizeLocalConditionsPayload,
} from "./localConditionsApi";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

function jsonResponse(payload, { ok = true } = {}) {
  return {
    ok,
    json: vi.fn().mockResolvedValue(payload),
  };
}

describe("local conditions api", () => {
  it("keeps the ordinary default API when the pilot is disabled", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    expect(buildLocalConditionsUrl("Udine")).toBe(`${API_BASE}/weather/current?city=Udine`);
  });

  it("routes the default current request to the pilot without changing an injected base", () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    expect(buildLocalConditionsUrl("Udine")).toBe("/__local-weather-pilot/weather/current?city=Udine");
    expect(buildLocalConditionsUrl("Udine", { apiBase: "/api" })).toBe("/api/weather/current?city=Udine");
    expect(buildLocalConditionsUrl("Udine", { apiBase: "/test-api" })).toBe("/test-api/weather/current?city=Udine");
  });

  it("delegates pilot current to weather v1 and does not fall back after an error", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const fetchImpl = vi.fn();
    const storage = { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn() };
    const now = vi.fn().mockReturnValue(123);
    const weatherV1Fetcher = vi.fn().mockRejectedValue(new Error("pilot v1 offline"));
    await expect(fetchLocalConditions("Udine", {
      fetchImpl, now, storage, weatherV1Fetcher,
    })).rejects.toThrow("pilot v1 offline");
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

  it("rejects Roma without making an Open-Meteo current-weather request during the pilot", async () => {
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

    await expect(fetchLocalConditions(roma, {
      fetchImpl,
      weatherV1Fetcher,
    })).rejects.toMatchObject({ code: "weather_provider_location_not_enabled" });
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(weatherV1Fetcher).not.toHaveBeenCalled();
  });

  it("uses the declared pilot clock for local autonomous conditions", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    vi.spyOn(localWeatherPilot, "getLocalWeatherPilotTestNow")
      .mockReturnValue("2026-09-04T05:00:00Z");
    vi.spyOn(localWeatherPilot, "getLocalWeatherPilotNow")
      .mockReturnValue(Date.parse("2026-09-04T05:00:00Z"));
    const requestClock = vi.fn().mockReturnValue(999);
    const weatherV1Fetcher = vi.fn().mockRejectedValue(new Error("stop after options"));

    await expect(fetchLocalConditions("Udine", {
      now: requestClock,
      weatherV1Fetcher,
    })).rejects.toThrow("stop after options");

    const modelClock = weatherV1Fetcher.mock.calls[0][1].now;
    expect(modelClock).not.toBe(requestClock);
    expect(modelClock()).toBe(Date.parse("2026-09-04T05:00:00Z"));
    expect(requestClock).not.toHaveBeenCalled();
  });

  it("routes autonomous production current conditions to weather v1 only", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(false);
    const fetchImpl = vi.fn();
    const weatherV1Fetcher = vi.fn().mockRejectedValue(new Error("autonomous unavailable"));

    await expect(fetchLocalConditions("Udine", {
      fetchImpl,
      providerConfig: { primary: "autonomous" },
      storage: null,
      weatherV1BaseUrl: "https://weather.example.test/data/",
      weatherV1Fetcher,
    })).rejects.toThrow("autonomous unavailable");
    expect(weatherV1Fetcher).toHaveBeenCalledWith("Udine", expect.objectContaining({
      baseUrl: "https://weather.example.test/data",
      fetchImpl,
      storage: null,
    }));
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("propaga il refresh forzato al runtime locale v1", async () => {
    vi.spyOn(localWeatherPilot, "isLocalWeatherPilot").mockReturnValue(true);
    const validAt = "2026-09-03T10:00:00Z";
    const now = () => Date.parse(validAt);
    const source = {
      active: "icon2i_local_pilot", primary_source: "icon2i_local_pilot",
      catalog: LOCAL_WEATHER_V1_CATALOG,
      icon: { status: "available", evidence: { path: "runs/20260903T000000Z/municipalities/030129.json", etag: '"icon-1"' } },
      cams: { status: "unavailable", evidence: null },
    };
    const dataQuality = {
      mode: "local_contract_v1", catalog_version: LOCAL_WEATHER_V1_CATALOG.version,
      catalog_sha256: LOCAL_WEATHER_V1_CATALOG.sha256, municipality_istat: "030129",
      run_utc: "2026-09-03T00:00:00Z", valid_at_utc: validAt, cams_status: "unavailable",
    };
    const weatherV1Fetcher = vi.fn().mockResolvedValue({
      city: "Udine",
      current: {
        city: "Udine", temperature: 15, primary_source: "icon2i_local_pilot", source, data_quality: dataQuality,
        hourly_forecast: Array.from({ length: 48 }, (_, index) => ({
          time: new Date(now() + (index + 1) * 3600000).toISOString(), temperature: 15,
        })),
      },
      forecast: {
        city: "Udine", daily: [], daily_extrema_version: 2,
        primary_source: "icon2i_local_pilot", source, data_quality: { ...dataQuality },
      },
    });
    await fetchLocalConditions("Udine", {
      fetchImpl: vi.fn(),
      force: true,
      now,
      storage: null,
      weatherV1Fetcher,
    });

    expect(weatherV1Fetcher).toHaveBeenCalledWith(
      "Udine",
      expect.objectContaining({ force: true, storage: null }),
    );
  });

  it("builds a coordinate-aware current-weather URL", () => {
    expect(buildLocalConditionsUrl({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      lat: 45.9892,
      lon: 12.5473,
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
    }, { apiBase: "/api" })).toBe(
      "/api/weather/current?city=Fontanafredda&lat=45.9892&lon=12.5473",
    );
  });

  it("adds a cache buster only for an explicit refresh", () => {
    expect(buildLocalConditionsUrl("Udine", {
      apiBase: "/api/",
      force: true,
      now: () => 123,
    })).toBe("/api/weather/current?city=Udine&_=123");
  });

  it("normalizes the direct current payload exposed by the backend", () => {
    const current = { city: "Pordenone", humidity: 64, pressure: 1009 };

    expect(normalizeLocalConditionsPayload(current)).toEqual({
      city: "Pordenone",
      current,
      raw: current,
    });
  });

  it("rejects an empty payload instead of caching it", () => {
    expect(() => normalizeLocalConditionsPayload({ city: "Udine" })).toThrow(
      "Dati meteo locali incompleti",
    );
  });

  it("accepts a payload backed only by the longer hourly reservoir", () => {
    const current = {
      city: "Udine",
      hourly_forecast: [{ time: "2026-08-19T09:00+02:00", temperature: 22 }],
    };

    expect(normalizeLocalConditionsPayload(current).current).toBe(current);
  });

  it("loads local conditions independently from the official bulletin", async () => {
    const current = { city: "Udine", humidity: 62 };
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(current));

    await expect(fetchLocalConditions({ city: "Udine" }, {
      apiBase: "/api",
      fetchImpl,
      providerConfig: {
        primary: "open_meteo",
        operatorOverride: "open_meteo",
      },
    })).resolves.toMatchObject({ city: "Udine", current });
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/weather/current?city=Udine",
      { cache: "default" },
    );
  });
});
