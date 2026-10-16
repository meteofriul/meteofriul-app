import { readFileSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { loadEnv } from "vite";

const DIRECT_OSM_TILE_HOST = "tile.openstreetmap.org";
const CARTO_TILE_HOST = "basemaps.cartocdn.com";

function readBundleSources(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) return readBundleSources(path);
    if (!entry.isFile() || !/\.(?:html|js)$/u.test(entry.name)) return [];
    return [readFileSync(path, "utf8")];
  });
}

export function assertCartoBasemapEnvironment({ env = {} } = {}) {
  const apiKey = String(env.VITE_TERRITORY_CARTO_API_KEY || "").trim();
  if (!apiKey) throw new Error("carto_basemap_api_key_missing");
  if (apiKey.length < 20 || /[\s?&#]/u.test(apiKey)) {
    throw new Error("carto_basemap_api_key_invalid");
  }
  return { keyLength: apiKey.length };
}

export function assertCartoBasemapBundle({ buildDirectory, apiKey } = {}) {
  const sources = readBundleSources(resolve(buildDirectory));
  const normalizedApiKey = String(apiKey || "").trim();
  if (!normalizedApiKey) {
    throw new Error("carto_basemap_bundle_api_key_missing");
  }
  if (!sources.some((source) => source.includes(CARTO_TILE_HOST))) {
    throw new Error("carto_basemap_bundle_missing");
  }
  if (sources.some((source) => source.includes(DIRECT_OSM_TILE_HOST))) {
    throw new Error("carto_direct_osm_tiles_present");
  }
  if (!sources.some((source) => (
    source.includes("openstreetmap.org/copyright")
    && source.includes("carto.com/attributions")
  ))) {
    throw new Error("carto_basemap_attribution_missing");
  }
  if (!sources.some((source) => source.includes(encodeURIComponent(normalizedApiKey)))) {
    throw new Error("carto_basemap_api_key_not_embedded");
  }
  return { sourceCount: sources.length };
}

function parseArguments(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || value === undefined) {
      throw new Error("carto_basemap_guard_arguments_invalid");
    }
    values[key.slice(2)] = value;
  }
  return values;
}

function runCli() {
  const args = parseArguments(process.argv.slice(2));
  const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const mode = String(args.mode || "android");
  const env = { ...loadEnv(mode, frontendRoot, ""), ...process.env };
  const environmentResult = assertCartoBasemapEnvironment({ env });
  const bundleResult = args["build-dir"]
    ? assertCartoBasemapBundle({
      apiKey: env.VITE_TERRITORY_CARTO_API_KEY,
      buildDirectory: args["build-dir"],
    })
    : null;
  process.stdout.write(`${JSON.stringify({
    basemap: "carto",
    ...environmentResult,
    ...(bundleResult || {}),
  })}\n`);
}

if (process.argv[1]
  && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  runCli();
}
