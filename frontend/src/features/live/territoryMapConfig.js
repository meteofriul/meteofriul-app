export const TERRITORY_FVG_BOUNDS = Object.freeze([
  Object.freeze([45.55, 12.25]),
  Object.freeze([46.75, 13.95]),
]);

// The FVG bounds remain the initial editorial view. Navigation can widen to
// the whole Italian territory covered by the national Radar-DPC product.
export const TERRITORY_ITALY_BOUNDS = Object.freeze([
  Object.freeze([35.1, 6.2]),
  Object.freeze([47.6, 19]),
]);

export function getTerritoryInitialCenter(location) {
  const lat = location?.lat == null || location.lat === "" ? Number.NaN : Number(location.lat);
  const lon = location?.lon == null || location.lon === "" ? Number.NaN : Number(location.lon);
  const [[south, west], [north, east]] = TERRITORY_ITALY_BOUNDS;

  if (
    !Number.isFinite(lat)
    || !Number.isFinite(lon)
    || lat < south
    || lat > north
    || lon < west
    || lon > east
  ) return null;

  return Object.freeze([lat, lon]);
}

const OPENSTREETMAP_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>';
const DEFAULT_MAX_ZOOM = 13;
const DEFAULT_MIN_ZOOM = 5;

const CARTO_POSITRON_BASEMAP = Object.freeze({
  attribution: `${OPENSTREETMAP_ATTRIBUTION} &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener noreferrer">CARTO</a>`,
  id: "carto-positron",
  maxZoom: DEFAULT_MAX_ZOOM,
  minZoom: DEFAULT_MIN_ZOOM,
  subdomains: "abcd",
  tileUrl: "https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png",
});

const CARTO_DARK_MATTER_BASEMAP = Object.freeze({
  ...CARTO_POSITRON_BASEMAP,
  id: "carto-dark-matter",
  tileUrl: "https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png",
});

function finiteZoom(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function environmentString(value) {
  return String(value || "").trim();
}

function withZooms(provider, minZoom, maxZoom) {
  return {
    ...provider,
    maxZoom,
    minZoom,
  };
}

/**
 * Keeps basemap providers and public client credentials outside the React map.
 * CARTO is the only direct basemap provider. OpenStreetMap remains credited as
 * the underlying data source, but is never used as a tile-provider fallback.
 */
export function getTerritoryBasemapConfig(
  environment = import.meta.env,
  { theme = "light" } = {},
) {
  const maxZoom = finiteZoom(
    environment?.VITE_TERRITORY_BASEMAP_MAX_ZOOM,
    DEFAULT_MAX_ZOOM,
  );
  const minZoom = finiteZoom(
    environment?.VITE_TERRITORY_BASEMAP_MIN_ZOOM,
    DEFAULT_MIN_ZOOM,
  );
  const cartoApiKey = environmentString(environment?.VITE_TERRITORY_CARTO_API_KEY);
  const cartoBasemap = theme === "dark"
    ? CARTO_DARK_MATTER_BASEMAP
    : CARTO_POSITRON_BASEMAP;
  const tileUrl = cartoApiKey
    ? `${cartoBasemap.tileUrl}?key=${encodeURIComponent(cartoApiKey)}`
    : cartoBasemap.tileUrl;

  return {
    fallback: null,
    primary: {
      ...withZooms(cartoBasemap, minZoom, maxZoom),
      tileUrl,
    },
  };
}
