// Explicit local bridge. No model files are imported into the Web bundle.
export const LOCAL_WEATHER_PILOT_REQUEST_HEADER = "X-Meteo-Friul-Local-Weather-Pilot";
export const ANDROID_LOCAL_WEATHER_PILOT_MODE = "android-local-pilot";
export const BROWSER_CLOUD_WEATHER_PILOT_MODE = "local-pilot-cloud";
export const ANDROID_LOCAL_WEATHER_PILOT_API_BASE = "http://127.0.0.1:8781";
export const ANDROID_CLOUD_WEATHER_PILOT_API_BASE = "https://meteofriul-weather-49007668366.europe-west1.run.app";
export const ANDROID_LOCAL_WEATHER_NATIONAL_API_BASE = "http://127.0.0.1:8782";
export const ANDROID_CLOUD_WEATHER_NATIONAL_API_BASE = "https://meteofriul-national-weather-49007668366.europe-west1.run.app";
export const LOCAL_COMMUNITY_PILOT_API_BASE = "http://127.0.0.1:8783/api";
export const CLOUD_COMMUNITY_PILOT_API_BASE = "https://meteofriul-community-49007668366.europe-west1.run.app/api";
const ANDROID_LOCAL_WEATHER_PILOT_MARKER = /^[0-9a-f]{64}$/u;
const CANONICAL_UTC_SECONDS = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/u;

export function resolveBrowserPilotEnvMode(mode) {
  return mode === BROWSER_CLOUD_WEATHER_PILOT_MODE ? "local-pilot" : mode;
}

function normalizePilotTestNow(value) {
  const candidate = String(value || "").trim();
  if (!candidate) return "";
  const milliseconds = Date.parse(candidate);
  if (
    !CANONICAL_UTC_SECONDS.test(candidate)
    || !Number.isFinite(milliseconds)
    || new Date(milliseconds).toISOString().replace(".000Z", "Z") !== candidate
  ) {
    throw new Error("local_weather_pilot_test_now_must_be_canonical_utc_seconds");
  }
  return candidate;
}

