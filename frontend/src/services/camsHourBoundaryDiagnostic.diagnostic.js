import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { harness, RUN_B } from "./camsRecoveryTestFixtures";
import { isValidUvDocument } from "../features/weather/uvForecast";
import { buildWeatherForecastViewModel } from "../features/weather/weatherForecastViewModel";
import { buildLocalWeatherPilotMetadata } from "../domain/weather/localWeatherPilotMetadata";
import { CAMS_AIR_FIELDS } from "./camsHourlyCache";

// Real adapter/runtime with synthetic provider I/O, not a phone reproduction.
// The raw HTTP/schema/hash validator is outside this fixture's boundary.
const HOUR = 3_600_000;
const BOUNDARY = Date.parse("2026-09-11T03:00:00Z"); // 05:00 Europe/Rome, CAMS run age 27 h.
const SAMPLE = "2026-09-11T03:00:00Z";
const iso = time => new Date(time).toISOString().replace(".000Z", "Z");
const AIR_VARIABLES = Object.freeze([
  ["particulate_matter_2.5um", "pm2_5"],
  ["particulate_matter_10um", "pm10"],
  ["ozone", "ozono"],
  ["nitrogen_dioxide", "biossido_azoto"],
].map(([id, ui_key]) => Object.freeze({
  id,
  ui_key,
  category: "air_quality",
  unit: "ug/m3",
  validation_status: "regularly_validated_in_situ_by_provider",
})));

function episodeHarness({ latency = 0 } = {}) {
  const h = harness({ available: true });
  h.publish();
  const originalFactory = h.clientFactory.getMockImplementation();
  h.clientFactory.mockImplementation(options => {
    const clients = originalFactory(options);
    const latest = clients.camsPollen.fetchLatest.getMockImplementation();
    if (latency) clients.camsPollen.fetchLatest.mockImplementation(signal => new Promise((resolve, reject) => {
      setTimeout(async () => resolve(await latest()), latency);
      signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })), { once: true });
    }));
    const municipality = clients.camsPollen.fetchMunicipality.getMockImplementation();
    clients.camsPollen.fetchMunicipality.mockImplementation(async (...args) => {
      const result = await municipality(...args);
      const run = Date.parse(result.document.run_at);
      result.document.valid_from = RUN_B;
      result.document.valid_to = iso(run + 96 * HOUR);
      result.document.freshness = {
        fresh_until: iso(run + 24 * HOUR), usable_until: iso(run + 30 * HOUR),
      };
      result.freshness = {
        status: Date.now() <= run + 24 * HOUR ? "fresh" : "stale",
        freshUntil: iso(run + 24 * HOUR), usableUntil: iso(run + 30 * HOUR),
        remainingCoverageHours: (run + 96 * HOUR - Date.now()) / HOUR, requiredFutureHours: 0,
      };
      // Different values at each real forecast hour make wrong selection visible.
      result.document.hourly.forEach((row, index) => { row.values.ragweed_pollen = index; });
      result.airResult = { ...result, document: {
        ...result.document, provider: "cams_europe",
        variables: AIR_VARIABLES,
        hourly: result.document.hourly.map((row, index) => ({
          ...row,
          values: Object.fromEntries(CAMS_AIR_FIELDS
            .map((id, field) => [id, index + 0.5 + field / 10])),
          quality_flags: Object.fromEntries(CAMS_AIR_FIELDS.map(id => [id, []])),
        })),
      } };
      return result;
    });
    return clients;
  });
  return h;
}

function expectCurrentCams(bundle) {
  expect(bundle.current.source.cams.status).toBe("available");
  expect(bundle.current.data_quality.cams_run_utc).toBe(RUN_B);
  expect(bundle.current.data_quality.cams_valid_at_utc).toBe(SAMPLE);
  expect(bundle.forecast.data_quality.cams_run_utc).toBe(RUN_B);
  expect(bundle.forecast.data_quality.cams_valid_at_utc).toBe(SAMPLE);
  expect(bundle.current.pollen_data.freshness).toBe("stale");
  expect(bundle.current.pollen_data.valid_at_utc).toBe(SAMPLE);
  expect(bundle.current.pollen_data.values.ambrosia).toBe(27);
  expect(bundle.current.air_quality_data).toMatchObject({
    valid_at: SAMPLE,
    run_at: RUN_B,
    values: {
      "particulate_matter_2.5um": 27.5,
      "particulate_matter_10um": 27.6,
      ozone: 27.7,
      nitrogen_dioxide: 27.8,
    },
  });
}

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(BOUNDARY); });
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); });

