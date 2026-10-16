import { describe, expect, it } from "vitest";

import {
  adaptNationalWeatherV2Cell,
  deriveNationalAccumulatedInterval,
  fetchNationalWeatherV2Bootstrap,
  readNationalWeatherV2PersistedBundle,
} from "./nationalWeatherV2Adapter";

function memoryStorage() {
  const values = new Map();
  return {
    values,
    getItem: key => values.get(key) ?? null,
    removeItem: key => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  };
}

function sourceFixture() {
  const runAt = "2026-09-20T00:00:00Z";
  const timeAxis = Array.from({ length: 73 }, (_, index) => (
    new Date(Date.parse(runAt) + index * 3_600_000).toISOString()
  ));
  const values = {
    t_2m_k: timeAxis.map((_, index) => 288.15 + index / 10),
    td_2m_k: timeAxis.map(() => 283.15),
    u_10m_m_s: timeAxis.map(() => 3),
    v_10m_m_s: timeAxis.map(() => 4),
    cloud_cover_pct: timeAxis.map(() => 20),
    pressure_msl_pa: timeAxis.map(() => 101_300),
    total_precipitation_mm: timeAxis.map((_, index) => index * 0.2),
    convective_rain_mm: timeAxis.map((_, index) => index * 0.05),
    grid_scale_rain_mm: timeAxis.map((_, index) => index * 0.15),
    convective_snow_mm: timeAxis.map(() => 0),
    grid_scale_snow_mm: timeAxis.map(() => 0),
    grid_scale_graupel_mm: timeAxis.map(() => 0),
    weather_code: timeAxis.map(() => 1),
    wind_gust_max_m_s: timeAxis.map(() => 8),
  };
  return {
    resolution: {
      source_run_id: "20260920T000000Z",
      run_at: runAt,
      generated_at: "2026-09-20T00:20:00Z",
      municipality: { istat_code: "041067", name: "Urbino", province: "PU" },
    },
    block: {
      time_axis: timeAxis,
      metadata: { catalog: { version: "istat-2026", sha256: "a".repeat(64) } },
    },
    cell: { latitude: 43.7262, longitude: 12.6363, values },
  };
}

describe("national weather v2 adapter", () => {
  it("derives intervals from accumulated precipitation without inventing lead zero", () => {
    expect(deriveNationalAccumulatedInterval([2], 0)).toBeNull();
    expect(deriveNationalAccumulatedInterval([1.1, 1.7], 1)).toBe(0.6);
    expect(deriveNationalAccumulatedInterval([1.1, 1.0995], 1)).toBe(0);
    expect(deriveNationalAccumulatedInterval([4.2, 0.7], 1)).toBe(0.7);
  });

  it("adapts a raw national cell to the existing Home and Previsioni contract", () => {
    const bundle = adaptNationalWeatherV2Cell(sourceFixture(), {
      now: Date.parse("2026-09-20T10:30:00Z"),
    });

    expect(bundle).toMatchObject({
      city: "Urbino",
      current: {
        city: "Urbino",
        temperature: 16,
        condition: "Poco nuvoloso",
        primary_source: "icon2i_local_pilot",
        data_quality: {
          mode: "national_contract_v2",
          municipality_istat: "041067",
          cams_status: "unavailable",
        },
      },
      forecast: { city: "Urbino", primary_source: "icon2i_local_pilot" },
    });
    expect(bundle.current.hourly_next_12h).toHaveLength(12);
    expect(bundle.current.hourly_forecast).toHaveLength(48);
    expect(bundle.forecast.forecast.length).toBeGreaterThan(1);
    expect(bundle.forecast.daily.time).toEqual(bundle.forecast.forecast.map(day => day.date));
  });

  it("separates homonymous municipalities and rejects an expired retained bundle", async () => {
    const storage = memoryStorage();
    const source = sourceFixture();
    const cellFetcher = async () => source;
    const first = { city: "Vercelli", province: "VC", countryCode: "IT" };
    const second = { city: "Vercelli", province: "XX", countryCode: "IT" };
    const now = () => Date.parse("2026-09-20T10:30:00Z");

    await fetchNationalWeatherV2Bootstrap(first, {
      baseUrl: "/national", cellFetcher, now, storage,
    });
    await fetchNationalWeatherV2Bootstrap(second, {
      baseUrl: "/national", cellFetcher, now, storage,
    });

    expect(storage.values.size).toBe(2);
    expect(readNationalWeatherV2PersistedBundle(first, {
      baseUrl: "/national", now, storage,
    })).not.toBeNull();
    expect(readNationalWeatherV2PersistedBundle(first, {
      baseUrl: "/national",
      now: () => Date.parse("2026-09-20T11:00:00Z"),
      storage,
    })).toBeNull();
    expect(storage.values.size).toBe(1);
  });
});
