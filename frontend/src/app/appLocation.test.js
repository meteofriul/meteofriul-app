import { describe, expect, it, vi } from "vitest";

import {
  APP_AUTO_LOCATION_STORAGE_KEY,
  APP_LOCATION_STORAGE_KEY,
  APP_RECENT_LOCATIONS_STORAGE_KEY,
  appendStoredRecentLocation,
  DEFAULT_APP_LOCATION,
  normalizeAppLocation,
  readInitialAppLocation,
  readStoredAutoLocationEnabled,
  readStoredRecentLocations,
  readStoredAppLocation,
  removeStoredRecentLocation,
  writeStoredAutoLocationEnabled,
  writeStoredAppLocation,
} from "./appLocation";

function createStorage(initial = {}) {
  const items = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => (items.has(key) ? items.get(key) : null)),
    setItem: vi.fn((key, value) => {
      items.set(key, value);
    }),
  };
}

describe("app location", () => {
  it("normalizes stored location records from the legacy key", () => {
    expect(normalizeAppLocation({
      city: " Pordenone ",
      region: " Friuli Venezia Giulia ",
      lat: "45.9567",
      lon: "12.6605",
      source: "manual",
    })).toEqual({
      city: "Pordenone",
      displayName: "Pordenone",
      region: "Friuli Venezia Giulia",
      lat: 45.9567,
      locality: { name: "Pordenone" },
      lon: 12.6605,
      municipality: { name: "Pordenone" },
      source: "manual",
    });
  });

  it("does not turn missing coordinates into the Gulf of Guinea", () => {
    expect(normalizeAppLocation({ city: "Udine", lat: null, lon: "" })).toMatchObject({
      lat: null,
      lon: null,
    });
  });

  it("does not classify a national place with missing region as FVG", () => {
    expect(normalizeAppLocation({
      city: "Roma",
      countryCode: "IT",
      lat: 41.9028,
      lon: 12.4964,
      municipality: null,
      locality: null,
    })).toMatchObject({
      city: "Roma",
      countryCode: "IT",
      region: "",
    });
  });

  it("reads the old defaultLocation key without inventing a new storage contract", () => {
    const storage = createStorage({
      [APP_LOCATION_STORAGE_KEY]: JSON.stringify({ city: "Cordenons", source: "manual" }),
    });

    expect(readStoredAppLocation({ storage })).toMatchObject({
      city: "Cordenons",
      source: "manual",
    });
  });

  it("preserves municipality and province identity for localized content", () => {
    expect(normalizeAppLocation({
      city: "Cordenons",
      region: "Friuli Venezia Giulia",
      province: "pn",
      provinceName: "Pordenone",
      istatCode: "093017",
      source: "manual",
    })).toMatchObject({
      city: "Cordenons",
      province: "PN",
      provinceName: "Pordenone",
      istatCode: "093017",
    });
  });

  it("persists only the canonical public point for an automatic external place", () => {
    expect(normalizeAppLocation({
      city: "Bologna",
      displayName: "Bologna",
      region: "Emilia-Romagna",
      lat: 44.4949188,
      lon: 11.3429472,
      municipality: null,
      locality: null,
      dataPoint: {
        lat: 44.4938203,
        lon: 11.3426327,
        source: "nominatim_place",
      },
      resolution: { status: "external_place" },
      source: "capacitor_geolocation",
    })).toMatchObject({
      city: "Bologna",
      lat: 44.4938203,
      lon: 11.3426327,
      municipality: null,
      locality: null,
      dataPoint: { source: "nominatim_place" },
      resolution: { status: "external_place" },
    });
  });

  it("accepts the public Nominatim point selected by national search", () => {
    expect(normalizeAppLocation({
      city: "Roma",
      displayName: "Roma",
      region: "Lazio",
      country: "Italia",
      countryCode: "IT",
      dataPoint: {
        lat: 41.8933,
        lon: 12.4829,
        source: "nominatim_search",
      },
      source: "manual",
    })).toMatchObject({
      city: "Roma",
      region: "Lazio",
      countryCode: "IT",
      lat: 41.8933,
      lon: 12.4829,
      dataPoint: { source: "nominatim_search" },
    });
  });

  it("falls back to Udine when storage is missing or invalid", () => {
    expect(readInitialAppLocation({ storage: createStorage() })).toEqual(DEFAULT_APP_LOCATION);
    expect(readStoredAppLocation({ storage: createStorage() })).toBeNull();
    expect(DEFAULT_APP_LOCATION).toMatchObject({
      city: "Udine",
      source: "placeholder",
    });
    expect(readInitialAppLocation({
      storage: createStorage({ [APP_LOCATION_STORAGE_KEY]: "{" }),
    })).toEqual(DEFAULT_APP_LOCATION);
  });

  it("writes normalized manual locations into the legacy key", () => {
    const storage = createStorage();

    const written = writeStoredAppLocation({
      city: " Tarvisio ",
      region: " Friuli Venezia Giulia ",
      lat: "46.5057",
      lon: "13.5782",
    }, { storage });

    expect(written).toEqual({
      city: "Tarvisio",
      displayName: "Tarvisio",
      region: "Friuli Venezia Giulia",
      lat: 46.5057,
      locality: { name: "Tarvisio" },
      lon: 13.5782,
      municipality: { name: "Tarvisio" },
      source: "manual",
    });
    expect(storage.setItem).toHaveBeenCalledWith(APP_LOCATION_STORAGE_KEY, JSON.stringify(written));
  });

  it("does not clear the automatic location preference when a manual location is saved", () => {
    const storage = createStorage({
      [APP_AUTO_LOCATION_STORAGE_KEY]: "true",
    });

    writeStoredAppLocation({ city: "Gorizia", source: "manual" }, { storage });

    expect(readStoredAutoLocationEnabled({ storage })).toBe(true);
  });

  it("reads and writes the legacy automatic location preference", () => {
    const storage = createStorage({
      [APP_AUTO_LOCATION_STORAGE_KEY]: "true",
    });

    expect(readStoredAutoLocationEnabled({ storage })).toBe(true);
    expect(writeStoredAutoLocationEnabled(false, { storage })).toBe(true);
    expect(storage.setItem).toHaveBeenCalledWith(APP_AUTO_LOCATION_STORAGE_KEY, "false");
    expect(readStoredAutoLocationEnabled({ storage })).toBe(false);
  });

  it("falls back safely when automatic-location storage cannot be read", () => {
    expect(readStoredAutoLocationEnabled({
      storage: {
        getItem: () => {
          throw new DOMException("blocked", "SecurityError");
        },
      },
    })).toBe(false);
  });

  it("keeps recent manual locations deduplicated with newest first", () => {
    const storage = createStorage({
      [APP_RECENT_LOCATIONS_STORAGE_KEY]: JSON.stringify([
        { city: "Udine", region: "Friuli Venezia Giulia" },
        { city: "Pordenone", region: "Friuli Venezia Giulia" },
      ]),
    });

    const recentLocations = appendStoredRecentLocation({
      city: " Udine ",
      region: "Friuli Venezia Giulia",
      source: "manual",
    }, { storage });

    expect(recentLocations.map((location) => location.city)).toEqual(["Udine", "Pordenone"]);
    expect(readStoredRecentLocations({ storage }).map((location) => location.city)).toEqual(["Udine", "Pordenone"]);
  });

  it("replaces an old municipality recent only after a matching ISTAT identity is selected", () => {
    const storage = createStorage({
      [APP_RECENT_LOCATIONS_STORAGE_KEY]: JSON.stringify([
        { city: "Urbino", displayName: "Urbino", region: "Marche", province: "PU",
          countryCode: "IT", lat: 43.725, lon: 12.636, source: "manual" },
      ]),
    });
    const verified = {
      city: "Urbino", displayName: "Urbino", region: "Marche", province: "PU",
      countryCode: "IT", istatCode: "041067",
      municipality: { name: "Urbino", province: "PU", istatCode: "041067" },
      lat: 43.726, lon: 12.637, source: "manual",
    };

    expect(appendStoredRecentLocation(verified, { storage })).toMatchObject([
      { city: "Urbino", istatCode: "041067" },
    ]);
    expect(readStoredRecentLocations({ storage })).toHaveLength(1);
  });

  it("hides a pre-existing duplicate only when the verified municipality is unambiguous", () => {
    const storage = createStorage({
      [APP_RECENT_LOCATIONS_STORAGE_KEY]: JSON.stringify([
        { city: "Urbino", region: "Marche", province: "PU", istatCode: "041067" },
        { city: "Urbino", region: "Marche", province: "PU" },
      ]),
    });

    expect(readStoredRecentLocations({ storage })).toMatchObject([
      { city: "Urbino", istatCode: "041067" },
    ]);
  });

  it("preserves uncertain homonyms and a distinct settlement", () => {
    const storage = createStorage({
      [APP_RECENT_LOCATIONS_STORAGE_KEY]: JSON.stringify([
        { city: "Urbino", displayName: "Urbino", region: "Marche", province: "PU",
          istatCode: "041067" },
        { city: "Urbino", displayName: "Urbino", region: "Marche", province: "AN" },
        { city: "Urbino", displayName: "Urbino", region: "Marche" },
        { city: "Urbino", displayName: "Pallino", region: "Marche", province: "PU",
          locality: { name: "Pallino", kind: "settlement" } },
      ]),
    });

    expect(readStoredRecentLocations({ storage }).map((location) => ({
      name: location.displayName, province: location.province || "",
    }))).toEqual([
      { name: "Urbino", province: "PU" },
      { name: "Urbino", province: "AN" },
      { name: "Urbino", province: "" },
      { name: "Pallino", province: "PU" },
    ]);
  });

  it("keeps same-name national places distinct by territorial identity", () => {
    const storage = createStorage();

    appendStoredRecentLocation({
      city: "San Pietro",
      countryCode: "IT",
      region: "Lazio",
      source: "manual",
    }, { storage });
    const locations = appendStoredRecentLocation({
      city: "San Pietro",
      countryCode: "IT",
      region: "Sicilia",
      source: "manual",
    }, { storage });

    expect(locations).toHaveLength(2);
    expect(locations.map((location) => location.region)).toEqual(["Sicilia", "Lazio"]);
  });

  it("does not infer FVG from a national municipality identity", () => {
    expect(normalizeAppLocation({
      city: "Roma",
      countryCode: "IT",
      municipality: {
        name: "Roma",
        istatCode: "058091",
        province: "RM",
        provinceName: "Roma",
      },
      source: "manual",
    })).toMatchObject({
      city: "Roma",
      countryCode: "IT",
      region: "",
    });
  });

  it("keeps distinct localities inside the same municipality separate", () => {
    const storage = createStorage({
      [APP_RECENT_LOCATIONS_STORAGE_KEY]: JSON.stringify([{
        city: "Fontanafredda",
        displayName: "Vigonovo",
        locality: { id: "locality:vigonovo", name: "Vigonovo" },
        municipality: { istatCode: "093022", name: "Fontanafredda" },
      }]),
    });

    const recentLocations = appendStoredRecentLocation({
      city: "Fontanafredda",
      displayName: "Talmasson",
      locality: { id: "locality:talmasson", name: "Talmasson" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      source: "manual",
    }, { storage });

    expect(recentLocations.map((location) => location.displayName)).toEqual([
      "Talmasson",
      "Vigonovo",
    ]);
  });

  it("preserves verified locality, municipality and resolution metadata", () => {
    expect(normalizeAppLocation({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      istatCode: "093022",
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
      dataPoint: {
        lat: 45.9888,
        lon: 12.548,
        source: "rafvg_irdat_5000",
      },
      lat: 45.9892108,
      lon: 12.5473156,
      resolution: {
        status: "resolved",
        municipalityResolved: true,
        localityCorroborated: true,
        boundaryDistanceM: "84.5",
      },
      positionAccuracyM: "12.5",
      positionCapturedAt: "2026-08-16T10:00:00+00:00",
      source: "capacitor_geolocation",
    })).toMatchObject({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      dataPoint: {
        lat: 45.9888,
        lon: 12.548,
        source: "rafvg_irdat_5000",
      },
      lat: 45.9888,
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      lon: 12.548,
      resolution: {
        status: "resolved",
        municipalityResolved: true,
        localityCorroborated: true,
        boundaryDistanceM: 84.5,
      },
      positionAccuracyM: 12.5,
      positionCapturedAt: "2026-08-16T10:00:00.000Z",
    });
  });

  it("drops legacy precise GPS coordinates until a canonical data point is available", () => {
    expect(normalizeAppLocation({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      lat: 45.9892108,
      lon: 12.5473156,
      source: "capacitor_geolocation",
    })).toMatchObject({
      lat: null,
      lon: null,
      source: "capacitor_geolocation",
    });
  });

  it("drops legacy precise coordinates from a GPS place reselected from recent locations", () => {
    expect(normalizeAppLocation({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      lat: 45.9892108,
      lon: 12.5473156,
      source: "manual_recent",
    })).toMatchObject({
      lat: null,
      lon: null,
      source: "manual_recent",
    });
  });

  it("repairs a stored manual municipality with its public catalog coordinates", () => {
    const storage = createStorage({
      [APP_LOCATION_STORAGE_KEY]: JSON.stringify({
        city: "Valvasone Arzene",
        displayName: "Valvasone Arzene",
        istatCode: "093053",
        lat: null,
        lon: null,
        locality: {
          name: "Valvasone Arzene",
          kind: "municipality",
          source: "manual_search",
        },
        municipality: {
          name: "Valvasone Arzene",
          istatCode: "093053",
          province: "PN",
          provinceName: "Pordenone",
        },
        source: "manual_recent",
      }),
    });

    expect(readStoredAppLocation({ storage })).toMatchObject({
      city: "Valvasone Arzene",
      dataPoint: {
        lat: 45.99648,
        lon: 12.85846,
        source: "municipality_catalog",
      },
      lat: 45.99648,
      lon: 12.85846,
      source: "manual_recent",
    });
  });

  it("does not replace a distinct recent locality with its municipality centroid", () => {
    expect(normalizeAppLocation({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      istatCode: "093022",
      lat: 45.9892108,
      lon: 12.5473156,
      locality: { name: "Vigonovo", kind: "settlement" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      source: "manual_recent",
    })).toMatchObject({
      lat: null,
      lon: null,
      source: "manual_recent",
    });
  });

  it("preserves an explicit municipality-only resolution without inventing a locality", () => {
    expect(normalizeAppLocation({
      city: "Pordenone",
      displayName: "Pordenone",
      locality: null,
      municipality: { istatCode: "093033", name: "Pordenone" },
      resolution: {
        status: "municipality_only",
        municipalityResolved: true,
        localityCorroborated: false,
        boundaryDistanceM: 1378.778,
      },
      source: "android_current_location",
    })).toMatchObject({
      city: "Pordenone",
      locality: null,
      municipality: { istatCode: "093033", name: "Pordenone" },
      resolution: {
        status: "municipality_only",
        boundaryDistanceM: 1378.778,
      },
    });
  });

  it("keeps only the latest six recent locations", () => {
    const storage = createStorage({
      [APP_RECENT_LOCATIONS_STORAGE_KEY]: JSON.stringify([
        { city: "Udine", region: "Friuli Venezia Giulia" },
        { city: "Pordenone", region: "Friuli Venezia Giulia" },
        { city: "Trieste", region: "Friuli Venezia Giulia" },
        { city: "Gorizia", region: "Friuli Venezia Giulia" },
        { city: "Tarvisio", region: "Friuli Venezia Giulia" },
        { city: "Lignano Sabbiadoro", region: "Friuli Venezia Giulia" },
      ]),
    });

    const recentLocations = appendStoredRecentLocation({
      city: "Tolmezzo",
      region: "Friuli Venezia Giulia",
      source: "manual",
    }, { storage });

    expect(recentLocations.map((location) => location.city)).toEqual([
      "Tolmezzo",
      "Udine",
      "Pordenone",
      "Trieste",
      "Gorizia",
      "Tarvisio",
    ]);
  });

  it("removes a recent location without changing the active location contract", () => {
    const storage = createStorage({
      [APP_LOCATION_STORAGE_KEY]: JSON.stringify({ city: "Pordenone", source: "manual" }),
      [APP_RECENT_LOCATIONS_STORAGE_KEY]: JSON.stringify([
        { city: "Pordenone", region: "Friuli Venezia Giulia" },
        { city: "Tarvisio", region: "Friuli Venezia Giulia" },
      ]),
    });

    const recentLocations = removeStoredRecentLocation({
      city: "Pordenone",
      region: "Friuli Venezia Giulia",
    }, { storage });

    expect(recentLocations.map((location) => location.city)).toEqual(["Tarvisio"]);
    expect(readStoredAppLocation({ storage })).toMatchObject({ city: "Pordenone" });
  });
});
