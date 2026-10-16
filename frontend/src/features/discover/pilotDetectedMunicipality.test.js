import { describe, expect, it } from "vitest";

import { getPilotDetectedMunicipality } from "./pilotDetectedMunicipality";

function located(overrides = {}) {
  return {
    city: "Pordenone",
    countryCode: "IT",
    region: "Friuli Venezia Giulia",
    istatCode: "093033",
    source: "capacitor_geolocation",
    lat: 45.9567,
    lon: 12.6605,
    dataPoint: { lat: 45.9567, lon: 12.6605, source: "municipality_catalog" },
    municipality: { name: "Pordenone", istatCode: "093033", source: "istat_boundaries" },
    resolution: { status: "municipality_only", municipalityResolved: true, boundaryDistanceM: 400 },
    positionAccuracyM: 18,
    positionCapturedAt: "2026-09-20T10:00:00.000Z",
    ...overrides,
  };
}

function detect(location, status = "success", autoLocationEnabled = true) {
  return getPilotDetectedMunicipality({
    autoLocationEnabled,
    deviceLocationStatus: { status, location },
  });
}

describe("pilot detected municipality", () => {
  it.each(["browser_geolocation", "capacitor_geolocation", "android_current_location", "android_last_location"])(
    "accepts a supported municipality from a validated %s session result",
    (source) => {
      const location = located({ source });
      expect(detect(location)).toBe(location);
    },
  );

  it("accepts a corroborated locality without treating nearest-locality selection as a municipal fallback", () => {
    const location = located({
      displayName: "Località rilevata",
      dataPoint: { lat: 45.9567, lon: 12.6605, source: "rafvg_irdat_5000" },
      resolution: {
        status: "resolved",
        municipalityResolved: true,
        localityCorroborated: true,
        matchMethod: "nearest",
        boundaryDistanceM: 400,
      },
    });
    expect(detect(location)).toBe(location);
  });

  it("uses the exact resolved ISTAT even when its duplicate top-level key is absent", () => {
    const location = located();
    delete location.istatCode;
    expect(detect(location)).toMatchObject({ istatCode: "093033" });
    expect(location.istatCode).toBeUndefined();
  });

  it.each(["idle", "last_known", "loading", "denied", "error"])(
    "hides a previously valid municipality when device status is %s",
    (status) => expect(detect(located(), status)).toBeNull(),
  );

  it("requires automatic mode and an explicit session location without selected-location fallback", () => {
    expect(getPilotDetectedMunicipality()).toBeNull();
    expect(detect(located(), "success", false)).toBeNull();
    expect(getPilotDetectedMunicipality({
      autoLocationEnabled: true,
      deviceLocationStatus: { status: "success", city: "Pordenone" },
      activeLocation: located(),
      editorialLocation: located(),
    })).toBeNull();
  });

  it.each(["manual", "manual_recent", "placeholder", "", "gps"])(
    "does not reinterpret %s selections or persisted records as device evidence",
    (source) => expect(detect(located({ source }))).toBeNull(),
  );

  it("rejects Verona even when a supported editorial municipality remains elsewhere", () => {
    expect(detect(located({
      city: "Verona",
      region: "Veneto",
      istatCode: "023091",
      municipality: null,
      dataPoint: { lat: 45.4384, lon: 10.9916, source: "nominatim_place" },
      resolution: { status: "external_place", municipalityResolved: false, matchMethod: "nearest" },
    }))).toBeNull();
    expect(detect(located({ region: "Veneto" }))).toBeNull();
    expect(detect(located({ countryCode: "SI" }))).toBeNull();
  });

  it.each([
    { municipality: null },
    { municipality: { name: "Pordenone", istatCode: "093033", source: "nearest" } },
    { municipality: { name: "Unknown", istatCode: "093999", source: "istat_boundaries" } },
    { istatCode: "030129" },
    { resolution: { status: "outside_fvg", municipalityResolved: false, boundaryDistanceM: 400 } },
    { resolution: { status: "resolved", municipalityResolved: false, boundaryDistanceM: 400 } },
    { resolution: { status: "resolved", municipalityResolved: true } },
    { resolution: { status: "municipality_only", municipalityResolved: true, boundaryDistanceM: 28 } },
    { resolution: { status: "municipality_only", municipalityResolved: true, boundaryDistanceM: 20 } },
    { dataPoint: null },
    { dataPoint: { lat: 91, lon: 12.66, source: "municipality_catalog" } },
    { dataPoint: { lat: 45.95, lon: 12.66, source: "nominatim_place" } },
    { positionAccuracyM: null },
    { positionAccuracyM: "" },
    { positionAccuracyM: false },
    { positionAccuracyM: -1 },
    { positionAccuracyM: 251 },
    { positionCapturedAt: null },
    { positionCapturedAt: "invalid" },
  ])("rejects missing, ambiguous or unsupported evidence: %j", (overrides) => {
    expect(detect(located(overrides))).toBeNull();
  });

  it("does not impose a new expiry shorter than the existing automatic-location runtime", () => {
    const location = located({ positionCapturedAt: "2026-09-20T09:30:00.000Z" });
    expect(detect(location)).toBe(location);
    expect(detect(location, "last_known")).toBeNull();
  });
});