describe("11 September CAMS forecast-hour diagnosis", () => {
  it.each([
    [24 * HOUR, "available", "fresh"],
    [24 * HOUR + 1, "available", "stale"],
    [30 * HOUR, "available", "stale"],
    [30 * HOUR + 1, "unavailable", null],
  ])("runtime distinguishes the 24/30-hour boundaries at age %i ms", async (age, status, freshness) => {
    vi.setSystemTime(Date.parse(RUN_B) + age);
    const bundle = await episodeHarness().fetch({ force: true });
    expect(bundle.current.source.cams.status).toBe(status);
    expect(bundle.current.pollen_data.freshness).toBe(freshness);
    if (status === "available") {
      expect(bundle.current.pollen_data.valid_at_utc).toBe(iso(Date.parse(RUN_B) + Math.floor(age / HOUR) * HOUR));
      expect(bundle.current.air_quality_data).not.toBeNull();
    } else {
      expect(bundle.current.air_quality_data).toBeNull();
      expect(bundle.current.data_quality.cams_diagnostic).toMatchObject({ code: "EXPIRED", stage: "adapt" });
    }
  });

  it("keeps the 27-hour run usable beyond freshness, selecting 03 UTC for both components", async () => {
    const h = episodeHarness();
    expectCurrentCams(await h.fetch({ force: true }));
  });

  it("rechecks a recently verified bundle and selects the new sample at exactly 03 UTC", async () => {
    vi.setSystemTime(BOUNDARY - 1_000);
    const h = episodeHarness();
    const before = await h.fetch();
    expect(before.current.pollen_data.valid_at_utc).toBe("2026-09-11T02:00:00Z");
    expect(before.current.pollen_data.values.ambrosia).toBe(26);
    vi.setSystemTime(BOUNDARY);
    expectCurrentCams(await h.fetch());
    expect(h.bundleFetcher).toHaveBeenCalledTimes(2);
  });

  it("keeps stale-but-usable CAMS available in the metadata and forecast card view model", async () => {
    const bundle = await episodeHarness().fetch({ force: true });
    expect(buildLocalWeatherPilotMetadata(bundle.current)).toMatchObject({
      cams_available: true, cams_pending: false, cams_status: "stale",
    });
    const model = buildWeatherForecastViewModel({
      ...bundle, rawCurrent: bundle.current, status: "fresh", isStale: false, error: null,
    }, { now: BOUNDARY, language: "it", location: { city: "Pordenone" } });
    expect(model.cams).toMatchObject({ status: "available", validAt: SAMPLE, air: bundle.current.air_quality_data });
    expect(model.cams.values.find(entry => entry.id === "ambrosia")?.value).toBe(27);
  });

  it.each([false, true])("must select the completion-time CAMS sample when a request crosses 03 UTC (deferCams=%s)", async deferCams => {
    vi.setSystemTime(BOUNDARY - 1_000);
    const h = episodeHarness({ latency: 5_000 });
    const update = vi.fn();
    const request = h.fetch({ force: true, deferCams, onCamsUpdate: update });
    await vi.advanceTimersByTimeAsync(0);
    if (deferCams) {
      expect((await request).current.source.cams.status).toBe("pending");
      expect(update).not.toHaveBeenCalled();
    }
    await vi.advanceTimersByTimeAsync(5_000);
    expect(Date.now()).toBe(BOUNDARY + 4_000);
    expect(h.observed[0].camsPollen.fetchMunicipality).toHaveBeenCalledTimes(1);
    // Drain the existing zero-delay observer delivery, not a product retry.
    await vi.advanceTimersByTimeAsync(1);
    if (deferCams) expect(update).toHaveBeenCalledTimes(1);
    const completed = deferCams ? update.mock.lastCall[0] : await request;
    // Correct requirement remains an ordinary assertion: no skip or expected-failure wrapper.
    expectCurrentCams(completed);
  });

  it("rejects the old UV run after 02 CEST without making the 27-hour CAMS bundle unusable", async () => {
    const run = Date.parse("2026-09-09T00:00:00Z");
    const uv = { schema: "pilot-uv-v1", unit: "1", run_at: iso(run), grid: [[46, 13]],
      hours: Array.from({ length: 72 }, (_, index) => ({ time: iso(run + index * HOUR), values: [0] })) };
    expect(isValidUvDocument(uv, run + 48 * HOUR)).toBe(true);
    expect(isValidUvDocument(uv, run + 48 * HOUR + 1)).toBe(false);
    expect(isValidUvDocument(uv, BOUNDARY)).toBe(false);
    expectCurrentCams(await episodeHarness().fetch({ force: true }));
  });
});
