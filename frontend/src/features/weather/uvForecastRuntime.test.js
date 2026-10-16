import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { uvForecast } from "./uvForecast";
import * as apiConfig from "../../services/apiConfig";
import {
  clearUvDocumentCache, readUvDocumentCache, readUvForecastState, subscribeToUvForecast, UV_CACHE_KEY,
  UV_CANDIDATE_CACHE_KEY, UV_FORECAST_URL, UV_REFRESH_INTERVAL_MS, UV_REQUEST_TIMEOUT_MS,
  writeUvDocumentCache,
} from "./uvForecastRuntime";

const HOUR = 3600000;
const RUN = Date.parse("2026-09-06T00:00:00Z");
function fixture(run = RUN) {
  return {
    schema: "pilot-uv-v1", unit: "1", run_at: new Date(run).toISOString(), grid: [[46, 13], [46.7, 13]],
    hours: Array.from({ length: 72 }, (_, index) => ({
      time: new Date(run + index * HOUR).toISOString(), values: index % 24 === 11 ? [5.9, 3] : [0, 0],
    })),
  };
}
function memoryStorage() {
  const entries = new Map();
  return { getItem: key => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value), removeItem: key => entries.delete(key) };
}
function events(extra = {}) {
  const listeners = new Map();
  return {
    ...extra,
    addEventListener: (name, fn) => listeners.set(name, fn),
    removeEventListener: (name, fn) => { if (listeners.get(name) === fn) listeners.delete(name); },
    emit: name => listeners.get(name)?.(),
    listeners,
  };
}
const response = document => ({ ok: true, json: async () => document });
const flush = async () => { for (let index = 0; index < 8; index += 1) await Promise.resolve(); };

