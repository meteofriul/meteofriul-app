import { afterEach, expect, it, vi } from "vitest";
afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });
it("removes public fallback endpoints from the Android loopback TEST and rejects an invalid runtime", async () => {
  vi.stubEnv("MODE", "android-local-pilot");
  vi.stubEnv("VITE_LOCAL_WEATHER_PILOT_API_BASE", "http://127.0.0.1:8781");
  vi.resetModules();
  const community = await import("./localCommunityPilot");
  const weather = await import("./weatherProviderRuntime");
  const national = await import("./localWeatherPilot");
  const prefetch = await import("./pilotWeatherPrefetch");
  const uv = await import("../features/weather/uvForecastRuntime");
  expect(community.PRODUCTION_COMMUNITY_API_BASE).toBe("");
  expect(weather.PRODUCTION_WEATHER_V1_BASE_URL).toBe("");
  expect(national.PRODUCTION_NATIONAL_WEATHER_API_BASE).toBe("");
  expect(prefetch.PILOT_WEATHER_PREFETCH_API_BASE).toBe("");
  expect(uv.UV_FORECAST_URL).toBe("");
  expect(() => community.getLocalCommunityPilotApiBase()).toThrow("local_community_runtime_required");
});
it.each(["android", "cloudflare", "android-local-pilot"])("preserves the public endpoints in %s with cloud services", async (mode) => {
  vi.stubEnv("MODE", mode);
  vi.stubEnv("VITE_LOCAL_WEATHER_PILOT_API_BASE", "https://meteofriul-weather-49007668366.europe-west1.run.app");
  vi.resetModules();
  const { PRODUCTION_COMMUNITY_API_BASE } = await import("./localCommunityPilot");
  expect(PRODUCTION_COMMUNITY_API_BASE).toBe("https://meteofriul-community-49007668366.europe-west1.run.app/api");
});
