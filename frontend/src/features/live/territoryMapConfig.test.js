import { describe, expect, it } from "vitest";

import {
  TERRITORY_FVG_BOUNDS,
  TERRITORY_ITALY_BOUNDS,
  getTerritoryInitialCenter,
  getTerritoryBasemapConfig,
} from "./territoryMapConfig";

describe("territory map configuration", () => {
  it("uses attributed CARTO tiles without mixing map data into React", () => {
    const config = getTerritoryBasemapConfig({});

    expect(config.primary.tileUrl).toContain("basemaps.cartocdn.com/rastertiles/light_all");
    expect(config.primary.tileUrl).not.toContain("tile.openstreetmap.org");
    expect(config.primary.attribution).toContain("OpenStreetMap");
    expect(config.primary.attribution).toContain("CARTO");
    expect(config.primary.id).toBe("carto-positron");
    expect(config.primary.minZoom).toBe(5);
    expect(config.fallback).toBeNull();
    expect(TERRITORY_FVG_BOUNDS).toEqual([[45.55, 12.25], [46.75, 13.95]]);
    expect(TERRITORY_ITALY_BOUNDS).toEqual([[35.1, 6.2], [47.6, 19]]);
  });

  it("centers the initial viewport on a selected Italian location and rejects invalid fallbacks", () => {
    expect(getTerritoryInitialCenter({ lat: 41.8933, lon: 12.4829 }))
      .toEqual([41.8933, 12.4829]);
    expect(getTerritoryInitialCenter({ lat: "41.8933", lon: "12.4829" }))
      .toEqual([41.8933, 12.4829]);
    expect(getTerritoryInitialCenter({ lat: null, lon: null })).toBeNull();
    expect(getTerritoryInitialCenter({ lat: 48.2082, lon: 16.3738 })).toBeNull();
  });

  it("keeps CARTO primary when the key is blank without adding a direct OSM fallback", () => {
    const config = getTerritoryBasemapConfig({
      VITE_TERRITORY_CARTO_API_KEY: "   ",
    });

    expect(config.primary.id).toBe("carto-positron");
    expect(config.primary.tileUrl).toContain("cartocdn");
    expect(config.primary.tileUrl).not.toContain("?key=");
    expect(config.primary.tileUrl).not.toContain("tile.openstreetmap.org");
    expect(config.fallback).toBeNull();
  });

  it("uses keyed CARTO Positron with its required attribution and no provider fallback", () => {
    const config = getTerritoryBasemapConfig({
      VITE_TERRITORY_CARTO_API_KEY: " key+/=?& ü ",
    });

    expect(config.primary).toMatchObject({
      id: "carto-positron",
      subdomains: "abcd",
    });
    expect(config.primary.tileUrl).toContain("basemaps.cartocdn.com/rastertiles/light_all");
    expect(config.primary.tileUrl).toContain("?key=key%2B%2F%3D%3F%26%20%C3%BC");
    expect(config.primary.attribution).toContain("OpenStreetMap");
    expect(config.primary.attribution).toContain("CARTO");
    expect(config.fallback).toBeNull();
  });

  it("uses CARTO Dark Matter with the same key and attribution in dark theme", () => {
    const config = getTerritoryBasemapConfig({
      VITE_TERRITORY_CARTO_API_KEY: " key+/=?& ü ",
    }, { theme: "dark" });

    expect(config.primary).toMatchObject({
      id: "carto-dark-matter",
      subdomains: "abcd",
    });
    expect(config.primary.tileUrl).toContain("basemaps.cartocdn.com/rastertiles/dark_all");
    expect(config.primary.tileUrl).toContain("?key=key%2B%2F%3D%3F%26%20%C3%BC");
    expect(config.primary.attribution).toContain("OpenStreetMap");
    expect(config.primary.attribution).toContain("CARTO");
    expect(config.fallback).toBeNull();
  });

  it("keeps the light CARTO style for unsupported theme values", () => {
    const config = getTerritoryBasemapConfig({
      VITE_TERRITORY_CARTO_API_KEY: "test",
    }, { theme: "sepia" });

    expect(config.primary.id).toBe("carto-positron");
    expect(config.primary.tileUrl).toContain("/light_all/");
  });

  it("keeps CARTO canonical while allowing supported zooms to be configured per build", () => {
    expect(getTerritoryBasemapConfig({
      VITE_TERRITORY_BASEMAP_MAX_ZOOM: "15",
      VITE_TERRITORY_BASEMAP_MIN_ZOOM: "6",
      VITE_TERRITORY_BASEMAP_URL: "https://tiles.example.test/{z}/{x}/{y}.png",
    })).toEqual({
      fallback: null,
      primary: {
        attribution: expect.stringContaining("CARTO"),
        id: "carto-positron",
        maxZoom: 15,
        minZoom: 6,
        subdomains: "abcd",
        tileUrl: expect.stringContaining("basemaps.cartocdn.com"),
      },
    });
  });
});
