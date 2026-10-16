import { describe, expect, it, vi } from "vitest";

import reverseFvgSuccessFixture from "../../../contracts/runtime-api/v1/location/reverse-fvg-success.json";

import {
  buildReverseLocationUrl,
  getReverseLocationCacheKey,
  isFvgReverseLocation,
  LOCATION_REVERSE_CACHE_MAX_AGE_MS,
  LOCATION_REVERSE_CACHE_PREFIX,
  normalizeReverseLocationPayload,
  resolveReverseLocation,
} from "./reverseLocation";

function createStorage(initial = {}) {
  const items = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => (items.has(key) ? items.get(key) : null)),
    setItem: vi.fn((key, value) => {
      items.set(key, value);
    }),
    removeItem: vi.fn((key) => {
      items.delete(key);
    }),
  };
}

describe("reverse location service", () => {
  it("uses boundary-safe precision for the reverse cache key", () => {
    expect(LOCATION_REVERSE_CACHE_PREFIX).toBe("locationReverseCache:v3");
    expect(getReverseLocationCacheKey(46.069312, 13.237221)).toBe(
      `${LOCATION_REVERSE_CACHE_PREFIX}:46.069312:13.237221`,
    );
  });

  it("builds the backend reverse geocoding URL", () => {
    expect(buildReverseLocationUrl({ apiBase: "/api/" })).toBe(
      "/api/location/reverse",
    );
  });

  it("normalizes backend payloads and marks FVG results explicitly", () => {
    expect(normalizeReverseLocationPayload(
      { city: "Pordenone", region: "Friuli Venezia Giulia", lat: "45.9567", lon: "12.6605" },
      { source: "browser_geolocation" },
    )).toEqual({
      city: "Pordenone",
      displayName: "Pordenone",
      region: "Friuli Venezia Giulia",
      lat: 45.9567,
      locality: { name: "Pordenone" },
      lon: 12.6605,
      municipality: { name: "Pordenone" },
      source: "browser_geolocation",
      insideFvg: true,
    });
    expect(normalizeReverseLocationPayload({
      city: "Cordenons",
      region: "Friuli Venezia Giulia",
      province: "PN",
      provinceName: "Pordenone",
      istatCode: "093017",
    })).toMatchObject({
      province: "PN",
      provinceName: "Pordenone",
      istatCode: "093017",
    });

    expect(isFvgReverseLocation({ region: "Veneto" })).toBe(false);
  });

  it("keeps the visible locality separate from its canonical municipality", () => {
    expect(normalizeReverseLocationPayload({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      region: "Friuli Venezia Giulia",
      lat: 45.9892108,
      lon: 12.5473156,
      dataPoint: {
        lat: 45.9888,
        lon: 12.548,
        source: "rafvg_irdat_5000",
      },
      locality: {
        id: "irdat:vigonovo",
        name: "Vigonovo",
        kind: "settlement",
        source: "rafvg_irdat_5000",
        datasetVersion: "2006",
      },
      municipality: {
        name: "Fontanafredda",
        istatCode: "093022",
        province: "PN",
        provinceName: "Pordenone",
        source: "istat_boundaries",
        datasetVersion: "2026-01-01",
      },
      resolution: {
        status: "resolved",
        municipalityResolved: true,
        localityCorroborated: true,
        boundaryDistanceM: "84.5",
      },
    })).toMatchObject({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      istatCode: "093022",
      lat: 45.9888,
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      lon: 12.548,
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      resolution: { boundaryDistanceM: 84.5, localityCorroborated: true },
    });
  });

  it("uses only the canonical data point for app weather coordinates", () => {
    const location = normalizeReverseLocationPayload({
      city: "Claut",
      displayName: "Cellino di Sopra",
      region: "Friuli Venezia Giulia",
      lat: 46.2479446,
      lon: 12.4703415,
      dataPoint: {
        lat: 46.24823,
        lon: 12.46971,
        source: "rafvg_irdat_5000",
      },
    });

    expect(location).toMatchObject({
      dataPoint: {
        lat: 46.24823,
        lon: 12.46971,
        source: "rafvg_irdat_5000",
      },
      lat: 46.24823,
      lon: 12.46971,
    });
    expect(location.lat).not.toBe(46.2479446);
    expect(location.lon).not.toBe(12.4703415);
  });

  it("normalizes an external GPS result without retaining the precise fix as weather point", () => {
    const location = normalizeReverseLocationPayload({
      city: "Bologna",
      displayName: "Bologna",
      region: "Emilia-Romagna",
      lat: 44.4949188,
      lon: 11.3429472,
      locality: null,
      municipality: null,
      dataPoint: {
        lat: 44.4938203,
        lon: 11.3426327,
        source: "nominatim_place",
      },
      resolution: {
        status: "external_place",
        municipalityResolved: false,
        localityCorroborated: false,
        matchMethod: "nearest",
        distanceM: 124,
      },
    }, { source: "capacitor_geolocation" });

    expect(location).toMatchObject({
      city: "Bologna",
      dataPoint: {
        lat: 44.4938203,
        lon: 11.3426327,
        source: "nominatim_place",
      },
      insideFvg: false,
      lat: 44.4938203,
      lon: 11.3426327,
      municipality: null,
      resolution: { status: "external_place" },
    });
    expect(location.lat).not.toBe(44.4949188);
    expect(location.lon).not.toBe(11.3429472);
  });

  it("uses cached reverse geocoding before the network", async () => {
    const cacheKey = getReverseLocationCacheKey(46.0693, 13.2372);
    const storage = createStorage({
      [cacheKey]: JSON.stringify({
        savedAt: 1000,
        data: {
          city: "Udine",
          region: "Friuli Venezia Giulia",
          lat: 46.0693,
          lon: 13.2372,
        },
      }),
    });
    const fetchImpl = vi.fn();

    const result = await resolveReverseLocation(
      { lat: 46.0693, lon: 13.2372 },
      {
        fetchImpl,
        now: () => 1000 + LOCATION_REVERSE_CACHE_MAX_AGE_MS - 1,
        storage,
      },
    );

    expect(result).toMatchObject({
      ok: true,
      fromCache: true,
      location: {
        city: "Udine",
        insideFvg: true,
      },
    });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("fetches, normalizes and stores reverse geocoding results", async () => {
    const storage = createStorage();
    const resolvedPayload = {
      ...reverseFvgSuccessFixture,
      locality: {
        id: "irdat:pordenone",
        name: "Pordenone",
        kind: "settlement",
        source: "rafvg_irdat_5000",
        datasetVersion: "2006",
      },
      resolution: {
        ...reverseFvgSuccessFixture.resolution,
        status: "resolved",
        localityCorroborated: true,
      },
    };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => resolvedPayload,
    });

    const result = await resolveReverseLocation(
      { lat: reverseFvgSuccessFixture.lat, lon: reverseFvgSuccessFixture.lon },
      {
        apiBase: "/api",
        fetchImpl,
        now: () => 42,
        source: "android_current_location",
        storage,
      },
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/location/reverse",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: 45.9567, lon: 12.6605 }),
      },
    );
    expect(result).toMatchObject({
      ok: true,
      fromCache: false,
      location: {
        city: "Pordenone",
        source: "android_current_location",
        insideFvg: true,
      },
    });
    expect(storage.setItem).toHaveBeenCalledTimes(1);
    expect(storage.setItem.mock.calls[0][0]).toBe(
      getReverseLocationCacheKey(45.9567, 12.6605),
    );
    const cachedReverse = JSON.parse(storage.setItem.mock.calls[0][1]);
    expect(cachedReverse).toMatchObject({
      savedAt: 42,
      data: {
        city: "Pordenone",
        dataPoint: resolvedPayload.dataPoint,
        lat: resolvedPayload.dataPoint.lat,
        lon: resolvedPayload.dataPoint.lon,
        locality: resolvedPayload.locality,
        municipality: resolvedPayload.municipality,
        resolution: {
          localityCorroborated: true,
          status: "resolved",
        },
      },
    });
    expect(cachedReverse.data.lat).not.toBe(resolvedPayload.lat);
    expect(cachedReverse.data.lon).not.toBe(resolvedPayload.lon);
  });

  it("forwards GPS accuracy for offline locality disambiguation", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => reverseFvgSuccessFixture,
    });

    await resolveReverseLocation(
      { lat: 46.2479446, lon: 12.4703415, accuracyM: 18.5 },
      { cacheEnabled: false, fetchImpl },
    );

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toEqual({
      lat: 46.2479446,
      lon: 12.4703415,
      accuracyM: 18.5,
    });
  });

  it("does not cache a municipality-only fallback", async () => {
    const storage = createStorage();
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...reverseFvgSuccessFixture,
        displayName: "Pordenone",
        locality: null,
        resolution: {
          ...reverseFvgSuccessFixture.resolution,
          status: "municipality_only",
          localityCorroborated: false,
        },
      }),
    });

    await resolveReverseLocation(
      { lat: 45.9567, lon: 12.6605, accuracyM: 80 },
      { fetchImpl, now: () => 42, storage },
    );

    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("does not pretend a failed reverse lookup is an FVG municipality", async () => {
    const result = await resolveReverseLocation(
      { lat: 45.44, lon: 12.31 },
      {
        fetchImpl: vi.fn().mockRejectedValue(new Error("offline")),
      },
    );

    expect(result).toMatchObject({
      ok: false,
      fromCache: false,
      error: "offline",
      location: {
        city: "Posizione attuale",
        region: "Italia",
        insideFvg: false,
      },
    });
  });

  it("forwards an abort signal only when automatic tracking supplies one", async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => reverseFvgSuccessFixture,
    });

    await resolveReverseLocation(
      { lat: reverseFvgSuccessFixture.lat, lon: reverseFvgSuccessFixture.lon },
      {
        fetchImpl,
        signal: controller.signal,
        storage: createStorage(),
      },
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/location/reverse",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: 45.9567, lon: 12.6605 }),
        signal: controller.signal,
      },
    );
  });

  it("does not persist coordinate history for automatic checks", async () => {
    const storage = createStorage();

    await resolveReverseLocation(
      { lat: reverseFvgSuccessFixture.lat, lon: reverseFvgSuccessFixture.lon },
      {
        cacheEnabled: false,
        fetchImpl: vi.fn().mockResolvedValue({
          ok: true,
          json: async () => reverseFvgSuccessFixture,
        }),
        storage,
      },
    );

    expect(storage.getItem).not.toHaveBeenCalled();
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("normalizes an aborted reverse request without leaking browser text", async () => {
    const result = await resolveReverseLocation(
      { lat: 45.9567, lon: 12.6605 },
      {
        fetchImpl: vi.fn().mockRejectedValue(new DOMException("The user aborted a request", "AbortError")),
      },
    );

    expect(result).toMatchObject({ ok: false, error: "aborted" });
  });
});
