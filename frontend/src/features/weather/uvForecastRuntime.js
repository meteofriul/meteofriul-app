import { startCapacitorAppResumeRuntime } from "../../services/capacitorAppResume";
import { getLocalWeatherPilotApiBase, isLocalWeatherPilot } from "../../services/localWeatherPilot";
import { ANDROID_LOOPBACK_ONLY_BUILD } from "../../services/localOnlyBuild";
import { isValidUvDocument, isVerifiedUvDocument } from "./uvForecast";

export const UV_FORECAST_URL = ANDROID_LOOPBACK_ONLY_BUILD ? "" : "https://meteofriul-weather-49007668366.europe-west1.run.app/weather/v1/uv/latest.json";
export const UV_CACHE_KEY = "meteofriul:uv:v1";
export const UV_CANDIDATE_CACHE_KEY = `${UV_CACHE_KEY}:candidate`;
export const UV_REFRESH_INTERVAL_MS = 15 * 60 * 1000;
export const UV_REQUEST_TIMEOUT_MS = 10000;

function safeStorage() {
  try { return globalThis.localStorage ?? null; } catch { return null; }
}

function parseCacheEntry(raw, now) {
  try {
    const entry = JSON.parse(raw ?? "null");
    const run = Date.parse(entry?.document?.run_at);
    return entry?.version === 1 && entry.url === UV_FORECAST_URL
      && Number.isFinite(entry.savedAt) && entry.savedAt <= now
      && Number.isFinite(run) && run <= entry.savedAt
      && isVerifiedUvDocument(entry.document) ? entry : null;
  } catch { return null; }
}

function readCacheEntry(storage, key, now) {
  try { return parseCacheEntry(storage?.getItem(key), now); } catch { return null; }
}

export function readUvDocumentCache({ storage = safeStorage(), now = Date.now() } = {}) {
  if (!Number.isFinite(now)) return null;
  const active = readCacheEntry(storage, UV_CACHE_KEY, now);
  if (active) return active.document;

  // A fully written candidate can be recovered only when no active document
  // exists. If an older active exists, an interrupted replacement keeps it.
  const candidate = readCacheEntry(storage, UV_CANDIDATE_CACHE_KEY, now);
  if (!candidate) return null;
  const serialized = JSON.stringify(candidate);
  try {
    storage?.setItem?.(UV_CACHE_KEY, serialized);
    if (storage?.getItem?.(UV_CACHE_KEY) !== serialized) return null;
    try { storage?.removeItem?.(UV_CANDIDATE_CACHE_KEY); } catch { /* best-effort journal cleanup */ }
    return candidate.document;
  } catch { return null; }
}

export function writeUvDocumentCache(document, { storage = safeStorage(), now = Date.now() } = {}) {
  if (!isValidUvDocument(document, now)) return false;
  const previous = readUvDocumentCache({ storage, now });
  if (previous && Date.parse(previous.run_at) > Date.parse(document.run_at)) return false;
  if (!storage?.setItem || !storage?.getItem) return false;
  const serialized = JSON.stringify({ version: 1, url: UV_FORECAST_URL, savedAt: now, document });
  try {
    storage.setItem(UV_CANDIDATE_CACHE_KEY, serialized);
    if (storage.getItem(UV_CANDIDATE_CACHE_KEY) !== serialized) return false;

    // Web Storage replaces one key atomically. The verified candidate therefore
    // becomes active in a single operation: interruption leaves either version,
    // never a partially serialized document.
    storage.setItem(UV_CACHE_KEY, serialized);
    if (storage.getItem(UV_CACHE_KEY) !== serialized) return false;
    try { storage.removeItem?.(UV_CANDIDATE_CACHE_KEY); } catch { /* active is already durable */ }
    return true;
  } catch { return false; }
}

export function clearUvDocumentCache({ storage = safeStorage() } = {}) {
  try {
    if (!storage?.removeItem) return false;
    storage.removeItem(UV_CACHE_KEY);
    storage.removeItem(UV_CANDIDATE_CACHE_KEY);
    return true;
  } catch { return false; }
}

export function readUvForecastState(options = {}) {
  const now = options.now ?? Date.now();
  const document = readUvDocumentCache({ ...options, now });
  return { document, now, saved: Boolean(document), error: null };
}