describe("pilot UV durable runtime", () => {
  let disposers;
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(RUN + 36 * HOUR);
    disposers = [];
  });
  afterEach(() => {
    disposers.forEach(stop => stop());
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });
  function start(overrides = {}) {
    const changes = [];
    const storage = memoryStorage();
    const windowRef = events();
    const documentRef = events({ visibilityState: "visible" });
    const navigatorRef = { onLine: true };
    const native = { stop: vi.fn() };
    const startNativeResume = vi.fn(() => native);
    const options = { storage, windowRef, documentRef, navigatorRef, startNativeResume, ...overrides };
    const stop = subscribeToUvForecast(state => changes.push(state), options);
    disposers.push(stop);
    return { ...options, stop, changes, native, latest: () => changes.at(-1) };
  }

  function previewEnvironment({ dev = true, mode = "local-pilot", native = false, hostname = "127.0.0.1" } = {}) {
    vi.stubEnv("DEV", dev);
    vi.stubEnv("MODE", mode);
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT", "1");
    vi.stubEnv("VITE_ANDROID_LOCAL_WEATHER_PILOT", native ? "1" : "0");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT_API_BASE", "/__local-weather-pilot");
    vi.stubGlobal("location", { hostname });
    vi.spyOn(apiConfig, "isAndroidCapacitorRuntime").mockReturnValue(native);
  }

  it("loads preview UV through the weather proxy without changing the canonical cache identity", async () => {
    previewEnvironment();
    const document = fixture();
    const runtime = start({ fetchImpl: vi.fn().mockResolvedValue(response(document)) });
    await flush();
    expect(runtime.fetchImpl).toHaveBeenCalledExactlyOnceWith(
      "/__local-weather-pilot/weather/v1/uv/latest.json",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(runtime.latest()).toMatchObject({ document, saved: false, error: null });
    expect(JSON.parse(runtime.storage.getItem(UV_CACHE_KEY)).url).toBe(UV_FORECAST_URL);
    expect(readUvDocumentCache({ storage: runtime.storage })).toEqual(document);
  });

  it.each([
    { dev: false, mode: "android-local-pilot", native: true, hostname: "localhost" },
    { dev: false, mode: "production", hostname: "meteofriul.app" },
    { mode: "development" },
    { hostname: "meteofriul.app" },
  ])("preserves the cloud UV URL outside the guarded browser preview: %j", async (environment) => {
    previewEnvironment(environment);
    const runtime = start({ fetchImpl: vi.fn().mockResolvedValue(response(fixture())) });
    await flush();
    expect(runtime.fetchImpl).toHaveBeenCalledExactlyOnceWith(UV_FORECAST_URL, expect.objectContaining({ cache: "no-store" }));
    expect(runtime.latest().error).toBeNull();
  });

  it("persists the complete regional document and rehydrates it offline after remount", async () => {
    const document = fixture();
    const runtime = start({ fetchImpl: vi.fn().mockResolvedValue(response(document)) });
    await flush();
    expect(runtime.latest()).toMatchObject({ document, saved: false, error: null });
    expect(runtime.fetchImpl).toHaveBeenCalledWith(UV_FORECAST_URL, expect.objectContaining({ cache: "no-store" }));
    runtime.stop();
    const offline = start({ storage: runtime.storage, navigatorRef: { onLine: false }, fetchImpl: vi.fn() });
    expect(offline.fetchImpl).not.toHaveBeenCalled();
    expect(offline.latest()).toMatchObject({ saved: true, error: "offline" });
    expect(uvForecast(offline.latest().document, { latitude: 46, longitude: 13 }, Date.now()).maximum).toBe(5.9);
    expect(uvForecast(offline.latest().document, { latitude: 46.7, longitude: 13 }, Date.now()).maximum).toBe(3);
  });

  it("retains valid data after HTTP failure, malformed JSON or invalid document", async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(response(fixture()))
      .mockResolvedValueOnce({ ok: false })
      .mockResolvedValueOnce({ ok: true, json: async () => { throw new Error("invalid JSON"); } })
      .mockResolvedValueOnce(response({ ...fixture(), hours: [] }));
    const runtime = start({ fetchImpl });
    await flush();
    const cached = runtime.storage.getItem(UV_CACHE_KEY);
    for (let index = 0; index < 3; index += 1) {
      await vi.advanceTimersByTimeAsync(UV_REFRESH_INTERVAL_MS);
      expect(runtime.latest()).toMatchObject({ document: fixture(), saved: true, error: "unavailable" });
      expect(runtime.storage.getItem(UV_CACHE_KEY)).toBe(cached);
    }
  });

  it("times out even if fetch ignores AbortSignal and ignores its late response", async () => {
    let resolveOld;
    const fetchImpl = vi.fn().mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }))
      .mockResolvedValueOnce(response(fixture(RUN + 24 * HOUR)));
    const storage = memoryStorage();
    writeUvDocumentCache(fixture(), { storage });
    const runtime = start({ storage, fetchImpl });
    const signal = fetchImpl.mock.calls[0][1].signal;
    await vi.advanceTimersByTimeAsync(UV_REQUEST_TIMEOUT_MS);
    expect(signal.aborted).toBe(true);
    expect(runtime.latest()).toMatchObject({ document: fixture(), saved: true, error: "timeout" });
    runtime.windowRef.emit("online");
    await flush();
    resolveOld(response(fixture()));
    await flush();
    expect(runtime.latest().document.run_at).toBe(fixture(RUN + 24 * HOUR).run_at);
  });

  it("retains verified saved data offline after source freshness expires", async () => {
    const storage = memoryStorage();
    vi.setSystemTime(RUN + 48 * HOUR - 30000);
    writeUvDocumentCache(fixture(), { storage });
    const runtime = start({ storage, navigatorRef: { onLine: false }, fetchImpl: vi.fn() });
    expect(runtime.latest().document).not.toBeNull();
    await vi.advanceTimersByTimeAsync(60000);
    expect(runtime.latest()).toMatchObject({ document: fixture(), saved: true, error: "offline" });
    expect(readUvDocumentCache({ storage })).toEqual(fixture());
    expect(uvForecast(runtime.latest().document, { latitude: 46, longitude: 13 }, Date.now()))
      .toMatchObject({ currentIsCurrent: true, currentUsable: false, sourceFresh: false });
    expect(runtime.fetchImpl).not.toHaveBeenCalled();
  });

  it("does not downgrade a newer valid run in memory or shared cache", async () => {
    const newer = fixture(RUN + 24 * HOUR);
    const storage = memoryStorage();
    writeUvDocumentCache(newer, { storage });
    const runtime = start({ storage, fetchImpl: vi.fn().mockResolvedValue(response(fixture())) });
    await flush();
    expect(runtime.latest()).toMatchObject({ document: newer, saved: true, error: "older_run" });
    expect(readUvDocumentCache({ storage })).toEqual(newer);
    expect(writeUvDocumentCache(fixture(), { storage })).toBe(false);
  });

  it("refreshes on browser/native resume and online, deduplicates in-flight events, skips hidden polling", async () => {
    let resolve;
    const fetchImpl = vi.fn(() => new Promise(done => { resolve = done; }));
    const runtime = start({ fetchImpl, documentRef: events({ visibilityState: "hidden" }) });
    await vi.advanceTimersByTimeAsync(UV_REFRESH_INTERVAL_MS);
    expect(fetchImpl).not.toHaveBeenCalled();
    runtime.documentRef.visibilityState = "visible";
    runtime.documentRef.emit("visibilitychange");
    runtime.windowRef.emit("pageshow");
    runtime.startNativeResume.mock.calls[0][0].onResume();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    resolve(response(fixture()));
    await flush();
    runtime.navigatorRef.onLine = false;
    runtime.windowRef.emit("offline");
    expect(runtime.latest()).toMatchObject({ saved: true, error: "offline" });
    runtime.navigatorRef.onLine = true;
    runtime.windowRef.emit("online");
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("cleans all browser/native listeners and ignores completion after unmount", async () => {
    let resolve;
    const runtime = start({ fetchImpl: vi.fn(() => new Promise(done => { resolve = done; })) });
    const signal = runtime.fetchImpl.mock.calls[0][1].signal;
    runtime.stop();
    const count = runtime.changes.length;
    resolve(response(fixture()));
    await flush();
    await vi.advanceTimersByTimeAsync(UV_REFRESH_INTERVAL_MS);
    expect(runtime.changes).toHaveLength(count);
    expect(runtime.storage.getItem(UV_CACHE_KEY)).toBeNull();
    expect(signal.aborted).toBe(true);
    expect(runtime.windowRef.listeners.size + runtime.documentRef.listeners.size).toBe(0);
    expect(runtime.native.stop).toHaveBeenCalled();
  });

  it("rejects corrupt, foreign-version/URL and future caches but retains an old verified active", () => {
    const storage = memoryStorage();
    for (const entry of ["{broken", JSON.stringify({ version: 2, url: UV_FORECAST_URL, savedAt: Date.now(), document: fixture() }),
      JSON.stringify({ version: 1, url: "https://other.invalid/", savedAt: Date.now(), document: fixture() }),
      JSON.stringify({ version: 1, url: UV_FORECAST_URL, savedAt: Date.now() + 1, document: fixture() }),
      JSON.stringify({ version: 1, url: UV_FORECAST_URL, savedAt: Date.now(), document: fixture(Date.now() + HOUR) })]) {
      storage.setItem(UV_CACHE_KEY, entry);
      expect(readUvDocumentCache({ storage })).toBeNull();
    }
    const old = fixture(RUN - 24 * HOUR);
    storage.setItem(UV_CACHE_KEY, JSON.stringify({ version: 1, url: UV_FORECAST_URL, savedAt: Date.now(), document: old }));
    expect(readUvDocumentCache({ storage })).toEqual(old);
  });

  it("does not adopt an unsaved network document when storage is blocked", async () => {
    vi.stubGlobal("localStorage", { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("quota"); } });
    expect(readUvForecastState().document).toBeNull();
    expect(writeUvDocumentCache(fixture())).toBe(false);
    const runtime = start({ storage: globalThis.localStorage, fetchImpl: vi.fn().mockResolvedValue(response(fixture())) });
    await flush();
    expect(runtime.latest()).toMatchObject({ document: null, saved: false, error: "storage" });
  });

  it("keeps the active document when candidate staging or activation fails", () => {
    const active = fixture();
    const candidate = fixture(RUN + 24 * HOUR);
    const storage = memoryStorage();
    expect(writeUvDocumentCache(active, { storage })).toBe(true);
    const originalSetItem = storage.setItem;

    storage.setItem = (key, value) => {
      if (key === UV_CANDIDATE_CACHE_KEY) throw new Error("candidate quota");
      originalSetItem(key, value);
    };
    expect(writeUvDocumentCache(candidate, { storage })).toBe(false);
    expect(readUvDocumentCache({ storage })).toEqual(active);

    storage.setItem = (key, value) => {
      if (key === UV_CACHE_KEY) throw new Error("interrupted before activation");
      originalSetItem(key, value);
    };
    expect(writeUvDocumentCache(candidate, { storage })).toBe(false);
    expect(readUvDocumentCache({ storage })).toEqual(active);
    expect(JSON.parse(storage.getItem(UV_CANDIDATE_CACHE_KEY)).document).toEqual(candidate);
  });

  it("rehydrates the previous active offline after an interrupted replacement", async () => {
    const active = fixture();
    const candidate = fixture(RUN + 24 * HOUR);
    const storage = memoryStorage();
    writeUvDocumentCache(active, { storage });
    const originalSetItem = storage.setItem;
    storage.setItem = (key, value) => {
      if (key === UV_CACHE_KEY) throw new Error("app interrupted");
      originalSetItem(key, value);
    };
    expect(writeUvDocumentCache(candidate, { storage })).toBe(false);

    const offline = start({ storage, navigatorRef: { onLine: false }, fetchImpl: vi.fn() });
    expect(offline.latest()).toMatchObject({ document: active, saved: true, error: "offline" });
    expect(offline.changes.every(change => change.document?.run_at === active.run_at)).toBe(true);
  });

  it("keeps the active state visible when persistence of a fetched candidate fails", async () => {
    const active = fixture();
    const candidate = fixture(RUN + 24 * HOUR);
    const storage = memoryStorage();
    writeUvDocumentCache(active, { storage });
    const originalSetItem = storage.setItem;
    storage.setItem = (key, value) => {
      if (key === UV_CANDIDATE_CACHE_KEY) throw new Error("quota");
      originalSetItem(key, value);
    };
    const runtime = start({ storage, fetchImpl: vi.fn().mockResolvedValue(response(candidate)) });
    await flush();

    expect(runtime.latest()).toMatchObject({ document: active, saved: true, error: "storage" });
    expect(runtime.changes.every(change => change.document?.run_at === active.run_at)).toBe(true);
    expect(readUvDocumentCache({ storage })).toEqual(active);
  });

  it("recovers a fully staged first document after interruption without exposing partial JSON", () => {
    const candidate = fixture();
    const storage = memoryStorage();
    const envelope = JSON.stringify({
      version: 1, url: UV_FORECAST_URL, savedAt: Date.now(), document: candidate,
    });
    storage.setItem(UV_CANDIDATE_CACHE_KEY, envelope);

    expect(readUvDocumentCache({ storage })).toEqual(candidate);
    expect(storage.getItem(UV_CACHE_KEY)).toBe(envelope);
    expect(storage.getItem(UV_CANDIDATE_CACHE_KEY)).toBeNull();

    storage.removeItem(UV_CACHE_KEY);
    storage.setItem(UV_CANDIDATE_CACHE_KEY, envelope.slice(0, -1));
    expect(readUvDocumentCache({ storage })).toBeNull();
  });

  it("persists a successful candidate before emitting it and never emits an empty intermediate state", async () => {
    const active = fixture();
    const candidate = fixture(RUN + 24 * HOUR);
    const storage = memoryStorage();
    writeUvDocumentCache(active, { storage });
    const runtime = start({ storage, fetchImpl: vi.fn().mockResolvedValue(response(candidate)) });
    await flush();

    expect(runtime.changes.map(change => change.document?.run_at)).toEqual([active.run_at, candidate.run_at]);
    expect(readUvDocumentCache({ storage })).toEqual(candidate);
    expect(storage.getItem(UV_CANDIDATE_CACHE_KEY)).toBeNull();
    runtime.stop();
    const offline = start({ storage, navigatorRef: { onLine: false }, fetchImpl: vi.fn() });
    expect(offline.latest()).toMatchObject({ document: candidate, saved: true, error: "offline" });
  });

  it("downloads and replaces UV during Rome nighttime without a solar gate", async () => {
    vi.setSystemTime(RUN + 24 * HOUR);
    const active = fixture();
    const candidate = fixture(RUN + 24 * HOUR);
    const storage = memoryStorage();
    writeUvDocumentCache(active, { storage, now: RUN + 24 * HOUR });
    const runtime = start({ storage, fetchImpl: vi.fn().mockResolvedValue(response(candidate)) });
    await flush();

    expect(runtime.fetchImpl).toHaveBeenCalledTimes(1);
    expect(runtime.latest()).toMatchObject({ document: candidate, error: null });
  });
  it("tolerates a SecurityError while accessing the storage property itself", () => {
    vi.stubGlobal("localStorage", null);
    Object.defineProperty(globalThis, "localStorage", { configurable: true, get() { throw new Error("SecurityError"); } });
    expect(readUvForecastState().document).toBeNull();
    expect(writeUvDocumentCache(fixture())).toBe(false);
    expect(clearUvDocumentCache()).toBe(false);
  });
  it("clears only the UV document and tolerates blocked or missing storage", () => {
    const storage = memoryStorage();
    writeUvDocumentCache(fixture(), { storage });
    storage.setItem(UV_CANDIDATE_CACHE_KEY, "unfinished");
    storage.setItem("language", "fur");
    storage.setItem("other-weather-cache", "keep");
    expect(clearUvDocumentCache({ storage })).toBe(true);
    expect(readUvDocumentCache({ storage })).toBeNull();
    expect(storage.getItem(UV_CANDIDATE_CACHE_KEY)).toBeNull();
    expect(storage.getItem("language")).toBe("fur");
    expect(storage.getItem("other-weather-cache")).toBe("keep");
    expect(clearUvDocumentCache({ storage: null })).toBe(false);
    expect(clearUvDocumentCache({ storage: {} })).toBe(false);
    expect(clearUvDocumentCache({ storage: { removeItem() { throw new Error("blocked"); } } })).toBe(false);
  });
});
