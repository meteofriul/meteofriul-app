import { describe, expect, it } from "vitest";

import {
  getEventsPendingDecision,
  getInitialHydrationDecision,
  getRefreshRequestDecision,
  getRefreshResultDecision,
  getRuntimeRefreshCompletionOutcome,
  getRuntimeRefreshGateOutcome,
  getRuntimeRefreshTimeoutOutcome,
  hasVisibleRuntimeData,
  hasVisibleRuntimeDataTree,
  isFreshAuthoritativeOfficialAlertsRuntime,
  RUNTIME_REFRESH_ACTION,
  RUNTIME_REFRESH_STATE,
  shouldIgnoreStaleLocationResponse,
  shouldRunForegroundRuntimeRefresh,
  shouldRunRuntimeRefresh,
  shouldWriteEventsCacheForPayload,
} from "./runtimeRefreshPolicy";

describe("runtimeRefreshPolicy", () => {
  it("hydrates from cache before the first network refresh", () => {
    expect(getInitialHydrationDecision({ hasFreshCache: true })).toEqual({
      action: RUNTIME_REFRESH_ACTION.hydrateFromCache,
      state: RUNTIME_REFRESH_STATE.hydrated,
      shouldFetchAfterRender: true,
    });

    expect(getInitialHydrationDecision({ hasStaleCache: true })).toMatchObject({
      action: RUNTIME_REFRESH_ACTION.hydrateFromCache,
      state: RUNTIME_REFRESH_STATE.hydrated,
    });
  });

  it("starts a refresh when no cache can hydrate the screen", () => {
    expect(getInitialHydrationDecision()).toEqual({
      action: RUNTIME_REFRESH_ACTION.refreshCurrentLocation,
      state: RUNTIME_REFRESH_STATE.refreshing,
      shouldFetchAfterRender: true,
    });
  });

  it("keeps visible data on failed refresh and shows unreachable only when empty", () => {
    expect(getRefreshResultDecision({
      error: "network_error",
      hasVisibleData: true,
      ok: false,
    })).toEqual({
      action: RUNTIME_REFRESH_ACTION.showPassiveFeedback,
      error: "network_error",
      state: RUNTIME_REFRESH_STATE.staleVisible,
      shouldKeepVisibleData: true,
    });

    expect(getRefreshResultDecision({
      error: "network_error",
      hasVisibleData: false,
      ok: false,
    })).toEqual({
      action: RUNTIME_REFRESH_ACTION.showUnreachableState,
      error: "network_error",
      state: RUNTIME_REFRESH_STATE.unreachableEmpty,
      shouldKeepVisibleData: false,
    });
  });

  it("distinguishes changed and unchanged successful refreshes", () => {
    expect(getRefreshResultDecision({ ok: true, changed: true })).toMatchObject({
      action: RUNTIME_REFRESH_ACTION.showPassiveFeedback,
      state: RUNTIME_REFRESH_STATE.fresh,
    });

    expect(getRefreshResultDecision({ ok: true, changed: false })).toMatchObject({
      action: RUNTIME_REFRESH_ACTION.showPassiveFeedback,
      state: RUNTIME_REFRESH_STATE.unchanged,
    });
  });

  it("ignores responses that belong to a previous location", () => {
    expect(shouldIgnoreStaleLocationResponse({
      activeLocationKey: "pordenone|city|city",
      responseLocationKey: "trieste|city|city",
    })).toBe(true);

    expect(getRefreshRequestDecision({
      activeLocationKey: "pordenone|city|city",
      responseLocationKey: "trieste|city|city",
    })).toEqual({
      action: RUNTIME_REFRESH_ACTION.ignoreResponse,
      state: RUNTIME_REFRESH_STATE.ignoredStaleLocation,
    });
  });

  it("refreshes the regional bulletin when no local city is resolved", () => {
    expect(getRefreshRequestDecision({ hasLocation: false })).toEqual({
      action: RUNTIME_REFRESH_ACTION.refreshRegionalBulletin,
      state: RUNTIME_REFRESH_STATE.refreshing,
    });
  });

  it("detects whether runtime data can remain visible", () => {
    expect(hasVisibleRuntimeData({ current: { temperature: 20 } })).toBe(true);
    expect(hasVisibleRuntimeData({ forecast: { official: {} } })).toBe(false);
    expect(hasVisibleRuntimeData({ forecast: { official: { it: { forecasts: [{ text: "Sole" }] } } } })).toBe(true);
    expect(hasVisibleRuntimeData({ events: [{ id: "event-1" }] })).toBe(true);
    expect(hasVisibleRuntimeData({ items: [] })).toBe(false);
    expect(hasVisibleRuntimeData(null)).toBe(false);
  });

  it("detects visible nested runtime data for route refresh outcomes", () => {
    expect(hasVisibleRuntimeDataTree({
      weather: { current: { temperature: 20 }, error: "network_error", status: "stale" },
    })).toBe(true);
    expect(hasVisibleRuntimeDataTree({
      forecast: { official: {} },
      isStale: true,
      status: "stale",
    })).toBe(false);
    expect(hasVisibleRuntimeDataTree({
      forecast: { official: { it: { forecasts: [{ text: "Sole" }] } } },
      isStale: true,
      status: "stale",
    })).toBe(true);
    expect(hasVisibleRuntimeDataTree({
      events: { items: [{ id: "event-1" }], error: "network_error", status: "stale" },
    })).toBe(true);
    expect(hasVisibleRuntimeDataTree({
      weather: { status: "error", error: "network_error" },
      events: { status: "error", error: "network_error", items: [] },
    })).toBe(false);
  });

  it("marks pull refresh as failed only when no visible data survives", () => {
    expect(getRuntimeRefreshCompletionOutcome([
      {
        status: "fulfilled",
        value: { status: "stale", error: "network_error", forecast: { days: [] } },
      },
    ])).toEqual({ ok: false });

    expect(getRuntimeRefreshCompletionOutcome([
      {
        status: "fulfilled",
        value: { status: "stale", error: "network_error", forecast: { official: {} }, isStale: true },
      },
    ])).toEqual({ ok: false });

    expect(getRuntimeRefreshCompletionOutcome([
      {
        status: "fulfilled",
        value: {
          status: "stale",
          error: "network_error",
          forecast: { official: { it: { forecasts: [{ text: "Sole" }] } } },
          isStale: true,
        },
      },
    ])).toEqual({ ok: true, partial: true });

    expect(getRuntimeRefreshCompletionOutcome([
      {
        status: "fulfilled",
        value: { ok: false, weather: { current: { temperature: 20 }, error: "network_error" } },
      },
    ])).toEqual({ ok: true, partial: true });

    expect(getRuntimeRefreshCompletionOutcome([
      {
        status: "fulfilled",
        value: { status: "error", error: "network_error" },
      },
    ])).toEqual({ ok: false });

    expect(getRuntimeRefreshCompletionOutcome([
      { status: "rejected", reason: new Error("network_error") },
    ])).toEqual({ ok: false });
  });

  it("reports a partial route refresh when one independent component fails", () => {
    expect(getRuntimeRefreshCompletionOutcome([
      { status: "fulfilled", value: { current: { temperature: 20 } } },
      { status: "rejected", reason: new Error("radar_unavailable") },
    ])).toEqual({ ok: true, partial: true });

    expect(getRuntimeRefreshCompletionOutcome([
      { status: "rejected", reason: new Error("webcams_unavailable") },
      { status: "rejected", reason: new Error("radar_unavailable") },
    ])).toEqual({ ok: false });
  });

  it("marks only an uncommitted weather candidate as failed while keeping its active data visible", () => {
    const visibleWeather = {
      current: { temperature: 20 },
      rawCurrent: {
        temperature: 20,
        cache: {
          runtime_fallback: true,
          runtime_fallback_source: "candidate_not_committed",
          runtime_fallback_code: "CACHE_PERSIST_FAILED",
        },
      },
    };
    expect(getRuntimeRefreshCompletionOutcome([
      { status: "fulfilled", value: visibleWeather },
    ])).toEqual({ ok: false });
    expect(hasVisibleRuntimeDataTree(visibleWeather)).toBe(true);

    expect(getRuntimeRefreshCompletionOutcome([{
      status: "fulfilled",
      value: {
        ...visibleWeather,
        rawCurrent: {
          ...visibleWeather.rawCurrent,
          cache: {
            runtime_fallback: true,
            runtime_fallback_source: "verified_memory_bundle",
          },
        },
      },
    }])).toEqual({ ok: true });
  });

  it("waits for both route data and an authoritative fresh alert state", () => {
    const freshActive = {
      alertState: "active",
      fromCache: false,
      retained: false,
      status: "fresh",
    };
    const freshInactive = {
      alertState: "inactive_confirmed",
      fromCache: false,
      retained: false,
      status: "fresh",
    };

    expect(getRuntimeRefreshGateOutcome({ route: { ok: true } })).toBeNull();
    expect(getRuntimeRefreshGateOutcome({ officialAlerts: freshActive })).toBeNull();
    expect(getRuntimeRefreshGateOutcome({
      officialAlerts: freshActive,
      route: { ok: true },
    })).toEqual({
      components: {
        officialAlerts: "settled",
        route: "settled",
      },
      ok: true,
      partial: false,
    });
    expect(getRuntimeRefreshGateOutcome({
      officialAlerts: freshInactive,
      route: {},
    })).toEqual({
      components: {
        officialAlerts: "settled",
        route: "settled",
      },
      ok: true,
      partial: false,
    });
  });

  it("settles a national route without waiting for FVG-only official alerts", () => {
    expect(getRuntimeRefreshGateOutcome({
      officialAlertsRequired: false,
      route: { ok: true },
    })).toEqual({
      components: { route: "settled" },
      ok: true,
      partial: false,
    });

    expect(getRuntimeRefreshTimeoutOutcome({
      officialAlertsRequired: false,
      route: { ok: true },
    })).toEqual({
      components: { route: "settled" },
      ok: true,
      partial: true,
    });
  });

  it("keeps the route successful but reports a partial result for non-authoritative alerts", () => {
    expect(isFreshAuthoritativeOfficialAlertsRuntime({
      alertState: "active",
      retained: true,
      status: "retained",
    })).toBe(false);
    expect(isFreshAuthoritativeOfficialAlertsRuntime({
      alertState: "active",
      fromCache: true,
      status: "cache",
    })).toBe(false);
    expect(isFreshAuthoritativeOfficialAlertsRuntime({
      alertState: "unavailable",
      status: "unavailable",
    })).toBe(false);

    expect(getRuntimeRefreshGateOutcome({
      officialAlerts: {
        alertState: "inactive_confirmed",
        status: "fresh",
      },
      route: { ok: true, partial: true },
    })).toEqual({
      components: {
        officialAlerts: "settled",
        route: "partial",
      },
      ok: true,
      partial: true,
    });
    expect(getRuntimeRefreshGateOutcome({
      officialAlerts: {
        alertState: "active",
        retained: true,
        status: "retained",
      },
      route: { ok: true },
    })).toEqual({
      components: {
        officialAlerts: "retained",
        route: "settled",
      },
      ok: true,
      partial: true,
    });
    expect(getRuntimeRefreshGateOutcome({
      officialAlerts: {
        alertState: "unavailable",
        status: "unavailable",
      },
      route: { ok: true },
    })).toEqual({
      components: {
        officialAlerts: "unavailable",
        route: "settled",
      },
      ok: true,
      partial: true,
    });
    expect(getRuntimeRefreshGateOutcome({
      officialAlerts: {
        alertState: "inactive_confirmed",
        status: "fresh",
      },
      route: { ok: false },
    })).toEqual({
      components: {
        officialAlerts: "settled",
        route: "failed",
      },
      ok: false,
      partial: false,
    });
  });

  it("does not turn a settled route into a failure when official alerts exceed the UI deadline", () => {
    expect(getRuntimeRefreshTimeoutOutcome({
      route: {
        components: {
          cams: "settled",
          icon: "settled",
        },
        ok: true,
      },
    })).toEqual({
      components: {
        cams: "settled",
        icon: "settled",
        officialAlerts: "pending",
      },
      ok: true,
      partial: true,
    });

    expect(getRuntimeRefreshTimeoutOutcome({
      officialAlerts: {
        alertState: "inactive_confirmed",
        status: "fresh",
      },
    })).toEqual({
      components: {
        officialAlerts: "settled",
        route: "pending",
      },
      ok: false,
      partial: false,
    });
  });

  it("does not cache pending Eventi payloads and keeps cache visible while retrying", () => {
    expect(shouldWriteEventsCacheForPayload({ isRefreshing: true })).toBe(false);
    expect(shouldWriteEventsCacheForPayload({ isPartial: true })).toBe(false);
    expect(shouldWriteEventsCacheForPayload({ events: [] })).toBe(true);

    expect(getEventsPendingDecision({
      hasCachedEvents: true,
      isRefreshing: true,
      retry: 3,
    })).toEqual({
      action: RUNTIME_REFRESH_ACTION.retryEventsIfPending,
      shouldKeepCachedEvents: true,
      shouldRetry: true,
      shouldWriteCache: false,
      state: RUNTIME_REFRESH_STATE.refreshing,
    });
  });

  it("stops retrying Eventi after the configured retry budget", () => {
    expect(getEventsPendingDecision({
      isPartial: true,
      retry: 20,
    })).toMatchObject({
      action: RUNTIME_REFRESH_ACTION.none,
      shouldRetry: false,
      shouldWriteCache: false,
    });
  });

  it("throttles foreground refreshes and never runs while hidden", () => {
    expect(shouldRunForegroundRuntimeRefresh({
      now: 120000,
      lastRefreshAt: 0,
    })).toBe(true);

    expect(shouldRunForegroundRuntimeRefresh({
      now: 119999,
      lastRefreshAt: 0,
      visibilityState: "hidden",
    })).toBe(false);

    expect(shouldRunForegroundRuntimeRefresh({
      now: 119999,
      lastRefreshAt: 0,
      minIntervalMs: 120000,
    })).toBe(true);

    expect(shouldRunForegroundRuntimeRefresh({
      now: 119999,
      lastRefreshAt: 1,
      minIntervalMs: 120000,
    })).toBe(false);

    expect(shouldRunForegroundRuntimeRefresh({
      now: 120001,
      lastRefreshAt: 1,
      minIntervalMs: 120000,
    })).toBe(true);
  });

  it("uses the runtime refresh gate for shell refresh requests", () => {
    expect(shouldRunRuntimeRefresh({
      force: true,
      now: 10,
      visibilityState: "hidden",
    })).toBe(true);

    expect(shouldRunRuntimeRefresh({
      now: 119999,
      lastRefreshAt: 1,
      minIntervalMs: 120000,
    })).toBe(false);

    expect(shouldRunRuntimeRefresh({
      now: 120001,
      lastRefreshAt: 1,
      minIntervalMs: 120000,
    })).toBe(true);

    expect(shouldRunRuntimeRefresh({ now: Number.NaN })).toBe(false);
  });
});
