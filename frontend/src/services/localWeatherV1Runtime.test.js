import { describe, expect, it, vi } from "vitest";

import {
  fetchLocalWeatherV1RuntimeBundle,
  LOCAL_WEATHER_V1_BUNDLE_CACHE_INDEX_KEY,
  LOCAL_WEATHER_V1_BUNDLE_CACHE_PREFIX,
  LOCAL_WEATHER_V1_VERIFY_WINDOW_MS,
  getLocalWeatherV1BundleCacheKey,
  readLocalWeatherV1PersistedBundle,
} from "./localWeatherV1Runtime";
import {
  LOCAL_WEATHER_V1_CATALOG,
  LOCAL_WEATHER_V1_ISTAT_CODES,
} from "./localWeatherV1Adapter";
import { CAMS_AIR_FIELDS, encodeCamsHourlyCacheV2 } from "./camsHourlyCache";
import * as weatherV1Client from "./weatherV1Client";
import * as pilotPrefetch from "./pilotWeatherPrefetch";

const RUN_AT = "2026-09-03T00:00:00Z";
const VALID_AT = "2026-09-03T10:00:00Z";
const CATALOG = LOCAL_WEATHER_V1_CATALOG;
const HOUR_MS = 60 * 60 * 1000;
const TEST_POLLEN_VARIABLES = [
  ["alder_pollen", "ontano"],
  ["birch_pollen", "betulla"],
  ["grass_pollen", "graminacee"],
  ["mugwort_pollen", "artemisia"],
  ["olive_pollen", "olivo"],
  ["ragweed_pollen", "ambrosia"],
];

function bundle({
  camsDisabledRunIds = [],
  camsPublishedAt,
  camsRevision = 1,
  camsRunAt = RUN_AT,
  camsStatus = "available",
  camsValidAt = VALID_AT,
  city = "Pordenone",
  istatCode = "093033",
  runAt = RUN_AT,
  temperature = 20,
  validAt = VALID_AT,
  hourCount = 48,
} = {}) {
  const camsAvailable = !["pending", "unavailable"].includes(camsStatus);
  const camsRunId = camsRunAt.replaceAll("-", "").replaceAll(":", "");
  const familyPublishedAt = camsPublishedAt
    || new Date(Date.parse(camsRunAt) + 2 * 60 * 60 * 1000).toISOString().replace(".000Z", "Z");
  const source = {
    active: "icon2i_local_pilot",
    primary_source: "icon2i_local_pilot",
    municipality_istat: istatCode,
    catalog: CATALOG,
    icon: {
      status: "available",
      evidence: {
        path: `runs/${runAt.replaceAll("-", "").replaceAll(":", "")}/municipalities/${istatCode}.json`,
        etag: `"icon-${runAt}"`,
      },
    },
    cams: {
      status: camsAvailable ? "available" : camsStatus,
      evidence: camsAvailable
        ? {
          family: {
            revision: camsRevision,
            published_at: familyPublishedAt,
            active_run_id: camsRunId,
            disabled_run_ids: [...camsDisabledRunIds],
          },
          stages: {
            latest: {
              path: `families/cams/runs/${camsRunId}/release.json#pollen`,
              etag: `"cams-family-${camsRunId}"`,
            },
            manifest: { path: `runs/${camsRunId}/manifest.json` },
            municipality: {
              path: `runs/${camsRunId}/municipalities/${istatCode}.json`,
            },
          },
        }
        : null,
    },
  };
  const dataQuality = {
    mode: "local_contract_v1",
    catalog_version: CATALOG.version,
    catalog_sha256: CATALOG.sha256,
    municipality_istat: istatCode,
    run_utc: runAt,
    valid_at_utc: validAt,
    catalog_point: { lat: 45.9567, lon: 12.6605 },
    flags: [],
    cams_status: camsStatus,
    cams_run_utc: camsAvailable ? camsRunAt : null,
    cams_valid_at_utc: camsAvailable ? camsValidAt : null,
  };
  return {
    city,
    current: {
      air_quality_data: null,
      city,
      temperature,
      primary_source: "icon2i_local_pilot",
      source,
      hourly_forecast: Array.from({ length: hourCount }, (_, index) => ({
        time: new Date(Date.parse(validAt) + (index + 1) * 60 * 60 * 1000).toISOString(),
        temperature, condition: "Coperto", wind_speed: 7, wind_direction: 90, wind_gusts: 12,
        cloud_cover: 80, precipitation: 0, rain: 0, humidity: 60, pressure: 1015, feels_like: 19,
        quality_flags: [], snowfall_water_equivalent_mm: 0,
        data_quality: { native_weather_code: 3, native_condition_label: "Coperto", native_condition_status: "valid" },
      })),
      pollen_data: {
        status: camsAvailable ? "experimental_model_snapshot" : camsStatus,
      },
      cache: { status: "fresh" },
      data_quality: dataQuality,
    },
    forecast: {
      city,
      daily_extrema_version: 2,
      daily: [],
      primary_source: "icon2i_local_pilot",
      source: { ...source },
      cache: { status: "fresh" },
      data_quality: { ...dataQuality },
    },
  };
}

function withVerifiedCamsHourlyCache(value, hourCount = 31) {
  const run = Date.parse(value.current.data_quality.cams_run_utc);
  const samples = Array.from({ length: hourCount }, (_, index) => ({
    valid_at_utc: new Date(run + index * HOUR_MS).toISOString(),
    pollen_values: Object.fromEntries(TEST_POLLEN_VARIABLES
      .map(([, uiKey]) => [uiKey, index + 0.25])),
    pollen_quality_flags: Object.fromEntries(TEST_POLLEN_VARIABLES
      .map(([id]) => [id, []])),
    air_values: { ozone: 100 + index },
  }));
  const payload = {
    version: 1,
    municipality_istat: value.current.data_quality.municipality_istat,
    catalog_sha256: CATALOG.sha256,
    run_utc: value.current.data_quality.cams_run_utc,
    generated_at_utc: new Date(run + 2 * HOUR_MS).toISOString(),
    fresh_until_utc: new Date(run + 24 * HOUR_MS).toISOString(),
    usable_until_utc: new Date(run + 30 * HOUR_MS).toISOString(),
    pollen_variables: TEST_POLLEN_VARIABLES.map(([id, uiKey]) => ({
      id,
      ui_key: uiKey,
      category: "pollen",
      unit: "grains/m3",
      validation_status: "valid",
    })),
    samples,
  };
  value.current.cams_hourly_cache = {
    ...payload,
    sha256: weatherV1Client.sha256Hex(JSON.stringify(payload)),
  };
  return value;
}

function withVerifiedCamsHourlyCacheV2(value, hourCount = 97, usableHours = 96) {
  const run = Date.parse(value.current.data_quality.cams_run_utc);
  const samples = Array.from({ length: hourCount }, (_, index) => ({
    valid_at_utc: new Date(run + index * HOUR_MS).toISOString().replace(".000Z", "Z"),
    pollen_values: Object.fromEntries(TEST_POLLEN_VARIABLES
      .map(([, uiKey], field) => [uiKey, index + field / 10])),
    pollen_quality_flags: Object.fromEntries(TEST_POLLEN_VARIABLES
      .map(([id], field) => [id, field === 0 && index % 2 ? ["interpolated"] : []])),
    air_values: Object.fromEntries(CAMS_AIR_FIELDS
      .map((id, field) => [id, 100 + index + field / 10])),
  }));
  value.current.cams_hourly_cache = encodeCamsHourlyCacheV2({
    municipality_istat: value.current.data_quality.municipality_istat,
    catalog_sha256: CATALOG.sha256,
    run_utc: value.current.data_quality.cams_run_utc,
    generated_at_utc: new Date(run + 2 * HOUR_MS).toISOString(),
    fresh_until_utc: new Date(run + 24 * HOUR_MS).toISOString(),
    usable_until_utc: new Date(run + usableHours * HOUR_MS).toISOString(),
    pollen_variables: TEST_POLLEN_VARIABLES.map(([id, uiKey]) => ({
      id,
      ui_key: uiKey,
      category: "pollen",
      unit: "grains/m3",
      validation_status: "valid",
    })),
    samples,
  });
  return value;
}

function withDeltaEligibleCamsShape(value, { cache = value.current.cams_hourly_cache ?? null } = {}) {
  for (const part of [value.current, value.forecast]) {
    part.source.status = "available";
    part.source.label = "ItaliaMeteo ICON-2I e CAMS · contratto locale v1";
    part.model_support = { icon2i: true, cams: true, open_meteo: false };
    part.data_quality.cams_sample_status = "current";
    part.data_quality.cams_diagnostic = null;
    part.data_quality.capability_gaps = [];
  }
  value.current.pollen = { overall: "low" };
  value.current.pollen_data = {
    status: "experimental_model_snapshot",
    valid_at_utc: value.current.data_quality.cams_valid_at_utc,
    values: { ambrosia: 10.5 },
  };
  value.current.air_quality_data = {
    run_at: value.current.data_quality.cams_run_utc,
    valid_at: value.current.data_quality.cams_valid_at_utc,
    values: Object.fromEntries(CAMS_AIR_FIELDS.map((id, field) => [id, 110 + field / 10])),
  };
  value.current.hourly_next_12h = value.current.hourly_forecast.slice(0, 12);
  value.current.cams_hourly_cache = cache;
  return value;
}

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    values,
    getItem: vi.fn((key) => values.get(key) ?? null),
    setItem: vi.fn((key, value) => values.set(key, value)),
    removeItem: vi.fn((key) => values.delete(key)),
  };
}

function enumerableMemoryStorage(initial = {}) {
  const storage = memoryStorage(initial);
  storage.key = vi.fn(index => [...storage.values.keys()][index] ?? null);
  Object.defineProperty(storage, "length", {
    configurable: true,
    get: () => storage.values.size,
  });
  return storage;
}

function dailyBundle({ enriched = false, ...bundleOptions } = {}) {
  const value = bundle(bundleOptions);
  const day = {
    date: "2026-09-03",
    condition: enriched ? "Sereno" : "Coperto",
    min_temp: enriched ? 18.94 : null,
    max_temp: enriched ? 32.29 : null,
    sampled_min_temp: enriched ? 18.94 : 24,
    sampled_max_temp: 32.29,
    source_hours: enriched ? 24 : 10,
    partial_day: !enriched,
    previous_run_at: enriched ? "2026-09-02T12:00:00Z" : null,
  };
  value.forecast.forecast = [day];
  value.forecast.daily = {
    time: [day.date],
    temperature_2m_min: [day.min_temp],
    temperature_2m_max: [day.max_temp],
    weathercode: [null],
    weather_code: [null],
  };
  return value;
}

function municipality(index) {
  const istatCode = `093${String(index).padStart(3, "0")}`;
  const city = `Comune ${index}`;
  return {
    city,
    municipality: { istatCode, name: city },
  };
}

function persistedBundleKeys(storage) {
  return [...storage.values.keys()].filter(
    (key) => key.startsWith(`${LOCAL_WEATHER_V1_BUNDLE_CACHE_PREFIX}:`)
      && key !== LOCAL_WEATHER_V1_BUNDLE_CACHE_INDEX_KEY,
  );
}

function options(bundleFetcher, now, extra = {}) {
  return {
    baseUrl: "/__local-weather-pilot",
    bundleFetcher,
    fetchImpl: vi.fn(),
    now,
    storage: null,
    verifyWindowMs: 0,
    ...extra,
  };
}

