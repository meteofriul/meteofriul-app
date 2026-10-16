import { describe, expect, it, vi } from "vitest";
import { LOCAL_WEATHER_V1_CATALOG } from "./localWeatherV1Adapter";
import {
  fetchLocalWeatherV1RuntimeBundle,
  getLocalWeatherV1BundleCacheKey,
  readLocalWeatherV1PersistedBundle,
} from "./localWeatherV1Runtime";

const RUN_A = "2026-09-09T00:00:00Z";
const RUN_B = "2026-09-10T00:00:00Z";
const VALID_AT = "2026-09-10T01:00:00Z";
const now = () => Date.parse("2026-09-10T01:15:00Z");
const runId = value => value.replaceAll("-", "").replaceAll(":", "");
let sequence = 0;

function bundle({ run = RUN_B, revision = 2, disabledRunIds = [], hourCount = 48 } = {}) {
  const source = {
    active: "icon2i_local_pilot", primary_source: "icon2i_local_pilot",
    municipality_istat: "093033", catalog: LOCAL_WEATHER_V1_CATALOG,
    icon: { status: "available", evidence: {
      path: `runs/${runId(RUN_B)}/municipalities/093033.json`, etag: '"icon"',
    } },
    cams: { status: "available", evidence: {
      family: { revision, published_at: `2026-09-10T00:0${revision}:00Z`,
        active_run_id: runId(run), disabled_run_ids: disabledRunIds },
      stages: {
        latest: { path: `families/cams/runs/${runId(run)}/release.json#pollen`, etag: '"cams"' },
        manifest: { path: `runs/${runId(run)}/manifest.json` },
        municipality: { path: `runs/${runId(run)}/municipalities/093033.json` },
      },
    } },
  };
  const dataQuality = {
    mode: "local_contract_v1", catalog_version: LOCAL_WEATHER_V1_CATALOG.version,
    catalog_sha256: LOCAL_WEATHER_V1_CATALOG.sha256, municipality_istat: "093033",
    run_utc: RUN_B, valid_at_utc: VALID_AT, flags: [],
    cams_status: "available", cams_run_utc: run, cams_valid_at_utc: VALID_AT,
  };
  return {
    city: "Pordenone",
    current: {
      city: "Pordenone", primary_source: "icon2i_local_pilot", source,
      temperature: 20, air_quality_data: null,
      pollen_data: { status: "experimental_model_snapshot" },
      cache: { status: "fresh" }, data_quality: dataQuality,
      hourly_forecast: Array.from({ length: hourCount }, (_, index) => ({
        time: new Date(Date.parse(VALID_AT) + (index + 1) * 3_600_000).toISOString(),
        temperature: 20, condition: "Coperto", wind_speed: 7, wind_direction: 90, wind_gusts: 12,
        cloud_cover: 80, precipitation: 0, rain: 0, humidity: 60, pressure: 1015, feels_like: 19,
        quality_flags: [], snowfall_water_equivalent_mm: 0,
        data_quality: { native_weather_code: 3, native_condition_label: "Coperto", native_condition_status: "valid" },
      })),
    },
    forecast: { city: "Pordenone", primary_source: "icon2i_local_pilot", source,
      daily_extrema_version: 2, daily: [], cache: { status: "fresh" }, data_quality: dataQuality },
  };
}

function harness() {
  const values = new Map();
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  let completeOld;
  let oldOptions;
  let started;
  const ready = new Promise(resolve => { started = resolve; });
  const bundleFetcher = vi.fn().mockImplementationOnce((_location, options) => {
    oldOptions = options;
    started();
    return new Promise((resolve, reject) => { completeOld = { resolve, reject }; });
  }).mockResolvedValueOnce(bundle()).mockRejectedValue(new Error("offline"));
  const options = {
    baseUrl: `/generation-race-${++sequence}`, storage, now, verificationNow: now,
    verifyWindowMs: 0, bundleFetcher, fetchImpl: vi.fn(),
  };
  return {
    options, ready,
    old: () => completeOld,
    oldOptions: () => oldOptions,
    fetch: extra => fetchLocalWeatherV1RuntimeBundle("Pordenone", { ...options, ...extra }),
    saved: () => JSON.parse(storage.getItem(getLocalWeatherV1BundleCacheKey("Pordenone", options))),
  };
}

describe("whole-bundle rejection is scoped to its cache generation", () => {
  it.each(["INTEGRITY_MISMATCH", "INVALID_DOCUMENT", "RUN_DISABLED"])(
    "rejects late %s without deleting the independently verified newer bundle", async code => {
      const h = harness();
      const oldRequest = h.fetch({ force: true });
      await h.ready;
      await h.fetch();
      const failure = Object.assign(new Error("old request rejected"), { code });
      h.old().reject(failure);
      await expect(oldRequest).rejects.toBe(failure);
      expect(h.saved().bundle.current.data_quality.cams_run_utc).toBe(RUN_B);
      // A later network failure can still use B; A itself never falls back.
      const retained = await h.fetch();
      expect(retained.current.data_quality.cams_run_utc).toBe(RUN_B);
      expect(retained.current.cache.runtime_fallback).toBe(true);
    },
  );

  it("still applies an authoritative ICON revocation observed by the overlapping request", async () => {
    const h = harness();
    const oldRequest = h.fetch({ force: true });
    await h.ready;
    await h.fetch();
    h.oldOptions().onIconLatest({ disabled_run_ids: [runId(RUN_B)] });
    const failure = Object.assign(new Error("replacement unavailable"), { code: "TRANSPORT_FAILURE" });
    h.old().reject(failure);
    await expect(oldRequest).rejects.toBe(failure);
    expect(h.saved()).toBeNull();
    expect(readLocalWeatherV1PersistedBundle("Pordenone", h.options)).toBeNull();
    await expect(h.fetch()).rejects.toThrow("offline");
  });

  it("still applies a newer authoritative CAMS rollback even when its replacement bundle is unusable", async () => {
    const h = harness();
    const oldRequest = h.fetch({ force: true });
    await h.ready;
    await h.fetch();
    h.old().resolve(bundle({ run: RUN_A, revision: 3, disabledRunIds: [runId(RUN_B)], hourCount: 0 }));
    await expect(oldRequest).rejects.toMatchObject({ code: "ICON_BUNDLE_UNUSABLE" });
    const saved = h.saved().bundle;
    expect(saved.current.source.icon.status).toBe("available");
    expect(saved.current.source.cams.status).toBe("unavailable");
    expect(saved.current.data_quality.cams_run_utc).toBeNull();
    expect(saved.current.data_quality.cams_diagnostic.code).toBe("RUN_DISABLED");
    const persisted = readLocalWeatherV1PersistedBundle("Pordenone", h.options);
    expect(persisted.current.source.icon.status).toBe("available");
    expect(persisted.current.source.cams.status).toBe("unavailable");
    const retained = await h.fetch();
    expect(retained.current.source.icon.status).toBe("available");
    expect(retained.current.source.cams.status).toBe("unavailable");
    expect(retained.current.cache.runtime_fallback).toBe(true);
  });
});
