// Source-boundary guards only. These do not simulate Android scheduling, prove
// graph validation, or replace the pure-Java, JS-client and on-device tests.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const FRONTEND_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SOURCE_ROOT = join(FRONTEND_ROOT, "android", "app", "src");
const PILOT_PACKAGE = "localPilot/java/com/meteofriul/app/pilot";
const CLASS_NAMES = [
  "PilotWeatherPrefetchCore", "PilotWeatherPrefetchHttp", "PilotWeatherPrefetchPlugin",
  "PilotWeatherPrefetchScheduler", "PilotWeatherPrefetchStore", "PilotWeatherPrefetchWorker",
];
const EXPECTED_ORIGIN = "https://meteofriul-weather-49007668366.europe-west1.run.app";
const EXPECTED_WORK = "meteofriul-pilot-weather-prefetch-v1";
const GENERATED_PLUGINS = [
  { pkg: "@capacitor/app", classpath: "com.capacitorjs.plugins.app.AppPlugin" },
  { pkg: "@capacitor/app-launcher", classpath: "com.capacitorjs.plugins.applauncher.AppLauncherPlugin" },
  { pkg: "@capacitor/geolocation", classpath: "com.capacitorjs.plugins.geolocation.GeolocationPlugin" },
  { pkg: "@capacitor/push-notifications", classpath: "com.capacitorjs.plugins.pushnotifications.PushNotificationsPlugin" },
  { pkg: "@capacitor/share", classpath: "com.capacitorjs.plugins.share.SharePlugin" },
];
const PILOT_PLUGIN = {
  pkg: "meteofriul-pilot-weather-prefetch",
  classpath: "com.meteofriul.app.pilot.PilotWeatherPrefetchPlugin",
};
const read = path => readFileSync(join(SOURCE_ROOT, path), "utf8");
const java = name => read(`${PILOT_PACKAGE}/${name}.java`);
const sources = Object.fromEntries(CLASS_NAMES.map(name => [name, java(name)]));
const source = suffix => sources[`PilotWeatherPrefetch${suffix}`];

function filesUnder(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? filesUnder(path) : [path];
  });
}

function numericConstant(text, name) {
  const match = text.match(new RegExp(`\\b${name}\\s*=\\s*([0-9_*\\s]+);`));
  assert.ok(match, `Missing simple bounded numeric constant ${name}`);
  const factors = match[1].replaceAll("_", "").split("*").map(value => Number(value.trim()));
  assert.ok(factors.every(value => Number.isSafeInteger(value) && value > 0));
  return factors.reduce((value, factor) => value * factor, 1);
}

