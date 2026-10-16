import { describe, expect, it } from "vitest";

import { buildNationalWeatherV2ResolveUrl } from "./nationalWeatherV2Client";

describe("national weather v2 client", () => {
  it("uses municipality and province without GPS in the exact pilot cloud URL", () => {
    const cloud = "https://meteofriul-national-weather-49007668366.europe-west1.run.app";
    const location = { city: "Urbino", province: "PU", lat: 43.7262, lon: 12.6363 };
    expect(buildNationalWeatherV2ResolveUrl(location, { baseUrl: cloud })).toBe(
      `${cloud}/weather/v2/icon2i/resolve.json?city=Urbino&province=PU`,
    );
    expect(buildNationalWeatherV2ResolveUrl(location, { baseUrl: "http://127.0.0.1:8782" })).toBe(
      "http://127.0.0.1:8782/weather/v2/icon2i/resolve.json?city=Urbino&province=PU&lat=43.7262&lon=12.6363",
    );
  });

  it("keeps cloud municipality and base validation without coordinate fallback", () => {
    const cloud = "https://meteofriul-national-weather-49007668366.europe-west1.run.app";
    expect(() => buildNationalWeatherV2ResolveUrl({ lat: 43.7, lon: 12.6 }, { baseUrl: cloud })).toThrow("Comune nazionale mancante");
    expect(() => buildNationalWeatherV2ResolveUrl({ city: "Urbino" }, { baseUrl: `${cloud}?unsafe=1` })).toThrow("Base nazionale v2 non valida");
  });

  it("resolves a municipality with province and complete coordinates", () => {
    const url = buildNationalWeatherV2ResolveUrl({
      city: "Urbino",
      province: "PU",
      countryCode: "IT",
      lat: 43.7262,
      lon: 12.6363,
    }, { baseUrl: "/__local-weather-national/" });

    expect(url).toBe(
      "/__local-weather-national/weather/v2/icon2i/resolve.json"
      + "?city=Urbino&province=PU&lat=43.7262&lon=12.6363",
    );
  });

  it("never sends a partial coordinate pair", () => {
    const url = buildNationalWeatherV2ResolveUrl(
      { city: "Roma", province: "RM", lat: 41.9 },
      { baseUrl: "http://127.0.0.1:8782" },
    );
    expect(url).toBe(
      "http://127.0.0.1:8782/weather/v2/icon2i/resolve.json?city=Roma&province=RM",
    );
  });
});
