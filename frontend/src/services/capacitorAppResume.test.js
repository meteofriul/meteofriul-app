import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS,
  CAPACITOR_AUTO_LOCATION_RETRY_INTERVAL_MS,
  createRateLimitedAppResumeHandler,
  runCapacitorResumeSequence,
  startCapacitorAppResumeRuntime,
} from "./capacitorAppResume";

const ANDROID_RUNTIME = {
  getPlatform: () => "android",
  isNativePlatform: () => true,
};

afterEach(() => {
  vi.useRealTimers();
});

describe("Capacitor app resume runtime", () => {
  it("settles the GPS check before refreshing cached runtime data", async () => {
    const calls = [];
    let releaseLocation;
    const sequence = runCapacitorResumeSequence({
      refreshLocation: vi.fn(() => new Promise((resolve) => {
        calls.push("location:start");
        releaseLocation = () => {
          calls.push("location:end");
          resolve({ ok: true, placeChanged: true });
        };
      })),
      refreshNotifications: vi.fn(async () => {
        calls.push("notifications");
      }),
      refreshRuntime: vi.fn(() => {
        calls.push("runtime");
      }),
    });

    await vi.waitFor(() => expect(releaseLocation).toBeTypeOf("function"));
    expect(calls).toEqual(["location:start"]);
    releaseLocation();

    await expect(sequence).resolves.toEqual({ ok: true, placeChanged: true });
    expect(calls).toEqual([
      "location:start",
      "location:end",
      "runtime",
      "notifications",
    ]);
  });

  it("skips GPS before the foreground cadence is due", async () => {
    const onDueResume = vi.fn();
    const handler = createRateLimitedAppResumeHandler({
      isDue: () => false,
      markChecked: vi.fn(),
      onDueResume,
    });

    await expect(handler()).resolves.toEqual({ status: "skipped" });
    expect(onDueResume).not.toHaveBeenCalled();
  });

  it("runs one GPS refresh and marks the check once the cadence is due", async () => {
    const markChecked = vi.fn();
    const onDueResume = vi.fn().mockResolvedValue({ ok: true, source: "test" });
    const handler = createRateLimitedAppResumeHandler({
      isDue: () => true,
      markChecked,
      now: () => 180_000,
      onDueResume,
    });

    await expect(handler()).resolves.toEqual({
      result: { ok: true, source: "test" },
      status: "settled",
    });
    expect(markChecked).toHaveBeenCalledWith(180_000, { ok: true, source: "test" });
    expect(onDueResume).toHaveBeenCalledTimes(1);
  });

  it("does not create a long cooldown after failure and retries after the short interval", async () => {
    let checkedAt = 1000;
    let currentTime = checkedAt + CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS;
    const markChecked = vi.fn((nextCheckedAt) => {
      checkedAt = nextCheckedAt;
    });
    const onDueResume = vi.fn()
      .mockResolvedValueOnce({ ok: false, reason: "timeout" })
      .mockResolvedValueOnce({ ok: true });
    const handler = createRateLimitedAppResumeHandler({
      isDue: () => currentTime - checkedAt >= CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS,
      markChecked,
      now: () => currentTime,
      onDueResume,
    });

    await expect(handler()).resolves.toMatchObject({ status: "failed" });
    expect(markChecked).not.toHaveBeenCalled();

    currentTime += CAPACITOR_AUTO_LOCATION_RETRY_INTERVAL_MS - 1;
    await expect(handler()).resolves.toEqual({
      reason: "retry_interval",
      status: "skipped",
    });
    expect(onDueResume).toHaveBeenCalledTimes(1);

    currentTime += 1;
    await expect(handler()).resolves.toMatchObject({ status: "settled" });
    expect(onDueResume).toHaveBeenCalledTimes(2);
    expect(markChecked).toHaveBeenCalledTimes(1);

    currentTime += CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS - 1;
    await expect(handler()).resolves.toEqual({ status: "skipped" });
  });

  it("keeps a thrown foreground location failure retryable", async () => {
    let currentTime = 500_000;
    const markChecked = vi.fn();
    const onDueResume = vi.fn()
      .mockRejectedValueOnce(new Error("gps_failed"))
      .mockResolvedValueOnce({ ok: true });
    const handler = createRateLimitedAppResumeHandler({
      isDue: () => true,
      markChecked,
      now: () => currentTime,
      onDueResume,
    });

    await expect(handler()).resolves.toEqual({
      error: "gps_failed",
      status: "failed",
    });
    expect(markChecked).not.toHaveBeenCalled();

    currentTime += CAPACITOR_AUTO_LOCATION_RETRY_INTERVAL_MS;
    await expect(handler()).resolves.toMatchObject({ status: "settled" });
    expect(markChecked).toHaveBeenCalledTimes(1);
  });

  it("does nothing in the browser", async () => {
    const app = { addListener: vi.fn() };
    const runtime = startCapacitorAppResumeRuntime({
      app,
      capacitor: { getPlatform: () => "web", isNativePlatform: () => false },
    });

    expect(runtime.active).toBe(false);
    await expect(runtime.ready).resolves.toBe(false);
    expect(app.addListener).not.toHaveBeenCalled();
  });

  it("queues one active resume received while a foreground refresh is in flight", async () => {
    let appStateListener;
    const remove = vi.fn();
    const app = {
      addListener: vi.fn(async (eventName, listener) => {
        expect(eventName).toBe("appStateChange");
        appStateListener = listener;
        return { remove };
      }),
    };
    let releaseResume;
    const onResume = vi.fn()
      .mockImplementationOnce(() => new Promise((resolve) => {
        releaseResume = resolve;
      }))
      .mockResolvedValue({ ok: true });
    const runtime = startCapacitorAppResumeRuntime({
      app,
      capacitor: ANDROID_RUNTIME,
      onResume,
    });

    await expect(runtime.ready).resolves.toBe(true);
    await appStateListener({ isActive: false });
    expect(onResume).not.toHaveBeenCalled();

    const firstResume = appStateListener({ isActive: true });
    await appStateListener({ isActive: true });
    expect(onResume).toHaveBeenCalledTimes(1);
    releaseResume();
    await firstResume;
    expect(onResume).toHaveBeenCalledTimes(2);

    runtime.stop();
    expect(remove).toHaveBeenCalledTimes(1);
  });

  it("cancels a queued refresh when the app returns to background", async () => {
    let appStateListener;
    let releaseResume;
    const onResume = vi.fn(() => new Promise((resolve) => {
      releaseResume = resolve;
    }));
    const runtime = startCapacitorAppResumeRuntime({
      app: {
        addListener: vi.fn(async (_eventName, listener) => {
          appStateListener = listener;
          return { remove: vi.fn() };
        }),
      },
      capacitor: ANDROID_RUNTIME,
      onResume,
    });

    await runtime.ready;
    const firstResume = appStateListener({ isActive: true });
    await appStateListener({ isActive: true });
    await appStateListener({ isActive: false });
    releaseResume();
    await firstResume;

    expect(onResume).toHaveBeenCalledTimes(1);
    runtime.stop();
  });

  it("runs a second one-shot check after three minutes while the app stays foreground", async () => {
    vi.useFakeTimers();
    let appStateListener;
    const onForegroundCheck = vi.fn().mockResolvedValue({ ok: true });
    const onResume = vi.fn().mockResolvedValue({ ok: true });
    const runtime = startCapacitorAppResumeRuntime({
      app: {
        addListener: vi.fn(async (_eventName, listener) => {
          appStateListener = listener;
          return { remove: vi.fn() };
        }),
      },
      capacitor: ANDROID_RUNTIME,
      onForegroundCheck,
      onResume,
    });

    await runtime.ready;
    await appStateListener({ isActive: true });
    expect(onResume).toHaveBeenCalledTimes(1);
    expect(onForegroundCheck).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS);
    expect(onForegroundCheck).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(1);

    runtime.stop();
  });

  it("refreshes immediately and starts the timer when Android is already active", async () => {
    vi.useFakeTimers();
    const onForegroundCheck = vi.fn().mockResolvedValue({ ok: true });
    const onResume = vi.fn();
    const runtime = startCapacitorAppResumeRuntime({
      app: {
        addListener: vi.fn(async () => ({ remove: vi.fn() })),
        getState: vi.fn().mockResolvedValue({ isActive: true }),
      },
      capacitor: ANDROID_RUNTIME,
      onForegroundCheck,
      onResume,
    });

    await expect(runtime.ready).resolves.toBe(true);
    expect(onResume).toHaveBeenCalledTimes(1);
    expect(onForegroundCheck).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(1);

    await vi.advanceTimersByTimeAsync(CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS);
    expect(onForegroundCheck).toHaveBeenCalledTimes(1);

    runtime.stop();
  });

  it("does not let a stale getState result override a newer background event", async () => {
    vi.useFakeTimers();
    let appStateListener;
    let resolveInitialState;
    const onForegroundCheck = vi.fn();
    const runtime = startCapacitorAppResumeRuntime({
      app: {
        addListener: vi.fn(async (_eventName, listener) => {
          appStateListener = listener;
          return { remove: vi.fn() };
        }),
        getState: vi.fn(() => new Promise((resolve) => {
          resolveInitialState = resolve;
        })),
      },
      capacitor: ANDROID_RUNTIME,
      onForegroundCheck,
      onResume: vi.fn(),
    });

    await vi.waitFor(() => expect(resolveInitialState).toBeTypeOf("function"));
    await appStateListener({ isActive: false });
    resolveInitialState({ isActive: true });
    await expect(runtime.ready).resolves.toBe(true);

    await vi.advanceTimersByTimeAsync(CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS * 2);
    expect(onForegroundCheck).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);

    runtime.stop();
  });

  it("queues the foreground timer instead of overlapping an active resume request", async () => {
    vi.useFakeTimers();
    let appStateListener;
    let releaseResume;
    const onForegroundCheck = vi.fn().mockResolvedValue({ ok: true });
    const onResume = vi.fn(() => new Promise((resolve) => {
      releaseResume = resolve;
    }));
    const runtime = startCapacitorAppResumeRuntime({
      app: {
        addListener: vi.fn(async (_eventName, listener) => {
          appStateListener = listener;
          return { remove: vi.fn() };
        }),
      },
      capacitor: ANDROID_RUNTIME,
      onForegroundCheck,
      onResume,
    });

    await runtime.ready;
    const activeResume = appStateListener({ isActive: true });
    await vi.advanceTimersByTimeAsync(CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS);
    expect(onResume).toHaveBeenCalledTimes(1);
    expect(onForegroundCheck).not.toHaveBeenCalled();

    releaseResume({ ok: true });
    await activeResume;
    expect(onForegroundCheck).toHaveBeenCalledTimes(1);

    runtime.stop();
  });

  it("does not run the foreground timer after the app becomes inactive", async () => {
    vi.useFakeTimers();
    let appStateListener;
    const onForegroundCheck = vi.fn();
    const runtime = startCapacitorAppResumeRuntime({
      app: {
        addListener: vi.fn(async (_eventName, listener) => {
          appStateListener = listener;
          return { remove: vi.fn() };
        }),
      },
      capacitor: ANDROID_RUNTIME,
      onForegroundCheck,
      onResume: vi.fn().mockResolvedValue({ ok: true }),
    });

    await runtime.ready;
    await appStateListener({ isActive: true });
    await appStateListener({ isActive: false });
    await vi.advanceTimersByTimeAsync(CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS * 2);

    expect(onForegroundCheck).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    runtime.stop();
  });

  it("clears the foreground timer when the runtime stops", async () => {
    vi.useFakeTimers();
    let appStateListener;
    const remove = vi.fn();
    const onForegroundCheck = vi.fn();
    const runtime = startCapacitorAppResumeRuntime({
      app: {
        addListener: vi.fn(async (_eventName, listener) => {
          appStateListener = listener;
          return { remove };
        }),
      },
      capacitor: ANDROID_RUNTIME,
      onForegroundCheck,
      onResume: vi.fn().mockResolvedValue({ ok: true }),
    });

    await runtime.ready;
    await appStateListener({ isActive: true });
    expect(vi.getTimerCount()).toBe(1);

    runtime.stop();
    await vi.advanceTimersByTimeAsync(CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS * 2);

    expect(onForegroundCheck).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    expect(remove).toHaveBeenCalledTimes(1);
  });

  it("removes a listener that resolves after cleanup", async () => {
    let resolveHandle;
    const remove = vi.fn();
    const app = {
      addListener: vi.fn(() => new Promise((resolve) => {
        resolveHandle = resolve;
      })),
    };
    const runtime = startCapacitorAppResumeRuntime({
      app,
      capacitor: ANDROID_RUNTIME,
    });

    runtime.stop();
    resolveHandle({ remove });
    await expect(runtime.ready).resolves.toBe(false);
    expect(remove).toHaveBeenCalledTimes(1);
  });
});
