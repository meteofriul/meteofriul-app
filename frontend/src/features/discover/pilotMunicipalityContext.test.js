import { describe, expect, it } from "vitest";

import { DEFAULT_APP_LOCATION, normalizeAppLocation } from "../../app/appLocation";
import { getPilotMunicipalityContext } from "./pilotMunicipalityContext";

function manual(overrides = {}) {
  return {
    city: "Pordenone", region: "Friuli Venezia Giulia", province: "PN",
    countryCode: "IT", istatCode: "093033", source: "manual",
    municipality: { name: "Pordenone", istatCode: "093033", province: "PN" },
    ...overrides,
  };
}

function gps(overrides = {}) {
  return {
    ...manual(),
    source: "capacitor_geolocation",
    municipality: { name: "Pordenone", istatCode: "093033", source: "istat_boundaries" },
    dataPoint: { lat: 45.9567, lon: 12.6605, source: "municipality_catalog" },
    resolution: { status: "municipality_only", municipalityResolved: true, boundaryDistanceM: 400 },
    positionAccuracyM: 18,
    positionCapturedAt: "2026-09-20T10:00:00.000Z",
    ...overrides,
  };
}

describe("pilot municipality context", () => {
  it("shows the normalized saved Pordenone manual default as selected", () => {
    const activeLocation = normalizeAppLocation(manual());
    expect(getPilotMunicipalityContext({ activeLocation })).toEqual({
      location: activeLocation, mode: "selected",
    });
  });

  it.each(["manual", "manual_recent", "manual_search", undefined])(
    "accepts supported manual and legacy sources: %s",
    (source) => {
      expect(getPilotMunicipalityContext({ activeLocation: manual({ source }) }))
        .toMatchObject({ mode: "selected", location: { istatCode: "093033" } });
    },
  );

  it("resolves an explicit FVG municipality name without inventing GPS evidence", () => {
    const activeLocation = { city: "udine", region: "Friuli Venezia Giulia" };
    expect(getPilotMunicipalityContext({ activeLocation })).toEqual({
      location: { city: "Udine", region: "Friuli Venezia Giulia", istatCode: "030129" },
      mode: "selected",
    });
    expect(activeLocation).not.toHaveProperty("istatCode");
  });

  it("supports municipality identity without a duplicate top-level ISTAT or city", () => {
    expect(getPilotMunicipalityContext({
      activeLocation: { source: "manual", province: "UD", municipality: { name: "Udine" } },
    })).toMatchObject({ mode: "selected", location: { city: "Udine", istatCode: "030129" } });
  });

  it("gives the successful current GPS municipality priority over the old manual selection", () => {
    const detected = gps({
      city: "Udine", province: "UD", istatCode: "030129",
      municipality: { name: "Udine", istatCode: "030129", source: "istat_boundaries" },
    });
    expect(getPilotMunicipalityContext({
      activeLocation: manual(), autoLocationEnabled: true,
      deviceLocationStatus: { status: "success", location: detected },
    })).toEqual({ location: detected, mode: "detected" });
  });

  it("never falls back to manual Pordenone after GPS successfully identifies Verona", () => {
    const verona = gps({
      city: "Verona", region: "Veneto", province: "VR", istatCode: "023091",
      municipality: null, resolution: { status: "external_place", municipalityResolved: false },
    });
    expect(getPilotMunicipalityContext({
      activeLocation: manual(), autoLocationEnabled: true,
      deviceLocationStatus: { status: "success", location: verona },
    })).toBeNull();
  });

  it("does not use a malformed success result as permission for a manual fallback", () => {
    expect(getPilotMunicipalityContext({
      activeLocation: manual(), autoLocationEnabled: true, deviceLocationStatus: { status: "success" },
    })).toBeNull();
  });

  it("uses the real active manual choice when automatic mode is off, ignoring an old GPS success", () => {
    const activeLocation = manual();
    expect(getPilotMunicipalityContext({
      activeLocation, autoLocationEnabled: false,
      deviceLocationStatus: { status: "success", location: gps() },
    })).toEqual({ location: activeLocation, mode: "selected" });
  });

  it.each(["idle", "last_known", "loading", "denied", "error"])(
    "does not reinterpret persisted GPS as manual after status %s",
    (status) => {
      expect(getPilotMunicipalityContext({
        activeLocation: gps(), autoLocationEnabled: true,
        deviceLocationStatus: { status, location: gps() },
      })).toBeNull();
      expect(getPilotMunicipalityContext({
        activeLocation: manual(), autoLocationEnabled: true,
        deviceLocationStatus: { status, location: gps() },
      })).toMatchObject({ mode: "selected" });
    },
  );

  it("keeps a disabled automatic GPS record and the unselected placeholder hidden", () => {
    expect(getPilotMunicipalityContext({
      activeLocation: gps(), deviceLocationStatus: { status: "success", location: gps() },
    })).toBeNull();
    expect(getPilotMunicipalityContext({ activeLocation: DEFAULT_APP_LOCATION })).toBeNull();
    expect(getPilotMunicipalityContext()).toBeNull();
  });

  it.each([
    { city: "Verona", region: "Veneto", province: "VR", istatCode: "023091", municipality: null },
    { countryCode: "SI" },
    { country: "Slovenia" },
    { countryCode: "IT", country_code: "AT" },
    { region: "Veneto" },
    { regionCode: "IT-36", region: "Veneto" },
    { regionCode: "IT-34" },
    { province: "UD" },
    { municipality: { name: "Pordenone", istatCode: "093033", province: "UD" } },
    { istatCode: "030129" },
    { istat: "030129" },
    { istatCode: "093999", municipality: null },
    { city: "Udine" },
    { municipality: { name: "Udine", istatCode: "093033" } },
    { source: "placeholder" },
    { source: "browser_geolocation" },
    { source: "android_current_location" },
  ])("rejects external, unsupported or contradictory manual identity: %j", (overrides) => {
    expect(getPilotMunicipalityContext({ activeLocation: manual(overrides) })).toBeNull();
  });

  it("does not resolve a bare city name or a foreign namesake using editorial fallback", () => {
    expect(getPilotMunicipalityContext({ activeLocation: { city: "Pordenone" } })).toBeNull();
    expect(getPilotMunicipalityContext({
      activeLocation: { city: "Pordenone", countryCode: "AR", region: "Friuli Venezia Giulia" },
      editorialLocation: manual(),
    })).toBeNull();
  });
});
