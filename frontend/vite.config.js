import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { assertReleaseApiEnvironment } from "./scripts/runtime-api-binding.mjs";
import {
  ANDROID_CLOUD_WEATHER_PILOT_API_BASE,
  BROWSER_CLOUD_WEATHER_PILOT_MODE,
  localWeatherPilotConfig,
  resolveBrowserPilotEnvMode,
} from "./scripts/local-weather-pilot-config.mjs";

const rootDir = fileURLToPath(new URL(".", import.meta.url));
const OFFICIAL_EVENTS_PROXY_TARGET = "https://meteofriul-events-49007668366.europe-west1.run.app";

export default defineConfig(({ command, mode }) => {
  const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8002";
  const pilotEnvMode = resolveBrowserPilotEnvMode(mode);
  const pilotEnv = loadEnv(pilotEnvMode, rootDir, "VITE_LOCAL_WEATHER_PILOT");
  const sharedPilotClientEnv = mode === BROWSER_CLOUD_WEATHER_PILOT_MODE
    ? loadEnv(pilotEnvMode, rootDir, "VITE_")
    : {};
  const sharedPilotClientDefines = Object.fromEntries(
    Object.entries(sharedPilotClientEnv).map(([key, value]) => [
      `import.meta.env.${key}`,
      JSON.stringify(value),
    ]),
  );
  const pilot = localWeatherPilotConfig({
    command, mode, flag: process.env.VITE_LOCAL_WEATHER_PILOT ?? pilotEnv.VITE_LOCAL_WEATHER_PILOT,
    androidBuildMarker: process.env.METEO_ANDROID_LOCAL_PILOT_GUARD_MARKER,
    cloud: process.env.METEO_PILOT_WEATHER_CLOUD === "1",
    community: process.env.METEO_PILOT_COMMUNITY_LOCAL === "1",
    nationalCloud: process.env.METEO_PILOT_NATIONAL_CLOUD === "1",
    stable: process.env.METEO_PILOT_STABLE_FRONTEND === "1",
    testNow: process.env.VITE_LOCAL_WEATHER_PILOT_NOW ?? pilotEnv.VITE_LOCAL_WEATHER_PILOT_NOW,
  });
  const browserPilotMode = ["local-pilot", BROWSER_CLOUD_WEATHER_PILOT_MODE].includes(mode);
  const browserLocalPilot = command === "serve" && browserPilotMode;
  const stableBrowserLocalPilot = browserPilotMode
    && process.env.METEO_PILOT_STABLE_FRONTEND === "1";
  if (stableBrowserLocalPilot && process.env.NODE_ENV !== "development") {
    throw new Error("stable_frontend_requires_development_environment");
  }
  const definitiveAppExperience = pilot.enabled
    || (command === "build" && ["android", "cloudflare"].includes(mode));

  if (command === "build" && ["android", "android-local-pilot", "cloudflare"].includes(mode)) {
    const env = loadEnv(mode, rootDir, "");
    const target = mode === "cloudflare" ? "cloudflare" : "android";
    const expectedApiBase = target === "android"
      ? env.VITE_ANDROID_API_BASE
      : env.VITE_API_BASE;
    assertReleaseApiEnvironment({ env, expectedApiBase, target });
  }

  const browserPilotProxy = {
    ...pilot.server.proxy,
    ...(browserLocalPilot ? {
      "/__local-weather-pilot": {
        ...pilot.server.proxy["/__local-weather-pilot"],
        // Use the existing, automatically refreshed pilot service. An
        // explicit override retains the offline snapshot workflow.
        target: process.env.VITE_LOCAL_WEATHER_PROXY_TARGET || ANDROID_CLOUD_WEATHER_PILOT_API_BASE,
      },
      "/__pilot-events": {
        target: process.env.VITE_LOCAL_EVENTS_PROXY_TARGET || OFFICIAL_EVENTS_PROXY_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/__pilot-events(?=\/|$)/, ""),
      },
    } : {}),
    "/api": {
      target: apiProxyTarget,
      changeOrigin: true,
      ...pilot.apiProxy,
    },
  };

  return {
    define: {
      ...sharedPilotClientDefines,
      ...pilot.define,
      "import.meta.env.VITE_DEFINITIVE_APP_EXPERIENCE": JSON.stringify(
        definitiveAppExperience ? "1" : "0",
      ),
      "import.meta.env.VITE_OFFICIAL_APP_RELEASE": JSON.stringify(
        command === "build" && ["android", "cloudflare"].includes(mode) ? "1" : "0",
      ),
    },
    build: {
      rollupOptions: {
        input: {
          main: resolve(rootDir, "index.html"),
        },
      },
    },
    plugins: [react(), {
      name: "pilot-brand-head",
      transformIndexHtml(html) {
        let transformed = html;
        if (stableBrowserLocalPilot) {
          transformed = transformed.replace(
            "</head>",
            '  <meta name="meteofriul-local-weather-pilot" content="stable-static-v1">\n  </head>',
          );
        }
        if (!definitiveAppExperience || pilot.enabled) return transformed;
        return transformed.replace(
          "</head>",
          '  <meta name="meteofriul-app-experience" content="definitive-v1">\n  </head>',
        );
      },
    }],
    server: {
      ...pilot.server,
      proxy: browserPilotProxy,
    },
    preview: browserLocalPilot ? {
      host: "127.0.0.1",
      port: 5174,
      strictPort: true,
      proxy: browserPilotProxy,
    } : undefined,
  };
});