test("structural: all prefetch implementation classes belong only to the localPilot source set", () => {
  const classFiles = new Set(CLASS_NAMES.map(name => `${name}.java`));
  const actual = filesUnder(SOURCE_ROOT)
    .filter(path => classFiles.has(path.split(/[\\/]/).at(-1)))
    .map(path => relative(SOURCE_ROOT, path).replaceAll("\\", "/")).sort();
  assert.deepEqual(actual, CLASS_NAMES.map(name => `${PILOT_PACKAGE}/${name}.java`).sort());
  for (const text of Object.values(sources)) assert.match(text, /^package com\.meteofriul\.app\.pilot;/m);
  const activity = read("main/java/com/meteofriul/app/MainActivity.java");
  assert.doesNotMatch(activity, /PilotWeatherPrefetch/);
  const gradle = readFileSync(join(FRONTEND_ROOT, "android", "app", "build.gradle"), "utf8");
  assert.match(gradle, /applicationIdSuffix '\.localpilot'/);
  assert.doesNotMatch(gradle, /(?:srcDirs|srcDir)\s*(?:=|\()?[^\n]*localPilot/);
});

test("structural: the pilot registry preserves all five generated plugins and adds only weather prefetch", () => {
  const main = JSON.parse(read("main/assets/capacitor.plugins.json"));
  const pilot = JSON.parse(read("localPilot/assets/capacitor.plugins.json"));
  assert.deepEqual(main, GENERATED_PLUGINS);
  assert.deepEqual(pilot, [...GENERATED_PLUGINS, PILOT_PLUGIN]);
  assert.match(source("Plugin"), /@CapacitorPlugin\(name = "PilotWeatherPrefetch"\)/);
  const methods = [...source("Plugin").matchAll(/@PluginMethod\s+public void (\w+)\(/g)].map(match => match[1]);
  assert.deepEqual(methods.sort(), ["clear", "configure", "readObject"]);
});

test("structural: native prefetch remains silent and independent of legacy location and Firebase flows", () => {
  const all = Object.values(sources).join("\n");
  assert.doesNotMatch(all, /import\s+(?:com\.google\.firebase|com\.google\.android\.gms\.location|android\.location|android\.app\.Notification)/);
  assert.doesNotMatch(all, /\b(?:FirebaseApp|FirebaseMessaging|FirebaseFirestore|LocationManager|FusedLocationProviderClient|MeteoBackground\w+|NotificationManager|NotificationCompat|ForegroundInfo)\b/);
  assert.doesNotMatch(all, /\b(?:setForeground|setForegroundAsync|startForeground|startForegroundService|requestPermissions|requestPermissionForAlias|notify)\s*\(/);
  assert.doesNotMatch(all, /\b(?:WebView|JavascriptInterface|evaluateJavascript)\b/);
});

test("structural: one constrained hourly work name is kept and clearing cancels only that work", () => {
  const scheduler = source("Scheduler");
  assert.match(scheduler, new RegExp(`WORK_NAME\\s*=\\s*"${EXPECTED_WORK}"`));
  assert.match(scheduler, /PeriodicWorkRequest\.Builder\(PilotWeatherPrefetchWorker\.class,\s*60,\s*TimeUnit\.MINUTES\)/);
  assert.match(scheduler, /setInitialDelay\(30,\s*TimeUnit\.MINUTES\)/);
  assert.match(scheduler, /setRequiredNetworkType\(NetworkType\.CONNECTED\)/);
  assert.match(scheduler, /setRequiresBatteryNotLow\(true\)/);
  assert.match(scheduler, /setBackoffCriteria\(BackoffPolicy\.EXPONENTIAL,\s*5,\s*TimeUnit\.MINUTES\)/);
  assert.match(scheduler, /enqueueUniquePeriodicWork\(WORK_NAME,\s*ExistingPeriodicWorkPolicy\.KEEP,\s*request\)/);
  assert.match(scheduler, /addTag\(WORK_NAME\)/);
  const all = Object.values(sources).join("\n");
  assert.deepEqual([...all.matchAll(/cancelUniqueWork\(([^)]+)\)/g)].map(match => match[1]), ["WORK_NAME"]);
  assert.doesNotMatch(all, /\b(?:cancelAllWork|cancelAllWorkByTag|cancelWorkById|enqueueUniqueWork|OneTimeWorkRequest)\b/);
  assert.ok(numericConstant(source("Worker"), "MAX_ATTEMPTS") <= 4);
  assert.match(source("Worker"), /getRunAttemptCount\(\)\s*\+\s*1\s*<\s*MAX_ATTEMPTS/);
  assert.match(source("Worker"), /store\.selection\(\)/);
});

test("structural: transport has one fixed pilot HTTPS origin, bounded reads and no redirects or credentials", () => {
  const all = Object.values(sources).join("\n");
  const origins = [...all.matchAll(/"(https?:\/\/[^"\s]+)"/g)].map(match => match[1]);
  assert.deepEqual(origins, [EXPECTED_ORIGIN]);
  const http = source("Http");
  assert.match(http, /new URL\(PilotWeatherPrefetchCore\.BASE_URL\s*\+\s*"\/weather\/v1\/"/);
  assert.match(http, /setInstanceFollowRedirects\(false\)/);
  assert.match(http, /setConnectTimeout\(12_000\)/);
  assert.match(http, /setReadTimeout\(12_000\)/);
  assert.match(http, /setRequestMethod\("GET"\)/);
  assert.match(http, /setRequestProperty\("If-None-Match",\s*etag\)/);
  assert.match(http, /body\.size\(\)\s*\+\s*count\s*>\s*maxBytes/);
  assert.match(http, /finally\s*\{\s*connection\.disconnect\(\)/);
  assert.doesNotMatch(http, /setRequestProperty\("(?:Authorization|Cookie|PRIVATE-TOKEN|X-Firebase-AppCheck)"/i);
  assert.doesNotMatch(http, /\b(?:setHostnameVerifier|setSSLSocketFactory|setDefaultSSLSocketFactory|setDefaultHostnameVerifier)\s*\(/);
});

test("structural: graph and disk bounds are explicit and municipality expansion stays selected-code only", () => {
  const core = source("Core");
  for (const [name, maximum] of [
    ["MAX_METADATA_BYTES", 128 * 1024], ["MAX_MANIFEST_BYTES", 2 * 1024 * 1024],
    ["MAX_PAYLOAD_BYTES", 512 * 1024], ["MAX_FAMILY_BYTES", 6 * 1024 * 1024],
  ]) assert.ok(numericConstant(core, name) <= maximum, `${name} exceeded the staging bound`);
  assert.ok(numericConstant(source("Store"), "MAX_STORED_BYTES") <= 16 * 1024 * 1024);
  assert.match(core, /objects\.size\(\)\s*>\s*5/);
  assert.match(core, /new String\[\]\s*\{\s*ICON,\s*CAMS\s*\}/);
  assert.match(core, /new String\[\]\s*\{\s*"core",\s*"pollen"\s*\}/);
  assert.match(core, /map\(manifest\.get\("objects"\)\)\.get\(selection\.istatCode\)/);
  assert.match(core, /!downloaded\.sha256\.equals\(hash\)/);
  assert.match(core, /downloaded\.bodyBytes\s*!=\s*size/);
  assert.doesNotMatch(core, /manifest\.get\("objects"\)[^;]*\.(?:entrySet|values|keySet)\(/);
});

test("structural: the native port exposes only selected immutable objects matching the requested hash", () => {
  const store = source("Store");
  const readObject = store.slice(store.indexOf("PilotWeatherPrefetchCore.RawObject readObject("), store.indexOf("private static JSONObject json("));
  assert.match(readObject, /validateConfiguration\(baseUrl,\s*istatCode\)/);
  assert.match(readObject, /allowedPath\(provider,\s*path,\s*istatCode,\s*false\)/);
  assert.match(readObject, /validHash\(sha256\)/);
  assert.match(readObject, /snapshot\.objects\.get\(provider\s*\+\s*"\/"\s*\+\s*path\)/);
  assert.match(readObject, /isCurrent\(selected\).*object\.sha256\.equals\(sha256\)/);
  assert.doesNotMatch(readObject, /return\s+snapshot\.pointer/);
});

test("structural: selection/reset and atomic stage publication share a generation lock", () => {
  const store = source("Store");
  assert.match(store, /getSharedPreferences\(NAMESPACE,\s*Context\.MODE_PRIVATE\)/);
  assert.match(store, /current\.generation\s*==\s*selection\.generation/);
  assert.match(store, /value\.getLong\("generation"\)\s*!=\s*selection\.generation/);
  const write = store.slice(store.indexOf("@Override public boolean write("), store.indexOf("PilotWeatherPrefetchCore.RawObject readObject("));
  assert.match(write, /synchronized\s*\(LOCK\)/);
  assert.ok(write.indexOf("if (!isCurrent(selection)) return false") < write.indexOf("destination.startWrite()"));
  assert.match(write, /destination\.finishWrite\(output\)/);
  assert.match(write, /destination\.failWrite\(output\)/);
  const clear = store.slice(store.indexOf("void clear()"), store.indexOf("private void deleteFiles()"));
  assert.match(clear, /synchronized\s*\(LOCK\)/);
  assert.match(clear, /putLong\("generation",\s*nextGeneration\(\)\)/);
  assert.ok(clear.indexOf("nextGeneration()") < clear.indexOf("deleteFiles()"));
  const plugin = source("Plugin");
  assert.ok(plugin.indexOf(".clear();") < plugin.indexOf("PilotWeatherPrefetchScheduler.clear(getContext())"));
});
