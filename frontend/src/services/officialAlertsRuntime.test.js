import { describe, expect, it, vi } from "vitest";

import { OFFICIAL_ALERT_STATES } from "../domain/alerts/officialAlerts";
import {
  REGIONAL_OFFICIAL_ALERTS_CACHE_KEY,
  readRegionalOfficialAlertsCache,
} from "./officialAlertsCache";
import {
  loadOfficialAlertsRuntime,
  readInitialOfficialAlertsRuntime,
} from "./officialAlertsRuntime";

const NOW = new Date("2026-08-20T18:00:00.000Z").getTime();

function createStorage(initial = {}) {
  const items = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => (items.has(key) ? items.get(key) : null)),
    setItem: vi.fn((key, value) => items.set(key, value)),
    removeItem: vi.fn((key) => items.delete(key)),
    items,
  };
}

function cacheEntry(data, savedAt = NOW) {
  return JSON.stringify({ data, savedAt });
}

function activeAlert(level = "gialla") {
  return {
    active: true,
    alerts: [{
      id: `regional-${level}`,
      level,
      valid_to: "2026-08-21T23:59:00+02:00",
    }],
    source_mode: "official_widget",
  };
}

function confirmedInactive() {
  return {
    active: false,
    alerts: [],
    source_mode: "official_widget",
  };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, reject, resolve };
}

describe("official alerts runtime", () => {
  it("hydrates the initial global state from the regional cache", () => {
    const payload = activeAlert();
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(payload),
    });

    expect(readInitialOfficialAlertsRuntime({ storage, now: () => NOW })).toMatchObject({
      active: true,
      alertState: OFFICIAL_ALERT_STATES.ACTIVE,
      canShowBanner: true,
      fromCache: true,
      payload,
      retained: false,
      status: "cache",
    });
  });

  it("publishes and caches a fresh official alert independently from OSMER", async () => {
    const payload = activeAlert("arancione");
    const storage = createStorage();
    const alertsFetcher = vi.fn().mockResolvedValue(payload);

    const state = await loadOfficialAlertsRuntime({
      alertsFetcher,
      apiBase: "/api",
      force: true,
      now: () => NOW,
      storage,
    });

    expect(alertsFetcher).toHaveBeenCalledWith({
      apiBase: "/api",
      fetchImpl: globalThis.fetch,
      force: true,
      now: expect.any(Function),
    });
    expect(state).toMatchObject({
      active: true,
      alertState: OFFICIAL_ALERT_STATES.ACTIVE,
      fromCache: false,
      payload,
      retained: false,
      status: "fresh",
    });
    expect(readRegionalOfficialAlertsCache({ storage, now: () => NOW })).toEqual(payload);
  });

  it("lets a confirmed inactive response clear the previous active alert", async () => {
    const previous = activeAlert();
    const inactive = confirmedInactive();
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(previous),
    });

    const state = await loadOfficialAlertsRuntime({
      alertsFetcher: vi.fn().mockResolvedValue(inactive),
      now: () => NOW,
      storage,
    });

    expect(state).toMatchObject({
      active: false,
      alertState: OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
      canShowBanner: false,
      fromCache: false,
      payload: inactive,
      retained: false,
      status: "fresh",
    });
    expect(readRegionalOfficialAlertsCache({ storage, now: () => NOW })).toEqual(inactive);
  });

  it("retains the last valid active alert when the official endpoint is inconclusive", async () => {
    const previous = activeAlert("rossa");
    const unavailable = {
      active: false,
      alerts: [],
      cache: { status: "unavailable" },
      error: "official_alerts_unavailable",
      source_mode: "official_alerts_unavailable_fast_fallback",
    };
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(previous),
    });

    const state = await loadOfficialAlertsRuntime({
      alertsFetcher: vi.fn().mockResolvedValue(unavailable),
      now: () => NOW,
      storage,
    });

    expect(state).toMatchObject({
      active: true,
      alertState: OFFICIAL_ALERT_STATES.ACTIVE,
      fromCache: true,
      payload: previous,
      retained: true,
      status: "retained",
    });
  });

  it("retains the last valid active alert when the network refresh fails", async () => {
    const previous = activeAlert();
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(previous),
    });

    const state = await loadOfficialAlertsRuntime({
      alertsFetcher: vi.fn().mockRejectedValue(new Error("rete non disponibile")),
      now: () => NOW,
      storage,
    });

    expect(state).toMatchObject({
      active: true,
      alertState: OFFICIAL_ALERT_STATES.ACTIVE,
      error: "rete non disponibile",
      fromCache: true,
      payload: previous,
      retained: true,
      status: "retained",
    });
  });

  it("reports a network error without inventing an inactive confirmation", async () => {
    const state = await loadOfficialAlertsRuntime({
      alertsFetcher: vi.fn().mockRejectedValue(new Error("offline")),
      now: () => NOW,
      storage: createStorage(),
    });

    expect(state).toMatchObject({
      active: false,
      alertState: OFFICIAL_ALERT_STATES.UNAVAILABLE,
      canShowBanner: false,
      error: "offline",
      fromCache: false,
      payload: null,
      retained: false,
      status: "error",
    });
  });

  it("does not let an older overlapping response overwrite a newer cache result", async () => {
    const storage = createStorage();
    const olderResponse = deferred();
    const newerResponse = deferred();
    const alertsFetcher = vi.fn()
      .mockImplementationOnce(() => olderResponse.promise)
      .mockImplementationOnce(() => newerResponse.promise);

    const olderLoad = loadOfficialAlertsRuntime({
      alertsFetcher,
      now: () => NOW,
      storage,
    });
    const newerLoad = loadOfficialAlertsRuntime({
      alertsFetcher,
      now: () => NOW,
      storage,
    });

    const inactive = confirmedInactive();
    newerResponse.resolve(inactive);
    const newerState = await newerLoad;

    olderResponse.resolve(activeAlert("rossa"));
    const olderState = await olderLoad;

    expect(newerState).toMatchObject({
      alertState: OFFICIAL_ALERT_STATES.INACTIVE_CONFIRMED,
      payload: inactive,
      status: "fresh",
    });
    expect(olderState).toEqual(newerState);
    expect(readRegionalOfficialAlertsCache({ storage, now: () => NOW })).toEqual(inactive);
  });

  it("treats a legacy empty-array response as unavailable, not confirmed inactive", async () => {
    const storage = createStorage();

    const state = await loadOfficialAlertsRuntime({
      alertsFetcher: vi.fn().mockResolvedValue([]),
      now: () => NOW,
      storage,
    });

    expect(state).toMatchObject({
      active: false,
      alertState: OFFICIAL_ALERT_STATES.UNAVAILABLE,
      canShowBanner: false,
      payload: [],
      retained: false,
      status: "unavailable",
    });
    expect(readRegionalOfficialAlertsCache({ storage, now: () => NOW })).toBeNull();
  });
});
