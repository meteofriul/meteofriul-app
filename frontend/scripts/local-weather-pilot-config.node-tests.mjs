import test from "node:test";
import assert from "node:assert/strict";
import {
  ANDROID_LOCAL_WEATHER_PILOT_API_BASE,
  ANDROID_LOCAL_WEATHER_NATIONAL_API_BASE,
  ANDROID_LOCAL_WEATHER_PILOT_MODE,
  BROWSER_CLOUD_WEATHER_PILOT_MODE,
  LOCAL_WEATHER_PILOT_REQUEST_HEADER,
  localWeatherPilotConfig,
  resolveBrowserPilotEnvMode,
} from "./local-weather-pilot-config.mjs";

const PROTECTED_MARKER = "a".repeat(64);

test("national cloud browser proxy is explicit, fixed, loopback-only and real-clock", () => {
  const result = localWeatherPilotConfig({ command: "serve", mode: "local-pilot", nationalCloud: true, community: true });
  assert.equal(result.server.host, "127.0.0.1");
  assert.equal(result.server.port, 5174);
  assert.equal(result.server.strictPort, true);
  assert.equal(result.server.proxy["/__local-weather-national"].target, "https://meteofriul-national-weather-49007668366.europe-west1.run.app");
  assert.equal(result.server.proxy["/__local-community"].target, "http://127.0.0.1:8783");
  assert.equal(result.define["import.meta.env.VITE_LOCAL_COMMUNITY_PILOT_API_BASE"], '"/__local-community/api"');
  assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_API_BASE"], '"/__local-weather-national"');
  for (const mode of ["production", "android", "cloudflare", "local-pilot-cloud", ANDROID_LOCAL_WEATHER_PILOT_MODE]) {
    assert.throws(() => localWeatherPilotConfig({ command: "serve", mode, nationalCloud: true }), /explicit_browser_local_pilot/);
  }
  assert.throws(() => localWeatherPilotConfig({ command: "build", mode: "local-pilot", nationalCloud: true }), /explicit_browser_local_pilot/);
  assert.throws(() => localWeatherPilotConfig({ command: "serve", mode: "local-pilot", nationalCloud: true, testNow: "2026-09-04T05:00:00Z" }), /requires_real_clock/);
});

test("community writes need an explicit isolated pilot opt-in", () => {
  const off = localWeatherPilotConfig({ command: "serve", mode: "local-pilot" });
  assert.equal(off.define["import.meta.env.VITE_LOCAL_COMMUNITY_PILOT_ENABLED"], '"0"');
  const local = localWeatherPilotConfig({ command: "serve", mode: "local-pilot", community: true });
  assert.equal(local.define["import.meta.env.VITE_LOCAL_COMMUNITY_PILOT_API_BASE"], '"/__local-community/api"');
  const proxy = local.server.proxy["/__local-community"];
  assert.equal(proxy.target, "http://127.0.0.1:8783");
  assert.equal(proxy.rewrite("/__local-community/api/community/reports"), "/api/community/reports");
  assert.equal(proxy.rewrite("/__local-community-evil/api"), "/__local-community-evil/api");
  for (const mode of ["production", "android", "cloudflare", "local-pilot-cloud"]) {
    assert.throws(() => localWeatherPilotConfig({ command: "serve", mode, community: true }));
  }
  const android = localWeatherPilotConfig({ command: "build", mode: ANDROID_LOCAL_WEATHER_PILOT_MODE, androidBuildMarker: PROTECTED_MARKER, community: true });
  assert.equal(android.define["import.meta.env.VITE_LOCAL_COMMUNITY_PILOT_API_BASE"], '"http://127.0.0.1:8783/api"');
});

