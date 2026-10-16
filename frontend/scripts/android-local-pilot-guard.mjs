import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

import { normalizeReleaseApiBase } from "./runtime-api-binding.mjs";
import {
  ANDROID_CLOUD_WEATHER_PILOT_API_BASE, ANDROID_CLOUD_WEATHER_NATIONAL_API_BASE,
  CLOUD_COMMUNITY_PILOT_API_BASE,
} from "./local-weather-pilot-config.mjs";

export const ANDROID_LOCAL_PILOT_API_BASE = "http://127.0.0.1:8781";
export const ANDROID_LOCAL_PILOT_NATIONAL_API_BASE = "http://127.0.0.1:8782";
export const ANDROID_LOCAL_PILOT_COMMUNITY_API_BASE = "http://127.0.0.1:8783/api";
export const ANDROID_LOCAL_PILOT_APPLICATION_ID = "com.meteofriul.app.localpilot";
const OFFICIAL_EVENTS_API_BASE = "https://meteofriul-events-49007668366.europe-west1.run.app/api";
const MARKER = /^[0-9a-f]{64}$/u;

function readEntrySources(buildDirectory) {
  const root = resolve(buildDirectory);
  const html = readFileSync(resolve(root, "index.html"), "utf8");
  const paths = [...html.matchAll(/<script\b[^>]*\bsrc=["']([^"']+\.js)["'][^>]*>/giu)]
    .map((match) => match[1].split(/[?#]/u, 1)[0])
    .filter(Boolean)
    .map((source) => resolve(root, source.replace(/^\/+/, "")));
  if (paths.length === 0) throw new Error("android_local_pilot_entry_bundle_missing");
  return paths.map((path) => readFileSync(path, "utf8"));
}

function readAllJavaScriptSources(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) return readAllJavaScriptSources(path);
    return entry.isFile() && entry.name.endsWith(".js") ? [readFileSync(path, "utf8")] : [];
  });
}

export function assertAndroidLocalPilotEnvironment({ env = {}, expectedApiBase, marker } = {}) {
  const normalizedMarker = String(marker || "");
  if (!MARKER.test(normalizedMarker)) {
    throw new Error("android_local_pilot_marker_invalid");
  }
  if (String(env.METEO_ANDROID_LOCAL_PILOT_GUARD_MARKER || "") !== normalizedMarker) {
    throw new Error("android_local_pilot_marker_mismatch");
  }
  if (String(env.METEO_PLAY_RELEASE_GUARD_MARKER || "").trim()) {
    throw new Error("android_local_pilot_play_marker_must_be_absent");
  }
  if (String(env.VITE_API_BASE || "").trim()) {
    throw new Error("vite_api_base_must_be_absent_for_android_local_pilot");
  }
  if (String(env.VITE_LOCAL_WEATHER_PILOT || "").trim()) {
    throw new Error("local_pilot_flag_is_owned_by_build_config");
  }
  if (
    String(env.VITE_LOCAL_WEATHER_NATIONAL_ENABLED || "").trim()
    || String(env.VITE_LOCAL_WEATHER_NATIONAL_API_BASE || "").trim()
  ) {
    throw new Error("local_pilot_national_binding_is_owned_by_build_config");
  }

  const expected = normalizeReleaseApiBase(expectedApiBase);
  if (String(env.VITE_LOCAL_COMMUNITY_PILOT_ENABLED || "").trim()
    || String(env.VITE_LOCAL_COMMUNITY_PILOT_API_BASE || "").trim()) {
    throw new Error("local_pilot_community_binding_is_owned_by_build_config");
  }
  const actual = normalizeReleaseApiBase(env.VITE_ANDROID_API_BASE);
  if (actual !== expected) {
    throw new Error("vite_android_api_base_does_not_match_expected_api");
  }
  return expected;
}