describe("local weather v1 runtime", () => {
  it("keeps native selection configured on a persisted-cache hit without waiting for prefetch", async () => {
    const reader = vi.spyOn(pilotPrefetch, "getPilotWeatherPrefetchReader").mockReturnValue(null);
    try {
      const now = () => Date.parse("2026-09-03T10:15:00Z");
      const baseUrl = pilotPrefetch.PILOT_WEATHER_PREFETCH_API_BASE;
      const storage = memoryStorage();
      const extra = { baseUrl, storage, verificationNow: now, verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS };
      await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(bundle()), now, extra));
      reader.mockClear();
      const fetcher = vi.fn().mockRejectedValue(new Error("network must not be needed"));
      const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(fetcher, now, extra));
      expect(result.current.temperature).toBe(20);
      expect(fetcher).not.toHaveBeenCalled();
      expect(reader).toHaveBeenCalledWith({ baseUrl, istatCode: "093033" });
    } finally { reader.mockRestore(); }
  });

  it("recovers missing morning extrema on a same-ICON v2 retry and persists them", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const extra = { baseUrl: "/daily-v2-recovery", storage, force: true };
    const partial = dailyBundle();
    const complete = dailyBundle({ enriched: true });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(partial), now, extra));

    const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(complete), now, extra));

    expect(result.forecast.forecast).toEqual(complete.forecast.forecast);
    expect(result.forecast.daily).toEqual(complete.forecast.daily);
    expect(result.current).toEqual(partial.current);
    expect(readLocalWeatherV1PersistedBundle("Pordenone", { ...extra, now }).forecast.forecast)
      .toEqual(complete.forecast.forecast);
  });

  it.each(["pending", "available"])("retains morning extrema after a failed history retry while enriching %s CAMS", async (camsStatus) => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const extra = { baseUrl: `/daily-v2-retention-${camsStatus}`, storage, force: true };
    const complete = dailyBundle({ enriched: true, camsStatus });
    const retry = dailyBundle({ camsRunAt: "2026-09-03T06:00:00Z", camsRevision: 2 });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(complete), now, extra));

    const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(retry), now, extra));

    expect(result.forecast.forecast).toEqual(complete.forecast.forecast);
    expect(result.forecast.daily).toEqual(complete.forecast.daily);
    expect(result.current.data_quality.cams_run_utc).toBe(retry.current.data_quality.cams_run_utc);
    expect(retry.forecast.forecast[0].previous_run_at).toBeNull();
    expect(readLocalWeatherV1PersistedBundle("Pordenone", { ...extra, now }).forecast.forecast)
      .toEqual(complete.forecast.forecast);
  });

  it("preserves morning extrema when history is missing again without a CAMS upgrade", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const extra = { baseUrl: "/daily-v2-no-degradation", storage: memoryStorage(), force: true };
    const complete = dailyBundle({ enriched: true });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(complete), now, extra));

    const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(dailyBundle()), now, extra));

    expect(result).toEqual(complete);
  });

  it.each([
    ["current condition", value => { value.current.temperature += 1; }],
    ["hourly value", value => { value.current.hourly_forecast[0].temperature = 99; }],
    ["ICON identity", value => { value.current.source.icon.evidence.etag = '"another-object"'; }],
    ["missing historical run", value => { value.forecast.forecast[0].previous_run_at = null; }],
    ["future historical run", value => { value.forecast.forecast[0].previous_run_at = "2026-09-04T00:00:00Z"; }],
    ["no additional hours", value => { value.forecast.forecast[0].source_hours = 10; }],
    ["narrower extrema", value => { value.forecast.forecast[0].sampled_min_temp = 25; value.forecast.forecast[0].min_temp = 25; value.forecast.daily.temperature_2m_min = [25]; }],
    ["inconsistent daily table", value => { value.forecast.daily.temperature_2m_min = [99]; }],
    ["different day", value => { value.forecast.forecast[0].date = "2026-09-04"; value.forecast.daily.time = ["2026-09-04"]; }],
  ])("does not accept daily enrichment with a changed %s", async (label, change) => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const extra = { baseUrl: `/daily-v2-invalid-${label}`, storage: memoryStorage(), force: true };
    const partial = dailyBundle();
    const invalid = dailyBundle({ enriched: true });
    change(invalid);
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(partial), now, extra));

    const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(invalid), now, extra));

    expect(result).toEqual(partial);
  });

  it("allows provenance-only changes on unchanged future days during morning recovery", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const extra = { baseUrl: "/daily-v2-future-days", storage: memoryStorage(), force: true };
    const partial = dailyBundle();
    const complete = dailyBundle({ enriched: true });
    for (const value of [partial, complete]) {
      const tomorrow = { ...dailyBundle({ enriched: true }).forecast.forecast[0], date: "2026-09-04",
        previous_run_at: value.forecast.forecast[0].previous_run_at };
      value.forecast.forecast.push(tomorrow);
      value.forecast.daily.time.push(tomorrow.date);
      value.forecast.daily.temperature_2m_min.push(tomorrow.min_temp);
      value.forecast.daily.temperature_2m_max.push(tomorrow.max_temp);
      value.forecast.daily.weathercode.push(null);
      value.forecast.daily.weather_code.push(null);
    }
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(partial), now, extra));

    const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(complete), now, extra));

    expect(result.forecast.forecast).toEqual(complete.forecast.forecast);
    expect(result.current).toEqual(partial.current);
  });

  it("upgrades saved daily extrema without changing current conditions", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const extra = { baseUrl: "/daily-extrema-upgrade", storage: memoryStorage(), verificationNow: now, verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS };
    const old = bundle();
    delete old.forecast.daily_extrema_version;
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(old), now, extra));
    const updated = bundle();
    updated.forecast.forecast = [{ date: "2026-09-03", sampled_min_temp: 18.94, sampled_max_temp: 32.29 }];
    const fetcher = vi.fn().mockResolvedValue(updated);
    const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(fetcher, now, extra));
    expect(fetcher).toHaveBeenCalledOnce();
    expect(result.forecast.forecast).toEqual(updated.forecast.forecast);
    expect(result.current).toEqual(old.current);
  });
  it("reuses persisted verification after reopen, but checks again after ten minutes", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    let clock = now();
    const verificationNow = () => clock;
    const storage = memoryStorage();
    const baseUrl = "/persisted-ten-minute-verification";
    const first = vi.fn().mockResolvedValue(bundle());
    const extra = { baseUrl, storage, verificationNow, verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS };
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(first, now, extra));
    clock += 9 * 60 * 1000;
    const reopened = vi.fn().mockResolvedValue(bundle());
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(reopened, now, extra));
    expect(reopened).not.toHaveBeenCalled();
    clock += 60 * 1000;
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(reopened, now, extra));
    expect(reopened).toHaveBeenCalledTimes(1);
  });

  it("does not reuse a recent verification across the forecast hour boundary", async () => {
    let time = Date.parse("2026-09-03T10:59:00Z");
    const now = () => time;
    const fetcher = vi.fn().mockResolvedValue(bundle());
    const opts = options(fetcher, now, { baseUrl: "/hour-boundary", verificationNow: now, verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", opts);
    time += 60000;
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", opts);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it.each(["pending", "fresh"])("air enrichment upgrades %s without changing ICON identity", async (camsStatus) => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const baseUrl = `/air-enrichment-${camsStatus}`;
    const pending = bundle({ camsStatus });
    pending.current.air_quality_data = null;
    const complete = bundle({ camsStatus: "fresh" });
    complete.current.air_quality_data = { valid_at: VALID_AT, run_at: RUN_AT, values: { "particulate_matter_2.5um": 5 } };
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(pending), now, { baseUrl, storage }));
    const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(complete), now, { baseUrl, storage, force: true }));
    expect(result.current.air_quality_data).toEqual(complete.current.air_quality_data);
    const later = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(pending), now, { baseUrl, storage, force: true }));
    expect(later.current.air_quality_data).toEqual(complete.current.air_quality_data);
  });

  it("revalidates legacy persisted bundles without the air field", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage({ unrelated: "keep" });
    const baseUrl = "/legacy-air-migration";
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(bundle()), now, { baseUrl, storage }));
    const key = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const stored = JSON.parse(storage.getItem(key));
    delete stored.bundle.current.air_quality_data;
    storage.setItem(key, JSON.stringify(stored));
    expect(readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, now, storage })).toBeNull();
    expect(storage.getItem("unrelated")).toBe("keep");
  });

  it("deduplicates concurrent whole-bundle reads", async () => {
    let resolve;
    const bundleFetcher = vi.fn(() => new Promise((done) => { resolve = done; }));
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const runtimeOptions = options(bundleFetcher, now);

    const left = fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    const right = fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    await vi.waitFor(() => expect(bundleFetcher).toHaveBeenCalledTimes(1));
    resolve(bundle());

    const [leftResult, rightResult] = await Promise.all([left, right]);
    expect(leftResult).toBe(rightResult);
    expect(bundleFetcher).toHaveBeenCalledWith("Pordenone", expect.objectContaining({
      force: false,
      storage: null,
    }));
  });

  it("riusa il bundle verificato tra chiamate sequenziali entro la verify-window", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    let verificationNowValue = Date.parse("2026-09-05T12:00:00Z");
    const verificationNow = () => verificationNowValue;
    const expected = bundle();
    const bundleFetcher = vi.fn().mockResolvedValue(expected);
    const runtimeOptions = options(bundleFetcher, now, {
      baseUrl: "/verify-window-shared",
      deferCams: true,
      verificationNow,
      verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS,
    });

    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions))
      .resolves.toBe(expected);
    verificationNowValue += LOCAL_WEATHER_V1_VERIFY_WINDOW_MS - 1;
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", {
      ...runtimeOptions,
      deferCams: false,
    })).resolves.toBe(expected);

    expect(bundleFetcher).toHaveBeenCalledOnce();
  });

  it("bypassa la verify-window con force e separa le richieste in-flight", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const expected = bundle();
    const bundleFetcher = vi.fn().mockResolvedValue(expected);
    const runtimeOptions = options(bundleFetcher, now, {
      baseUrl: "/verify-window-force",
      verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS,
    });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);

    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", {
      ...runtimeOptions,
      force: true,
    })).resolves.toBe(expected);

    expect(bundleFetcher).toHaveBeenCalledTimes(2);
    expect(bundleFetcher.mock.calls.map(([, fetchOptions]) => fetchOptions.force))
      .toEqual([false, true]);

    const concurrentFetcher = vi.fn().mockResolvedValue(expected);
    const concurrentOptions = options(concurrentFetcher, now, {
      baseUrl: "/verify-window-force-in-flight",
      verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS,
    });
    await Promise.all([
      fetchLocalWeatherV1RuntimeBundle("Pordenone", concurrentOptions),
      fetchLocalWeatherV1RuntimeBundle("Pordenone", { ...concurrentOptions, force: true }),
    ]);
    expect(concurrentFetcher).toHaveBeenCalledTimes(2);
  });

  it("scade sul wall-clock anche quando l'orologio modello resta fisso", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    let verificationNowValue = Date.parse("2026-09-05T12:00:00Z");
    const verificationNow = () => verificationNowValue;
    const expected = bundle();
    const bundleFetcher = vi.fn().mockResolvedValue(expected);
    const runtimeOptions = options(bundleFetcher, now, {
      baseUrl: "/verify-window-expired",
      verificationNow,
      verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS,
    });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);

    verificationNowValue += LOCAL_WEATHER_V1_VERIFY_WINDOW_MS;
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);

    expect(bundleFetcher).toHaveBeenCalledTimes(2);
    expect(bundleFetcher).toHaveBeenLastCalledWith(
      "Pordenone",
      expect.objectContaining({ force: false }),
    );
  });

  it("limita la verify-window configurabile a dieci minuti", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const bundleFetcher = vi.fn().mockResolvedValue(bundle());

    await expect(fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(bundleFetcher, now, { verifyWindowMs: 10 * 60 * 1000 + 1 }),
    )).rejects.toThrow("Finestra di verifica weather v1 locale non valida");
    expect(bundleFetcher).not.toHaveBeenCalled();
  });

  it("mantiene verify-window separate per Comune", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const udine = municipality(77);
    const bundleFetcher = vi.fn()
      .mockResolvedValueOnce(bundle())
      .mockResolvedValueOnce(bundle({
        city: udine.city,
        istatCode: udine.municipality.istatCode,
      }));
    const runtimeOptions = options(bundleFetcher, now, {
      baseUrl: "/verify-window-municipalities",
      verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS,
    });

    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    await fetchLocalWeatherV1RuntimeBundle(udine, runtimeOptions);

    expect(bundleFetcher).toHaveBeenCalledTimes(2);
  });

  it("sanitizes B in another municipality without discarding its verified ICON window", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/verify-window-revocation";
    const storage = memoryStorage();
    const udine = municipality(77);
    const bRunId = RUN_AT.replaceAll("-", "").replaceAll(":", "");
    const bundleFetcher = vi.fn()
      .mockResolvedValueOnce(bundle())
      .mockResolvedValueOnce(bundle({
        camsDisabledRunIds: [bRunId],
        camsPublishedAt: "2026-09-03T03:00:00Z",
        camsRevision: 2,
        camsRunAt: "2026-09-02T18:00:00Z",
        city: udine.city,
        istatCode: udine.municipality.istatCode,
      }))
      .mockRejectedValueOnce(new Error("offline after revocation"));
    const runtimeOptions = options(bundleFetcher, now, {
      baseUrl,
      storage,
      verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS,
    });

    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    await fetchLocalWeatherV1RuntimeBundle(udine, runtimeOptions);
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions))
      .resolves.toMatchObject({
        current: {
          source: { icon: { status: "available" }, cams: { status: "unavailable" } },
          data_quality: { cams_status: "unavailable", cams_run_utc: null },
        },
      });

    expect(bundleFetcher).toHaveBeenCalledTimes(2);
  });

  it("retains the last verified visible bundle after a transient refresh failure", async () => {
    let nowValue = Date.parse("2026-09-03T10:15:00Z");
    const now = () => nowValue;
    const expected = bundle();
    const bundleFetcher = vi.fn()
      .mockResolvedValueOnce(expected)
      .mockRejectedValueOnce(new Error("offline"));
    const runtimeOptions = options(bundleFetcher, now);

    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions)).resolves.toBe(expected);
    nowValue = Date.parse("2026-09-03T10:45:00Z");
    const retained = await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);

    expect(retained.current.temperature).toBe(20);
    expect(retained.current.cache).toMatchObject({
      runtime_fallback: true,
      runtime_fallback_source: "verified_memory_bundle",
    });
    expect(retained.current.data_quality.flags).toContain("runtime_refresh_failed_bundle_retained");
  });

  it("rehydrates a verified autonomous bundle after a remount and coordinate drift", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const firstLocation = {
      city: "Pordenone",
      lat: 45.9567,
      lon: 12.6605,
      municipality: { istatCode: "093033", name: "Pordenone" },
    };
    const remountedLocation = {
      ...firstLocation,
      lat: 45.9612,
      lon: 12.6519,
    };
    const success = vi.fn().mockResolvedValue(bundle());
    const offlineAfterRemount = vi.fn().mockRejectedValue(new Error("offline"));

    await fetchLocalWeatherV1RuntimeBundle(firstLocation, options(success, now, { storage }));
    const cacheKey = getLocalWeatherV1BundleCacheKey(firstLocation, {
      baseUrl: "/__local-weather-pilot",
    });
    expect(JSON.parse(storage.values.get(cacheKey))).toMatchObject({
      version: 4,
      municipality: "istat:093033",
      bundle: { city: "Pordenone" },
    });

    const retained = await fetchLocalWeatherV1RuntimeBundle(
      remountedLocation,
      options(offlineAfterRemount, now, { storage }),
    );
    expect(retained.current).toMatchObject({
      temperature: 20,
      cache: {
        runtime_fallback: true,
        runtime_fallback_source: "verified_persistent_bundle",
      },
    });
    expect(offlineAfterRemount).toHaveBeenCalledOnce();
  });

  it("elimina i bundle v2/v3 senza toccare cache raw o chiavi estranee", () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/legacy-cams-family-cache";
    const currentKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const legacyKey = currentKey.replace(
      "meteofriul:weather-v1:bundle:v4:",
      "meteofriul:weather-v1:bundle:v2:",
    );
    const legacyIndex = "meteofriul:weather-v1:bundle:v2:lru";
    const legacyV3Key = currentKey.replace(
      "meteofriul:weather-v1:bundle:v4:",
      "meteofriul:weather-v1:bundle:v3:",
    );
    const legacyV3Index = "meteofriul:weather-v1:bundle:v3:lru";
    const storage = memoryStorage({
      [legacyKey]: JSON.stringify({
        version: 2,
        municipality: "city:pordenone",
        bundle: bundle(),
      }),
      [legacyIndex]: JSON.stringify({ version: 2, keys: [legacyKey] }),
      [legacyV3Key]: JSON.stringify({
        version: 3,
        municipality: "city:pordenone",
        bundle: bundle(),
      }),
      [legacyV3Index]: JSON.stringify({ version: 3, keys: [legacyV3Key] }),
      "meteofriul:weather-v1:v3:raw:keep": "raw",
      unrelated: "keep",
    });

    expect(readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, now, storage }))
      .toBeNull();
    expect(storage.values.has(legacyKey)).toBe(false);
    expect(storage.values.has(legacyIndex)).toBe(false);
    expect(storage.values.has(legacyV3Key)).toBe(false);
    expect(storage.values.has(legacyV3Index)).toBe(false);
    expect(storage.values.get("meteofriul:weather-v1:v3:raw:keep")).toBe("raw");
    expect(storage.values.get("unrelated")).toBe("keep");
  });

  it("keeps eight persisted bundles globally and touches a valid read before eviction", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage({
      unrelated: "keep",
      "meteofriul:weather-v1:v2:low-level": "keep",
    });
    const baseUrl = "/persistent-global-lru";
    const locations = Array.from({ length: 9 }, (_, index) => municipality(index + 1));

    for (const [index, location] of locations.slice(0, 8).entries()) {
      await fetchLocalWeatherV1RuntimeBundle(location, options(
        vi.fn().mockResolvedValue(bundle({
          city: location.city,
          istatCode: location.municipality.istatCode,
          temperature: index + 1,
        })),
        now,
        { baseUrl, storage },
      ));
    }

    expect(readLocalWeatherV1PersistedBundle(locations[0], { baseUrl, now, storage }))
      .toMatchObject({ current: { temperature: 1 } });
    await fetchLocalWeatherV1RuntimeBundle(locations[8], options(
      vi.fn().mockResolvedValue(bundle({
        city: locations[8].city,
        istatCode: locations[8].municipality.istatCode,
        temperature: 9,
      })),
      now,
      { baseUrl, storage },
    ));

    const firstKey = getLocalWeatherV1BundleCacheKey(locations[0], { baseUrl });
    const secondKey = getLocalWeatherV1BundleCacheKey(locations[1], { baseUrl });
    const ninthKey = getLocalWeatherV1BundleCacheKey(locations[8], { baseUrl });
    const index = JSON.parse(storage.values.get(LOCAL_WEATHER_V1_BUNDLE_CACHE_INDEX_KEY));
    expect(index).toEqual({
      version: 4,
      keys: expect.any(Array),
    });
    expect(index.keys).toHaveLength(8);
    expect(index.keys).toEqual(expect.arrayContaining([firstKey, ninthKey]));
    expect(index.keys).not.toContain(secondKey);
    expect(persistedBundleKeys(storage)).toHaveLength(8);
    expect(storage.values.has(firstKey)).toBe(true);
    expect(storage.values.has(secondKey)).toBe(false);
    expect(storage.values.get("unrelated")).toBe("keep");
    expect(storage.values.get("meteofriul:weather-v1:v2:low-level")).toBe("keep");
  });

  it("evicts the oldest indexed bundle and retries one time after storage quota", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    let quotaFailures = 0;
    storage.setItem = vi.fn((key, value) => {
      if (!storage.values.has(key) && storage.values.size >= 9) {
        quotaFailures += 1;
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      storage.values.set(key, value);
    });
    const baseUrl = "/persistent-quota-retry";
    const locations = Array.from({ length: 9 }, (_, index) => municipality(index + 21));

    for (const [index, location] of locations.entries()) {
      await fetchLocalWeatherV1RuntimeBundle(location, options(
        vi.fn().mockResolvedValue(bundle({
          city: location.city,
          istatCode: location.municipality.istatCode,
          temperature: index + 1,
        })),
        now,
        { baseUrl, storage },
      ));
    }

    const oldestKey = getLocalWeatherV1BundleCacheKey(locations[0], { baseUrl });
    const newestKey = getLocalWeatherV1BundleCacheKey(locations[8], { baseUrl });
    expect(quotaFailures).toBeGreaterThanOrEqual(1);
    expect(storage.values.has(oldestKey)).toBe(false);
    expect(storage.values.has(newestKey)).toBe(true);
    expect(persistedBundleKeys(storage)).toHaveLength(8);
    expect(JSON.parse(storage.values.get(LOCAL_WEATHER_V1_BUNDLE_CACHE_INDEX_KEY)).keys)
      .toHaveLength(8);
  });

  it("adotta ICON nuovo dopo il recupero mirato dello scope raw v4 obsoleto", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const verificationNow = () => 2_000;
    const baseUrl = "https://reader.current.example/weather/v1";
    const seedStorage = enumerableMemoryStorage({ unrelated: "keep" });
    const active = withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle({ temperature: 20 })));
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(active), now,
      { baseUrl, storage: seedStorage, force: true, verificationNow: () => 1_000 },
    ));

    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const oldScope = weatherV1Client.sha256Hex("http://127.0.0.1:8781").slice(0, 16);
    const obsoleteRawKey = `meteofriul:weather-v1:v4:${oldScope}:icon2i:municipality:0`;
    const storage = enumerableMemoryStorage(Object.fromEntries([
      ...seedStorage.values.entries(),
      [obsoleteRawKey, "x".repeat(200_000)],
    ]));
    const baselineWithoutObsolete = [...storage.values.entries()]
      .filter(([key]) => key !== obsoleteRawKey)
      .reduce((total, [key, value]) => total + key.length + value.length, 0);
    const quota = baselineWithoutObsolete + 100_000;
    let quotaFailures = 0;
    storage.setItem.mockImplementation((key, value) => {
      const previous = storage.values.get(key);
      const currentSize = [...storage.values.entries()].reduce(
        (total, [storedKey, storedValue]) => total + storedKey.length + storedValue.length,
        0,
      );
      const nextSize = currentSize
        - (previous === undefined ? 0 : key.length + previous.length)
        + key.length + value.length;
      if (nextSize > quota) {
        quotaFailures += 1;
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      storage.values.set(key, value);
    });

    const next = withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle({
      runAt: "2026-09-03T06:00:00Z",
      temperature: 24,
    })));
    const bundleFetcher = vi.fn(async () => {
      // The production adapter constructs this client before downloading ICON.
      // Its constructor performs the narrowly scoped raw-cache cleanup.
      weatherV1Client.createWeatherV1Client({
        baseUrl,
        fetchImpl: vi.fn(),
        storage,
        now,
        catalog: LOCAL_WEATHER_V1_CATALOG,
        istatCodes: LOCAL_WEATHER_V1_ISTAT_CODES,
      });
      return next;
    });
    const selected = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      bundleFetcher, now,
      { baseUrl, storage, force: true, verificationNow },
    ));

    expect(storage.values.has(obsoleteRawKey)).toBe(false);
    expect(selected.current).toMatchObject({
      temperature: 24,
      data_quality: {
        run_utc: "2026-09-03T06:00:00Z",
        cams_run_utc: RUN_AT,
      },
    });
    expect(selected.current.cams_hourly_cache).toMatchObject({ version: 2, sample_count: 97 });
    expect(selected.current.cache).not.toHaveProperty("runtime_fallback");
    expect(JSON.parse(storage.getItem(activeKey)).bundle.current.temperature).toBe(24);
    expect(storage.getItem(`${activeKey}:candidate`)).toBeNull();
    expect(storage.getItem("unrelated")).toBe("keep");
    expect(quotaFailures).toBe(0);

    const offlineFetcher = vi.fn().mockRejectedValue(new Error("offline"));
    const reopened = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      offlineFetcher, now,
      { baseUrl, storage: { ...storage }, force: true },
    ));
    expect(offlineFetcher).toHaveBeenCalledOnce();
    expect(reopened.current).toMatchObject({
      temperature: 24,
      data_quality: {
        run_utc: "2026-09-03T06:00:00Z",
        cams_run_utc: RUN_AT,
      },
    });
    expect(reopened.current.cams_hourly_cache).toMatchObject({ version: 2, sample_count: 97 });
  });

  it("keeps the active bundle when the candidate commit is interrupted, then reopens cleanly", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const baseUrl = "/candidate-interrupted-with-active";
    const active = bundle({ camsStatus: "fresh", temperature: 20 });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(active), now, { baseUrl, storage },
    ));
    const key = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const originalSetItem = storage.setItem.getMockImplementation();
    let interrupt = true;
    storage.setItem.mockImplementation((targetKey, value) => {
      if (interrupt && targetKey === key) {
        interrupt = false;
        throw new Error("simulated process interruption before active commit");
      }
      return originalSetItem(targetKey, value);
    });
    const candidate = bundle({
      camsStatus: "fresh", runAt: "2026-09-03T06:00:00Z", temperature: 24,
    });

    const retained = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(candidate), now, { baseUrl, storage, force: true },
    ));

    expect(retained.current.temperature).toBe(20);
    expect(JSON.parse(storage.getItem(key)).bundle.current.temperature).toBe(20);
    expect(storage.getItem(`${key}:candidate`)).not.toBeNull();
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", {
      baseUrl, storage: { ...storage }, now,
    });
    expect(reopened.current.temperature).toBe(20);
    expect(storage.getItem(`${key}:candidate`)).toBeNull();
  });

  it("recovers a fully saved candidate after interruption when no previous active exists", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const baseUrl = "/candidate-interrupted-without-active";
    const key = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const originalSetItem = storage.setItem.getMockImplementation();
    storage.setItem.mockImplementation((targetKey, value) => {
      if (targetKey === key) throw new Error("simulated process interruption before first active commit");
      return originalSetItem(targetKey, value);
    });

    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(bundle({ camsStatus: "fresh", temperature: 23 })),
      now,
      { baseUrl, storage, force: true },
    ))).rejects.toMatchObject({ code: "CACHE_PERSIST_FAILED" });
    expect(storage.getItem(key)).toBeNull();
    expect(storage.getItem(`${key}:candidate`)).not.toBeNull();

    storage.setItem.mockImplementation(originalSetItem);
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", {
      baseUrl, storage: { ...storage }, now,
    });
    expect(reopened.current.temperature).toBe(23);
    expect(JSON.parse(storage.getItem(key)).bundle.current.temperature).toBe(23);
    expect(storage.getItem(`${key}:candidate`)).toBeNull();
  });

  it("persists a newer locally verified provider fallback before replacing the active bundle", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const baseUrl = "/provider-fallback-atomic-promotion";
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(bundle({ camsStatus: "unavailable", temperature: 20 })),
      now,
      { baseUrl, storage },
    ));
    const key = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const previousVerifiedAt = JSON.parse(storage.getItem(key)).verifiedAt;
    const fallback = bundle({
      camsStatus: "pending",
      runAt: "2026-09-03T06:00:00Z",
      temperature: 24,
    });
    fallback.current.source.icon.evidence.network_fallback = true;

    const promoted = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(fallback),
      now,
      { baseUrl, storage, force: true },
    ));

    expect(promoted.current.temperature).toBe(24);
    const persisted = JSON.parse(storage.getItem(key));
    expect(persisted.bundle.current.temperature).toBe(24);
    expect(persisted.verifiedAt).toBe(previousVerifiedAt);
    expect(readLocalWeatherV1PersistedBundle("Pordenone", {
      baseUrl, storage: { ...storage }, now,
    }).current.temperature).toBe(24);
  });

  it("sanitizes an orphan first-save candidate when a later family decision revokes CAMS", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = enumerableMemoryStorage();
    const baseUrl = "/orphan-candidate-revocation";
    const key = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const originalSetItem = storage.setItem.getMockImplementation();
    storage.setItem.mockImplementation((targetKey, value) => {
      if (targetKey === key) throw new Error("interrupted before first active commit");
      return originalSetItem(targetKey, value);
    });
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(bundle()), now, { baseUrl, storage, force: true },
    ))).rejects.toMatchObject({ code: "CACHE_PERSIST_FAILED" });
    expect(storage.getItem(`${key}:candidate`)).not.toBeNull();

    storage.setItem.mockImplementation(originalSetItem);
    const other = municipality(88);
    await fetchLocalWeatherV1RuntimeBundle(other, options(vi.fn().mockResolvedValue(bundle({
      camsDisabledRunIds: ["20260903T000000Z"],
      camsPublishedAt: "2026-09-03T03:00:00Z",
      camsRevision: 2,
      camsRunAt: "2026-09-02T18:00:00Z",
      city: other.city,
      istatCode: other.municipality.istatCode,
    })), now, { baseUrl, storage, force: true }));

    const staged = JSON.parse(storage.getItem(`${key}:candidate`));
    expect(staged.bundle.current).toMatchObject({
      source: { icon: { status: "available" }, cams: { status: "unavailable" } },
      data_quality: { cams_status: "unavailable", cams_run_utc: null },
      air_quality_data: null,
      pollen_data: { status: "unavailable" },
    });
    const recovered = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage, now });
    expect(recovered.current).toMatchObject({
      source: { icon: { status: "available" }, cams: { status: "unavailable" } },
      data_quality: { cams_status: "unavailable", cams_run_utc: null },
    });
    expect(storage.getItem(`${key}:candidate`)).toBeNull();
  });

  it("recovers a corrupt index without storage enumeration or touching foreign caches", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const foreignKey = "foreign:weather:bundle";
    const lowLevelKey = "meteofriul:weather-v1:v2:scope:icon2i:latest:0";
    const storage = memoryStorage({
      [LOCAL_WEATHER_V1_BUNDLE_CACHE_INDEX_KEY]: "{not-json",
      [foreignKey]: "keep",
      [lowLevelKey]: "keep",
    });
    const location = municipality(51);
    const baseUrl = "/persistent-corrupt-index";

    await expect(fetchLocalWeatherV1RuntimeBundle(location, options(
      vi.fn().mockResolvedValue(bundle({
        city: location.city,
        istatCode: location.municipality.istatCode,
      })),
      now,
      { baseUrl, storage },
    ))).resolves.toMatchObject({ city: location.city });

    expect(JSON.parse(storage.values.get(LOCAL_WEATHER_V1_BUNDLE_CACHE_INDEX_KEY))).toMatchObject({
      version: 4,
      keys: [getLocalWeatherV1BundleCacheKey(location, { baseUrl })],
    });
    expect(storage.values.get(foreignKey)).toBe("keep");
    expect(storage.values.get(lowLevelKey)).toBe("keep");
  });

  it("rejects persisted bundles with the wrong source, municipality or model freshness", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const location = "Pordenone";
    const invalidSource = structuredClone(bundle());
    invalidSource.current.primary_source = "open_meteo";
    const wrongMunicipality = bundle({ city: "Udine", istatCode: "030129" });
    const expired = bundle({
      runAt: "2026-09-02T00:00:00Z",
      validAt: "2026-09-03T10:00:00Z",
    });
    const wrongCatalog = structuredClone(bundle());
    wrongCatalog.current.data_quality.catalog_sha256 = "0".repeat(64);
    const legacyCamsEvidence = structuredClone(bundle());
    delete legacyCamsEvidence.current.source.cams.evidence;
    const nonCanonicalRevocations = structuredClone(bundle());
    nonCanonicalRevocations.current.source.cams.evidence.family.disabled_run_ids = [
      "20260902T000000Z",
      "20260902T000000Z",
    ];
    const mismatchedForecastDecision = structuredClone(bundle());
    mismatchedForecastDecision.forecast.source.cams = structuredClone(
      mismatchedForecastDecision.forecast.source.cams,
    );
    mismatchedForecastDecision.forecast.source.cams.evidence.family.revision = 2;

    for (const [index, invalid] of [
      invalidSource,
      wrongMunicipality,
      expired,
      wrongCatalog,
      legacyCamsEvidence,
      nonCanonicalRevocations,
      mismatchedForecastDecision,
    ].entries()) {
      const baseUrl = `/invalid-persisted-${index}`;
      const storage = memoryStorage();
      const key = getLocalWeatherV1BundleCacheKey(location, { baseUrl });
      storage.values.set(key, JSON.stringify({
        version: 4,
        municipality: "city:pordenone",
        bundle: invalid,
      }));

      await expect(fetchLocalWeatherV1RuntimeBundle(location, options(
        vi.fn().mockRejectedValue(new Error("offline")),
        now,
        { baseUrl, storage },
      ))).rejects.toThrow("offline");
      expect(storage.removeItem).toHaveBeenCalledWith(key);
      expect(storage.values.has(key)).toBe(false);
    }
  });

  it("advances the current sample at the full-hour boundary without counting the previous hour", async () => {
    let nowValue = Date.parse("2026-09-03T09:59:59.999Z");
    const now = () => nowValue;
    const bundleFetcher = vi.fn()
      .mockResolvedValueOnce(bundle({ validAt: "2026-09-03T09:00:00Z", camsStatus: "unavailable" }))
      .mockRejectedValueOnce(new Error("offline"));
    const runtimeOptions = options(bundleFetcher, now, { baseUrl: "/boundary-sixty-minutes" });

    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions))
      .resolves.toMatchObject({ current: { temperature: 20 } });
    nowValue = Date.parse("2026-09-03T10:00:00Z");
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions))
      .resolves.toMatchObject({ current: {
        data_quality: { valid_at_utc: "2026-09-03T10:00:00.000Z" },
        hourly_forecast: expect.arrayContaining([expect.objectContaining({ time: "2026-09-03T10:00:00.000Z" })]),
      } });
  });

  it("advances a terminal CAMS timeout from pending without degrading complete CAMS", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const baseUrl = "/cams-terminal-ranking";
    const pending = bundle({ camsStatus: "pending" });
    const unavailable = bundle({ camsStatus: "unavailable" });

    await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(pending), now, { baseUrl, storage }),
    );
    const terminal = await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(unavailable), now, { baseUrl, storage }),
    );
    expect(terminal.current.data_quality.cams_status).toBe("unavailable");

    const complete = bundle({ camsStatus: "fresh" });
    await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(complete), now, { baseUrl, storage }),
    );
    const noDowngrade = await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(unavailable), now, { baseUrl, storage }),
    );
    expect(noDowngrade.current.data_quality.cams_status).toBe("fresh");
  });

  it("removes revoked CAMS B in every municipality while retaining verified ICON", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/cams-family-revocation";
    const storage = memoryStorage({ unrelated: "keep" });
    const other = municipality(88);
    const bRunId = RUN_AT.replaceAll("-", "").replaceAll(":", "");
    const aRunAt = "2026-09-02T18:00:00Z";

    await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(bundle()), now, { baseUrl, storage }),
    );
    await fetchLocalWeatherV1RuntimeBundle(
      other,
      options(vi.fn().mockResolvedValue(bundle({
        city: other.city,
        istatCode: other.municipality.istatCode,
      })), now, { baseUrl, storage }),
    );
    expect(persistedBundleKeys(storage)).toHaveLength(2);
    const activeKeys = persistedBundleKeys(storage);
    for (const key of activeKeys) storage.setItem(`${key}:candidate`, storage.getItem(key));

    const rolledBack = bundle({
      camsDisabledRunIds: [bRunId],
      camsPublishedAt: "2026-09-03T03:00:00Z",
      camsRevision: 2,
      camsRunAt: aRunAt,
    });
    await expect(fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(rolledBack), now, { baseUrl, storage }),
    )).resolves.toMatchObject({
      current: { data_quality: { cams_run_utc: aRunAt } },
    });

    expect(persistedBundleKeys(storage).filter(key => !key.endsWith(":candidate"))).toHaveLength(2);
    const retainedOther = readLocalWeatherV1PersistedBundle(other, { baseUrl, storage, now });
    expect(retainedOther.current).toMatchObject({
      temperature: 20,
      source: { icon: { status: "available" }, cams: { status: "unavailable" } },
      data_quality: { cams_status: "unavailable", cams_run_utc: null },
      pollen_data: { status: "unavailable" },
      air_quality_data: null,
    });
    expect(retainedOther.current.data_quality.cams_diagnostic).toMatchObject({
      code: "RUN_DISABLED",
      stage: "family",
    });
    for (const key of activeKeys) expect(storage.getItem(`${key}:candidate`)).toBeNull();
    expect(storage.values.get("unrelated")).toBe("keep");
    await expect(fetchLocalWeatherV1RuntimeBundle(
      other,
      options(vi.fn().mockResolvedValue(bundle({
        city: other.city,
        istatCode: other.municipality.istatCode,
      })), now, { baseUrl, storage }),
    )).rejects.toMatchObject({ code: "RUN_DISABLED" });
    const offline = await fetchLocalWeatherV1RuntimeBundle(
      other,
      options(vi.fn().mockRejectedValue(new Error("offline")), now, { baseUrl, storage }),
    );
    expect(offline.current).toMatchObject({
      cache: { runtime_fallback: true },
      source: { icon: { status: "available" }, cams: { status: "unavailable" } },
    });
  });

  it("keeps sanitized ICON durable when quota blocks the replacement CAMS candidate", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/cams-revocation-quota";
    const storage = memoryStorage();
    const key = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const revokedRunId = RUN_AT.replaceAll("-", "").replaceAll(":", "");
    await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(bundle()), now, { baseUrl, storage }),
    );
    const originalSetItem = storage.setItem.getMockImplementation();
    storage.setItem.mockImplementation((targetKey, value) => {
      if (targetKey === `${key}:candidate` && !storage.values.has(targetKey)) {
        const error = new Error("Quota exceeded while staging replacement");
        error.name = "QuotaExceededError";
        throw error;
      }
      return originalSetItem(targetKey, value);
    });
    const rollback = bundle({
      camsDisabledRunIds: [revokedRunId],
      camsPublishedAt: "2026-09-03T03:00:00Z",
      camsRevision: 2,
      camsRunAt: "2026-09-02T18:00:00Z",
    });

    const retained = await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(rollback), now, { baseUrl, storage, force: true }),
    );

    expect(retained.current).toMatchObject({
      temperature: 20,
      source: { icon: { status: "available" }, cams: { status: "unavailable" } },
      data_quality: { cams_status: "unavailable", cams_run_utc: null },
    });
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", {
      baseUrl, storage: { ...storage }, now,
    });
    expect(reopened.current).toMatchObject({
      temperature: 20,
      source: { icon: { status: "available" }, cams: { status: "unavailable" } },
      data_quality: { cams_status: "unavailable", cams_run_utc: null },
    });
  });

  it("recognizes an atomic CAMS sanitation committed just before a storage interruption", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/cams-revocation-interrupted-write";
    const storage = memoryStorage();
    const key = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const revokedRunId = RUN_AT.replaceAll("-", "").replaceAll(":", "");
    await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(bundle()), now, { baseUrl, storage }),
    );
    const originalSetItem = storage.setItem.getMockImplementation();
    let interrupted = false;
    storage.setItem.mockImplementation((targetKey, value) => {
      if (!interrupted && targetKey === key && value.includes('"cams_status":"unavailable"')) {
        interrupted = true;
        originalSetItem(targetKey, value);
        throw new Error("process interrupted immediately after atomic replacement");
      }
      if (targetKey === `${key}:candidate`) throw new Error("candidate staging unavailable");
      return originalSetItem(targetKey, value);
    });
    const rollback = bundle({
      camsDisabledRunIds: [revokedRunId],
      camsPublishedAt: "2026-09-03T03:00:00Z",
      camsRevision: 2,
      camsRunAt: "2026-09-02T18:00:00Z",
    });

    const retained = await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(rollback), now, { baseUrl, storage, force: true }),
    );

    expect(interrupted).toBe(true);
    expect(retained.current.data_quality.cams_status).toBe("unavailable");
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", {
      baseUrl, storage: { ...storage }, now,
    });
    expect(reopened.current).toMatchObject({
      temperature: 20,
      source: { icon: { status: "available" }, cams: { status: "unavailable" } },
      data_quality: { cams_status: "unavailable", cams_run_utc: null },
    });
  });

  it("non ritiene B se currentRow/adapt fallisce dopo aver osservato il rollback ad A", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/cams-family-partial-revocation";
    const storage = memoryStorage();
    const bRunId = RUN_AT.replaceAll("-", "").replaceAll(":", "");
    await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(bundle()), now, { baseUrl, storage }),
    );

    const decisionOnly = bundle({
      camsDisabledRunIds: [bRunId],
      camsPublishedAt: "2026-09-03T03:00:00Z",
      camsRevision: 2,
      camsRunAt: "2026-09-02T18:00:00Z",
    });
    for (const value of [decisionOnly.current, decisionOnly.forecast]) {
      value.data_quality.cams_status = "unavailable";
      value.data_quality.cams_run_utc = null;
      value.data_quality.cams_valid_at_utc = null;
      value.source.cams.status = "unavailable";
      value.source.cams.evidence.stages = {};
      value.source.cams.diagnostic = {
        provider: "cams_europe_pollen",
        status: "unavailable",
        stage: "adapt",
        code: "INVALID_TIMELINE",
      };
    }
    decisionOnly.current.pollen_data.status = "unavailable";

    await expect(fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(decisionOnly), now, { baseUrl, storage }),
    )).resolves.toBe(decisionOnly);
    const [persistedKey] = persistedBundleKeys(storage);
    expect(JSON.parse(storage.values.get(persistedKey)).bundle.current).toMatchObject({
      data_quality: { cams_status: "unavailable", cams_run_utc: null },
      source: {
        cams: {
          evidence: {
            family: {
              active_run_id: "20260902T180000Z",
              disabled_run_ids: [bRunId],
              revision: 2,
            },
          },
          diagnostic: { stage: "adapt", code: "INVALID_TIMELINE" },
        },
      },
    });

    const offline = await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockRejectedValue(new Error("offline")), now, { baseUrl, storage }),
    );
    expect(offline.current).toMatchObject({
      cache: { runtime_fallback: true },
      data_quality: { cams_status: "unavailable", cams_run_utc: null },
      source: {
        cams: {
          evidence: {
            family: {
              active_run_id: "20260902T180000Z",
              disabled_run_ids: [bRunId],
              revision: 2,
            },
          },
        },
      },
    });
  });

  it.each([
    ["senza revocare B", { camsRevision: 2, camsDisabledRunIds: [] }],
    ["senza incrementare revision", { camsRevision: 1, camsDisabledRunIds: ["20260903T000000Z"] }],
  ])("non seleziona un rollback CAMS %s", async (_label, family) => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = `/invalid-cams-rollback-${_label}`;
    const storage = memoryStorage();
    await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(bundle()), now, { baseUrl, storage }),
    );

    await expect(fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(bundle({
        ...family,
        camsPublishedAt: "2026-09-03T03:00:00Z",
        camsRunAt: "2026-09-02T18:00:00Z",
      })), now, { baseUrl, storage }),
    )).rejects.toMatchObject({ code: "CAMS_FAMILY_REGRESSION" });
    expect(readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage, now })
      .current.data_quality.cams_run_utc).toBe(RUN_AT);
  });

  it("does not change ICON temperature while accepting a CAMS-only supplement", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const baseUrl = "/cams-icon-integrity";
    const pending = bundle({ camsStatus: "pending", temperature: 20 });

    await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(pending), now, { baseUrl, storage }),
    );
    const inconsistent = await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(
        vi.fn().mockResolvedValue(bundle({ camsStatus: "fresh", temperature: 21 })),
        now,
        { baseUrl, storage },
      ),
    );
    expect(inconsistent.current).toMatchObject({
      temperature: 20,
      data_quality: { cams_status: "pending" },
    });

    const consistent = await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(
        vi.fn().mockResolvedValue(bundle({ camsStatus: "fresh", temperature: 20 })),
        now,
        { baseUrl, storage },
      ),
    );
    expect(consistent.current).toMatchObject({
      temperature: 20,
      data_quality: { cams_status: "fresh" },
    });
  });

  it("keeps CAMS complete at equal ICON time and never lets an older callback regress it", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const baseUrl = "/monotonic-bundle-cache";
    const complete = bundle({ camsStatus: "fresh", temperature: 21 });

    await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(complete), now, { baseUrl, storage }),
    );
    for (const camsStatus of ["pending", "unavailable"]) {
      const selected = await fetchLocalWeatherV1RuntimeBundle(
        "Pordenone",
        options(
          vi.fn().mockResolvedValue(bundle({ camsStatus, temperature: 19 })),
          now,
          { baseUrl, storage },
        ),
      );
      expect(selected.current).toMatchObject({
        temperature: 21,
        data_quality: { cams_status: "fresh" },
      });
    }

    const newerIcon = bundle({
      camsStatus: "pending",
      runAt: "2026-09-03T06:00:00Z",
      temperature: 24,
    });
    const selectedNewer = await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(newerIcon), now, { baseUrl, storage }),
    );
    expect(selectedNewer.current).toMatchObject({
      temperature: 24,
      data_quality: { cams_status: "fresh", run_utc: "2026-09-03T06:00:00Z" },
    });

    const selectedAgainstOldCallback = await fetchLocalWeatherV1RuntimeBundle(
      "Pordenone",
      options(vi.fn().mockResolvedValue(complete), now, { baseUrl, storage }),
    );
    expect(selectedAgainstOldCallback.current).toMatchObject({
      temperature: 24,
      data_quality: { cams_status: "fresh", run_utc: "2026-09-03T06:00:00Z" },
    });
  });

  it("uses the next real cached sample offline instead of expiring ICON after one hour", async () => {
    let nowValue = Date.parse("2026-09-03T10:15:00Z");
    const now = () => nowValue;
    const bundleFetcher = vi.fn()
      .mockResolvedValueOnce(bundle())
      .mockRejectedValue(new Error("offline"));
    const runtimeOptions = options(bundleFetcher, now);
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);

    nowValue = Date.parse("2026-09-03T11:01:00Z");
    const retained = await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    expect(retained.current.data_quality.valid_at_utc).toBe("2026-09-03T11:00:00.000Z");
    expect(retained.current.hourly_forecast).toHaveLength(47);
    expect(retained.current.hourly_forecast[0].time).toBe("2026-09-03T12:00:00.000Z");
  });

  it.each([48, 36, 24, 12])("accepts %i actual future hourly samples without requiring 48", async hourCount => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const expected = bundle({ hourCount, camsStatus: "unavailable" });
    const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(expected), now, { baseUrl: `/actual-future-${hourCount}` },
    ));
    expect(result.current.hourly_forecast).toHaveLength(hourCount);
    expect(result.current.hourly_next_12h?.length ?? 12).toBe(12);
    expect(result.current.hourly_forecast.every(row => Date.parse(row.time) >= now())).toBe(true);
  });

  it("rejects eleven future samples and never counts the past hour to reach twelve", async () => {
    for (const [hourCount, instant] of [[11, "2026-09-03T10:15:00Z"], [12, "2026-09-03T11:15:00Z"]]) {
      const now = () => Date.parse(instant);
      await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
        vi.fn().mockResolvedValue(bundle({ hourCount, camsStatus: "unavailable" })), now,
        { baseUrl: `/not-twelve-${hourCount}` },
      ))).rejects.toMatchObject({ code: "ICON_BUNDLE_UNUSABLE" });
    }
  });

  it.each(["gap", "duplicate", "invalid"])("does not repair an hourly timeline containing a %s", async flaw => {
    const value = bundle({ camsStatus: "unavailable" });
    if (flaw === "gap") value.current.hourly_forecast.splice(3, 1);
    if (flaw === "duplicate") value.current.hourly_forecast[3] = { ...value.current.hourly_forecast[2] };
    if (flaw === "invalid") value.current.hourly_forecast[3].time = "not-a-time";
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(value), () => Date.parse("2026-09-03T10:15:00Z"),
      { baseUrl: `/unrepaired-${flaw}` },
    ))).rejects.toMatchObject({ code: "ICON_BUNDLE_UNUSABLE" });
  });

  it("advances offline through 48, 36, 24 and 12 real hours, then rejects eleven and recovers a new run", async () => {
    let nowValue = Date.parse("2026-09-03T10:15:00Z");
    const now = () => nowValue;
    const original = bundle({ camsStatus: "unavailable" });
    original.current.hourly_forecast.forEach((row, index) => { row.temperature = index + 1; });
    const bundleFetcher = vi.fn().mockResolvedValueOnce(original).mockRejectedValue(new Error("offline"));
    const runtimeOptions = options(bundleFetcher, now, { baseUrl: "/decreasing-real-window" });
    expect((await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions)).current.hourly_forecast).toHaveLength(48);
    for (const elapsed of [12, 24, 36]) {
      nowValue = Date.parse("2026-09-03T10:15:00Z") + elapsed * 60 * 60 * 1000;
      const retained = await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
      expect(retained.current.hourly_forecast).toHaveLength(48 - elapsed);
      expect(retained.current.temperature).toBe(elapsed);
      expect(Date.parse(retained.current.data_quality.valid_at_utc)).toBe(nowValue - 15 * 60 * 1000);
      expect(retained.current.hourly_forecast.every(row => Date.parse(row.time) >= nowValue)).toBe(true);
      expect(retained.current.cache.runtime_fallback).toBe(true);
    }
    nowValue += 60 * 60 * 1000;
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions)).rejects.toThrow("offline");

    const replacement = bundle({ runAt: "2026-09-04T12:00:00Z", validAt: "2026-09-04T23:00:00Z",
      camsStatus: "unavailable", temperature: 18 });
    bundleFetcher.mockResolvedValueOnce(replacement);
    const recovered = await fetchLocalWeatherV1RuntimeBundle("Pordenone", { ...runtimeOptions, force: true });
    expect(recovered.current.hourly_forecast).toHaveLength(48);
    expect(recovered.current.temperature).toBe(18);
    expect(recovered.current.data_quality.run_utc).toBe("2026-09-04T12:00:00Z");
    expect(recovered.current.cache.runtime_fallback).not.toBe(true);
  });

  it("rebases persisted real samples after reopening instead of freezing the saved temperature", async () => {
    let nowValue = Date.parse("2026-09-03T10:15:00Z");
    const now = () => nowValue;
    const storage = memoryStorage();
    const baseUrl = "/reopen-real-hour";
    const original = bundle({ camsStatus: "unavailable" });
    original.current.hourly_forecast[2].temperature = 27;
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(original), now, { baseUrl, storage }));
    nowValue = Date.parse("2026-09-03T13:15:00Z");
    const reopenedStorage = { ...storage };
    const bootstrap = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage: reopenedStorage, now });
    expect(bootstrap.current).toMatchObject({ temperature: 27,
      data_quality: { valid_at_utc: "2026-09-03T13:00:00.000Z" } });
    expect(bootstrap.current.hourly_forecast).toHaveLength(45);
    const offline = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockRejectedValue(new Error("offline")), now, { baseUrl, storage: reopenedStorage },
    ));
    expect(offline.current.temperature).toBe(27);
    expect(offline.current.cache.runtime_fallback_source).toBe("verified_persistent_bundle");
  });

  it("does not keep the last temperature when the actual current sample is absent", async () => {
    const now = () => Date.parse("2026-09-03T11:15:00Z");
    const missingCurrent = bundle({ camsStatus: "unavailable" });
    missingCurrent.current.hourly_forecast.shift();
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(missingCurrent), now, { baseUrl: "/no-current-value" },
    ))).rejects.toMatchObject({ code: "ICON_BUNDLE_UNUSABLE" });
  });

  it("keeps the last verified CAMS sample when the current hour is absent", async () => {
    let nowValue = Date.parse("2026-09-03T10:15:00Z");
    const now = () => nowValue;
    const original = bundle();
    original.current.air_quality_data = { uv_index: 3, pm10: 14 };
    original.current.pollen_data.values = { birch_pollen: 12 };
    const storage = memoryStorage();
    const baseUrl = "/expired-cams-keeps-icon";
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(original), now, { baseUrl, storage }));
    nowValue = Date.parse("2026-09-03T11:15:00Z");
    const retained = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage, now });
    expect(retained.current.hourly_forecast).toHaveLength(47);
    expect(retained.current.source.icon.status).toBe("available");
    expect(retained.current.data_quality).toMatchObject({
      cams_status: "stale", cams_sample_status: "last_known", cams_valid_at_utc: VALID_AT,
    });
    expect(retained.forecast.data_quality.cams_status).toBe("stale");
    expect(retained.current.air_quality_data).toMatchObject({ uv_index: 3, pm10: 14,
      sample_status: "last_known" });
    expect(retained.current.pollen_data).toMatchObject({
      status: "experimental_model_snapshot", values: { birch_pollen: 12 },
      sample_status: "last_known",
    });
  });

  it("keeps an active CAMS series as timestamped last-known after 30 hours and offline reopening", async () => {
    const run = Date.parse(RUN_AT);
    let nowValue = run + 29 * 60 * 60 * 1000 + 15 * 60 * 1000;
    const now = () => nowValue;
    const validAt = new Date(run + 29 * 60 * 60 * 1000).toISOString();
    const active = bundle({
      camsStatus: "stale",
      camsValidAt: validAt,
      hourCount: 42,
      validAt,
    });
    active.current.pollen_data = {
      status: "experimental_model_snapshot",
      valid_at_utc: validAt,
      values: { ambrosia: 4.2 },
    };
    active.current.air_quality_data = {
      run_at: RUN_AT,
      valid_at: validAt,
      values: { ozone: 41.5 },
    };
    const storage = memoryStorage();
    const baseUrl = "/active-cams-past-usable";
    const fetcher = vi.fn().mockResolvedValueOnce(active).mockRejectedValue(new Error("offline"));
    const runtimeOptions = options(fetcher, now, { baseUrl, storage, force: true });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);

    nowValue = run + 30 * 60 * 60 * 1000 + 1;
    const retained = await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    expect(retained.current.data_quality).toMatchObject({
      cams_sample_status: "last_known",
      cams_status: "stale",
      cams_valid_at_utc: validAt,
    });
    expect(retained.forecast.data_quality.cams_valid_at_utc).toBe(validAt);
    expect(retained.current.pollen_data).toMatchObject({
      sample_status: "last_known",
      values: { ambrosia: 4.2 },
    });
    expect(retained.current.air_quality_data).toMatchObject({
      sample_status: "last_known",
      values: { ozone: 41.5 },
    });
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", {
      baseUrl, storage: { ...storage }, now,
    });
    expect(reopened.current.data_quality.cams_sample_status).toBe("last_known");
    expect(reopened.current.air_quality_data.values.ozone).toBe(41.5);
  });

  it("adds a verified hourly series to a same-run legacy active and selects its later sample offline", async () => {
    const run = Date.parse(RUN_AT);
    let nowValue = run + 10 * HOUR_MS + 15 * 60 * 1000;
    const now = () => nowValue;
    const legacy = bundle();
    legacy.current.pollen_data = {
      status: "experimental_model_snapshot",
      valid_at_utc: VALID_AT,
      values: { ambrosia: 10.25 },
    };
    legacy.current.air_quality_data = {
      run_at: RUN_AT,
      valid_at: VALID_AT,
      values: { ozone: 110 },
    };
    legacy.current.hourly_next_12h = legacy.current.hourly_forecast.slice(0, 12);
    const candidate = withVerifiedCamsHourlyCache(bundle());
    const storage = memoryStorage();
    const baseUrl = "/same-run-hourly-cache-migration";
    const fetcher = vi.fn().mockResolvedValueOnce(legacy).mockResolvedValueOnce(candidate);
    const runtimeOptions = options(fetcher, now, { baseUrl, storage, force: true });

    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    storage.setItem.mockClear();
    storage.removeItem.mockClear();
    const enriched = await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    expect(enriched.current.air_quality_data.values.ozone).toBe(110);
    expect(enriched.current.cams_hourly_cache.samples).toHaveLength(31);
    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const writtenKeys = storage.setItem.mock.calls.map(([key]) => key);
    expect(writtenKeys.indexOf(candidateKey)).toBeGreaterThanOrEqual(0);
    expect(writtenKeys.indexOf(activeKey)).toBeGreaterThan(writtenKeys.indexOf(candidateKey));
    expect(storage.values.has(candidateKey)).toBe(false);

    nowValue = run + 30 * HOUR_MS + 1;
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", {
      baseUrl, storage: { ...storage }, now,
    });
    expect(reopened.current.data_quality).toMatchObject({
      cams_status: "stale",
      cams_sample_status: "last_known",
      cams_valid_at_utc: new Date(run + 30 * HOUR_MS).toISOString(),
    });
    expect(reopened.current.air_quality_data).toMatchObject({
      sample_status: "last_known",
      values: { ozone: 130 },
    });
    expect(reopened.current.pollen_data).toMatchObject({
      sample_status: "last_known",
      values: { ambrosia: 30.25 },
    });
  });

  it("reconstructs and selects the exact future sample from a compact v2 cache", async () => {
    const run = Date.parse(RUN_AT);
    let nowValue = run + 10 * HOUR_MS + 15 * 60 * 1000;
    const now = () => nowValue;
    const value = withVerifiedCamsHourlyCacheV2(bundle());
    value.current.pollen_data = {
      status: "experimental_model_snapshot",
      valid_at_utc: VALID_AT,
      values: { ambrosia: 10.5 },
    };
    value.current.air_quality_data = {
      run_at: RUN_AT,
      valid_at: VALID_AT,
      values: Object.fromEntries(CAMS_AIR_FIELDS.map((id, field) => [id, 110 + field / 10])),
    };
    const storage = memoryStorage();
    const baseUrl = "/compact-v2-future-selection";
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(value), now, { baseUrl, storage, force: true },
    ));

    nowValue = run + 35 * HOUR_MS + 1;
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", {
      baseUrl, storage: { ...storage }, now,
    });
    expect(reopened.current.cams_hourly_cache).toMatchObject({ version: 2, sample_count: 97 });
    expect(reopened.current.data_quality).toMatchObject({
      cams_status: "stale",
      cams_sample_status: "last_known",
      cams_valid_at_utc: new Date(run + 35 * HOUR_MS).toISOString().replace(".000Z", "Z"),
    });
    expect(reopened.current.pollen_data).toMatchObject({
      sample_status: "last_known",
      values: { ambrosia: 35.5 },
    });
    expect(reopened.current.pollen_data.all_variables[0].quality_flags).toEqual(["interpolated"]);
    expect(reopened.current.air_quality_data).toMatchObject({
      sample_status: "last_known",
      values: {
        "particulate_matter_2.5um": 135,
        "particulate_matter_10um": 135.1,
        ozone: 135.2,
        nitrogen_dioxide: 135.3,
      },
    });
  });

  it("stages a CAMS delta under the observed device quota and promotes without evicting", async () => {
    const STORAGE_QUOTA = 5_242_880;
    const OBSERVED_INITIAL_USAGE = 5_176_800;
    const OBSERVED_ACTIVE_CHARACTERS = 70_169;
    const OBSERVED_TARGET_CHARACTERS = 82_968;
    const OBSERVED_PROMOTION_DELTA = OBSERVED_TARGET_CHARACTERS - OBSERVED_ACTIVE_CHARACTERS;
    let nowValue = Date.parse("2026-09-03T10:15:00Z");
    const now = () => nowValue;
    const baseUrl = "/compact-v2-quota-atomic-promotion";
    const completeCamsDomain = value => {
      for (const part of [value.current, value.forecast]) {
        part.source.status = "available";
        part.source.label = "ItaliaMeteo ICON-2I e CAMS · contratto locale v1";
        part.model_support = { icon2i: true, cams: true, open_meteo: false };
        part.data_quality.cams_sample_status = "current";
        part.data_quality.cams_diagnostic = null;
        part.data_quality.capability_gaps = [];
      }
      value.current.pollen = { overall: "low" };
      return value;
    };
    const activeFixture = (paddingLength = 0, camsPaddingLength = 0) => {
      const value = bundle();
      value.current.pollen_data = {
        status: "experimental_model_snapshot",
        valid_at_utc: VALID_AT,
        values: { ambrosia: 10.5 },
        device_cams_padding: "c".repeat(camsPaddingLength),
      };
      value.current.air_quality_data = {
        run_at: RUN_AT,
        valid_at: VALID_AT,
        values: Object.fromEntries(CAMS_AIR_FIELDS.map((id, field) => [id, 110 + field / 10])),
      };
      value.current.hourly_next_12h = value.current.hourly_forecast.slice(0, 12);
      // The compact unit fixture omits many verified fields present in the
      // 70,169-character device record. Keep their measured storage footprint
      // without changing the cache data being exercised.
      value.current.device_record_shape_padding = "x".repeat(paddingLength);
      value.current.cams_hourly_cache = null;
      return completeCamsDomain(value);
    };
    const targetFixture = (paddingLength = 0) => {
      const value = withVerifiedCamsHourlyCacheV2(bundle({
        camsValidAt: new Date(Date.parse(RUN_AT) + 11 * HOUR_MS).toISOString(),
      }));
      value.current.pollen_data = {
        status: "experimental_model_snapshot",
        valid_at_utc: new Date(Date.parse(RUN_AT) + 11 * HOUR_MS).toISOString(),
        values: { ambrosia: 11.5 },
        device_cams_padding: "",
      };
      value.current.air_quality_data = {
        run_at: RUN_AT,
        valid_at: new Date(Date.parse(RUN_AT) + 11 * HOUR_MS).toISOString(),
        values: Object.fromEntries(CAMS_AIR_FIELDS.map((id, field) => [id, 111 + field / 10])),
      };
      value.current.hourly_next_12h = value.current.hourly_forecast.slice(0, 12);
      value.current.device_record_shape_padding = "x".repeat(paddingLength);
      return completeCamsDomain(value);
    };

    const calibrationStorage = memoryStorage();
    const calibrationBaseUrl = `${baseUrl}-calibration`;
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(activeFixture()), now,
      { baseUrl: calibrationBaseUrl, storage: calibrationStorage, verificationNow: () => 1 },
    ));
    const calibrationKey = getLocalWeatherV1BundleCacheKey("Pordenone", {
      baseUrl: calibrationBaseUrl,
    });
    const compactActiveCharacters = calibrationStorage.getItem(calibrationKey).length;
    nowValue = Date.parse("2026-09-03T11:15:00Z");
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(targetFixture()), now,
      { baseUrl: calibrationBaseUrl, storage: calibrationStorage, force: true,
        verificationNow: () => 1 },
    ));
    const compactTargetCharacters = calibrationStorage.getItem(calibrationKey).length;
    const camsPaddingLength = compactTargetCharacters
      - compactActiveCharacters
      - OBSERVED_PROMOTION_DELTA;
    expect(camsPaddingLength).toBeGreaterThan(0);

    nowValue = Date.parse("2026-09-03T10:15:00Z");
    const paddedCalibrationStorage = memoryStorage();
    const paddedCalibrationBaseUrl = `${baseUrl}-padded-calibration`;
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(activeFixture(0, camsPaddingLength)), now,
      { baseUrl: paddedCalibrationBaseUrl, storage: paddedCalibrationStorage,
        verificationNow: () => 1 },
    ));
    const paddedCalibrationKey = getLocalWeatherV1BundleCacheKey("Pordenone", {
      baseUrl: paddedCalibrationBaseUrl,
    });
    const paddingLength = OBSERVED_ACTIVE_CHARACTERS
      - paddedCalibrationStorage.getItem(paddedCalibrationKey).length;
    expect(paddingLength).toBeGreaterThan(0);

    const storage = memoryStorage();
    const active = activeFixture(paddingLength, camsPaddingLength);
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(active), now, { baseUrl, storage, verificationNow: () => 1 },
    ));
    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const initialActive = storage.getItem(activeKey);
    expect(initialActive).toHaveLength(OBSERVED_ACTIVE_CHARACTERS);
    const usedCharacters = () => [...storage.values]
      .reduce((total, [key, value]) => total + key.length + value.length, 0);
    const fillerKey = "unrelated:quota-fixture";
    const fillerLength = OBSERVED_INITIAL_USAGE - usedCharacters() - fillerKey.length;
    expect(fillerLength).toBeGreaterThan(0);
    storage.values.set(fillerKey, "x".repeat(fillerLength));
    expect(usedCharacters()).toBe(OBSERVED_INITIAL_USAGE);

    nowValue = Date.parse("2026-09-03T11:15:00Z");
    const compact = targetFixture(paddingLength);
    const successfulOperations = [];
    const failedOperations = [];
    let fullCandidateCharacters = null;
    let deltaCharacters = null;
    let deltaFootprint = null;
    const originalSetItem = storage.setItem.getMockImplementation();
    const originalRemoveItem = storage.removeItem.getMockImplementation();
    storage.setItem.mockImplementation((key, value) => {
      const previous = storage.values.get(key);
      const projected = usedCharacters()
        - (previous === undefined ? 0 : key.length + previous.length)
        + key.length + value.length;
      if (projected > STORAGE_QUOTA) {
        if (key === candidateKey && fullCandidateCharacters === null) {
          fullCandidateCharacters = value.length;
        }
        failedOperations.push(`set:${key}`);
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      if (key === candidateKey && JSON.parse(value)?.kind === "cams-delta") {
        deltaCharacters = value.length;
        deltaFootprint = key.length + value.length;
      }
      originalSetItem(key, value);
      successfulOperations.push(`set:${key}`);
    });
    storage.removeItem.mockImplementation((key) => {
      expect(storage.values.has(activeKey)).toBe(true);
      const existed = storage.values.has(key);
      originalRemoveItem(key);
      expect(storage.values.has(activeKey)).toBe(true);
      if (existed) successfulOperations.push(`remove:${key}`);
    });

    const selected = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(compact), now,
      { baseUrl, storage, force: true, verificationNow: () => 1 },
    ));

    expect(selected.current.cams_hourly_cache)
      .toMatchObject({ version: 2, sample_count: 97 });
    expect(storage.getItem(candidateKey)).toBeNull();
    expect(storage.getItem(activeKey)).not.toBe(initialActive);
    expect(fullCandidateCharacters).toBe(OBSERVED_TARGET_CHARACTERS);
    expect(deltaFootprint).toBeLessThanOrEqual(
      STORAGE_QUOTA - OBSERVED_INITIAL_USAGE
        - (OBSERVED_TARGET_CHARACTERS - OBSERVED_ACTIVE_CHARACTERS),
    );
    expect(deltaCharacters).toBeGreaterThan(0);
    expect(failedOperations).toEqual([`set:${candidateKey}`]);
    const stagedAt = successfulOperations.indexOf(`set:${candidateKey}`);
    const removedAt = successfulOperations.indexOf(`remove:${candidateKey}`);
    const promotedAt = successfulOperations.indexOf(`set:${activeKey}`);
    expect(stagedAt).toBeGreaterThanOrEqual(0);
    expect(promotedAt).toBeGreaterThan(stagedAt);
    expect(removedAt).toBeGreaterThan(promotedAt);
    expect(successfulOperations).not.toContain(`remove:${activeKey}`);
    expect(storage.values.get(fillerKey)).toHaveLength(fillerLength);

    nowValue = Date.parse(RUN_AT) + 35 * HOUR_MS + 1;
    const offlineFetcher = vi.fn().mockRejectedValue(new Error("offline"));
    const reopened = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      offlineFetcher,
      now,
      { baseUrl, storage: { ...storage }, force: true },
    ));
    expect(offlineFetcher).toHaveBeenCalledOnce();
    expect(reopened.current.cams_hourly_cache).toMatchObject({ version: 2, sample_count: 97 });
    expect(reopened.current.data_quality).toMatchObject({
      cams_sample_status: "last_known",
      cams_valid_at_utc: new Date(Date.parse(RUN_AT) + 35 * HOUR_MS)
        .toISOString().replace(".000Z", "Z"),
    });
    expect(reopened.current.pollen_data.values.ambrosia).toBe(35.5);
    expect(reopened.current.air_quality_data.values).toMatchObject({
      "particulate_matter_2.5um": 135,
      "particulate_matter_10um": 135.1,
      ozone: 135.2,
      nitrogen_dioxide: 135.3,
    });
    expect(storage.getItem(candidateKey)).toBeNull();
    expect(storage.values.get(fillerKey)).toHaveLength(fillerLength);
  });

  it("preserves the ICON verification timestamp while promoting a deferred CAMS delta", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    let verificationNowValue = 1_000;
    const verificationNow = () => verificationNowValue;
    const baseUrl = "/cams-delta-deferred-new-icon-verification";
    const storage = memoryStorage();
    const active = withDeltaEligibleCamsShape(bundle());
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(active), now,
      { baseUrl, storage, force: true, verificationNow },
    ));

    let publishCams;
    const onCamsUpdate = vi.fn();
    verificationNowValue = 2_000;
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn((_location, fetchOptions) => {
        publishCams = fetchOptions.onCamsUpdate;
        return active;
      }),
      now,
      { baseUrl, storage, force: true, deferCams: true, onCamsUpdate, verificationNow },
    ));

    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    expect(JSON.parse(storage.getItem(activeKey)).verifiedAt).toBe(2_000);
    const originalSetItem = storage.setItem.getMockImplementation();
    let rejectedFullCandidates = 0;
    let stagedDeltas = 0;
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === candidateKey && parsed?.kind !== "cams-delta") {
        rejectedFullCandidates += 1;
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      if (key === candidateKey && parsed?.kind === "cams-delta") stagedDeltas += 1;
      originalSetItem(key, value);
    });
    storage.removeItem.mockClear();

    verificationNowValue = 3_000;
    publishCams(withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle())));
    await vi.waitFor(() => expect(onCamsUpdate).toHaveBeenCalledOnce());

    const promoted = JSON.parse(storage.getItem(activeKey));
    expect(promoted.verifiedAt).toBe(2_000);
    expect(promoted.camsVerifiedAt).toBe(3_000);
    expect(promoted.bundle.current.cams_hourly_cache)
      .toMatchObject({ version: 2, sample_count: 97 });
    expect(rejectedFullCandidates).toBe(1);
    expect(stagedDeltas).toBe(1);
    expect(storage.getItem(candidateKey)).toBeNull();
    expect(storage.removeItem.mock.calls.every(([key]) => key === candidateKey)).toBe(true);
  });

  it("rebases deferred CAMS onto durable ICON when the newer ICON cannot fit quota", async () => {
    let nowValue = Date.parse("2026-09-03T10:15:00Z");
    const now = () => nowValue;
    let verificationNowValue = 1_000;
    const verificationNow = () => verificationNowValue;
    const baseUrl = "/cams-delta-deferred-rebase-durable-icon";
    const storage = memoryStorage();
    const active = withDeltaEligibleCamsShape(bundle());
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(active), now,
      { baseUrl, storage, force: true, verificationNow },
    ));

    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const initialActive = storage.getItem(activeKey);
    const rawActive = JSON.parse(initialActive).bundle;
    const unrelatedCaches = {
      "unrelated:icon-cache": "other-icon-data",
      "unrelated:cams-cache": "other-cams-data",
    };
    for (const [key, value] of Object.entries(unrelatedCaches)) storage.values.set(key, value);

    // Reproduce a real delayed supplement: the durable record was stored at
    // 10:15, then the clock advanced far enough that its prepared view rebases
    // the current ICON sample and trims past hourly rows. The CAMS delta must
    // still be based on the byte-identical raw record, not that transient view.
    nowValue = Date.parse(RUN_AT) + 28 * HOUR_MS + 15 * 60 * 1000;
    const preparedActive = readLocalWeatherV1PersistedBundle("Pordenone", {
      baseUrl, storage, now,
    });
    expect(preparedActive.current.data_quality.valid_at_utc)
      .toBe(new Date(Date.parse(RUN_AT) + 28 * HOUR_MS).toISOString());
    expect(preparedActive.current.data_quality.valid_at_utc)
      .not.toBe(rawActive.current.data_quality.valid_at_utc);
    expect(preparedActive.current.hourly_forecast.length)
      .toBeLessThan(rawActive.current.hourly_forecast.length);

    const newerIconRun = "2026-09-03T06:00:00Z";
    const laterValidAt = new Date(Date.parse(RUN_AT) + 28 * HOUR_MS).toISOString();
    const newerCamsRun = "2026-09-03T12:00:00Z";
    const newerIcon = withDeltaEligibleCamsShape(bundle({
      runAt: newerIconRun,
      validAt: laterValidAt,
    }));
    const supplement = withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle({
      camsRevision: 2,
      camsRunAt: newerCamsRun,
      camsValidAt: laterValidAt,
      runAt: newerIconRun,
      validAt: laterValidAt,
    })));
    const originalSetItem = storage.setItem.getMockImplementation();
    let rejectedFullCandidates = 0;
    let stagedDeltas = 0;
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === candidateKey && parsed?.kind !== "cams-delta") {
        rejectedFullCandidates += 1;
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      if (key === candidateKey && parsed?.kind === "cams-delta") stagedDeltas += 1;
      originalSetItem(key, value);
    });

    let publishCams;
    const onCamsUpdate = vi.fn();
    const iconFetcher = vi.fn((_location, fetchOptions) => {
      publishCams = fetchOptions.onCamsUpdate;
      return newerIcon;
    });
    verificationNowValue = 2_000;
    const initial = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      iconFetcher,
      now,
      { baseUrl, storage, force: true, deferCams: true, onCamsUpdate, verificationNow },
    ));

    expect(initial.current.data_quality.run_utc).toBe(RUN_AT);
    expect(initial.current.cache).toMatchObject({
      runtime_fallback: true,
      runtime_fallback_source: "candidate_not_committed",
      runtime_fallback_code: "CACHE_PERSIST_FAILED",
    });
    expect(initial.current.data_quality.flags).toEqual(expect.arrayContaining([
      "runtime_refresh_failed_bundle_retained",
      "runtime_candidate_not_committed",
    ]));
    expect(storage.getItem(activeKey)).toBe(initialActive);
    expect(publishCams).toBeTypeOf("function");

    verificationNowValue = 3_000;
    publishCams(supplement);
    await vi.waitFor(() => expect(onCamsUpdate).toHaveBeenCalledOnce());

    const promoted = JSON.parse(storage.getItem(activeKey));
    expect(promoted.verifiedAt).toBe(1_000);
    expect(promoted.camsVerifiedAt).toBe(3_000);
    expect(promoted.bundle.current.data_quality.run_utc).toBe(RUN_AT);
    expect(promoted.bundle.current.source.icon.evidence.path)
      .toBe(active.current.source.icon.evidence.path);
    expect(promoted.bundle.current.data_quality.cams_run_utc).toBe(newerCamsRun);
    expect(promoted.bundle.current.cams_hourly_cache)
      .toMatchObject({ version: 2, sample_count: 97 });
    expect(onCamsUpdate.mock.calls[0][0].current.data_quality.run_utc).toBe(RUN_AT);
    expect(onCamsUpdate.mock.calls[0][0].current.cache).toMatchObject({
      runtime_fallback: true,
      runtime_fallback_source: "candidate_not_committed",
      runtime_fallback_code: "CACHE_PERSIST_FAILED",
    });
    expect(onCamsUpdate.mock.calls[0][0].current.data_quality.flags)
      .toContain("runtime_candidate_not_committed");
    expect(onCamsUpdate.mock.calls[0][0].current.cams_hourly_cache)
      .toMatchObject({ version: 2, sample_count: 97 });
    expect(rejectedFullCandidates).toBe(2);
    expect(stagedDeltas).toBe(1);
    expect(storage.getItem(candidateKey)).toBeNull();
    for (const [key, value] of Object.entries(unrelatedCaches)) {
      expect(storage.getItem(key)).toBe(value);
    }

    nowValue += 5 * HOUR_MS;
    const offlineValidAt = new Date(Date.parse(RUN_AT) + 33 * HOUR_MS)
      .toISOString().replace(".000Z", "Z");
    const offlineFetcher = vi.fn().mockRejectedValue(new Error("offline"));
    const reopened = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      offlineFetcher,
      now,
      { baseUrl, storage: { ...storage }, force: true },
    ));
    expect(offlineFetcher).toHaveBeenCalledOnce();
    expect(reopened.current.data_quality.run_utc).toBe(RUN_AT);
    expect(reopened.current.source.icon.evidence.path)
      .toBe(active.current.source.icon.evidence.path);
    expect(reopened.current.cams_hourly_cache)
      .toMatchObject({ version: 2, sample_count: 97 });
    expect(reopened.current.data_quality.cams_valid_at_utc).toBe(offlineValidAt);
    expect(reopened.current.pollen_data.values.ambrosia).toBe(21.5);
    expect(reopened.current.air_quality_data.values).toMatchObject({
      "particulate_matter_2.5um": 121,
      "particulate_matter_10um": 121.1,
      ozone: 121.2,
      nitrogen_dioxide: 121.3,
    });
    for (const [key, value] of Object.entries(unrelatedCaches)) {
      expect(storage.getItem(key)).toBe(value);
    }

    storage.setItem.mockImplementation(originalSetItem);
    verificationNowValue = 4_000;
    iconFetcher.mockResolvedValue(supplement);
    const recovered = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      iconFetcher, now,
      { baseUrl, storage, force: true, verificationNow },
    ));
    expect(recovered.current.data_quality.run_utc).toBe(newerIconRun);
    expect(recovered.current.cache).not.toHaveProperty("runtime_fallback");
    expect(recovered.current.data_quality.flags)
      .not.toContain("runtime_candidate_not_committed");
    expect(JSON.parse(storage.getItem(activeKey)).bundle.current.data_quality.run_utc)
      .toBe(newerIconRun);
  });

  it("mantiene il marker quota nel fast path e nel fallback fino al commit ICON", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    let verificationNowValue = 1_000;
    const verificationNow = () => verificationNowValue;
    const baseUrl = "/candidate-marker-sequential-paths";
    const storage = memoryStorage();
    const active = bundle({ camsStatus: "unavailable", temperature: 20 });
    const candidate = bundle({
      camsStatus: "unavailable",
      runAt: "2026-09-03T06:00:00Z",
      temperature: 24,
    });
    let outcome = active;
    const fetcher = vi.fn(() => {
      if (outcome instanceof Error) throw outcome;
      return outcome;
    });
    const runtimeOptions = options(fetcher, now, {
      baseUrl,
      storage,
      verificationNow,
      verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS,
    });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", {
      ...runtimeOptions,
      force: true,
    });

    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const originalSetItem = storage.setItem.getMockImplementation();
    storage.setItem.mockImplementation((key, value) => {
      if (key === `${activeKey}:candidate`) {
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      originalSetItem(key, value);
    });
    outcome = candidate;
    verificationNowValue = 2_000;
    const failed = await fetchLocalWeatherV1RuntimeBundle("Pordenone", {
      ...runtimeOptions,
      force: true,
    });
    expect(failed.current.cache.runtime_fallback_source).toBe("candidate_not_committed");

    const callsBeforeFastPath = fetcher.mock.calls.length;
    verificationNowValue = 3_000;
    const fastPath = await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    expect(fetcher).toHaveBeenCalledTimes(callsBeforeFastPath);
    expect(fastPath.current.cache).toMatchObject({
      runtime_fallback_source: "candidate_not_committed",
      runtime_fallback_code: "CACHE_PERSIST_FAILED",
    });

    outcome = new Error("offline after candidate failure");
    const caught = await fetchLocalWeatherV1RuntimeBundle("Pordenone", {
      ...runtimeOptions,
      force: true,
    });
    expect(caught.current.cache).toMatchObject({
      runtime_fallback_source: "candidate_not_committed",
      runtime_fallback_code: "CACHE_PERSIST_FAILED",
    });
    expect(caught.current.data_quality.flags).toContain("runtime_candidate_not_committed");

    storage.setItem.mockImplementation(originalSetItem);
    outcome = candidate;
    verificationNowValue = 4_000;
    const committed = await fetchLocalWeatherV1RuntimeBundle("Pordenone", {
      ...runtimeOptions,
      force: true,
    });
    expect(committed.current.data_quality.run_utc).toBe("2026-09-03T06:00:00Z");
    expect(committed.current.cache).not.toHaveProperty("runtime_fallback");
    expect(committed.current.data_quality.flags)
      .not.toContain("runtime_candidate_not_committed");
  });

  it("promotes a same-object deferred CAMS delta with a v2 cache and advancing clock", async () => {
    let nowValue = Date.parse("2026-09-03T10:15:00Z");
    let advanceClock = false;
    let elapsedMilliseconds = 0;
    const now = () => nowValue + (advanceClock ? elapsedMilliseconds++ : 0);
    let verificationNowValue = 1_000;
    const verificationNow = () => verificationNowValue;
    const baseUrl = "/cams-delta-deferred-same-run-real-gaps";
    const storage = memoryStorage();
    const realCapabilityGaps = [
      "visibility",
      "precipitation_probability",
      "station_observations",
    ];
    const withRealCapabilityGaps = value => {
      for (const part of [value.current, value.forecast]) {
        part.data_quality.capability_gaps = [...realCapabilityGaps];
      }
      return value;
    };
    const active = withRealCapabilityGaps(withDeltaEligibleCamsShape(
      withVerifiedCamsHourlyCacheV2(bundle()),
    ));
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(active), now,
      { baseUrl, storage, force: true, verificationNow },
    ));

    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const initialActive = storage.getItem(activeKey);
    const unrelatedCaches = {
      "unrelated:icon-cache": "other-icon-data",
      "unrelated:cams-cache": "other-cams-data",
    };
    for (const [key, value] of Object.entries(unrelatedCaches)) storage.values.set(key, value);

    nowValue = Date.parse(RUN_AT) + 20 * HOUR_MS + 15 * 60 * 1000;
    const laterValidAt = new Date(Date.parse(RUN_AT) + 20 * HOUR_MS)
      .toISOString().replace(".000Z", "Z");
    const newerIcon = withRealCapabilityGaps(withDeltaEligibleCamsShape(bundle({
      runAt: RUN_AT,
      validAt: laterValidAt,
    })));
    const supplement = withRealCapabilityGaps(withDeltaEligibleCamsShape(
      withVerifiedCamsHourlyCacheV2(bundle({
        camsValidAt: laterValidAt,
        runAt: RUN_AT,
        validAt: laterValidAt,
      })),
    ));
    expect(newerIcon.current.source.icon.evidence)
      .toEqual(active.current.source.icon.evidence);
    expect(supplement.current.cams_hourly_cache.sha256)
      .toBe(active.current.cams_hourly_cache.sha256);
    const originalSetItem = storage.setItem.getMockImplementation();
    let rejectedFullCandidates = 0;
    let stagedDeltas = 0;
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === candidateKey && parsed?.kind !== "cams-delta") {
        rejectedFullCandidates += 1;
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      if (key === candidateKey && parsed?.kind === "cams-delta") stagedDeltas += 1;
      originalSetItem(key, value);
    });

    let publishCams;
    const onCamsUpdate = vi.fn();
    advanceClock = true;
    verificationNowValue = 2_000;
    const initial = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn((_location, fetchOptions) => {
        publishCams = fetchOptions.onCamsUpdate;
        return newerIcon;
      }),
      now,
      { baseUrl, storage, force: true, deferCams: true, onCamsUpdate, verificationNow },
    ));
    expect(initial.current.data_quality.run_utc).toBe(RUN_AT);
    expect(storage.getItem(activeKey)).toBe(initialActive);

    verificationNowValue = 3_000;
    publishCams(supplement);
    await vi.waitFor(() => expect(onCamsUpdate).toHaveBeenCalledOnce());

    expect(rejectedFullCandidates).toBe(1);
    expect(stagedDeltas).toBe(1);
    expect(storage.getItem(candidateKey)).toBeNull();
    const promoted = JSON.parse(storage.getItem(activeKey));
    const persistedBeforeRefresh = JSON.parse(initialActive);
    const iconDisplay = value => {
      const providerFields = new Set([
        "pollen", "pollen_data", "air_quality_data", "cams_hourly_cache",
        "source", "model_support", "cache", "data_quality",
      ]);
      const stripProviderFields = part => Object.fromEntries(
        Object.entries(part).filter(([field]) => !providerFields.has(field)),
      );
      return {
        city: value.city,
        current: stripProviderFields(value.current),
        forecast: stripProviderFields(value.forecast),
      };
    };
    expect(promoted.verifiedAt).toBe(1_000);
    expect(promoted.camsVerifiedAt).toBe(3_000);
    expect(promoted.bundle.current.source.icon)
      .toEqual(persistedBeforeRefresh.bundle.current.source.icon);
    expect(iconDisplay(promoted.bundle))
      .toEqual(iconDisplay(persistedBeforeRefresh.bundle));
    expect(promoted.bundle.current.data_quality).toMatchObject({
      run_utc: RUN_AT,
      cams_run_utc: RUN_AT,
      cams_valid_at_utc: laterValidAt,
      capability_gaps: realCapabilityGaps,
    });
    expect(promoted.bundle.current.cams_hourly_cache)
      .toMatchObject({ version: 2, sample_count: 97 });
    for (const [key, value] of Object.entries(unrelatedCaches)) {
      expect(storage.getItem(key)).toBe(value);
    }

    nowValue = Date.parse(RUN_AT) + 33 * HOUR_MS + 15 * 60 * 1000;
    const offlineFetcher = vi.fn().mockRejectedValue(new Error("offline"));
    const reopened = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      offlineFetcher,
      now,
      { baseUrl, storage: { ...storage }, force: true },
    ));
    expect(offlineFetcher).toHaveBeenCalledOnce();
    expect(reopened.current.data_quality).toMatchObject({
      run_utc: RUN_AT,
      cams_run_utc: RUN_AT,
      cams_valid_at_utc: new Date(Date.parse(RUN_AT) + 33 * HOUR_MS)
        .toISOString().replace(".000Z", "Z"),
      cams_sample_status: "last_known",
      capability_gaps: realCapabilityGaps,
    });
    expect(reopened.current.pollen_data.values.ambrosia).toBe(33.5);
    expect(reopened.current.air_quality_data.values).toMatchObject({
      "particulate_matter_2.5um": 133,
      "particulate_matter_10um": 133.1,
      ozone: 133.2,
      nitrogen_dioxide: 133.3,
    });
    for (const [key, value] of Object.entries(unrelatedCaches)) {
      expect(storage.getItem(key)).toBe(value);
    }
  });

  it("does not rebase deferred CAMS onto an active with invalid verification metadata", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/cams-delta-deferred-invalid-active-metadata";
    const storage = memoryStorage();
    const active = withDeltaEligibleCamsShape(bundle());
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(active), now,
      { baseUrl, storage, force: true, verificationNow: () => 1_000 },
    ));

    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const corrupted = JSON.parse(storage.getItem(activeKey));
    corrupted.verifiedAt = "1000";
    const corruptedSerialized = JSON.stringify(corrupted);
    storage.values.set(activeKey, corruptedSerialized);

    const newerIconRun = "2026-09-03T06:00:00Z";
    const newerIcon = withDeltaEligibleCamsShape(bundle({
      runAt: newerIconRun,
      validAt: VALID_AT,
    }));
    const supplement = withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle({
      runAt: newerIconRun,
      validAt: VALID_AT,
    })));
    const originalSetItem = storage.setItem.getMockImplementation();
    let stagedDeltas = 0;
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === candidateKey && parsed?.kind !== "cams-delta") {
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      if (key === candidateKey && parsed?.kind === "cams-delta") stagedDeltas += 1;
      originalSetItem(key, value);
    });

    let publishCams;
    const onCamsUpdate = vi.fn();
    const initial = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn((_location, fetchOptions) => {
        publishCams = fetchOptions.onCamsUpdate;
        return newerIcon;
      }),
      now,
      { baseUrl, storage, force: true, deferCams: true, onCamsUpdate,
        verificationNow: () => 2_000 },
    ));
    expect(initial.current.data_quality.run_utc).toBe(RUN_AT);

    publishCams(supplement);
    await vi.waitFor(() => expect(onCamsUpdate).toHaveBeenCalledOnce());

    expect(onCamsUpdate.mock.calls[0][0].current.data_quality.run_utc).toBe(RUN_AT);
    expect(onCamsUpdate.mock.calls[0][0].current.cams_hourly_cache).toBeNull();
    expect(storage.getItem(activeKey)).toBe(corruptedSerialized);
    expect(storage.getItem(candidateKey)).toBeNull();
    expect(stagedDeltas).toBe(0);
  });

  it("removes only the verified CAMS delta before retrying a quota-blocked promotion", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/cams-delta-promotion-quota-retry";
    const storage = memoryStorage();
    const stableOptions = { baseUrl, storage, force: true, verificationNow: () => 1 };
    const active = withDeltaEligibleCamsShape(bundle());
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(active), now, stableOptions,
    ));
    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const initialActive = storage.getItem(activeKey);
    const operations = [];
    let blockedPromotion = false;
    const originalSetItem = storage.setItem.getMockImplementation();
    const originalRemoveItem = storage.removeItem.getMockImplementation();
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === candidateKey && parsed?.kind !== "cams-delta") {
        operations.push("fail:full-candidate");
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      if (key === activeKey && storage.values.has(candidateKey) && !blockedPromotion) {
        blockedPromotion = true;
        operations.push("fail:active-with-delta");
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      originalSetItem(key, value);
      if (key === candidateKey || key === activeKey) operations.push(`set:${key}`);
    });
    storage.removeItem.mockImplementation(key => {
      expect(storage.values.has(activeKey)).toBe(true);
      const existed = storage.values.has(key);
      originalRemoveItem(key);
      expect(storage.values.has(activeKey)).toBe(true);
      if (key === candidateKey && existed) operations.push("remove:delta");
    });

    const candidate = withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle()));
    const selected = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(candidate), now, stableOptions,
    ));

    expect(selected.current.cams_hourly_cache).toMatchObject({ version: 2, sample_count: 97 });
    expect(storage.getItem(activeKey)).not.toBe(initialActive);
    expect(storage.getItem(candidateKey)).toBeNull();
    expect(operations).toEqual([
      "fail:full-candidate",
      `set:${candidateKey}`,
      "fail:active-with-delta",
      "remove:delta",
      `set:${activeKey}`,
    ]);
    expect(storage.removeItem).not.toHaveBeenCalledWith(activeKey);
  });

  it("rejects a tampered CAMS delta readback and preserves the byte-identical active", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/cams-delta-tampered-readback";
    const storage = memoryStorage();
    const stableOptions = { baseUrl, storage, force: true, verificationNow: () => 1 };
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(withDeltaEligibleCamsShape(bundle())), now, stableOptions,
    ));
    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const initialActive = storage.getItem(activeKey);
    const originalSetItem = storage.setItem.getMockImplementation();
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === candidateKey && parsed?.kind !== "cams-delta") {
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      if (key === candidateKey && parsed?.kind === "cams-delta") {
        parsed.domain.current.data_quality.cams_valid_at_utc = "2026-09-03T09:00:00Z";
        originalSetItem(key, JSON.stringify(parsed));
        return;
      }
      originalSetItem(key, value);
    });

    const candidate = withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle()));
    const selected = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(candidate), now, stableOptions,
    ));

    expect(selected.current.cams_hourly_cache).toBeNull();
    expect(storage.getItem(activeKey)).toBe(initialActive);
    expect(storage.getItem(candidateKey)).toBeNull();
    expect(storage.removeItem).not.toHaveBeenCalledWith(activeKey);
  });

  it("discards a staged CAMS delta when its exact active base changes before promotion", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/cams-delta-base-race";
    const storage = memoryStorage();
    const stableOptions = { baseUrl, storage, force: true, verificationNow: () => 1 };
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(withDeltaEligibleCamsShape(bundle())), now, stableOptions,
    ));
    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const originalSetItem = storage.setItem.getMockImplementation();
    let racedActive = null;
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === candidateKey && parsed?.kind !== "cams-delta") {
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      originalSetItem(key, value);
      if (key === candidateKey && parsed?.kind === "cams-delta") {
        const concurrent = JSON.parse(storage.values.get(activeKey));
        concurrent.camsVerifiedAt += 1;
        racedActive = JSON.stringify(concurrent);
        storage.values.set(activeKey, racedActive);
      }
    });

    const candidate = withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle()));
    const selected = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(candidate), now, stableOptions,
    ));

    expect(racedActive).not.toBeNull();
    expect(selected.current.cams_hourly_cache).toBeNull();
    expect(storage.getItem(activeKey)).toBe(racedActive);
    expect(storage.getItem(candidateKey)).toBeNull();
    expect(readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage, now })
      .current.cams_hourly_cache).toBeNull();
  });

  it("discards a staged delta when its CAMS run is revoked before recovery", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/cams-delta-revoked-while-staged";
    const storage = memoryStorage();
    const stableOptions = { baseUrl, storage, force: true, verificationNow: () => 1 };
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(withDeltaEligibleCamsShape(bundle())), now, stableOptions,
    ));
    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const originalSetItem = storage.setItem.getMockImplementation();
    const originalRemoveItem = storage.removeItem.getMockImplementation();
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === candidateKey && parsed?.kind !== "cams-delta") {
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      if (key === activeKey) throw new Error("simulated process interruption");
      originalSetItem(key, value);
    });
    storage.removeItem.mockImplementation(key => {
      if (key === candidateKey && storage.values.has(key)) {
        throw new Error("simulated process interruption");
      }
      originalRemoveItem(key);
    });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle()))),
      now,
      stableOptions,
    ));
    expect(JSON.parse(storage.getItem(candidateKey))).toMatchObject({
      kind: "cams-delta",
      cams_run_id: "20260903T000000Z",
    });

    storage.setItem.mockImplementation(originalSetItem);
    storage.removeItem.mockImplementation(originalRemoveItem);
    const replacement = withDeltaEligibleCamsShape(bundle({
      camsDisabledRunIds: ["20260903T000000Z"],
      camsPublishedAt: "2026-09-03T08:00:00Z",
      camsRevision: 2,
      camsRunAt: "2026-09-03T06:00:00Z",
      camsValidAt: VALID_AT,
    }));
    replacement.current.hourly_forecast = [];
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(replacement), now, stableOptions,
    ))).rejects.toMatchObject({ code: "ICON_BUNDLE_UNUSABLE" });

    expect(storage.getItem(candidateKey)).toBeNull();
    expect(JSON.parse(storage.getItem(activeKey))).toMatchObject({
      camsVerifiedAt: null,
      bundle: { current: { data_quality: { cams_status: "unavailable" } } },
    });
  });

  it.each([
    {
      label: "a different municipality",
      candidate: () => withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle({
        city: "Udine",
        istatCode: "030129",
      }))),
      rejects: true,
    },
    {
      label: "a different ICON object",
      candidate: () => withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle({
        runAt: "2026-09-03T06:00:00Z",
      }))),
      rejects: false,
    },
  ])("does not stage a CAMS delta from $label", async ({ candidate, rejects }) => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = `/cams-delta-ineligible-${rejects ? "municipality" : "icon"}`;
    const storage = memoryStorage();
    const stableOptions = { baseUrl, storage, force: true, verificationNow: () => 1 };
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(withDeltaEligibleCamsShape(bundle())), now, stableOptions,
    ));
    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const initialActive = storage.getItem(activeKey);
    const originalSetItem = storage.setItem.getMockImplementation();
    let stagedDeltas = 0;
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === candidateKey && parsed?.kind !== "cams-delta") {
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      if (key === candidateKey && parsed?.kind === "cams-delta") stagedDeltas += 1;
      originalSetItem(key, value);
    });

    const request = fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(candidate()), now, stableOptions,
    ));
    if (rejects) await expect(request).rejects.toMatchObject({ code: "ICON_BUNDLE_UNUSABLE" });
    else expect((await request).current.cams_hourly_cache).toBeNull();

    expect(stagedDeltas).toBe(0);
    expect(storage.getItem(activeKey)).toBe(initialActive);
    expect(storage.getItem(candidateKey)).toBeNull();
  });

  it("reopens the previous active after interruption leaves only a staged CAMS delta", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/cams-delta-crash-before-promotion";
    const storage = memoryStorage();
    const stableOptions = { baseUrl, storage, force: true, verificationNow: () => 1 };
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(withDeltaEligibleCamsShape(bundle())), now, stableOptions,
    ));
    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const initialActive = storage.getItem(activeKey);
    const originalSetItem = storage.setItem.getMockImplementation();
    const originalRemoveItem = storage.removeItem.getMockImplementation();
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === candidateKey && parsed?.kind !== "cams-delta") {
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      if (key === activeKey) throw new Error("simulated process interruption");
      originalSetItem(key, value);
    });
    storage.removeItem.mockImplementation(key => {
      if (key === candidateKey && storage.values.has(key)) {
        throw new Error("simulated process interruption");
      }
      originalRemoveItem(key);
    });

    const candidate = withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle()));
    const selected = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(candidate), now, stableOptions,
    ));
    expect(selected.current.cams_hourly_cache).toBeNull();
    expect(storage.getItem(activeKey)).toBe(initialActive);
    expect(JSON.parse(storage.getItem(candidateKey))).toMatchObject({ kind: "cams-delta" });

    storage.setItem.mockImplementation(originalSetItem);
    storage.removeItem.mockImplementation(originalRemoveItem);
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage, now });
    expect(reopened.current.cams_hourly_cache).toBeNull();
    expect(storage.getItem(activeKey)).toBe(initialActive);
    expect(storage.getItem(candidateKey)).toBeNull();
  });

  it("reopens the new active after interruption leaves its already-promoted CAMS delta", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/cams-delta-crash-after-promotion";
    const storage = memoryStorage();
    const stableOptions = { baseUrl, storage, force: true, verificationNow: () => 1 };
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(withDeltaEligibleCamsShape(bundle())), now, stableOptions,
    ));
    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const candidateKey = `${activeKey}:candidate`;
    const initialActive = storage.getItem(activeKey);
    const originalSetItem = storage.setItem.getMockImplementation();
    const originalRemoveItem = storage.removeItem.getMockImplementation();
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === candidateKey && parsed?.kind !== "cams-delta") {
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      originalSetItem(key, value);
    });
    storage.removeItem.mockImplementation(key => {
      if (key === candidateKey && storage.values.has(key)) {
        throw new Error("simulated process interruption");
      }
      originalRemoveItem(key);
    });

    const candidate = withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle()));
    const selected = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(candidate), now, stableOptions,
    ));
    expect(selected.current.cams_hourly_cache).toMatchObject({ version: 2, sample_count: 97 });
    expect(storage.getItem(activeKey)).not.toBe(initialActive);
    expect(JSON.parse(storage.getItem(candidateKey))).toMatchObject({ kind: "cams-delta" });

    storage.setItem.mockImplementation(originalSetItem);
    storage.removeItem.mockImplementation(originalRemoveItem);
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage, now });
    expect(reopened.current.cams_hourly_cache).toMatchObject({ version: 2, sample_count: 97 });
    expect(storage.getItem(candidateKey)).toBeNull();
  });

  it("does not enrich a same-run active from a different CAMS object identity", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const legacy = bundle();
    legacy.current.air_quality_data = {
      run_at: RUN_AT,
      valid_at: VALID_AT,
      values: { ozone: 110 },
    };
    legacy.current.hourly_next_12h = legacy.current.hourly_forecast.slice(0, 12);
    const candidate = withVerifiedCamsHourlyCache(bundle());
    candidate.current.source.cams.evidence.stages.latest.etag = '"different-cams-object"';
    const fetcher = vi.fn().mockResolvedValueOnce(legacy).mockResolvedValueOnce(candidate);
    const runtimeOptions = options(fetcher, now, {
      baseUrl: "/same-run-hourly-cache-other-object",
      storage: memoryStorage(),
      force: true,
    });

    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    const selected = await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    expect(selected.current.cams_hourly_cache).toBeUndefined();
    expect(selected.current.air_quality_data.values.ozone).toBe(110);
  });

  it("restores 48 hours on a same-run online refresh after a partial-hour cache projection", async () => {
    let nowValue = Date.parse("2026-09-03T10:00:00Z");
    const now = () => nowValue;
    const initial = bundle({ camsStatus: "unavailable" });
    const next = bundle({ camsStatus: "unavailable" });
    const currentRow = { ...initial.current.hourly_forecast[0], time: VALID_AT };
    initial.current.hourly_forecast = [currentRow, ...initial.current.hourly_forecast.slice(0, 47)];
    const bundleFetcher = vi.fn().mockResolvedValueOnce(initial).mockResolvedValueOnce(next);
    const runtimeOptions = options(bundleFetcher, now, {
      baseUrl: "/restore-full-window",
      storage: memoryStorage(),
    });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    nowValue = Date.parse("2026-09-03T10:15:00Z");
    const expanded = await fetchLocalWeatherV1RuntimeBundle("Pordenone", { ...runtimeOptions, force: true });
    expect(expanded.current.hourly_forecast).toHaveLength(48);
    expect(expanded.current.hourly_forecast.at(-1).time).toBe(next.current.hourly_forecast.at(-1).time);
  });

  it("does not adopt a first CAMS candidate beyond the existing 30-hour usability limit", async () => {
    const run = Date.parse(RUN_AT);
    const now = () => run + 30 * 60 * 60 * 1000 + 1;
    const validAt = new Date(run + 30 * 60 * 60 * 1000).toISOString();
    const incoming = bundle({ camsStatus: "stale", camsValidAt: validAt, hourCount: 41, validAt });
    const selected = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(incoming),
      now,
      { baseUrl: "/first-cams-past-usable", storage: memoryStorage(), force: true },
    ));

    expect(selected.current.source.cams.status).toBe("unavailable");
    expect(selected.current.data_quality).toMatchObject({
      cams_status: "unavailable",
      cams_run_utc: null,
      cams_valid_at_utc: null,
    });
    expect(selected.current.air_quality_data).toBeNull();
    expect(selected.current.data_quality.cams_diagnostic).toMatchObject({ code: "EXPIRED", stage: "adapt" });
  });

  it.each([408, 429, 503])("keeps verified ICON for transient HTTP %i", async httpStatus => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const bundleFetcher = vi.fn().mockResolvedValueOnce(bundle({ camsStatus: "unavailable" }))
      .mockRejectedValueOnce(Object.assign(new Error("temporary"), { code: "HTTP_ERROR", httpStatus }));
    const runtimeOptions = options(bundleFetcher, now, { baseUrl: `/transient-${httpStatus}` });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    expect((await fetchLocalWeatherV1RuntimeBundle("Pordenone", { ...runtimeOptions, force: true }))
      .current.cache.runtime_fallback).toBe(true);
  });

  it.each(["RUN_DISABLED", "INTEGRITY_MISMATCH", "CATALOG_MISMATCH", "RUN_MISMATCH", "INVALID_JSON", "INVALID_DOCUMENT", "FRESHNESS_MISMATCH", 401, 403, 404])(
    "keeps the verified active bundle after candidate error %s, including reopening", async code => {
      const now = () => Date.parse("2026-09-03T10:15:00Z");
      const storage = memoryStorage({ unrelated: "keep" });
      const error = Object.assign(new Error("hard failure"), typeof code === "number" ? { code: "HTTP_ERROR", httpStatus: code } : { code });
      const bundleFetcher = vi.fn().mockResolvedValueOnce(bundle({ camsStatus: "unavailable" }))
        .mockRejectedValueOnce(error).mockRejectedValue(new Error("offline"));
      const baseUrl = `/hard-no-resurrection-${code}`;
      const runtimeOptions = options(bundleFetcher, now, { baseUrl, storage, verifyWindowMs: LOCAL_WEATHER_V1_VERIFY_WINDOW_MS });
      await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
      await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", {
        ...runtimeOptions,
        force: true,
      })).rejects.toBe(error);
      const reopened = await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
      expect(reopened.current).toMatchObject({
        temperature: 20,
        data_quality: { cams_status: "unavailable", cams_run_utc: null },
        pollen_data: { status: "unavailable" },
      });
      expect(readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage: { ...storage }, now })).not.toBeNull();
      expect(storage.values.get("unrelated")).toBe("keep");
    },
  );

  it("purges revoked ICON A before downloading B, so a transport failure cannot resurrect A", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const baseUrl = "/icon-revocation-before-transport";
    const initial = bundle({ camsStatus: "unavailable" });
    const other = municipality(88);
    const bundleFetcher = vi.fn().mockResolvedValueOnce(initial).mockImplementationOnce(async (_location, request) => {
      request.onIconLatest({ revision: 2, latest: { source_run_id: "20260903T060000Z" }, disabled_run_ids: ["20260903T000000Z"] });
      throw Object.assign(new Error("offline after pointer"), { code: "TRANSPORT_FAILURE" });
    });
    const runtimeOptions = options(bundleFetcher, now, { baseUrl, storage });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    await fetchLocalWeatherV1RuntimeBundle(other, options(vi.fn().mockResolvedValue(bundle({
      city: other.city, istatCode: other.municipality.istatCode, camsStatus: "unavailable",
    })), now, { baseUrl, storage }));
    const stagedKeys = persistedBundleKeys(storage);
    for (const key of stagedKeys) storage.setItem(`${key}:candidate`, storage.getItem(key));
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", { ...runtimeOptions, force: true })).rejects.toThrow("offline after pointer");
    expect(persistedBundleKeys(storage)).toHaveLength(0);
    for (const key of stagedKeys) expect(storage.getItem(`${key}:candidate`)).toBeNull();
    expect(readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage: { ...storage }, now })).toBeNull();
    expect(readLocalWeatherV1PersistedBundle(other, { baseUrl, storage, now })).toBeNull();
  });

  it("elimina il marker del candidato fallito quando quel run viene revocato", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const baseUrl = "/revoked-uncommitted-icon-candidate";
    const storage = memoryStorage({ "pilot-uv-cache": "preserve-uv" });
    const active = withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle()));
    const candidateRun = "2026-09-03T06:00:00Z";
    const candidateRunId = "20260903T060000Z";
    const candidate = withDeltaEligibleCamsShape(withVerifiedCamsHourlyCacheV2(bundle({
      runAt: candidateRun,
      temperature: 24,
    })));
    const fetcher = vi.fn().mockResolvedValue(active);
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      fetcher, now, { baseUrl, storage, force: true },
    ));
    const activeKey = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const originalSetItem = storage.setItem.getMockImplementation();
    storage.setItem.mockImplementation((key, value) => {
      const parsed = (() => { try { return JSON.parse(value); } catch { return null; } })();
      if (key === `${activeKey}:candidate` && parsed?.kind !== "cams-delta") {
        const error = new Error("Quota exceeded");
        error.name = "QuotaExceededError";
        throw error;
      }
      originalSetItem(key, value);
    });

    fetcher.mockResolvedValue(candidate);
    const retained = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      fetcher, now, { baseUrl, storage, force: true },
    ));
    expect(retained.current.cache.runtime_fallback_source).toBe("candidate_not_committed");
    expect(retained.current.data_quality.run_utc).toBe(RUN_AT);

    fetcher.mockImplementation((_location, request) => {
      request.onIconLatest({
        revision: 2,
        latest: { source_run_id: "20260903T120000Z" },
        disabled_run_ids: [candidateRunId],
      });
      throw new Error("offline after revocation");
    });
    const afterRevocation = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      fetcher, now, { baseUrl, storage, force: true },
    ));

    expect(afterRevocation.current.data_quality).toMatchObject({
      run_utc: RUN_AT,
      cams_run_utc: RUN_AT,
    });
    expect(afterRevocation.current.cache.runtime_fallback).toBe(true);
    expect(afterRevocation.current.cache.runtime_fallback_source)
      .not.toBe("candidate_not_committed");
    expect(afterRevocation.current.cache).not.toHaveProperty("runtime_fallback_code");
    expect(afterRevocation.current.data_quality.flags)
      .not.toContain("runtime_candidate_not_committed");
    expect(storage.getItem("pilot-uv-cache")).toBe("preserve-uv");
    expect(JSON.parse(storage.getItem(activeKey)).bundle.current.data_quality.run_utc)
      .toBe(RUN_AT);
  });

  it("consults the validated raw pointer before restoring a saved bundle on reopening", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const baseUrl = "/cold-icon-pointer-revocation";
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(
      vi.fn().mockResolvedValue(bundle({ camsStatus: "unavailable" })), now, { baseUrl, storage },
    ));
    const pointer = vi.spyOn(weatherV1Client, "readCachedIconLatest").mockReturnValue({
      revision: 2, latest: { source_run_id: "20260903T060000Z" }, disabled_run_ids: ["20260903T000000Z"],
    });
    try {
      expect(readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage: { ...storage }, now })).toBeNull();
      expect(pointer).toHaveBeenCalled();
      expect(persistedBundleKeys(storage)).toHaveLength(0);
    } finally { pointer.mockRestore(); }
  });

  it("does not accept an incoming window which fell from twelve to eleven while fetching", async () => {
    let nowValue = Date.parse("2026-09-03T10:15:00Z");
    const now = () => nowValue;
    const value = bundle({ hourCount: 12, camsStatus: "unavailable" });
    const fetcher = vi.fn(async () => {
      await Promise.resolve();
      nowValue = Date.parse("2026-09-03T11:15:00Z");
      return value;
    });
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", options(fetcher, now,
      { baseUrl: "/window-expired-during-fetch" }))).rejects.toMatchObject({ code: "ICON_BUNDLE_UNUSABLE" });
  });

  it("updates only existing freshness metadata when the saved ICON crosses fresh_until", async () => {
    let nowValue = Date.parse("2026-09-03T10:15:00Z");
    const now = () => nowValue;
    const value = bundle({ camsStatus: "unavailable" });
    value.current.data_quality.status = "fresh";
    value.current.data_quality.fresh_until_utc = "2026-09-03T10:30:00Z";
    value.forecast.data_quality = { ...value.current.data_quality };
    const storage = memoryStorage();
    const baseUrl = "/fresh-until-metadata";
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(value), now, { baseUrl, storage }));
    nowValue = Date.parse("2026-09-03T10:31:00Z");
    const retained = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage, now });
    expect(retained.current.data_quality.status).toBe("stale");
    expect(retained.current.cache.status).toBe("stale");
    expect(retained.forecast.cache.status).toBe("stale");
    expect(retained.current.hourly_forecast).toHaveLength(48);
    expect(retained.current.source.label).toBe(value.current.source.label);
  });

  it("rejects an abort without purging good data because navigation was cancelled", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const abort = Object.assign(new Error("aborted"), { code: "TRANSPORT_FAILURE", aborted: true });
    const bundleFetcher = vi.fn().mockResolvedValueOnce(bundle({ camsStatus: "unavailable" }))
      .mockRejectedValueOnce(abort).mockRejectedValueOnce(new Error("offline"));
    const runtimeOptions = options(bundleFetcher, now, { baseUrl: "/abort-no-fallback" });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions)).rejects.toBe(abort);
    expect((await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions)).current.cache.runtime_fallback).toBe(true);
  });

  it("keeps the active municipality, other municipalities and endpoints after a candidate error", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const storage = memoryStorage();
    const baseUrl = "/scoped-hard-error";
    const other = municipality(88);
    const fetcher = vi.fn().mockResolvedValueOnce(bundle({ camsStatus: "unavailable" }))
      .mockRejectedValueOnce(Object.assign(new Error("invalid hash"), { code: "INTEGRITY_MISMATCH" }));
    const runtimeOptions = options(fetcher, now, { baseUrl, storage });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    await fetchLocalWeatherV1RuntimeBundle(other, options(vi.fn().mockResolvedValue(bundle({
      city: other.city, istatCode: other.municipality.istatCode, camsStatus: "unavailable",
    })), now, { baseUrl, storage }));
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(bundle({ camsStatus: "unavailable" })),
      now, { baseUrl: "/unrelated-endpoint", storage }));
    await expect(fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions))
      .rejects.toMatchObject({ code: "INTEGRITY_MISMATCH" });
    expect(readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage, now })).not.toBeNull();
    expect(readLocalWeatherV1PersistedBundle(other, { baseUrl, storage, now })).not.toBeNull();
    expect(readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl: "/unrelated-endpoint", storage, now })).not.toBeNull();
  });

  it("does not share retained data between municipalities or fetcher identities", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const success = vi.fn().mockResolvedValue(bundle());
    const failure = vi.fn().mockRejectedValue(new Error("offline"));
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(success, now));

    await expect(
      fetchLocalWeatherV1RuntimeBundle("Udine", options(failure, now)),
    ).rejects.toThrow("offline");
    await expect(
      fetchLocalWeatherV1RuntimeBundle("Pordenone", options(failure, now)),
    ).rejects.toThrow("offline");
  });

  it("deduplica il defer CAMS, distribuisce il supplemento e conserva quello arricchito", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const initial = bundle({ camsStatus: "pending" });
    const enriched = bundle({ temperature: 20, camsStatus: "fresh" });
    let publishCams;
    const bundleFetcher = vi.fn()
      .mockImplementationOnce((_location, fetchOptions) => {
        publishCams = fetchOptions.onCamsUpdate;
        return initial;
      })
      .mockRejectedValueOnce(new Error("offline"));
    const leftUpdate = vi.fn(() => Promise.reject(new Error("observer stopped")));
    const rightUpdate = vi.fn();
    const runtimeOptions = options(bundleFetcher, now, {
      deferCams: true,
      onCamsUpdate: leftUpdate,
      storage: memoryStorage(),
    });

    const left = fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    const right = fetchLocalWeatherV1RuntimeBundle("Pordenone", {
      ...runtimeOptions,
      onCamsUpdate: rightUpdate,
    });
    await expect(Promise.all([left, right])).resolves.toEqual([initial, initial]);
    expect(bundleFetcher).toHaveBeenCalledOnce();
    expect(bundleFetcher).toHaveBeenCalledWith("Pordenone", expect.objectContaining({
      deferCams: true,
      force: false,
      onCamsUpdate: expect.any(Function),
    }));

    publishCams(enriched);
    await vi.waitFor(() => expect(rightUpdate).toHaveBeenCalledWith(
      enriched,
      { lifecycle: "final" },
    ));
    expect(leftUpdate).toHaveBeenCalledWith(enriched, { lifecycle: "final" });

    const retained = await fetchLocalWeatherV1RuntimeBundle("Pordenone", runtimeOptions);
    expect(bundleFetcher).toHaveBeenCalledTimes(2);
    expect(retained.current).toMatchObject({
      temperature: 20,
      data_quality: { cams_status: "fresh" },
      cache: {
        runtime_fallback: true,
        runtime_fallback_source: "verified_memory_bundle",
      },
    });
  });

  it("non condivide in-flight tra modalita CAMS defer e obbligatoria", async () => {
    const now = () => Date.parse("2026-09-03T10:15:00Z");
    const initial = bundle({ camsStatus: "pending" });
    const enriched = bundle({ temperature: 22, camsStatus: "fresh" });
    let publishCams;
    const bundleFetcher = vi.fn((_location, fetchOptions) => {
      if (!fetchOptions.deferCams) return enriched;
      publishCams = fetchOptions.onCamsUpdate;
      return initial;
    });

    const [deferred, required] = await Promise.all([
      fetchLocalWeatherV1RuntimeBundle("Pordenone", options(bundleFetcher, now, {
        deferCams: true,
      })),
      fetchLocalWeatherV1RuntimeBundle("Pordenone", options(bundleFetcher, now)),
    ]);

    expect(deferred.current.data_quality.cams_status).toBe("pending");
    expect(required.current.data_quality.cams_status).toBe("fresh");
    expect(bundleFetcher).toHaveBeenCalledTimes(2);
    publishCams(enriched);
  });
});


