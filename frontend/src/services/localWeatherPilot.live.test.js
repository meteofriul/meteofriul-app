import { describe, expect, it } from "vitest";

import {
  fetchLocalWeatherV1Bootstrap,
  LOCAL_WEATHER_V1_CATALOG,
  LOCAL_WEATHER_V1_ISTAT_CODES,
} from "./localWeatherV1Adapter";
import { createWeatherV1Client } from "./weatherV1Client";

const runLivePilot = globalThis.process?.env.METEOFRIUL_RUN_LOCAL_PILOT_LIVE === "1";

describe.skipIf(!runLivePilot)("local weather pilot live contract", () => {
  it("loads Pordenone through latest, manifest and immutable municipality objects", async () => {
    const result = await fetchLocalWeatherV1Bootstrap(
      { city: "Pordenone" },
      {
        baseUrl: "http://127.0.0.1:5174/__local-weather-pilot",
        fetchImpl: globalThis.fetch,
        storage: null,
        now: Date.now,
        deferCams: true,
      },
    );

    expect(result.city).toBe("Pordenone");
    expect(result.current.primary_source).toBe("icon2i_local_pilot");
    expect(result.current.model_support.open_meteo).toBe(false);
    expect(result.current.hourly_forecast).toHaveLength(48);
    expect(result.current.data_quality.municipality_istat).toBe("093033");
    expect(result.forecast.primary_source).toBe("icon2i_local_pilot");
  }, 20_000);

  it("validates every ICON municipality object exposed by the local data plane", async () => {
    const client = createWeatherV1Client({
      baseUrl: "http://127.0.0.1:5174/__local-weather-pilot",
      fetchImpl: globalThis.fetch,
      storage: null,
      now: Date.now,
      catalog: LOCAL_WEATHER_V1_CATALOG,
      istatCodes: LOCAL_WEATHER_V1_ISTAT_CODES,
      force: true,
    });
    const latest = await client.icon2i.fetchLatest();
    const manifest = await client.icon2i.fetchManifest(latest);

    expect(Object.keys(manifest.document.objects).sort()).toEqual(LOCAL_WEATHER_V1_ISTAT_CODES);

    const pending = [...LOCAL_WEATHER_V1_ISTAT_CODES];
    const validated = [];
    const worker = async () => {
      while (pending.length) {
        const istatCode = pending.shift();
        const payload = await client.icon2i.fetchMunicipality(manifest, istatCode);
        expect(payload.document.municipality.istat_code).toBe(istatCode);
        expect(payload.document.hourly).toHaveLength(73);
        expect(payload.document.two_hourly).toHaveLength(36);
        validated.push(istatCode);
      }
    };
    await Promise.all(Array.from({ length: 8 }, () => worker()));

    expect(validated.sort()).toEqual(LOCAL_WEATHER_V1_ISTAT_CODES);
  }, 60_000);

  it("validates every CAMS and pollen municipality object exposed by the local data plane", async () => {
    // Pin the validation clock inside the selected CAMS run's usable window so
    // this contract test stays deterministic while still exercising all live
    // HTTP objects exposed by the local pilot.
    const client = createWeatherV1Client({
      baseUrl: "http://127.0.0.1:5174/__local-weather-pilot",
      fetchImpl: globalThis.fetch,
      storage: null,
      now: () => Date.parse("2026-09-04T12:00:00Z"),
      catalog: LOCAL_WEATHER_V1_CATALOG,
      istatCodes: LOCAL_WEATHER_V1_ISTAT_CODES,
      force: true,
    });

    const validateProvider = async (providerClient, expectedVariableCount) => {
      const latest = await providerClient.fetchLatest();
      const manifest = await providerClient.fetchManifest(latest);
      expect(Object.keys(manifest.document.objects).sort()).toEqual(LOCAL_WEATHER_V1_ISTAT_CODES);

      const pending = [...LOCAL_WEATHER_V1_ISTAT_CODES];
      const validated = [];
      const worker = async () => {
        while (pending.length) {
          const istatCode = pending.shift();
          const payload = await providerClient.fetchMunicipality(manifest, istatCode);
          expect(payload.document.municipality.istat_code).toBe(istatCode);
          expect(payload.document.variables).toHaveLength(expectedVariableCount);
          expect(payload.document.hourly).toHaveLength(97);
          validated.push(istatCode);
        }
      };
      await Promise.all(Array.from({ length: 8 }, () => worker()));
      expect(validated.sort()).toEqual(LOCAL_WEATHER_V1_ISTAT_CODES);
    };

    await validateProvider(client.camsEurope, 28);
    await validateProvider(client.camsPollen, 6);
  }, 120_000);
});