export function assertAndroidLocalPilotBundle({ buildDirectory, expectedApiBase, cloud = false, community = false } = {}) {
  const weatherBase = cloud ? ANDROID_CLOUD_WEATHER_PILOT_API_BASE : ANDROID_LOCAL_PILOT_API_BASE;
  const nationalBase = cloud ? ANDROID_CLOUD_WEATHER_NATIONAL_API_BASE : ANDROID_LOCAL_PILOT_NATIONAL_API_BASE;
  const communityBase = cloud ? CLOUD_COMMUNITY_PILOT_API_BASE : ANDROID_LOCAL_PILOT_COMMUNITY_API_BASE;
  const expected = normalizeReleaseApiBase(expectedApiBase);
  const entrySources = readEntrySources(buildDirectory);
  const allJavaScriptSources = readAllJavaScriptSources(resolve(buildDirectory));
  if (!entrySources.some((source) => source.includes(expected))) {
    throw new Error("android_local_pilot_official_api_missing");
  }
  if (!allJavaScriptSources.some((source) => source.includes(weatherBase))) {
    throw new Error("android_local_pilot_loopback_missing");
  }
  if (
    !allJavaScriptSources.some((source) => source.includes(nationalBase))
  ) {
    throw new Error(cloud ? "android_cloud_pilot_national_endpoint_missing" : "android_local_pilot_national_loopback_missing");
  }
  if (community && !allJavaScriptSources.some((source) => source.includes(communityBase))) {
    throw new Error(cloud ? "android_cloud_pilot_community_endpoint_missing" : "android_local_pilot_community_loopback_missing");
  }

  const cloudRunUrls = new Set();
  const cloudRunPattern = /https:\/\/[a-z0-9.-]+\.run\.app(?:\/api\/?)?/giu;
  const loopbackUrls = new Set();
  const loopbackPattern = /http:\/\/(?:127\.0\.0\.1|localhost)(?::\d+)?(?:\/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*)?/giu;
  for (const source of allJavaScriptSources) {
    for (const match of source.matchAll(cloudRunPattern)) {
      cloudRunUrls.add(match[0].replace(/\/$/u, ""));
    }
    for (const match of source.matchAll(loopbackPattern)) loopbackUrls.add(match[0].replace(/\/$/u, ""));
  }
  // Local previews and protected development builds read the same official
  // Events catalogue as production. Keep this exact binding, never a wildcard.
  const allowedCloudUrls = new Set([expected, OFFICIAL_EVENTS_API_BASE]);
  if (cloud) {
    allowedCloudUrls.add(weatherBase);
    allowedCloudUrls.add(nationalBase);
    if (community) allowedCloudUrls.add(communityBase);
  }
  const unexpectedCloudUrls = [...cloudRunUrls].filter((url) => !allowedCloudUrls.has(url));
  if (unexpectedCloudUrls.length) {
    throw new Error(`android_local_pilot_contains_unexpected_official_api: ${unexpectedCloudUrls.join(", ")}`);
  }
  const allowedLoopbacks = cloud
    ? new Set()
    : new Set([ANDROID_LOCAL_PILOT_API_BASE, ANDROID_LOCAL_PILOT_NATIONAL_API_BASE]);
  if (community) {
    if (!cloud) allowedLoopbacks.add(ANDROID_LOCAL_PILOT_COMMUNITY_API_BASE);
    if (!cloud && !loopbackUrls.has(ANDROID_LOCAL_PILOT_COMMUNITY_API_BASE)) {
      throw new Error("android_local_pilot_community_loopback_missing");
    }
  }
  if ([...loopbackUrls].some((url) => !allowedLoopbacks.has(url))) {
    throw new Error("android_local_pilot_contains_unexpected_loopback");
  }

  return {
    entryCount: entrySources.length,
    localWeatherApiBase: weatherBase,
    nationalWeatherApiBase: nationalBase,
    officialApiBase: expected,
  };
}

