import { expect, it } from "vitest";
import { fetchLocalWeatherV1Bootstrap } from "./localWeatherV1Adapter";
import { fetchLocalWeatherV1RuntimeBundle } from "./localWeatherV1Runtime";

// Opt-in, read-only benchmark: separate storage, no user cache changes.
it.skipIf(process.env.METEOFRIUL_TIMING !== "1")("measures real municipality changes", async () => {
  const data = new Map();
  const storage = { getItem: k => data.get(k) ?? null, setItem: (k,v) => data.set(k,v), removeItem: k => data.delete(k) };
  let requests = [];
  const fetchImpl = async (...args) => {
    const start = performance.now();
    const response = await fetch(...args);
    requests.push({ path: String(args[0]).replace(/^.*\/weather\/v1/, ""), status: response.status, ms: Math.round(performance.now()-start) });
    return response;
  };
  for (const [phase, force] of [["first", false], ["cached", false], ["refresh", true]]) {
    for (const city of ["Udine", "Pordenone", "Trieste", "Tarvisio"]) {
      requests = [];
      const start = performance.now();
      let finish;
      const supplement = new Promise(resolve => { finish = resolve; });
      const initial = await fetchLocalWeatherV1RuntimeBundle({city}, {
        baseUrl: "http://127.0.0.1:5176/__local-weather-pilot", fetchImpl, storage,
        now: Date.now, force, deferCams: true, bundleFetcher: fetchLocalWeatherV1Bootstrap,
        onCamsUpdate: finish,
      });
      const weatherMs = Math.round(performance.now()-start);
      expect(initial.forecast).toBeTruthy();
      // A refresh can immediately retain previous air: wait for the actual
      // supplement before measuring completion or starting the next sample.
      const full = phase === "cached" ? initial : await supplement;
      expect(full.current.air_quality_data).toBeTruthy();
      process.stdout.write(JSON.stringify({ phase, city, weatherMs, completeMs: Math.round(performance.now()-start), requests }) + "\n");
    }
  }
}, 120000);
