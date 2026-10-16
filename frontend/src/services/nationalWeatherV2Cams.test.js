import { afterEach, describe, expect, it, vi } from "vitest";
import { LOCAL_WEATHER_V1_CATALOG } from "./localWeatherV1Adapter";
import {
  clearNationalWeatherV2CamsRuntime,
  enrichNationalWeatherV2WithCams,
  readNationalWeatherV2CamsBundle,
} from "./nationalWeatherV2Cams";

const BASE = "https://meteofriul-weather-49007668366.europe-west1.run.app";
const NOW = Date.parse("2026-09-21T15:30:00Z");
const OBSERVED_GRASS = Number("1.3538589477539062");

function bundle(code = "093033") {
  const source = { active: "icon2i_local_pilot", primary_source: "icon2i_local_pilot",
    municipality_istat: code, run_id: "20260921T000000Z", contract: "weather/v2/icon2i" };
  const quality = { mode: "national_contract_v2", catalog_sha256: "national-catalog-hash",
    municipality_istat: code, valid_at_utc: "2026-09-21T15:00:00Z", run_utc: "2026-09-21T00:00:00Z",
    cams_status: "unavailable", flags: ["experimental_national_v2"], capability_gaps: ["visibility", "cams_pollen"] };
  return { city: code === "093033" ? "Pordenone" : "Roma", current: {
    temperature: 22, source, primary_source: "icon2i_local_pilot", data_quality: quality,
    hourly_forecast: [{ time: "2026-09-21T16:00:00Z", temperature: 24 }],
    model_support: { icon2i: true, cams: false },
    pollen: null, pollen_data: { status: "unavailable" }, air_quality_data: null,
    uv_data: { status: "fresh", value: 3.2 },
  }, forecast: { source, data_quality: { ...quality }, daily: { time: ["2026-09-21"] },
    model_support: { icon2i: true, cams: false } } };
}

function supplement() {
  // Same shape and observed concentrations as the healthy cloud Pordenone
  // payload at 15Z on 21 September; transport/hash verification is tested v1.
  return { available: true, status: "fresh", municipality_istat: "093033",
    catalog: LOCAL_WEATHER_V1_CATALOG,
    source: { status: "available", provider: "cams_europe_pollen", run_utc: "2026-09-21T00:00:00Z",
      evidence: { family: { revision: 13, active_run_id: "20260921T000000Z", disabled_run_ids: [] } } },
    fresh_until_utc: "2026-09-22T00:00:00Z", usable_until_utc: "2026-09-22T06:00:00Z",
    pollen: "Previsione pollini CAMS · sperimentale",
    pollen_data: { status: "experimental_model_snapshot", sample_status: "current",
      run_utc: "2026-09-21T00:00:00Z", valid_at_utc: "2026-09-21T15:00:00Z",
      values: { graminacee: OBSERVED_GRASS, artemisia: 12.647167205810547, ambrosia: 1.3555908203125,
        ontano: 0, betulla: 0, olivo: 0 } },
    air_quality_data: { sample_status: "current", valid_at: "2026-09-21T15:00:00Z", values: {
      "particulate_matter_2.5um": 5.357701726715902, "particulate_matter_10um": 8.425292685743102,
      nitrogen_dioxide: 3.272950355182047, ozone: 85.30396300443499,
    } }, cams_hourly_cache: { test: "verified-cache" }, diagnostic: null };
}

function options(extra = {}) {
  return { baseUrl: BASE, now: () => NOW, verificationNow: () => NOW, ...extra };
}

afterEach(() => {
  clearNationalWeatherV2CamsRuntime();
  vi.useRealTimers();
});

