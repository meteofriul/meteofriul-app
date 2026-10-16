import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  assertReleaseApiEnvironment,
  assertReleaseBundleApiBinding,
  normalizeReleaseApiBase,
} from "./runtime-api-binding.mjs";

const EXPECTED_API =
  "https://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app/api";

function createBuild(bundleSource, { definitive = true, includeBrand = true } = {}) {
  const directory = mkdtempSync(join(tmpdir(), "meteofriul-api-guard-"));
  mkdirSync(join(directory, "assets"));
  if (includeBrand) {
    mkdirSync(join(directory, "brand", "pilot-r4"), { recursive: true });
    writeFileSync(
      join(directory, "brand", "pilot-r4", "meteo-eventi-friul-mark-192.png"),
      "brand",
    );
  }
  writeFileSync(
    join(directory, "index.html"),
    `<!doctype html>${definitive ? '<meta name="meteofriul-app-experience" content="definitive-v1">' : ""}<script type="module" src="/assets/main.js"></script>`,
  );
  writeFileSync(join(directory, "assets", "main.js"), bundleSource);
  return directory;
}

test("accepts only the tagged Cloud Run HTTPS /api endpoint", () => {
  assert.equal(normalizeReleaseApiBase(`${EXPECTED_API}/`), EXPECTED_API);
  for (const invalid of [
    "/api",
    "http://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app/api",
    "https://meteofriul-api-bx24xqvcda-ew.a.run.app/api",
    `${EXPECTED_API}?preview=1`,
    `${EXPECTED_API}/weather`,
  ]) {
    assert.throws(() => normalizeReleaseApiBase(invalid));
  }
});

test("keeps Web and Android release variables mutually exclusive", () => {
  assert.equal(
    assertReleaseApiEnvironment({
      env: { VITE_API_BASE: EXPECTED_API },
      expectedApiBase: EXPECTED_API,
      target: "cloudflare",
    }),
    EXPECTED_API,
  );
  assert.equal(
    assertReleaseApiEnvironment({
      env: { VITE_ANDROID_API_BASE: EXPECTED_API },
      expectedApiBase: EXPECTED_API,
      target: "android",
    }),
    EXPECTED_API,
  );
  assert.throws(() => assertReleaseApiEnvironment({
    env: { VITE_API_BASE: "/api" },
    expectedApiBase: EXPECTED_API,
    target: "cloudflare",
  }));
  assert.throws(() => assertReleaseApiEnvironment({
    env: { VITE_ANDROID_API_BASE: EXPECTED_API, VITE_API_BASE: EXPECTED_API },
    expectedApiBase: EXPECTED_API,
    target: "android",
  }));
});

test("requires the expected API in the generated entry bundle", () => {
  const validBuild = createBuild(`const API=${JSON.stringify(EXPECTED_API)};`);
  const missingBuild = createBuild('const API="/api";');
  const wrongBuild = createBuild(
    'const API="https://other---meteofriul-api-bx24xqvcda-ew.a.run.app/api";',
  );
  const contaminatedBuild = createBuild(
    `const API=${JSON.stringify(EXPECTED_API)};`,
  );
  const legacyExperienceBuild = createBuild(
    `const API=${JSON.stringify(EXPECTED_API)};`,
    { definitive: false },
  );
  const missingBrandBuild = createBuild(
    `const API=${JSON.stringify(EXPECTED_API)};`,
    { includeBrand: false },
  );
  writeFileSync(
    join(contaminatedBuild, "assets", "lazy-pilot.js"),
    'const PILOT="http://127.0.0.1:8781";',
  );

  try {
    assert.deepEqual(
      assertReleaseBundleApiBinding({
        buildDirectory: validBuild,
        expectedApiBase: EXPECTED_API,
      }),
      { entryCount: 1, expectedApiBase: EXPECTED_API },
    );
    assert.throws(() => assertReleaseBundleApiBinding({
      buildDirectory: missingBuild,
      expectedApiBase: EXPECTED_API,
    }), /release_bundle_expected_api_missing/u);
    assert.throws(() => assertReleaseBundleApiBinding({
      buildDirectory: wrongBuild,
      expectedApiBase: EXPECTED_API,
    }), /release_bundle_expected_api_missing/u);
    assert.throws(() => assertReleaseBundleApiBinding({
      buildDirectory: contaminatedBuild,
      expectedApiBase: EXPECTED_API,
    }), /release_bundle_contains_local_weather_pilot_loopback/u);
    assert.throws(() => assertReleaseBundleApiBinding({
      buildDirectory: legacyExperienceBuild,
      expectedApiBase: EXPECTED_API,
    }), /release_bundle_definitive_experience_missing/u);
    assert.throws(() => assertReleaseBundleApiBinding({
      buildDirectory: missingBrandBuild,
      expectedApiBase: EXPECTED_API,
    }));
  } finally {
    rmSync(validBuild, { force: true, recursive: true });
    rmSync(missingBuild, { force: true, recursive: true });
    rmSync(wrongBuild, { force: true, recursive: true });
    rmSync(contaminatedBuild, { force: true, recursive: true });
    rmSync(legacyExperienceBuild, { force: true, recursive: true });
    rmSync(missingBrandBuild, { force: true, recursive: true });
  }
});
