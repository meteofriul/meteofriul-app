import {
  getLocationMunicipality,
  getLocationMunicipalityName,
} from "../domain/geo/locationIdentity";
import { sha256Hex } from "./weatherV1Client";

const CONTRACT = "weather/v2/icon2i";
const OFFICIAL_CLOUD_BASE = "https://meteofriul-national-weather-49007668366.europe-west1.run.app";
const RESOLUTION_KIND = "meteofriul.weather.icon.national.local_pilot_resolution";
const BLOCK_KIND = "meteofriul.weather.icon.national.block";
const ISTAT = /^\d{6}$/u;
const RUN_ID = /^\d{8}T\d{6}Z$/u;
const SAFE_PATH = /^runs\/\d{8}T\d{6}Z\/blocks\/[a-z0-9-]+\.json$/u;
const HASH = /^[0-9a-f]{64}$/u;

export class NationalWeatherV2ClientError extends Error {
  constructor(code, message, options) {
    super(message, options);
    this.name = "NationalWeatherV2ClientError";
    this.code = code;
  }
}

function fail(code, message, cause) {
  throw new NationalWeatherV2ClientError(code, message, cause ? { cause } : undefined);
}

function normalizedBase(value) {
  const base = String(value || "").trim().replace(/\/+$/u, "");
  if (!base || base.includes("?") || base.includes("#") || base.includes("\\")) {
    fail("INVALID_BASE_URL", "Base nazionale v2 non valida");
  }
  return base;
}

function finiteCoordinate(value, minimum, maximum) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum ? parsed : null;
}

export function buildNationalWeatherV2ResolveUrl(location, { baseUrl } = {}) {
  const city = getLocationMunicipalityName(location);
  if (!city) fail("LOCATION_REQUIRED", "Comune nazionale mancante");
  const base = normalizedBase(baseUrl);
  const municipality = getLocationMunicipality(location);
  const query = new URLSearchParams({ city });
  const province = municipality?.province || location?.province;
  if (province) query.set("province", String(province).trim());
  const latitude = finiteCoordinate(location?.lat ?? location?.latitude, -90, 90);
  const longitude = finiteCoordinate(location?.lon ?? location?.longitude, -180, 180);
  // The cloud reader resolves the municipality by name + province. Do not
  // place device GPS in Cloud Run request URLs/logs; local pilot keeps its API.
  if (base !== OFFICIAL_CLOUD_BASE && latitude !== null && longitude !== null) {
    query.set("lat", String(latitude));
    query.set("lon", String(longitude));
  }
  return `${base}/${CONTRACT}/resolve.json?${query}`;
}

function validateResolution(value) {
  if (
    value?.schema_version !== 1
    || value?.kind !== RESOLUTION_KIND
    || value?.contract !== CONTRACT
    || value?.status !== "experimental_local_pilot_only"
    || !RUN_ID.test(value?.source_run_id)
    || !ISTAT.test(value?.municipality?.istat_code)
    || typeof value?.municipality?.name !== "string"
    || typeof value?.block_id !== "string"
    || typeof value?.cell_id !== "string"
    || !SAFE_PATH.test(value?.block_path)
    || !Number.isSafeInteger(value?.block_json_bytes)
    || value.block_json_bytes < 1
    || !HASH.test(value?.block_sha256)
  ) fail("INVALID_RESOLUTION", "Resolver nazionale v2 non valido");
  if (!value.block_path.startsWith(`runs/${value.source_run_id}/blocks/`)) {
    fail("INVALID_RESOLUTION", "Resolver nazionale v2 incoerente");
  }
  return value;
}

const blockPromises = new Map();
const MAX_MEMORY_BLOCKS = 2;

function retainBlockPromise(key, promise) {
  blockPromises.delete(key);
  blockPromises.set(key, promise);
  while (blockPromises.size > MAX_MEMORY_BLOCKS) {
    blockPromises.delete(blockPromises.keys().next().value);
  }
}