test("cloud weather is limited to the protected pilot build", () => {
  assert.throws(() => localWeatherPilotConfig({ command: "build", mode: "android", cloud: true }), /protected_android_pilot/);
  const config = localWeatherPilotConfig({ command: "build", mode: ANDROID_LOCAL_WEATHER_PILOT_MODE, androidBuildMarker: PROTECTED_MARKER, cloud: true });
  assert.equal(config.define["import.meta.env.VITE_LOCAL_WEATHER_PILOT_API_BASE"], '"https://meteofriul-weather-49007668366.europe-west1.run.app"');
  assert.equal(config.define["import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_ENABLED"], '"1"');
  assert.equal(config.define["import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_API_BASE"], '"https://meteofriul-national-weather-49007668366.europe-west1.run.app"');
  const community = localWeatherPilotConfig({ command: "build", mode: ANDROID_LOCAL_WEATHER_PILOT_MODE, androidBuildMarker: PROTECTED_MARKER, cloud: true, community: true });
  assert.equal(community.define["import.meta.env.VITE_LOCAL_COMMUNITY_PILOT_API_BASE"], '"https://meteofriul-community-49007668366.europe-west1.run.app/api"');
  assert.throws(() => localWeatherPilotConfig({ command: "build", mode: ANDROID_LOCAL_WEATHER_PILOT_MODE, androidBuildMarker: PROTECTED_MARKER, cloud: true, testNow: "2026-09-04T05:00:00Z" }), /requires_real_clock/);
});

