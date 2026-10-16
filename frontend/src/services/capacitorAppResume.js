import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

import { isAndroidCapacitorRuntime } from "./apiConfig";

export const CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS = 3 * 60 * 1000;
export const CAPACITOR_AUTO_LOCATION_RETRY_INTERVAL_MS = 30 * 1000;

export function createRateLimitedAppResumeHandler({
  isDue,
  markChecked,
  now = Date.now,
  onDueResume,
  retryIntervalMs = CAPACITOR_AUTO_LOCATION_RETRY_INTERVAL_MS,
} = {}) {
  let lastAttemptAt = Number.NEGATIVE_INFINITY;

  return async () => {
    if (!isDue?.()) return { status: "skipped" };

    const attemptedAt = Number(now?.());
    if (!Number.isFinite(attemptedAt)) return { status: "skipped" };
    if (attemptedAt - lastAttemptAt < retryIntervalMs) {
      return { status: "skipped", reason: "retry_interval" };
    }
    lastAttemptAt = attemptedAt;

    let result;
    try {
      result = await onDueResume?.();
    } catch (error) {
      return {
        error: error?.message || "resume_location_failed",
        status: "failed",
      };
    }

    if (!result?.ok) {
      return { result, status: "failed" };
    }

    markChecked?.(attemptedAt, result);
    return { result, status: "settled" };
  };
}

export async function runCapacitorResumeSequence({
  refreshLocation,
  refreshNotifications,
  refreshRuntime,
} = {}) {
  const locationResult = await refreshLocation?.();
  refreshRuntime?.();
  await refreshNotifications?.();

  return locationResult;
}

export function startCapacitorAppResumeRuntime({
  app = App,
  capacitor = Capacitor,
  clearTimeoutImpl = globalThis.clearTimeout,
  foregroundCheckIntervalMs = CAPACITOR_AUTO_LOCATION_RESUME_INTERVAL_MS,
  onForegroundCheck,
  onResume,
  setTimeoutImpl = globalThis.setTimeout,
} = {}) {
  let foregroundTimerId = null;
  let listenerHandle = null;
  let stopped = false;
  let appStateGeneration = 0;
  let appIsActive = false;
  let taskInFlight = false;
  let queuedTask = null;

  if (!isAndroidCapacitorRuntime(capacitor) || typeof app?.addListener !== "function") {
    return {
      active: false,
      ready: Promise.resolve(false),
      stop() {},
    };
  }

  const clearForegroundTimer = () => {
    if (foregroundTimerId == null) return;

    clearTimeoutImpl?.(foregroundTimerId);
    foregroundTimerId = null;
  };

  const queueTask = (taskName) => {
    if (taskName === "resume" || queuedTask == null) queuedTask = taskName;
  };

  const runForegroundTask = async (taskName) => {
    if (stopped || !appIsActive) return { status: "skipped" };
    if (taskInFlight) {
      queueTask(taskName);
      return { status: "queued" };
    }

    taskInFlight = true;
    let currentTask = taskName;
    try {
      do {
        queuedTask = null;
        const callback = currentTask === "foreground_check"
          ? (onForegroundCheck || onResume)
          : onResume;
        try {
          await callback?.();
        } catch {
          // A failed foreground refresh must not break the next check.
        }
        currentTask = queuedTask;
      } while (!stopped && appIsActive && currentTask);
    } finally {
      taskInFlight = false;
      queuedTask = null;
    }

    return { status: "settled" };
  };

  const scheduleForegroundCheck = () => {
    clearForegroundTimer();
    if (
      stopped ||
      !appIsActive ||
      typeof setTimeoutImpl !== "function" ||
      !Number.isFinite(foregroundCheckIntervalMs) ||
      foregroundCheckIntervalMs <= 0
    ) return;

    foregroundTimerId = setTimeoutImpl(async () => {
      foregroundTimerId = null;
      if (stopped || !appIsActive) return;

      await runForegroundTask("foreground_check");
      scheduleForegroundCheck();
    }, foregroundCheckIntervalMs);
  };

  const applyAppState = async ({ isActive } = {}, { runResume = true } = {}) => {
    appIsActive = Boolean(isActive);
    if (stopped || !appIsActive) {
      queuedTask = null;
      clearForegroundTimer();
      return;
    }

    scheduleForegroundCheck();
    if (runResume) return runForegroundTask("resume");
    return { status: "scheduled" };
  };

  const ready = Promise.resolve(app.addListener("appStateChange", (state = {}) => {
    appStateGeneration += 1;
    return applyAppState(state);
  }))
    .then(async (handle) => {
      if (stopped) {
        handle?.remove?.();
        return false;
      }

      listenerHandle = handle;
      if (typeof app?.getState === "function") {
        const observedGeneration = appStateGeneration;
        try {
          const initialState = await app.getState();
          if (!stopped && appStateGeneration === observedGeneration) {
            appStateGeneration += 1;
            await applyAppState(initialState, { runResume: true });
          }
        } catch {
          // Without a trustworthy foreground state, no timer is started.
        }
      }

      if (stopped) return false;
      return true;
    })
    .catch(() => false);

  return {
    active: true,
    ready,
    stop() {
      if (stopped) return;

      stopped = true;
      appIsActive = false;
      queuedTask = null;
      clearForegroundTimer();
      listenerHandle?.remove?.();
      listenerHandle = null;
    },
  };
}
