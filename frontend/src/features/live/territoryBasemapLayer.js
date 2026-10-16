function layerOptions(provider) {
  const options = {
    attribution: provider.attribution,
    maxZoom: provider.maxZoom,
    minZoom: provider.minZoom,
  };
  if (provider.subdomains) options.subdomains = provider.subdomains;
  return options;
}

/**
 * Mounts the configured client-side basemap without changing providers.
 * Tiles stay direct-to-provider: this layer never proxies or persists them.
 */
export function mountTerritoryBasemapLayer({ basemap, leaflet, map }) {
  const primary = basemap?.primary;
  if (!primary?.tileUrl) throw new Error("Territory basemap primary provider is missing");

  const activeLayer = leaflet.tileLayer(primary.tileUrl, layerOptions(primary));
  activeLayer.addTo(map);

  return () => {
    try {
      map.removeLayer(activeLayer);
    } catch {
      // The owning Leaflet map may already be disposed during route teardown.
    }
  };
}
