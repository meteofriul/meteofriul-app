import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchLocalWeatherV1Bootstrap,
  LOCAL_WEATHER_V1_CAMS_TIMEOUT_MS,
} from "./localWeatherV1Adapter";
import {
  LOCAL_WEATHER_V1_VERIFY_WINDOW_MS,
} from "./localWeatherV1Runtime";
import { runCapacitorResumeSequence, startCapacitorAppResumeRuntime } from "./capacitorAppResume";
import { shouldRunRuntimeRefresh } from "../domain/runtime/runtimeRefreshPolicy";

// Explicit diagnostic integration: real adapter, bundle retention and resume runtime;
// only provider I/O and the clock are injected. This does not mount App.jsx
// and does not exercise the raw HTTP contract validator or a live endpoint.
import { harness, MINUTE, START, RUN_A, RUN_B } from "./camsRecoveryTestFixtures";

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(START); });
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); });

describe("CAMS recovery diagnostic with controlled time", () => {
  it("keeps unavailable for ordinary reads without renewing its timestamp, then fetches at ten minutes", async () => {
    const h = harness();
    const initial = await h.fetch();
    expect(initial.current.source.cams.status).toBe("unavailable");
    expect(initial.current.pollen_data.values).toEqual({});
    expect(h.saved().verifiedAt).toBe(START);
    h.publish();
    for (const elapsed of [MINUTE, 5 * MINUTE, LOCAL_WEATHER_V1_VERIFY_WINDOW_MS - 1]) {
      vi.setSystemTime(START + elapsed);
      expect((await h.fetch()).current.source.cams.status).toBe("unavailable");
      expect(h.bundleFetcher).toHaveBeenCalledTimes(1);
      expect(h.saved().verifiedAt).toBe(START);
    }
    vi.setSystemTime(START + LOCAL_WEATHER_V1_VERIFY_WINDOW_MS);
    const recovered = await h.fetch();
    expect(h.bundleFetcher).toHaveBeenCalledTimes(2);
    expect(h.bundleFetcher.mock.calls.every(([, options]) => options.force === false)).toBe(true);
    expect(recovered.current.source.cams.status).toBe("available");
    expect(recovered.current.data_quality.cams_run_utc).toBe(RUN_B);
    expect(recovered.current.temperature).toBe(initial.current.temperature);
    expect(h.saved().verifiedAt).toBe(START + LOCAL_WEATHER_V1_VERIFY_WINDOW_MS);
  });

  it("expiry itself starts no request; an ordinary request after expiry recovers without force", async () => {
    const h = harness();
    await h.fetch();
    h.publish();
    await vi.advanceTimersByTimeAsync(LOCAL_WEATHER_V1_VERIFY_WINDOW_MS + MINUTE);
    expect(h.bundleFetcher).toHaveBeenCalledTimes(1);
    expect(h.saved().bundle.current.source.cams.status).toBe("unavailable");
    expect((await h.fetch()).current.source.cams.status).toBe("available");
    expect(h.bundleFetcher).toHaveBeenCalledTimes(2);
    expect(h.bundleFetcher.mock.lastCall[1].force).toBe(false);
  });

  it.each([[5650, false], [25000, true]])("a %i-ms response completes within the finite budget or is ignored after abort", async (latency, timesOut) => {
    const h = harness({ available: true });
    const originalFactory = h.clientFactory.getMockImplementation();
    const serverReply = vi.fn();
    h.clientFactory.mockImplementationOnce(options => {
      const clients = originalFactory(options);
      const originalLatest = clients.camsPollen.fetchLatest.getMockImplementation();
      clients.camsPollen.fetchLatest.mockImplementationOnce(signal => new Promise((resolve, reject) => {
        // The server can finish later even though the frontend has aborted.
        setTimeout(async () => { serverReply(); resolve(await originalLatest()); }, latency);
        signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })), { once: true });
      }));
      return clients;
    });
    const update = vi.fn();
    const pending = await h.fetch({ deferCams: true, onCamsUpdate: update });
    expect(pending.current.source.cams.status).toBe("pending");
    expect(LOCAL_WEATHER_V1_CAMS_TIMEOUT_MS).toBe(20000);
    await vi.advanceTimersByTimeAsync(4001);
    expect(update).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(latency - 4000);
    expect(serverReply).toHaveBeenCalledTimes(1);
    expect(update).toHaveBeenCalledTimes(1);
    expect(h.observed[0].camsPollen.fetchManifest).toHaveBeenCalledTimes(timesOut ? 0 : 1);
    expect(update.mock.lastCall[0].current.source.cams.status).toBe(timesOut ? "unavailable" : "available");
    if (timesOut) expect(update.mock.lastCall[0].current.source.cams.diagnostic.code).toBe("CAMS_TIMEOUT");
    else expect(update.mock.lastCall[0].current.data_quality.cams_run_utc).toBe(RUN_A);
    expect(h.bundleFetcher).toHaveBeenCalledTimes(1);
  });

  it("an App-gated ten-minute opportunity recovers CAMS even four seconds before the ICON verification window ends", async () => {
    const h = harness();
    // The separate timeout test proves terminal verification happens after
    // the request starts. Here inject that completion time and use the real
    // gate with the cadence/minInterval wired by App.jsx (App is not mounted).
    vi.setSystemTime(START + 4000);
    await h.fetch();
    h.publish();
    let lastRefreshAt = START;
    async function normalOpportunity() {
      if (!shouldRunRuntimeRefresh({
        now: Date.now(), lastRefreshAt, minIntervalMs: 10 * MINUTE,
        visibilityState: "visible",
      })) return { status: "skipped" };
      lastRefreshAt = Date.now();
      return { status: "settled", bundle: await h.fetch({ retryUnavailableCams: true }) };
    }
    vi.setSystemTime(START + 10 * MINUTE);
    expect(h.saved().camsVerifiedAt).toBeNull();
    expect((await normalOpportunity()).bundle.current.data_quality.cams_run_utc).toBe(RUN_B);
    expect(h.bundleFetcher).toHaveBeenCalledTimes(2);
    expect(h.observed[1].icon2i.fetchLatest).not.toHaveBeenCalled();
    expect(h.observed[1].icon2i.fetchManifest).not.toHaveBeenCalled();
    expect(h.observed[1].icon2i.fetchMunicipality).not.toHaveBeenCalled();
    expect(h.saved().verifiedAt).toBe(START + 4000);
    expect(h.saved().camsVerifiedAt).toBe(START + 10 * MINUTE);
    // The first existing opportunity already recovered; coincident events
    // still respect the App gate and must not multiply requests.
    vi.setSystemTime(START + 10 * MINUTE + 4000);
    expect(await normalOpportunity()).toEqual({ status: "skipped" });
    expect(h.bundleFetcher).toHaveBeenCalledTimes(2);
    expect(h.bundleFetcher.mock.lastCall[1].force).toBe(false);
  });

  it.each([
    ["force", { force: true }, true],
    ["verification-window bypass", { verifyWindowMs: 0 }, false],
  ])("recovers before expiry with %s and forwards its actual force value", async (_label, extra, expectedForce) => {
    const h = harness();
    await h.fetch();
    h.publish();
    vi.setSystemTime(START + MINUTE);
    expect((await h.fetch(extra)).current.source.cams.status).toBe("available");
    expect(h.bundleFetcher).toHaveBeenCalledTimes(2);
    expect(h.clientFactory.mock.lastCall[0].force).toBe(expectedForce);
  });

  it("a network error preserves usable ICON and CAMS and does not postpone the next ordinary retry", async () => {
    const h = harness({ available: true });
    const usable = await h.fetch();
    h.state.offline = true;
    vi.setSystemTime(START + LOCAL_WEATHER_V1_VERIFY_WINDOW_MS);
    const fallback = await h.fetch();
    expect(fallback.current.cache.runtime_fallback).toBe(true);
    expect(fallback.current.source.cams.status).toBe("available");
    expect(fallback.current.temperature).toBe(usable.current.temperature);
    expect(fallback.current.pollen_data.values).toEqual(usable.current.pollen_data.values);
    expect(h.saved().verifiedAt).toBe(START);
    h.state.offline = false;
    h.publish();
    vi.setSystemTime(START + LOCAL_WEATHER_V1_VERIFY_WINDOW_MS + 1);
    const recovered = await h.fetch();
    expect(h.bundleFetcher).toHaveBeenCalledTimes(3);
    expect(recovered.current.data_quality.cams_run_utc).toBe(RUN_B);
    expect(recovered.current.cache.runtime_fallback).not.toBe(true);
  });

  it("a CAMS-only failure cannot replace still usable pollen by unavailable", async () => {
    const h = harness({ available: true });
    const usable = await h.fetch();
    h.state.available = false;
    vi.setSystemTime(START + MINUTE);
    const retained = await h.fetch({ force: true });
    expect(h.bundleFetcher).toHaveBeenCalledTimes(2);
    expect(retained.current.source.cams.status).toBe("available");
    expect(retained.current.pollen_data).toEqual(usable.current.pollen_data);
  });

  it("rejecting an older in-flight response must preserve the newer verified bundle", async () => {
    const h = harness({ available: true });
    let releaseOld;
    const oldGate = new Promise(resolve => { releaseOld = resolve; });
    let oldBuilt;
    const oldReady = new Promise(resolve => { oldBuilt = resolve; });
    h.bundleFetcher.mockImplementationOnce(async (location, options) => {
      const older = await fetchLocalWeatherV1Bootstrap(location, { ...options, clientFactory: h.clientFactory });
      oldBuilt();
      await oldGate;
      return older;
    });
    const oldRequest = h.fetch({ force: true });
    await oldReady;
    h.publish();
    const newer = await h.fetch();
    expect(newer.current.data_quality.cams_run_utc).toBe(RUN_B);
    releaseOld();
    await expect(oldRequest).rejects.toMatchObject({ code: "CAMS_FAMILY_REGRESSION" });
    // Rejecting A is correct. Deleting already-verified B because A arrived
    // late is a distinct violation; deliberately keep this assertion strict.
    expect(h.saved()).toMatchObject({ bundle: { current: { data_quality: { cams_run_utc: RUN_B } } } });
  });

  it("a late deferred CAMS error cannot overwrite the newer successful supplement", async () => {
    const h = harness({ available: true });
    let rejectOld;
    const originalFactory = h.clientFactory.getMockImplementation();
    h.clientFactory.mockImplementationOnce(options => {
      const clients = originalFactory(options);
      clients.camsPollen.fetchLatest.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectOld = reject; }));
      return clients;
    });
    const oldUpdates = vi.fn();
    const newUpdates = vi.fn();
    const pending = await h.fetch({ deferCams: true, onCamsUpdate: oldUpdates });
    expect(pending.current.source.cams.status).toBe("pending");
    h.publish();
    await h.fetch({ force: true, deferCams: true, onCamsUpdate: newUpdates });
    await vi.advanceTimersByTimeAsync(0);
    expect(newUpdates.mock.lastCall[0].current.data_quality.cams_run_utc).toBe(RUN_B);
    rejectOld(Object.assign(new Error("late network error"), { code: "TRANSPORT_FAILURE" }));
    await vi.advanceTimersByTimeAsync(0);
    expect(oldUpdates.mock.lastCall[0].current.data_quality.cams_run_utc).toBe(RUN_B);
    expect(h.saved().bundle.current.data_quality.cams_run_utc).toBe(RUN_B);
  });

  it("unavailable has no pollen values, whereas valid zeros remain six measured model zeros", async () => {
    const h = harness();
    const unavailable = await h.fetch();
    expect(unavailable.current.pollen_data).toMatchObject({ status: "unavailable", values: {}, level: null });
    h.publish();
    const zeros = await h.fetch({ force: true });
    expect(zeros.current.pollen_data.status).toBe("experimental_model_snapshot");
    expect(Object.keys(zeros.current.pollen_data.values)).toHaveLength(6);
    expect(Object.values(zeros.current.pollen_data.values)).toEqual([0, 0, 0, 0, 0, 0]);
    expect(zeros.current.pollen_data.level).toBeNull();
  });

  it("Android resume after the pilot gate re-enters the real runtime without a manual refresh", async () => {
    const h = harness();
    await h.fetch();
    h.publish();
    let listener;
    let lastRefreshAt = START;
    let visible = true;
    let latestResult;
    const refreshRuntime = vi.fn(() => {
      if (!shouldRunRuntimeRefresh({
        now: Date.now(), lastRefreshAt, minIntervalMs: 10 * MINUTE,
        visibilityState: visible ? "visible" : "hidden",
      })) return Promise.resolve({ status: "skipped" });
      lastRefreshAt = Date.now();
      latestResult = h.fetch();
      return latestResult;
    });
    // Match App.jsx: the three-minute foreground callback checks location;
    // only the resume sequence invokes requestRuntimeRefresh directly.
    const foregroundLocation = vi.fn().mockResolvedValue({ ok: true });
    const runtime = startCapacitorAppResumeRuntime({
      app: { addListener: vi.fn(async (_event, callback) => { listener = callback; return { remove: vi.fn() }; }) },
      capacitor: { getPlatform: () => "android", isNativePlatform: () => true },
      onForegroundCheck: foregroundLocation,
      onResume: () => runCapacitorResumeSequence({ refreshLocation: foregroundLocation, refreshRuntime }),
    });
    try {
      await runtime.ready;
      await listener({ isActive: true });
      await vi.advanceTimersByTimeAsync(3 * MINUTE);
      expect(foregroundLocation).toHaveBeenCalledTimes(2);
      expect(h.bundleFetcher).toHaveBeenCalledTimes(1);
      visible = false;
      await listener({ isActive: false });
      await vi.advanceTimersByTimeAsync(8 * MINUTE);
      expect(h.bundleFetcher).toHaveBeenCalledTimes(1);
      visible = true;
      await listener({ isActive: true });
      expect((await latestResult).current.data_quality.cams_run_utc).toBe(RUN_B);
      expect(h.bundleFetcher).toHaveBeenCalledTimes(2);
      expect(h.bundleFetcher.mock.lastCall[1].force).toBe(false);
    } finally {
      runtime.stop();
    }
  });
});
