import { describe, expect, it, vi } from "vitest";

import { mountTerritoryBasemapLayer } from "./territoryBasemapLayer";

function createHarness() {
  const layers = [];
  const leaflet = {
    tileLayer: vi.fn((tileUrl, options) => {
      const listeners = new Map();
      const layer = {
        addTo: vi.fn(() => layer),
        listeners,
        off: vi.fn((event, listener) => {
          if (listeners.get(event) === listener) listeners.delete(event);
          return layer;
        }),
        on: vi.fn((event, listener) => {
          listeners.set(event, listener);
          return layer;
        }),
        options,
        tileUrl,
      };
      layers.push(layer);
      return layer;
    }),
  };
  const map = { removeLayer: vi.fn() };
  return { layers, leaflet, map };
}

const CARTO = {
  attribution: "OpenStreetMap · CARTO",
  id: "carto-positron",
  maxZoom: 13,
  minZoom: 5,
  subdomains: "abcd",
  tileUrl: "https://{s}.basemaps.cartocdn.com/tiles/{z}/{x}/{y}.png?key=test",
};

describe("territory basemap layer", () => {
  it("mounts only the configured CARTO provider and never registers a provider fallback", () => {
    const harness = createHarness();
    const dispose = mountTerritoryBasemapLayer({
      basemap: { fallback: null, primary: CARTO },
      leaflet: harness.leaflet,
      map: harness.map,
    });

    expect(harness.layers).toHaveLength(1);
    expect(harness.layers[0].tileUrl).toContain("cartocdn.com");
    expect(harness.layers[0].options).toMatchObject({
      attribution: "OpenStreetMap · CARTO",
      subdomains: "abcd",
    });
    expect(harness.layers[0].addTo).toHaveBeenCalledWith(harness.map);
    expect(harness.layers[0].listeners.has("tileerror")).toBe(false);
    dispose();
    expect(harness.map.removeLayer).toHaveBeenCalledWith(harness.layers[0]);
  });
});
