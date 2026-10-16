import { describe, expect, it, vi } from "vitest";
import { DEFAULT_APP_LOCATION } from "../app/appLocation";

import {
  buildBulletinForecastUrl,
  buildOfficialAlertsUrl,
  fetchBulletinPayload,
  fetchOfficialAlertsPayload,
} from "./bulletinApi";

function jsonResponse(payload, { ok = true } = {}) {
  return {
    ok,
    json: vi.fn().mockResolvedValue(payload),
  };
}

describe("bulletin api", () => {
  it("loads the first-run bulletin by municipality without inventing coordinates", async () => {
    const initialLocation = structuredClone(DEFAULT_APP_LOCATION);
    const forecast = { official: { it: { forecasts: [{ text: "Sole" }] } } };
    const fetchImpl = vi.fn(async (url) => jsonResponse(forecast, {
      ok: !new URL(url, "https://localhost").searchParams.has("lat"),
    }));

    await expect(fetchBulletinPayload(initialLocation, {
      apiBase: "/api",
      fetchImpl,
      includeAlerts: false,
      force: true,
      now: () => 123,
    })).resolves.toMatchObject({ city: "Udine", forecast });
    expect(fetchImpl).toHaveBeenCalledExactlyOnceWith(
      "/api/weather/forecast?city=Udine&_=123",
      { cache: "no-store" },
    );
    expect(initialLocation).toEqual(DEFAULT_APP_LOCATION);
    expect(initialLocation).toMatchObject({ lat: null, lon: null });
  });

  it.each([
    { label: "null", value: null },
    { label: "undefined", value: undefined },
    { label: "empty string", value: "" },
    { label: "whitespace", value: "  " },
    { label: "boolean", value: false },
    { label: "array", value: [] },
    { label: "object", value: {} },
    { label: "NaN", value: NaN },
    { label: "Infinity", value: Infinity },
  ])(
    "omits the coordinate pair when either value is missing or invalid ($label)",
    ({ value }) => {
      for (const coordinates of [{ lat: value, lon: 13.23715 }, { lat: 46.0693, lon: value }]) {
        expect(buildBulletinForecastUrl({ city: "Udine", ...coordinates }, { apiBase: "/api" }))
          .toBe("/api/weather/forecast?city=Udine");
      }
    },
  );

  it.each([
    [46.0693, 13.23715, "46.0693", "13.23715"],
    ["46.0693", "13.23715", "46.0693", "13.23715"],
    [0, 13.23715, "0", "13.23715"],
    [46.0693, 0, "46.0693", "0"],
  ])("preserves explicitly provided finite coordinates (%s, %s)", (lat, lon, expectedLat, expectedLon) => {
    const url = new URL(buildBulletinForecastUrl({ city: "Udine", lat, lon }, { apiBase: "/api" }), "https://localhost");
    expect(url.searchParams.get("lat")).toBe(expectedLat);
    expect(url.searchParams.get("lon")).toBe(expectedLon);
  });

  it("builds separate forecast and alert URLs", () => {
    const location = {
      city: "Fontanafredda",
      displayName: "Vigonovo",
      lat: 45.9892,
      lon: 12.5473,
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
    };

    expect(buildBulletinForecastUrl(location, { apiBase: "/api" })).toBe(
      "/api/weather/forecast?city=Fontanafredda&lat=45.9892&lon=12.5473",
    );
    expect(buildOfficialAlertsUrl({ apiBase: "/api" })).toBe(
      "/api/weather/official-alerts",
    );
  });

  it("adds an explicit cache buster for forced refreshes", () => {
    expect(buildBulletinForecastUrl("Udine", {
      apiBase: "/api/",
      force: true,
      now: () => 123,
    })).toContain("_=123");
    expect(buildOfficialAlertsUrl({
      apiBase: "/api/",
      force: true,
      now: () => 123,
    })).toBe("/api/weather/official-alerts?_=123");
  });

  it("loads official alerts without requesting the OSMER forecast", async () => {
    const payload = {
      active: true,
      alerts: [{ id: "regional-yellow", level: "gialla" }],
      source_mode: "official_widget",
    };
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(payload));

    await expect(fetchOfficialAlertsPayload({
      apiBase: "/api",
      fetchImpl,
      force: true,
      now: () => 123,
    })).resolves.toEqual(payload);
    expect(fetchImpl).toHaveBeenCalledOnce();
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/weather/official-alerts?_=123",
      { cache: "no-store" },
    );
  });

  it("fails explicitly when the endpoint-only official-alert request is unavailable", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({}, { ok: false }));

    await expect(fetchOfficialAlertsPayload({
      apiBase: "/api",
      fetchImpl,
    })).rejects.toThrow("Risposta allerte ufficiali non valida");
  });

  it("loads the official forecast even when the alert endpoint is unavailable", async () => {
    const forecast = { official: { it: { forecasts: [{ text: "Sole" }] } } };
    const fetchImpl = vi.fn((url) => (
      url.includes("official-alerts")
        ? Promise.resolve(jsonResponse({}, { ok: false }))
        : Promise.resolve(jsonResponse(forecast))
    ));

    await expect(fetchBulletinPayload({ city: "Udine" }, {
      apiBase: "/api",
      fetchImpl,
    })).resolves.toMatchObject({
      city: "Udine",
      forecast,
      officialAlerts: null,
    });
  });

  it("can load only the OSMER forecast when official alerts are managed separately", async () => {
    const forecast = { official: { it: { forecasts: [{ text: "Sole" }] } } };
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(forecast));

    await expect(fetchBulletinPayload({ city: "Udine" }, {
      apiBase: "/api",
      fetchImpl,
      force: true,
      includeAlerts: false,
      now: () => 123,
    })).resolves.toMatchObject({
      city: "Udine",
      forecast,
      officialAlerts: null,
    });

    expect(fetchImpl).toHaveBeenCalledOnce();
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/weather/forecast?city=Udine&_=123",
      { cache: "no-store" },
    );
    expect(fetchImpl.mock.calls.some(([url]) => String(url).includes("official-alerts"))).toBe(false);
  });

  it("fails when the forecast endpoint is unavailable", async () => {
    const fetchImpl = vi.fn((url) => (
      url.includes("official-alerts")
        ? Promise.resolve(jsonResponse({ active: false, alerts: [] }))
        : Promise.resolve(jsonResponse({}, { ok: false }))
    ));

    await expect(fetchBulletinPayload("Udine", {
      apiBase: "/api",
      fetchImpl,
    })).rejects.toThrow("Risposta bollettino OSMER non valida");
  });
});