describe("persisted CAMS 36h continuity", () => {
  function continuous(value) {
    const doc = { schema_version: 1, kind: "meteofriul.weather.cams_continuity",
      policy_id: "cams_continuity_36h_v1", source_run_id: "20260903T000000Z", catalog: CATALOG,
      release_sha256: "a".repeat(64), release_json_bytes: 1024,
      issued_at: "2026-09-03T02:00:00Z", run_at: RUN_AT,
      fresh_until: "2026-09-04T00:00:00Z", usable_until: "2026-09-04T12:00:00Z",
      current_sample_max_lag_minutes: 60 };
    for (const part of [value.current,value.forecast]) {
      const stages = part.source.cams.evidence.stages;
      stages.latest.family_release = { source_run_id: doc.source_run_id,
        release_path: `runs/${doc.source_run_id}/release.json`, release_sha256: doc.release_sha256,
        release_json_bytes: doc.release_json_bytes };
      stages.latest.family_release_published_at = doc.issued_at;
      for (const stage of Object.values(stages)) stage.freshness = {
        freshUntil: doc.fresh_until, usableUntil: doc.usable_until, continuity: doc };
    }
    return value;
  }
  it.each([24, 24+1/HOUR_MS, 30+1/HOUR_MS, 33, 36, 36+1/HOUR_MS])(
    "reopens offline at %s hours, with native hourly selection and strict cutoff", async hours => {
      let time = Date.parse(VALID_AT); const now = () => time;
      const value = continuous(withVerifiedCamsHourlyCacheV2(bundle({ hourCount: 62 })));
      const storage = memoryStorage(); const baseUrl = `/continuity-${hours}`;
      await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(value), now, { storage, baseUrl }));
      time = Date.parse(RUN_AT) + hours * HOUR_MS;
      const reopened = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage: { ...storage }, now });
      expect(reopened).not.toBeNull();
      if (hours > 36) {
        expect(reopened.current.source.cams.status).toBe("unavailable");
        expect(reopened.current.air_quality_data).toBeNull();
        expect(reopened.current.pollen_data.values).toEqual({});
      } else {
        expect(reopened.current.data_quality).toMatchObject({ cams_status: hours <= 24 ? "fresh" : "stale", cams_sample_status: "current", cams_run_utc: RUN_AT });
        expect(Date.parse(reopened.current.air_quality_data.valid_at)).toBe(Date.parse(RUN_AT) + Math.floor(hours)*HOUR_MS);
        expect(reopened.current.air_quality_data.values.ozone).toBeCloseTo(100 + Math.floor(hours) + CAMS_AIR_FIELDS.indexOf("ozone")/10);
      }
    });
  it("does not keep a fresh label across 24h or invent the next sample when the hourly cache is missing", async () => {
    const time = Date.parse(RUN_AT) + 24*HOUR_MS + 1;
    const value = continuous(bundle({ runAt: "2026-09-04T00:00:00Z", validAt: "2026-09-04T00:00:00Z", camsValidAt: "2026-09-04T00:00:00Z" }));
    const storage = memoryStorage(); const baseUrl = "/continuity-without-series";
    const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(value), () => time, { baseUrl, storage }));
    expect(result.current.data_quality).toMatchObject({ cams_status: "stale", cams_sample_status: "current" });
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage: { ...storage }, now: () => time + HOUR_MS });
    expect(reopened.current.source.cams.status).toBe("unavailable");
  });
  it("cannot extend validity from a cache timestamp alone", async () => {
    const value = withVerifiedCamsHourlyCacheV2(bundle({ hourCount: 62 }));
    const time = Date.parse(RUN_AT) + 33*HOUR_MS;
    const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(value), () => time));
    expect(result.current.source.cams.status).toBe("unavailable");
  });
  it("rejects broken binding in the continuity evidence", async () => {
    const value = continuous(withVerifiedCamsHourlyCacheV2(bundle({ hourCount: 62 })));
    value.current.source.cams.evidence.stages.latest.family_release.release_sha256 = "b".repeat(64);
    const result = await fetchLocalWeatherV1RuntimeBundle("Pordenone", options(vi.fn().mockResolvedValue(value), () => Date.parse(VALID_AT)));
    expect(result.current.data_quality.cams_diagnostic.code).toBe("CONTINUITY_MISMATCH");
  });

  function migrationBundles() {
    return {
      legacy: withVerifiedCamsHourlyCacheV2(bundle({ hourCount: 62 }), 97, 30),
      candidate: continuous(withVerifiedCamsHourlyCacheV2(bundle({ hourCount: 62 }), 97, 36)),
    };
  }
  it.each([true, false])("continuity migration preserves the grant and series with legacy cache=%s", async hasSeries => {
    let time = Date.parse(VALID_AT);
    const now = () => time;
    const { legacy, candidate } = migrationBundles();
    if (!hasSeries) delete legacy.current.cams_hourly_cache;
    const storage = memoryStorage();
    const baseUrl = `/continuity-migration-${hasSeries}`;
    const fetcher = vi.fn().mockResolvedValueOnce(legacy).mockResolvedValueOnce(candidate);
    const opts = options(fetcher, now, { storage, baseUrl, force: true });
    const before = await fetchLocalWeatherV1RuntimeBundle("Pordenone", opts);
    const upgraded = await fetchLocalWeatherV1RuntimeBundle("Pordenone", opts);
    expect(fetcher).toHaveBeenCalledTimes(2);
    for (const value of [upgraded.current, upgraded.forecast]) {
      expect(value.source.cams.evidence.stages.latest.freshness.continuity.policy_id).toBe("cams_continuity_36h_v1");
      expect(value.data_quality.cams_run_utc).toBe(RUN_AT);
      expect(value.data_quality.cams_valid_at_utc).toBe(VALID_AT);
    }
    expect(Date.parse(upgraded.current.cams_hourly_cache.usable_until_utc)).toBe(Date.parse(RUN_AT) + 36*HOUR_MS);
    expect(upgraded.current.temperature).toBe(before.current.temperature);
    expect(upgraded.current.hourly_forecast).toEqual(before.current.hourly_forecast);
    if (hasSeries) {
      expect(upgraded.current.air_quality_data.values).toEqual(before.current.air_quality_data.values);
      expect(upgraded.current.pollen_data.values).toEqual(before.current.pollen_data.values);
    }
    for (const hours of [24, 33, 36, 36+1/HOUR_MS]) {
      time = Date.parse(RUN_AT) + hours*HOUR_MS;
      const reopened = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage: { ...storage }, now });
      expect(reopened).not.toBeNull();
      if (hours > 36) {
        expect(reopened.current.source.cams.status).toBe("unavailable");
        expect(reopened.current.air_quality_data).toBeNull();
      } else {
        expect(reopened.current.data_quality).toMatchObject({ cams_sample_status: "current", cams_status: hours <= 24 ? "fresh" : "stale" });
        expect(Date.parse(reopened.current.air_quality_data.valid_at)).toBe(Date.parse(RUN_AT) + hours*HOUR_MS);
      }
    }
  });
  it("continuity migration does not lose the grant to a subsequent legacy response", async () => {
    const { legacy, candidate } = migrationBundles();
    const now = () => Date.parse(VALID_AT);
    const storage = memoryStorage(); const baseUrl = "/continuity-migration-no-downgrade";
    const opts = options(vi.fn().mockResolvedValueOnce(candidate).mockResolvedValueOnce(legacy), now, { storage, baseUrl, force: true });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", opts);
    const retained = await fetchLocalWeatherV1RuntimeBundle("Pordenone", opts);
    expect(retained.current.source.cams.evidence.stages.latest.freshness.continuity).toBeDefined();
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage: { ...storage }, now: () => Date.parse(RUN_AT)+33*HOUR_MS });
    expect(reopened.current.data_quality.cams_sample_status).toBe("current");
  });
  it.each(["identity", "invalid-proof", "short-series"])("continuity migration rejects %s", async reason => {
    const { legacy, candidate } = migrationBundles();
    if (reason === "identity") {
      candidate.current.source.cams.evidence.stages.latest.etag = '"another-family"';
    } else if (reason === "invalid-proof") {
      candidate.current.source.cams.evidence.stages.latest.family_release.release_sha256 = "b".repeat(64);
    } else {
      withVerifiedCamsHourlyCacheV2(candidate, 97, 30);
    }
    const now = () => Date.parse(VALID_AT);
    const storage = memoryStorage(); const baseUrl = `/continuity-migration-reject-${reason}`;
    const opts = options(vi.fn().mockResolvedValueOnce(legacy).mockResolvedValueOnce(candidate), now, { storage, baseUrl, force: true });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", opts);
    const retained = await fetchLocalWeatherV1RuntimeBundle("Pordenone", opts);
    expect(retained.current.source.cams.evidence.stages.latest.freshness?.continuity).toBeUndefined();
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage: { ...storage }, now: () => Date.parse(RUN_AT)+33*HOUR_MS });
    expect(reopened.current.data_quality.cams_sample_status).toBe("last_known");
  });
  it("continuity migration leaves the legacy generation intact when staging fails", async () => {
    const { legacy, candidate } = migrationBundles();
    const now = () => Date.parse(VALID_AT);
    const storage = memoryStorage(); const baseUrl = "/continuity-migration-write-failure";
    const opts = options(vi.fn().mockResolvedValueOnce(legacy).mockResolvedValueOnce(candidate), now, { storage, baseUrl, force: true });
    await fetchLocalWeatherV1RuntimeBundle("Pordenone", opts);
    const key = getLocalWeatherV1BundleCacheKey("Pordenone", { baseUrl });
    const write = storage.setItem.getMockImplementation();
    storage.setItem.mockImplementation((target, value) => {
      if (target.startsWith(`${key}:candidate`)) throw new Error("staging interrupted");
      return write(target, value);
    });
    const retained = await fetchLocalWeatherV1RuntimeBundle("Pordenone", opts);
    expect(retained.current.source.cams.evidence.stages.latest.freshness?.continuity).toBeUndefined();
    const reopened = readLocalWeatherV1PersistedBundle("Pordenone", { baseUrl, storage: { ...storage }, now });
    expect(reopened.current.source.cams.evidence.stages.latest.freshness?.continuity).toBeUndefined();
    expect(Date.parse(reopened.current.cams_hourly_cache.usable_until_utc)).toBe(Date.parse(RUN_AT)+30*HOUR_MS);
  });
});