// The regional document is shared by every location. Selection remains local.
// Source freshness controls candidate adoption and presentation metadata; it
// does not erase a structurally verified active series.
export function subscribeToUvForecast(onChange, {
  fetchImpl = globalThis.fetch,
  storage = safeStorage(),
  now = Date.now,
  windowRef = globalThis.window,
  documentRef = globalThis.document,
  navigatorRef = globalThis.navigator,
  timerApi = globalThis,
  startNativeResume = startCapacitorAppResumeRuntime,
} = {}) {
  let state = readUvForecastState({ storage, now: now() });
  let stopped = false;
  let pending = null;
  let lastSuccess = Number.NEGATIVE_INFINITY;

  const emit = (changes = {}) => {
    if (stopped) return;
    const time = now();
    state = { ...state, ...changes, now: time };
    if (!isVerifiedUvDocument(state.document) || Date.parse(state.document.run_at) > time) {
      state = { ...state, document: null, saved: false };
    }
    onChange(state);
  };
  const finish = (request) => {
    timerApi.clearTimeout(request.timeout);
    if (pending === request) pending = null;
  };
  const fail = (request, reason) => {
    if (stopped || pending !== request) return;
    finish(request);
    request.controller.abort();
    emit({ saved: Boolean(state.document), error: reason });
  };
  const refresh = async () => {
    emit(); // Advance the selected sample without making cache lifetime depend on the network.
    if (navigatorRef?.onLine === false) {
      emit({ saved: Boolean(state.document), error: "offline" });
      return;
    }
    if (stopped || pending
        || documentRef?.visibilityState === "hidden"
        || now() - lastSuccess < UV_REFRESH_INTERVAL_MS) return;
    const request = { controller: new AbortController(), timeout: null };
    pending = request;
    request.timeout = timerApi.setTimeout(() => fail(request, "timeout"), UV_REQUEST_TIMEOUT_MS);
    try {
      // The guarded PC-connected TEST uses local UV too; public builds keep
      // their canonical endpoint and cache identity.
      const requestUrl = (import.meta.env.DEV === true || ANDROID_LOOPBACK_ONLY_BUILD) && isLocalWeatherPilot()
        ? `${getLocalWeatherPilotApiBase()}/weather/v1/uv/latest.json`
        : UV_FORECAST_URL;
      if (!requestUrl) throw new Error("local_weather_runtime_required");
      const response = await fetchImpl(requestUrl, { signal: request.controller.signal, cache: "no-store" });
      if (!response?.ok) throw new Error("unavailable");
      const document = await response.json();
      if (stopped || pending !== request) return;
      const time = now();
      if (!isValidUvDocument(document, time)) throw new Error("invalid");
      const saved = readUvDocumentCache({ storage, now: time });
      const previous = [state.document, saved].filter(value => isVerifiedUvDocument(value)
          && Date.parse(value.run_at) <= time)
        .sort((a, b) => Date.parse(b.run_at) - Date.parse(a.run_at))[0];
      if (previous && Date.parse(previous.run_at) > Date.parse(document.run_at)) {
        lastSuccess = time;
        emit({ document: previous, saved: true, error: "older_run" });
      } else {
        const persisted = writeUvDocumentCache(document, { storage, now: time });
        if (persisted) {
          lastSuccess = time;
          emit({ document, saved: false, error: null });
        } else {
          emit({ document: previous ?? null, saved: Boolean(previous), error: "storage" });
        }
      }
      finish(request);
    } catch {
      fail(request, "unavailable");
    }
  };
  const resume = () => { void refresh(); };
  const reconnect = () => { lastSuccess = Number.NEGATIVE_INFINITY; resume(); };
  const interval = timerApi.setInterval(resume, UV_REFRESH_INTERVAL_MS);
  const clock = timerApi.setInterval(() => emit(), 60000);
  windowRef?.addEventListener("online", reconnect);
  windowRef?.addEventListener("offline", resume);
  windowRef?.addEventListener("pageshow", resume);
  documentRef?.addEventListener("visibilitychange", resume);
  const nativeResume = startNativeResume({ onResume: resume, foregroundCheckIntervalMs: 0 });
  resume();

  return () => {
    stopped = true;
    if (pending) {
      pending.controller.abort();
      finish(pending);
    }
    timerApi.clearInterval(interval);
    timerApi.clearInterval(clock);
    windowRef?.removeEventListener("online", reconnect);
    windowRef?.removeEventListener("offline", resume);
    windowRef?.removeEventListener("pageshow", resume);
    documentRef?.removeEventListener("visibilitychange", resume);
    nativeResume?.stop();
  };
}