export function assertAndroidLocalPilotSourceIsolation({ frontendRoot } = {}) {
  const root = resolve(frontendRoot);
  const read = (path) => readFileSync(resolve(root, path), "utf8");
  const productionConfig = JSON.parse(read("capacitor.config.json"));
  const localConfig = JSON.parse(read("android/app/src/localPilot/assets/capacitor.config.json"));
  const mainManifest = read("android/app/src/main/AndroidManifest.xml");
  const localManifest = read("android/app/src/localPilot/AndroidManifest.xml");
  const localNetworkSecurity = read(
    "android/app/src/localPilot/res/xml/network_security_config_local_pilot.xml",
  );
  const gradle = read("android/app/build.gradle");
  const weatherScheduler = read(
    "android/app/src/main/java/com/meteofriul/app/location/MeteoBackgroundWeatherScheduler.java",
  );

  if (
    productionConfig.appId !== "com.meteofriul.app"
    || productionConfig.server?.androidScheme !== "https"
    || productionConfig.android?.allowMixedContent !== false
    || productionConfig.android?.webContentsDebuggingEnabled !== false
  ) throw new Error("android_production_capacitor_security_changed");
  if (
    localConfig.appId !== ANDROID_LOCAL_PILOT_APPLICATION_ID
    || localConfig.loggingBehavior !== "none"
    || localConfig.server?.hostname !== "localhost"
    || localConfig.server?.androidScheme !== "https"
    || localConfig.android?.allowMixedContent !== true
    || localConfig.android?.webContentsDebuggingEnabled !== true
  ) throw new Error("android_local_pilot_capacitor_contract_invalid");
  if (/usesCleartextTraffic|networkSecurityConfig/u.test(mainManifest)) {
    throw new Error("android_production_manifest_contains_local_network_policy");
  }
  if (
    !localManifest.includes('android:usesCleartextTraffic="true"')
    || !localManifest.includes('android:networkSecurityConfig="@xml/network_security_config_local_pilot"')
    || !localManifest.includes('android.permission.ACCESS_BACKGROUND_LOCATION')
    || !localManifest.includes('tools:node="remove"')
  ) throw new Error("android_local_pilot_manifest_contract_invalid");
  if (
    !localNetworkSecurity.includes('<base-config cleartextTrafficPermitted="false"')
    || !localNetworkSecurity.includes('<domain>localhost</domain>')
    || !localNetworkSecurity.includes('<domain>127.0.0.1</domain>')
  ) throw new Error("android_local_pilot_network_policy_invalid");
  if (
    !gradle.includes("applicationIdSuffix '.localpilot'")
    || !gradle.includes("buildConfigField 'boolean', 'LOCAL_WEATHER_PILOT', 'true'")
    || !gradle.includes("METEO_ANDROID_LOCAL_PILOT_GUARD_MARKER")
    || !gradle.includes("Android local-pilot and Play release tasks are mutually exclusive")
  ) throw new Error("android_local_pilot_gradle_isolation_invalid");
  if (!weatherScheduler.includes("if (BuildConfig.LOCAL_WEATHER_PILOT)")) {
    throw new Error("android_local_pilot_background_weather_not_disabled");
  }

  return {
    applicationId: localConfig.appId,
    productionScheme: productionConfig.server.androidScheme,
    localPilotScheme: localConfig.server.androidScheme,
  };
}

function parseArguments(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || value === undefined) {
      throw new Error("android_local_pilot_guard_arguments_invalid");
    }
    values[key.slice(2)] = value;
  }
  return values;
}

function runCli() {
  const args = parseArguments(process.argv.slice(2));
  const expectedApiBase = String(args.expected || "");
  const marker = String(args.marker || "");
  assertAndroidLocalPilotEnvironment({ env: process.env, expectedApiBase, marker });
  assertAndroidLocalPilotSourceIsolation({ frontendRoot: args["frontend-root"] });
  const result = assertAndroidLocalPilotBundle({
    buildDirectory: args["build-dir"],
    expectedApiBase,
    cloud: process.env.METEO_PILOT_WEATHER_CLOUD === "1",
    community: process.env.METEO_PILOT_COMMUNITY_LOCAL === "1",
  });
  process.stdout.write(
    `Android local pilot verificato: ${result.localWeatherApiBase}; meteo nazionale: ${result.nationalWeatherApiBase || "disabilitato"}; API ufficiale: ${result.officialApiBase}\n`,
  );
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) runCli();
