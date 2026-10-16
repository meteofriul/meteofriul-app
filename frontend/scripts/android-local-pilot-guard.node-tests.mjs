import assert from "node:assert/strict";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { loadConfig } from "@capacitor/cli/dist/config.js";
import { updateAndroid } from "@capacitor/cli/dist/android/update.js";

import {
  ANDROID_LOCAL_PILOT_API_BASE,
  ANDROID_LOCAL_PILOT_COMMUNITY_API_BASE,
  ANDROID_LOCAL_PILOT_NATIONAL_API_BASE,
  ANDROID_LOCAL_PILOT_APPLICATION_ID,
  assertAndroidLocalPilotBundle,
  assertAndroidLocalPilotEnvironment,
  assertAndroidLocalPilotSourceIsolation,
} from "./android-local-pilot-guard.mjs";

const EXPECTED_API =
  "https://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app/api";
const MARKER = "b".repeat(64);

test("cloud pilot requires exact national and optional community endpoints and no PC loopback", () => {
  const directory = createBuild(`const API=${JSON.stringify(EXPECTED_API)}; const WEATHER="https://meteofriul-weather-49007668366.europe-west1.run.app"; const NATIONAL="https://meteofriul-national-weather-49007668366.europe-west1.run.app";`);
  try {
    assertAndroidLocalPilotBundle({ buildDirectory: directory, expectedApiBase: EXPECTED_API, cloud: true });
    assert.throws(() => assertAndroidLocalPilotBundle({ buildDirectory: directory, expectedApiBase: EXPECTED_API, cloud: true, community: true }), /community_endpoint_missing/);
    writeFileSync(join(directory, "assets", "community.js"), 'const COMMUNITY="https://meteofriul-community-49007668366.europe-west1.run.app/api";');
    assertAndroidLocalPilotBundle({ buildDirectory: directory, expectedApiBase: EXPECTED_API, cloud: true, community: true });
    writeFileSync(join(directory, "assets", "events.js"), 'const EVENTS="https://meteofriul-events-49007668366.europe-west1.run.app/api";');
    assertAndroidLocalPilotBundle({ buildDirectory: directory, expectedApiBase: EXPECTED_API, cloud: true, community: true });
    writeFileSync(join(directory, "assets", "unexpected.js"), 'const UNKNOWN="https://another-335641913741.europe-west1.run.app/api";');
    assert.throws(() => assertAndroidLocalPilotBundle({ buildDirectory: directory, expectedApiBase: EXPECTED_API, cloud: true, community: true }), /unexpected_official_api/);
    rmSync(join(directory, "assets", "unexpected.js"));
    writeFileSync(join(directory, "assets", "extra.js"), 'const OLD="http://127.0.0.1:8781";');
    assert.throws(() => assertAndroidLocalPilotBundle({ buildDirectory: directory, expectedApiBase: EXPECTED_API, cloud: true, community: true }), /unexpected_loopback/);
    writeFileSync(join(directory, "assets", "extra.js"), 'const NATIONAL="http://127.0.0.1:8782";');
    assert.throws(() => assertAndroidLocalPilotBundle({ buildDirectory: directory, expectedApiBase: EXPECTED_API, cloud: true, community: true }), /unexpected_loopback/);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});
const FRONTEND_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

test("community loopback must be explicitly enabled and is not a cloud endpoint", () => {
  const base = `const API=${JSON.stringify(EXPECTED_API)}; const WEATHER=${JSON.stringify(ANDROID_LOCAL_PILOT_API_BASE)}; const NATIONAL=${JSON.stringify(ANDROID_LOCAL_PILOT_NATIONAL_API_BASE)};`;
  const directory = createBuild(base);
  try {
    assert.throws(() => assertAndroidLocalPilotBundle({ buildDirectory: directory, expectedApiBase: EXPECTED_API, community: true }), /community_loopback_missing/);
    writeFileSync(join(directory, "assets", "community.js"), `const COMMUNITY=${JSON.stringify(ANDROID_LOCAL_PILOT_COMMUNITY_API_BASE)};`);
    assertAndroidLocalPilotBundle({ buildDirectory: directory, expectedApiBase: EXPECTED_API, community: true });
    assert.throws(() => assertAndroidLocalPilotBundle({ buildDirectory: directory, expectedApiBase: EXPECTED_API }), /unexpected_loopback/);
    assert.throws(() => assertAndroidLocalPilotBundle({ buildDirectory: directory, expectedApiBase: EXPECTED_API, community: true, cloud: true }), /loopback_missing/);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

function createBuild(bundleSource) {
  const directory = mkdtempSync(join(tmpdir(), "meteofriul-android-local-pilot-guard-"));
  mkdirSync(join(directory, "assets"));
  writeFileSync(
    join(directory, "index.html"),
    '<!doctype html><script type="module" src="/assets/main.js"></script>',
  );
  writeFileSync(join(directory, "assets", "main.js"), bundleSource);
  return directory;
}

test("requires a one-run marker, the tagged HTTPS API and no release contamination", () => {
  const env = {
    METEO_ANDROID_LOCAL_PILOT_GUARD_MARKER: MARKER,
    VITE_ANDROID_API_BASE: EXPECTED_API,
  };
  assert.equal(
    assertAndroidLocalPilotEnvironment({ env, expectedApiBase: EXPECTED_API, marker: MARKER }),
    EXPECTED_API,
  );
  assert.throws(() => assertAndroidLocalPilotEnvironment({
    env,
    expectedApiBase: EXPECTED_API,
    marker: "short",
  }), /marker_invalid/u);
  assert.throws(() => assertAndroidLocalPilotEnvironment({
    env: { ...env, METEO_PLAY_RELEASE_GUARD_MARKER: "c".repeat(64) },
    expectedApiBase: EXPECTED_API,
    marker: MARKER,
  }), /play_marker_must_be_absent/u);
  assert.throws(() => assertAndroidLocalPilotEnvironment({
    env: { ...env, VITE_API_BASE: EXPECTED_API },
    expectedApiBase: EXPECTED_API,
    marker: MARKER,
  }), /vite_api_base_must_be_absent/u);
  assert.throws(() => assertAndroidLocalPilotEnvironment({
    env: { ...env, VITE_LOCAL_WEATHER_NATIONAL_ENABLED: "1" },
    expectedApiBase: EXPECTED_API,
    marker: MARKER,
  }), /national_binding_is_owned/u);
  assert.throws(() => assertAndroidLocalPilotEnvironment({
    env: { ...env, VITE_LOCAL_WEATHER_NATIONAL_API_BASE: ANDROID_LOCAL_PILOT_NATIONAL_API_BASE },
    expectedApiBase: EXPECTED_API,
    marker: MARKER,
  }), /national_binding_is_owned/u);
});

test("requires the regional and national loopbacks and the official HTTPS API", () => {
  const valid = createBuild(
    `const OFFICIAL=${JSON.stringify(EXPECTED_API)};const WEATHER=${JSON.stringify(ANDROID_LOCAL_PILOT_API_BASE)};const NATIONAL=${JSON.stringify(ANDROID_LOCAL_PILOT_NATIONAL_API_BASE)};`,
  );
  const wrongLoopback = createBuild(
    `const OFFICIAL=${JSON.stringify(EXPECTED_API)};const WEATHER="http://localhost:8781";`,
  );
  const missingNational = createBuild(
    `const OFFICIAL=${JSON.stringify(EXPECTED_API)};const WEATHER=${JSON.stringify(ANDROID_LOCAL_PILOT_API_BASE)};`,
  );
  const extraLoopback = createBuild(
    `const OFFICIAL=${JSON.stringify(EXPECTED_API)};const WEATHER=${JSON.stringify(ANDROID_LOCAL_PILOT_API_BASE)};const NATIONAL=${JSON.stringify(ANDROID_LOCAL_PILOT_NATIONAL_API_BASE)};`,
  );
  writeFileSync(
    join(extraLoopback, "assets", "lazy-other.js"),
    'const OTHER="http://127.0.0.1:9999";',
  );
  try {
    assert.deepEqual(assertAndroidLocalPilotBundle({
      buildDirectory: valid,
      expectedApiBase: EXPECTED_API,
    }), {
      entryCount: 1,
      localWeatherApiBase: ANDROID_LOCAL_PILOT_API_BASE,
      nationalWeatherApiBase: ANDROID_LOCAL_PILOT_NATIONAL_API_BASE,
      officialApiBase: EXPECTED_API,
    });
    assert.throws(() => assertAndroidLocalPilotBundle({
      buildDirectory: wrongLoopback,
      expectedApiBase: EXPECTED_API,
    }), /loopback_missing/u);
    assert.throws(() => assertAndroidLocalPilotBundle({
      buildDirectory: missingNational,
      expectedApiBase: EXPECTED_API,
    }), /national_loopback_missing/u);
    assert.throws(() => assertAndroidLocalPilotBundle({
      buildDirectory: extraLoopback,
      expectedApiBase: EXPECTED_API,
    }), /unexpected_loopback/u);
  } finally {
    rmSync(valid, { force: true, recursive: true });
    rmSync(wrongLoopback, { force: true, recursive: true });
    rmSync(missingNational, { force: true, recursive: true });
    rmSync(extraLoopback, { force: true, recursive: true });
  }
});

test("keeps cleartext, debug identity and background-weather opt-out in local sources only", () => {
  assert.deepEqual(assertAndroidLocalPilotSourceIsolation({ frontendRoot: FRONTEND_ROOT }), {
    applicationId: ANDROID_LOCAL_PILOT_APPLICATION_ID,
    productionScheme: "https",
    localPilotScheme: "https",
  });
});

test("fresh-clone plugin update needs no dist and copies no main Web assets", async () => {
  const directory = mkdtempSync(join(tmpdir(), "meteofriul-pilot-cap-scaffold-"));
  try {
    // Capacitor's loader resolves both config and dependencies from cwd. This
    // test is also invoked from the repository root, not only from frontend.
    const previousCwd = process.cwd();
    let config;
    try {
      process.chdir(FRONTEND_ROOT);
      config = await loadConfig();
    } finally {
      process.chdir(previousCwd);
    }
    const originalAndroidRoot = config.android.platformDirAbs;
    // Keep package discovery in the frontend, but redirect every Android write
    // to this disposable fixture. The ordinary Web build deliberately is absent.
    for (const [key, value] of Object.entries(config.android)) {
      if (key.endsWith("Abs") && typeof value === "string" && value.startsWith(originalAndroidRoot)) {
        config.android[key] = join(directory, value.slice(originalAndroidRoot.length));
      }
    }
    config.app.webDirAbs = join(directory, "missing-dist");
    mkdirSync(config.android.assetsDirAbs, { recursive: true });
    await assert.rejects(updateAndroid(config), /Could not find the web assets directory/);

    // This is the bootstrap performed by the protected PowerShell script.
    mkdirSync(config.android.webDirAbs, { recursive: true });
    await updateAndroid(config);
    const plugins = JSON.parse(readFileSync(join(config.android.assetsDirAbs, "capacitor.plugins.json"), "utf8"));
    assert.equal(plugins.length, 5);
    assert.ok(plugins.some(plugin => plugin.pkg === "@capacitor/geolocation"));
    assert.ok(plugins.some(plugin => plugin.pkg === "@capacitor/share"));
    assert.ok(existsSync(join(config.android.cordovaPluginsDirAbs, "build.gradle")));
    assert.equal(existsSync(config.app.webDirAbs), false);
    assert.equal(existsSync(join(config.android.webDirAbs, "index.html")), false);
    assert.equal(existsSync(join(config.android.assetsDirAbs, "capacitor.config.json")), false);
    assert.equal(existsSync(join(directory, "app/src/localPilot")), false);

    const script = readFileSync(join(FRONTEND_ROOT, "../scripts/build-android-local-weather-pilot.ps1"), "utf8");
    const prepareAt = script.indexOf("New-Item -ItemType Directory -Path $mainPublicRoot -Force");
    assert.ok(prepareAt >= 0 && prepareAt < script.indexOf("& npx cap update android"));
    assert.ok(script.indexOf("& node $guardScript") < script.indexOf("& robocopy $buildDirectory $localPublicRoot"));
    assert.match(script, /adb reverse tcp:8781 tcp:8781 e adb reverse tcp:8782 tcp:8782/u);
    assert.match(script, /NationalWeatherApiBase = if \(\$WeatherCloud\) \{ "https:\/\/meteofriul-national-weather-49007668366\.europe-west1\.run\.app" \}/u);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