test("ordinary dev and production keep pilot disabled", () => {
  for (const command of ["serve", "build"]) {
    const result = localWeatherPilotConfig({ command, mode: "production" });
    assert.equal(result.enabled, false);
    assert.deepEqual(result.server, {});
    assert.deepEqual(result.apiProxy, {});
    assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_PILOT"], '"0"');
    assert.equal(result.define["import.meta.env.VITE_ANDROID_LOCAL_WEATHER_PILOT"], '"0"');
    assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_PILOT_API_BASE"], '""');
    assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_PILOT_NOW"], '""');
    assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_ENABLED"], '"0"');
    assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_API_BASE"], '""');
  }
});
test("explicit dev mode is loopback, separate port, exact private prefix only", () => {
  const result = localWeatherPilotConfig({ command: "serve", mode: "local-pilot" });
  assert.equal(result.enabled, true);
  assert.equal(result.server.host, "127.0.0.1");
  assert.equal(result.server.port, 5174);
  assert.equal(result.server.strictPort, true);
  assert.deepEqual(result.apiProxy, {
    headers: { [LOCAL_WEATHER_PILOT_REQUEST_HEADER]: "1" },
  });
  assert.equal(result.define["import.meta.env.VITE_ANDROID_LOCAL_WEATHER_PILOT"], '"0"');
  assert.equal(
    result.define["import.meta.env.VITE_LOCAL_WEATHER_PILOT_API_BASE"],
    '"/__local-weather-pilot"',
  );
  assert.deepEqual(Object.keys(result.server.proxy), [
    "/__local-weather-pilot",
    "/__local-weather-national",
  ]);
  const proxy = result.server.proxy["/__local-weather-pilot"];
  assert.equal(proxy.target, "http://127.0.0.1:8781");
  assert.equal(
    proxy.rewrite("/__local-weather-pilot/weather/v1/icon2i/latest.json"),
    "/weather/v1/icon2i/latest.json",
  );
  assert.equal(proxy.rewrite("/__local-weather-pilot-evil/weather/v1"), "/__local-weather-pilot-evil/weather/v1");
  assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_ENABLED"], '"1"');
  assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_API_BASE"], '"/__local-weather-national"');
  const nationalProxy = result.server.proxy["/__local-weather-national"];
  assert.equal(nationalProxy.target, ANDROID_LOCAL_WEATHER_NATIONAL_API_BASE);
  assert.equal(
    nationalProxy.rewrite("/__local-weather-national/weather/v2/icon2i/resolve.json"),
    "/weather/v2/icon2i/resolve.json",
  );

});
test("stable browser pilot disables HMR without widening the mode", () => {
  const result = localWeatherPilotConfig({
    command: "serve",
    mode: "local-pilot",
    stable: true,
  });
  assert.equal(result.enabled, true);
  assert.equal(result.server.hmr, false);
  assert.throws(() => localWeatherPilotConfig({
    command: "serve",
    mode: "production",
    stable: true,
  }), /stable_frontend_requires_explicit_browser_local_pilot/u);
  const buildResult = localWeatherPilotConfig({
    command: "build",
    mode: "local-pilot",
    stable: true,
  });
  assert.equal(buildResult.enabled, true);
  assert.deepEqual(buildResult.server, {});
  assert.throws(() => localWeatherPilotConfig({
    command: "build",
    mode: "local-pilot",
  }), /local_weather_pilot_is_development_only_no_build/u);
});
test("browser cloud pilot mode remains a development-only loopback bridge", () => {
  assert.equal(resolveBrowserPilotEnvMode(BROWSER_CLOUD_WEATHER_PILOT_MODE), "local-pilot");
  assert.equal(resolveBrowserPilotEnvMode("production"), "production");
  const result = localWeatherPilotConfig({
    command: "serve",
    mode: BROWSER_CLOUD_WEATHER_PILOT_MODE,
  });
  assert.equal(result.enabled, true);
  assert.equal(result.server.host, "127.0.0.1");
  assert.equal(result.server.port, 5174);
  assert.equal(
    result.define["import.meta.env.VITE_LOCAL_WEATHER_PILOT_API_BASE"],
    '"/__local-weather-pilot"',
  );
  assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_ENABLED"], '"0"');
  assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_API_BASE"], '""');
  assert.deepEqual(Object.keys(result.server.proxy), ["/__local-weather-pilot"]);
  assert.throws(() => localWeatherPilotConfig({
    command: "build",
    mode: BROWSER_CLOUD_WEATHER_PILOT_MODE,
  }), /no_build/u);
});
test("protected Android build emits only the loopback data-plane binding", () => {
  const result = localWeatherPilotConfig({
    androidBuildMarker: PROTECTED_MARKER,
    command: "build",
    mode: ANDROID_LOCAL_WEATHER_PILOT_MODE,
    testNow: "2026-09-04T05:00:00Z",
  });
  assert.equal(result.enabled, true);
  assert.deepEqual(result.server, {});
  assert.deepEqual(result.apiProxy, {});
  assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_PILOT"], '"1"');
  assert.equal(result.define["import.meta.env.VITE_ANDROID_LOCAL_WEATHER_PILOT"], '"1"');
  assert.equal(
    result.define["import.meta.env.VITE_LOCAL_WEATHER_PILOT_API_BASE"],
    JSON.stringify(ANDROID_LOCAL_WEATHER_PILOT_API_BASE),
  );
  assert.equal(
    result.define["import.meta.env.VITE_LOCAL_WEATHER_PILOT_NOW"],
    '"2026-09-04T05:00:00Z"',
  );
  assert.equal(result.define["import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_ENABLED"], '"1"');
  assert.equal(
    result.define["import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_API_BASE"],
    JSON.stringify(ANDROID_LOCAL_WEATHER_NATIONAL_API_BASE),
  );
});
test("test clock is canonical and cannot leak outside an explicit pilot", () => {
  assert.throws(() => localWeatherPilotConfig({
    command: "serve", mode: "development", testNow: "2026-09-04T05:00:00Z",
  }), /requires_explicit_pilot_mode/u);
  assert.throws(() => localWeatherPilotConfig({
    command: "serve", mode: "local-pilot", testNow: "2026-09-04 05:00:00",
  }), /canonical_utc_seconds/u);
  assert.throws(() => localWeatherPilotConfig({
    command: "serve", mode: "local-pilot", testNow: "2026-02-30T05:00:00Z",
  }), /canonical_utc_seconds/u);
});
test("all builds reject experimental mode or environment flag", () => {
  for (const mode of ["local-pilot", "production", "android", "cloudflare"]) {
    assert.throws(() => localWeatherPilotConfig({ command: "build", mode, flag: "1" }), /no_build/);
  }
  assert.throws(() => localWeatherPilotConfig({ command: "build", mode: "local-pilot" }), /no_build/);
  assert.throws(() => localWeatherPilotConfig({
    command: "build",
    mode: ANDROID_LOCAL_WEATHER_PILOT_MODE,
  }), /protected_build_script/);
  assert.throws(() => localWeatherPilotConfig({
    androidBuildMarker: "not-a-marker",
    command: "build",
    mode: ANDROID_LOCAL_WEATHER_PILOT_MODE,
  }), /protected_build_script/);
  assert.throws(() => localWeatherPilotConfig({
    androidBuildMarker: PROTECTED_MARKER,
    command: "serve",
    mode: ANDROID_LOCAL_WEATHER_PILOT_MODE,
  }), /protected_build_script/);
  assert.throws(() => localWeatherPilotConfig({ command: "serve", mode: "development", flag: "1" }), /explicit/);
});
