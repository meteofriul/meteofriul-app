import { describe, expect, it } from "vitest";
import {
  AUTO_LOCATION_FOREGROUND_RECHECK_MS,
  getGpsLocationQualityDecision,
  isManualDefaultLocationRecord,
  isSameResolvedPlace,
  shouldReplaceResolvedPlace,
  shouldKeepAutoLocationEnabledAfterFailure,
  shouldRunForegroundAutoLocationCheck,
} from "./autoLocationPolicy.js";

describe("autoLocationPolicy", () => {
  it("treats only manual records as startup default when automatic location is enabled", () => {
    expect(isManualDefaultLocationRecord(
      { city: "Pordenone", source: "manual" },
      { autoLocationEnabled: true }
    )).toBe(true);

    expect(isManualDefaultLocationRecord(
      { city: "Pordenone", source: "gps" },
      { autoLocationEnabled: true }
    )).toBe(false);

    expect(isManualDefaultLocationRecord(
      { city: "Pordenone", source: "android_current_location" },
      { autoLocationEnabled: true }
    )).toBe(false);
  });

  it("keeps legacy source-less records only when automatic location is not enabled", () => {
    expect(isManualDefaultLocationRecord(
      { city: "Udine" },
      { autoLocationEnabled: false }
    )).toBe(true);

    expect(isManualDefaultLocationRecord(
      { city: "Udine" },
      { autoLocationEnabled: true }
    )).toBe(false);
  });

  it("keeps automatic location enabled for temporary failures only", () => {
    expect(shouldKeepAutoLocationEnabledAfterFailure("native_location_timeout")).toBe(true);
    expect(shouldKeepAutoLocationEnabledAfterFailure("permission_pending")).toBe(true);
    expect(shouldKeepAutoLocationEnabledAfterFailure("denied")).toBe(false);
    expect(shouldKeepAutoLocationEnabledAfterFailure("permission_denied")).toBe(false);
    expect(shouldKeepAutoLocationEnabledAfterFailure("unsupported")).toBe(false);
  });

  it("checks automatic device location on foreground only after the configured interval", () => {
    expect(shouldRunForegroundAutoLocationCheck({
      autoLocationEnabled: false,
      now: 1000,
      lastCheckedAt: 0,
    })).toBe(false);

    expect(shouldRunForegroundAutoLocationCheck({
      autoLocationEnabled: true,
      now: 1000,
      lastCheckedAt: 0,
    })).toBe(true);

    expect(shouldRunForegroundAutoLocationCheck({
      autoLocationEnabled: true,
      now: AUTO_LOCATION_FOREGROUND_RECHECK_MS + 999,
      lastCheckedAt: 1000,
    })).toBe(false);

    expect(shouldRunForegroundAutoLocationCheck({
      autoLocationEnabled: true,
      now: AUTO_LOCATION_FOREGROUND_RECHECK_MS + 1000,
      lastCheckedAt: 1000,
    })).toBe(true);
  });

  it("compares resolved places by city and compatible region, not exact device coordinates", () => {
    expect(isSameResolvedPlace(
      { city: "Pordenone", region: "Friuli Venezia Giulia", lat: 45.95 },
      { city: "pordenone", region: "Friuli Venezia Giulia", lat: 46.01 }
    )).toBe(true);

    expect(isSameResolvedPlace(
      { city: "Pordenone", region: "" },
      { city: "Pordenone", region: "Friuli Venezia Giulia" }
    )).toBe(true);

    expect(isSameResolvedPlace(
      { city: "Tarvisio", region: "Friuli Venezia Giulia" },
      { city: "Pordenone", region: "Friuli Venezia Giulia" }
    )).toBe(false);
  });

  it("distinguishes verified localities inside the same municipality", () => {
    const municipality = { istatCode: "093022", name: "Fontanafredda" };
    const vigonovo = {
      city: "Fontanafredda",
      displayName: "Vigonovo",
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality,
      source: "capacitor_geolocation",
    };
    const talmasson = {
      city: "Fontanafredda",
      displayName: "Talmasson",
      locality: { id: "irdat:talmasson", name: "Talmasson" },
      municipality,
      source: "capacitor_geolocation",
    };

    expect(isSameResolvedPlace(vigonovo, { ...vigonovo, lat: 45.99 })).toBe(true);
    expect(isSameResolvedPlace(vigonovo, talmasson)).toBe(false);
    expect(shouldReplaceResolvedPlace(vigonovo, talmasson)).toBe(true);
  });

  it("replaces an old locality with a reliable municipality-only result", () => {
    expect(shouldReplaceResolvedPlace({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      resolution: { status: "resolved", localityCorroborated: true },
      source: "capacitor_geolocation",
    }, {
      city: "Fontanafredda",
      displayName: "Fontanafredda",
      locality: null,
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      resolution: { status: "municipality_only", localityCorroborated: false },
      source: "capacitor_geolocation",
    })).toBe(true);
  });

  it("clears a same-name locality when only the municipality remains reliable", () => {
    expect(shouldReplaceResolvedPlace({
      city: "Pulfero",
      displayName: "Pulfero",
      locality: { id: "irdat:pulfero", name: "Pulfero" },
      municipality: { istatCode: "030086", name: "Pulfero" },
      resolution: { status: "resolved", localityCorroborated: true },
      source: "capacitor_geolocation",
    }, {
      city: "Pulfero",
      displayName: "Pulfero",
      locality: null,
      municipality: { istatCode: "030086", name: "Pulfero" },
      resolution: { status: "municipality_only", localityCorroborated: false },
      source: "capacitor_geolocation",
    })).toBe(true);
  });

  it("replaces a matching placeholder or manual city with the resolved GPS record", () => {
    const resolved = {
      city: "Udine",
      region: "Friuli Venezia Giulia",
      source: "android_current_location",
    };

    expect(shouldReplaceResolvedPlace({
      city: "Udine",
      region: "Friuli Venezia Giulia",
      source: "placeholder",
    }, resolved)).toBe(true);
    expect(shouldReplaceResolvedPlace({
      city: "Udine",
      region: "Friuli Venezia Giulia",
      source: "manual",
    }, resolved)).toBe(true);
    expect(shouldReplaceResolvedPlace({
      city: "Udine",
      region: "Friuli Venezia Giulia",
      source: "android_last_location",
    }, resolved)).toBe(false);
  });

  it("accepts fresh and precise device-location/native payloads without deciding the city", () => {
    expect(getGpsLocationQualityDecision({
      ok: true,
      lat: "46.0693",
      lon: "13.2372",
      age_ms: 2 * 60 * 1000,
      accuracy_m: 25,
    })).toEqual({
      usable: true,
      confidence: "fast",
      lat: 46.0693,
      lon: 13.2372,
      ageMs: 120000,
      accuracyM: 25,
    });

    expect(getGpsLocationQualityDecision({
      ok: true,
      lat: 46.0693,
      lon: 13.2372,
      ageMs: 1000,
      accuracyM: 250.01,
    })).toEqual({
      usable: false,
      confidence: "none",
      reason: "stale_or_imprecise",
    });
  });

  it("rejects stale, imprecise or incomplete device-location/native payloads", () => {
    expect(getGpsLocationQualityDecision({ ok: false, reason: "permission_denied" })).toEqual({
      usable: false,
      confidence: "none",
      reason: "permission_denied",
    });

    expect(getGpsLocationQualityDecision({
      ok: true,
      lat: 46.0693,
      lon: 13.2372,
      age_ms: 2 * 60 * 60 * 1000,
      accuracy_m: 20,
    })).toEqual({
      usable: false,
      confidence: "none",
      reason: "stale_or_imprecise",
    });

    expect(getGpsLocationQualityDecision({
      ok: true,
      lat: 46.0693,
      lon: 13.2372,
      age_ms: 1000,
    })).toEqual({
      usable: false,
      confidence: "none",
      reason: "missing_quality",
    });
  });
});
