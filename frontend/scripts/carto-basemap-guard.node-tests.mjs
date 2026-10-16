import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  assertCartoBasemapBundle,
  assertCartoBasemapEnvironment,
} from "./carto-basemap-guard.mjs";

const VALID_KEY = `cb1_${"a".repeat(28)}`;

function createBundle(source) {
  const directory = mkdtempSync(join(tmpdir(), "meteofriul-carto-guard-"));
  mkdirSync(join(directory, "assets"));
  writeFileSync(
    join(directory, "index.html"),
    '<!doctype html><script type="module" src="/assets/main.js"></script>',
  );
  writeFileSync(join(directory, "assets", "main.js"), source);
  return directory;
}

test("requires a non-placeholder CARTO client key for official builds", () => {
  assert.deepEqual(assertCartoBasemapEnvironment({
    env: { VITE_TERRITORY_CARTO_API_KEY: VALID_KEY },
  }), { keyLength: VALID_KEY.length });
  assert.throws(() => assertCartoBasemapEnvironment(), /api_key_missing/u);
  assert.throws(() => assertCartoBasemapEnvironment({
    env: { VITE_TERRITORY_CARTO_API_KEY: "test" },
  }), /api_key_invalid/u);
  assert.throws(() => assertCartoBasemapEnvironment({
    env: { VITE_TERRITORY_CARTO_API_KEY: `${VALID_KEY}?other=value` },
  }), /api_key_invalid/u);
});

test("requires CARTO and both attributions while rejecting direct OSM tiles", () => {
  const valid = createBundle(`
    const TILES = "https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png?key=${VALID_KEY}";
    const OSM = "https://www.openstreetmap.org/copyright";
    const CARTO = "https://carto.com/attributions";
  `);
  const directOsm = createBundle(`
    const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    const CARTO = "https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png?key=${VALID_KEY}";
    const OSM = "https://www.openstreetmap.org/copyright";
    const CREDIT = "https://carto.com/attributions";
  `);
  const missingAttribution = createBundle(
    `const TILES = "https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png?key=${VALID_KEY}";`,
  );
  const missingKey = createBundle(`
    const TILES = "https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png";
    const OSM = "https://www.openstreetmap.org/copyright";
    const CARTO = "https://carto.com/attributions";
  `);
  const wrongKey = createBundle(`
    const TILES = "https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png?key=cb1_wrong_wrong_wrong_wrong_wrong";
    const OSM = "https://www.openstreetmap.org/copyright";
    const CARTO = "https://carto.com/attributions";
  `);
  try {
    assert.deepEqual(assertCartoBasemapBundle({
      apiKey: VALID_KEY,
      buildDirectory: valid,
    }), {
      sourceCount: 2,
    });
    assert.throws(() => assertCartoBasemapBundle({
      apiKey: VALID_KEY,
      buildDirectory: directOsm,
    }), /direct_osm_tiles_present/u);
    assert.throws(() => assertCartoBasemapBundle({
      apiKey: VALID_KEY,
      buildDirectory: missingAttribution,
    }), /attribution_missing/u);
    assert.throws(() => assertCartoBasemapBundle({
      buildDirectory: valid,
    }), /bundle_api_key_missing/u);
    assert.throws(() => assertCartoBasemapBundle({
      apiKey: VALID_KEY,
      buildDirectory: missingKey,
    }), /api_key_not_embedded/u);
    assert.throws(() => assertCartoBasemapBundle({
      apiKey: VALID_KEY,
      buildDirectory: wrongKey,
    }), /api_key_not_embedded/u);
  } finally {
    rmSync(valid, { force: true, recursive: true });
    rmSync(directOsm, { force: true, recursive: true });
    rmSync(missingAttribution, { force: true, recursive: true });
    rmSync(missingKey, { force: true, recursive: true });
    rmSync(wrongKey, { force: true, recursive: true });
  }
});
