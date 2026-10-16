import { describe, expect, it, vi } from "vitest";

import {
  buildRadarUrl,
  fetchRadarPayload,
  normalizeRadarPayload,
} from "./radarApi";

function buildPayload() {
  return {
    available: true,
    city: "Pordenone",
    products: [
      {
        id: "rain",
        layer: "radar:sri",
        product_type: "SRI",
        time: "2026-08-03T07:10:00Z",
      },
    ],
    tiles: {
      base_url: "https://tiles.example.test",
    },
  };
}

describe("radar api", () => {
  it("builds a coordinate-aware URL and adds a token only on refresh", () => {
    expect(buildRadarUrl({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      lat: 45.9892,
      lon: 12.5473,
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
    }, {
      apiBase: "/api/",
    })).toBe("/api/weather/radar?city=Fontanafredda&lat=45.9892&lon=12.5473");

    expect(buildRadarUrl("Udine", {
      apiBase: "/api",
      force: true,
      now: () => 123,
    })).toBe("/api/weather/radar?city=Udine&_=123");
  });

  it("accepts only an available DPC V2 tile payload with timestamped products", () => {
    expect(normalizeRadarPayload(buildPayload())).toMatchObject({
      city: "Pordenone",
      products: [{ id: "rain", layer: "radar:sri" }],
    });

    expect(() => normalizeRadarPayload({ available: false, products: [] })).toThrow(
      "Radar temporaneamente non disponibile",
    );
    expect(() => normalizeRadarPayload({
      ...buildPayload(),
      tiles: undefined,
      wms: { url: "https://radar.example.test/wms" },
    })).toThrow("Radar temporaneamente non disponibile");
  });

  it("loads radar independently from bulletin and alerts", async () => {
    const payload = buildPayload();
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(payload),
    });

    await expect(fetchRadarPayload({ city: "Pordenone" }, {
      apiBase: "/api",
      fetchImpl,
    })).resolves.toMatchObject({ city: "Pordenone" });

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/weather/radar?city=Pordenone",
      { cache: "default" },
    );
  });
});