describe("national ICON with the separate FVG CAMS channel", () => {
  it("joins the observed fresh Pordenone sample without changing national weather, UV, catalog or source", async () => {
    const national = bundle();
    const original = structuredClone(national);
    const camsFetcher = vi.fn().mockResolvedValue(supplement());
    const result = await enrichNationalWeatherV2WithCams(national, options({ camsFetcher }));
    expect(result.current).toMatchObject({ temperature: 22, uv_data: original.current.uv_data,
      source: { contract: "weather/v2/icon2i", cams: { status: "available" } },
      data_quality: { mode: "national_contract_v2", catalog_sha256: "national-catalog-hash",
        cams_status: "fresh", cams_catalog_sha256: LOCAL_WEATHER_V1_CATALOG.sha256 },
      pollen_data: { values: { graminacee: OBSERVED_GRASS } },
      air_quality_data: { values: { "particulate_matter_2.5um": 5.357701726715902 } },
    });
    expect(result.forecast.daily).toEqual(original.forecast.daily);
    expect(result.current.hourly_forecast).toEqual(original.current.hourly_forecast);
    expect(national).toEqual(original);
    expect(camsFetcher).toHaveBeenCalledWith({ city: "Pordenone", municipality: { istatCode: "093033", name: "Pordenone" } },
      expect.objectContaining({ baseUrl: BASE, onCamsFamilyLatest: expect.any(Function) }));
  });

  it("returns ICON immediately, deduplicates CAMS and updates every subscribed caller asynchronously", async () => {
    vi.useFakeTimers();
    let complete;
    const camsFetcher = vi.fn(() => new Promise(resolve => { complete = resolve; }));
    const first = vi.fn();
    const second = vi.fn();
    const pending = await enrichNationalWeatherV2WithCams(bundle(), options({ camsFetcher, deferCams: true, onCamsUpdate: first }));
    await enrichNationalWeatherV2WithCams(bundle(), options({ camsFetcher, deferCams: true, onCamsUpdate: second }));
    expect(pending.current.temperature).toBe(22);
    expect(pending.current.data_quality.cams_status).toBe("pending");
    expect(first).not.toHaveBeenCalled();
    expect(camsFetcher).toHaveBeenCalledTimes(1);
    complete(supplement());
    await vi.runAllTimersAsync();
    expect(first).toHaveBeenCalledTimes(1);
    expect(second).toHaveBeenCalledTimes(1);
    expect(first.mock.calls[0][0].current.air_quality_data.values.ozone).toBe(85.30396300443499);
    expect(readNationalWeatherV2CamsBundle(bundle(), options()).current.data_quality.cams_status).toBe("fresh");
    await enrichNationalWeatherV2WithCams(bundle(), options({ camsFetcher }));
    expect(camsFetcher).toHaveBeenCalledTimes(1);
  });

  it("fails only CAMS on transport error and allows resume retry without falling back to official weather", async () => {
    vi.useFakeTimers();
    const onCamsUpdate = vi.fn();
    const onCamsFailure = vi.fn();
    const camsFetcher = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue(supplement());
    const initial = await enrichNationalWeatherV2WithCams(bundle(), options({ camsFetcher, deferCams: true, onCamsUpdate, onCamsFailure }));
    expect(initial.current.temperature).toBe(22);
    await vi.runAllTimersAsync();
    expect(onCamsFailure).toHaveBeenCalledTimes(1);
    expect(onCamsUpdate.mock.calls[0][0].current).toMatchObject({ temperature: 22, air_quality_data: null,
      data_quality: { cams_status: "unavailable", mode: "national_contract_v2" } });
    const result = await enrichNationalWeatherV2WithCams(bundle(), options({ camsFetcher, retryUnavailableCams: true }));
    expect(result.current.data_quality.cams_status).toBe("fresh");
    expect(camsFetcher).toHaveBeenCalledTimes(2);
  });

  it("clearly reports no CAMS coverage outside FVG without any reader request", async () => {
    const camsFetcher = vi.fn();
    const result = await enrichNationalWeatherV2WithCams(bundle("058091"), options({ camsFetcher }));
    expect(result.current).toMatchObject({ temperature: 22, air_quality_data: null, pollen_data: { status: "unavailable" },
      data_quality: { cams_coverage: "fvg_only", cams_diagnostic: { code: "CAMS_COVERAGE_UNAVAILABLE" } } });
    expect(camsFetcher).not.toHaveBeenCalled();
  });

  it("rejects a different municipality or catalog instead of mixing it into national ICON", async () => {
    const camsFetcher = vi.fn().mockResolvedValue({ ...supplement(), municipality_istat: "030129" });
    const result = await enrichNationalWeatherV2WithCams(bundle(), options({ camsFetcher }));
    expect(result.current.air_quality_data).toBeNull();
    expect(result.current.data_quality.cams_diagnostic.code).toBe("PROVIDER_IDENTITY_MISMATCH");
    expect(result.current.temperature).toBe(22);
  });

  it("does not serve a previous hour, expired verification, stale freshness or another endpoint from memory", async () => {
    const camsFetcher = vi.fn().mockResolvedValue(supplement());
    await enrichNationalWeatherV2WithCams(bundle(), options({ camsFetcher }));
    for (const opts of [
      { now: () => Date.parse("2026-09-21T16:00:00Z") },
      { verificationNow: () => NOW + 60_001 },
      { now: () => Date.parse("2026-09-22T07:00:00Z") },
      { baseUrl: "http://127.0.0.1:8780" },
    ]) expect(readNationalWeatherV2CamsBundle(bundle(), options(opts)).current.air_quality_data).toBeNull();
  });

  it("never allows a slow superseded request to replace the forced fresh supplement", async () => {
    vi.useFakeTimers();
    let complete;
    const camsFetcher = vi.fn().mockImplementationOnce(() => new Promise(resolve => { complete = resolve; }))
      .mockResolvedValue(supplement());
    const oldUpdate = vi.fn();
    await enrichNationalWeatherV2WithCams(bundle(), options({ camsFetcher, deferCams: true, onCamsUpdate: oldUpdate }));
    await enrichNationalWeatherV2WithCams(bundle(), options({ camsFetcher, force: true }));
    complete({ ...supplement(), pollen: "obsolete" });
    await vi.runAllTimersAsync();
    expect(oldUpdate).not.toHaveBeenCalled();
    expect(readNationalWeatherV2CamsBundle(bundle(), options()).current.pollen).not.toBe("obsolete");
  });
});