export function localWeatherPilotConfig({
  command,
  mode,
  flag,
  androidBuildMarker,
  testNow,
  cloud = false,
  community = false,
  eventsLocal = false,
  nationalCloud = false,
  stable = false,
} = {}) {
  const requestedDev = ["local-pilot", BROWSER_CLOUD_WEATHER_PILOT_MODE].includes(mode);
  const requestedAndroid = mode === ANDROID_LOCAL_WEATHER_PILOT_MODE;
  if (eventsLocal && (!requestedAndroid || !community || cloud)) {
    throw new Error("local_events_requires_protected_local_community_android_build");
  }
  const stableBuild = stable && requestedDev && command === "build";
  if (cloud && !requestedAndroid) throw new Error("cloud_weather_requires_protected_android_pilot");
  if (nationalCloud && ((command !== "serve" && !stableBuild) || mode !== "local-pilot")) {
    throw new Error("national_cloud_requires_explicit_browser_local_pilot");
  }
  if (stable && (!requestedDev || !["build", "serve"].includes(command))) {
    throw new Error("stable_frontend_requires_explicit_browser_local_pilot");
  }
  const flagged = flag != null && !["", "0", "false"].includes(String(flag).toLowerCase());

  if (requestedAndroid) {
    if (
      command !== "build"
      || !ANDROID_LOCAL_WEATHER_PILOT_MARKER.test(String(androidBuildMarker || ""))
    ) {
      throw new Error("android_local_weather_pilot_requires_protected_build_script");
    }
  } else if (command !== "serve" && !stableBuild && (requestedDev || flagged)) {
    throw new Error("local_weather_pilot_is_development_only_no_build");
  }
  if (requestedDev && command !== "serve" && !stableBuild) {
    throw new Error("local_weather_pilot_is_development_only_no_build");
  }
  if (flagged && !requestedDev && !requestedAndroid) {
    throw new Error("local_weather_pilot_requires_explicit_local_pilot_mode");
  }

  const enabled = (requestedDev && (command === "serve" || stableBuild)) || requestedAndroid;
  // The explicit browser bridge changes only its server-side proxy destination.
  // The legacy browser cloud bridge and ordinary/release builds are unchanged.
  const nationalEnabled = enabled
    && mode !== BROWSER_CLOUD_WEATHER_PILOT_MODE;
  if (community && !nationalEnabled) throw new Error("local_community_requires_local_pilot");
  const communityEnabled = community && nationalEnabled;
  const normalizedTestNow = normalizePilotTestNow(testNow);
  if ((cloud || nationalCloud) && normalizedTestNow) throw new Error("cloud_pilot_requires_real_clock");
  if (normalizedTestNow && !enabled) {
    throw new Error("local_weather_pilot_test_now_requires_explicit_pilot_mode");
  }
  const runtimeApiBase = requestedAndroid
    ? (cloud ? ANDROID_CLOUD_WEATHER_PILOT_API_BASE : ANDROID_LOCAL_WEATHER_PILOT_API_BASE)
    : requestedDev
      ? "/__local-weather-pilot"
      : "";

  return {
    enabled,
    define: {
      "import.meta.env.VITE_LOCAL_EVENTS_API_BASE": JSON.stringify(eventsLocal ? "http://127.0.0.1:8784/api" : ""),
      "import.meta.env.VITE_ANDROID_LOCAL_WEATHER_PILOT": JSON.stringify(requestedAndroid ? "1" : "0"),
      "import.meta.env.VITE_LOCAL_WEATHER_PILOT": JSON.stringify(enabled ? "1" : "0"),
      "import.meta.env.VITE_LOCAL_WEATHER_PILOT_API_BASE": JSON.stringify(runtimeApiBase),
      "import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_ENABLED": JSON.stringify(nationalEnabled ? "1" : "0"),
      "import.meta.env.VITE_LOCAL_WEATHER_NATIONAL_API_BASE": JSON.stringify(
        nationalEnabled
          ? requestedAndroid
            ? cloud ? ANDROID_CLOUD_WEATHER_NATIONAL_API_BASE : ANDROID_LOCAL_WEATHER_NATIONAL_API_BASE
            : "/__local-weather-national"
          : "",
      ),
      "import.meta.env.VITE_LOCAL_WEATHER_PILOT_NOW": JSON.stringify(normalizedTestNow),
      "import.meta.env.VITE_LOCAL_COMMUNITY_PILOT_ENABLED": JSON.stringify(communityEnabled ? "1" : "0"),
      "import.meta.env.VITE_LOCAL_COMMUNITY_PILOT_API_BASE": JSON.stringify(
        communityEnabled ? requestedAndroid
          ? cloud ? CLOUD_COMMUNITY_PILOT_API_BASE : LOCAL_COMMUNITY_PILOT_API_BASE
          : "/__local-community/api" : "",
      ),
    },
    apiProxy: requestedDev ? {
      headers: { [LOCAL_WEATHER_PILOT_REQUEST_HEADER]: "1" },
    } : {},
    server: requestedDev && command === "serve" ? {
      host: "127.0.0.1", port: 5174, strictPort: true,
      ...(stable ? { hmr: false } : {}),
      proxy: {
        "/__local-weather-pilot": {
          target: "http://127.0.0.1:8781",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/__local-weather-pilot(?=\/|$)/, ""),
        },
        ...(communityEnabled ? {
          "/__local-community": {
            target: "http://127.0.0.1:8783",
            changeOrigin: true,
            rewrite: (path) => path.replace(/^\/__local-community(?=\/|$)/, ""),
          },
        } : {}),
        ...(nationalEnabled ? {
          "/__local-weather-national": {
            target: nationalCloud ? ANDROID_CLOUD_WEATHER_NATIONAL_API_BASE : ANDROID_LOCAL_WEATHER_NATIONAL_API_BASE,
            changeOrigin: true,
            rewrite: (path) => path.replace(/^\/__local-weather-national(?=\/|$)/, ""),
          },
        } : {}),
      },
    } : {},
  };
}
