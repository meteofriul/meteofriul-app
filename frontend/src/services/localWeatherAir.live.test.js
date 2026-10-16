import { expect, it } from "vitest";
import { fetchLocalWeatherV1Bootstrap } from "./localWeatherV1Adapter";
import { fetchLocalWeatherV1RuntimeBundle } from "./localWeatherV1Runtime";

const baseUrl = process.env.METEOFRIUL_LIVE_BASE_URL || "http://127.0.0.1:8781";
const now = process.env.METEOFRIUL_LIVE_REAL_CLOCK === "1"
  ? Date.now
  : () => Date.parse("2026-09-04T21:00:00Z");

it.skipIf(process.env.METEOFRIUL_RUN_LOCAL_PILOT_LIVE !== "1")("delivers air from the restored historical pilot", async () => {
  const bundle = await fetchLocalWeatherV1Bootstrap({ city: "Udine" }, {
    baseUrl,
    fetchImpl: globalThis.fetch,
    storage: null,
    now,
    force: true,
  });
  expect(bundle.current.pollen_data.status).toBe("experimental_model_snapshot");
  expect(bundle.current.air_quality_data).not.toBeNull();
  expect(bundle.current.air_quality_data.run_at).toBe(bundle.current.data_quality.cams_run_utc);
  expect(bundle.current.air_quality_data.values["particulate_matter_2.5um"]).toEqual(expect.any(Number));
}, 20000);

it.skipIf(process.env.METEOFRIUL_RUN_LOCAL_PILOT_LIVE !== "1")("retains real deferred air through the runtime", async () => {
  let resolve;
  const updated = new Promise(r => { resolve = r; });
  await fetchLocalWeatherV1RuntimeBundle({city: "Pordenone"}, {
    baseUrl, fetchImpl: globalThis.fetch, storage: null,
    now, force: true,
    bundleFetcher: fetchLocalWeatherV1Bootstrap, deferCams: true, onCamsUpdate: resolve,
  });
  const bundle = await updated;
  expect(bundle.current.air_quality_data).not.toBeNull();
}, 20000);
