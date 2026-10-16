import { describe, expect, it } from "vitest";

import { fetchNationalWeatherV2Bootstrap } from "./nationalWeatherV2Adapter";

const runLive = globalThis.process?.env.METEOFRIUL_RUN_NATIONAL_V2_LIVE === "1";

describe.skipIf(!runLive)("national weather v2 live pilot contract", () => {
  it.each([
    [{ city: "Urbino", province: "PU", countryCode: "IT", regionCode: "IT-57", lat: 43.7262, lon: 12.6363 }, "041067"],
    [{ city: "Udine", province: "UD", countryCode: "IT", regionCode: "IT-36", lat: 46.0635, lon: 13.2358 }, "030129"],
  ])("resolves and adapts %s from the real national bundle", async (location, expectedIstat) => {
    const result = await fetchNationalWeatherV2Bootstrap(location, {
      baseUrl: "http://127.0.0.1:8782",
      fetchImpl: globalThis.fetch,
      storage: null,
      now: Date.now,
      force: true,
    });

    expect(result.city).toBe(location.city);
    expect(result.current.primary_source).toBe("icon2i_local_pilot");
    expect(result.current.data_quality).toMatchObject({
      mode: "national_contract_v2",
      municipality_istat: expectedIstat,
      run_utc: "2026-09-20T00:00:00Z",
    });
    expect(result.current.hourly_next_12h).toHaveLength(12);
    expect(result.forecast.forecast.length).toBeGreaterThan(1);
  }, 20_000);
});
