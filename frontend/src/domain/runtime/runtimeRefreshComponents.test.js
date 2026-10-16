import { describe, expect, it } from "vitest";

import { getRuntimeRefreshCompletionOutcome } from "./runtimeRefreshPolicy";

function fulfilled(value) {
  return { status: "fulfilled", value };
}

function visibleWeather({ camsStatus = "fresh" } = {}) {
  return {
    status: "fresh",
    current: { temperature: 20 },
    rawCurrent: {
      data_quality: {
        cams_status: camsStatus,
        status: "fresh",
      },
      source: {
        cams: { status: camsStatus === "fresh" ? "available" : camsStatus },
        icon: { status: "available" },
      },
    },
    forecast: { days: [{ date: "2026-09-14" }] },
  };
}

describe("runtime refresh component contracts", () => {
  it("expands Home into ICON, CAMS and events while keeping OSMER independent", () => {
    const outcome = getRuntimeRefreshCompletionOutcome([
      fulfilled({
        ok: true,
        weather: visibleWeather({ camsStatus: "pending" }),
        events: {
          error: null,
          isPartial: true,
          isRefreshing: false,
          items: [{ id: "event-1" }],
          status: "partial",
        },
      }),
      fulfilled({
        error: "Risposta bollettino OSMER non valida",
        forecast: {
          official: { it: { forecasts: [{ text: "Sole e nubi" }] } },
        },
        fromCache: true,
        status: "stale",
      }),
    ], ["home", "osmer"]);

    expect(outcome).toEqual({
      components: {
        cams: "pending",
        events: "partial",
        icon: "settled",
        osmer: "retained",
      },
      ok: true,
      partial: true,
    });
  });

  it("expands Live into webcams and community without letting either hide radar", () => {
    const outcome = getRuntimeRefreshCompletionOutcome([
      fulfilled({
        community: {
          error: "community offline",
          payload: null,
          status: "error",
        },
        error: null,
        items: [{ id: "cam-1" }],
        ok: true,
        status: "ready",
        webcams: {
          error: null,
          payload: { ok: true, webcams: [{ id: "cam-1" }] },
          status: "fresh",
        },
      }),
      fulfilled({
        error: "radar offline",
        fromCache: true,
        payload: {
          available: true,
          products: [{ product_type: "SRI", time: "2026-09-14T18:00:00Z" }],
          tiles: { base_url: "https://example.test/{z}/{x}/{y}.png" },
        },
        status: "stale",
      }),
    ], ["live", "radar"]);

    expect(outcome).toEqual({
      components: {
        community: "unavailable",
        radar: "retained",
        webcams: "settled",
      },
      ok: true,
      partial: true,
    });
  });

  it("does not promote a partial Events response to a complete refresh", () => {
    expect(getRuntimeRefreshCompletionOutcome([
      fulfilled({
        error: null,
        isPartial: true,
        isRefreshing: false,
        items: [{ id: "event-1" }],
        status: "partial",
      }),
    ], ["events"])).toEqual({
      components: { events: "partial" },
      ok: true,
      partial: true,
    });
  });

  it("reports deferred CAMS as pending without turning successful ICON into a failure", () => {
    expect(getRuntimeRefreshCompletionOutcome([
      fulfilled(visibleWeather({ camsStatus: "pending" })),
    ], ["weather"])).toEqual({
      components: {
        cams: "pending",
        icon: "settled",
      },
      ok: true,
      partial: true,
    });
  });

  it("does not transfer an uncommitted ICON candidate failure to valid CAMS data", () => {
    const weather = visibleWeather();
    weather.rawCurrent.cache = {
      runtime_fallback_code: "CACHE_PERSIST_FAILED",
      runtime_fallback_source: "candidate_not_committed",
    };

    expect(getRuntimeRefreshCompletionOutcome([
      fulfilled(weather),
      fulfilled(weather),
    ], ["weather", "cams"])).toEqual({
      components: {
        cams: "settled",
        icon: "failed",
      },
      ok: true,
      partial: true,
    });
  });
});
