import { beforeAll, describe, expect, it } from "vitest";
import { fetchLocalWeatherV1Bootstrap } from "./localWeatherV1Adapter";
import { fetchLocalWeatherV1RuntimeBundle } from "./localWeatherV1Runtime";

// Read-only, explicitly enabled integration check. No browser/user cache writes,
// no synthetic ICON values and no calls to schedulers or acquisition jobs.
const enabled = globalThis.process?.env.METEOFRIUL_RUN_ICON_FALLBACK_LIVE === "1";
const baseUrl = globalThis.process?.env.METEOFRIUL_ICON_FALLBACK_BASE_URL
  || "http://127.0.0.1:5176/__local-weather-pilot";
const HOUR = 3_600_000;
const location = { city: "Pordenone", municipality: { istatCode: "093033", name: "Pordenone" } };

function storageFor(values) {
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
    key: index => [...values.keys()][index] ?? null,
    get length() { return values.size; },
  };
}

describe.skipIf(!enabled)("real ICON payload through pilot offline fallback", () => {
  const values = new Map();
  let validTo;
  let runAt;
  beforeAll(async () => {
    const onlineIconOnly = (url, options) => {
      if (!url.includes("/weather/v1/icon2i/")) throw new TypeError("CAMS unavailable in integration test");
      return globalThis.fetch(url, options);
    };
    const bundle = await fetchLocalWeatherV1RuntimeBundle(location, {
      baseUrl, fetchImpl: onlineIconOnly, storage: storageFor(values),
      now: Date.now, force: true, bundleFetcher: fetchLocalWeatherV1Bootstrap,
    });
    runAt = Date.parse(bundle.current.data_quality.run_utc);
    // The 72 h horizon is validated by the raw ICON v1 contract before use.
    validTo = runAt + 72 * HOUR;
    expect(bundle.current.hourly_forecast.length).toBeGreaterThanOrEqual(12);
    expect(bundle.current.data_quality.cams_status).toBe("unavailable");
  }, 30_000);

  it.each([48, 36, 24, 12])("reopens offline and rebuilds %i hours from the validated raw cache", async count => {
    // New storage facade and fetch identity simulate a cold client. Each test
    // uses a private clone, so clock changes cannot contaminate other tests.
    const storage = storageFor(new Map(values));
    const clock = validTo - (count - 1) * HOUR;
    const result = await fetchLocalWeatherV1RuntimeBundle(location, {
      baseUrl, storage, fetchImpl: async () => { throw new TypeError("offline"); },
      now: () => clock, force: true, bundleFetcher: fetchLocalWeatherV1Bootstrap,
    });
    expect(result.current.hourly_forecast).toHaveLength(count);
    expect(Date.parse(result.current.data_quality.run_utc)).toBe(runAt);
    expect(result.current.hourly_forecast.every(row => Date.parse(row.time) >= clock)).toBe(true);
    expect(new Set(result.current.hourly_forecast.map(row => row.time)).size).toBe(count);
    expect(result.current.hourly_forecast.at(-1).time).toBe(new Date(validTo).toISOString().replace(".000Z", "Z"));
    expect(result.current.temperature).toEqual(expect.any(Number));
    expect(result.current.data_quality.cams_status).toBe("unavailable");
  });

  it("recomputes the hour and rejects the same run once only 11 future rows remain", async () => {
    const storage = storageFor(new Map(values));
    let clock = validTo - 11 * HOUR;
    const options = {
      baseUrl, storage, fetchImpl: async () => { throw new TypeError("offline"); },
      now: () => clock, force: true, bundleFetcher: fetchLocalWeatherV1Bootstrap,
    };
    const accepted = await fetchLocalWeatherV1RuntimeBundle(location, options);
    expect(accepted.current.hourly_forecast).toHaveLength(12);
    clock += 1;
    await expect(fetchLocalWeatherV1RuntimeBundle(location, options)).rejects.toBeDefined();
  });
});