async function readJsonResponse(response, label) {
  if (!response?.ok) fail("HTTP_ERROR", `${label} non disponibile`);
  const text = await response.text();
  let document;
  try {
    document = JSON.parse(text);
  } catch (error) {
    fail("INVALID_JSON", `${label} non e JSON valido`, error);
  }
  return { text, document };
}

function validateBlock(block, resolution) {
  if (
    block?.schema_version !== 2
    || block?.kind !== BLOCK_KIND
    || block?.contract !== CONTRACT
    || block?.source_run_id !== resolution.source_run_id
    || block?.block_id !== resolution.block_id
    || !Array.isArray(block?.time_axis)
    || block.time_axis.length < 13
    || block?.municipality_cells?.[resolution.municipality.istat_code] !== resolution.cell_id
    || !Array.isArray(block?.cells)
  ) fail("INVALID_BLOCK", "Blocco nazionale v2 non valido");
  let previous = null;
  for (const value of block.time_axis) {
    const timestamp = Date.parse(value);
    if (!Number.isFinite(timestamp) || (previous !== null && timestamp - previous !== 3_600_000)) {
      fail("INVALID_BLOCK", "Timeline nazionale v2 non valida");
    }
    previous = timestamp;
  }
  const cell = block.cells.find((candidate) => candidate?.cell_id === resolution.cell_id);
  if (!cell?.values || typeof cell.values !== "object") {
    fail("INVALID_BLOCK", "Cella nazionale v2 mancante");
  }
  const required = [
    "t_2m_k", "td_2m_k", "u_10m_m_s", "v_10m_m_s", "cloud_cover_pct",
    "pressure_msl_pa", "total_precipitation_mm", "weather_code", "wind_gust_max_m_s",
    "convective_rain_mm", "grid_scale_rain_mm", "convective_snow_mm",
    "grid_scale_snow_mm", "grid_scale_graupel_mm",
  ];
  for (const id of required) {
    const series = cell.values[id];
    if (!Array.isArray(series) || series.length !== block.time_axis.length) {
      fail("INVALID_BLOCK", `Serie nazionale v2 non valida: ${id}`);
    }
  }
  return cell;
}

export async function fetchNationalWeatherV2Cell(
  location,
  {
    baseUrl,
    fetchImpl = globalThis.fetch,
    force = false,
  } = {},
) {
  if (typeof fetchImpl !== "function") fail("FETCH_UNAVAILABLE", "Fetch non disponibile");
  const base = normalizedBase(baseUrl);
  const resolutionResponse = await fetchImpl(
    buildNationalWeatherV2ResolveUrl(location, { baseUrl: base }),
    { cache: "no-store" },
  );
  const { document: resolutionDocument } = await readJsonResponse(resolutionResponse, "Resolver nazionale v2");
  const resolution = validateResolution(resolutionDocument);
  const blockUrl = `${base}/${CONTRACT}/${resolution.block_path}`;
  const blockKey = `${blockUrl}#${resolution.block_sha256}`;
  let pending = !force ? blockPromises.get(blockKey) : null;
  if (pending) retainBlockPromise(blockKey, pending);
  if (!pending) {
    pending = (async () => {
      const response = await fetchImpl(blockUrl, { cache: force ? "reload" : "force-cache" });
      const { text, document } = await readJsonResponse(response, "Blocco nazionale v2");
      const bytes = new TextEncoder().encode(text);
      if (bytes.length !== resolution.block_json_bytes || sha256Hex(bytes) !== resolution.block_sha256) {
        fail("BLOCK_INTEGRITY_FAILED", "Integrita blocco nazionale v2 non valida");
      }
      return document;
    })();
    if (!force) {
      retainBlockPromise(blockKey, pending);
      pending.catch(() => {
        if (blockPromises.get(blockKey) === pending) blockPromises.delete(blockKey);
      });
    }
  }
  const block = await pending;
  const cell = validateBlock(block, resolution);
  return { resolution, block, cell };
}

export function resetNationalWeatherV2ClientCacheForTests() {
  blockPromises.clear();
}
