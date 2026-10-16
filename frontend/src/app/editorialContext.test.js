import { describe, expect, it, vi } from "vitest";

import {
  EDITORIAL_CONTEXT_STORAGE_KEY,
  createEditorialContext,
  readInitialEditorialContext,
  writeStoredEditorialContext,
} from "./editorialContext";

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: vi.fn((key) => values.get(key) ?? null),
    setItem: vi.fn((key, value) => values.set(key, value)),
  };
}

describe("editorial context", () => {
  it("captures an FVG weather location only for the first migration", () => {
    expect(readInitialEditorialContext({
      storage: createStorage(),
      weatherLocation: { city: "Pordenone", region: "Friuli Venezia Giulia" },
    }).focusLocation.city).toBe("Pordenone");
  });

  it("falls back to the FVG editorial default for a national weather location", () => {
    const context = readInitialEditorialContext({
      storage: createStorage(),
      weatherLocation: { city: "Roma", region: "Lazio", countryCode: "IT" },
    });

    expect(context).toMatchObject({
      followsWeatherLocation: false,
      regionCode: "IT-36",
      scopeId: "fvg-editorial",
    });
    expect(context.focusLocation).toMatchObject({
      city: "Udine",
      dataPoint: {
        source: "municipality_catalog",
      },
      lat: 46.0693,
      lon: 13.23715,
    });
  });

  it("restores a public municipality center for legacy FVG editorial contexts", () => {
    const storage = createStorage({
      [EDITORIAL_CONTEXT_STORAGE_KEY]: JSON.stringify({
        focusLocation: {
          city: "Pordenone",
          region: "Friuli Venezia Giulia",
          province: "PN",
        },
        scopeId: "fvg-editorial",
        version: 1,
      }),
    });

    expect(readInitialEditorialContext({ storage }).focusLocation).toMatchObject({
      city: "Pordenone",
      dataPoint: { source: "municipality_catalog" },
      lat: 45.95689,
      lon: 12.66051,
    });
  });

  it("keeps a stored editorial focus independent from later weather changes", () => {
    const storage = createStorage();
    writeStoredEditorialContext(createEditorialContext({
      city: "Pordenone",
      region: "Friuli Venezia Giulia",
    }), { storage });

    const context = readInitialEditorialContext({
      storage,
      weatherLocation: { city: "Torino", region: "Piemonte", countryCode: "IT" },
    });

    expect(context.focusLocation.city).toBe("Pordenone");
    expect(storage.setItem).toHaveBeenCalledWith(
      EDITORIAL_CONTEXT_STORAGE_KEY,
      expect.any(String),
    );
  });
});
