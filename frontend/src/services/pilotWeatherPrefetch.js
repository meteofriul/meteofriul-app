import { Capacitor, registerPlugin } from "@capacitor/core";
import { ANDROID_LOOPBACK_ONLY_BUILD } from "./localOnlyBuild";

import { isAndroidCapacitorRuntime } from "./apiConfig";
import { getLocalWeatherPilotTestNow, isLocalWeatherPilot } from "./localWeatherPilot";

export const PILOT_WEATHER_PREFETCH_PLUGIN = "PilotWeatherPrefetch";
export const PILOT_WEATHER_PREFETCH_API_BASE = ANDROID_LOOPBACK_ONLY_BUILD ? "" : "https://meteofriul-weather-49007668366.europe-west1.run.app";
export const PILOT_WEATHER_PREFETCH_READ_TIMEOUT_MS = 500;
const CONFIGURE_TIMEOUT_MS = 1000;
const HASH = /^[a-f0-9]{64}$/;
const PROVIDERS = new Set(["icon2i", "cams_europe", "cams_europe_pollen", "families/cams"]);
const NativePrefetch = registerPlugin(PILOT_WEATHER_PREFETCH_PLUGIN);

function supportedRuntime() {
  return isLocalWeatherPilot()
    && !getLocalWeatherPilotTestNow()
    && isAndroidCapacitorRuntime(Capacitor)
    && Capacitor.isPluginAvailable(PILOT_WEATHER_PREFETCH_PLUGIN);
}

// Native storage is an optional source of bytes, never a weather cache authority.
// A stalled bridge must not delay the ordinary network path indefinitely.
function optionalCall(call, timeoutMs) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(value);
    };
    const timer = setTimeout(() => finish(null), timeoutMs);
    Promise.resolve().then(() => call(() => !settled)).then(finish, () => finish(null));
  });
}

function immutableRequest({ provider, path, sha256 }, istatCode) {
  if (!PROVIDERS.has(provider) || !HASH.test(sha256 || "") || typeof path !== "string") return false;
  if (provider === "families/cams") return /^runs\/\d{8}T\d{6}Z\/release\.json$/.test(path);
  return /^runs\/\d{8}T\d{6}Z\/manifest\.json$/.test(path)
    || new RegExp(`^runs/\\d{8}T\\d{6}Z/municipalities/${istatCode}\\.json$`).test(path);
}

export function createPilotWeatherPrefetchBridge({
  plugin,
  isEnabled = () => false,
  readTimeoutMs = PILOT_WEATHER_PREFETCH_READ_TIMEOUT_MS,
} = {}) {
  let generation = 0;
  let selectedKey = null;
  let configuredKey = null;
  let configuration = Promise.resolve(null);
  const reads = new Map();
  const enabled = () => {
    try { return Boolean(isEnabled() && plugin?.configure && plugin?.readObject); }
    catch { return false; }
  };

  return {
    readerFor({ baseUrl, istatCode } = {}) {
      if (!enabled() || baseUrl !== PILOT_WEATHER_PREFETCH_API_BASE || !/^\d{6}$/.test(istatCode || "")) return null;
      const key = `${baseUrl}|${istatCode}`;
      if (selectedKey !== key || configuredKey !== key) {
        if (selectedKey !== key) {
          generation += 1;
          selectedKey = key;
          reads.clear();
        }
        const configuringGeneration = generation;
        // Serialise selection/clear commands, but skip selections superseded
        // before they reach the bridge. Same-location callers share one setup.
        configuredKey = key;
        configuration = configuration.then(async () => {
          if (configuringGeneration !== generation) return null;
          const result = await optionalCall(() => plugin.configure({ baseUrl, istatCode }), CONFIGURE_TIMEOUT_MS);
          if ((!result || result.available === false) && generation === configuringGeneration) configuredKey = null;
          return result;
        });
      }
      const readerGeneration = generation;
      return async ({ provider, path, sha256, signal } = {}) => {
        if (!enabled() || readerGeneration !== generation || signal?.aborted
          || !immutableRequest({ provider, path, sha256 }, istatCode)) return null;
        // Give native setup and lookup one shared foreground budget.
        const readKey = `${readerGeneration}|${provider}|${path}|${sha256}`;
        let pending = reads.get(readKey);
        if (!pending) {
          const ready = configuration;
          pending = optionalCall(async (stillWaiting) => {
            const status = await ready;
            if (!stillWaiting() || !enabled() || !status || status.available === false || readerGeneration !== generation) return null;
            return plugin.readObject({ baseUrl, istatCode, provider, path, sha256 });
          }, readTimeoutMs).finally(() => {
            if (reads.get(readKey) === pending) reads.delete(readKey);
          });
          reads.set(readKey, pending);
        }
        const value = await pending;
        if (!enabled() || readerGeneration !== generation || signal?.aborted || !value || value.available === false
          || value.baseUrl !== baseUrl || value.provider !== provider || value.path !== path
          || value.sha256 !== sha256 || typeof value.body !== "string" || typeof value.etag !== "string") return null;
        // Hash, size, canonical JSON, schema, provenance and revocations are
        // checked by weatherV1Client. This bridge never writes localStorage.
        return { body: value.body, etag: value.etag };
      };
    },

    clear() {
      if (!enabled() || typeof plugin.clear !== "function") return Promise.resolve(false);
      generation += 1;
      selectedKey = null;
      configuredKey = null;
      reads.clear();
      configuration = configuration.then(() => optionalCall(() => plugin.clear(), CONFIGURE_TIMEOUT_MS));
      return configuration.then(result => Boolean(result && result.available !== false));
    },
  };
}

const bridge = createPilotWeatherPrefetchBridge({ plugin: NativePrefetch, isEnabled: supportedRuntime });

export function getPilotWeatherPrefetchReader(options) {
  return bridge.readerFor(options);
}

export function clearPilotWeatherPrefetch() {
  if (!supportedRuntime()) return Promise.resolve(null);
  return bridge.clear();
}
