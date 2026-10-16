import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const RELEASE_TARGETS = new Set(["android", "cloudflare"]);
const TAGGED_CLOUD_RUN_HOST = /^[a-z0-9-]+---[a-z0-9-]+-[a-z0-9]+\.a\.run\.app$/u;
const LOCAL_WEATHER_PILOT_LOOPBACK = "http://127.0.0.1:8781";
const DEFINITIVE_EXPERIENCE_META = '<meta name="meteofriul-app-experience" content="definitive-v1">';
const DEFINITIVE_BRAND_MARK = "brand/pilot-r4/meteo-eventi-friul-mark-192.png";

export function normalizeReleaseApiBase(value) {
  const candidate = String(value || "").trim();
  let url;

  try {
    url = new URL(candidate);
  } catch {
    throw new Error("release_api_base_must_be_absolute_https");
  }

  if (
    url.protocol !== "https:" ||
    !TAGGED_CLOUD_RUN_HOST.test(url.hostname) ||
    url.username ||
    url.password ||
    url.port ||
    url.search ||
    url.hash ||
    !["/api", "/api/"].includes(url.pathname)
  ) {
    throw new Error("release_api_base_must_be_tagged_cloud_run_api");
  }

  return `${url.origin}/api`;
}

export function assertReleaseApiEnvironment({ env = {}, expectedApiBase, target }) {
  if (!RELEASE_TARGETS.has(target)) {
    throw new Error("release_target_invalid");
  }

  const expected = normalizeReleaseApiBase(expectedApiBase);
  const key = target === "android" ? "VITE_ANDROID_API_BASE" : "VITE_API_BASE";
  const forbiddenKey = target === "android" ? "VITE_API_BASE" : "VITE_ANDROID_API_BASE";
  const actual = normalizeReleaseApiBase(env[key]);

  if (actual !== expected) {
    throw new Error(`${key.toLowerCase()}_does_not_match_expected_api`);
  }
  if (String(env[forbiddenKey] || "").trim()) {
    throw new Error(`${forbiddenKey.toLowerCase()}_must_be_absent_for_${target}`);
  }

  return expected;
}

function getEntryScriptPaths(buildDirectory) {
  const indexPath = resolve(buildDirectory, "index.html");
  const html = readFileSync(indexPath, "utf8");
  const sources = [...html.matchAll(/<script\b[^>]*\bsrc=["']([^"']+\.js)["'][^>]*>/giu)]
    .map((match) => match[1].split(/[?#]/u, 1)[0])
    .filter(Boolean);

  if (sources.length === 0) {
    throw new Error("release_entry_bundle_missing");
  }

  return sources.map((source) => resolve(buildDirectory, source.replace(/^\/+/, "")));
}

function getJavaScriptPaths(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) return getJavaScriptPaths(path);
    return entry.isFile() && entry.name.endsWith(".js") ? [path] : [];
  });
}

export function assertReleaseBundleApiBinding({ buildDirectory, expectedApiBase }) {
  const expected = normalizeReleaseApiBase(expectedApiBase);
  const html = readFileSync(resolve(buildDirectory, "index.html"), "utf8");
  if (!html.includes(DEFINITIVE_EXPERIENCE_META)) {
    throw new Error("release_bundle_definitive_experience_missing");
  }
  readFileSync(resolve(buildDirectory, DEFINITIVE_BRAND_MARK));
  const entrySources = getEntryScriptPaths(buildDirectory).map((path) => readFileSync(path, "utf8"));
  const allJavaScriptSources = getJavaScriptPaths(resolve(buildDirectory))
    .map((path) => readFileSync(path, "utf8"));

  if (!entrySources.some((source) => source.includes(expected))) {
    throw new Error("release_bundle_expected_api_missing");
  }
  if (allJavaScriptSources.some((source) => source.includes(LOCAL_WEATHER_PILOT_LOOPBACK))) {
    throw new Error("release_bundle_contains_local_weather_pilot_loopback");
  }

  const cloudRunUrls = new Set();
  const pattern = /https:\/\/[a-z0-9.-]+\.a\.run\.app\/api\/?/giu;
  for (const source of allJavaScriptSources) {
    for (const match of source.matchAll(pattern)) {
      cloudRunUrls.add(normalizeReleaseApiBase(match[0]));
    }
  }

  const unexpected = [...cloudRunUrls].filter((url) => url !== expected);
  if (unexpected.length > 0) {
    throw new Error("release_bundle_contains_unexpected_api");
  }

  return { entryCount: entrySources.length, expectedApiBase: expected };
}

function parseArguments(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || value === undefined) {
      throw new Error("release_guard_arguments_invalid");
    }
    values[key.slice(2)] = value;
  }
  return values;
}

function runCli() {
  const args = parseArguments(process.argv.slice(2));
  const target = String(args.target || "").trim();
  const expectedEnv = String(args["expected-env"] || "").trim();
  const expectedApiBase = expectedEnv ? process.env[expectedEnv] : args.expected;
  const buildDirectory = resolve(String(args["build-dir"] || ""));

  assertReleaseApiEnvironment({ env: process.env, expectedApiBase, target });
  const result = assertReleaseBundleApiBinding({ buildDirectory, expectedApiBase });
  process.stdout.write(`Runtime API verificata (${target}): ${result.expectedApiBase}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  runCli();
}
