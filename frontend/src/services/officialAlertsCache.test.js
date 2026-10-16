import { describe, expect, it, vi } from "vitest";

import {
  REGIONAL_OFFICIAL_ALERTS_CACHE_KEY,
  hydrateOfficialAlertsFromRegionalCache,
  readRegionalOfficialAlertsCache,
  reconcileRegionalOfficialAlerts,
  writeRegionalOfficialAlertsCache,
} from "./officialAlertsCache";

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

function activeAlert(level = "gialla", validTo = "2026-08-21T23:59:00+02:00") {
  return {
    active: true,
    alerts: [{ id: `alert-${level}`, level, valid_to: validTo }],
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

describe("regional official alerts cache", () => {
  it("stores one FVG-wide active alert without a location key", () => {
    const storage = createStorage();
    const alert = activeAlert();

    expect(writeRegionalOfficialAlertsCache(alert, { storage, now: () => NOW })).toBe(true);
    expect(storage.setItem).toHaveBeenCalledWith(
      REGIONAL_OFFICIAL_ALERTS_CACHE_KEY,
      expect.any(String),
    );
    expect(readRegionalOfficialAlertsCache({ storage, now: () => NOW })).toEqual(alert);
  });

  it("shows the same regional alert after a municipality changes", () => {
    const alert = activeAlert();
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(alert),
    });
    const pordenoneCache = { active: false, alerts: [], source_mode: "official_alerts_unavailable_fast_fallback" };
    const barcisCache = null;

    expect(hydrateOfficialAlertsFromRegionalCache(pordenoneCache, {
      storage,
      now: () => NOW,
    })).toEqual(alert);
    expect(hydrateOfficialAlertsFromRegionalCache(barcisCache, {
      storage,
      now: () => NOW,
    })).toEqual(alert);
  });

  it("keeps an active alert when a refresh is unavailable", () => {
    const alert = activeAlert();
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(alert),
    });
    const unavailable = {
      active: false,
      alerts: [],
      cache: { status: "unavailable" },
      error: "official_alerts_unavailable",
      source_mode: "official_alerts_unavailable_fast_fallback",
    };

    expect(reconcileRegionalOfficialAlerts(unavailable, null, {
      storage,
      now: () => NOW,
    })).toEqual(alert);
  });

  it("replaces the previous level with a newer active alert", () => {
    const yellow = activeAlert("gialla");
    const orange = activeAlert("arancione");
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(yellow),
    });

    expect(reconcileRegionalOfficialAlerts(orange, null, {
      storage,
      now: () => NOW,
    })).toEqual(orange);
    expect(readRegionalOfficialAlertsCache({ storage, now: () => NOW })).toEqual(orange);
  });

  it("keeps a confirmed inactive tombstone from reviving an older municipal alert", () => {
    const inactive = confirmedInactive();
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(inactive),
    });

    expect(hydrateOfficialAlertsFromRegionalCache(activeAlert(), {
      storage,
      now: () => NOW,
    })).toEqual(inactive);
  });

  it("removes an active alert once its official validity expires", () => {
    const expired = activeAlert("arancione", "2026-08-20T19:00:00+02:00");
    const storage = createStorage({
      [REGIONAL_OFFICIAL_ALERTS_CACHE_KEY]: cacheEntry(expired),
    });

    expect(readRegionalOfficialAlertsCache({ storage, now: () => NOW })).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY);
  });

  it("does not persist an active payload without an official expiry", () => {
    const storage = createStorage();
    const incomplete = {
      active: true,
      alerts: [{ id: "missing-validity", level: "gialla" }],
      source_mode: "official_widget",
    };

    expect(writeRegionalOfficialAlertsCache(incomplete, {
      storage,
      now: () => NOW,
    })).toBe(false);
    expect(storage.items.has(REGIONAL_OFFICIAL_ALERTS_CACHE_KEY)).toBe(false);
  });
});
