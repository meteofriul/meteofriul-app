import { describe, expect, it } from "vitest";

import { buildBulletinRadarViewModel } from "./bulletinRadarViewModel";

const NOW = Date.parse("2026-08-03T07:29:00Z");

function buildState(overrides = {}) {
  return {
    isStale: false,
    payload: {
      available: true,
      city: "Pordenone",
      location: { lat: 45.9567, lon: 12.6605 },
      products: [
        {
          id: "rain",
          layer: "radar:sri",
          period_minutes: 5,
          product_type: "SRI",
          time: "2026-08-03T07:10:00Z",
          unit: "mm/h",
        },
        {
          id: "accumulation_1h",
          layer: "radar:srt1",
          period_minutes: 5,
          product_type: "SRT1",
          time: "2026-08-03T07:10:00Z",
          unit: "mm",
        },
      ],
      source: {
        label: "Radar-DPC",
        license: "CC BY-SA 4.0",
        license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
        url: "https://example.test/radar",
      },
      tiles: {
        base_url: "https://tiles.example.test",
        encoding: "red_channel_normalized",
        format: "webp",
        tile_size: 256,
        zoom: 7,
      },
    },
    status: "fresh",
    ...overrides,
  };
}

describe("bulletin radar view model", () => {
  it("exposes only SRI for the animated radar card", () => {
    const model = buildBulletinRadarViewModel(buildState(), {
      language: "it",
      now: () => NOW,
    });

    expect(model).toMatchObject({
      available: true,
      city: "Pordenone",
      sourceLabel: "Radar-DPC",
      title: "Radar precipitazioni",
    });
    expect(model.product).toMatchObject({
      id: "rain",
      label: "Pioggia",
      productType: "SRI",
      unit: "mm/h",
    });
    expect(model).not.toHaveProperty("products");
    expect(model.location).toEqual({ lat: 45.9567, lon: 12.6605 });
    expect(model.tiles).toEqual({
      baseUrl: "https://tiles.example.test",
      encoding: "red_channel_normalized",
      format: "webp",
      tileSize: 256,
      zoom: 7,
    });
    expect(model.isStale).toBe(false);
    expect(model.copy.live).toBe("LIVE");
    expect(model.copy.waiting).toBe("Radar in attesa del prossimo fotogramma");
    expect(model.legend).toEqual({
      ariaLabel: "Scala dell'intensità della pioggia da 0 a 100 millimetri all'ora",
      label: "Intensità pioggia",
      labels: ["Debole", "Moderata", "Intensa", "Forte", "Molto forte"],
      max: 100,
      min: 0,
      unit: "mm/h",
    });
  });

  it("marks cached fallback without hiding it", () => {
    const model = buildBulletinRadarViewModel(buildState({ isStale: true }), {
      language: "it",
    });

    expect(model.isStale).toBe(true);
    expect(model.animationLabel).toBe("Rivedi 90 minuti");
    expect(model.staleNotice).toContain("Radar non aggiornato");
  });

  it("does not fall back to the one-hour accumulation product", () => {
    const state = buildState();
    state.payload.products = state.payload.products.filter(({ id }) => id === "accumulation_1h");

    expect(buildBulletinRadarViewModel(state, { language: "it" })).toBeNull();
  });

  it("marks product metadata older than twenty minutes as stale", () => {
    const model = buildBulletinRadarViewModel(buildState(), {
      language: "it",
      now: () => Date.parse("2026-08-03T07:31:00Z"),
    });

    expect(model.isStale).toBe(true);
    expect(model.eyebrowLabel).toBe("Ultima osservazione radar");
  });

  it("renders a compact unavailable state only after an actual error", () => {
    expect(buildBulletinRadarViewModel({ status: "empty" })).toBeNull();
    expect(buildBulletinRadarViewModel({ status: "error" }, { language: "fur" })).toMatchObject({
      available: false,
      unavailableLabel: "Radar pal moment no disponibil",
    });
  });

  it("localizes the automatic playback waiting state in Friulian", () => {
    const model = buildBulletinRadarViewModel(buildState(), { language: "fur" });
    expect(model.copy.waiting).toBe("Radar in spiete de prossime imagjin");
  });

  it("uses national radar copy without promising an OSMER bulletin for Roma", () => {
    const location = {
      city: "Roma",
      countryCode: "IT",
      region: "Lazio",
      regionCode: "IT-62",
    };
    const available = buildBulletinRadarViewModel(buildState(), { language: "it", location });
    const unavailable = buildBulletinRadarViewModel(
      { status: "error" },
      { language: "it", location },
    );

    expect(available.copy.mapLabel).toBe("Mappa radar delle precipitazioni sull’Italia");
    expect(unavailable.unavailableDetail).toBe("Riprova più tardi.");
    expect(unavailable.unavailableDetail).not.toContain("Bollettino");
  });
});
